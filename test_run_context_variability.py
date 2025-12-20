"""
Test that RunContext technical factors vary across runs but are reproducible within run.

Invariants:
1. Same (base_seed, run_id) → identical results (determinism)
2. Same base_seed, different run_id → different technical latents (variability)
3. Different run_id → same biology, different measurements (measurement-only drift)
"""

import sys
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_determinism_within_run():
    """
    Test 5.1: Same base_seed + run_id yields identical results.

    This is the most fundamental test: reproducibility.
    """
    base_seed = 42
    run_id_shared = 1000

    # Create two VMs with same seed and run_id
    context1 = RunContext.sample(run_id_shared)
    vm1 = BiologicalVirtualMachine(seed=base_seed, run_context=context1)

    context2 = RunContext.sample(run_id_shared)
    vm2 = BiologicalVirtualMachine(seed=base_seed, run_context=context2)

    # Run identical protocol
    for vm in [vm1, vm2]:
        vm.seed_vessel("test_well", "A549", 1e6)
        vm.advance_time(24.0)  # 24h growth
        vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)
        vm.advance_time(24.0)  # 24h treatment

    # Measure in both
    result1 = vm1.cell_painting_assay("test_well", plate_id="P1", batch_id="B1", well_position="A1")
    result2 = vm2.cell_painting_assay("test_well", plate_id="P1", batch_id="B1", well_position="A1")

    # Assert byte-identical results
    morph1 = result1["morphology"]
    morph2 = result2["morphology"]

    max_diff = max(abs(morph1[ch] - morph2[ch]) for ch in morph1.keys())
    print(f"Max channel difference: {max_diff:.12f}")

    if max_diff > 1e-9:
        print("❌ FAIL: Results not reproducible within run")
        for ch in morph1.keys():
            diff = abs(morph1[ch] - morph2[ch])
            if diff > 1e-9:
                print(f"  {ch}: {morph1[ch]:.6f} vs {morph2[ch]:.6f} (diff={diff:.12f})")
        return False
    else:
        print("✓ PASS: Results reproducible (byte-identical)")
        return True


def test_variability_across_runs():
    """
    Test 5.2: Different run_id yields different technical latents.

    This tests that batch/lot/instrument effects actually vary.
    """
    base_seed = 42

    # Two runs with different run_ids
    run_id_A = 1000
    run_id_B = 2000

    context_A = RunContext.sample(run_id_A)
    vm_A = BiologicalVirtualMachine(seed=base_seed, run_context=context_A)

    context_B = RunContext.sample(run_id_B)
    vm_B = BiologicalVirtualMachine(seed=base_seed, run_context=context_B)

    # Run identical protocol on both
    for vm in [vm_A, vm_B]:
        vm.seed_vessel("sentinel", "A549", 1e6)
        vm.advance_time(24.0)  # Just growth, no treatment (sentinel baseline)

    # Measure sentinels
    result_A = vm_A.cell_painting_assay("sentinel", plate_id="P1", batch_id="B1", well_position="H12")
    result_B = vm_B.cell_painting_assay("sentinel", plate_id="P1", batch_id="B1", well_position="H12")

    morph_A = result_A["morphology"]
    morph_B = result_B["morphology"]

    # Assert: sentinels differ due to technical factors
    # Expected technical CV ~5-15%, so differences should be detectable
    diffs = {ch: abs(morph_A[ch] - morph_B[ch]) for ch in morph_A.keys()}
    relative_diffs = {ch: diffs[ch] / max(morph_A[ch], 1e-6) for ch in morph_A.keys()}

    print("Sentinel baseline differences across runs:")
    for ch in sorted(morph_A.keys()):
        print(f"  {ch}: {morph_A[ch]:.2f} vs {morph_B[ch]:.2f} (rel diff: {100*relative_diffs[ch]:.1f}%)")

    # If ALL channels differ by < 0.1%, technical factors aren't varying
    # (This threshold depends on your technical CV params, tune as needed)
    min_detectable_diff = 0.001  # 0.1% relative difference
    significant_diffs = [ch for ch, rd in relative_diffs.items() if rd > min_detectable_diff]

    if len(significant_diffs) == 0:
        print("❌ FAIL: No significant differences across runs (technical factors not varying)")
        return False
    else:
        print(f"✓ PASS: {len(significant_diffs)}/{len(morph_A)} channels show variability")
        return True


def test_biology_invariance_to_measurement_drift():
    """
    Test 5.3: Different run_id changes measurements but not latent biology.

    This is the critical separation-of-concerns test.
    """
    base_seed = 42

    run_id_A = 1000
    run_id_B = 2000

    context_A = RunContext.sample(run_id_A)
    vm_A = BiologicalVirtualMachine(seed=base_seed, run_context=context_A)

    context_B = RunContext.sample(run_id_B)
    vm_B = BiologicalVirtualMachine(seed=base_seed, run_context=context_B)

    # Run identical protocol
    for vm in [vm_A, vm_B]:
        vm.seed_vessel("test_well", "A549", 1e6)
        vm.advance_time(24.0)
        vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)
        vm.advance_time(24.0)

    # Check latent biology state (pre-measurement)
    vessel_A = vm_A.vessel_states["test_well"]
    vessel_B = vm_B.vessel_states["test_well"]

    # Biology should be identical (observer independence)
    biology_fields = ["viability", "cell_count", "er_stress", "mito_dysfunction", "transport_dysfunction"]
    biology_identical = True

    print("Latent biology comparison (should be identical):")
    for field in biology_fields:
        val_A = getattr(vessel_A, field)
        val_B = getattr(vessel_B, field)
        diff = abs(val_A - val_B)
        print(f"  {field}: {val_A:.6f} vs {val_B:.6f} (diff={diff:.9f})")
        if diff > 1e-9:
            biology_identical = False

    # Measurements should differ (technical factors)
    result_A = vm_A.cell_painting_assay("test_well", plate_id="P1", batch_id="B1", well_position="A1")
    result_B = vm_B.cell_painting_assay("test_well", plate_id="P1", batch_id="B1", well_position="A1")

    morph_A = result_A["morphology"]
    morph_B = result_B["morphology"]

    measurement_differs = any(
        abs(morph_A[ch] - morph_B[ch]) / max(morph_A[ch], 1e-6) > 0.001
        for ch in morph_A.keys()
    )

    print("\nMeasurements comparison (should differ):")
    for ch in sorted(morph_A.keys()):
        diff = abs(morph_A[ch] - morph_B[ch])
        rel_diff = diff / max(morph_A[ch], 1e-6)
        print(f"  {ch}: {morph_A[ch]:.2f} vs {morph_B[ch]:.2f} (rel diff: {100*rel_diff:.1f}%)")

    if not biology_identical:
        print("❌ FAIL: Biology state differs across runs (should be invariant)")
        return False
    elif not measurement_differs:
        print("❌ FAIL: Measurements don't differ across runs (technical factors not working)")
        return False
    else:
        print("✓ PASS: Biology invariant, measurements differ")
        return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing RunContext Technical Factor Variability")
    print("=" * 70)
    print()

    tests = [
        ("Determinism within run", test_determinism_within_run),
        ("Variability across runs", test_variability_across_runs),
        ("Biology invariance to measurement drift", test_biology_invariance_to_measurement_drift),
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
