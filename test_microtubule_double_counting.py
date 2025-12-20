"""
Test that microtubule morphology is not double-counted.

Bug (fixed): stress_axes['microtubule'] effects were applied to actin,
then transport_dysfunction latent state ALSO applied to actin.

Fix: Skip stress_axes effects for microtubule (line 2231), rely on latent state only.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_microtubule_single_application():
    """
    Test that actin signal is only modified ONCE for microtubule compounds.

    Setup:
    - Apply nocodazole (microtubule disruptor)
    - Check that actin inflation comes from transport_dysfunction latent only
    - Verify no double-counting vs baseline

    Expected: actin = baseline * (1 + TRANSPORT_DYSFUNCTION_MORPH_ALPHA * transport_dysfunction)
    Not: actin = baseline * axis_effect * (1 + TRANSPORT...)
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Get baseline morphology (no compound)
    result_baseline = vm.cell_painting_assay("test_well")
    actin_baseline = result_baseline['morphology_struct']['actin']

    print(f"Baseline actin: {actin_baseline:.2f}")

    # Apply microtubule compound and let transport dysfunction build
    vm.treat_with_compound("test_well", "nocodazole", dose_uM=1.0)
    vm.advance_time(12.0)  # Let latent state accumulate

    vessel = vm.vessel_states["test_well"]
    transport_dys = vessel.transport_dysfunction

    print(f"Transport dysfunction after 12h nocodazole: {transport_dys:.3f}")

    # Get morphology after treatment
    result_treated = vm.cell_painting_assay("test_well")
    actin_treated = result_treated['morphology_struct']['actin']

    print(f"Treated actin (structural): {actin_treated:.2f}")

    # Expected inflation from latent state only
    from src.cell_os.hardware.biological_virtual import TRANSPORT_DYSFUNCTION_MORPH_ALPHA
    expected_multiplier = 1.0 + TRANSPORT_DYSFUNCTION_MORPH_ALPHA * transport_dys
    expected_actin = actin_baseline * expected_multiplier

    print(f"Expected actin (latent only): {expected_actin:.2f}")
    print(f"Multiplier expected: {expected_multiplier:.3f}")
    print(f"Multiplier observed: {actin_treated / actin_baseline:.3f}")

    # Check that observed matches expected (within noise tolerance)
    ratio = actin_treated / expected_actin
    if abs(ratio - 1.0) > 0.05:  # 5% tolerance for numerical drift
        print(f"❌ FAIL: Actin inflation doesn't match latent-only model (ratio={ratio:.3f})")
        print(f"  This suggests double-counting or missing gating")
        return False

    print(f"✓ PASS: Actin inflation matches latent-only model (ratio={ratio:.3f})")
    return True


def test_microtubule_vs_er_stress_independence():
    """
    Test that microtubule (gated) and ER stress (not gated) work independently.

    Apply both nocodazole (microtubule) and tunicamycin (ER stress).
    Verify:
    - Actin responds to transport dysfunction only (not direct axis effect)
    - ER responds to both direct axis effect AND latent state
    """
    vm = BiologicalVirtualMachine(seed=50)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Get baseline
    result_baseline = vm.cell_painting_assay("test_well")
    actin_baseline = result_baseline['morphology_struct']['actin']
    er_baseline = result_baseline['morphology_struct']['er']

    # Apply both compounds
    vm.treat_with_compound("test_well", "nocodazole", dose_uM=1.0)  # microtubule
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)  # er_stress
    vm.advance_time(12.0)

    vessel = vm.vessel_states["test_well"]

    print(f"Transport dysfunction: {vessel.transport_dysfunction:.3f}")
    print(f"ER stress: {vessel.er_stress:.3f}")

    result_treated = vm.cell_painting_assay("test_well")
    actin_treated = result_treated['morphology_struct']['actin']
    er_treated = result_treated['morphology_struct']['er']

    # Actin should respond to transport dysfunction latent only
    from src.cell_os.hardware.biological_virtual import (
        TRANSPORT_DYSFUNCTION_MORPH_ALPHA,
        ER_STRESS_MORPH_ALPHA
    )

    actin_multiplier = 1.0 + TRANSPORT_DYSFUNCTION_MORPH_ALPHA * vessel.transport_dysfunction
    expected_actin = actin_baseline * actin_multiplier

    # ER should respond to BOTH direct axis effect AND latent state
    # (We can't easily predict direct axis effect without YAML, so just check it increased)
    er_multiplier = er_treated / er_baseline

    print(f"\nActin:")
    print(f"  Expected multiplier: {actin_multiplier:.3f}")
    print(f"  Observed multiplier: {actin_treated / actin_baseline:.3f}")

    print(f"\nER:")
    print(f"  Observed multiplier: {er_multiplier:.3f} (should be > 1.0, includes axis + latent)")

    # Check actin matches latent-only model
    actin_ratio = actin_treated / expected_actin
    if abs(actin_ratio - 1.0) > 0.05:
        print(f"❌ FAIL: Actin doesn't match latent-only (ratio={actin_ratio:.3f})")
        return False

    # Check ER increased (axis effect + latent should inflate)
    if er_multiplier < 1.05:
        print(f"❌ FAIL: ER didn't increase (multiplier={er_multiplier:.3f})")
        return False

    print(f"✓ PASS: Microtubule (gated) and ER stress (not gated) work independently")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Microtubule Double-Counting Fix")
    print("=" * 70)
    print()

    tests = [
        ("Microtubule single application", test_microtubule_single_application),
        ("Microtubule vs ER stress independence", test_microtubule_vs_er_stress_independence),
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
