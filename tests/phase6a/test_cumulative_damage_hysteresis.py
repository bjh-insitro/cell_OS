"""
Test cumulative damage integrators (Phase: Scars).

Verifies that:
1. Damage accumulates under sustained stress
2. Damage decays slowly when stress is removed
3. Hysteresis exists: second pulse causes worse outcome than first
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_er_damage_accumulates_under_stress():
    """
    ER damage should accumulate when cells are stressed and approach steady state.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply ER stress compound
    vm.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=1.0)

    # Initial damage should be zero
    assert vessel.er_damage == 0.0, "Initial er_damage should be 0.0"

    # Run for 24h - damage should accumulate
    vm.advance_time(24.0)
    damage_24h = vessel.er_damage

    # Run for another 24h - damage should increase further
    vm.advance_time(24.0)
    damage_48h = vessel.er_damage

    # Assertions
    assert damage_24h > 0.01, f"Damage at 24h ({damage_24h:.4f}) should be > 0.01"
    assert damage_48h > damage_24h, f"Damage at 48h ({damage_48h:.4f}) should exceed 24h ({damage_24h:.4f})"
    assert damage_48h < 1.0, f"Damage at 48h ({damage_48h:.4f}) should be < 1.0"

    print(f"✓ ER damage accumulates: 0h=0.000, 24h={damage_24h:.4f}, 48h={damage_48h:.4f}")


def test_mito_damage_accumulates_under_stress():
    """
    Mito damage should accumulate when cells are stressed.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply mito stress compound
    vm.treat_with_compound("Plate1_A01", "rotenone", dose_uM=5.0)

    # Initial damage should be zero
    assert vessel.mito_damage == 0.0, "Initial mito_damage should be 0.0"

    # Run for 24h
    vm.advance_time(24.0)
    damage_24h = vessel.mito_damage

    # Run for another 24h
    vm.advance_time(24.0)
    damage_48h = vessel.mito_damage

    # Assertions
    assert damage_24h > 0.01, f"Mito damage at 24h ({damage_24h:.4f}) should be > 0.01"
    assert damage_48h > damage_24h, f"Mito damage at 48h ({damage_48h:.4f}) should exceed 24h ({damage_24h:.4f})"

    print(f"✓ Mito damage accumulates: 0h=0.000, 24h={damage_24h:.4f}, 48h={damage_48h:.4f}")


def test_transport_damage_accumulates_under_stress():
    """
    Transport damage should accumulate under microtubule stress.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply microtubule stress compound
    vm.treat_with_compound("Plate1_A01", "nocodazole", dose_uM=5.0)

    # Initial damage should be zero
    assert vessel.transport_damage == 0.0, "Initial transport_damage should be 0.0"

    # Run for 24h
    vm.advance_time(24.0)
    damage_24h = vessel.transport_damage

    # Run for another 24h
    vm.advance_time(24.0)
    damage_48h = vessel.transport_damage

    # Assertions
    assert damage_24h > 0.01, f"Transport damage at 24h ({damage_24h:.4f}) should be > 0.01"
    assert damage_48h > damage_24h, f"Transport damage at 48h ({damage_48h:.4f}) should exceed 24h ({damage_24h:.4f})"

    print(f"✓ Transport damage accumulates: 0h=0.000, 24h={damage_24h:.4f}, 48h={damage_48h:.4f}")


