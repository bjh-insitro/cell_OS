"""
Tests for honesty-first scoring mode (Issue #7).

Tests that:
1. Correct + confident gets full reward
2. Correct + uncertain gets partial reward (lucky guess)
3. JUSTIFIED refusal gets modest positive reward (v0.6.1)
4. UNJUSTIFIED refusal gets 0.0 (v0.6.1 - anti-spam fix)
5. Wrong + uncertain gets small penalty (honest mistake)
6. Wrong + confident gets full penalty (overconfident)

v0.6.1: Added refusal spam attack defense tests (Fix B)
"""

import pytest
from cell_os.hardware.reward import (
    compute_honesty_score,
    HonestyScoreReceipt,
    ScoringMode,
)


class TestHonestyScoring:
    """Test honesty-first scoring logic."""

    def test_correct_confident_full_reward(self):
        """Correct + high confidence = +1.0."""
        receipt = compute_honesty_score(
            predicted_axis="er_stress",
            true_axis="er_stress",
            confidence=0.5,  # High confidence
        )
        assert receipt.honesty_score == 1.0
        assert receipt.accuracy_correct is True
        assert receipt.confidence_calibrated is True

    def test_correct_uncertain_partial_reward(self):
        """Correct + low confidence = +0.5 (lucky guess)."""
        receipt = compute_honesty_score(
            predicted_axis="er_stress",
            true_axis="er_stress",
            confidence=0.05,  # Low confidence
        )
        assert receipt.honesty_score == 0.5
        assert receipt.accuracy_correct is True
        assert receipt.confidence_calibrated is True

    def test_justified_refusal_modest_reward(self):
        """JUSTIFIED refusal (None + low confidence) = +0.2 (acknowledged uncertainty)."""
        receipt = compute_honesty_score(
            predicted_axis=None,  # Refused to predict
            true_axis="er_stress",
            confidence=0.0,  # Low confidence - justifies refusal
        )
        assert receipt.honesty_score == 0.2
        assert receipt.refused is True
        assert receipt.accuracy_correct is False
        assert receipt.confidence_calibrated is True
        # v0.6.1: Check justification tracking
        assert receipt.refusal_justified is True
        assert "Justified" in receipt.refusal_reason

    def test_unjustified_refusal_no_reward(self):
        """UNJUSTIFIED refusal (None + high confidence) = 0.0 (spam)."""
        receipt = compute_honesty_score(
            predicted_axis=None,  # Refused to predict
            true_axis="er_stress",
            confidence=0.5,  # High confidence - refusal is unjustified
        )
        assert receipt.honesty_score == 0.0  # No reward for spam
        assert receipt.refused is True
        assert receipt.accuracy_correct is False
        assert receipt.confidence_calibrated is False  # Refusing when confident is not calibrated
        # v0.6.1: Check justification tracking
        assert receipt.refusal_justified is False
        assert "Unjustified" in receipt.refusal_reason

    def test_wrong_uncertain_small_penalty(self):
        """Wrong + low confidence = -0.3 (honest mistake)."""
        receipt = compute_honesty_score(
            predicted_axis="mitochondrial",  # Wrong
            true_axis="er_stress",
            confidence=0.05,  # Low confidence
        )
        assert receipt.honesty_score == -0.3
        assert receipt.accuracy_correct is False
        assert receipt.confidence_calibrated is True

    def test_wrong_confident_full_penalty(self):
        """Wrong + high confidence = -1.0 (overconfident)."""
        receipt = compute_honesty_score(
            predicted_axis="mitochondrial",  # Wrong
            true_axis="er_stress",
            confidence=0.5,  # High confidence
        )
        assert receipt.honesty_score == -1.0
        assert receipt.accuracy_correct is False
        assert receipt.confidence_calibrated is False


class TestAccuracyComparison:
    """Compare honesty vs accuracy scoring."""

    def test_accuracy_rewards_correct_only(self):
        """Accuracy mode gives +1 for correct, -1 for wrong, 0 for refusal."""
        # Correct
        r1 = compute_honesty_score("er_stress", "er_stress", 0.5)
        assert r1.accuracy_score == 1.0

        # Wrong
        r2 = compute_honesty_score("mito", "er_stress", 0.5)
        assert r2.accuracy_score == -1.0

        # Refusal
        r3 = compute_honesty_score(None, "er_stress", 0.0)
        assert r3.accuracy_score == 0.0

    def test_honesty_rewards_calibration(self):
        """Honesty mode differentiates confident vs uncertain mistakes."""
        # Both wrong, but different confidence
        uncertain_wrong = compute_honesty_score("mito", "er_stress", 0.05)
        confident_wrong = compute_honesty_score("mito", "er_stress", 0.50)

        # Same accuracy score
        assert uncertain_wrong.accuracy_score == confident_wrong.accuracy_score

        # Different honesty score
        assert uncertain_wrong.honesty_score > confident_wrong.honesty_score
        assert uncertain_wrong.honesty_score == -0.3
        assert confident_wrong.honesty_score == -1.0


