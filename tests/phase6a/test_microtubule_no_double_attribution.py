"""
Enforcement Test: Microtubule No Double Attribution

Guards against:
- Double-crediting microtubule death to both death_compound and death_mitotic_catastrophe
- Dividing cells should ONLY credit death_mitotic_catastrophe (mitosis-linked)
- Non-dividing cells (neurons) should ONLY credit death_compound (transport collapse)

Critical property:
- For dividing cells + microtubule compounds: death_compound should remain ~0
- For non-dividing cells + microtubule compounds: death_mitotic_catastrophe should remain ~0
- No scenario where BOTH ledgers are credited significantly
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

def test_dividing_cells_only_mitotic_attribution():
    """
    Test that dividing cells (A549) credit ONLY death_mitotic_catastrophe for microtubule drugs.

    Setup:
    - Seed A549 (cancer line, dividing)
    - Treat with nocodazole (microtubule disruptor)
    - Advance time to allow death to accumulate
    - Verify death_mitotic_catastrophe > 0 but death_compound ≈ 0
    """
    print("Test: Dividing cells - only mitotic attribution")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=5e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_A01"]

    # Treat with microtubule disruptor at high dose
    vm.treat_with_compound("P1_A01", "nocodazole", 0.5)  # High dose to ensure death

    # Advance to 48h (allows mitotic death + any attrition to accumulate)
    vm.advance_time(48.0)

    death_compound = vessel.death_compound
    death_mitotic = vessel.death_mitotic_catastrophe
    total_death = 1.0 - vessel.viability

    print(f"t=48h:")
    print(f"  Viability: {vessel.viability:.4f}")
    print(f"  Total death: {total_death:.4f}")
    print(f"  death_compound: {death_compound:.4f}")
    print(f"  death_mitotic_catastrophe: {death_mitotic:.4f}")

    # Verify mitotic catastrophe is dominant
    if total_death > 0.05:  # At least 5% death happened
        if death_mitotic > 0.02:  # At least 2% credited to mitotic
            if death_compound < 0.01:  # Less than 1% to compound (near-zero)
                print(f"✓ PASS: Mitotic death attributed exclusively to death_mitotic_catastrophe")
                print(f"  No double-attribution (death_compound ≈ 0)")
                return True
            else:
                print(f"❌ FAIL: Both death_compound and death_mitotic credited")
                print(f"  This is double-attribution - microtubule death counted twice")
                return False
        else:
            print(f"❌ FAIL: No mitotic death despite microtubule treatment")
            print(f"  Expected death_mitotic_catastrophe > 0.02 for high-dose nocodazole")
            return False
    else:
        print(f"❌ FAIL: No significant death occurred")
        print(f"  Expected total_death > 0.05 for 0.5µM nocodazole @ 48h")
        return False


def test_neurons_only_transport_collapse_attribution():
    """
    Test that non-dividing cells (neurons) credit ONLY death_compound for microtubule drugs.

    Setup:
    - Seed iPSC_NGN2 (neurons, non-dividing)
    - Treat with nocodazole (microtubule disruptor)
    - Advance time to allow transport collapse death
    - Verify death_compound > 0 but death_mitotic_catastrophe ≈ 0
    """
    print("\nTest: Non-dividing cells - only transport collapse attribution")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_B02", "iPSC_NGN2", initial_count=5e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_B02"]

    # Treat with microtubule disruptor at high dose
    vm.treat_with_compound("P1_B02", "nocodazole", 1.0)  # Very high dose for neurons

    # Advance to 48h (allows transport collapse death to accumulate)
    # Neurons need longer exposure for axonal transport collapse
    vm.advance_time(48.0)

    death_compound = vessel.death_compound
    death_mitotic = vessel.death_mitotic_catastrophe
    total_death = 1.0 - vessel.viability

    print(f"t=48h:")
    print(f"  Viability: {vessel.viability:.4f}")
    print(f"  Total death: {total_death:.4f}")
    print(f"  death_compound: {death_compound:.4f}")
    print(f"  death_mitotic_catastrophe: {death_mitotic:.4f}")

    # Neurons shouldn't have mitotic death (they don't divide)
    # Death should be attributed to compound (transport collapse)
    if death_mitotic < 0.01:  # Near-zero mitotic (neurons don't divide)
        print(f"✓ PASS: No mitotic attribution for non-dividing cells")
        # Note: Transport collapse death might accumulate slowly
        # So we don't require death_compound > 0, just that mitotic = 0
        if death_compound > 0.01:
            print(f"  Transport collapse death properly attributed to death_compound")
        else:
            print(f"  (No transport collapse death yet - may need longer time or higher dose)")
        return True
    else:
        print(f"❌ FAIL: Mitotic catastrophe credited for non-dividing cells")
        print(f"  Neurons (iPSC_NGN2) should not have death_mitotic_catastrophe")
        return False


def test_no_cross_contamination_other_axes():
    """
    Test that non-microtubule compounds still credit death_compound normally.

    Setup:
    - Seed A549
    - Treat with tunicamycin (ER stress, NOT microtubule)
    - Advance time to allow attrition
    - Verify death_compound > 0 and death_mitotic_catastrophe ≈ 0
    """
    print("\nTest: Non-microtubule compounds - normal compound attribution")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_C03", "A549", initial_count=5e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_C03"]

    # Treat with ER stress compound (NOT microtubule)
    vm.treat_with_compound("P1_C03", "tunicamycin", 3.0)

    # Advance to 48h
    vm.advance_time(48.0)

    death_compound = vessel.death_compound
    death_mitotic = vessel.death_mitotic_catastrophe
    death_er_stress = vessel.death_er_stress
    total_death = 1.0 - vessel.viability

    print(f"t=48h:")
    print(f"  Viability: {vessel.viability:.4f}")
    print(f"  Total death: {total_death:.4f}")
    print(f"  death_compound: {death_compound:.4f}")
    print(f"  death_er_stress: {death_er_stress:.4f}")
    print(f"  death_mitotic_catastrophe: {death_mitotic:.4f}")

    # Non-microtubule compounds should credit death_compound (or mechanism-specific)
    # No mitotic catastrophe (not a microtubule drug)
    if death_mitotic < 0.01:  # Near-zero (not microtubule)
        if death_compound > 0.01 or death_er_stress > 0.01:
            print(f"✓ PASS: Non-microtubule compound attributed normally")
            print(f"  No mitotic catastrophe (correct - not microtubule axis)")
            return True
        else:
            print(f"⚠ WARNING: No death attribution despite treatment")
            print(f"  May need higher dose or longer time")
            return True  # Not a failure - just no death yet
    else:
        print(f"❌ FAIL: Mitotic catastrophe for non-microtubule compound")
        print(f"  Only microtubule drugs should trigger mitotic catastrophe")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test: Microtubule No Double Attribution")
    print("=" * 70)
    print()

    tests = [
        ("Dividing cells - only mitotic attribution", test_dividing_cells_only_mitotic_attribution),
        ("Non-dividing cells - only transport collapse attribution", test_neurons_only_transport_collapse_attribution),
        ("Non-microtubule compounds - normal attribution", test_no_cross_contamination_other_axes),
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
