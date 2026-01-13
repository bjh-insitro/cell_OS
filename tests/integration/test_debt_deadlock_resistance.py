"""
Agent 3: Epistemic Debt Deadlock Resistance Tests

These tests prove that the debt system is:
1. Survivable: Agent can always attempt recovery
2. Disciplined: Overconfidence still hurts
3. Explicit: Deadlocks are detected and terminal

Mission: Make epistemic debt actionable but survivable.
"""

from cell_os.epistemic_agent import (
    EpistemicController,
    EpistemicControllerConfig,
    MIN_CALIBRATION_COST_WELLS
)


def test_calibration_recovery_under_debt():
    """
    Test 1: Calibration Recovery

    Scenario:
    1. Agent incurs high debt (> 2.0 bits)
    2. Non-calibration is blocked
    3. Calibration is triggered
    4. Calibration reduces debt
    5. Exploration resumes

    Assertion:
    - Debt strictly decreases
    - No deadlock
    - No refusal loop
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Step 1: Incur high debt
    for i in range(3):
        controller.claim_action(
            action_id=f"overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"overclaim_{i}",
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt_before = controller.get_total_debt()
    assert debt_before >= 2.0, f"Should have high debt, got {debt_before:.3f}"

    # Step 2: Non-calibration blocked
    should_refuse_bio, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",
        base_cost_wells=20,
        budget_remaining=100,
        debt_hard_threshold=2.0
    )
    assert should_refuse_bio, "Biology should be blocked by debt"
    assert refusal_reason == "epistemic_debt_action_blocked"

    # Step 3: Calibration is allowed (capped inflation)
    should_refuse_calib, refusal_reason_calib, context_calib = controller.should_refuse_action(
        template_name="baseline_replicates",
        base_cost_wells=12,
        budget_remaining=100,
        debt_hard_threshold=2.0
    )
    assert not should_refuse_calib, "Calibration must be allowed"

    # Step 4: Execute calibration and earn repayment
    repayment = controller.compute_repayment(
        action_id="calib_001",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=0.1
    )
    assert repayment > 0, "Calibration must earn repayment"

    debt_after = controller.get_total_debt()
    assert debt_after < debt_before, \
        f"Debt must decrease after calibration: {debt_before:.3f} → {debt_after:.3f}"

    # Step 5: If debt dropped enough, biology resumes
    if debt_after < 2.0:
        should_refuse_bio_after, _, _ = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=20,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )
        assert not should_refuse_bio_after, "Biology should resume after debt clearance"

    print(f"✓ Calibration recovery test PASSED")
    print(f"  Debt: {debt_before:.3f} → {debt_after:.3f}")
    print(f"  Repayment: {repayment:.3f} bits")


def test_deadlock_detection_explicit():
    """
    Test 2: Deadlock Detection

    Scenario:
    1. Force high debt (> 2.0 bits)
    2. Artificially constrain budget
    3. Ensure calibration is unaffordable (even with capped inflation)

    Assertion:
    - Deadlock is detected explicitly
    - is_deadlocked flag is True
    - Refusal reason is "epistemic_deadlock_detected"
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Step 1: Accumulate massive debt
    for i in range(10):
        controller.claim_action(
            action_id=f"overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"overclaim_{i}",
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 2.0, f"Should have massive debt, got {debt:.3f}"

    # Step 2: Constrain budget so calibration is unaffordable
    # Calibration costs 12 wells base
    # With capped inflation (1.5×), max cost is 18 wells
    # Set budget to 10 wells → calibration unaffordable
    budget_remaining = 10

    # Step 3: Attempt any action (doesn't matter what)
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",  # Non-calibration
        base_cost_wells=20,
        budget_remaining=budget_remaining,
        debt_hard_threshold=2.0
    )

    # Assertions
    assert should_refuse, "Action should be refused"
    assert context["is_deadlocked"], "Deadlock should be detected"
    assert refusal_reason == "epistemic_deadlock_detected", \
        f"Expected deadlock reason, got '{refusal_reason}'"

    print(f"✓ Deadlock detection test PASSED")
    print(f"  Debt: {debt:.3f} bits")
    print(f"  Budget: {budget_remaining} wells")
    print(f"  Min calibration cost (inflated): ~{int(MIN_CALIBRATION_COST_WELLS * 1.5)} wells")
    print(f"  Deadlock detected: {context['is_deadlocked']}")