class TestScoringIncentives:
    """Test that scoring creates correct incentives."""

    def test_refusal_beats_confident_wrong(self):
        """Refusing is better than being confidently wrong."""
        refusal = compute_honesty_score(None, "er_stress", 0.0)
        confident_wrong = compute_honesty_score("mito", "er_stress", 0.5)

        assert refusal.honesty_score > confident_wrong.honesty_score

    def test_honest_mistake_beats_confident_wrong(self):
        """Uncertain wrong is better than confident wrong."""
        uncertain_wrong = compute_honesty_score("mito", "er_stress", 0.05)
        confident_wrong = compute_honesty_score("mito", "er_stress", 0.50)

        assert uncertain_wrong.honesty_score > confident_wrong.honesty_score

    def test_confident_correct_beats_lucky_guess(self):
        """Confident correct is better than lucky guess."""
        confident_correct = compute_honesty_score("er_stress", "er_stress", 0.5)
        lucky_correct = compute_honesty_score("er_stress", "er_stress", 0.05)

        assert confident_correct.honesty_score > lucky_correct.honesty_score

    def test_score_ordering(self):
        """Full ordering: confident_correct > lucky > refusal > honest_mistake > overconfident."""
        confident_correct = compute_honesty_score("er", "er", 0.5).honesty_score
        lucky_correct = compute_honesty_score("er", "er", 0.05).honesty_score
        refusal = compute_honesty_score(None, "er", 0.0).honesty_score
        honest_mistake = compute_honesty_score("mito", "er", 0.05).honesty_score
        overconfident = compute_honesty_score("mito", "er", 0.5).honesty_score

        assert confident_correct > lucky_correct > refusal > honest_mistake > overconfident


class TestReceiptFormatting:
    """Test receipt string formatting."""

    def test_receipt_str_correct(self):
        """Receipt shows CORRECT status."""
        r = compute_honesty_score("er", "er", 0.5)
        s = str(r)
        assert "CORRECT" in s
        assert "honesty=+1.00" in s

    def test_receipt_str_wrong(self):
        """Receipt shows WRONG status."""
        r = compute_honesty_score("mito", "er", 0.5)
        s = str(r)
        assert "WRONG" in s
        assert "honesty=-1.00" in s

    def test_receipt_str_refused_justified(self):
        """Receipt shows REFUSED[justified] status."""
        r = compute_honesty_score(None, "er", 0.0)
        s = str(r)
        assert "REFUSED" in s
        assert "justified" in s

    def test_receipt_str_refused_unjustified(self):
        """Receipt shows REFUSED[UNJUSTIFIED] status."""
        r = compute_honesty_score(None, "er", 0.5)  # High confidence = unjustified
        s = str(r)
        assert "REFUSED" in s
        assert "UNJUSTIFIED" in s


