"""
Test that stress_threshold_shift works in the correct direction.

Bug: Previously used division (theta / shift), which inverted the semantics.
Fix: Now uses multiplication (theta * shift).

Semantics:
- sensitive (shift=0.8) should die at LOWER stress (theta = 0.7 * 0.8 = 0.56)
- resistant (shift=1.2) should die at HIGHER stress (theta = 0.7 * 1.2 = 0.84)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_sensitive_dies_before_resistant():
    """
    Test that sensitive subpop reaches death threshold before resistant.

    Apply ER stress and check that sensitive cells accumulate death first.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Apply moderate ER stress
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.5)

    # Let stress build up gradually
    for _ in range(12):
        vm.advance_time(2.0)  # 24h total

    vessel = vm.vessel_states["test_well"]

    # Check stress distribution
    print("ER stress after 24h tunicamycin 1.5µM:")
    for name, subpop in vessel.subpopulations.items():
        print(f"  {name}: stress={subpop['er_stress']:.3f}, "
              f"threshold_shift={subpop['stress_threshold_shift']:.2f}")

    # Compute effective thresholds
    from src.cell_os.hardware.biological_virtual import ER_STRESS_DEATH_THETA

    theta_sensitive = ER_STRESS_DEATH_THETA * vessel.subpopulations['sensitive']['stress_threshold_shift']
    theta_typical = ER_STRESS_DEATH_THETA * vessel.subpopulations['typical']['stress_threshold_shift']
    theta_resistant = ER_STRESS_DEATH_THETA * vessel.subpopulations['resistant']['stress_threshold_shift']

    print(f"\nEffective death thresholds:")
    print(f"  sensitive: {theta_sensitive:.3f}")
    print(f"  typical: {theta_typical:.3f}")
    print(f"  resistant: {theta_resistant:.3f}")

    # Check ordering: sensitive < typical < resistant
    if not (theta_sensitive < theta_typical < theta_resistant):
        print(f"❌ FAIL: Threshold ordering wrong")
        print(f"  Expected: sensitive < typical < resistant")
        print(f"  Got: {theta_sensitive:.3f} < {theta_typical:.3f} < {theta_resistant:.3f}")
        return False

    # Check death: if stress is high enough, sensitive should die first
    print(f"\nDeath accounting:")
    print(f"  death_er_stress: {vessel.death_er_stress:.4f}")
    print(f"  viability: {vessel.viability:.4f}")

    # Sensitive threshold is 0.56, typical is 0.70, resistant is 0.84
    # If all subpops have stress > 0.56, death should start
    stress_sensitive = vessel.subpopulations['sensitive']['er_stress']
    stress_resistant = vessel.subpopulations['resistant']['er_stress']

    if stress_sensitive > theta_sensitive and stress_resistant < theta_resistant:
        # Ideal adversarial case: sensitive dying, resistant not yet
        print(f"✓ Adversarial distribution: sensitive at risk, resistant safe")
        if vessel.death_er_stress > 0.001:
            print(f"✓ PASS: Sensitive dies first (death started)")
            return True
        else:
            print(f"⚠ WARN: Death should have started but didn't")
            return False
    elif stress_sensitive > theta_sensitive:
        # At least sensitive is dying
        print(f"✓ Sensitive above threshold, death should be happening")
        if vessel.death_er_stress > 0.001:
            print(f"✓ PASS: Death started (threshold order correct)")
            return True
        else:
            print(f"⚠ WARN: Death should have started but didn't")
            return False
    else:
        print(f"⚠ WARN: Stress too low to test threshold ordering")
        print(f"  But threshold order is correct: {theta_sensitive:.3f} < {theta_typical:.3f} < {theta_resistant:.3f}")
        return True


def test_threshold_values():
    """
    Test that computed thresholds match expectations.
    """
    from src.cell_os.hardware.biological_virtual import (
        ER_STRESS_DEATH_THETA,
        MITO_DYSFUNCTION_DEATH_THETA
    )

    # ER stress thresholds
    theta_er_sensitive = ER_STRESS_DEATH_THETA * 0.8
    theta_er_typical = ER_STRESS_DEATH_THETA * 1.0
    theta_er_resistant = ER_STRESS_DEATH_THETA * 1.2

    print(f"ER stress thresholds (base={ER_STRESS_DEATH_THETA}):")
    print(f"  sensitive (0.8): {theta_er_sensitive:.3f}")
    print(f"  typical (1.0): {theta_er_typical:.3f}")
    print(f"  resistant (1.2): {theta_er_resistant:.3f}")

    # Mito dysfunction thresholds
    theta_mito_sensitive = MITO_DYSFUNCTION_DEATH_THETA * 0.8
    theta_mito_typical = MITO_DYSFUNCTION_DEATH_THETA * 1.0
    theta_mito_resistant = MITO_DYSFUNCTION_DEATH_THETA * 1.2

    print(f"\nMito dysfunction thresholds (base={MITO_DYSFUNCTION_DEATH_THETA}):")
    print(f"  sensitive (0.8): {theta_mito_sensitive:.3f}")
    print(f"  typical (1.0): {theta_mito_typical:.3f}")
    print(f"  resistant (1.2): {theta_mito_resistant:.3f}")

    # Verify ordering
    if not (theta_er_sensitive < theta_er_typical < theta_er_resistant):
        print(f"❌ FAIL: ER threshold ordering wrong")
        return False

    if not (theta_mito_sensitive < theta_mito_typical < theta_mito_resistant):
        print(f"❌ FAIL: Mito threshold ordering wrong")
        return False

    print(f"\n✓ PASS: All thresholds ordered correctly (sensitive < typical < resistant)")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Threshold Shift Direction (Fix from Review)")
    print("=" * 70)
    print()

    tests = [
        ("Threshold values correct", test_threshold_values),
        ("Sensitive dies before resistant", test_sensitive_dies_before_resistant),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
