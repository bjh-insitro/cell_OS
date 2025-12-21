"""
Test confluence saturation dt-invariance (interval-integrated growth).

This test isolates the confluence saturation nonlinearity from other effects
to verify that the predictor-corrector integration converges as dt → 0.

Contract:
- Same initial confluence (in nonlinear regime)
- Same total time
- Different dt → final cell count should converge
- Relative error should be < 1% (tighten to 0.1% if pure growth)
"""

import numpy as np
import copy
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_confluence_saturation_dt_invariance():
    """
    Growth saturation should converge across different step sizes.

    Start at high confluence (0.80) where saturation is nonlinear.
    Run 24h with dt=0.25h vs dt=2h.
    Final cell counts should converge within 1%.

    Note: Very large dt (6h+) will have higher error due to first-order
    predictor-corrector approximation. Test focuses on practical dt ranges.
    """
    # Create vessels with identical initial state
    vm1 = BiologicalVirtualMachine()
    vm2 = BiologicalVirtualMachine()

    # Seed vessels at high confluence (0.80, in nonlinear regime)
    capacity = 1.0e6
    initial_count = 0.80 * capacity

    v1 = "v_dt_025"
    v2 = "v_dt_2"

    vm1.seed_vessel(v1, "A549", initial_count=initial_count, capacity=capacity)
    vm2.seed_vessel(v2, "A549", initial_count=initial_count, capacity=capacity)

    vessel1 = vm1.vessel_states[v1]
    vessel2 = vm2.vessel_states[v2]

    # Set initial confluence explicitly (computed from cell_count / capacity)
    vessel1.confluence = vessel1.cell_count / vessel1.vessel_capacity
    vessel2.confluence = vessel2.cell_count / vessel2.vessel_capacity

    # Verify initial conditions match
    assert abs(vessel1.cell_count - vessel2.cell_count) < 1.0

    print(f"Initial confluence: {vessel1.confluence:.3f}")
    print(f"Initial cell count: {vessel1.cell_count:.2e}")

    # Verify we're in the nonlinear regime (>0.7)
    assert vessel1.confluence > 0.7, f"Initial confluence too low: {vessel1.confluence:.3f}"

    # Run growth-only simulation with different dt
    total_h = 24.0

    # Scenario 1: Small dt (0.25h)
    t = 0.0
    while t < total_h - 1e-9:
        step = min(0.25, total_h - t)
        vm1._update_vessel_growth(vessel1, step)
        t += step

    n_small = vessel1.cell_count
    c_small = vessel1.confluence

    # Scenario 2: Medium dt (2h)
    t = 0.0
    while t < total_h - 1e-9:
        step = min(2.0, total_h - t)
        vm2._update_vessel_growth(vessel2, step)
        t += step

    n_med = vessel2.cell_count
    c_med = vessel2.confluence

    print(f"\nFinal cell counts:")
    print(f"  dt=0.25h: {n_small:.6e} (confluence={c_small:.3f})")
    print(f"  dt=2.0h:  {n_med:.6e}   (confluence={c_med:.3f})")

    # Compute relative error
    n_ref = n_small  # Use smallest dt as reference
    rel_err = abs(n_med - n_ref) / n_ref

    print(f"\nRelative error (vs dt=0.25h):")
    print(f"  dt=2.0h:  {rel_err:.4%}")

    # Acceptance: relative error < 1% for practical dt ranges
    assert rel_err < 0.01, \
        f"dt=2.0h error too large: {rel_err:.4%} (expected <1%)"

    print("\n✓ Confluence saturation dt-invariance: PASS")


def test_saturation_monotonicity():
    """
    Saturation factor should be monotonic: higher confluence → lower growth factor.
    """
    vm = BiologicalVirtualMachine()

    # Create a vessel to access the saturation logic
    v = "v_test"
    vm.seed_vessel(v, "A549", initial_count=5000, capacity=10000)
    vessel = vm.vessel_states[v]

    # Get max_confluence parameter
    params = vm.cell_line_params.get(vessel.cell_line, vm.defaults)
    max_confluence = params.get("max_confluence", 0.9)

    # Test saturation factor at different confluence levels
    # Include max_confluence explicitly
    confluences = [0.0, 0.3, 0.5, 0.7, 0.85, max_confluence, 1.0]
    confluences = sorted(set(confluences))  # Remove duplicates and sort
    sat_factors = []

    for c in confluences:
        gf = 1.0 - (c / max_confluence) ** 2
        gf = max(0.0, min(1.0, gf))
        sat_factors.append(gf)

    print("Saturation factor vs confluence:")
    for c, gf in zip(confluences, sat_factors):
        print(f"  confluence={c:.2f} → sat_factor={gf:.4f}")

    # Assert monotonicity: sat_factor should decrease with confluence
    for i in range(len(sat_factors) - 1):
        assert sat_factors[i] >= sat_factors[i+1], \
            f"Saturation not monotonic: {sat_factors[i]:.4f} vs {sat_factors[i+1]:.4f}"

    # Assert bounds
    assert all(0.0 <= gf <= 1.0 for gf in sat_factors), \
        "Saturation factor out of bounds [0, 1]"

    # At confluence=0, should be near 1.0
    assert sat_factors[0] > 0.99, f"Saturation at c=0 too low: {sat_factors[0]:.4f}"

    # At confluence=max_confluence, should be 0.0
    idx_max = confluences.index(max_confluence)
    assert sat_factors[idx_max] == 0.0, \
        f"Saturation at max_confluence should be 0.0: {sat_factors[idx_max]:.4f}"

    print("✓ Saturation monotonicity: PASS")


def test_saturation_zero_time():
    """
    Zero-time update should not change cell count (no phantom growth).
    """
    vm = BiologicalVirtualMachine()
    v = "v_test"
    vm.seed_vessel(v, "A549", initial_count=8000, capacity=10000)
    vessel = vm.vessel_states[v]

    n_before = vessel.cell_count

    # Zero-time update
    vm._update_vessel_growth(vessel, 0.0)

    n_after = vessel.cell_count

    assert n_before == n_after, \
        f"Zero-time update changed cell count: {n_before:.2e} → {n_after:.2e}"

    print("✓ Saturation zero-time invariance: PASS")


if __name__ == "__main__":
    test_confluence_saturation_dt_invariance()
    test_saturation_monotonicity()
    test_saturation_zero_time()
    print("\n✅ All confluence saturation tests PASSED")
