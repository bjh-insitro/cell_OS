"""
v6 Patch Validation: Run-Level Biology Variability (Batch Effects)

Tripwires to ensure run-level modifiers actually change biology trajectories,
not just add cosmetic noise.

Tests:
1. Time-to-threshold spreads (non-degenerate distribution)
2. Correlation structure (within-run high, across-run lower)
3. Assay RNG isolation (measurements don't perturb biology)
4. Determinism + caching (same seed → same modifiers)
"""

import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.database.repositories.compound_repository import get_compound_ic50


def test_time_to_threshold_spreads():
    """
    Test 1: Time-to-threshold has non-zero spread (not a delta function).

    BEFORE v6: all vessels hit threshold at exactly 27.0h (std=0.0)
    AFTER v6: time spreads with CV ~ 0.10-0.20
    """
    print("\nTest 1: Time-to-threshold distribution spread")
    print("=" * 70)

    ic50_uM = get_compound_ic50("tunicamycin", "A549")
    dose_uM = ic50_uM * 4.0
    threshold = 0.5

    times_to_threshold = []
    n_runs = 8

    for run_idx in range(n_runs):
        seed = 1000 + run_idx
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", "A549", initial_count=1e6)

        # Run protocol
        vm.advance_time(24.0)
        vm.treat_with_compound("test", "tunicamycin", dose_uM=dose_uM)

        # Find time-to-threshold
        t = 24.0
        while t < 72.0:
            vm.advance_time(3.0)
            t += 3.0
            vessel = vm.vessel_states["test"]
            if vessel.viability < threshold:
                times_to_threshold.append(t)
                break

    times_to_threshold = np.array(times_to_threshold)
    mean_time = np.mean(times_to_threshold)
    std_time = np.std(times_to_threshold)
    cv_time = std_time / mean_time if mean_time > 0 else 0

    print(f"Times to threshold {threshold}: {times_to_threshold}")
    print(f"Mean: {mean_time:.2f}h, Std: {std_time:.2f}h, CV: {cv_time:.4f}")

    # KILL-SHOT ASSERTION: std must be non-zero
    assert std_time > 0, f"FAIL: std={std_time:.6f} is zero (delta function still present)"

    # Target: CV should be at least 0.05 (5%)
    assert cv_time > 0.05, f"FAIL: CV={cv_time:.4f} < 0.05 (variance too small)"

    print(f"✓ PASS: Time-to-threshold spreads (CV={cv_time:.4f} > 0.05)")
    return True


def test_correlation_structure():
    """
    Test 2: Within-run correlation high, across-run correlation lower.

    Ensures batch effects dominate (vessels in same run are correlated),
    not independent jitter.
    """
    print("\nTest 2: Correlation structure (within vs across runs)")
    print("=" * 70)

    ic50_uM = get_compound_ic50("tunicamycin", "A549")
    dose_uM = ic50_uM * 4.0

    n_runs = 4
    n_vessels_per_run = 4

    # Collect final viabilities for each vessel in each run
    run_data = []

    for run_idx in range(n_runs):
        seed = 2000 + run_idx
        vm = BiologicalVirtualMachine(seed=seed)

        vessel_viabs = []
        for v_idx in range(n_vessels_per_run):
            vid = f"v{v_idx}"
            vm.seed_vessel(vid, "A549", initial_count=1e6)

        vm.advance_time(24.0)
        for v_idx in range(n_vessels_per_run):
            vid = f"v{v_idx}"
            vm.treat_with_compound(vid, "tunicamycin", dose_uM=dose_uM)

        vm.advance_time(48.0)

        for v_idx in range(n_vessels_per_run):
            vid = f"v{v_idx}"
            vessel_viabs.append(vm.vessel_states[vid].viability)

        run_data.append(vessel_viabs)

    run_data = np.array(run_data)  # Shape: (n_runs, n_vessels_per_run)

    # Compute within-run correlations
    within_run_corrs = []
    for run_viabs in run_data:
        # Correlate all pairs within this run
        for i in range(len(run_viabs)):
            for j in range(i + 1, len(run_viabs)):
                # For single timepoint, correlation is trivial (1.0)
                # But the VARIANCE within run tells us something
                pass

    # Better metric: within-run variance vs between-run variance
    within_run_vars = [np.var(run_viabs) for run_viabs in run_data]
    mean_within_run_var = np.mean(within_run_vars)

    run_means = [np.mean(run_viabs) for run_viabs in run_data]
    between_run_var = np.var(run_means)

    print(f"Mean within-run variance: {mean_within_run_var:.6f}")
    print(f"Between-run variance: {between_run_var:.6f}")

    # ASSERTION: between-run variance should dominate within-run variance
    # (Batch effects are stronger than vessel-to-vessel noise within a batch)
    if mean_within_run_var > 0:
        ratio = between_run_var / mean_within_run_var
        print(f"Between/Within ratio: {ratio:.2f}")
        assert ratio > 1.0, f"FAIL: Between-run variance ({between_run_var:.6f}) not larger than within-run ({mean_within_run_var:.6f})"
    else:
        # If within-run var is zero, that's also a problem (perfect clones)
        assert between_run_var > 1e-6, f"FAIL: Both variances near zero (no variability at all)"

    print(f"✓ PASS: Batch effects dominate (between-run var > within-run var)")
    return True


