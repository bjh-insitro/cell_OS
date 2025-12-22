"""
Agent 2 Phase 2: Scenario B - Debt Deadlock Reproduction

Mission: Reproduce (or attempt to reproduce) epistemic debt deadlock.

Agent 3 already fixed the primary deadlock with capped calibration inflation.
This test verifies the fix and searches for edge cases.

Success criteria for REPRODUCTION (failure is good):
- Debt > 2.0 bits (threshold exceeded)
- Non-calibration actions blocked
- Calibration IS unaffordable even with Agent 3 capped inflation
- System cannot recover (permanent deadlock)

Success criteria for FIX VERIFICATION (pass is good):
- High debt blocks non-calibration
- Calibration remains affordable (capped at 1.5× inflation)
- Debt can be repaid
- System recovers from insolvency
"""

from cell_os.epistemic_control import (
    EpistemicController,
    EpistemicControllerConfig,
    MIN_CALIBRATION_COST_WELLS,
)


def test_debt_deadlock_fixed_by_agent3():
    """
    Test: Verify Agent 3's capped inflation prevents deadlock.

    Scenario:
    1. Accumulate high debt (> 2.0 bits)
    2. Check that non-calibration is blocked
    3. Check that calibration is AFFORDABLE (Agent 3 fix)
    4. Execute calibration and verify debt decreases
    """
    print("=" * 70)
    print("Scenario B.1: Debt Deadlock Prevention (Agent 3 Fix Verification)")
    print("=" * 70)

    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Step 1: Accumulate debt
    print("\n[Step 1] Accumulating epistemic debt...")
    for i in range(5):
        controller.claim_action(
            action_id=f"overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"overclaim_{i}",
            actual_gain_bits=0.0,  # Realized nothing
            action_type="biology"
        )

    debt = controller.get_total_debt()
    print(f"Debt accumulated: {debt:.3f} bits")

    if debt < 2.0:
        print(f"✗ SETUP FAILURE: Debt ({debt:.3f}) < 2.0 threshold")
        return False

    print(f"✓ Debt > 2.0 threshold ({debt:.3f} bits)")

    # Step 2: Check that non-calibration is blocked
    print("\n[Step 2] Checking non-calibration action blocking...")
    should_refuse_bio, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",  # Non-calibration
        base_cost_wells=20,
        budget_remaining=100,
        debt_hard_threshold=2.0
    )

    if not should_refuse_bio:
        print(f"✗ FAILURE: Non-calibration NOT blocked despite debt={debt:.3f}")
        return False

    print(f"✓ Non-calibration blocked: {refusal_reason}")
    print(f"  Debt: {context['debt_bits']:.3f} bits")
    print(f"  Base cost: {context['base_cost_wells']} wells")
    print(f"  Inflated cost: {context['inflated_cost_wells']} wells")

    # Step 3: Check that calibration is AFFORDABLE (Agent 3 fix)
    print("\n[Step 3] Checking calibration affordability (Agent 3 capped inflation)...")
    should_refuse_calib, refusal_reason_calib, context_calib = controller.should_refuse_action(
        template_name="baseline_replicates",  # Calibration
        base_cost_wells=12,
        budget_remaining=100,
        debt_hard_threshold=2.0
    )

    if should_refuse_calib:
        print(f"✗ DEADLOCK DETECTED: Calibration REFUSED even with Agent 3 fix!")
        print(f"  Refusal reason: {refusal_reason_calib}")
        print(f"  Base cost: {context_calib['base_cost_wells']} wells")
        print(f"  Inflated cost: {context_calib['inflated_cost_wells']} wells")
        print(f"  Budget: {context_calib['budget_remaining']} wells")
        print(f"  Is deadlocked: {context_calib.get('is_deadlocked', False)}")
        return False

    print(f"✓ Calibration AFFORDABLE (Agent 3 capped inflation)")
    print(f"  Base cost: {context_calib['base_cost_wells']} wells")
    print(f"  Inflated cost: {context_calib['inflated_cost_wells']} wells")
    print(f"  Inflation multiplier: {context_calib['inflated_cost_wells'] / context_calib['base_cost_wells']:.2f}×")

    if context_calib['inflated_cost_wells'] / context_calib['base_cost_wells'] > 1.5:
        print(f"✗ FAILURE: Calibration inflation > 1.5× cap!")
        return False

    print(f"✓ Calibration inflation capped at ≤1.5×")

    # Step 4: Execute calibration and verify debt repayment
    print("\n[Step 4] Executing calibration and verifying debt repayment...")
    repayment = controller.compute_repayment(
        action_id="calib_recovery",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=0.05  # Small improvement
    )

    print(f"Repayment earned: {repayment:.3f} bits")

    if repayment <= 0:
        print(f"✗ FAILURE: No repayment earned from calibration!")
        return False

    debt_after = controller.get_total_debt()
    print(f"Debt after repayment: {debt_after:.3f} bits (was {debt:.3f})")

    if debt_after >= debt:
        print(f"✗ FAILURE: Debt did NOT decrease!")
        return False

    print(f"✓ Debt decreased: {debt:.3f} → {debt_after:.3f} bits")

    # Check if biology can resume
    if debt_after < 2.0:
        print(f"\n[Step 5] Debt below threshold - checking if biology resumes...")
        should_refuse_bio_after, _, _ = controller.should_refuse_action(
            template_name="dose_response",
            base_cost_wells=20,
            budget_remaining=100,
            debt_hard_threshold=2.0
        )

        if should_refuse_bio_after:
            print(f"✗ FAILURE: Biology still blocked after debt clearance!")
            return False

        print(f"✓ Biology resumed after debt repayment")

    print(f"\n✓ AGENT 3 FIX VERIFIED: Debt deadlock prevented by capped inflation")
    return True


