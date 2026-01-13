"""
Tests for conservation and debt enforcement contracts.

These tests verify that:
1. ConservationViolation is raised when death accounting fails
2. DebtViolation is raised when non-calibration actions attempted while insolvent
3. Cost multiplier calculation is correct
"""

import pytest
from dataclasses import dataclass
from typing import List, Any

from cell_os.contracts import (
    # Conservation
    ConservationViolation,
    assert_conservation,
    conserved_death,
    check_monotonicity,
    # Debt
    DebtViolation,
    DEBT_HARD_BLOCK_THRESHOLD,
    is_calibration_action,
    check_debt_threshold,
    debt_enforced,
    compute_cost_multiplier,
    CALIBRATION_ACTION_TYPES,
)
from cell_os.hardware.constants import DEATH_EPS, TRACKED_DEATH_FIELDS


# =============================================================================
# Mock classes for testing
# =============================================================================

@dataclass
class MockVessel:
    """Mock vessel for testing conservation contracts."""
    well_id: str = "test_well"
    viability: float = 1.0
    death_compound: float = 0.0
    death_starvation: float = 0.0
    death_mitotic_catastrophe: float = 0.0
    death_er_stress: float = 0.0
    death_mito_dysfunction: float = 0.0
    death_confluence: float = 0.0
    death_contamination: float = 0.0
    death_unknown: float = 0.0
    death_committed_er: float = 0.0
    death_committed_mito: float = 0.0


@dataclass
class MockDebtLedger:
    """Mock debt ledger for testing debt contracts."""
    total_debt: float = 0.0


class MockAgent:
    """Mock agent for testing debt decorator."""
    def __init__(self, debt: float = 0.0):
        self.debt_ledger = MockDebtLedger(total_debt=debt)
        self.action_count = 0

    @debt_enforced()
    def execute_action(self, action_type: str = "unknown") -> str:
        self.action_count += 1
        return f"executed {action_type}"


class MockSimulator:
    """Mock simulator for testing conservation decorator."""
    def __init__(self):
        self.vessels: List[MockVessel] = []
        self.step_count = 0

    @conserved_death
    def step(self, dt: float) -> None:
        self.step_count += 1
        # In a real implementation, this would modify vessel state


# =============================================================================
# Conservation contract tests
# =============================================================================

class TestConservationContract:
    """Test assert_conservation function."""

    def test_valid_conservation_passes(self):
        """Conservation should pass when viable + death = 1.0."""
        vessel = MockVessel(viability=0.7, death_compound=0.2, death_er_stress=0.1)
        # Should not raise
        assert_conservation(vessel)

    def test_violation_raises_exception(self):
        """Conservation should fail when viable + death != 1.0."""
        vessel = MockVessel(viability=0.8, death_compound=0.1)  # Sum = 0.9
        with pytest.raises(ConservationViolation) as exc_info:
            assert_conservation(vessel)

        assert exc_info.value.expected == 1.0
        assert abs(exc_info.value.actual - 0.9) < 0.01
        assert "Conservation violated" in str(exc_info.value)

    def test_violation_contains_forensic_details(self):
        """Violation should contain field-by-field breakdown."""
        vessel = MockVessel(viability=0.5, death_compound=0.3)  # Sum = 0.8
        with pytest.raises(ConservationViolation) as exc_info:
            assert_conservation(vessel)

        details = exc_info.value.details
        assert "viability" in details
        assert "death_total" in details
        assert "fields" in details
        assert details["viability"] == 0.5

    def test_tolerance_allows_small_deviations(self):
        """Small deviations within tolerance should pass."""
        vessel = MockVessel(viability=0.7 + DEATH_EPS, death_compound=0.3)
        # Should not raise (within default tolerance)
        assert_conservation(vessel, tolerance=DEATH_EPS * 100)

    def test_zero_viability_valid(self):
        """Zero viability is valid if death fields sum to 1.0."""
        vessel = MockVessel(
            viability=0.0,
            death_compound=0.5,
            death_er_stress=0.3,
            death_mito_dysfunction=0.2,
        )
        # Should not raise
        assert_conservation(vessel)


class TestConservedDeathDecorator:
    """Test @conserved_death decorator."""

    def test_decorator_checks_after_method(self):
        """Decorator should check conservation after method returns."""
        sim = MockSimulator()
        sim.vessels = [MockVessel(viability=0.7, death_compound=0.3)]

        # Should not raise - conservation is valid
        sim.step(1.0)
        assert sim.step_count == 1

    def test_decorator_raises_on_violation(self):
        """Decorator should raise if conservation violated after method."""
        sim = MockSimulator()
        sim.vessels = [MockVessel(viability=0.7, death_compound=0.1)]  # Invalid

        with pytest.raises(ConservationViolation):
            sim.step(1.0)


class TestMonotonicity:
    """Test check_monotonicity function."""

    def test_monotonicity_passes_when_increasing(self):
        """Should pass when death fields increase."""
        vessel = MockVessel(death_compound=0.2, death_er_stress=0.1)
        prev = {"death_compound": 0.1, "death_er_stress": 0.05}

        # Should not raise
        check_monotonicity(vessel, prev)

    def test_monotonicity_fails_when_decreasing(self):
        """Should fail when death fields decrease."""
        vessel = MockVessel(death_compound=0.1)  # Decreased
        prev = {"death_compound": 0.2}

        with pytest.raises(ValueError, match="Monotonicity violated"):
            check_monotonicity(vessel, prev)


