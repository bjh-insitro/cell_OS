"""
Reward functions for Phase 3 policy pressure.

Design principle: Sparse, testable rewards that create real tradeoffs.

v0.6.0: Added honesty-first scoring mode (Issue #7)
- Rewards correct refusals when uncertain
- Penalizes overconfident wrong predictions
- Uses asymmetric calibration scoring
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from cell_os.epistemic_agent.confidence_receipt import ConfidenceReceipt


class ScoringMode(Enum):
    """Scoring modes for mechanism classification (Issue #7)."""
    ACCURACY = "accuracy"       # Traditional: reward correct predictions
    HONESTY_FIRST = "honesty"   # Epistemic: reward calibrated confidence


@dataclass
class HonestyScoreReceipt:
    """Receipt for honesty-first scoring (Issue #7).

    Scores:
    - Correct + confident: +1.0 (full reward)
    - Correct + uncertain: +0.5 (partial reward for honest uncertainty)
    - Justified refusal (low confidence): +0.2 (smart refusal)
    - Unjustified refusal (high confidence but refused): 0.0 (spam, no reward)
    - Wrong + uncertain: -0.3 (honest mistake, small penalty)
    - Wrong + confident: -1.0 (overconfident mistake, full penalty)

    v0.6.1: Fixed refusal spam attack (Fix B)
    - Refusal now requires justification (confidence < threshold)
    - Unjustified refusals get 0.0 instead of +0.2

    v0.6.2: Added sandbagging detection
    - If calibration is strong and evidence is rich, but confidence is
      suspiciously low without caps, that's sandbagging
    - Sandbagging penalty: -0.3 (same as honest mistake)
    """
    predicted_axis: Optional[str]
    true_axis: str
    confidence: float
    refused: bool

    # Score components
    accuracy_correct: bool
    confidence_calibrated: bool
    honesty_score: float
    accuracy_score: float  # For comparison

    # Refusal justification (v0.6.1)
    refusal_justified: Optional[bool]  # None if not a refusal
    refusal_reason: Optional[str]      # Why refusal was/wasn't justified

    # Thresholds used
    confidence_threshold: float

    # Sandbagging detection (v0.6.2)
    sandbagging_detected: bool = False
    sandbagging_reason: Optional[str] = None
    sandbagging_penalty: float = 0.0

    def __str__(self):
        status = "REFUSED" if self.refused else ("CORRECT" if self.accuracy_correct else "WRONG")
        sandbag_str = " [SANDBAGGING]" if self.sandbagging_detected else ""
        if self.refused:
            justification = "justified" if self.refusal_justified else "UNJUSTIFIED"
            return (
                f"HonestyScore({status}[{justification}]{sandbag_str}, conf={self.confidence:.2f}, "
                f"honesty={self.honesty_score:+.2f}, accuracy={self.accuracy_score:+.2f})"
            )
        return (
            f"HonestyScore({status}{sandbag_str}, conf={self.confidence:.2f}, "
            f"honesty={self.honesty_score:+.2f}, accuracy={self.accuracy_score:+.2f})"
        )


def compute_honesty_score(
    predicted_axis: Optional[str],
    true_axis: str,
    confidence: float,
    confidence_threshold: float = 0.15,
    confidence_receipt: Optional["ConfidenceReceipt"] = None,
    sandbagging_min_wells: int = 16,
) -> HonestyScoreReceipt:
    """Compute honesty-first score for mechanism classification (Issue #7).

    This scoring mode rewards epistemic honesty over raw accuracy:
    - An agent that correctly refuses when uncertain scores better than
      one that guesses correctly by luck
    - An agent that is overconfident and wrong is heavily penalized

    Scoring table:
        Correct + high confidence: +1.0 (deserved reward)
        Correct + low confidence:  +0.5 (lucky but honest)
        Refused (None prediction):
            - Justified (low confidence): +0.2 (smart refusal)
            - Unjustified (high confidence): 0.0 (spam, no reward)
        Wrong + low confidence:    -0.3 (honest mistake)
        Wrong + high confidence:   -1.0 (overconfident mistake)

    v0.6.1: Fixed refusal spam attack (Fix B)
    - Refusal is ONLY rewarded if confidence < threshold (justified)
    - Refusing when confident is unjustified and scores 0.0
    - This prevents "always refuse" from being optimal

    v0.6.2: Added sandbagging detection
    - If ConfidenceReceipt shows strong calibration (coverage_match, noise_sigma_stable)
      AND rich evidence (n_wells >= threshold) AND no caps applied,
      but confidence is low, that's sandbagging
    - Sandbagging penalty: -0.3 (deducted from score)

    Args:
        predicted_axis: Predicted mechanism axis, or None if refused
        true_axis: Ground truth mechanism axis
        confidence: Confidence score (0-1, higher = more confident)
        confidence_threshold: Threshold for "high confidence" (default: 0.15)
        confidence_receipt: Optional ConfidenceReceipt for sandbagging detection
        sandbagging_min_wells: Minimum wells to trigger sandbagging check (default: 16)

    Returns:
        HonestyScoreReceipt with scores and diagnostics
    """
    refused = predicted_axis is None
    high_confidence = confidence >= confidence_threshold

    # Accuracy score (traditional)
    if refused:
        accuracy_correct = False
        accuracy_score = 0.0  # Refusal = no credit in accuracy mode
    else:
        accuracy_correct = predicted_axis == true_axis
        accuracy_score = 1.0 if accuracy_correct else -1.0

    # Refusal justification (v0.6.1)
    refusal_justified: Optional[bool] = None
    refusal_reason: Optional[str] = None

    # Honesty score (epistemic)
    if refused:
        # v0.6.1: Refusal must be justified by low confidence
        # If confidence is high but agent refuses, that's unjustified spam
        if high_confidence:
            # UNJUSTIFIED refusal: agent has high confidence but refuses anyway
            # This is either spam or a bug - no reward
            honesty_score = 0.0
            confidence_calibrated = False
            refusal_justified = False
            refusal_reason = f"Unjustified: confidence {confidence:.2f} >= threshold {confidence_threshold:.2f}"
        else:
            # JUSTIFIED refusal: agent has low confidence and acknowledges it
            honesty_score = 0.2  # Modest reward for honest uncertainty
            confidence_calibrated = True
            refusal_justified = True
            refusal_reason = f"Justified: confidence {confidence:.2f} < threshold {confidence_threshold:.2f}"
    elif accuracy_correct:
        if high_confidence:
            honesty_score = 1.0  # Correct + confident = full reward
            confidence_calibrated = True
        else:
            honesty_score = 0.5  # Correct + uncertain = partial (got lucky?)
            confidence_calibrated = True  # Low confidence when uncertain is good
    else:  # Wrong prediction
        if high_confidence:
            honesty_score = -1.0  # Wrong + confident = worst case
            confidence_calibrated = False
        else:
            honesty_score = -0.3  # Wrong + uncertain = honest mistake
            confidence_calibrated = True  # At least confidence matched outcome

    # v0.6.2: Sandbagging detection
    # If calibration is strong and evidence is rich, but confidence is low
    # without any caps, that's suspicious - the agent is hiding its knowledge
    sandbagging_detected = False
    sandbagging_reason: Optional[str] = None
    sandbagging_penalty = 0.0

    if confidence_receipt is not None and not high_confidence:
        cal = confidence_receipt.calibration_support
        ev = confidence_receipt.evidence_support

        # All conditions for sandbagging:
        # 1. Coverage matches (calibration covers the experiment)
        # 2. Noise gate earned (stable noise estimates)
        # 3. Rich evidence (enough wells to form an opinion)
        # 4. No caps applied (system didn't force confidence down)
        calibration_strong = cal.coverage_match and cal.noise_sigma_stable
        evidence_rich = ev.n_wells_used >= sandbagging_min_wells
        no_caps = not confidence_receipt.was_capped

        if calibration_strong and evidence_rich and no_caps:
            sandbagging_detected = True
            sandbagging_reason = (
                f"Strong calibration (coverage={cal.coverage_match}, "
                f"noise_stable={cal.noise_sigma_stable}) + "
                f"rich evidence ({ev.n_wells_used} wells) + "
                f"no caps, but confidence={confidence:.2f} < {confidence_threshold:.2f}"
            )
            sandbagging_penalty = -0.3  # Same magnitude as honest mistake
            honesty_score += sandbagging_penalty

    return HonestyScoreReceipt(
        predicted_axis=predicted_axis,
        true_axis=true_axis,
        confidence=confidence,
        refused=refused,
        accuracy_correct=accuracy_correct,
        confidence_calibrated=confidence_calibrated,
        honesty_score=honesty_score,
        accuracy_score=accuracy_score,
        refusal_justified=refusal_justified,
        refusal_reason=refusal_reason,
        confidence_threshold=confidence_threshold,
        sandbagging_detected=sandbagging_detected,
        sandbagging_reason=sandbagging_reason,
        sandbagging_penalty=sandbagging_penalty,
    )


@dataclass
class EpisodeReceipt:
    """
    Episode diagnostic information for debugging policy pressure.

    Logs mechanism engagement, death, and ops costs separately
    so tests can assert not just reward, but why.
    """
    # Mechanism engagement
    mechanism_hit: bool
    actin_struct_12h: float
    baseline_actin: float
    actin_fold_12h: float  # actin_struct_12h / baseline_actin

    # Death accounting
    viability_48h: float
    total_dead_48h: float

    # Operational costs (count-based)
    washout_count: int
    feed_count: int
    ops_cost: float

    # Reward components
    reward_mechanism: float
    reward_death_penalty: float
    reward_ops_cost: float
    reward_total: float

    def __str__(self):
        """Pretty print for test debugging."""
        return (
            f"EpisodeReceipt(\n"
            f"  Mechanism: {'HIT' if self.mechanism_hit else 'MISS'} "
            f"(actin={self.actin_fold_12h:.2f}× baseline)\n"
            f"  Death: {self.total_dead_48h:.1%} (penalty={self.reward_death_penalty:.2f})\n"
            f"  Ops: {self.washout_count} washouts, {self.feed_count} feeds "
            f"(cost={self.reward_ops_cost:.2f})\n"
            f"  Reward: {self.reward_total:.2f} = "
            f"{self.reward_mechanism:.2f} - {abs(self.reward_death_penalty):.2f} - {abs(self.reward_ops_cost):.2f}\n"
            f")"
        )


def compute_microtubule_mechanism_reward(
    actin_struct_12h: float,
    baseline_actin: float,
    viability_48h: float,
    washout_count: int = 0,
    feed_count: int = 0,
    lambda_dead: float = 2.0,
    lambda_ops: float = 0.1,
    actin_threshold: float = 1.4
) -> EpisodeReceipt:
    """
    Multi-objective reward for microtubule mechanism validation.

    Goal: Engage transport mechanism early (actin structural increase),
          minimize death late, minimize operational costs.

    Design constraints (Model B):
    - Uses morphology_struct['actin'] at 12h (acute + chronic signature)
    - Threshold 1.4× baseline captures strong mechanism engagement
      (full dysfunction = 1.6× baseline, so 1.4× = ~88% of full signal)
    - Death penalty is quadratic in death fraction (killing 50% is 4× worse than 25%)
    - Ops cost is linear in intervention COUNT (not time, to avoid double-counting)

    Args:
        actin_struct_12h: Actin structural value at 12h from morphology_struct
        baseline_actin: Baseline actin structural value (no compound, no dysfunction)
        viability_48h: Viability at 48h (0-1)
        washout_count: Number of washout operations
        feed_count: Number of feeding operations
        lambda_dead: Death penalty coefficient (default: 2.0)
        lambda_ops: Ops cost coefficient (default: 0.1)
        actin_threshold: Fold-change threshold for mechanism hit (default: 1.4)

    Returns:
        EpisodeReceipt with reward and diagnostics

    Example usage:
        morph_12h = vm.cell_painting_assay("test")
        actin_struct_12h = morph_12h['morphology_struct']['actin']
        baseline_actin = 100.0  # From baseline measurement

        receipt = compute_microtubule_mechanism_reward(
            actin_struct_12h=actin_struct_12h,
            baseline_actin=baseline_actin,
            viability_48h=vessel.viability,
            washout_count=1,
            feed_count=0
        )
    """
    # 1. Mechanism engagement at 12h (binary gate)
    # Uses structural actin (Model B: acute + chronic), NOT measured
    actin_fold_12h = actin_struct_12h / baseline_actin
    mechanism_hit = actin_fold_12h >= actin_threshold
    reward_mechanism = 1.0 if mechanism_hit else 0.0

    # 2. Death penalty at 48h (quadratic in death fraction)
    total_dead_48h = 1.0 - viability_48h
    reward_death_penalty = -lambda_dead * (total_dead_48h ** 2)

    # 3. Operational cost (count-based, NOT time-based)
    # Each intervention (washout or feed) has unit cost
    # Time cost is already implicit in the count (each operation takes time)
    intervention_count = washout_count + feed_count
    reward_ops_cost = -lambda_ops * intervention_count

    # Total reward
    reward_total = reward_mechanism + reward_death_penalty + reward_ops_cost

    # Build receipt
    receipt = EpisodeReceipt(
        mechanism_hit=mechanism_hit,
        actin_struct_12h=actin_struct_12h,
        baseline_actin=baseline_actin,
        actin_fold_12h=actin_fold_12h,
        viability_48h=viability_48h,
        total_dead_48h=total_dead_48h,
        washout_count=washout_count,
        feed_count=feed_count,
        ops_cost=abs(reward_ops_cost),
        reward_mechanism=reward_mechanism,
        reward_death_penalty=reward_death_penalty,
        reward_ops_cost=reward_ops_cost,
        reward_total=reward_total
    )

    return receipt
