"""
Agent 3: E2E Tests - Epistemic Debt Enforcement With Teeth

These tests prove that epistemic debt is a REAL, PHYSICAL constraint:
1. Debt blocks non-calibration actions when threshold exceeded
2. Calibration is the ONLY recovery path
3. Budget reserve prevents insolvency deadlocks

Test philosophy:
- Debt must hurt before it kills
- Agent can always recover via calibration
- No silent bypasses allowed
"""

import pytest
from cell_os.epistemic_agent import (
    EpistemicController,
    EpistemicControllerConfig,
    MIN_CALIBRATION_COST_WELLS
)


def test_epistemic_debt_forces_calibration_then_recovers():
    """
    Prove that debt blocks biology, forces calibration, then allows recovery.

    Scenario:
    1. Accumulate debt beyond threshold by overclaiming
    2. Attempt biology action → should be REFUSED
    3. Attempt calibration action → should be ALLOWED
    4. After calibration, debt should decrease
    5. Biology should resume successfully

    This is the core enforcement test.
    """
    # Initialize controller
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Step 1: Accumulate debt beyond threshold (2.0 bits)
    # Claim 1.0 bit per action, realize 0.0, accumulate 1.0 bit penalty each
    for i in range(3):
        action_id = f"overclaim_{i}"
        controller.claim_action(
            action_id=action_id,
            action_type="biology",
            expected_gain_bits=1.0
        )
        # Realize 0 bits (total failure)
        controller.resolve_action(
            action_id=action_id,
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 2.0, f"Should have accumulated debt >= 2.0, got {debt:.3f}"

    # Step 2: Attempt biology action → SHOULD BE REFUSED
    should_refuse_bio, refusal_reason_bio, context_bio = controller.should_refuse_action(
        template_name="dose_response",  # Non-calibration
        base_cost_wells=20,
        budget_remaining=100,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # CRITICAL ASSERTION: Biology must be blocked
    assert should_refuse_bio, "Biology action MUST be refused when debt > threshold"
    assert refusal_reason_bio == "epistemic_debt_action_blocked", \
        f"Expected 'epistemic_debt_action_blocked', got '{refusal_reason_bio}'"
    assert context_bio["blocked_by_threshold"], "Should be blocked by threshold, not cost"

    # Step 3: Attempt calibration action → SHOULD BE ALLOWED
    should_refuse_calib, refusal_reason_calib, context_calib = controller.should_refuse_action(
        template_name="baseline_replicates",  # Calibration
        base_cost_wells=12,
        budget_remaining=100,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # CRITICAL ASSERTION: Calibration must be allowed
    assert not should_refuse_calib, "Calibration action MUST be allowed even when debt > threshold"

    # Step 4: Execute calibration and earn repayment
    repayment = controller.compute_repayment(
        action_id="calibration_001",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=0.1  # 10% noise improvement
    )

    # Verify repayment was earned
    assert repayment > 0, "Calibration MUST earn repayment"
    assert repayment >= 0.25, "Should earn at least base repayment (0.25 bits)"

    debt_after_repayment = controller.get_total_debt()
    assert debt_after_repayment < debt, \
        f"Debt should decrease after repayment: {debt:.3f} → {debt_after_repayment:.3f}"

    # Step 5: If debt dropped below threshold, biology should be allowed again
    if debt_after_repayment < 2.0:
        should_refuse_bio_after, _, _ = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=20,
            budget_remaining=100,
            debt_hard_threshold=2.0,
            calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
        )
        assert not should_refuse_bio_after, \
            "Biology should be allowed again after debt drops below threshold"


def test_budget_reserve_prevents_debt_deadlock():
    """
    Prove that budget reserve prevents epistemic bankruptcy.

    Scenario:
    1. Budget is low: enough for biology but not (biology + calibration)
    2. Attempt biology action → should be REFUSED by reserve check
    3. Refusal reason should be "insufficient_budget_for_epistemic_recovery"
    4. Verify that MIN_CALIBRATION_COST_WELLS is reserved

    This prevents the deadlock:
    - Agent accumulates debt
    - Agent spends all budget on biology
    - Agent gets blocked
    - Agent can't afford calibration
    - Agent is stuck forever
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Set debt to 0 (reserve check is independent of debt level)
    assert controller.get_total_debt() == 0.0

    # Budget scenario: 30 wells remaining
    # Biology costs 20 wells (inflated)
    # After biology: 30 - 20 = 10 wells left
    # MIN_CALIBRATION_COST_WELLS = 12 wells
    # Therefore: 10 < 12 → should be refused by reserve check

    budget_remaining = 30
    biology_cost = 20

    # Verify our assumptions
    assert biology_cost < budget_remaining, "Biology cost must be affordable (soft check)"
    assert budget_remaining - biology_cost < MIN_CALIBRATION_COST_WELLS, \
        f"After biology, budget should be below reserve: {budget_remaining - biology_cost} < {MIN_CALIBRATION_COST_WELLS}"

    # Attempt biology action
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",  # Non-calibration
        base_cost_wells=biology_cost,
        budget_remaining=budget_remaining,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # CRITICAL ASSERTIONS: Reserve check must block
    assert should_refuse, "Action MUST be refused when it would violate budget reserve"
    assert refusal_reason == "insufficient_budget_for_epistemic_recovery", \
        f"Expected 'insufficient_budget_for_epistemic_recovery', got '{refusal_reason}'"
    assert context["blocked_by_reserve"], "Should be blocked by reserve check"
    assert context["budget_after_action"] < MIN_CALIBRATION_COST_WELLS, \
        "Budget after action should be below minimum calibration cost"

    # Verify calibration would still be allowed (even with low budget)
    should_refuse_calib, _, context_calib = controller.should_refuse_action(
        template_name="baseline_replicates",  # Calibration
        base_cost_wells=12,
        budget_remaining=budget_remaining,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # Calibration should be allowed (it IS the reserve)
    # But it might be blocked by cost if budget < 12
    if budget_remaining >= MIN_CALIBRATION_COST_WELLS:
        assert not should_refuse_calib, \
            "Calibration should be allowed when budget >= MIN_CALIBRATION_COST_WELLS"


def test_debt_threshold_is_hard_not_soft():
    """
    Prove that debt threshold is a HARD block, not just cost inflation.

    Even if budget is infinite, non-calibration actions must be blocked
    when debt > threshold.
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate massive debt
    for i in range(10):
        action_id = f"overclaim_{i}"
        controller.claim_action(
            action_id=action_id,
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=action_id,
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 2.0, f"Should have accumulated massive debt, got {debt:.3f}"

    # Infinite budget
    budget_remaining = 1000000

    # Attempt biology with infinite budget
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",
        base_cost_wells=20,
        budget_remaining=budget_remaining,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # CRITICAL ASSERTION: Hard block even with infinite budget
    assert should_refuse, "Biology MUST be blocked even with infinite budget when debt > threshold"
    assert refusal_reason == "epistemic_debt_action_blocked", \
        "Refusal must be due to threshold, not cost"
    assert context["blocked_by_threshold"], "Should be blocked by threshold"
    assert not context["blocked_by_cost"], "Should NOT be blocked by cost (budget is infinite)"


def test_calibration_always_accessible():
    """
    Prove that calibration is ALWAYS accessible, even under extreme debt.

    This is the recovery guarantee: agent can always escape debt via calibration.
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate extreme debt (10 bits)
    for i in range(10):
        action_id = f"overclaim_{i}"
        controller.claim_action(
            action_id=action_id,
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=action_id,
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 10.0, f"Should have extreme debt, got {debt:.3f}"

    # Attempt calibration with minimal budget
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="baseline_replicates",
        base_cost_wells=12,
        budget_remaining=50,  # Enough for calibration
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration", "dmso_replicates", "baseline_replicates"}
    )

    # CRITICAL ASSERTION: Calibration must be accessible
    assert not should_refuse, \
        "Calibration MUST be accessible even under extreme debt"


def test_debt_contamination_tracking():
    """
    Prove that disabling debt enforcement contaminates the run.

    This prevents silent bypasses.
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=False  # DISABLE enforcement
    )
    controller = EpistemicController(config)

    # CRITICAL ASSERTION: Contamination must be flagged
    assert controller.is_contaminated, \
        "Controller MUST be flagged as contaminated when debt enforcement disabled"
    assert controller.contamination_reason == "DEBT_ENFORCEMENT_DISABLED", \
        "Contamination reason must be explicit"


def test_repayment_requires_evidence():
    """
    Prove that debt repayment requires measurable evidence.

    Non-calibration actions earn zero repayment.
    Calibration without improvement earns base repayment only.
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate some debt first
    controller.claim_action(
        action_id="overclaim_1",
        action_type="biology",
        expected_gain_bits=1.0
    )
    controller.resolve_action(
        action_id="overclaim_1",
        actual_gain_bits=0.0,
        action_type="biology"
    )

    # Non-calibration earns zero repayment
    repayment_bio = controller.compute_repayment(
        action_id="bio_001",
        action_type="dose_response",
        is_calibration=False
    )
    assert repayment_bio == 0.0, "Non-calibration MUST earn zero repayment"

    # Calibration without improvement earns base repayment
    repayment_base = controller.compute_repayment(
        action_id="calib_001",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=None
    )
    assert repayment_base == 0.25, "Calibration without improvement should earn base repayment (0.25 bits)"

    # Calibration with improvement earns bonus
    repayment_bonus = controller.compute_repayment(
        action_id="calib_002",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=0.1  # 10% improvement
    )
    assert repayment_bonus > 0.25, "Calibration with improvement should earn bonus repayment"
    assert repayment_bonus <= 1.0, "Repayment should be capped at 1.0 bit"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
