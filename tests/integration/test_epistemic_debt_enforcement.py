"""
Test epistemic debt enforcement end-to-end.

These tests verify the forcing function:
1. Overclaiming accumulates debt
2. Debt >= 2.0 bits HARD BLOCKS non-calibration actions
3. Calibration actions remain accessible when in debt
4. Calibration repays debt and restores access

This is the "honesty tax" - agents that overclaim lose access to biology
until they calibrate.
"""

import pytest
from cell_os.epistemic_agent import EpistemicController, EpistemicControllerConfig
from cell_os.epistemic_agent import EpistemicDebtLedger


class TestDebtAccumulation:
    """Test that overclaiming accumulates debt."""

    def test_overclaim_increases_debt(self):
        """Claiming more than realized should increase debt."""
        controller = EpistemicController()

        # Claim 1.0 bit, realize only 0.3
        controller.claim_action("action_1", "exploration", expected_gain_bits=1.0)
        debt_increment = controller.resolve_action("action_1", actual_gain_bits=0.3)

        assert debt_increment == pytest.approx(0.7, abs=0.001)
        assert controller.get_total_debt() == pytest.approx(0.7, abs=0.001)

    def test_underclaim_does_not_reduce_debt(self):
        """Claiming less than realized should NOT reduce debt (asymmetric)."""
        controller = EpistemicController()

        # First, accumulate some debt
        controller.claim_action("action_1", "exploration", expected_gain_bits=1.0)
        controller.resolve_action("action_1", actual_gain_bits=0.3)
        debt_before = controller.get_total_debt()

        # Now underclaim (claim 0.5, realize 1.0)
        controller.claim_action("action_2", "exploration", expected_gain_bits=0.5)
        debt_increment = controller.resolve_action("action_2", actual_gain_bits=1.0)

        # Underclaim should not add debt
        assert debt_increment == 0.0
        # Debt should remain the same (no free forgiveness)
        assert controller.get_total_debt() == pytest.approx(debt_before, abs=0.001)

    def test_debt_accumulates_across_actions(self):
        """Debt should accumulate across multiple overclaiming actions."""
        controller = EpistemicController()

        # 5 overclaiming actions, each overclaims by 0.7 bits
        for i in range(5):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        assert controller.get_total_debt() == pytest.approx(3.5, abs=0.001)


class TestDebtEnforcement:
    """Test that debt enforces access restrictions."""

    def test_high_debt_blocks_non_calibration(self):
        """Debt >= 2.0 bits should block non-calibration actions."""
        controller = EpistemicController()

        # Accumulate 2.1 bits of debt
        for i in range(3):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        assert controller.get_total_debt() == pytest.approx(2.1, abs=0.001)

        # Non-calibration action should be refused
        should_refuse, reason, context = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=24,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )

        assert should_refuse is True
        assert reason == "epistemic_debt_action_blocked"
        assert context["debt_bits"] == pytest.approx(2.1, abs=0.001)
        assert context["blocked_by_threshold"] is True

    def test_high_debt_allows_calibration(self):
        """Calibration actions should be allowed even with high debt."""
        controller = EpistemicController()

        # Accumulate 3.5 bits of debt (well above threshold)
        for i in range(5):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        assert controller.get_total_debt() == pytest.approx(3.5, abs=0.001)

        # Calibration actions should still be allowed
        for template in ["baseline", "calibration", "dmso_replicates"]:
            should_refuse, reason, context = controller.should_refuse_action(
                template_name=template,
                base_cost_wells=24,
                budget_remaining=100,
                debt_hard_threshold=2.0
            )

            assert should_refuse is False, f"{template} should be allowed even with high debt"

    def test_low_debt_allows_all_actions(self):
        """Debt below threshold should allow all actions."""
        controller = EpistemicController()

        # Accumulate 1.4 bits of debt (below 2.0 threshold)
        for i in range(2):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        assert controller.get_total_debt() == pytest.approx(1.4, abs=0.001)

        # Non-calibration should be allowed
        should_refuse, reason, context = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=24,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )

        assert should_refuse is False


