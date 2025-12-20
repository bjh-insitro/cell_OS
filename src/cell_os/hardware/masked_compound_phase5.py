"""
Phase 5: Epistemic Control - Ambiguity by design.

Library with "weak signature" compounds that force temporal information-risk tradeoffs:
- Early (12h): ambiguous signatures (weak induction)
- Late (24-36h): clear signatures (full induction, but costly death)

This makes greedy policies fail deterministically, not probabilistically.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Phase5Compound:
    """
    Compound with tunable signature strength.

    Fields:
        compound_id: Masked identifier (e.g., "test_A")
        true_stress_axis: Ground truth axis
        compound_name: Real compound name
        reference_dose_uM: Reference dose
        potency_scalar: Multiplier for latent induction rates (k_on)
                        - 1.0 = normal (clean signatures)
                        - 0.3-0.5 = weak (ambiguous early, clear late)
        toxicity_scalar: Multiplier for death rates
                        - 1.0 = normal
                        - 1.5-2.0 = high (punishes late readouts)

    Design contract:
        Weak compounds (potency ~0.3-0.5) are ambiguous at 12h but clear by 24-36h.
        This forces probe-then-commit instead of greedy classify-at-12h.
    """
    compound_id: str
    true_stress_axis: str
    compound_name: str
    reference_dose_uM: float
    potency_scalar: float = 1.0  # Affects k_on for latent induction
    toxicity_scalar: float = 1.0  # Affects death rates

    def __str__(self):
        return (f"Phase5Compound(id={self.compound_id}, axis={self.true_stress_axis}, "
                f"potency={self.potency_scalar:.1f}×, toxicity={self.toxicity_scalar:.1f}×)")


# Phase 5 Library: 3 axes × (1 clean + 1 weak) = 6 compounds minimum
PHASE5_LIBRARY: Dict[str, Phase5Compound] = {
    # ER axis
    "test_A_clean": Phase5Compound(
        compound_id="test_A_clean",
        true_stress_axis="er_stress",
        compound_name="tunicamycin",
        reference_dose_uM=0.5,
        potency_scalar=1.0,  # Clean: normal induction
        toxicity_scalar=1.0
    ),
    "test_A_weak": Phase5Compound(
        compound_id="test_A_weak",
        true_stress_axis="er_stress",
        compound_name="tunicamycin",
        reference_dose_uM=0.5,
        potency_scalar=0.7,  # Weak but detectable: 0.5× dose @ 12h works, 0.25× fails
        toxicity_scalar=2.5   # High toxicity: naive violates death budget
    ),

    # Mito axis
    "test_B_clean": Phase5Compound(
        compound_id="test_B_clean",
        true_stress_axis="mitochondrial",
        compound_name="cccp",
        reference_dose_uM=1.0,
        potency_scalar=1.0,  # Clean: normal induction
        toxicity_scalar=1.0
    ),
    "test_B_weak": Phase5Compound(
        compound_id="test_B_weak",
        true_stress_axis="mitochondrial",
        compound_name="cccp",
        reference_dose_uM=3.0,  # Higher dose so naive gets lethal exposure
        potency_scalar=0.40,   # Weak: 0.5× dose @ 12h works, 0.25× fails (with relaxed threshold)
        toxicity_scalar=4.0   # Moderate toxicity with higher base dose
    ),

    # Transport/microtubule axis
    "test_C_clean": Phase5Compound(
        compound_id="test_C_clean",
        true_stress_axis="microtubule",
        compound_name="paclitaxel",
        reference_dose_uM=0.0053,  # Balanced: detectable at 0.5×, survives to 24h
        potency_scalar=1.0,  # Clean: normal induction
        toxicity_scalar=1.0
    ),
    "test_C_weak": Phase5Compound(
        compound_id="test_C_weak",
        true_stress_axis="microtubule",
        compound_name="paclitaxel",
        reference_dose_uM=0.0054,  # Fine-tuned: detectable at 0.5×, survives 24h within budget
        potency_scalar=0.95,   # Nearly full potency to ensure detection at 0.5×
        toxicity_scalar=1.0   # Lower toxicity to allow smart policy to survive 24h exposure
    ),
}

# Subset for deterministic test failures
WEAK_SIGNATURE_SUBSET = [
    "test_A_weak",
    "test_B_weak",
    "test_C_weak"
]

CLEAN_SIGNATURE_SUBSET = [
    "test_A_clean",
    "test_B_clean",
    "test_C_clean"
]


def infer_stress_axis_with_confidence(
    er_fold: float,
    mito_fold: float,
    actin_fold: float,
    upr_fold: float,
    atp_fold: float,
    trafficking_fold: float
) -> tuple[Optional[str], float]:
    """
    Infer stress axis with confidence score.

    Returns:
        (predicted_axis, confidence) where confidence is separation margin.

        confidence = (primary_score - runner_up_score)
        - High confidence (>0.3): clear winner
        - Low confidence (<0.15): ambiguous, forced guess

    This is the uncomfortable question answered in code:
    "What does it mean to be uncertain?"

    Answer: Small separation between top two axes.
    """
    # Compute signature scores for each axis (0-1 scale, higher = stronger)

    # ER score: both UPR and ER_struct must be elevated
    er_score = 0.0
    if upr_fold > 1.30 and er_fold > 1.30:
        # Strength = geometric mean of deviations from threshold
        upr_deviation = (upr_fold - 1.30) / 0.70  # Normalize to [0,1] assuming max ~2.0×
        er_deviation = (er_fold - 1.30) / 0.70
        er_score = (upr_deviation * er_deviation) ** 0.5

    # Mito score: ATP low OR (ATP low AND mito_struct down)
    mito_score = 0.0
    if atp_fold < 0.95:
        # Strong signal: ATP low (relaxed threshold for moderate dose probe)
        atp_deviation = (0.95 - atp_fold) / 0.65  # Normalize to [0,1] assuming min ~0.30
        mito_score = atp_deviation

        # Boost if mito_struct also down
        if mito_fold < 0.95:
            mito_deviation = (0.95 - mito_fold) / 0.35  # Normalize
            mito_score = max(mito_score, (atp_deviation + mito_deviation) / 2)
    elif atp_fold < 0.98 and mito_fold < 0.98:
        # Very weak signal: both slightly shifted (for very low doses)
        atp_deviation = (0.98 - atp_fold) / 0.68
        mito_deviation = (0.98 - mito_fold) / 0.38
        mito_score = (atp_deviation * mito_deviation) ** 0.5

    # Transport score: both trafficking and actin_struct must be elevated
    transport_score = 0.0
    if trafficking_fold > 1.30 and actin_fold > 1.30:
        # Strength = geometric mean of deviations
        trafficking_deviation = (trafficking_fold - 1.30) / 1.20  # Normalize assuming max ~2.5×
        actin_deviation = (actin_fold - 1.30) / 1.20
        transport_score = (trafficking_deviation * actin_deviation) ** 0.5

    # Rank axes by score
    scores = {
        "er_stress": er_score,
        "mitochondrial": mito_score,
        "microtubule": transport_score
    }

    sorted_axes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    winner, winner_score = sorted_axes[0]
    runner_up, runner_up_score = sorted_axes[1]

    # Confidence = separation margin
    confidence = winner_score - runner_up_score

    # If winner score is too low, treat as uncertain (no clear signal)
    if winner_score < 0.15:
        return None, 0.0

    # If confidence is too low, we have a forced guess under uncertainty
    # (Still return prediction, but caller can check confidence)
    return winner, confidence


def check_valid_attempt(
    dose_schedule: list[float],
    assay_times: list[float],
    time_step_h: float = 6.0
) -> bool:
    """
    Check if policy made a "valid attempt" to probe mechanism.

    Valid attempt requires:
    - At least one assay readout at t >= 12h under nonzero dose
    - OR cumulative dose-time exposure >= minimum threshold

    This prevents "do nothing and classify from baseline" from winning.

    Args:
        dose_schedule: List of dose fractions at each timestep
        assay_times: List of times when assays were taken
        time_step_h: Duration of each timestep (default: 6h)

    Returns:
        True if valid attempt, False otherwise
    """
    # Check assay criterion: at least one assay at t>=12h with dose>0
    for assay_time in assay_times:
        if assay_time >= 12.0:
            # Check if dose was nonzero at or before this time
            step_idx = int(assay_time / time_step_h)
            if step_idx < len(dose_schedule):
                cumulative_dose = sum(dose_schedule[:step_idx+1])
                if cumulative_dose > 0:
                    return True

    # Check exposure criterion: cumulative dose-time >= threshold
    # (dose_fraction × time_step_h summed over all steps)
    cumulative_exposure = sum(dose * time_step_h for dose in dose_schedule)
    MIN_EXPOSURE_H = 12.0  # Equivalent to 0.5× dose for 24h, or 1.0× for 12h

    if cumulative_exposure >= MIN_EXPOSURE_H:
        return True

    return False