def test_assay_rng_isolation():
    """
    Test 3: Assay measurements don't perturb biology trajectories.

    Run two identical protocols, but in one, insert extra measurements.
    Biology trajectories must be identical.
    """
    print("\nTest 3: Assay RNG isolation (observer independence)")
    print("=" * 70)

    seed = 3000
    ic50_uM = get_compound_ic50("tunicamycin", "A549")
    dose_uM = ic50_uM * 4.0

    # Run A: no extra measurements
    vm_A = BiologicalVirtualMachine(seed=seed)
    vm_A.seed_vessel("test", "A549", initial_count=1e6)
    vm_A.advance_time(24.0)
    vm_A.treat_with_compound("test", "tunicamycin", dose_uM=dose_uM)
    vm_A.advance_time(24.0)

    viab_A = vm_A.vessel_states["test"].viability
    count_A = vm_A.vessel_states["test"].cell_count

    # Run B: with extra measurements (perturb assay RNG call order)
    vm_B = BiologicalVirtualMachine(seed=seed)
    vm_B.seed_vessel("test", "A549", initial_count=1e6)
    vm_B.advance_time(24.0)

    # Extra measurement (uses assay RNG)
    vm_B.count_cells("test")

    vm_B.treat_with_compound("test", "tunicamycin", dose_uM=dose_uM)

    # More extra measurements
    vm_B.count_cells("test")
    vm_B.count_cells("test")

    vm_B.advance_time(24.0)

    viab_B = vm_B.vessel_states["test"].viability
    count_B = vm_B.vessel_states["test"].cell_count

    print(f"Run A (no extra measurements): viab={viab_A:.6f}, count={count_A:.0f}")
    print(f"Run B (extra measurements):    viab={viab_B:.6f}, count={count_B:.0f}")

    # ASSERTION: biology must be identical (observer independence)
    viab_diff = abs(viab_A - viab_B)
    count_diff = abs(count_A - count_B)

    assert viab_diff < 1e-9, f"FAIL: Viability differs ({viab_diff:.12f}) - assay RNG contaminating biology"
    assert count_diff < 1e-3, f"FAIL: Cell count differs ({count_diff:.3f}) - assay RNG contaminating biology"

    print(f"✓ PASS: Assay measurements don't perturb biology (viab_diff={viab_diff:.12f})")
    return True


def test_determinism_and_caching():
    """
    Test 4: Modifiers are deterministic and cached.

    Same seed → same modifiers.
    Different seed → at least one modifier differs.
    Modifiers stable across repeated calls within a run.
    """
    print("\nTest 4: Determinism and caching of biology modifiers")
    print("=" * 70)

    # Test 4a: Same seed → same modifiers
    seed = 4000

    vm1 = BiologicalVirtualMachine(seed=seed)
    mods1 = vm1.run_context.get_biology_modifiers()

    vm2 = BiologicalVirtualMachine(seed=seed)
    mods2 = vm2.run_context.get_biology_modifiers()

    print(f"Seed {seed}, VM1: {mods1}")
    print(f"Seed {seed}, VM2: {mods2}")

    for key in mods1.keys():
        diff = abs(mods1[key] - mods2[key])
        assert diff < 1e-12, f"FAIL: Modifier {key} differs between runs with same seed ({diff:.12f})"

    print(f"✓ PASS: Same seed → same modifiers (deterministic)")

    # Test 4b: Different seed → at least one modifier differs
    vm3 = BiologicalVirtualMachine(seed=seed + 1)
    mods3 = vm3.run_context.get_biology_modifiers()

    print(f"Seed {seed+1}, VM3: {mods3}")

    at_least_one_differs = False
    for key in mods1.keys():
        if abs(mods1[key] - mods3[key]) > 1e-6:
            at_least_one_differs = True
            print(f"  {key}: {mods1[key]:.6f} vs {mods3[key]:.6f} (differs)")

    assert at_least_one_differs, f"FAIL: Different seeds produce identical modifiers"
    print(f"✓ PASS: Different seeds → at least one modifier differs")

    # Test 4c: Caching (repeated calls return same values)
    vm4 = BiologicalVirtualMachine(seed=seed + 2)
    mods4_first = vm4.run_context.get_biology_modifiers()
    mods4_second = vm4.run_context.get_biology_modifiers()

    for key in mods4_first.keys():
        diff = abs(mods4_first[key] - mods4_second[key])
        assert diff < 1e-12, f"FAIL: Modifier {key} not cached (differs on repeat call: {diff:.12f})"

    print(f"✓ PASS: Modifiers are cached (stable across repeated calls)")

    return True


if __name__ == "__main__":
    print("=" * 70)
    print("v6 Patch Validation: Run-Level Biology Variability")
    print("=" * 70)

    tests = [
        ("Time-to-threshold spreads", test_time_to_threshold_spreads),
        ("Correlation structure", test_correlation_structure),
        ("Assay RNG isolation", test_assay_rng_isolation),
        ("Determinism + caching", test_determinism_and_caching),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except AssertionError as e:
            print(f"\n❌ FAIL: {e}")
            results.append((name, False))
        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