# =============================================================================
# Debt contract tests
# =============================================================================

class TestDebtThreshold:
    """Test debt threshold checking."""

    def test_low_debt_allows_all_actions(self):
        """Below threshold, all actions should be allowed."""
        # Should not raise
        check_debt_threshold(debt=1.0, action_type="biology_experiment")

    def test_high_debt_blocks_non_calibration(self):
        """At or above threshold, non-calibration should be blocked."""
        with pytest.raises(DebtViolation) as exc_info:
            check_debt_threshold(debt=2.5, action_type="biology_experiment")

        assert exc_info.value.action_type == "biology_experiment"
        assert exc_info.value.current_debt == 2.5
        assert "blocked" in str(exc_info.value)

    def test_high_debt_allows_calibration(self):
        """Even at high debt, calibration actions should be allowed."""
        for action in CALIBRATION_ACTION_TYPES:
            # Should not raise
            check_debt_threshold(debt=5.0, action_type=action)

    def test_exactly_at_threshold_blocks(self):
        """Debt exactly at threshold should block."""
        with pytest.raises(DebtViolation):
            check_debt_threshold(
                debt=DEBT_HARD_BLOCK_THRESHOLD,
                action_type="biology_experiment",
            )


class TestCalibrationActionDetection:
    """Test is_calibration_action function."""

    def test_recognizes_calibration_actions(self):
        """Should recognize all calibration action types."""
        for action in CALIBRATION_ACTION_TYPES:
            assert is_calibration_action(action), f"{action} should be calibration"

    def test_rejects_non_calibration_actions(self):
        """Should reject non-calibration actions."""
        assert not is_calibration_action("biology_experiment")
        assert not is_calibration_action("scrna_seq")
        assert not is_calibration_action("unknown")

    def test_case_insensitive(self):
        """Should be case-insensitive."""
        assert is_calibration_action("CALIBRATION")
        assert is_calibration_action("Baseline")


class TestDebtEnforcedDecorator:
    """Test @debt_enforced decorator."""

    def test_allows_action_when_debt_low(self):
        """Should allow actions when debt is below threshold."""
        agent = MockAgent(debt=1.0)
        result = agent.execute_action(action_type="experiment")
        assert result == "executed experiment"
        assert agent.action_count == 1

    def test_blocks_action_when_debt_high(self):
        """Should block non-calibration when debt is high."""
        agent = MockAgent(debt=3.0)
        with pytest.raises(DebtViolation):
            agent.execute_action(action_type="experiment")
        assert agent.action_count == 0  # Action not executed

    def test_allows_calibration_when_debt_high(self):
        """Should allow calibration actions even when debt is high."""
        agent = MockAgent(debt=5.0)
        result = agent.execute_action(action_type="calibration")
        assert result == "executed calibration"
        assert agent.action_count == 1


class TestCostMultiplier:
    """Test compute_cost_multiplier function."""

    def test_no_debt_no_multiplier(self):
        """Zero debt should have multiplier of 1.0."""
        assert compute_cost_multiplier(debt=0.0, base_cost=100.0) == 1.0

    def test_debt_increases_cost(self):
        """Positive debt should increase cost."""
        multiplier = compute_cost_multiplier(debt=1.0, base_cost=100.0)
        assert multiplier > 1.0

    def test_expensive_assays_penalized_more(self):
        """More expensive assays should have higher multiplier."""
        cheap_mult = compute_cost_multiplier(debt=1.0, base_cost=20.0)
        expensive_mult = compute_cost_multiplier(debt=1.0, base_cost=200.0)
        assert expensive_mult > cheap_mult

    def test_multiplier_increases_with_debt(self):
        """Higher debt should mean higher multiplier."""
        low_debt = compute_cost_multiplier(debt=0.5, base_cost=100.0)
        high_debt = compute_cost_multiplier(debt=2.0, base_cost=100.0)
        assert high_debt > low_debt

    def test_multiplier_never_below_one(self):
        """Multiplier should never be below 1.0."""
        # Even with negative debt (edge case), should be >= 1.0
        assert compute_cost_multiplier(debt=-1.0, base_cost=100.0) >= 1.0


# =============================================================================
# Integration tests
# =============================================================================

class TestContractIntegration:
    """Integration tests for contracts working together."""

    def test_violation_details_serializable(self):
        """Violation details should be JSON-serializable for logging."""
        import json

        vessel = MockVessel(viability=0.5, death_compound=0.2)
        try:
            assert_conservation(vessel)
        except ConservationViolation as e:
            # Details should be serializable
            json_str = json.dumps(e.details)
            assert "viability" in json_str

    def test_debt_violation_details_serializable(self):
        """Debt violation details should be JSON-serializable."""
        import json

        try:
            check_debt_threshold(debt=3.0, action_type="experiment")
        except DebtViolation as e:
            json_str = json.dumps(e.details)
            assert "allowed_actions" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
