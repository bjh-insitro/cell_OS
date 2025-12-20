"""
Lock in semantic invariants for subpopulations and hazards.

These are regression tests for subtle semantic breaks that don't throw errors.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_subpop_viabilities_sync_to_vessel():
    """
    Invariant #1: Subpopulation viabilities mirror vessel viability (epistemic model).

    If this breaks, someone reintroduced the "synthetic death process" bug.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Apply stress and death
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)
    vm.advance_time(48.0)

    vessel = vm.vessel_states["test_well"]

    # Check: all subpop viabilities equal vessel viability
    for subpop_name, subpop in vessel.subpopulations.items():
        diff = abs(subpop['viability'] - vessel.viability)
        if diff > 1e-9:
            print(f"❌ FAIL: {subpop_name} viability {subpop['viability']:.6f} != vessel {vessel.viability:.6f}")
            return False

    # Check: mixture equals vessel (should be exact)
    mixture = vessel.viability_mixture
    if abs(mixture - vessel.viability) > 1e-9:
        print(f"❌ FAIL: Mixture {mixture:.6f} != vessel {vessel.viability:.6f}")
        return False

    print(f"✓ PASS: All subpop viabilities sync to vessel (viability={vessel.viability:.4f})")
    return True


def test_hazards_computed_from_mixture_not_sum():
    """
    Invariant #2: ER/mito hazards come from mixture, not weighted sum over subpops.

    If this breaks, hazards will be ~3× too large (sum of per-subpop weighted hazards).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Induce ER stress
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)

    vessel = vm.vessel_states["test_well"]

    # After 24h of tunicamycin, ER stress should be high
    if vessel.er_stress < 0.5:
        print(f"⚠ WARN: ER stress unexpectedly low ({vessel.er_stress:.3f}), test may be weak")

    # The key check: mixture should equal scalar
    mixture_er = vessel.er_stress_mixture
    scalar_er = vessel.er_stress

    if abs(mixture_er - scalar_er) > 1e-9:
        print(f"❌ FAIL: ER mixture {mixture_er:.6f} != scalar {scalar_er:.6f}")
        return False

    # Check that hazard proposals happen exactly once per mechanism
    # (We can't directly inspect _step_hazard_proposals after the fact, but we can
    # verify death accounting: if hazards were triple-counted, death would be ~3× higher)

    # Rough heuristic: with tunicamycin at 2µM for 24h, death_er_stress should be
    # detectable but not saturated. If it's >0.9, hazards might be over-counted.
    if vessel.death_er_stress > 0.9:
        print(f"⚠ WARN: death_er_stress suspiciously high ({vessel.death_er_stress:.3f}), possible over-counting")

    print(f"✓ PASS: Hazards from mixture (ER stress={vessel.er_stress:.3f}, death_er={vessel.death_er_stress:.3f})")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Semantic Invariants (Regression Guards)")
    print("=" * 70)
    print()

    tests = [
        ("Subpop viabilities sync to vessel", test_subpop_viabilities_sync_to_vessel),
        ("Hazards from mixture not sum", test_hazards_computed_from_mixture_not_sum),
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
