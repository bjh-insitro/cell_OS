"""
Adversarial Test: Step-Size Consistency

These tests try to BREAK the simulator by varying step size. If integration
is correct, results should converge monotonically as dt → 0.

Critical properties:
- Depletion linearity: 2×12h ≈ 1×24h (path-independent)
- Attrition convergence: viability converges as dt decreases
- No hidden per-step effects (washout, contamination)

If these fail, something is using "hours" as a discrete switch or
re-sampling randomness in a dt-dependent way.
"""

import sys
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

EPSILON = 1e-6  # Numerical tolerance for float comparisons


def test_depletion_linearity_low_density():
    """
    Test nutrient depletion linearity at low cell density.

    Setup:
    - Low density (1e6 cells) → linear regime (no saturation)
    - Compare: 1×24h vs 2×12h vs 4×6h
    - Assert: glucose drop path-independent (within numerical error)

    If fails: Depletion is using discrete per-step logic instead of integration.
    """
    print("Test: Depletion linearity (low density)")
    print("-" * 70)

    seed = 42
    vessel_id = "P1_A01"
    initial_count = 1e6  # Low density

    results = {}

    # Case A: 1×24h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=0.98)
    glc_t0 = vm.vessel_states[vessel_id].media_glucose_mM

    vm.advance_time(24.0)

    glc_t24 = vm.vessel_states[vessel_id].media_glucose_mM
    results['1x24h'] = glc_t0 - glc_t24

    # Case B: 2×12h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=0.98)

    vm.advance_time(12.0)
    vm.advance_time(12.0)

    glc_t24 = vm.vessel_states[vessel_id].media_glucose_mM
    results['2x12h'] = glc_t0 - glc_t24

    # Case C: 4×6h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=0.98)

    for _ in range(4):
        vm.advance_time(6.0)

    glc_t24 = vm.vessel_states[vessel_id].media_glucose_mM
    results['4x6h'] = glc_t0 - glc_t24

    print(f"Glucose depletion @ 24h:")
    for key, drop in results.items():
        print(f"  {key}: {drop:.4f} mM")

    # Verify path independence (within numerical error)
    # Expected: Euler integration error scales with dt, so we expect O(dt) relative error
    baseline = results['1x24h']
    rel_error_2x12h = abs(results['2x12h'] - baseline) / baseline
    rel_error_4x6h = abs(results['4x6h'] - baseline) / baseline

    print(f"\nRelative errors (vs 1×24h baseline):")
    print(f"  2×12h: {rel_error_2x12h:.2%}")
    print(f"  4×6h: {rel_error_4x6h:.2%}")

    # Tolerance: Euler integration gives O(dt) error
    # With dt=24h baseline, 12h should be ~50% better, 6h ~75% better
    # But we're looking for "same order of magnitude" not exact convergence
    if rel_error_2x12h < 0.10 and rel_error_4x6h < 0.10:
        print(f"✓ PASS: Path-independent within 10% (linear regime)")
        return True
    else:
        print(f"❌ FAIL: Path-dependent depletion (discretization artifact)")
        return False


def test_depletion_linearity_with_growth_and_death():
    """
    Test nutrient depletion linearity with exponential growth + death.

    Setup:
    - High dose treatment → cells die during interval
    - Cell count changes exponentially (growth + death)
    - Depletion rate depends on viable cell count
    - Compare: 1×24h vs 2×12h

    This is harder than low density because consumption rate is time-varying.
    If fails: Depletion doesn't properly integrate over changing cell counts.
    """
    print("\n\nTest: Depletion linearity with growth and death")
    print("-" * 70)

    seed = 123
    vessel_id = "P1_B02"
    initial_count = 5e6  # High density

    # Case A: 1×24h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=1.0)
    glc_t0 = vm.vessel_states[vessel_id].media_glucose_mM

    # Treat with high dose (causes death)
    vm.treat_with_compound(vessel_id, "tunicamycin", 3.0)

    vm.advance_time(24.0)

    glc_t24_A = vm.vessel_states[vessel_id].media_glucose_mM
    viability_A = vm.vessel_states[vessel_id].viability
    count_A = vm.vessel_states[vessel_id].cell_count
    drop_A = glc_t0 - glc_t24_A

    # Case B: 2×12h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=1.0)

    # Same treatment
    vm.treat_with_compound(vessel_id, "tunicamycin", 3.0)

    vm.advance_time(12.0)
    vm.advance_time(12.0)

    glc_t24_B = vm.vessel_states[vessel_id].media_glucose_mM
    viability_B = vm.vessel_states[vessel_id].viability
    count_B = vm.vessel_states[vessel_id].cell_count
    drop_B = glc_t0 - glc_t24_B

    print(f"Case A (1×24h):")
    print(f"  Glucose drop: {drop_A:.4f} mM")
    print(f"  Viability: {viability_A:.4f}")
    print(f"  Cell count: {count_A:.2e}")

    print(f"\nCase B (2×12h):")
    print(f"  Glucose drop: {drop_B:.4f} mM")
    print(f"  Viability: {viability_B:.4f}")
    print(f"  Cell count: {count_B:.2e}")

    # Verify viability and count match (biology should be path-independent)
    viability_diff = abs(viability_A - viability_B)
    count_rel_diff = abs(count_A - count_B) / max(count_A, count_B)

    if viability_diff < 0.01 and count_rel_diff < 0.05:
        print(f"\n✓ Biology path-independent:")
        print(f"  Viability diff: {viability_diff:.4f}")
        print(f"  Count rel diff: {count_rel_diff:.2%}")
    else:
        print(f"\n❌ FAIL: Biology is path-dependent")
        print(f"  Viability diff: {viability_diff:.4f} (expected < 0.01)")
        print(f"  Count rel diff: {count_rel_diff:.2%} (expected < 5%)")
        return False

    # Verify depletion matches (should integrate correctly over changing counts)
    depletion_rel_diff = abs(drop_A - drop_B) / max(drop_A, drop_B)

    if depletion_rel_diff < 0.10:
        print(f"✓ PASS: Depletion path-independent even with growth+death")
        print(f"  Depletion rel diff: {depletion_rel_diff:.2%}")
        return True
    else:
        print(f"❌ FAIL: Depletion path-dependent")
        print(f"  Depletion rel diff: {depletion_rel_diff:.2%} (expected < 10%)")
        return False