class TestDebtRepayment:
    """Test that calibration repays debt."""

    def test_calibration_repays_debt(self):
        """Calibration actions should repay debt."""
        controller = EpistemicController()

        # Accumulate 2.1 bits of debt
        for i in range(3):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        debt_before = controller.get_total_debt()
        assert debt_before == pytest.approx(2.1, abs=0.001)

        # Calibration repays debt
        repayment = controller.compute_repayment(
            action_id="calibrate_1",
            action_type="baseline",
            is_calibration=True,
            noise_improvement=0.05  # 5% noise improvement
        )

        # Base repayment (0.25) + bonus for noise improvement
        assert repayment > 0.25
        assert controller.get_total_debt() < debt_before

    def test_non_calibration_does_not_repay(self):
        """Non-calibration actions should NOT repay debt."""
        controller = EpistemicController()

        # Accumulate debt
        controller.claim_action("action_1", "exploration", expected_gain_bits=1.0)
        controller.resolve_action("action_1", actual_gain_bits=0.3)

        debt_before = controller.get_total_debt()

        # Non-calibration attempt to repay
        repayment = controller.compute_repayment(
            action_id="explore_1",
            action_type="dose_response",
            is_calibration=False  # Not calibration
        )

        assert repayment == 0.0
        assert controller.get_total_debt() == debt_before

    def test_calibration_restores_access(self):
        """Calibration should restore access once debt drops below threshold."""
        controller = EpistemicController()

        # Accumulate 2.5 bits of debt (enough to trigger block)
        controller.claim_action("action_1", "exploration", expected_gain_bits=2.5)
        controller.resolve_action("action_1", actual_gain_bits=0.0)

        # Verify blocked
        should_refuse, _, _ = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=24,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )
        assert should_refuse is True

        # Calibrate multiple times to repay debt
        for i in range(4):
            controller.compute_repayment(
                action_id=f"calibrate_{i}",
                action_type="baseline",
                is_calibration=True,
                noise_improvement=0.1  # Good improvement
            )

        # Debt should now be below threshold
        assert controller.get_total_debt() < 2.0

        # Access should be restored
        should_refuse, _, _ = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=24,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )
        assert should_refuse is False


class TestCostInflation:
    """Test that debt inflates costs."""

    def test_debt_inflates_exploration_cost(self):
        """High debt should inflate exploration costs."""
        controller = EpistemicController()

        base_cost = 100.0

        # No debt - no inflation
        inflated_no_debt = controller.get_inflated_cost(base_cost)
        assert inflated_no_debt == pytest.approx(base_cost, abs=1.0)

        # Accumulate debt
        for i in range(3):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        # Should have 2.1 bits of debt
        debt = controller.get_total_debt()

        # Cost should be inflated
        inflated_with_debt = controller.get_inflated_cost(base_cost)
        assert inflated_with_debt > base_cost * 1.05  # At least 5% inflation

    def test_calibration_cost_is_capped(self):
        """Calibration cost inflation should be capped to prevent deadlock."""
        controller = EpistemicController()

        # Accumulate high debt
        for i in range(5):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        base_cost = 24.0  # Typical calibration cost

        # Calibration inflation should be capped at 1.5x
        inflated_cal = controller.get_inflated_cost(base_cost, is_calibration=True)
        assert inflated_cal <= base_cost * 1.5


class TestDeadlockPrevention:
    """Test deadlock detection and prevention."""

    def test_detects_epistemic_deadlock(self):
        """Should detect when agent can't afford calibration to escape debt."""
        controller = EpistemicController()

        # Accumulate massive debt
        for i in range(10):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=2.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.0)

        # With tiny budget, even calibration becomes unaffordable
        should_refuse, reason, context = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=24,
            budget_remaining=10,  # Not enough even for calibration
            debt_hard_threshold=2.0
        )

        assert should_refuse is True
        assert context.get("is_deadlocked") is True
        assert reason == "epistemic_deadlock_detected"


class TestIntegrationWithLedger:
    """Test integration between controller and ledger."""

    def test_controller_statistics_match_ledger(self):
        """Controller statistics should match underlying ledger."""
        controller = EpistemicController()

        # Make some claims
        for i in range(3):
            controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
            controller.resolve_action(f"action_{i}", actual_gain_bits=0.3)

        stats = controller.get_statistics()

        assert stats["total_claims"] == 3
        assert stats["resolved_claims"] == 3
        assert stats["total_debt"] == pytest.approx(2.1, abs=0.001)
        assert stats["mean_overclaim"] == pytest.approx(0.7, abs=0.001)
        assert stats["overclaim_rate"] == pytest.approx(1.0, abs=0.001)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