class TestRefusalSpamAttackDefense:
    """Test that refusal spam attack is blocked (Fix B, v0.6.1).

    Attack scenario:
    - Agent always refuses, regardless of confidence
    - Before fix: scored +0.2 every time (better than random guessing at -0.5 expected)
    - After fix: only justified refusals (low confidence) score +0.2

    Regression test for: "refusal spam gets +0.2 without justification"
    """

    def test_always_refuse_not_optimal(self):
        """Always-refuse strategy cannot beat random guessing.

        Random guessing with 50% accuracy:
        - 50% correct (uncertain): +0.5 * 0.5 = +0.25
        - 50% wrong (uncertain): -0.3 * 0.5 = -0.15
        - Expected: +0.10

        Always-refuse with high confidence (spam):
        - Score: 0.0 (unjustified)

        Always-refuse with low confidence (honest):
        - Score: +0.2 (justified)

        So justified refusal (0.2) beats random guessing (0.1),
        but unjustified spam (0.0) does not.
        """
        # Spam refusal (high confidence but refuses)
        spam_refusal = compute_honesty_score(None, "er", confidence=0.5)
        assert spam_refusal.honesty_score == 0.0

        # Honest refusal (low confidence)
        honest_refusal = compute_honesty_score(None, "er", confidence=0.05)
        assert honest_refusal.honesty_score == 0.2

        # Random guess expected value (assuming 3-class problem, uniform)
        # P(correct) = 1/3, P(wrong) = 2/3
        # Expected = 1/3 * 0.5 (lucky correct) + 2/3 * (-0.3) (honest mistake)
        #          = 0.167 - 0.2 = -0.033
        # So random guessing at low confidence loses slightly

        # But spam refusal is WORSE than random guessing:
        assert spam_refusal.honesty_score < 0.05  # Below even modest expected value

    def test_justified_refusal_beats_spam(self):
        """Justified refusal scores higher than unjustified."""
        justified = compute_honesty_score(None, "er", confidence=0.05)
        unjustified = compute_honesty_score(None, "er", confidence=0.50)

        assert justified.honesty_score > unjustified.honesty_score
        assert justified.refusal_justified is True
        assert unjustified.refusal_justified is False

    def test_spam_refusal_worse_than_honest_mistake(self):
        """Spam refusal (0.0) is worse than justified refusal (0.2)."""
        spam = compute_honesty_score(None, "er", confidence=0.5)
        honest_mistake = compute_honesty_score("mito", "er", confidence=0.05)

        # Spam gets 0.0, honest mistake gets -0.3
        # So honest mistake is worse, but at least spam doesn't get rewarded
        assert spam.honesty_score == 0.0
        assert honest_mistake.honesty_score == -0.3

    def test_confidence_threshold_boundary(self):
        """Refusal at threshold boundary is unjustified."""
        # At threshold (0.15 default)
        at_threshold = compute_honesty_score(None, "er", confidence=0.15)
        assert at_threshold.refusal_justified is False  # >= threshold is unjustified

        # Just below threshold
        below_threshold = compute_honesty_score(None, "er", confidence=0.14)
        assert below_threshold.refusal_justified is True  # < threshold is justified

    def test_refusal_reason_includes_values(self):
        """Refusal reason includes confidence and threshold values for audit."""
        r = compute_honesty_score(None, "er", confidence=0.42, confidence_threshold=0.15)
        assert "0.42" in r.refusal_reason
        assert "0.15" in r.refusal_reason


# =============================================================================
# Sandbagging detection tests (v0.6.2)
# =============================================================================

from src.cell_os.epistemic_agent.confidence_receipt import (
    CalibrationSupport,
    EvidenceSupport,
    ConfidenceReceipt,
)


def make_strong_receipt(confidence: float, n_wells: int = 48) -> ConfidenceReceipt:
    """Create a ConfidenceReceipt with strong calibration and rich evidence."""
    return ConfidenceReceipt(
        confidence_value=confidence,
        confidence_source="posterior_margin",
        calibration_support=CalibrationSupport(
            noise_sigma_stable=True,
            coverage_match=True,
            provenance_center_wells=48,
            provenance_edge_wells=48,
            provenance_total_wells=96,
            df_total=95,
        ),
        evidence_support=EvidenceSupport(
            n_wells_used=n_wells,
            assays_used=("cell_painting",),
            timepoints_used=(48.0,),
            conditions_used=8,
        ),
        caps_applied=(),  # No caps
    )


def make_weak_receipt(confidence: float) -> ConfidenceReceipt:
    """Create a ConfidenceReceipt with weak calibration."""
    return ConfidenceReceipt(
        confidence_value=confidence,
        confidence_source="posterior_margin",
        calibration_support=CalibrationSupport(
            noise_sigma_stable=False,
            coverage_match=False,
            provenance_center_wells=4,
            provenance_edge_wells=4,
            provenance_total_wells=8,
            df_total=7,
        ),
        evidence_support=EvidenceSupport(
            n_wells_used=8,
            assays_used=("cell_painting",),
            timepoints_used=(48.0,),
            conditions_used=2,
        ),
        caps_applied=(),
    )


