"""
Cell Painting assay simulator.

Simulates 5-channel morphology imaging (ER, Mito, Nucleus, Actin, RNA)
with realistic biological and technical noise.
"""

import re
import logging
import numpy as np
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

from .base import AssaySimulator
from .._impl import stable_u32, lognormal_multiplier
from ..run_context import pipeline_transform
from ...sim import biology_core
from ..constants import (
    ENABLE_ER_STRESS,
    ENABLE_MITO_DYSFUNCTION,
    ENABLE_TRANSPORT_DYSFUNCTION,
    ENABLE_INTERVENTION_COSTS,
    ER_STRESS_MORPH_ALPHA,
    MITO_DYSFUNCTION_MORPH_ALPHA,
    TRANSPORT_DYSFUNCTION_MORPH_ALPHA,
    WASHOUT_INTENSITY_PENALTY,
    WASHOUT_INTENSITY_RECOVERY_H,
)
from ..injections.segmentation_failure import SegmentationFailureInjection
from ..injections.base import InjectionContext

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


class CellPaintingAssay(AssaySimulator):
    """
    Cell Painting morphology assay simulator.

    Returns 5-channel morphology features:
    - ER (endoplasmic reticulum)
    - Mito (mitochondria)
    - Nucleus (nuclear morphology)
    - Actin (cytoskeleton)
    - RNA (translation sites)

    Includes realistic noise:
    - Biological variance (dose-dependent)
    - Technical noise (plate, day, operator, well)
    - Batch effects (run context, pipeline drift)
    - Artifacts (washout, plating stress, well failures)
    - Contact pressure bias (confluence confound)
    """

    def measure(self, vessel: "VesselState", **kwargs) -> Dict[str, Any]:
        """
        Simulate Cell Painting morphology assay.

        MEASUREMENT TIMING: This assay reads at t_measure = vm.simulated_time,
        which is t1 after advance_time() returns. This represents "readout after
        interval of biology." All time-dependent artifacts (washout, plating)
        use t_measure as reference.

        Args:
            vessel: Vessel state to measure
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with channel values and metadata
        """
        # Lock measurement purity - capture state before measurement
        state_before = (vessel.cell_count, vessel.viability, vessel.confluence)

        # Lazy load thalamus params
        if not hasattr(self.vm, 'thalamus_params') or self.vm.thalamus_params is None:
            self.vm._load_cell_thalamus_params()

        vessel_id = vessel.vessel_id
        cell_line = vessel.cell_line

        # Get baseline morphology for this cell line
        baseline = self.vm.thalamus_params['baseline_morphology'].get(cell_line, {})
        if not baseline:
            logger.warning(f"No baseline morphology for {cell_line}, using A549")
            baseline = self.vm.thalamus_params['baseline_morphology']['A549']

        # Start with baseline
        morph = {
            'er': baseline['er'],
            'mito': baseline['mito'],
            'nucleus': baseline['nucleus'],
            'actin': baseline['actin'],
            'rna': baseline['rna']
        }

        # Apply persistent per-well latent biology (BEFORE compound effects)
        # This creates stable well-to-well differences independent of treatment
        self._ensure_well_biology(vessel)
        morph = self._apply_well_biology_baseline(vessel, morph)

        # Apply compound effects via stress axes
        morph, has_microtubule_compound = self._apply_compound_effects(vessel, morph, baseline)

        # Apply latent stress state effects (morphology-first mechanisms)
        morph = self._apply_latent_stress_effects(vessel, morph)

        # Apply contact pressure bias (measurement confounder)
        morph = self._apply_contact_pressure_bias(vessel, morph)

        # Keep structural morphology (before viability scaling) for output
        morph_struct = morph.copy()

        # Compute transport dysfunction score for diagnostics
        transport_dysfunction_score = self._compute_transport_dysfunction_score(
            vessel, morph, baseline, has_microtubule_compound
        )

        # Apply measurement layer (viability + artifacts + noise)
        morph = self._apply_measurement_layer(vessel, morph, **kwargs)

        # Simulate delay
        self.vm._simulate_delay(2.0)

        # Assert measurement purity
        self._assert_measurement_purity(vessel, state_before)

        # Extract batch metadata
        plate_id = kwargs.get('plate_id', 'P1')
        batch_id = kwargs.get('batch_id', 'batch_default')

        result = {
            "status": "success",
            "action": "cell_painting",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            # Two-layer readout: structural (latent-driven) vs measured (intensity-scaled)
            "morphology_struct": morph_struct,
            "morphology_measured": morph,
            "morphology": morph,  # Backward compatibility
            "signal_intensity": 0.3 + 0.7 * vessel.viability,  # Viability factor
            "transport_dysfunction_score": transport_dysfunction_score,
            "death_mode": vessel.death_mode,
            "viability": vessel.viability,
            "timestamp": datetime.now().isoformat(),
            # Pipeline drift metadata for epistemic control
            "run_context_id": self.vm.run_context.context_id,
            "batch_id": batch_id,
            "plate_id": plate_id,
            "measurement_modifiers": self.vm.run_context.get_measurement_modifiers(),
        }

        # Check for well failure
        well_position = kwargs.get('well_position', 'A1')
        failure_result = self._apply_well_failure(morph, well_position, plate_id, batch_id)
        if failure_result:
            result['morphology'] = failure_result['morphology']
            result['morphology_measured'] = failure_result['morphology']
            result['well_failure'] = failure_result['failure_mode']
            result['qc_flag'] = 'FAIL'

        # Apply segmentation failure (adversarial measurement layer)
        # This changes sufficient statistics - not just noise
        segmentation_result = self._apply_segmentation_failure(vessel, result, **kwargs)
        if segmentation_result:
            result.update(segmentation_result)

        return result

    def _ensure_well_biology(self, vessel: "VesselState") -> None:
        """
        Create persistent per-well latent biology once (at 'plating').
        Uses a deterministic RNG stream if available, otherwise falls back to rng_assay.
        """
        if getattr(vessel, "well_biology", None) is not None:
            return

        # Prefer a deterministic per-well RNG if you have one.
        # If you don't, this still works, but reproducibility depends on call order.
        rng = getattr(vessel, "rng_well", None) or self.vm.rng_assay

        # These are fractional shifts (not multipliers yet).
        vessel.well_biology = {
            # Baseline morphology offsets (vehicle replicates should show this)
            "er_baseline_shift": float(rng.normal(0.0, 0.08)),       # ~8% sd
            "mito_baseline_shift": float(rng.normal(0.0, 0.10)),     # ~10% sd
            "rna_baseline_shift": float(rng.normal(0.0, 0.06)),      # ~6% sd

            # Nucleus sits in both stain and focus worlds but weaker
            "nucleus_baseline_shift": float(rng.normal(0.0, 0.04)),  # ~4% sd

            # Actin is more "structure" than "stain"
            "actin_baseline_shift": float(rng.normal(0.0, 0.05)),    # ~5% sd

            # Treatment response gain variation (lognormal so it's always positive)
            "stress_susceptibility": float(rng.lognormal(mean=0.0, sigma=0.15)),  # ~15% log-sd
        }

    def _apply_well_biology_baseline(self, vessel: "VesselState", morph: Dict[str, float]) -> Dict[str, float]:
        """Apply persistent per-well baseline shifts to morphology."""
        morph["er"] *= (1.0 + vessel.well_biology["er_baseline_shift"])
        morph["mito"] *= (1.0 + vessel.well_biology["mito_baseline_shift"])
        morph["rna"] *= (1.0 + vessel.well_biology["rna_baseline_shift"])
        morph["nucleus"] *= (1.0 + vessel.well_biology["nucleus_baseline_shift"])
        morph["actin"] *= (1.0 + vessel.well_biology["actin_baseline_shift"])
        return morph

    def _apply_compound_effects(
        self, vessel: "VesselState", morph: Dict[str, float], baseline: Dict[str, float]
    ) -> tuple[Dict[str, float], bool]:
        """Apply compound-induced morphology changes via stress axes."""
        # Read authoritative compound concentrations
        if self.vm.injection_mgr is not None and self.vm.injection_mgr.has_vessel(vessel.vessel_id):
            compounds_snapshot = self.vm.injection_mgr.get_all_compounds_uM(vessel.vessel_id)
        else:
            compounds_snapshot = vessel.compounds

        has_microtubule_compound = False

        for compound_name, dose_uM in compounds_snapshot.items():
            if dose_uM == 0:
                continue

            # Look up compound params
            compound_params = self.vm.thalamus_params['compounds'].get(compound_name, {})
            if not compound_params:
                logger.warning(f"Unknown compound for morphology: {compound_name}")
                continue

            stress_axis = compound_params['stress_axis']

            # Track microtubule compounds for transport dysfunction diagnostic
            if stress_axis == "microtubule":
                has_microtubule_compound = True
                continue  # Skip direct rendering (handled by latent state)

            # Get adjusted potency from vessel metadata
            meta = vessel.compound_meta.get(compound_name)
            if meta:
                ec50 = meta['ic50_uM']
                hill_slope = meta['hill_slope']
                potency_scalar = meta.get('potency_scalar', 1.0)
            else:
                ec50 = compound_params['ec50_uM']
                hill_slope = compound_params['hill_slope']
                potency_scalar = 1.0

            intensity = compound_params['intensity']
            axis_effects = self.vm.thalamus_params['stress_axes'][stress_axis]['channels']

            # Calculate dose response (Hill equation)
            dose_effect = intensity * potency_scalar * (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)

            # Apply to each channel
            for channel, axis_strength in axis_effects.items():
                morph[channel] *= (1.0 + dose_effect * axis_strength)

        return morph, has_microtubule_compound

    def _apply_latent_stress_effects(self, vessel: "VesselState", morph: Dict[str, float]) -> Dict[str, float]:
        """Apply latent stress state effects (morphology-first mechanisms)."""
        if ENABLE_ER_STRESS and vessel.er_stress > 0:
            morph['er'] *= (1.0 + ER_STRESS_MORPH_ALPHA * vessel.er_stress)

        if ENABLE_MITO_DYSFUNCTION and vessel.mito_dysfunction > 0:
            morph['mito'] *= max(0.1, 1.0 - MITO_DYSFUNCTION_MORPH_ALPHA * vessel.mito_dysfunction)

        if ENABLE_TRANSPORT_DYSFUNCTION and vessel.transport_dysfunction > 0:
            morph['actin'] *= (1.0 + TRANSPORT_DYSFUNCTION_MORPH_ALPHA * vessel.transport_dysfunction)

        return morph

    def _apply_contact_pressure_bias(self, vessel: "VesselState", morph: Dict[str, float]) -> Dict[str, float]:
        """Apply contact pressure-dependent morphology bias (measurement confounder)."""
        p = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        if p > 0.01:
            # Bounded, monotonic, channel-specific shifts
            shifts = {
                "nucleus": -0.08,
                "actin": +0.10,
                "er": +0.06,
                "mito": -0.05,
                "rna": -0.04,
            }
            for channel, coeff in shifts.items():
                if channel in morph:
                    morph[channel] = morph[channel] * (1.0 + coeff * p)
        return morph

    def _compute_transport_dysfunction_score(
        self, vessel: "VesselState", morph: Dict[str, float], baseline: Dict[str, float], has_microtubule: bool
    ) -> float:
        """Compute transport dysfunction score from morphology (diagnostic only)."""
        if has_microtubule:
            return biology_core.compute_transport_dysfunction_score(
                cell_line=vessel.cell_line,
                stress_axis="microtubule",
                actin_signal=morph['actin'],
                mito_signal=morph['mito'],
                baseline_actin=baseline['actin'],
                baseline_mito=baseline['mito']
            )
        return 0.0

    def _apply_measurement_layer(
        self, vessel: "VesselState", morph: Dict[str, float], **kwargs
    ) -> Dict[str, float]:
        """Apply measurement layer: viability scaling, washout artifacts, noise, batch effects."""
        t_measure = self.vm.simulated_time

        # 1. Viability factor (biological signal attenuation)
        viability_factor = 0.3 + 0.7 * vessel.viability

        # 2. Washout multiplier (measurement artifact)
        washout_multiplier = self._compute_washout_multiplier(vessel, t_measure)

        # Apply biology + measurement factors
        for channel in morph:
            morph[channel] *= viability_factor * washout_multiplier

        # 3. Biological noise (dose-dependent)
        morph = self._add_biological_noise(vessel, morph)

        # 4. Plating artifacts (early timepoint variance inflation)
        morph = self._add_plating_artifacts(vessel, morph, t_measure)

        # 5. Technical noise (plate/day/operator/well/edge effects)
        morph = self._add_technical_noise(vessel, morph, **kwargs)

        # 6. Pipeline drift (batch-dependent feature extraction)
        plate_id = kwargs.get('plate_id', 'P1')
        batch_id = kwargs.get('batch_id', 'batch_default')
        # DIAGNOSTIC: Bypass pipeline_transform to isolate per-channel coupling
        DIAGNOSTIC_DISABLE_SHARED_FACTORS = True  # Same flag as in _add_technical_noise
        if not DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            morph = pipeline_transform(
                morphology=morph,
                context=self.vm.run_context,
                batch_id=batch_id,
                plate_id=plate_id
            )
        # else: skip pipeline_transform (no-op)

        return morph

    def _compute_washout_multiplier(self, vessel: "VesselState", t_measure: float) -> float:
        """Compute washout artifact multiplier."""
        washout_multiplier = 1.0

        if ENABLE_INTERVENTION_COSTS and vessel.last_washout_time is not None:
            time_since_washout = t_measure - vessel.last_washout_time
            if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
                # Deterministic penalty
                recovery_fraction = time_since_washout / WASHOUT_INTENSITY_RECOVERY_H
                washout_penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
                washout_multiplier *= (1.0 - washout_penalty)

        # Stochastic contamination artifact
        if vessel.washout_artifact_until_time and t_measure < vessel.washout_artifact_until_time:
            remaining_time = vessel.washout_artifact_until_time - t_measure
            decay_fraction = remaining_time / WASHOUT_INTENSITY_RECOVERY_H
            artifact_effect = vessel.washout_artifact_magnitude * decay_fraction
            washout_multiplier *= (1.0 - artifact_effect)

        return washout_multiplier

    def _add_biological_noise(self, vessel: "VesselState", morph: Dict[str, float]) -> Dict[str, float]:
        """
        Structured biology:
        - Per-well baseline shifts already applied (in _apply_well_biology_baseline)
        - Stress susceptibility as gain on stress-induced morphology
        - Small residual biological noise (do NOT crank this into amplitude mush)
        """
        bio_cfg = self.vm.thalamus_params.get("biological_noise", {})
        base_residual_cv = float(bio_cfg.get("cell_line_cv", 0.04))  # keep modest
        stress_multiplier = float(bio_cfg.get("stress_cv_multiplier", 1.0))

        stress_level = max(0.0, min(1.0, 1.0 - vessel.viability))
        sus = vessel.well_biology["stress_susceptibility"]

        # Stress susceptibility as gain on stress-driven deviation
        # Apply an extra multiplier that ramps with stress_level.
        # This makes perturbations show higher CV than vehicle, which is realistic.
        if stress_level > 0:
            gain = 1.0 + (sus - 1.0) * stress_level
            for ch in morph:
                morph[ch] *= gain

        # Residual biological noise, still dose/stress-dependent but small
        effective_cv = base_residual_cv * (1.0 + stress_level * (stress_multiplier - 1.0))
        if effective_cv > 0:
            for ch in morph:
                morph[ch] *= lognormal_multiplier(self.vm.rng_assay, effective_cv)

        return morph

    def _add_plating_artifacts(self, vessel: "VesselState", morph: Dict[str, float], t_measure: float) -> Dict[str, float]:
        """Add plating artifact variance inflation (early timepoints unreliable)."""
        if vessel.plating_context is not None:
            time_since_seed = t_measure - vessel.seed_time
            tau_recovery = vessel.plating_context['tau_recovery_h']

            post_dissoc_stress = vessel.plating_context['post_dissociation_stress']
            artifact_magnitude = post_dissoc_stress * float(np.exp(-time_since_seed / tau_recovery))

            clumpiness = vessel.plating_context['clumpiness']
            clump_variance = clumpiness * float(np.exp(-time_since_seed / (tau_recovery * 0.5)))

            if artifact_magnitude > 0.01 or clump_variance > 0.01:
                artifact_cv = artifact_magnitude + clump_variance
                for channel in morph:
                    morph[channel] *= lognormal_multiplier(self.vm.rng_assay, artifact_cv)

        return morph

    def _get_plate_stain_factor(self, plate_id: str, batch_id: str, cv: float) -> float:
        """Deterministic plate-level stain factor (like other batch factors)."""
        return self._get_batch_factor("stain", plate_id, batch_id, cv)

    def _get_tile_focus_factor(self, plate_id: str, batch_id: str, well_position: str, cv: float) -> float:
        """
        Deterministic per-tile focus factor.
        Tile here means e.g. 4x4 blocks to mimic focus surface.
        """
        # parse well -> (row_idx, col_idx)
        row = ord(well_position[0].upper()) - ord("A")
        col = int(well_position[1:]) - 1

        tile_r = row // 4
        tile_c = col // 4
        tile_id = f"{plate_id}_focusTile_{tile_r}_{tile_c}"
        return self._get_batch_factor("focus", tile_id, batch_id, cv)

    def _add_technical_noise(self, vessel: "VesselState", morph: Dict[str, float], **kwargs) -> Dict[str, float]:
        """Add technical noise from plate/day/operator/well/edge effects."""
        tech_noise = self.vm.thalamus_params['technical_noise']

        plate_id = kwargs.get('plate_id', 'P1')
        batch_id = kwargs.get('batch_id', 'batch_default')
        day = kwargs.get('day', 1)
        operator = kwargs.get('operator', 'OP1')
        well_position = kwargs.get('well_position', 'A1')

        # Deterministic batch effects (seeded by context + batch ID)
        # DIAGNOSTIC: Temporarily disable to isolate per-channel coupling
        DIAGNOSTIC_DISABLE_SHARED_FACTORS = True
        if DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            plate_factor = 1.0
            day_factor = 1.0
            operator_factor = 1.0
        else:
            plate_factor = self._get_batch_factor('plate', plate_id, batch_id, tech_noise['plate_cv'])
            day_factor = self._get_batch_factor('day', day, batch_id, tech_noise['day_cv'])
            operator_factor = self._get_batch_factor('op', operator, batch_id, tech_noise['operator_cv'])

        # Per-channel well factor (breaks global multiplier dominance)
        # Use per-channel deterministic seeding for transparency and persistence
        well_cv = tech_noise['well_cv']
        well_factors_per_channel = {}
        if well_cv > 0:
            for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
                # Deterministic per-channel: key to plate + well + channel
                channel_seed = stable_u32(f"well_factor_{plate_id}_{well_position}_{channel}")
                channel_rng = np.random.default_rng(channel_seed)
                well_factors_per_channel[channel] = lognormal_multiplier(channel_rng, well_cv)
        else:
            well_factors_per_channel = {ch: 1.0 for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']}

        # Edge effect
        # DIAGNOSTIC: Disable edge effect to isolate per-channel coupling
        if DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            edge_factor = 1.0
        else:
            edge_effect = tech_noise.get('edge_effect', 0.0)
            is_edge = self._is_edge_well(well_position)
            edge_factor = (1.0 - edge_effect) if is_edge else 1.0

        # Run context modifiers (lot/instrument effects)
        meas_mods = self.vm.run_context.get_measurement_modifiers()
        # DIAGNOSTIC: Disable illumination_bias to isolate per-channel coupling
        if DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            illumination_bias = 1.0
            channel_biases = {ch: 1.0 for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']}
        else:
            illumination_bias = meas_mods['illumination_bias']
            channel_biases = meas_mods['channel_biases']

        # Add coupled nuisance factors
        stain_cv = float(tech_noise.get("stain_cv", 0.05))   # new param
        focus_cv = float(tech_noise.get("focus_cv", 0.04))   # new param

        stain_factor = self._get_plate_stain_factor(plate_id, batch_id, stain_cv) if stain_cv > 0 else 1.0
        focus_factor = self._get_tile_focus_factor(plate_id, batch_id, well_position, focus_cv) if focus_cv > 0 else 1.0

        # Focus should also inflate variance on structure channels (nucleus/actin).
        # Translate focus_factor into a "focus badness" scalar.
        focus_badness = abs(float(np.log(focus_factor))) if focus_factor > 0 else 0.0

        # Shared factors (plate/day/operator/edge/illumination) - NOT per-channel well_factor
        shared_tech_factor = plate_factor * day_factor * operator_factor * edge_factor * illumination_bias

        # Apply shared factors + per-channel well factor + biases + coupled stain/focus
        for channel in morph:
            channel_bias = channel_biases.get(channel, 1.0)
            well_factor = well_factors_per_channel.get(channel, 1.0)

            # Stain coupling: strong on ER/Mito/RNA, moderate on Nucleus, weak on Actin
            if channel in ("er", "mito"):
                coupled = stain_factor
            elif channel == "rna":
                coupled = stain_factor ** 0.9
            elif channel == "nucleus":
                coupled = stain_factor ** 0.5
            elif channel == "actin":
                coupled = stain_factor ** 0.2
            else:
                coupled = 1.0

            # Focus coupling: strong on Nucleus/Actin, weak on ER/Mito/RNA
            if channel in ("nucleus", "actin"):
                coupled *= focus_factor
            else:
                coupled *= focus_factor ** 0.2

            # Apply: shared factors × per-channel well factor × channel bias × coupled factors
            morph[channel] *= shared_tech_factor * well_factor * channel_bias * coupled

            # Focus-induced variance inflation for structure channels (fingerprint)
            if channel in ("nucleus", "actin") and focus_badness > 0:
                extra_cv = min(0.25, 0.05 + 0.4 * focus_badness)  # cap it
                morph[channel] *= lognormal_multiplier(self.vm.rng_assay, extra_cv)

            morph[channel] = max(0.0, morph[channel])

        return morph

    def _get_batch_factor(self, prefix: str, identifier: Any, batch_id: str, cv: float) -> float:
        """Get deterministic batch effect factor."""
        if cv <= 0:
            return 1.0
        rng = np.random.default_rng(stable_u32(f"{prefix}_{self.vm.run_context.seed}_{batch_id}_{identifier}"))
        return lognormal_multiplier(rng, cv)

    def _is_edge_well(self, well_position: str, plate_format: int = 384) -> bool:
        """Detect if well is on plate edge."""
        match = re.search(r'([A-P])(\d{1,2})$', well_position)
        if not match:
            return False

        row = match.group(1)
        col = int(match.group(2))

        if plate_format == 384:
            return row in ['A', 'P'] or col in [1, 24]
        elif plate_format == 96:
            return row in ['A', 'H'] or col in [1, 12]
        return False

    def _apply_well_failure(
        self, morph: Dict[str, float], well_position: str, plate_id: str, batch_id: str
    ) -> Optional[Dict]:
        """Apply random well failures (bubbles, contamination, etc.)."""
        tech_noise = self.vm.thalamus_params.get('technical_noise', {})
        failure_rate = tech_noise.get('well_failure_rate', 0.0)

        if failure_rate <= 0:
            return None

        # Seed failures by run context + plate + well
        rng_failure = np.random.default_rng(
            stable_u32(f"well_failure_{self.vm.run_context.seed}_{batch_id}_{plate_id}_{well_position}")
        )
        if rng_failure.random() > failure_rate:
            return None

        # Select failure mode
        failure_modes = self.vm.thalamus_params.get('well_failure_modes', {})
        if not failure_modes:
            return None

        modes = list(failure_modes.keys())
        probs = [failure_modes[mode].get('probability', 0.0) for mode in modes]
        total_prob = sum(probs)
        if total_prob <= 0:
            return None

        probs = [p / total_prob for p in probs]
        selected_mode = rng_failure.choice(modes, p=probs)
        effect = failure_modes[selected_mode].get('effect', 'no_signal')

        # Apply failure effect
        failed_morph = morph.copy()

        if effect == 'no_signal':
            for channel in failed_morph:
                failed_morph[channel] = rng_failure.uniform(0.1, 2.0)
        elif effect == 'outlier_high':
            for channel in failed_morph:
                failed_morph[channel] *= rng_failure.uniform(5.0, 20.0)
        elif effect == 'outlier_low':
            for channel in failed_morph:
                failed_morph[channel] *= rng_failure.uniform(0.05, 0.3)
        elif effect == 'partial_signal':
            failed_channels = rng_failure.choice(
                list(failed_morph.keys()),
                size=rng_failure.integers(1, len(failed_morph)),
                replace=False
            )
            for channel in failed_channels:
                failed_morph[channel] = rng_failure.uniform(0.1, 2.0)
        elif effect == 'mixed_signal':
            mix_ratio = rng_failure.uniform(0.3, 0.7)
            for channel in failed_morph:
                neighbor_signal = failed_morph[channel] * rng_failure.uniform(0.5, 2.0)
                failed_morph[channel] = mix_ratio * failed_morph[channel] + (1 - mix_ratio) * neighbor_signal

        return {
            'morphology': failed_morph,
            'failure_mode': selected_mode,
            'effect': effect
        }

    def _apply_segmentation_failure(
        self, vessel: "VesselState", result: Dict[str, Any], **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Apply segmentation failure (adversarial measurement layer).

        This is NOT noise - it changes sufficient statistics:
        - Cell count (merges/splits/drops)
        - Feature values (texture attenuation, size bias)
        - QC flags (survivorship bias)

        Args:
            vessel: Vessel state
            result: Cell painting result dict
            **kwargs: Must contain focus_offset_um, stain_scale, well_position

        Returns:
            Dict with updated fields or None if segmentation disabled
        """
        # Check if segmentation failure is enabled
        enable_segmentation_failure = kwargs.get('enable_segmentation_failure', True)
        if not enable_segmentation_failure:
            return None

        # Initialize segmentation injection (shared instance for determinism)
        if not hasattr(self, '_segmentation_injection'):
            self._segmentation_injection = SegmentationFailureInjection()

        # Build injection context
        ctx = InjectionContext(
            simulated_time=self.vm.simulated_time,
            run_context=self.vm.run_context,
            well_position=kwargs.get('well_position', 'A1'),
            plate_id=kwargs.get('plate_id', 'P1')
        )

        # Create deterministic RNG for segmentation (separate from biology/assay streams)
        from .._impl import stable_u32
        well_position = kwargs.get('well_position', 'A1')
        plate_id = kwargs.get('plate_id', 'P1')
        seg_seed = stable_u32(f"segmentation_{self.vm.run_context.seed}_{plate_id}_{well_position}")
        rng = np.random.default_rng(seg_seed)

        state = self._segmentation_injection.initialize_state(ctx, rng)

        # Extract parameters for segmentation quality computation
        confluence = vessel.confluence
        debris_level = self._estimate_debris_level(vessel)
        focus_offset_um = kwargs.get('focus_offset_um', 0.0)
        stain_scale = kwargs.get('stain_scale', 1.0)

        # True cell count (before segmentation)
        true_count = int(vessel.cell_count)

        # Apply segmentation distortion
        observed_count, distorted_morphology, qc_metadata = self._segmentation_injection.hook_cell_painting_assay(
            ctx=ctx,
            state=state,
            true_count=true_count,
            true_morphology=result['morphology'].copy(),
            confluence=confluence,
            debris_level=debris_level,
            focus_offset_um=focus_offset_um,
            stain_scale=stain_scale,
            rng=rng
        )

        # Update result with segmentation distortions
        updates = {
            'cell_count_true': true_count,
            'cell_count_observed': observed_count,
            'morphology': distorted_morphology,
            'morphology_measured': distorted_morphology,
            'segmentation_quality': qc_metadata['segmentation_quality'],
            'segmentation_qc_passed': qc_metadata['qc_passed'],
            'segmentation_warnings': qc_metadata['qc_warnings'],
            'merge_count': qc_metadata['merge_count'],
            'split_count': qc_metadata['split_count'],
            'size_bias': qc_metadata['size_bias'],
        }

        # If QC failed, mark result
        if not qc_metadata['qc_passed']:
            updates['qc_flag'] = 'SEGMENTATION_FAIL'
            updates['data_quality'] = 'poor'

        return updates

    def _estimate_debris_level(self, vessel: "VesselState") -> float:
        """
        Estimate debris level from vessel state.

        Debris increases with:
        - Low viability (dead cells)
        - High death rates
        - Time since last washout
        """
        # Base debris from viability
        debris_from_death = 1.0 - vessel.viability

        # Debris from death mode (apoptotic bodies, necrotic debris)
        death_mode_multiplier = 1.0
        if vessel.death_mode == 'apoptosis':
            death_mode_multiplier = 1.5  # Fragmented cells
        elif vessel.death_mode == 'necrosis':
            death_mode_multiplier = 2.0  # Ruptured cells
        elif vessel.death_mode == 'silent':
            death_mode_multiplier = 0.5  # Detached (not visible)

        debris = debris_from_death * death_mode_multiplier

        # Clamp to [0, 1]
        debris = np.clip(debris, 0.0, 1.0)

        return float(debris)
