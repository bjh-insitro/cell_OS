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

        return RunContext(
            incubator_shift=float(incubator_shift),
            reagent_lot_shift=reagent_lot_shift,
            scalar_reagent_lot_shift=scalar_reagent_lot_shift,
            instrument_shift=float(instrument_shift),
            seed=seed,
            context_id=context_id
        )

    def get_biology_modifiers(self) -> Dict[str, float]:
        """
        Get modifiers for biological parameters.

        IMPORTANT FIX #5: Biology modifiers are now CONSTANT across runs.
        Run-to-run variability should come from MEASUREMENT drift, not biology drift.

        Incubator effects on biology (ec50, stress sensitivity, growth rate) are
        intentionally disabled to maintain observer independence.

        If you want biology variation, it should be:
        1. Sampled from base_seed (not run_id), OR
        2. Explicitly modeled as a separate "biological batch effect" with clear semantics

        Returns dict with:
        - ec50_multiplier: ALWAYS 1.0 (no EC50 variation)
        - stress_sensitivity: ALWAYS 1.0 (no stress variation)
        - growth_rate_multiplier: ALWAYS 1.0 (no growth variation)
        """
        # FIX #5: Return constants to preserve biology invariance across runs
        # Previously: these were functions of self.incubator_shift, causing run-dependent biology
        return {
            'ec50_multiplier': 1.0,
            'stress_sensitivity': 1.0,
            'growth_rate_multiplier': 1.0
        }

    def get_measurement_modifiers(self) -> Dict[str, any]:
        """
        Get modifiers for measurement parameters.

        Returns dict with:
        - channel_biases: per-channel intensity multipliers (imaging reagent lots)
        - scalar_assay_biases: per-assay intensity multipliers (biochemical kit lots)
        - noise_inflation: multiplier for measurement CV (instrument drift)
        - illumination_bias: global intensity shift for imaging (lamp aging, focus drift)
        - reader_gain: global intensity shift for plate reader (scalar assays)

        Key: illumination_bias and reader_gain are CORRELATED (both from instrument_shift),
        so imaging and biochemical assays share measurement curse on bad days.
        """
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

        # Instrument shift affects noise and ALL intensity measurements
        # CRITICAL: illumination_bias (imaging) and reader_gain (plate reader) are CORRELATED
        # via shared instrument_shift latent, so cross-modality disagreement teaches caution
        noise_inflation = float(1.0 + 0.5 * abs(self.instrument_shift))  # Up to 1.025× more noise
        illumination_bias = float(np.exp(self.instrument_shift))  # ±0.05 → 0.95× to 1.05× intensity (imaging)
        reader_gain = float(np.exp(self.instrument_shift))  # ±0.05 → 0.95× to 1.05× intensity (plate reader)

        return {
            'channel_biases': channel_biases,
            'scalar_assay_biases': scalar_assay_biases,
            'noise_inflation': noise_inflation,
            'illumination_bias': illumination_bias,
            'reader_gain': reader_gain
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
