"""
Test that _apply_instant_kill semantics are correct (Fix #1 from review).

Bug: Docstring said "fraction of viable killed" but implementation did absolute drop.
Fix: Now correctly implements fraction of viable killed.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_instant_kill_fraction_of_viable():
    """
    Test that kill_fraction means "fraction of viable cells killed".

    If viability=0.8 and kill_fraction=0.5:
    - We kill 50% of viable cells
    - Realized kill = 0.8 * 0.5 = 0.4
    - New viability = 0.8 - 0.4 = 0.4 (NOT 0.8 - 0.5 = 0.3)
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=0.8)
    vessel = vm.vessel_states["test_well"]

    # Kill 50% of viable cells
    kill_fraction = 0.5
    vm._apply_instant_kill(vessel, kill_fraction, "death_compound")

    expected_viability = 0.8 * (1.0 - 0.5)  # 0.4
    expected_death_compound = 0.8 - 0.4  # 0.4 (realized kill)

    print(f"Initial viability: 0.8")
    print(f"Kill fraction: {kill_fraction} (50% of viable)")
    print(f"Expected viability: {expected_viability:.4f}")
    print(f"Actual viability: {vessel.viability:.4f}")
    print(f"Expected death_compound: {expected_death_compound:.4f}")
    print(f"Actual death_compound: {vessel.death_compound:.4f}")

    if abs(vessel.viability - expected_viability) > 1e-6:
        print(f"❌ FAIL: Viability incorrect")
        return False

    if abs(vessel.death_compound - expected_death_compound) > 1e-6:
        print(f"❌ FAIL: Death accounting incorrect")
        return False

    print(f"✓ PASS: Instant kill semantics correct (fraction of viable)")
    return True


def test_instant_kill_at_low_viability():
    """
    Test that instant kill doesn't overkill at low viability.

    If viability=0.3 and kill_fraction=0.5:
    - We kill 50% of viable cells (NOT 50% absolute)
    - Realized kill = 0.3 * 0.5 = 0.15
    - New viability = 0.3 - 0.15 = 0.15
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=0.3)
    vessel = vm.vessel_states["test_well"]

    # Kill 50% of viable cells
    kill_fraction = 0.5
    vm._apply_instant_kill(vessel, kill_fraction, "death_compound")

    expected_viability = 0.3 * (1.0 - 0.5)  # 0.15
    expected_death_compound = 0.3 - 0.15  # 0.15 (realized kill)

    print(f"Initial viability: 0.3")
    print(f"Kill fraction: {kill_fraction} (50% of viable)")
    print(f"Expected viability: {expected_viability:.4f}")
    print(f"Actual viability: {vessel.viability:.4f}")
    print(f"Expected death_compound: {expected_death_compound:.4f}")
    print(f"Actual death_compound: {vessel.death_compound:.4f}")

    if abs(vessel.viability - expected_viability) > 1e-6:
        print(f"❌ FAIL: Viability incorrect (overkill bug)")
        return False

    if abs(vessel.death_compound - expected_death_compound) > 1e-6:
        print(f"❌ FAIL: Death accounting incorrect")
        return False

    print(f"✓ PASS: No overkill at low viability")
    return True


def test_treat_with_compound_uses_correct_semantics():
    """
    Test that treat_with_compound() correctly uses the new semantics.

    viability_effect is a survival multiplier, so kill_fraction = 1 - viability_effect
    should be interpreted as "fraction of viable killed".
    """
    vm = BiologicalVirtualMachine(seed=42)
    # Start with non-perfect viability to detect overkill
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=0.90)

    initial_viability = vm.vessel_states["test_well"].viability
    print(f"Initial viability: {initial_viability:.4f}")

    # Apply moderate dose (should kill some but not all)
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)

    vessel = vm.vessel_states["test_well"]
    final_viability = vessel.viability
    death_compound = vessel.death_compound

    print(f"Final viability: {final_viability:.4f}")
    print(f"Death compound: {death_compound:.4f}")

    # Check conservation (includes seeding stress in death_unknown)
    total_dead = 1.0 - final_viability
    total_accounted = death_compound + vessel.death_unknown
    if abs(total_accounted - total_dead) > 1e-6:
        print(f"❌ FAIL: Death accounting doesn't match viability drop")
        print(f"  total_dead = {total_dead:.6f}, death_compound = {death_compound:.6f}, ")
        print(f"  death_unknown = {vessel.death_unknown:.6f}, total = {total_accounted:.6f}")
        return False

    # Viability should have dropped but not gone negative
    if final_viability < 0:
        print(f"❌ FAIL: Negative viability (overkill bug)")
        return False

    if final_viability >= initial_viability:
        print(f"❌ FAIL: Viability didn't drop (compound had no effect)")
        return False

    print(f"✓ PASS: treat_with_compound semantics correct")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Instant Kill Semantics (Fix #1)")
    print("=" * 70)
    print()

    tests = [
        ("Instant kill fraction of viable", test_instant_kill_fraction_of_viable),
        ("No overkill at low viability", test_instant_kill_at_low_viability),
        ("treat_with_compound uses correct semantics", test_treat_with_compound_uses_correct_semantics),
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
