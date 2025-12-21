"""
Test: Debt repayment mechanics (the redemption path).

These tests verify that debt repayment is evidence-based, not free forgiveness:
1. Calibration that improves noise earns bonus repayment
2. Calibration without improvement earns only base repayment
3. Repayment is capped (no single action wipes massive debt)

This is about honest redemption. Calibration is work, not magic.
"""

from cell_os.epistemic_control import EpistemicController, EpistemicControllerConfig


def test_repayment_is_evidence_based():
    """
    Test 1: Calibration with measurable improvement earns bonus repayment.

    Flow:
    1. Accumulate 2.0 bits of debt
    2. Run calibration that reduces noise by 5%
    3. Verify debt reduced by > base repayment (0.25 bits)
    4. Verify repayment includes bonus for improvement
    """

    controller = EpistemicController(
        config=EpistemicControllerConfig(
            debt_sensitivity=0.15,
            enable_debt_tracking=True
        )
    )

    # Accumulate 2.0 bits debt
    controller.claim_action("action_1", "exploration", expected_gain_bits=1.0)
    controller.resolve_action("action_1", actual_gain_bits=0.0)

    controller.claim_action("action_2", "exploration", expected_gain_bits=1.0)
    controller.resolve_action("action_2", actual_gain_bits=0.0)

    debt_initial = controller.get_total_debt()
    assert abs(debt_initial - 2.0) < 0.01, f"Expected 2.0 bits debt, got {debt_initial}"

    # Run calibration with 5% noise improvement
    noise_improvement = 0.05  # 5% reduction in rel_width

    repayment = controller.compute_repayment(
        action_id="calib_1",
        action_type="baseline",
        is_calibration=True,
        noise_improvement=noise_improvement
    )

    debt_after = controller.get_total_debt()

    # Assertions

    # 1. Repayment should exceed base (0.25 bits)
    BASE_REPAYMENT = 0.25
    assert repayment > BASE_REPAYMENT, \
        f"With improvement, repayment ({repayment:.3f}) should exceed base ({BASE_REPAYMENT})"

    # 2. Debt should be reduced by repayment amount
    expected_debt_after = debt_initial - repayment
    assert abs(debt_after - expected_debt_after) < 0.001, \
        f"Expected debt {expected_debt_after:.3f}, got {debt_after:.3f}"

    # 3. Bonus should be proportional to improvement
    # Bonus = improvement * 7.5, capped at 0.75
    expected_bonus = min(0.75, noise_improvement * 7.5)
    expected_total = BASE_REPAYMENT + expected_bonus
    assert abs(repayment - expected_total) < 0.01, \
        f"Expected repayment {expected_total:.3f}, got {repayment:.3f}"

    print(f"\n✓ Evidence-based repayment test PASSED")
    print(f"   Debt: {debt_initial:.3f} → {debt_after:.3f}")
    print(f"   Repayment: {repayment:.3f} bits")
    print(f"   Breakdown: base={BASE_REPAYMENT}, bonus={expected_bonus:.3f} (from {noise_improvement*100:.1f}% improvement)")


def test_no_free_forgiveness():
    """
    Test 2: Calibration without measurable improvement earns only base repayment.

    This prevents calibration from being a magical debt eraser.
    """

    controller = EpistemicController(
        config=EpistemicControllerConfig(
            debt_sensitivity=0.15,
            enable_debt_tracking=True
        )
    )

    # Accumulate 1.5 bits debt
    controller.claim_action("action_1", "exploration", expected_gain_bits=1.5)
    controller.resolve_action("action_1", actual_gain_bits=0.0)

    debt_initial = controller.get_total_debt()
    assert abs(debt_initial - 1.5) < 0.01, f"Expected 1.5 bits debt, got {debt_initial}"

    # Run calibration WITHOUT noise improvement
    repayment = controller.compute_repayment(
        action_id="calib_1",
        action_type="baseline",
        is_calibration=True,
        noise_improvement=None  # No improvement measured
    )

    debt_after = controller.get_total_debt()

    # Assertions

    # 1. Repayment should be exactly base (0.25 bits)
    BASE_REPAYMENT = 0.25
    assert abs(repayment - BASE_REPAYMENT) < 0.001, \
        f"Without improvement, repayment should be base ({BASE_REPAYMENT}), got {repayment:.3f}"

    # 2. Debt reduced by base amount only
    expected_debt_after = debt_initial - BASE_REPAYMENT
    assert abs(debt_after - expected_debt_after) < 0.001, \
        f"Expected debt {expected_debt_after:.3f}, got {debt_after:.3f}"

    # 3. Run another calibration (verify cumulative)
    repayment2 = controller.compute_repayment(
        action_id="calib_2",
        action_type="baseline",
        is_calibration=True,
        noise_improvement=0.0  # Explicitly zero improvement
    )

    debt_final = controller.get_total_debt()

    assert abs(repayment2 - BASE_REPAYMENT) < 0.001, \
        "Second calibration should also earn base repayment"

    expected_debt_final = expected_debt_after - BASE_REPAYMENT
    assert abs(debt_final - expected_debt_final) < 0.001, \
        f"Expected final debt {expected_debt_final:.3f}, got {debt_final:.3f}"

    print(f"\n✓ No free forgiveness test PASSED")
    print(f"   Debt: {debt_initial:.3f} → {debt_after:.3f} → {debt_final:.3f}")
    print(f"   Each calibration repaid base {BASE_REPAYMENT} bits")
    print(f"   No bonus without measurable improvement")