def test_extreme_debt_still_recoverable():
    """
    Test: Can we recover from EXTREME debt (10+ bits)?

    Even with massive overclaiming, calibration should remain affordable.
    """
    print("\n" + "=" * 70)
    print("Scenario B.2: Extreme Debt Recoverability")
    print("=" * 70)

    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate massive debt
    print("\n[Step 1] Accumulating EXTREME epistemic debt...")
    for i in range(20):
        controller.claim_action(
            action_id=f"massive_overclaim_{i}",
            action_type="biology",
            expected_gain_bits=1.0
        )
        controller.resolve_action(
            action_id=f"massive_overclaim_{i}",
            actual_gain_bits=0.0,
            action_type="biology"
        )

    debt = controller.get_total_debt()
    print(f"Extreme debt accumulated: {debt:.3f} bits")

    if debt < 10.0:
        print(f"⚠️  Debt ({debt:.3f}) < 10.0 (expected extreme)")

    # Check calibration affordability
    print("\n[Step 2] Checking calibration affordability with extreme debt...")
    budget = 50  # Reasonable budget
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="baseline_replicates",
        base_cost_wells=12,
        budget_remaining=budget,
        debt_hard_threshold=2.0
    )

    if should_refuse:
        print(f"✗ DEADLOCK: Calibration REFUSED with extreme debt!")
        print(f"  Refusal: {refusal_reason}")
        print(f"  Inflated cost: {context['inflated_cost_wells']} wells")
        print(f"  Budget: {budget} wells")

        if context.get('is_deadlocked', False):
            print(f"  ✓ Deadlock explicitly detected (good error message)")
        else:
            print(f"  ✗ Deadlock NOT explicitly detected (silent failure)")

        return False

    print(f"✓ Calibration STILL AFFORDABLE even with extreme debt")
    print(f"  Debt: {debt:.3f} bits")
    print(f"  Inflated cost: {context['inflated_cost_wells']} wells")
    print(f"  Budget: {budget} wells")
    print(f"  Inflation multiplier: {context['inflated_cost_wells'] / context['base_cost_wells']:.2f}×")

    return True


def test_deadlock_explicit_detection():
    """
    Test: If deadlock DOES occur, is it explicitly detected?

    Force a deadlock by constraining budget below minimum calibration cost.
    """
    print("\n" + "=" * 70)
    print("Scenario B.3: Explicit Deadlock Detection")
    print("=" * 70)

    config = EpistemicControllerConfig(
        debt_sensitivity=0.5,
        enable_debt_tracking=True
    )
    controller = EpistemicController(config)

    # Accumulate debt
    print("\n[Step 1] Accumulating debt...")
    for i in range(5):
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
    print(f"Debt: {debt:.3f} bits")

    # Constrain budget below inflated calibration cost
    print("\n[Step 2] Constraining budget to force deadlock...")
    budget = 10  # Less than minimum calibration cost (12 wells base × 1.5 cap = 18 wells)

    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",  # Any non-calibration action
        base_cost_wells=20,
        budget_remaining=budget,
        debt_hard_threshold=2.0
    )

    print(f"\nRefusal check:")
    print(f"  Should refuse: {should_refuse}")
    print(f"  Reason: {refusal_reason}")
    print(f"  Is deadlocked: {context.get('is_deadlocked', False)}")

    if not context.get('is_deadlocked', False):
        print(f"\n✗ FAILURE: Deadlock exists but NOT explicitly detected!")
        print(f"  Budget: {budget} wells")
        print(f"  Min calibration cost (inflated): ~{int(MIN_CALIBRATION_COST_WELLS * 1.5)} wells")
        print(f"  Debt: {debt:.3f} bits > 2.0 threshold")
        print(f"  System should flag this as terminal deadlock")
        return False

    print(f"\n✓ Deadlock EXPLICITLY DETECTED")
    print(f"  Refusal reason: {refusal_reason}")
    print(f"  Budget: {budget} wells")
    print(f"  Required for recovery: ~{context.get('required_reserve', MIN_CALIBRATION_COST_WELLS)} wells")

    return True


if __name__ == "__main__":
    print("Agent 2 Phase 2: Reproducing (or Verifying) Debt Deadlock")
    print("\n")

    results = []

    results.append(("Agent 3 fix verification", test_debt_deadlock_fixed_by_agent3()))
    results.append(("Extreme debt recoverability", test_extreme_debt_still_recoverable()))
    results.append(("Explicit deadlock detection", test_deadlock_explicit_detection()))

    print("\n" + "=" * 70)
    print("SCENARIO B RESULTS")
    print("=" * 70)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(p for _, p in results)

    if all_passed:
        print("\n✓ All scenarios passed")
        print("  - Agent 3 fix prevents deadlock")
        print("  - Extreme debt is recoverable")
        print("  - Deadlock is explicitly detected when it occurs")
    else:
        print("\n✗ FAILURES DETECTED")
        print("  Agent 2 must address debt recoverability")
