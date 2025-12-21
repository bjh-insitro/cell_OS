"""
Test contact_pressure dt-invariance.

Pressure is a lagged state that should converge to the same steady-state
independent of step size.

Contract:
- Pressure ∈ [0, 1] (hard clamped)
- For fixed confluence, pressure converges similarly under different dt
- Higher confluence → higher steady-state pressure (monotonic)
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_contact_pressure_dt_invariance():
    """
    Pressure should converge similarly under different step sizes.

    Setup: vessel with fixed confluence (no growth).
    Run T=24h with dt=0.25h vs dt=2h.
    Expect: abs(p_small_dt - p_large_dt) < 1e-3
    """
    vm = BiologicalVirtualMachine()

    # Seed vessel with fixed confluence (no growth after this)
    vessel_id = "test_vessel"
    vm.seed_vessel(vessel_id, "A549", initial_count=8000, capacity=10000)
    vessel = vm.vessel_states[vessel_id]

    # Initial confluence = 0.8 (above midpoint c0=0.75)
    assert vessel.cell_count / vessel.vessel_capacity == 0.8

    # Scenario 1: Small dt (0.25h steps)
    vm1 = BiologicalVirtualMachine()
    v1 = "v1"
    vm1.seed_vessel(v1, "A549", initial_count=8000, capacity=10000)
    vessel1 = vm1.vessel_states[v1]

    # Disable growth by zeroing doubling time
    vessel1.cell_count = 8000  # Keep fixed

    for _ in range(96):  # 24h / 0.25h = 96 steps
        vm1._update_contact_pressure(vessel1, 0.25)
        vessel1.cell_count = 8000  # Keep confluence fixed

    p_small_dt = vessel1.contact_pressure

    # Scenario 2: Large dt (2h steps)
    vm2 = BiologicalVirtualMachine()
    v2 = "v2"
    vm2.seed_vessel(v2, "A549", initial_count=8000, capacity=10000)
    vessel2 = vm2.vessel_states[v2]
    vessel2.cell_count = 8000

    for _ in range(12):  # 24h / 2h = 12 steps
        vm2._update_contact_pressure(vessel2, 2.0)
        vessel2.cell_count = 8000

    p_large_dt = vessel2.contact_pressure

    # Both should converge to similar steady-state
    print(f"p_small_dt (0.25h): {p_small_dt:.6f}")
    print(f"p_large_dt (2h):    {p_large_dt:.6f}")
    print(f"Difference:         {abs(p_small_dt - p_large_dt):.6f}")

    assert abs(p_small_dt - p_large_dt) < 1e-3, \
        f"Pressure not dt-invariant: {p_small_dt:.6f} vs {p_large_dt:.6f}"

    # Both should be in [0, 1]
    assert 0.0 <= p_small_dt <= 1.0
    assert 0.0 <= p_large_dt <= 1.0

    print("✓ Contact pressure dt-invariance: PASS")


def test_contact_pressure_monotonic():
    """
    Higher confluence should give higher steady-state pressure.
    """
    vm = BiologicalVirtualMachine()

    # Low confluence (0.5)
    v_low = "v_low"
    vm.seed_vessel(v_low, "A549", initial_count=5000, capacity=10000)
    vessel_low = vm.vessel_states[v_low]

    for _ in range(12):  # Converge over 24h with dt=2h
        vm._update_contact_pressure(vessel_low, 2.0)
        vessel_low.cell_count = 5000  # Keep fixed

    p_low = vessel_low.contact_pressure

    # High confluence (0.9)
    v_high = "v_high"
    vm.seed_vessel(v_high, "A549", initial_count=9000, capacity=10000)
    vessel_high = vm.vessel_states[v_high]

    for _ in range(12):
        vm._update_contact_pressure(vessel_high, 2.0)
        vessel_high.cell_count = 9000

    p_high = vessel_high.contact_pressure

    print(f"Pressure at confluence 0.5: {p_low:.6f}")
    print(f"Pressure at confluence 0.9: {p_high:.6f}")

    # Monotonic: higher confluence → higher pressure
    assert p_high > p_low, \
        f"Pressure not monotonic: {p_low:.6f} (c=0.5) vs {p_high:.6f} (c=0.9)"

    # At c=0.5 (below midpoint c0=0.75), pressure should be low
    assert p_low < 0.5, f"Pressure too high at low confluence: {p_low:.6f}"

    # At c=0.9 (above midpoint), pressure should be high
    assert p_high > 0.7, f"Pressure too low at high confluence: {p_high:.6f}"

    print("✓ Contact pressure monotonicity: PASS")


def test_contact_pressure_zero_time():
    """
    Zero-time update should not change pressure (no phantom effects).
    """
    vm = BiologicalVirtualMachine()
    v = "v_test"
    vm.seed_vessel(v, "A549", initial_count=8000, capacity=10000)
    vessel = vm.vessel_states[v]

    # Initialize pressure
    vm._update_contact_pressure(vessel, 2.0)
    p_before = vessel.contact_pressure

    # Zero-time update
    vm._update_contact_pressure(vessel, 0.0)
    p_after = vessel.contact_pressure

    assert p_before == p_after, \
        f"Zero-time update changed pressure: {p_before:.6f} → {p_after:.6f}"

    print("✓ Contact pressure zero-time invariance: PASS")


if __name__ == "__main__":
    test_contact_pressure_dt_invariance()
    test_contact_pressure_monotonic()
    test_contact_pressure_zero_time()
    print("\n✅ All contact_pressure tests PASSED")
