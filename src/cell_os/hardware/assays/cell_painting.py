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
from .assay_params import DEFAULT_ASSAY_PARAMS
from .._impl import stable_u32, lognormal_multiplier, heavy_tail_shock, additive_floor_noise, apply_saturation, quantize_adc
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
from ...contracts import enforce_measurement_contract, CELL_PAINTING_CONTRACT

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


def _cell_count_proxy_from_confluence(confluence: float, nominal_full_well: float = 10000.0) -> float:
    """
    Confluence-based proxy for cell count (cross-modal independence).

    Cell Painting cannot read true cell_count (that's a separate modality).
    Use confluence as observable proxy for scaling/normalization.
    """
    c = 0.0 if confluence is None else float(confluence)
    return max(0.0, min(1.0, c)) * nominal_full_well


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

    def _compute_structured_imaging_artifacts(
        self,
        vessel: "VesselState",
        well_position: str,
        experiment_seed: int,
        enable_channel_weights: bool = True,
        enable_segmentation_modes: bool = True,
        enable_spatial_field: bool = True
    ) -> Dict[str, Any]:
        """
        Compute all structured imaging artifacts from vessel state (Layer A adapter).

        This is the ONLY place that calls the three core functions.
        Does NOT apply artifacts - just reports them.
        Does NOT touch RNG - pure function.

        Args:
            vessel: Vessel state with debris tracking
            well_position: Well ID like "A01" (for spatial field)
            experiment_seed: Seed for this plate instance (for spatial field)
            enable_channel_weights: Return per-channel background (default True)
            enable_segmentation_modes: Return merge/split modes (default True)
            enable_spatial_field: Return spatial pattern (default True)

        Returns:
            {
                'background': {__global__: float} or {er: float, mito: float, ...},
                'segmentation': {scalar_bump: float, modes: {...}},
                'spatial': {field_strength: float, spatial_pattern: ndarray, ...} or None,
                'debris_cells': float,
                'initial_cells': float,
                'adherent_cells': float,
            }
        """
        from ...sim.imaging_artifacts_core import (
            compute_background_multipliers_by_channel,
            compute_segmentation_failure_modes,
            compute_segmentation_failure_probability_bump,
            compute_debris_field_modifiers,
        )

        debris_cells = float(getattr(vessel, 'debris_cells', 0.0))
        initial_cells = float(getattr(vessel, 'initial_cells', 1.0))
        # Use confluence-based proxy (cross-modal independence)
        adherent_cells = _cell_count_proxy_from_confluence(vessel.confluence)
        confluence = float(vessel.confluence)

        # Determine if edge well
        is_edge = self.vm._is_edge_well(well_position) if hasattr(self.vm, '_is_edge_well') else False

        # Background multipliers
        if enable_channel_weights:
            # Per-channel weights (RNA/Actin more sensitive to background)
            channel_weights = {
                'rna': 1.5,
                'actin': 1.3,
                'nucleus': 1.0,
                'er': 0.8,
                'mito': 0.8
            }
            bg_mults = compute_background_multipliers_by_channel(
                debris_cells=debris_cells,
                initial_cells=initial_cells,
                channel_weights=channel_weights
            )
        else:
            # Scalar (backward compatible)
            bg_mults = compute_background_multipliers_by_channel(
                debris_cells=debris_cells,
                initial_cells=initial_cells,
                channel_weights=None
            )

        # Segmentation failures (always compute scalar for backward compat)
        seg_scalar = compute_segmentation_failure_probability_bump(
            debris_cells=debris_cells,
            adherent_cell_count=adherent_cells
        )

        seg_result = {'scalar_bump': seg_scalar}
        if enable_segmentation_modes:
            seg_modes = compute_segmentation_failure_modes(
                debris_cells=debris_cells,
                adherent_cell_count=adherent_cells,
                confluence=confluence
            )
            seg_result['modes'] = seg_modes

        # Spatial field
        spatial_result = None
        if enable_spatial_field:
            spatial_result = compute_debris_field_modifiers(
                debris_cells=debris_cells,
                initial_cells=initial_cells,
                is_edge=is_edge,
                well_id=well_position,
                experiment_seed=experiment_seed
            )

        return {
            'background': bg_mults,
            'segmentation': seg_result,
            'spatial': spatial_result,
            'debris_cells': debris_cells,
            'initial_cells': initial_cells,
            'adherent_cells': adherent_cells,
        }

    @enforce_measurement_contract(CELL_PAINTING_CONTRACT)
    def measure(self, vessel: "VesselState", **kwargs) -> Dict[str, Any]:
        """
        Simulate Cell Painting morphology assay.

        MEASUREMENT TIMING: This assay reads at t_measure = vm.simulated_time,
        which is t1 after advance_time() returns. This represents "readout after
        interval of biology." All time-dependent artifacts (washout, plating)
        use t_measure as reference.

        Args:
            vessel: Vessel state to measure
            enable_structured_artifacts: Enable structured artifacts (default False)
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with channel values and metadata
        """
        # Lock measurement purity - capture state before measurement
        state_before = (vessel.viability, vessel.confluence)

        # Layer C: Feature flag (off by default for backward compatibility)
        enable_structured = kwargs.get('enable_structured_artifacts', False)

        # Compute structured artifacts if enabled (Layer A adapter)
        if enable_structured:
            well_position = kwargs.get('well_position', 'A1')
            experiment_seed = kwargs.get('experiment_seed', 0)
            self._structured_artifacts = self._compute_structured_imaging_artifacts(
                vessel=vessel,
                well_position=well_position,
                experiment_seed=experiment_seed
            )
        else:
            self._structured_artifacts = None

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

        # Apply latent stress state effects (morphology-first mechanisms)
        # Treatment blinding: use only latent states, NOT compound identity
        morph = self._apply_latent_stress_effects(vessel, morph)

        # Infer microtubule compound presence from transport dysfunction
        # (Observable from morphology, not from treatment identity)
        has_microtubule_compound = float(getattr(vessel, "transport_dysfunction", 0.0) or 0.0) > 0.3

        # Apply contact pressure bias (measurement confounder)
        morph = self._apply_contact_pressure_bias(vessel, morph)

        # Keep structural morphology (before viability scaling) for output
        morph_struct = morph.copy()

        # Compute transport dysfunction score for diagnostics
        transport_dysfunction_score = self._compute_transport_dysfunction_score(
            vessel, morph, baseline, has_microtubule_compound
        )

        # Apply measurement layer (viability + artifacts + noise)
        # Returns both morphology and detector metadata (saturation/quantization flags)
        morph, detector_metadata = self._apply_measurement_layer(vessel, morph, **kwargs)

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
            "signal_intensity": (
                DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR
                + (1 - DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR) * vessel.viability
            ),  # ASSUMPTION: See assay_params.py and ASSUMPTIONS_AND_BOUNDARIES.md
            "transport_dysfunction_score": transport_dysfunction_score,
            "timestamp": datetime.now().isoformat(),
            # Pipeline drift metadata for epistemic control
            "run_context_id": self.vm.run_context.context_id,
            "batch_id": batch_id,
            "plate_id": plate_id,
            "measurement_modifiers": self.vm.run_context.get_measurement_modifiers(
                self.vm.simulated_time, modality='imaging'
            ),
            # Detector metadata: censoring flags for agent reasoning about measurement quality
            "detector_metadata": detector_metadata,
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

        # Compute Cell Painting quality degradation from debris/handling
        cp_quality_metrics = self._compute_cp_quality_metrics(vessel)
        result.update(cp_quality_metrics)

        # Add imaging artifacts for audit trail (always present, None if flag off)
        result['imaging_artifacts'] = self._structured_artifacts

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
    ) -> tuple[Dict[str, float], Dict[str, Any]]:
        """Apply measurement layer: viability scaling, washout artifacts, debris artifacts, noise, batch effects.

        Measurement pipeline order:
        1. Viability factor (biological signal attenuation)
        2. Washout multiplier (measurement artifact)
        3. Exposure multiplier (agent-controlled instrument setting)
        4. Debris background (fluorescence contamination)
        5. Biological noise (dose-dependent lognormal)
        6. Plating artifacts (early timepoint variance inflation)
        7. Technical noise (plate/day/operator/well/edge effects)
        8. Additive floor (detector read noise, stochastic)
        9. Saturation (detector dynamic range, deterministic)
        10. Quantization (ADC digitization, deterministic)
        11. Pipeline drift (software feature extraction)

        Returns:
            tuple: (morphology, detector_metadata) where detector_metadata contains:
                - is_saturated[ch]: True if signal hit ceiling
                - is_quantized[ch]: True if quantization applied
                - quant_step[ch]: Quantization step size (0.0 if dormant)
                - snr_floor_proxy[ch]: signal / sigma_floor (None if sigma_floor == 0)
                - exposure_multiplier: Agent-controlled signal scaling (default 1.0)
        """
        t_measure = self.vm.simulated_time
        tech_noise = self.vm.thalamus_params['technical_noise']

        # 1. Viability factor (biological signal attenuation)
        # ASSUMPTION: Dead cells retain CP_DEAD_SIGNAL_FLOOR signal. See assay_params.py
        viability_factor = (
            DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR
            + (1 - DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR) * vessel.viability
        )

        # 2. Washout multiplier (measurement artifact)
        washout_multiplier = self._compute_washout_multiplier(vessel, t_measure)

        # 3. Exposure multiplier (scales signal strength before detector)
        # Agent-controlled: trade-off between SNR (floor-limited) and saturation
        exposure_multiplier = kwargs.get('exposure_multiplier', 1.0)
        if exposure_multiplier != 1.0:
            for channel in morph:
                morph[channel] *= exposure_multiplier

        # 4. Debris background fluorescence multiplier (Layer B: branch on flag)
        if self._structured_artifacts is not None:
            # Structured artifacts enabled (per-channel)
            bg_mults = self._structured_artifacts['background']
            if '__global__' in bg_mults:
                # Scalar mode
                debris_mult = bg_mults['__global__']
                for channel in morph:
                    morph[channel] *= viability_factor * washout_multiplier * debris_mult
            else:
                # Per-channel mode
                for channel in morph:
                    debris_mult = bg_mults.get(channel, 1.0)
                    morph[channel] *= viability_factor * washout_multiplier * debris_mult
        else:
            # Phase 1 scalar artifacts (backward compatible)
            debris_multiplier = self._compute_debris_background_multiplier(vessel)
            for channel in morph:
                morph[channel] *= viability_factor * washout_multiplier * debris_multiplier

        # 5. Biological noise (dose-dependent)
        morph = self._add_biological_noise(vessel, morph)

        # 6. Plating artifacts (early timepoint variance inflation)
        morph = self._add_plating_artifacts(vessel, morph, t_measure)

        # 7. Technical noise (plate/day/operator/well/edge effects)
        # NOTE: Debris also inflates noise variance via bg_noise_multiplier
        # Applied in _add_technical_noise() by scaling CVs
        morph = self._add_technical_noise(vessel, morph, **kwargs)

        # 8-10. Detector stack (v7: unified with optical materials, includes realism layers)
        # Applies: additive floor, saturation, QC pathologies, quantization
        # v7 realism: position effects, edge noise inflation, outliers
        from ..detector_stack import apply_detector_stack

        # Get realism config from run context (or override for counterfactual analysis)
        realism_config = kwargs.get('realism_config_override') or self.vm.run_context.get_realism_config()
        realism_config_source = "override" if 'realism_config_override' in kwargs else "run_context"

        # Get well position (parse from vessel_id or kwargs)
        well_position = kwargs.get('well_position', vessel.vessel_id)

        # Create dedicated detector RNG (same strategy as optical materials)
        # Seed from (run_seed, "cell_painting_detector", well_position)
        import hashlib
        seed_string = f"cp_detector|{self.vm.run_context.seed}|{well_position}"
        hash_bytes = hashlib.blake2s(seed_string.encode(), digest_size=4).digest()
        detector_seed = int.from_bytes(hash_bytes, byteorder='little')
        import numpy as np
        rng_detector = np.random.default_rng(detector_seed)

        # Apply unified detector stack
        morph, detector_metadata = apply_detector_stack(
            signal=morph,
            detector_params=tech_noise,
            rng_detector=rng_detector,
            exposure_multiplier=1.0,  # Already applied in step 3
            well_position=well_position,
            plate_format=384,  # TODO: get from plate design
            enable_vignette=False,  # Cell Painting doesn't use vignette (that's for materials)
            enable_pipeline=False,  # Pipeline drift handled separately in step 11
            enable_detector_bias=False,  # No detector bias for cells (only materials)
            run_seed=self.vm.run_context.seed,
            realism_config=realism_config
        )

        # Extract metadata (detector_stack returns all fields we need)
        is_saturated = detector_metadata['is_saturated']
        is_quantized = detector_metadata['is_quantized']
        quant_step = detector_metadata['quant_step']
        snr_floor_proxy = detector_metadata['snr_floor_proxy']
        edge_distance = detector_metadata.get('edge_distance', 0.0)  # v7
        qc_flags = detector_metadata.get('qc_flags', {})  # v7

        # 11. Pipeline drift (batch-dependent feature extraction)
        plate_id = kwargs.get('plate_id', 'P1')
        batch_id = kwargs.get('batch_id', 'batch_default')
        # Shared factors re-enabled after fixing nutrient depletion bug (commit b241033)
        DIAGNOSTIC_DISABLE_SHARED_FACTORS = False
        if not DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            morph = pipeline_transform(
                morphology=morph,
                context=self.vm.run_context,
                batch_id=batch_id,
                plate_id=plate_id
            )
        # else: skip pipeline_transform (no-op)

        # Compute realism config hash for auditability
        import json
        realism_config_str = json.dumps(realism_config, sort_keys=True)
        realism_config_hash = hashlib.blake2s(realism_config_str.encode(), digest_size=4).hexdigest()

        # Assemble detector metadata (v7: includes edge_distance, qc_flags, realism provenance)
        detector_metadata = {
            'is_saturated': is_saturated,
            'is_quantized': is_quantized,
            'quant_step': quant_step,
            'snr_floor_proxy': snr_floor_proxy,
            'exposure_multiplier': exposure_multiplier,  # Agent-controlled instrument setting
            'edge_distance': edge_distance,  # v7: continuous edge distance (0 = center, 1 = edge)
            'qc_flags': qc_flags,  # v7: outlier flags (is_outlier, pathology_type, affected_channel)
            'realism_config_source': realism_config_source,  # v7: "run_context" or "override" (for provenance)
            'realism_config_hash': realism_config_hash,  # v7: short hash for auditability
        }

        return morph, detector_metadata

    def _compute_debris_background_multiplier(self, vessel: "VesselState") -> float:
        """
        Compute debris-driven background fluorescence multiplier.

        Debris scatters light and increases autofluorescence, inflating
        measurement signal. This is applied globally across all channels.

        Returns multiplier in [1.0, 1.25] (1.0 = no debris, 1.25 = max inflation).
        """
        from ...sim.imaging_artifacts_core import compute_background_noise_multiplier

        debris_cells = float(getattr(vessel, 'debris_cells', 0.0))
        initial_cells = float(getattr(vessel, 'initial_cells', 1.0))

        if debris_cells == 0 or initial_cells == 0:
            return 1.0  # No debris or no baseline → no inflation

        multiplier = compute_background_noise_multiplier(
            debris_cells=debris_cells,
            initial_cells=initial_cells,
            base_multiplier=1.0,
            debris_coefficient=0.05,  # 5% inflation per 100% debris
            max_multiplier=1.25  # Cap at 25% inflation
        )

        return multiplier

    def _compute_debris_segmentation_failure_bump(self, vessel: "VesselState") -> float:
        """
        Compute debris-driven segmentation failure probability bump.

        Debris confounds segmentation algorithms, increasing merge/split/drop
        errors. This is an ADDITIVE probability bump on top of base failure rate.

        Returns probability bump in [0, 0.5] (0 = no debris, 0.5 = max bump).
        """
        from ...sim.imaging_artifacts_core import compute_segmentation_failure_probability_bump

        debris_cells = float(getattr(vessel, 'debris_cells', 0.0))
        # Use confluence-based proxy (cross-modal independence)
        adherent_cells = _cell_count_proxy_from_confluence(vessel.confluence)

        if debris_cells == 0 or adherent_cells <= 0:
            return 0.0  # No debris or no cells → no bump

        prob_bump = compute_segmentation_failure_probability_bump(
            debris_cells=debris_cells,
            adherent_cell_count=adherent_cells,
            base_probability=0.0,
            debris_coefficient=0.02,  # 2% failure bump per 100% debris ratio
            max_probability=0.5  # Cap at 50% bump
        )

        return prob_bump

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

    def _compute_damage_noise_multiplier(self, vessel: "VesselState") -> float:
        """
        Compute noise inflation factor from accumulated cellular damage.

        Damage-driven heteroskedasticity: As cells accumulate scars from stress,
        measurement variance increases even after stress is removed. This creates
        path-dependent uncertainty that makes agents learn damage matters.

        Args:
            vessel: Vessel state with damage fields

        Returns:
            Noise multiplier in [1.0, 5.0]:
            - D=0: mult=1.0 (clean cells, baseline noise)
            - D=0.5: mult~2.05 (moderate damage, ~2× variance)
            - D=1.0: mult~4.0 (severe damage, ~4× variance)
        """
        # Extract damage from all three stress axes
        er_damage = float(getattr(vessel, 'er_damage', 0.0))
        mito_damage = float(getattr(vessel, 'mito_damage', 0.0))
        transport_damage = float(getattr(vessel, 'transport_damage', 0.0))

        # Use max damage (any axis can drive noise inflation)
        D = max(er_damage, mito_damage, transport_damage)
        D = np.clip(D, 0.0, 1.0)

        # Smooth monotone functional form with convex curvature:
        # noise_mult = 1 + a*D + b*D²
        # Calibration:
        # - D=0: 1.0
        # - D=0.5: 1.0 + 1.2*0.5 + 1.8*0.25 = 2.05
        # - D=1.0: 1.0 + 1.2 + 1.8 = 4.0
        a = 1.2
        b = 1.8

        noise_mult = 1.0 + a * D + b * (D ** 2)

        # Bounded to prevent runaway (cap at 5.0)
        noise_mult = float(np.clip(noise_mult, 1.0, 5.0))

        return noise_mult

    def _add_biological_noise(self, vessel: "VesselState", morph: Dict[str, float]) -> Dict[str, float]:
        """
        Structured biology:
        - Per-well baseline shifts already applied (in _apply_well_biology_baseline)
        - Stress susceptibility as gain on stress-induced morphology
        - Small residual biological noise (do NOT crank this into amplitude mush)
        - STATE-DEPENDENT NOISE: Damage inflates outlier probability (heteroskedasticity)
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

        # Residual biological noise: base lognormal (per-channel) + rare heavy-tail shock (shared)
        # Structure: morph[ch] *= base_lognormal_i(cv) × shared_shock
        #
        # DESIGN NOTE - Channel correlation:
        # Heavy-tail shock is sampled ONCE per measurement and applied to ALL channels.
        # This creates "this well looks globally weird" signatures (focus drift, bubbles,
        # contamination affect all channels together). Base lognormal remains per-channel
        # to preserve existing variance structure. Result: outliers are correlated across
        # channels, but not perfectly (base lognormal still varies per-channel).
        effective_cv = base_residual_cv * (1.0 + stress_level * (stress_multiplier - 1.0))

        if effective_cv > 0:
            # Draw base lognormal per channel (existing behavior)
            base_factors = {}
            for ch in morph:
                base_factors[ch] = lognormal_multiplier(self.vm.rng_assay, effective_cv)

            # Draw heavy-tail shock once (shared across all channels)
            tech_noise = self.vm.thalamus_params.get('technical_noise', {})
            p_heavy_base = tech_noise.get('heavy_tail_frequency', 0.0)

            # STATE-DEPENDENT OUTLIERS: Damage increases heavy-tail frequency
            # More damaged cells show more outlier behavior (irregular morphology, heterogeneity)
            # Coupling: p_heavy increases monotonically with damage, bounded
            damage_noise_mult = self._compute_damage_noise_multiplier(vessel)
            # Scale p_heavy by sqrt(damage_noise_mult) to avoid over-amplification
            # (p_heavy is probability, not variance - use conservative scaling)
            p_heavy = float(np.clip(p_heavy_base * np.sqrt(damage_noise_mult), 0.0, 0.25))

            if p_heavy > 0:
                # Heavy-tail shock enabled: overlay on base lognormal
                shock = heavy_tail_shock(
                    rng=self.vm.rng_assay,
                    nu=tech_noise.get('heavy_tail_nu', 4.0),
                    log_scale=tech_noise.get('heavy_tail_log_scale', 0.35),
                    p_heavy=p_heavy,
                    clip_min=tech_noise.get('heavy_tail_min_multiplier', 0.2),
                    clip_max=tech_noise.get('heavy_tail_max_multiplier', 5.0)
                )
            else:
                # Heavy-tail shock dormant: no overlay
                shock = 1.0

            # Apply: base (per-channel) × shock (shared)
            for ch in morph:
                morph[ch] *= base_factors[ch] * shock

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
        # Shared factors re-enabled after fixing nutrient depletion bug (commit b241033)
        DIAGNOSTIC_DISABLE_SHARED_FACTORS = False
        if DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            plate_factor = 1.0
            day_factor = 1.0
            operator_factor = 1.0
        else:
            plate_factor = self._get_batch_factor('plate', plate_id, batch_id, tech_noise['plate_cv'])
            day_factor = self._get_batch_factor('day', day, batch_id, tech_noise['day_cv'])
            operator_factor = self._get_batch_factor('op', operator, batch_id, tech_noise['operator_cv'])

        # Per-channel well factor (breaks global multiplier dominance)
        # EXCHANGEABLE SAMPLING FIX (Attack 2): Use well_uid, not well_position
        well_cv = tech_noise['well_cv']
        well_factors_per_channel = {}
        if well_cv > 0:
            # Get exchangeable well UID from RunContext
            well_uid = self.vm.run_context.get_well_uid(plate_id, well_position)
            for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
                # Deterministic per-channel: key to well_uid + channel (NOT position)
                channel_seed = stable_u32(f"well_factor_{well_uid}_{channel}")
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

        # Run context modifiers (lot/instrument effects + temporal drift)
        # Pass t_measure and modality='imaging' for time-dependent drift
        t_measure = self.vm.simulated_time
        meas_mods = self.vm.run_context.get_measurement_modifiers(t_measure, modality='imaging')
        # DIAGNOSTIC: Disable gain to isolate per-channel coupling
        if DIAGNOSTIC_DISABLE_SHARED_FACTORS:
            gain = 1.0
            channel_biases = {ch: 1.0 for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']}
        else:
            gain = meas_mods['gain']  # Includes batch effect + temporal drift
            channel_biases = meas_mods['channel_biases']

        # Add coupled nuisance factors
        stain_cv = float(tech_noise.get("stain_cv", 0.05))   # new param
        focus_cv = float(tech_noise.get("focus_cv", 0.04))   # new param

        stain_factor = self._get_plate_stain_factor(plate_id, batch_id, stain_cv) if stain_cv > 0 else 1.0
        focus_factor = self._get_tile_focus_factor(plate_id, batch_id, well_position, focus_cv) if focus_cv > 0 else 1.0

        # STATE-DEPENDENT NOISE: Add per-measurement multiplicative noise scaled by damage
        # Damaged cells show higher measurement-to-measurement variance (irregular uptake, heterogeneous morphology)
        # This is applied PER MEASUREMENT (not batch-level), so it creates detectable variance differences
        damage_noise_mult = self._compute_damage_noise_multiplier(vessel)
        # Convert noise multiplier to CV: mult=2 → cv~0.35, mult=4 → cv~1.05
        # Use strong scaling to make damage-dependent variance detectable against baseline noise
        # Aggressive scaling needed because base Cell Painting noise (biological + technical) dilutes signal
        damage_cv = 0.35 * (damage_noise_mult - 1.0)  # D=0 → cv=0, D=0.8 → cv~0.74, D=1.0 → cv~1.05
        # ALWAYS draw from RNG to keep streams synchronized (draw from N(0,1) scaled by cv)
        if damage_cv > 0:
            damage_noise_factor = lognormal_multiplier(self.vm.rng_assay, damage_cv)
        else:
            # Draw from RNG but don't apply noise (keeps RNG synchronized)
            _ = self.vm.rng_assay.normal(0, 1)  # Consume RNG state
            damage_noise_factor = 1.0

        # Focus should also inflate variance on structure channels (nucleus/actin).
        # Translate focus_factor into a "focus badness" scalar.
        focus_badness = abs(float(np.log(focus_factor))) if focus_factor > 0 else 0.0

        # Hardware artifacts from Cell Painting (EL406 Cell Painting)
        # Affects measurement quality (stain intensity, background)
        hardware_factor = 1.0
        try:
            from src.cell_os.hardware.hardware_artifacts import get_hardware_bias

            # Get hardware sensitivity params
            hardware_sensitivity = self.vm.thalamus_params.get('hardware_sensitivity', {}) if hasattr(self.vm, 'thalamus_params') and self.vm.thalamus_params else {}

            hardware_bias = get_hardware_bias(
                plate_id=plate_id,
                batch_id=batch_id,
                well_position=well_position,
                instrument='el406_cellpainting',
                operation='cell_painting',
                seed=self.vm.run_context.seed,
                tech_noise=tech_noise,
                cell_line=vessel.cell_line,
                cell_line_params=hardware_sensitivity,
                run_context=self.vm.run_context
            )

            hardware_factor = hardware_bias['combined_factor']

        except (ImportError, Exception) as e:
            # Fallback: no hardware artifacts if import fails
            pass

        # Shared factors (plate/day/operator/edge/gain/hardware) - NOT per-channel well_factor
        # CANONICAL GAIN APPLICATION: gain applied exactly once here (includes batch + drift)
        shared_tech_factor = plate_factor * day_factor * operator_factor * edge_factor * gain * hardware_factor

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

            # Apply: shared factors × per-channel well factor × channel bias × coupled factors × damage noise
            morph[channel] *= shared_tech_factor * well_factor * channel_bias * coupled * damage_noise_factor

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

    def _add_additive_floor(self, morph: Dict[str, float]) -> Dict[str, float]:
        """
        Add detector read noise (additive floor).

        Applies additive Gaussian noise independent of signal magnitude.
        This models CCD/PMT dark current and read noise that dominates at
        low signal but becomes negligible at high signal.

        Golden-preserving: only draws from rng_assay when at least one sigma > 0.
        This avoids changing RNG consumption in existing tests with dormant config.

        Design trade: violates strict draw-count invariance across configs, but
        preserves baseline golden test trajectories. If strict invariance is needed,
        add dedicated rng_detector stream (future work).

        Args:
            morph: Morphology dict (after multiplicative noise stack)

        Returns:
            Morphology with additive floor applied and clamped at 0
        """
        tech_noise = self.vm.thalamus_params['technical_noise']

        # Use canonical channel list (not morph.keys()) to avoid silent failures
        # if morph ever contains extra features
        channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

        # Check if any sigma is nonzero (golden-preserving: skip RNG if all 0)
        sigmas = {ch: tech_noise.get(f'additive_floor_sigma_{ch}', 0.0) for ch in channels}

        if any(s > 0 for s in sigmas.values()):
            for ch in channels:
                sigma = sigmas[ch]
                if sigma > 0:
                    noise = additive_floor_noise(self.vm.rng_assay, sigma)
                    morph[ch] = max(0.0, morph[ch] + noise)

        return morph

    def _apply_saturation(self, morph: Dict[str, float]) -> tuple[Dict[str, float], Dict[str, bool]]:
        """
        Apply detector saturation (dynamic range limits).

        Models camera/PMT photon well depth and digitizer max. Signal compresses
        smoothly as it approaches ceiling, asymptotically saturating. This creates:
        - Plateaus in dose-response curves at high signal
        - Compressed variance at saturation boundary
        - Reduced information gain in clipped regime

        Epistemic forcing function: Agent must learn to:
        - Operate in linear regime (not just "go bigger")
        - Recognize when instrument is information-limited
        - Calibrate dynamic range, not just pick compounds

        Deterministic (no RNG): Detector physics, not randomness.
        Golden-preserving: Dormant when all ceilings <= 0.

        Applied AFTER additive floor (detector noise happens first),
        BEFORE pipeline_transform (software post-processing happens last).

        Args:
            morph: Morphology dict (after additive floor)

        Returns:
            Morphology with saturation applied (soft knee compression)
        """
        tech_noise = self.vm.thalamus_params['technical_noise']

        # Use canonical channel list (not morph.keys())
        channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

        # Shared soft-knee parameters (apply to all channels)
        knee_start_frac = tech_noise.get('saturation_knee_start_fraction', 0.85)
        tau_frac = tech_noise.get('saturation_tau_fraction', 0.08)

        # Apply per-channel saturation (independent ceilings)
        # Track which channels saturated (for detector metadata)
        is_saturated = {}
        for ch in channels:
            ceiling = tech_noise.get(f'saturation_ceiling_{ch}', 0.0)
            if ceiling > 0:  # Only apply if enabled for this channel
                y_pre = morph[ch]
                y_sat = apply_saturation(
                    y=y_pre,
                    ceiling=ceiling,
                    knee_start_frac=knee_start_frac,
                    tau_frac=tau_frac
                )
                morph[ch] = y_sat
                # Mark as saturated if within epsilon of ceiling
                is_saturated[ch] = (y_sat >= ceiling - 0.001)
            else:
                is_saturated[ch] = False

        return morph, is_saturated

    def _apply_adc_quantization(self, morph: Dict[str, float]) -> tuple[Dict[str, float], Dict[str, float], Dict[str, bool]]:
        """
        Apply ADC quantization (analog-to-digital conversion).

        Models digitizer bit depth: continuous analog signal → discrete digital codes.
        Removes arbitrarily fine decimal precision that doesn't exist in real detectors.
        Creates visible banding at low signal and dead zones where signal changes don't
        affect output.

        Epistemic forcing function: Agent must recognize:
        - Digitization limits (can't resolve sub-LSB differences)
        - Information dead zones (plateaus where nudging has no effect)
        - Low-signal coarseness (banding visible)

        Deterministic (no RNG): ADC conversion is electronics, not randomness.
        Golden-preserving: Dormant when all bits=0 and step=0.0.

        Applied AFTER saturation (analog compression),
        BEFORE pipeline_transform (software feature extraction).

        NOTE: This is "feature-level quantization" (applied to morphology channels),
        not pixel-level ADC simulation. It approximates the effect of digitization
        on aggregated features.

        Args:
            morph: Morphology dict (after saturation)

        Returns:
            Morphology with ADC quantization applied
        """
        tech_noise = self.vm.thalamus_params['technical_noise']

        # Use canonical channel list (not morph.keys())
        channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

        # Shared defaults
        bits_default = int(tech_noise.get('adc_quant_bits_default', 0))
        step_default = float(tech_noise.get('adc_quant_step_default', 0.0))
        mode = tech_noise.get('adc_quant_rounding_mode', 'round_half_up')

        # Apply per-channel quantization
        # Track quantization metadata (for detector metadata)
        quant_step = {}
        is_quantized = {}

        for ch in channels:
            # Per-channel overrides (fall back to defaults)
            bits = int(tech_noise.get(f'adc_quant_bits_{ch}', bits_default))
            step = float(tech_noise.get(f'adc_quant_step_{ch}', step_default))

            # Get ceiling from saturation config (needed for bits-mode)
            # If saturation is dormant (ceiling=0), bits-mode will raise ValueError
            ceiling = float(tech_noise.get(f'saturation_ceiling_{ch}', 0.0))

            # Determine effective step (same logic as quantize_adc)
            effective_step = 0.0
            if bits > 0:
                if ceiling > 0:
                    num_codes = (1 << bits) - 1
                    effective_step = ceiling / max(num_codes, 1)
            elif step > 0:
                effective_step = step

            # Apply quantization (dormant if bits=0 and step=0.0)
            if bits > 0 or step > 0:
                morph[ch] = quantize_adc(
                    y=morph[ch],
                    step=step,
                    bits=bits,
                    ceiling=ceiling,
                    mode=mode
                )
                is_quantized[ch] = True
                quant_step[ch] = effective_step
            else:
                is_quantized[ch] = False
                quant_step[ch] = 0.0

        return morph, quant_step, is_quantized

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

        # Estimated cell count (before segmentation) - use confluence proxy
        estimated_count = int(_cell_count_proxy_from_confluence(vessel.confluence))

        # Apply segmentation distortion
        observed_count, distorted_morphology, qc_metadata = self._segmentation_injection.hook_cell_painting_assay(
            ctx=ctx,
            state=state,
            true_count=estimated_count,
            true_morphology=result['morphology'].copy(),
            confluence=confluence,
            debris_level=debris_level,
            focus_offset_um=focus_offset_um,
            stain_scale=stain_scale,
            rng=rng
        )

        # ADDITIONAL debris-driven segmentation failure (Layer B: branch on flag)
        # This is separate from the quality degradation in compute_segmentation_quality()
        # Debris confounds segmentation algorithms beyond just reducing quality
        seg_quality_original = qc_metadata['segmentation_quality']

        if self._structured_artifacts is not None:
            # Structured artifacts enabled (modes-based)
            seg = self._structured_artifacts['segmentation']
            if 'modes' in seg:
                # Use merge/split modes
                modes = seg['modes']
                # TODO: Apply merge/split distortions to morphology (not implemented yet)
                # For now, use combined probability as quality reduction
                total_failure_prob = modes['p_merge'] + modes['p_split']
                seg_quality_adjusted = seg_quality_original * (1.0 - total_failure_prob)
                seg_fail_prob_bump = total_failure_prob
            else:
                # Fall back to scalar
                seg_fail_prob_bump = seg['scalar_bump']
                seg_quality_adjusted = seg_quality_original * (1.0 - seg_fail_prob_bump)
        else:
            # Phase 1 scalar artifacts (backward compatible)
            seg_fail_prob_bump = self._compute_debris_segmentation_failure_bump(vessel)
            seg_quality_adjusted = seg_quality_original * (1.0 - seg_fail_prob_bump)

        seg_quality_adjusted = float(np.clip(seg_quality_adjusted, 0.0, 1.0))

        # Update result with segmentation distortions (use adjusted quality)
        updates = {
            'cell_count_estimated': estimated_count,
            'cell_count_observed': observed_count,
            'morphology': distorted_morphology,
            'morphology_measured': distorted_morphology,
            'segmentation_quality': seg_quality_adjusted,  # Adjusted for debris bump
            'segmentation_quality_pre_debris': seg_quality_original,  # Original (for debugging)
            'debris_seg_fail_bump': seg_fail_prob_bump,  # Debris contribution (for debugging)
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

        Now uses ACTUAL debris tracking from wash/fixation physics.
        Debris increases with:
        - Wash/fixation detachment (imperfect aspiration)
        - Low viability (dead cells)
        - High death rates
        """
        # ACTUAL debris from wash/fixation (preferred if available)
        if hasattr(vessel, 'debris_cells') and vessel.debris_cells > 0:
            # Normalize to [0, 1] range using initial cells as anchor
            initial_cells = getattr(vessel, 'initial_cells', 10000.0)
            if initial_cells > 0:
                return float(min(1.0, vessel.debris_cells / initial_cells))

        # Fallback: estimate from viability (observable)
        # No death_mode branching - use only continuous observables
        debris_from_death = 1.0 - vessel.viability

        # Clamp to [0, 1]
        debris = float(np.clip(debris_from_death, 0.0, 1.0))

        return debris

    def _compute_cp_quality_metrics(self, vessel: "VesselState") -> Dict[str, Any]:
        """
        Compute Cell Painting quality degradation from debris and handling loss.

        Stickology doesn't kill cells - it ruins your measurement.

        Quality model:
        1. debris_load: Fraction of debris relative to live cells
        2. handling_loss: Fraction of cells lost to handling
        3. cp_quality: Overall quality scalar (0..1, 1=perfect)
        4. segmentation_yield: Fraction of cells successfully segmented
        5. n_segmented: Effective segmented cell count
        6. noise_mult: Noise inflation multiplier
        7. artifact_level: Step-like failure indicator (0-3)

        Returns:
            Dict with quality metrics
        """
        eps = 1e-9

        # Extract state - use confluence proxy
        live_cells = _cell_count_proxy_from_confluence(vessel.confluence)
        debris_cells = float(getattr(vessel, 'debris_cells', 0.0))
        cells_lost = float(getattr(vessel, 'cells_lost_to_handling', 0.0))

        # Total cell material (live + debris + lost)
        total_material = live_cells + debris_cells + cells_lost + eps

        # 1. Debris load (debris as fraction of live + debris)
        debris_load = debris_cells / (live_cells + debris_cells + eps)
        debris_load = float(np.clip(debris_load, 0.0, 1.0))

        # 2. Handling loss fraction
        handling_loss = cells_lost / total_material
        handling_loss = float(np.clip(handling_loss, 0.0, 1.0))

        # 3. CP quality scalar (debris is worse than clean loss)
        # Recommended: a=1.2 (debris), b=0.4 (handling loss)
        a = 1.2
        b = 0.4
        cp_quality = 1.0 - a * debris_load - b * handling_loss
        cp_quality = float(np.clip(cp_quality, 0.0, 1.0))

        # 4. Segmentation yield (debris poisons segmentation)
        # Base: c = 0.8 (segmentation drops 80% at 100% debris)
        # Heterogeneity amplifies: clumpy debris is worse for segmentation
        # - Low heterogeneity (0.2): 1.0× multiplier (diffuse debris)
        # - High heterogeneity (0.5): 1.3× multiplier (clumpy debris, edge junk)

        # Get adhesion heterogeneity (spatial clumpiness of debris)
        adhesion_heterogeneity = 0.3  # Default
        if hasattr(self.vm, 'thalamus_params') and self.vm.thalamus_params:
            hardware_sens = self.vm.thalamus_params.get('hardware_sensitivity', {})
            cell_params = hardware_sens.get(vessel.cell_line, hardware_sens.get('DEFAULT', {}))
            adhesion_heterogeneity = cell_params.get('adhesion_heterogeneity', 0.3)

        # ASSUMPTION: Segmentation yield degrades linearly with debris. See assay_params.py
        c_base = DEFAULT_ASSAY_PARAMS.SEGMENTATION_C_BASE
        clumpiness_amplifier = 1.0 + 0.6 * adhesion_heterogeneity  # [1.0×, 1.3×]
        c_effective = c_base * clumpiness_amplifier

        segmentation_yield = 1.0 - c_effective * debris_load
        segmentation_yield = float(np.clip(segmentation_yield, 0.0, 1.0))

        # 5. Effective segmented cell count
        n_segmented = int(round(live_cells * segmentation_yield))

        # 6. Noise multiplier (quality degradation inflates noise)
        # d = 2.0: worst case triples noise (1 + 2*(1-0) = 3)
        d = 2.0
        noise_mult = 1.0 + d * (1.0 - cp_quality)
        noise_mult = float(np.clip(noise_mult, 1.0, 3.0))

        # 7. Artifact level (step-like failure, deterministic)
        # Thresholds: 0.30, 0.50, 0.65
        artifact_level = 0
        if debris_load > 0.30:
            artifact_level += 1
        if debris_load > 0.50:
            artifact_level += 1
        if debris_load > 0.65:
            artifact_level += 1

        # Apply artifact penalty to cp_quality
        artifact_penalty = 0.1 * artifact_level
        cp_quality_final = float(np.clip(cp_quality - artifact_penalty, 0.0, 1.0))

        # 8. Edge damage from aspiration/dispense (position-dependent artifacts)
        # Aspiration at fixed position (9 o'clock) creates L-R asymmetry
        # Shows up as: worse segmentation, more noise, amplified debris effects
        edge_damage_score = float(getattr(vessel, 'edge_damage_score', 0.0))

        # Initialize edge damage diagnostic variables
        edge_damage_seg_penalty = 0.0
        edge_damage_noise_mult = 1.0
        edge_damage_debris_amp = 1.0

        if edge_damage_score > 0:
            try:
                from src.cell_os.hardware.aspiration_effects import get_edge_damage_contribution_to_cp_quality

                edge_effects = get_edge_damage_contribution_to_cp_quality(
                    edge_damage_score=edge_damage_score,
                    debris_load=debris_load
                )

                # Apply edge damage effects
                # 1. Reduce segmentation yield (damaged cells fail segmentation)
                seg_penalty = edge_effects['segmentation_yield_penalty']
                edge_damage_seg_penalty = seg_penalty  # Track for diagnostics
                segmentation_yield *= (1.0 - seg_penalty)
                segmentation_yield = float(np.clip(segmentation_yield, 0.0, 1.0))
                n_segmented = int(round(live_cells * segmentation_yield))

                # 2. Amplify noise (irregular morphology)
                edge_damage_noise_mult = edge_effects['noise_multiplier']  # Track for diagnostics
                noise_mult *= edge_damage_noise_mult
                noise_mult = float(np.clip(noise_mult, 1.0, 5.0))

                # 3. Amplify debris interference (damaged cells + debris = especially bad)
                debris_amplification = edge_effects['debris_amplification']
                edge_damage_debris_amp = debris_amplification  # Track for diagnostics
                effective_debris_load = debris_load * debris_amplification

                # Re-compute cp_quality with amplified debris
                cp_quality_edge = 1.0 - a * effective_debris_load - b * handling_loss
                cp_quality_edge = float(np.clip(cp_quality_edge, 0.0, 1.0))
                cp_quality_final = min(cp_quality_final, cp_quality_edge)  # Take worst

            except (ImportError, Exception):
                # Edge damage disabled (no aspiration_effects module)
                pass

        return {
            'debris_load': debris_load,
            'debris_numerator': debris_cells,  # For debugging: explicit numerator
            'debris_denominator': live_cells + debris_cells,  # For debugging: explicit denominator
            'handling_loss_fraction': handling_loss,
            'adhesion_heterogeneity': adhesion_heterogeneity,  # Spatial clumpiness
            'clumpiness_amplifier': clumpiness_amplifier,  # Segmentation penalty multiplier
            'cp_quality': cp_quality_final,
            'cp_quality_pre_artifact': cp_quality,  # Before artifact penalty
            'segmentation_yield': segmentation_yield,
            'n_segmented': n_segmented,
            'n_cells_measured': n_segmented,  # Alias for backward compatibility
            'noise_mult': noise_mult,
            'artifact_level': artifact_level,
            'artifact_penalty': artifact_penalty,
            # Edge damage diagnostics (position-dependent artifacts)
            'edge_damage_score': edge_damage_score,  # Cumulative damage (0-1, saturates)
            'edge_damage_seg_penalty': edge_damage_seg_penalty,  # Segmentation penalty (0-0.15)
            'edge_damage_noise_mult': edge_damage_noise_mult,  # Noise amplification (1.0-1.5×)
            'edge_damage_debris_amp': edge_damage_debris_amp  # Debris amplification (1.0-1.3×)
        }
