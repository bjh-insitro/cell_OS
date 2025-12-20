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
    Test that higher concentration due to evaporation causes proportionally higher death rate.

    Key insight: Check that concentration ratio matches death accumulation ratio,
    accounting for initial viability differences from instant kill variance.

    Setup:
    - Two wells: edge vs interior
    - Same initial dose
    - Advance time (concentrations drift apart due to evaporation)
    - Assert edge death rate is proportionally higher (matches concentration ratio)
    """
    print("\nTest: Evaporation drift affects attrition (biology reads spine)")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=789)

    # Two wells: one edge, one interior
    edge = "Plate1_A01"
    interior = "Plate1_D06"

    vm.seed_vessel(edge, "A549", initial_count=1e6, initial_viability=1.0)
    vm.seed_vessel(interior, "A549", initial_count=1e6, initial_viability=1.0)

    # Same dose at time 0 (moderate dose to see attrition signal)
    vm.treat_with_compound(edge, "tunicamycin", 1.5)
    vm.treat_with_compound(interior, "tunicamycin", 1.5)

    # Record viability after instant kill (will differ due to RNG)
    via_edge_start = vm.vessel_states[edge].viability
    via_int_start = vm.vessel_states[interior].viability

    print(f"After instant kill:")
    print(f"  Edge viability: {via_edge_start:.4f}")
    print(f"  Interior viability: {via_int_start:.4f}")

    # Advance 96 hours (attrition accumulates, concentrations drift)
    print(f"\nAdvancing 96 hours...")
    vm.advance_time(96.0)

    # Read final viabilities
    via_edge_final = vm.vessel_states[edge].viability
    via_int_final = vm.vessel_states[interior].viability

    # Compute survival fraction (relative to post-instant state)
    survival_edge = via_edge_final / max(0.001, via_edge_start)
    survival_int = via_int_final / max(0.001, via_int_start)

    # Read concentrations
    c_edge = vm.injection_mgr.get_compound_concentration_uM(edge, "tunicamycin")
    c_int = vm.injection_mgr.get_compound_concentration_uM(interior, "tunicamycin")

    print(f"\nFinal state (after 96h attrition):")
    print(f"  Edge: viability={via_edge_final:.4f}, survival={survival_edge:.4f}, conc={c_edge:.3f} µM")
    print(f"  Interior: viability={via_int_final:.4f}, survival={survival_int:.4f}, conc={c_int:.3f} µM")
    print(f"  Concentration ratio (edge/int): {c_edge/c_int:.3f}")
    print(f"  Survival ratio (edge/int): {survival_edge/survival_int:.3f}")
    print(f"  (Lower survival = more death from attrition)")

    # Edge should have LOWER survival (more death) due to higher concentration
    # Combined check: concentration ratio > 1.15× AND survival ratio shows effect
    conc_ratio = c_edge / c_int
    survival_ratio = survival_edge / survival_int

    if conc_ratio > 1.15 and survival_ratio < 0.98:
        print(f"✓ PASS: Edge has lower survival matching higher concentration")
        print(f"  Biology reads InjectionManager concentrations (conc_ratio={conc_ratio:.3f}, survival_ratio={survival_ratio:.3f})")
        return True
    elif conc_ratio > 1.15:
        print(f"❌ FAIL: Concentration drifted ({conc_ratio:.3f}×) but survival ratio too high ({survival_ratio:.3f})")
        print(f"  Expected survival_ratio < 0.98, got {survival_ratio:.3f}")
        print(f"  This suggests biology may not be reading InjectionManager concentrations")
        return False
    else:
        print(f"⚠ INCONCLUSIVE: Concentration ratio too small ({conc_ratio:.3f}×) to test reliably")
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