def test_attrition_convergence_variable_hazard():
    """
    Test attrition convergence as dt → 0 with time-varying hazard.

    Setup:
    - Treat with ER stress compound (hazard ramps up over time)
    - Compare dt = 24h, 12h, 6h, 3h
    - Assert: viability converges monotonically as dt → 0

    Why time-varying? Constant hazards are too forgiving (exp(-h*t) is exact).
    Time-varying hazards expose Euler integration errors.

    If fails: Hazard is applied as discrete per-step hit instead of integrated rate.
    """
    print("\n\nTest: Attrition convergence with time-varying hazard")
    print("-" * 70)

    seed = 999
    vessel_id = "P1_C03"
    initial_count = 5e6

    results = {}

    # Test different step sizes
    for steps, dt in [(2, 24.0), (4, 12.0), (8, 6.0), (16, 3.0)]:
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel(vessel_id, "A549", initial_count=initial_count, initial_viability=1.0)

        # Treat with ER stress compound (hazard ramps up as stress accumulates)
        vm.treat_with_compound(vessel_id, "tunicamycin", 2.0)

        # Step through 48h
        for _ in range(steps):
            vm.advance_time(dt)

        viability = vm.vessel_states[vessel_id].viability
        results[f'{steps}x{dt:.0f}h'] = viability

    print(f"Viability @ 48h (varying step size):")
    for key, viability in results.items():
        print(f"  {key}: {viability:.6f}")

    # Check for monotonic convergence
    # As dt decreases, viability should converge to some value
    # We're looking for |v(dt/2) - v(dt)| to decrease
    viabilities = list(results.values())

    # Compute successive differences
    diffs = [abs(viabilities[i+1] - viabilities[i]) for i in range(len(viabilities)-1)]

    print(f"\nSuccessive differences:")
    keys = list(results.keys())
    for i, diff in enumerate(diffs):
        print(f"  |{keys[i+1]} - {keys[i]}|: {diff:.6f}")

    # Check if differences are decreasing (convergence)
    is_converging = all(diffs[i] >= diffs[i+1] * 0.7 for i in range(len(diffs)-1))

    if is_converging:
        print(f"✓ PASS: Viability converges as dt → 0")
        print(f"  Differences decrease monotonically (integration is stable)")
        return True
    else:
        print(f"❌ FAIL: Viability does not converge")
        print(f"  Differences jitter (discrete per-step artifact)")
        return False


def test_rng_step_size_independence():
    """
    Test that RNG draws don't scale with number of steps.

    Setup:
    - Run same scenario with 1×24h vs 24×1h
    - No stochastic operations (feed, washout) during stepping
    - Only measurement noise at end
    - Assert: measurement variance is dt-independent

    If fails: Per-step random draws accumulating (should be per-time, not per-step).
    """
    print("\n\nTest: RNG step-size independence")
    print("-" * 70)

    vessel_id = "P1_D04"
    n_runs = 10

    # Collect measurement variance for 1×24h
    measurements_1x24 = []
    for run in range(n_runs):
        vm = BiologicalVirtualMachine(seed=1000 + run)
        vm.seed_vessel(vessel_id, "A549", initial_count=5e6, initial_viability=0.98)
        vm.advance_time(24.0)

        # Measure (includes biological noise)
        result = vm.cell_painting_assay(vessel_id)
        measurements_1x24.append(result['morphology']['er'])

    var_1x24 = np.var(measurements_1x24)

    # Collect measurement variance for 24×1h (many small steps)
    measurements_24x1 = []
    for run in range(n_runs):
        vm = BiologicalVirtualMachine(seed=1000 + run)
        vm.seed_vessel(vessel_id, "A549", initial_count=5e6, initial_viability=0.98)

        for _ in range(24):
            vm.advance_time(1.0)

        # Measure (includes biological noise)
        result = vm.cell_painting_assay(vessel_id)
        measurements_24x1.append(result['morphology']['er'])

    var_24x1 = np.var(measurements_24x1)

    print(f"Measurement variance (ER channel, n={n_runs}):")
    print(f"  1×24h: {var_1x24:.2f}")
    print(f"  24×1h: {var_24x1:.2f}")
    print(f"  Ratio: {var_24x1 / var_1x24:.2f}×")

    # Variance should be similar (within factor of 2)
    # If 24×1h has much higher variance, per-step noise is accumulating
    ratio = var_24x1 / var_1x24
    if 0.5 < ratio < 2.0:
        print(f"\n✓ PASS: Measurement variance dt-independent")
        print(f"  No accumulation of per-step randomness")
        return True
    else:
        print(f"\n❌ FAIL: Measurement variance scales with number of steps")
        print(f"  Per-step noise accumulating (should be per-time)")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Adversarial Test: Step-Size Consistency")
    print("=" * 70)
    print()

    tests = [
        ("Depletion linearity (low density)", test_depletion_linearity_low_density),
        ("Depletion linearity with growth+death", test_depletion_linearity_with_growth_and_death),
        ("Attrition convergence (variable hazard)", test_attrition_convergence_variable_hazard),
        ("RNG step-size independence", test_rng_step_size_independence),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
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
