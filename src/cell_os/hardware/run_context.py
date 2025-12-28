"""
Run Context: Batch, Lot, and Instrument Latents

Phase 5B Realism Injection #1:
Correlated "today is cursed" effects that touch both biology and measurement.

Key insight: Context creates shared, non-identifiable structure that looks like
biology until you pay an explicit calibration cost.

This forces:
- Calibration plate workflows (spend intervention to disambiguate context)
- "Same compound, different conclusion" outcomes (Context A vs Context B)
- Correlated failure modes (not i.i.d. noise)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional

# v6: Import batch effects for semantic provenance
from .batch_effects import RunBatchProfile

# Drift model for within-run temporal measurement drift
from .drift_model import DriftModel


@dataclass
class RunContext:
    """
    Batch/lot/instrument context that affects biology and measurement.

    Factors are sampled once per run (or per day) and persist across all plates.

    Factors:
    - incubator_shift: affects growth rate and stress sensitivity (biology)
    - reagent_lot_shift: channel-specific intensity biases (imaging)
    - scalar_reagent_lot_shift: per-assay kit biases (biochemical readouts)
    - instrument_shift: illumination/focus/noise floor shifts (measurement)

    All factors are correlated to create coherent "cursed days".
    """
    # Global factors (shared across all plates in run)
    incubator_shift: float  # -0.3 to +0.3, affects biology
    reagent_lot_shift: Dict[str, float]  # Per-channel intensity biases (imaging)
    scalar_reagent_lot_shift: Dict[str, float]  # Per-assay kit biases (ATP/LDH/UPR/TRAFFICKING)
    instrument_shift: float  # -0.2 to +0.2, affects measurement noise

    # Optional per-plate deltas (small variations within run)
    plate_deltas: Optional[Dict[str, float]] = None

    # Metadata
    seed: int = 0
    context_id: str = ""

    # v6: Batch effect profile (semantic provenance)
    _profile: Optional[RunBatchProfile] = None

    # v6: Cached biology modifiers (derived from profile once per run)
    _biology_modifiers: Optional[Dict[str, float]] = None

    # Within-run drift (temporal measurement drift)
    drift_enabled: bool = True
    _drift_model: Optional[DriftModel] = None

    # v7: Simulation realism controls (demo-visible plate artifacts)
    realism_profile: str = "clean"  # "clean", "realistic", or "hostile"
    batch_id: str = ""  # Derived from context_id for batch tracking

    # Optional batch metadata (for demo outputs and plotting)
    operator_id: Optional[str] = None
    media_lot_id: Optional[str] = None
    stain_lot_id: Optional[str] = None
    instrument_day: Optional[str] = None

    @staticmethod
    def sample(seed: int, config: Optional[Dict] = None) -> 'RunContext':
        """
        Sample a run context with correlated factors.

        Args:
            seed: RNG seed for reproducibility
            config: Optional config dict with:
                - context_strength: multiplier for factor magnitudes (default 1.0)
                - correlation_strength: how correlated factors are (default 0.5)

        Returns:
            RunContext with sampled factors
        """
        rng = np.random.default_rng(seed)
        config = config or {}

        context_strength = config.get('context_strength', 1.0)
        correlation = config.get('correlation_strength', 0.5)

        # Sample correlated factors
        # Start with shared "cursed day" latent
        cursed_latent = rng.normal(0, 1.0)

        # Incubator shift: affects growth and stress sensitivity
        # Correlated with cursed_latent (when day is cursed, incubator is off)
        incubator_shift = (
            correlation * cursed_latent +
            np.sqrt(1 - correlation**2) * rng.normal(0, 1.0)
        ) * 0.3 * context_strength

        # Instrument shift: affects measurement noise and illumination
        # Also correlated with cursed_latent (bad days have bad optics)
        instrument_shift = (
            correlation * cursed_latent +
            np.sqrt(1 - correlation**2) * rng.normal(0, 1.0)
        ) * 0.05 * context_strength  # Reduced from 0.2 → ±5% illumination (was ±22%)

        # Reagent lot shift: channel-specific biases (imaging)
        # Some correlation with cursed_latent, but also independent per-channel
        channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
        reagent_lot_shift = {}
        for channel in channels:
            # Each channel gets: correlated component + independent component
            channel_shift = (
                0.5 * correlation * cursed_latent +  # Some shared
                0.5 * rng.normal(0, 1.0)  # Some independent
            ) * 0.05 * context_strength  # Reduced from 0.15 → ±5% channel bias (was ±16%)
            reagent_lot_shift[channel] = float(channel_shift)

        # Scalar assay reagent lot shift: per-assay biases (biochemical readouts)
        # Similar structure to imaging channels, but for ATP/LDH/UPR/TRAFFICKING kits
        scalar_assays = ['ATP', 'LDH', 'UPR', 'TRAFFICKING']
        scalar_reagent_lot_shift = {}
        for assay in scalar_assays:
            # Each assay kit gets: correlated component + independent component
            assay_shift = (
                0.5 * correlation * cursed_latent +  # Some shared (bad day = bad reagents)
                0.5 * rng.normal(0, 1.0)  # Some independent (each kit is different lot)
            ) * 0.05 * context_strength  # Reduced from 0.15 → ±5% assay bias (was ±16%)
            scalar_reagent_lot_shift[assay] = float(assay_shift)

        # Generate context ID for tracking
        context_id = f"ctx_{seed:08x}"

        # Initialize drift model (if enabled)
        drift_enabled = config.get('drift_enabled', True)
        drift_model = DriftModel(seed + 200) if drift_enabled else None

        # v7: Realism profile and batch metadata
        realism_profile = config.get('realism_profile', 'clean')
        batch_id = config.get('batch_id', f"batch_{seed:08x}")
        operator_id = config.get('operator_id', None)
        media_lot_id = config.get('media_lot_id', None)
        stain_lot_id = config.get('stain_lot_id', None)
        instrument_day = config.get('instrument_day', None)

        return RunContext(
            incubator_shift=float(incubator_shift),
            reagent_lot_shift=reagent_lot_shift,
            scalar_reagent_lot_shift=scalar_reagent_lot_shift,
            instrument_shift=float(instrument_shift),
            seed=seed,
            context_id=context_id,
            drift_enabled=drift_enabled,
            _drift_model=drift_model,
            realism_profile=realism_profile,
            batch_id=batch_id,
            operator_id=operator_id,
            media_lot_id=media_lot_id,
            stain_lot_id=stain_lot_id,
            instrument_day=instrument_day
        )

    def get_biology_modifiers(self) -> Dict[str, float]:
        """
        Get modifiers for biological parameters.

        v6: Biology modifiers are derived from RunBatchProfile (correlated batch effects).

        These create run-level variability (cursed days, media lot variation, incubator drift)
        while preserving:
        - Determinism: same seed → same profile → same modifiers
        - Observer independence: sampled from run seed, not assay RNG
        - Within-run correlation: all vessels in a run share these modifiers
        - Semantic provenance: multipliers have named causes (media lot, incubator, cell state)

        Returns dict with:
        - ec50_multiplier: dose-response shift (from media lot + run context)
        - hazard_multiplier: attrition kinetics shift (from media lot + cell state)
        - growth_rate_multiplier: growth rate shift (from incubator + cell state)
        - burden_half_life_multiplier: washout clearance shift (from incubator)
        - stress_sensitivity: reserved for future use (stress mechanism k_on rates)
        """
        # Lazy initialization: sample profile once, cache multipliers forever
        if self._biology_modifiers is None:
            # Sample profile if not already set (test hook: allows explicit profile injection)
            if self._profile is None:
                # Sample batch effect profile using seed+999 offset (PRESERVED from v5)
                # This RNG is separate from measurement noise (observer independence)
                profile_seed = self.seed + 999

                # Sample profile with correlated latent causes
                self._profile = RunBatchProfile.sample(profile_seed)

            # Derive multipliers from profile (single source of truth)
            self._biology_modifiers = self._profile.to_multipliers()

            # Add stress_sensitivity placeholder (not yet implemented)
            self._biology_modifiers['stress_sensitivity'] = 1.0

        return self._biology_modifiers

    def set_batch_profile_for_testing(self, profile: RunBatchProfile) -> None:
        """
        Inject a custom batch profile for testing (NOT part of stable API).

        This is a test-only hook to allow explicit control over batch effects.
        Use case: Phase 4 tests that need to vary batch profile while holding
        other factors constant.

        WARNING: This bypasses the normal seed+999 sampling. Only use in tests.

        Args:
            profile: RunBatchProfile to inject

        Example:
            >>> ctx = RunContext.sample(seed=42)
            >>> custom_profile = RunBatchProfile.nominal(seed=100)
            >>> ctx.set_batch_profile_for_testing(custom_profile)
            >>> mods = ctx.get_biology_modifiers()  # Uses custom_profile
        """
        if not isinstance(profile, RunBatchProfile):
            raise TypeError(f"Expected RunBatchProfile, got {type(profile)}")

        self._profile = profile
        self._biology_modifiers = None  # Clear cache to force re-derivation

    def get_measurement_modifiers(self, t_hours: float = 0.0, modality: str = 'imaging') -> Dict[str, any]:
        """
        Get modifiers for measurement parameters at time t for specific modality.

        Args:
            t_hours: Time in hours (for within-run drift)
            modality: 'imaging' or 'reader'

        Returns dict with:
        - channel_biases: per-channel intensity multipliers (imaging reagent lots)
        - scalar_assay_biases: per-assay intensity multipliers (biochemical kit lots)
        - noise_inflation: multiplier for measurement CV (instrument drift)
        - gain: global intensity shift for this modality (includes batch + drift)

        Key: imaging and reader gains can drift independently (modality-specific),
        but share some common "cursed day" component via shared wander.
        """
        # Units sanity check (catches seconds vs hours confusion)
        t_hours = float(t_hours)
        assert 0 <= t_hours <= 1000, (
            f"Time must be in hours and < 1000h. Got t_hours={t_hours}. "
            f"If this failed, check that simulated_time is in hours, not seconds."
        )

        # Static batch effects (existing, sampled once per run)
        base_gain = float(np.exp(self.instrument_shift))  # ±5% from batch context

        # Within-run temporal drift (if enabled)
        if self.drift_enabled and self._drift_model is not None:
            drift_gain = self._drift_model.get_gain(t_hours, modality)
            drift_noise_inflation = self._drift_model.get_noise_inflation(t_hours, modality)
        else:
            drift_gain = 1.0
            drift_noise_inflation = 1.0

        # Combine batch and drift
        total_gain = base_gain * drift_gain

        # Imaging reagent lot affects channel intensities
        channel_biases = {
            ch: float(np.exp(shift))  # ±0.05 → 0.95× to 1.05× intensity
            for ch, shift in self.reagent_lot_shift.items()
        }

        # Biochemical reagent lot affects scalar assay intensities
        scalar_assay_biases = {
            assay: float(np.exp(shift))  # ±0.05 → 0.95× to 1.05× intensity
            for assay, shift in self.scalar_reagent_lot_shift.items()
        }

        # Base noise inflation from batch context
        base_noise_inflation = float(1.0 + 0.5 * abs(self.instrument_shift))  # Up to 1.025× more noise

        # Total noise inflation (batch + drift)
        total_noise_inflation = base_noise_inflation * drift_noise_inflation

        return {
            'channel_biases': channel_biases,
            'scalar_assay_biases': scalar_assay_biases,
            'noise_inflation': total_noise_inflation,
            'gain': total_gain,
            # Legacy fields for backward compatibility (can be deprecated later)
            'illumination_bias': total_gain if modality == 'imaging' else base_gain,
            'reader_gain': total_gain if modality == 'reader' else base_gain,
        }

    def get_realism_config(self) -> Dict[str, float]:
        """
        Get realism layer parameters for detector-side effects.

        v7: Demo-visible plate artifacts (position effects, QC pathologies).
        Profiles control the strength of visual realism in plots.

        Returns dict with:
        - position_row_bias_pct: Row gradient magnitude (±N% end-to-end)
        - position_col_bias_pct: Col gradient magnitude (±N% end-to-end)
        - edge_mean_shift_pct: Mean shift at edges (negative = dimmer)
        - edge_noise_multiplier: Noise inflation at edges (1.0 = no change)
        - outlier_rate: Fraction of wells with QC pathologies (0.0-1.0)
        - batch_effect_strength: Amplify existing batch shifts (1.0 = normal)

        Profile presets:
        - clean: All effects disabled (default for existing tests)
        - realistic: Moderate effects (visible but plausible)
        - hostile: Strong effects (stress-test agent robustness)
        """
        profile = self.realism_profile.lower()

        if profile == "realistic":
            return {
                'position_row_bias_pct': 2.0,
                'position_col_bias_pct': 2.0,
                'edge_mean_shift_pct': -5.0,
                'edge_noise_multiplier': 2.0,
                'outlier_rate': 0.01,
                'batch_effect_strength': 1.0,
            }
        elif profile == "hostile":
            return {
                'position_row_bias_pct': 3.0,
                'position_col_bias_pct': 3.0,
                'edge_mean_shift_pct': -7.0,
                'edge_noise_multiplier': 2.5,
                'outlier_rate': 0.03,
                'batch_effect_strength': 1.5,
            }
        else:  # "clean" or unknown
            return {
                'position_row_bias_pct': 0.0,
                'position_col_bias_pct': 0.0,
                'edge_mean_shift_pct': 0.0,
                'edge_noise_multiplier': 1.0,
                'outlier_rate': 0.0,
                'batch_effect_strength': 1.0,
            }

    def summary(self) -> str:
        """Human-readable summary of context effects."""
        bio_mods = self.get_biology_modifiers()
        meas_mods = self.get_measurement_modifiers()

        summary = [
            f"RunContext: {self.context_id}",
            f"  Biology:",
            f"    EC50: {bio_mods['ec50_multiplier']:.3f}×",
            f"    Stress sensitivity: {bio_mods['stress_sensitivity']:.3f}×",
            f"    Growth rate: {bio_mods['growth_rate_multiplier']:.3f}×",
            f"  Measurement:",
            f"    Noise inflation: {meas_mods['noise_inflation']:.3f}×",
            f"    Illumination bias: {meas_mods['illumination_bias']:.3f}×",
            f"    Channel biases: er={meas_mods['channel_biases']['er']:.3f}×, "
            f"mito={meas_mods['channel_biases']['mito']:.3f}×, "
            f"actin={meas_mods['channel_biases']['actin']:.3f}×"
        ]
        return "\n".join(summary)

    def to_dict(self) -> Dict:
        """
        Serialize RunContext for logging (v6: includes batch effect provenance).

        Returns dict with:
        - context_id: run identifier
        - seed: RNG seed
        - batch_effects: semantic provenance (schema_version, profile, multipliers, hash)
        - measurement_effects: instrument/reagent biases (for future use)

        This is the single source of truth for "why did this run behave this way?"
        """
        # Force profile initialization if not already cached
        bio_mods = self.get_biology_modifiers()

        # Get profile serialization (includes schema_version, mapping_version, profile_hash)
        batch_effects_dict = self._profile.to_dict() if self._profile else None

        # Get measurement modifiers (for completeness)
        meas_mods = self.get_measurement_modifiers()

        return {
            'context_id': self.context_id,
            'seed': self.seed,
            'batch_effects': batch_effects_dict,
            'measurement_effects': {
                'channel_biases': meas_mods['channel_biases'],
                'scalar_assay_biases': meas_mods['scalar_assay_biases'],
                'noise_inflation': meas_mods['noise_inflation'],
                'illumination_bias': meas_mods['illumination_bias'],
                'reader_gain': meas_mods['reader_gain']
            }
        }


def sample_plating_context(seed: int, config: Optional[Dict] = None) -> Dict[str, float]:
    """
    Sample per-plate plating artifacts (Injection #2 prep).

    Returns dict with:
    - seeding_density_error: fractional error in seeded density (-0.2 to +0.2)
    - post_dissociation_stress: initial stress level (0 to 0.3)
    - clumpiness: spatial heterogeneity factor (0 to 0.3)
    - tau_recovery_h: recovery time constant (6 to 16 hours)
    """
    rng = np.random.default_rng(seed)
    config = config or {}

    strength = config.get('plating_artifact_strength', 1.0)

    return {
        'seeding_density_error': float(rng.uniform(-0.2, 0.2) * strength),
        'post_dissociation_stress': float(rng.uniform(0.0, 0.3) * strength),
        'clumpiness': float(rng.uniform(0.0, 0.3) * strength),
        'tau_recovery_h': float(rng.uniform(6.0, 16.0))
    }


def pipeline_transform(
    morphology: Dict[str, float],
    context: 'RunContext',
    batch_id: str,
    plate_id: Optional[str] = None
) -> Dict[str, float]:
    """
    Phase 5B Injection #3: Pipeline Drift

    Apply batch-dependent feature extraction failures to morphology.

    This creates "same biology, different features" outcomes that prevent
    feature overtrust. Two batches can genuinely disagree on channel intensities,
    not just due to Gaussian noise.

    Transforms applied:
    1. Affine transforms per batch (rotation/scaling in feature space)
    2. Channel-specific segmentation bias (nucleus area shifts)
    3. Discrete failure modes (focus off, illumination correction wrong)

    Key: Pipeline drift is mildly correlated with reagent_lot_shift so that
    "cursed days" affect both biology AND feature extraction in the same direction.
    This creates the most realistic suffering where naive policies get seduced.

    Args:
        morphology: True morphology dict (er, mito, nucleus, actin, rna)
        context: RunContext with reagent lot effects
        batch_id: Batch identifier for deterministic pipeline effects
        plate_id: Optional plate identifier for per-plate failures

    Returns:
        Transformed morphology with batch-dependent biases
    """
    import hashlib

    # Deterministic RNG per batch
    batch_seed = int.from_bytes(
        hashlib.blake2s(batch_id.encode(), digest_size=4).digest(), "little"
    )
    rng_batch = np.random.default_rng(batch_seed)

    # Start with copy of true morphology
    transformed = morphology.copy()

    # 1. Channel-specific segmentation bias (correlated with reagent lot)
    # When reagent lot is bad, segmentation also tends to be off
    # Correlation = 0.3 (mild, not deterministic)
    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        reagent_shift = context.reagent_lot_shift.get(channel, 0.0)

        # Pipeline bias: 30% correlated with reagent lot + 70% independent
        pipeline_bias = (
            0.3 * reagent_shift +  # Correlated component
            0.7 * rng_batch.normal(0, 0.1)  # Independent component
        )

        # Apply as multiplicative bias (segmentation threshold shifts)
        transformed[channel] *= float(np.exp(pipeline_bias))

    # 2. Affine transform in feature space (batch-specific rotation/scaling)
    # Some batches compress ER-mito separation, others amplify it
    # This creates "same compound, different conclusion" at the feature level
    affine_scale_er = float(np.exp(rng_batch.normal(0, 0.05)))
    affine_scale_mito = float(np.exp(rng_batch.normal(0, 0.05)))

    transformed['er'] *= affine_scale_er
    transformed['mito'] *= affine_scale_mito

    # 3. Discrete failure modes (rare but catastrophic)
    # These are per-plate, not per-batch (plate-level QC failures)
    if plate_id is not None:
        plate_seed = int.from_bytes(
            hashlib.blake2s(f"{batch_id}_{plate_id}".encode(), digest_size=4).digest(), "little"
        )
        rng_plate = np.random.default_rng(plate_seed)

        failure_prob = 0.05  # 5% of plates have systematic failures
        if rng_plate.random() < failure_prob:
            failure_type = rng_plate.choice(['focus_off', 'illumination_wrong', 'segmentation_fail'])

            if failure_type == 'focus_off':
                # Out of focus → all channels dimmer and blurrier (reduced dynamic range)
                focus_penalty = rng_plate.uniform(0.7, 0.9)
                for channel in transformed:
                    transformed[channel] *= focus_penalty

            elif failure_type == 'illumination_wrong':
                # Illumination correction failed → channel-dependent intensity shifts
                for channel in transformed:
                    illum_shift = rng_plate.uniform(0.8, 1.3)
                    transformed[channel] *= illum_shift

            elif failure_type == 'segmentation_fail':
                # Segmentation thresholds wrong → nucleus/actin ratio off
                transformed['nucleus'] *= rng_plate.uniform(0.6, 0.8)
                transformed['actin'] *= rng_plate.uniform(1.2, 1.5)

    # Ensure no negative values
    for channel in transformed:
        transformed[channel] = max(0.0, transformed[channel])

    return transformed