def test_repayment_cap_enforced():
    """
    Test 3: Single calibration cannot wipe massive debt.

    Even with large improvement, repayment is capped at 1.0 bit.
    """

    controller = EpistemicController(
        config=EpistemicControllerConfig(
            debt_sensitivity=0.15,
            enable_debt_tracking=True
        )
    )

    # Accumulate 10 bits of debt (massive overclaim)
    for i in range(10):
        controller.claim_action(f"action_{i}", "exploration", expected_gain_bits=1.0)
        controller.resolve_action(f"action_{i}", actual_gain_bits=0.0)

    debt_initial = controller.get_total_debt()
    assert debt_initial >= 10.0, f"Expected >=10 bits debt, got {debt_initial}"

    # Run calibration with huge improvement (20% noise reduction)
    huge_improvement = 0.20

    repayment = controller.compute_repayment(
        action_id="calib_1",
        action_type="baseline",
        is_calibration=True,
        noise_improvement=huge_improvement
    )

    debt_after = controller.get_total_debt()

    # Assertions

    # 1. Repayment should be capped at 1.0 bit
    REPAYMENT_CAP = 1.0
    assert repayment <= REPAYMENT_CAP, \
        f"Repayment ({repayment:.3f}) should not exceed cap ({REPAYMENT_CAP})"

    assert abs(repayment - REPAYMENT_CAP) < 0.001, \
        f"With huge improvement, should hit cap, got {repayment:.3f}"

    # 2. Debt reduced by exactly 1.0 bit
    expected_debt_after = debt_initial - REPAYMENT_CAP
    assert abs(debt_after - expected_debt_after) < 0.001, \
        f"Expected debt {expected_debt_after:.3f}, got {debt_after:.3f}"

    # 3. Agent must do multiple calibrations to clear massive debt
    # (This forces repeated honest work, not one-time magic)
    assert debt_after > 5.0, \
        "With 10 bits debt, one calibration should not clear half"

    print(f"\n✓ Repayment cap test PASSED")
    print(f"   Debt: {debt_initial:.3f} → {debt_after:.3f}")
    print(f"   Repayment: {repayment:.3f} bits (capped at {REPAYMENT_CAP})")
    print(f"   Agent must do {int(debt_after / REPAYMENT_CAP) + 1} more calibrations to clear debt")


def test_non_calibration_earns_zero():
    """
    Test 4: Only calibration templates earn repayment.

    Exploration actions don't reduce debt, even if successful.
    """

    controller = EpistemicController(
        config=EpistemicControllerConfig(
            debt_sensitivity=0.15,
            enable_debt_tracking=True
        )
    )

    # Accumulate 1.0 bit debt
    controller.claim_action("action_1", "exploration", expected_gain_bits=1.0)
    controller.resolve_action("action_1", actual_gain_bits=0.0)

    debt_initial = controller.get_total_debt()
    assert abs(debt_initial - 1.0) < 0.01, f"Expected 1.0 bit debt, got {debt_initial}"

    # Try to get repayment from non-calibration action
    repayment = controller.compute_repayment(
        action_id="explore_1",
        action_type="dose_ladder",
        is_calibration=False,  # Not calibration
        noise_improvement=0.10  # Even with improvement
    )

    debt_after = controller.get_total_debt()

    # Assertions

    # 1. No repayment for non-calibration
    assert repayment == 0.0, \
        f"Non-calibration should earn zero repayment, got {repayment:.3f}"

    # 2. Debt unchanged
    assert abs(debt_after - debt_initial) < 0.001, \
        f"Debt should be unchanged, was {debt_initial:.3f}, now {debt_after:.3f}"

    print(f"\n✓ Non-calibration test PASSED")
    print(f"   Debt: {debt_initial:.3f} → {debt_after:.3f}")
    print(f"   Exploration earns zero repayment (even with improvement)")


if __name__ == "__main__":
    print("Running debt repayment tests...\n")
    print("="*70)

    try:
        test_repayment_is_evidence_based()
        print("\n" + "="*70)

        test_no_free_forgiveness()
        print("\n" + "="*70)

        test_repayment_cap_enforced()
        print("\n" + "="*70)

        test_non_calibration_earns_zero()
        print("\n" + "="*70)

        print("\n✅ ALL DEBT REPAYMENT TESTS PASSED")
        print("\nRedemption is honest:")
        print("  1. Repayment requires evidence (measurable improvement) ✓")
        print("  2. No free forgiveness (base repayment only without improvement) ✓")
        print("  3. Repayment capped (no single magic eraser) ✓")
        print("  4. Only calibration earns repayment ✓")
        print("\nCalibration is work, not magic.")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")
        raise
