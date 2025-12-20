"""
Enforcement Test 2: Evaporation Drift Affects Attrition

Asserts that InjectionManager is the spine, not decoration.

Guards against:
- Biology reading from legacy concentration fields instead of InjectionManager
- Evaporation being decorative (changes state but not biology)
- Parallel truth sources (intent vs measured)

Tests:
1. Edge well concentration increases more than interior (spatial drift real)
2. Higher concentration causes more attrition (biology reads spine)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_evaporation_drift_increases_concentration_edge_vs_interior():
    """
    Test that evaporation drift increases concentration more in edge wells.

    Setup:
    - Two wells: edge (A01) vs interior (D06)
    - Same initial dose
    - Advance time without ops
    - Assert edge concentration > interior concentration
    """
    print("Test: Evaporation drift increases concentration (edge vs interior)")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)

    # Two wells: one edge, one interior (96-well convention)
    edge = "Plate1_A01"      # edge (row A, col 1)
    interior = "Plate1_D06"  # interior

    vm.seed_vessel(edge, "A549", initial_count=1e6, initial_viability=0.98)
    vm.seed_vessel(interior, "A549", initial_count=1e6, initial_viability=0.98)

    print(f"Initial state:")
    print(f"  Edge ({edge}): seeded")
    print(f"  Interior ({interior}): seeded")

    # Same dose at time 0
    vm.treat_with_compound(edge, "tunicamycin", 0.8)
    vm.treat_with_compound(interior, "tunicamycin", 0.8)

    print(f"\nAfter treatment:")
    print(f"  Both wells dosed with 0.8 µM tunicamycin")

    # Advance 48 hours so evap drift matters
    print(f"\nAdvancing 48 hours...")
    vm.advance_time(48.0)

    # Read current concentrations from InjectionManager spine
    c_edge = vm.injection_mgr.get_compound_concentration_uM(edge, "tunicamycin")
    c_int = vm.injection_mgr.get_compound_concentration_uM(interior, "tunicamycin")

    print(f"\nFinal concentrations (after 48h evaporation):")
    print(f"  Edge: {c_edge:.3f} µM")
    print(f"  Interior: {c_int:.3f} µM")
    print(f"  Ratio (edge/interior): {c_edge/c_int:.3f}")

    # Edge must concentrate more
    if c_edge > c_int:
        print(f"✓ PASS: Edge well concentrated more (expected)")
        return True
    else:
        print(f"❌ FAIL: Edge well did not concentrate more (c_edge={c_edge:.3f}, c_int={c_int:.3f})")
        return False


def test_evaporation_drift_affects_attrition():
    """
    Test that higher concentration due to evaporation causes more attrition.

    Setup:
    - Two wells: edge vs interior
    - Same initial dose
    - Advance time without ops
    - Assert edge has more death (higher death_compound) from concentrated exposure

    Use death_compound accumulation instead of viability to avoid confounding from
    instant kill variance.
    """
    print("\nTest: Evaporation drift affects attrition (biology reads spine)")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=789)

    # Two wells: one edge, one interior
    edge = "Plate1_A01"
    interior = "Plate1_D06"

    vm.seed_vessel(edge, "A549", initial_count=1e6, initial_viability=1.0)  # Start with 100% to isolate attrition
    vm.seed_vessel(interior, "A549", initial_count=1e6, initial_viability=1.0)

    # Same dose at time 0 (low dose to avoid instant kill, focus on attrition)
    vm.treat_with_compound(edge, "tunicamycin", 0.5)
    vm.treat_with_compound(interior, "tunicamycin", 0.5)

    # Record death_compound after instant kill
    death_edge_after_instant = vm.vessel_states[edge].death_compound
    death_int_after_instant = vm.vessel_states[interior].death_compound

    print(f"After instant kill:")
    print(f"  Edge: death_compound={death_edge_after_instant:.4f}")
    print(f"  Interior: death_compound={death_int_after_instant:.4f}")

    # Advance 48 hours (attrition accumulates)
    print(f"\nAdvancing 48 hours...")
    vm.advance_time(48.0)

    # Read final death_compound (includes instant + attrition)
    death_edge_final = vm.vessel_states[edge].death_compound
    death_int_final = vm.vessel_states[interior].death_compound

    # Attrition delta = final - instant
    attrition_edge = death_edge_final - death_edge_after_instant
    attrition_int = death_int_final - death_int_after_instant

    # Read concentrations for context
    c_edge = vm.injection_mgr.get_compound_concentration_uM(edge, "tunicamycin")
    c_int = vm.injection_mgr.get_compound_concentration_uM(interior, "tunicamycin")

    print(f"\nFinal state (after 48h attrition):")
    print(f"  Edge: death_compound={death_edge_final:.4f}, attrition={attrition_edge:.4f}, conc={c_edge:.3f} µM")
    print(f"  Interior: death_compound={death_int_final:.4f}, attrition={attrition_int:.4f}, conc={c_int:.3f} µM")
    print(f"  Attrition ratio (edge/interior): {attrition_edge/max(0.001, attrition_int):.3f}")

    # Edge should have more attrition due to higher concentration
    if attrition_edge > attrition_int:
        print(f"✓ PASS: Edge well has more attrition (higher concentrated exposure)")
        return True
    else:
        print(f"❌ FAIL: Edge well does not have more attrition (edge={attrition_edge:.4f}, int={attrition_int:.4f})")
        print(f"  This suggests biology is not reading InjectionManager concentrations")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test 2: Evaporation Drift Affects Attrition")
    print("=" * 70)
    print()

    tests = [
        ("Concentration drift (edge vs interior)", test_evaporation_drift_increases_concentration_edge_vs_interior),
        ("Attrition affected by drift", test_evaporation_drift_affects_attrition),
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
