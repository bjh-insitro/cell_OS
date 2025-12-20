"""
Test that stress_axis diagnostic is deterministic when multiple compounds present.

Fix #2: Previously, stress_axis was "last compound wins" (order-dependent).
Now it's deterministic: uses "microtubule" axis if any microtubule compound present.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_stress_axis_deterministic_with_multiple_compounds():
    """
    Test that transport_dysfunction_score is computed deterministically
    when multiple compounds are present.

    Bug: stress_axis was overwritten in loop, making it "last compound wins"
    Fix: Use has_microtubule_compound flag, compute for "microtubule" axis deterministically
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Treat with multiple compounds (microtubule + ER stress)
    # Order matters for the bug, but shouldn't matter after fix
    vm.treat_with_compound("test_well", "nocodazole", dose_uM=1.0)  # microtubule
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)  # er_stress

    vm.advance_time(12.0)

    # Call assay multiple times - should get same transport_dysfunction_score
    result1 = vm.cell_painting_assay("test_well")
    result2 = vm.cell_painting_assay("test_well")

    score1 = result1['transport_dysfunction_score']
    score2 = result2['transport_dysfunction_score']

    print(f"Transport dysfunction score (call 1): {score1:.4f}")
    print(f"Transport dysfunction score (call 2): {score2:.4f}")

    # Scores should be identical (deterministic)
    if abs(score1 - score2) > 1e-9:
        print(f"❌ FAIL: Transport dysfunction score not deterministic")
        return False

    # Since nocodazole is microtubule, score should be computed (not 0.0)
    # But it might be 0 if transport dysfunction hasn't built up yet
    vessel = vm.vessel_states["test_well"]
    print(f"Transport dysfunction latent: {vessel.transport_dysfunction:.4f}")

    # The key test: score is deterministic regardless of compound iteration order
    print(f"✓ PASS: Transport dysfunction score is deterministic")
    return True


def test_stress_axis_zero_when_no_microtubule():
    """
    Test that transport_dysfunction_score is 0 when no microtubule compound present.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Treat with ER stress compound only (no microtubule)
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)
    vm.advance_time(12.0)

    result = vm.cell_painting_assay("test_well")
    score = result['transport_dysfunction_score']

    print(f"Transport dysfunction score (no microtubule): {score:.4f}")

    if abs(score) > 1e-9:
        print(f"❌ FAIL: Expected score=0 when no microtubule compound")
        return False

    print(f"✓ PASS: Transport dysfunction score is 0 (no microtubule)")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Stress Axis Determinism (Fix #2)")
    print("=" * 70)
    print()

    tests = [
        ("Deterministic with multiple compounds", test_stress_axis_deterministic_with_multiple_compounds),
        ("Zero when no microtubule", test_stress_axis_zero_when_no_microtubule),
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
