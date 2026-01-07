"""
Tests for honesty-first scoring mode (Issue #7).

Tests that:
1. Correct + confident gets full reward
2. Correct + uncertain gets partial reward (lucky guess)
3. Refusal gets modest positive reward
4. Wrong + uncertain gets small penalty (honest mistake)
5. Wrong + confident gets full penalty (overconfident)
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

    def test_refusal_modest_reward(self):
        """Refusal (None) = +0.2 (acknowledged uncertainty)."""
        receipt = compute_honesty_score(
            predicted_axis=None,  # Refused to predict
            true_axis="er_stress",
            confidence=0.0,
        )
        assert receipt.honesty_score == 0.2
        assert receipt.refused is True
        assert receipt.accuracy_correct is False
        assert receipt.confidence_calibrated is True

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

    def test_receipt_str_refused(self):
        """Receipt shows REFUSED status."""
        r = compute_honesty_score(None, "er", 0.0)
        s = str(r)
        assert "REFUSED" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