def test_damage_decays_without_stress():
    """
    Damage should decay slowly when stress is removed (24h half-life expected).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply ER stress to accumulate damage
    vm.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=2.0)
    vm.advance_time(48.0)  # Build up damage
    damage_peak = vessel.er_damage

    # Washout compound to remove stress
    vm.wash_vessel("Plate1_A01")

    # Run recovery periods
    vm.advance_time(24.0)  # 24h recovery
    damage_24h_recovery = vessel.er_damage

    vm.advance_time(24.0)  # 48h total recovery
    damage_48h_recovery = vessel.er_damage

    # Assertions: damage should decay with ~24h half-life
    # After 24h: expect ~50% remaining
    # After 48h: expect ~25% remaining
    half_life_tolerance = 0.2  # 20% tolerance for complex dynamics

    expected_24h = damage_peak * 0.5
    expected_48h = damage_peak * 0.25

    assert damage_24h_recovery < damage_peak, "Damage should decrease during recovery"
    assert damage_48h_recovery < damage_24h_recovery, "Damage should continue decreasing"

    # Check half-life is in expected range (20-30h)
    # If t_half=24h, damage_24h_recovery ≈ 0.5 * damage_peak
    ratio_24h = damage_24h_recovery / damage_peak if damage_peak > 0 else 0
    assert 0.3 < ratio_24h < 0.7, f"Decay ratio at 24h ({ratio_24h:.2f}) should be ~0.5 (half-life ~24h)"

    print(f"✓ Damage decays: peak={damage_peak:.4f}, 24h={damage_24h_recovery:.4f}, 48h={damage_48h_recovery:.4f}")
    print(f"  Decay ratio at 24h: {ratio_24h:.2f} (expect ~0.5 for 24h half-life)")


def test_hysteresis_second_pulse_is_worse():
    """
    Hysteresis: second pulse should cause worse outcome than first pulse.

    This is the key test for stress memory. Cells that have been stressed
    retain damage that makes them more vulnerable to subsequent insults.
    """
    # First pulse: naïve cells
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vm1.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=1.5)
    vm1.advance_time(24.0)
    vessel1 = vm1.vessel_states["Plate1_A01"]
    pulse1_viability = vessel1.viability
    pulse1_damage = vessel1.er_damage

    # Second pulse: cells with prior damage
    vm2 = BiologicalVirtualMachine(seed=42)
    vm2.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    # First pulse
    vm2.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=1.5)
    vm2.advance_time(24.0)
    vm2.wash_vessel("Plate1_A01")  # Remove compound

    # Recovery period (damage persists but stress drops)
    vm2.advance_time(24.0)
    vessel2 = vm2.vessel_states["Plate1_A01"]
    damage_before_pulse2 = vessel2.er_damage
    viability_before_pulse2 = vessel2.viability

    # Second pulse (same dose)
    vm2.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=1.5)
    vm2.advance_time(24.0)
    pulse2_viability = vessel2.viability
    pulse2_damage = vessel2.er_damage

    # Assertions: second pulse should be worse
    print(f"\nPulse 1 (naïve cells):")
    print(f"  Viability after 24h: {pulse1_viability:.4f}")
    print(f"  Damage after 24h: {pulse1_damage:.4f}")

    print(f"\nPulse 2 (pre-damaged cells):")
    print(f"  Damage before pulse: {damage_before_pulse2:.4f}")
    print(f"  Viability before pulse: {viability_before_pulse2:.4f}")
    print(f"  Viability after 24h: {pulse2_viability:.4f}")
    print(f"  Damage after 24h: {pulse2_damage:.4f}")

    # Key assertion: second pulse causes lower viability (worse outcome)
    viability_drop_pulse1 = 1.0 - pulse1_viability
    viability_drop_pulse2 = viability_before_pulse2 - pulse2_viability

    print(f"\nViability drop comparison:")
    print(f"  Pulse 1: {viability_drop_pulse1:.4f}")
    print(f"  Pulse 2: {viability_drop_pulse2:.4f}")

    # Second pulse should cause MORE damage due to pre-existing damage
    assert damage_before_pulse2 > 0.01, f"Damage should persist before pulse 2 ({damage_before_pulse2:.4f})"
    assert pulse2_viability < pulse1_viability, \
        f"Pulse 2 viability ({pulse2_viability:.4f}) should be < Pulse 1 ({pulse1_viability:.4f})"

    print(f"\n✓ Hysteresis confirmed: second pulse is worse")
    print(f"  Viability: Pulse 1 = {pulse1_viability:.4f}, Pulse 2 = {pulse2_viability:.4f}")


def test_chronic_damage_causes_slow_death():
    """
    Accumulated damage should cause slow attrition even without active compound.

    This tests that chronic damage creates a hazard that removes the
    "immortal above viability 0.5" pathology.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply high stress to build up damage
    vm.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=3.0)
    vm.advance_time(48.0)
    damage_after_stress = vessel.er_damage
    viability_after_stress = vessel.viability

    # Washout compound but keep damage
    vm.wash_vessel("Plate1_A01")
    vm.advance_time(1.0)  # Let stress decay
    stress_after_washout = vessel.er_stress
    damage_after_washout = vessel.er_damage
    viability_after_washout = vessel.viability

    # Run for extended period without compound - damage should cause slow death
    vm.advance_time(72.0)
    viability_final = vessel.viability

    print(f"\nChronic damage test:")
    print(f"  Damage after stress: {damage_after_stress:.4f}")
    print(f"  Viability after stress: {viability_after_stress:.4f}")
    print(f"  Stress after washout: {stress_after_washout:.4f}")
    print(f"  Damage after washout: {damage_after_washout:.4f}")
    print(f"  Viability after washout: {viability_after_washout:.4f}")
    print(f"  Viability after 72h recovery: {viability_final:.4f}")

    # Assertions
    assert damage_after_washout > 0.3, f"Damage should persist after washout ({damage_after_washout:.4f})"
    assert stress_after_washout < 0.1, f"Stress should decay after washout ({stress_after_washout:.4f})"
    assert viability_final < viability_after_washout, \
        f"Chronic damage should cause death even without compound ({viability_final:.4f} vs {viability_after_washout:.4f})"

    print(f"\n✓ Chronic damage causes slow death despite low stress")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Cumulative Damage Integrators (Phase: Scars)")
    print("=" * 70)
    print()

    tests = [
        ("ER damage accumulates under stress", test_er_damage_accumulates_under_stress),
        ("Mito damage accumulates under stress", test_mito_damage_accumulates_under_stress),
        ("Transport damage accumulates under stress", test_transport_damage_accumulates_under_stress),
        ("Damage decays without stress", test_damage_decays_without_stress),
        ("Hysteresis: second pulse is worse", test_hysteresis_second_pulse_is_worse),
        ("Chronic damage causes slow death", test_chronic_damage_causes_slow_death),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            test_func()
            results.append((name, True))
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