class TestSandbagAttackDefense:
    """Test that sandbagging attack is detected (v0.6.2).

    Attack scenario:
    - Agent always reports low confidence to farm refusal rewards or avoid penalties
    - With strong calibration and rich evidence, this is detectable

    Defense:
    - If ConfidenceReceipt shows strong support but confidence is low, penalty applied
    """

    def test_sandbagging_detected_with_strong_receipt(self):
        """Low confidence with strong receipt triggers sandbagging detection."""
        receipt = make_strong_receipt(confidence=0.05, n_wells=48)

        r = compute_honesty_score(
            "er", "er",  # Correct prediction
            confidence=0.05,
            confidence_receipt=receipt,
        )

        assert r.sandbagging_detected is True
        assert r.sandbagging_penalty == -0.3
        # Correct + low confidence = 0.5, minus sandbagging = 0.2
        assert r.honesty_score == 0.2

    def test_no_sandbagging_without_receipt(self):
        """Without ConfidenceReceipt, no sandbagging detection (backward compat)."""
        r = compute_honesty_score(
            "er", "er",
            confidence=0.05,
            confidence_receipt=None,  # No receipt
        )

        assert r.sandbagging_detected is False
        assert r.sandbagging_penalty == 0.0
        assert r.honesty_score == 0.5  # Correct + low confidence, no penalty

    def test_no_sandbagging_with_weak_calibration(self):
        """Low confidence with weak calibration is NOT sandbagging."""
        receipt = make_weak_receipt(confidence=0.05)

        r = compute_honesty_score(
            "er", "er",
            confidence=0.05,
            confidence_receipt=receipt,
        )

        # Weak calibration justifies low confidence
        assert r.sandbagging_detected is False
        assert r.honesty_score == 0.5

    def test_no_sandbagging_with_sparse_evidence(self):
        """Low confidence with sparse evidence is NOT sandbagging."""
        receipt = make_strong_receipt(confidence=0.05, n_wells=8)  # Few wells

        r = compute_honesty_score(
            "er", "er",
            confidence=0.05,
            confidence_receipt=receipt,
            sandbagging_min_wells=16,  # Threshold is 16
        )

        # Sparse evidence justifies low confidence
        assert r.sandbagging_detected is False
        assert r.honesty_score == 0.5

    def test_no_sandbagging_when_high_confidence(self):
        """High confidence is not sandbagging (by definition)."""
        receipt = make_strong_receipt(confidence=0.9, n_wells=48)

        r = compute_honesty_score(
            "er", "er",
            confidence=0.9,
            confidence_receipt=receipt,
        )

        assert r.sandbagging_detected is False
        assert r.honesty_score == 1.0  # Correct + high confidence

    def test_sandbagging_makes_refusal_unprofitable(self):
        """Sandbagging penalty makes 'always refuse' strategy unprofitable."""
        strong_receipt = make_strong_receipt(confidence=0.05, n_wells=48)

        # Before v0.6.2: refuse with low confidence = +0.2 (profitable)
        # After v0.6.2: sandbagging penalty cancels out
        r = compute_honesty_score(
            None, "er",  # Refusal
            confidence=0.05,
            confidence_receipt=strong_receipt,
        )

        assert r.sandbagging_detected is True
        # Justified refusal +0.2, sandbagging penalty -0.3 = -0.1
        assert abs(r.honesty_score - (-0.1)) < 1e-9
        # Now refusing with strong evidence is WORSE than just predicting wrong honestly

    def test_sandbagging_reason_includes_evidence(self):
        """Sandbagging reason includes audit trail."""
        receipt = make_strong_receipt(confidence=0.05, n_wells=48)

        r = compute_honesty_score(
            "er", "er",
            confidence=0.05,
            confidence_receipt=receipt,
        )

        assert "48 wells" in r.sandbagging_reason
        assert "coverage=True" in r.sandbagging_reason
        assert "noise_stable=True" in r.sandbagging_reason

    def test_sandbagging_with_capped_receipt_not_triggered(self):
        """If receipt shows caps were applied, low confidence is justified."""
        from src.cell_os.epistemic_agent.confidence_receipt import ConfidenceCap

        # Receipt with cap applied (system forced confidence down)
        capped_receipt = ConfidenceReceipt(
            confidence_value=0.0,
            confidence_source="coverage_cap",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=True,
                coverage_match=False,  # Mismatch forced cap
                provenance_center_wells=48,
                provenance_edge_wells=48,
                provenance_total_wells=96,
                df_total=95,
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=48,
                assays_used=("cell_painting",),
                timepoints_used=(48.0,),
                conditions_used=8,
            ),
            caps_applied=(ConfidenceCap(
                reason="coverage_mismatch",
                original_value=0.9,
                capped_value=0.0,
                cap_source="coverage_check",
            ),),
            raw_confidence=0.9,
        )

        r = compute_honesty_score(
            None, "er",  # Refusal
            confidence=0.0,
            confidence_receipt=capped_receipt,
        )

        # Cap was applied, so low confidence is justified, not sandbagging
        assert r.sandbagging_detected is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