def test_inflation_asymmetry_calibration_vs_exploration():
    """
    Test 3: Inflation Asymmetry

    Scenario:
    1. Accumulate high debt
    2. Compare cost inflation for:
       - Calibration template
       - Exploration template

    Assertion:
    - Calibration inflation is CAPPED (≤ 1.5×)
    - Exploration inflation is UNCAPPED (can be 2×, 3×, etc.)
    - Calibration is always cheaper than exploration under debt
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate high debt (8.0 bits - enough to see clear asymmetry)
    for i in range(8):
        controller.claim_action(
            action_id=f"overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"overclaim_{i}",
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 8.0, f"Should have high debt for testing, got {debt:.3f}"

    # Test calibration inflation (CAPPED)
    base_cost = 12.0
    calib_inflated = controller.get_inflated_cost(
        base_cost=base_cost,
        is_calibration=True
    )
    calib_multiplier = calib_inflated / base_cost

    # Test exploration inflation (UNCAPPED)
    explo_inflated = controller.get_inflated_cost(
        base_cost=base_cost,
        is_calibration=False
    )
    explo_multiplier = explo_inflated / base_cost

    # Assertions
    assert calib_multiplier <= 1.5, \
        f"Calibration inflation should be capped at 1.5×, got {calib_multiplier:.2f}×"

    assert explo_multiplier > calib_multiplier, \
        f"Exploration should be more expensive than calibration: {explo_multiplier:.2f}× vs {calib_multiplier:.2f}×"

    # Exploration should be noticeably more expensive due to uncapped inflation
    assert explo_multiplier >= 1.6, \
        f"Exploration should have significant inflation at debt={debt:.1f}, got {explo_multiplier:.2f}×"

    print(f"✓ Inflation asymmetry test PASSED")
    print(f"  Debt: {debt:.3f} bits")
    print(f"  Base cost: {base_cost:.0f} wells")
    print(f"  Calibration: {calib_inflated:.1f} wells ({calib_multiplier:.2f}×) - CAPPED")
    print(f"  Exploration: {explo_inflated:.1f} wells ({explo_multiplier:.2f}×) - UNCAPPED")
    print(f"  Asymmetry: Calibration is {explo_multiplier / calib_multiplier:.2f}× cheaper")


def test_deadlock_never_happens_with_sufficient_budget():
    """
    Test 4: Deadlock Prevention via Capped Inflation

    Scenario:
    - High debt (10 bits)
    - Sufficient budget (50 wells)
    - Calibration should NEVER be deadlocked with capped inflation

    Assertion:
    - Even with extreme debt, calibration is affordable
    - No deadlock
    """
    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Extreme debt (10 bits)
    for i in range(10):
        controller.claim_action(
            action_id=f"overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"overclaim_{i}",
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    assert debt >= 10.0, f"Should have extreme debt, got {debt:.3f}"

    # Reasonable budget
    budget_remaining = 50

    # Check if calibration is affordable
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="baseline_replicates",
        base_cost_wells=12,
        budget_remaining=budget_remaining,
        debt_hard_threshold=2.0
    )

    # Assertions
    assert not should_refuse, \
        f"Calibration should be affordable even with extreme debt={debt:.1f}"
    assert not context["is_deadlocked"], \
        f"No deadlock should occur with budget={budget_remaining}"

    print(f"✓ Deadlock prevention test PASSED")
    print(f"  Debt: {debt:.3f} bits (EXTREME)")
    print(f"  Budget: {budget_remaining} wells")
    print(f"  Calibration inflated cost: {context['inflated_cost_wells']} wells")
    print(f"  Deadlocked: {context['is_deadlocked']} (should be False)")


if __name__ == "__main__":
    print("=" * 70)
    print("Agent 3: Epistemic Debt Deadlock Resistance Tests")
    print("=" * 70)
    print()

    print("Test 1: Calibration Recovery Under Debt")
    print("-" * 70)
    test_calibration_recovery_under_debt()
    print()

    print("Test 2: Deadlock Detection (Explicit)")
    print("-" * 70)
    test_deadlock_detection_explicit()
    print()

    print("Test 3: Inflation Asymmetry (Calibration vs Exploration)")
    print("-" * 70)
    test_inflation_asymmetry_calibration_vs_exploration()
    print()

    print("Test 4: Deadlock Prevention with Sufficient Budget")
    print("-" * 70)
    test_deadlock_never_happens_with_sufficient_budget()
    print()

    print("=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    print()
    print("Debt system is now:")
    print("  ✓ Survivable: Agent can always recover via calibration")
    print("  ✓ Disciplined: Overconfidence still hurts (inflation)")
    print("  ✓ Explicit: Deadlocks detected and terminal")
    print()
    print("Mission complete: Epistemic debt is actionable but survivable.")
