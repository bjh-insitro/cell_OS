"""
Enforcement Test: Treatment Causality (No Paradox)

Guards against:
- Instant kill happening before exposure exists in authoritative spine
- Death from compound that doesn't exist yet (temporal paradox)
- Causality violations between operations and effects

Critical property:
- When instant kill happens, compound must already exist in InjectionManager
- Exposure delivery must precede instant effect (causal consistency)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_treatment_causality_instant_kill_after_exposure():
    """
    Test that instant kill happens AFTER compound exists in spine.

    Setup:
    - Seed vessel
    - Call treat_with_compound (which does instant kill)
    - Verify compound exists in InjectionManager when viability changed

    If causality is violated, viability changes but compound doesn't exist yet.
    """
    print("Test: Instant kill happens after exposure delivery")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_A01"]
    viability_before = vessel.viability

    print(f"Before treatment: viability={viability_before:.4f}")

    # Call treat_with_compound (should deliver exposure THEN instant kill)
    result = vm.treat_with_compound("P1_A01", "tunicamycin", 2.0)

    viability_after = vessel.viability
    compound_in_spine = vm.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")
    compound_in_vessel = vessel.compounds.get("tunicamycin", 0.0)

    print(f"After treatment:")
    print(f"  Viability: {viability_after:.4f}")
    print(f"  Compound (spine): {compound_in_spine:.3f} µM")
    print(f"  Compound (vessel): {compound_in_vessel:.3f} µM")

    # Verify causality: if viability changed, compound must exist
    viability_changed = abs(viability_after - viability_before) > 1e-6

    if viability_changed:
        if compound_in_spine > 0 and compound_in_vessel > 0:
            print(f"✓ PASS: Compound exists in spine when instant kill happened")
            print(f"  Causality maintained: exposure → instant effect")
            return True
        else:
            print(f"❌ FAIL: Viability changed but compound doesn't exist")
            print(f"  Causality violation: instant kill before exposure delivery")
            return False
    else:
        # No instant kill happened (dose too low), but compound should still exist
        if compound_in_spine > 0:
            print(f"✓ PASS: No instant kill, but compound exists in spine")
            return True
        else:
            print(f"❌ FAIL: Compound missing from spine after treatment")
            return False


def test_treatment_timeline_consistency():
    """
    Test that exposure timeline is consistent with death timeline.

    Setup:
    - Seed vessel at t=0
    - Treat at t=0
    - Verify death_compound and compound exposure both exist at t=0

    If timeline is inconsistent, death happens at t=0 but exposure appears later.
    """
    print("\nTest: Treatment timeline consistency")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_B02"]

    # Record initial state
    death_compound_before = vessel.death_compound
    t0 = vm.simulated_time

    print(f"t={t0:.1f}: Before treatment")
    print(f"  death_compound: {death_compound_before:.6f}")

    # Treat (should deliver exposure + instant kill at same moment)
    vm.treat_with_compound("P1_B02", "tunicamycin", 3.0)

    # Check state immediately after treatment (still at t=0)
    death_compound_after = vessel.death_compound
    compound_in_spine = vm.injection_mgr.get_compound_concentration_uM("P1_B02", "tunicamycin")
    compound_start_time = vessel.compound_start_time.get("tunicamycin", None)
    t_after = vm.simulated_time

    print(f"t={t_after:.1f}: After treatment")
    print(f"  death_compound: {death_compound_after:.6f}")
    print(f"  compound (spine): {compound_in_spine:.3f} µM")
    print(f"  compound_start_time: {compound_start_time:.1f}")

    # Verify timeline consistency
    death_happened = death_compound_after > death_compound_before
    exposure_exists = compound_in_spine > 0
    timeline_consistent = (compound_start_time == t0) if compound_start_time is not None else False

    if death_happened and exposure_exists and timeline_consistent:
        print(f"✓ PASS: Death and exposure both happened at t={t0:.1f}")
        print(f"  Timeline is consistent: no temporal paradox")
        return True
    else:
        print(f"❌ FAIL: Timeline inconsistency detected")
        if death_happened and not exposure_exists:
            print(f"  Death happened but exposure missing (causality violation)")
        if exposure_exists and not timeline_consistent:
            print(f"  Exposure timeline mismatch (start_time != simulated_time)")
        return False


def test_exposure_state_never_disagrees_with_death():
    """
    Test that exposure state and death state never disagree.

    Setup:
    - Seed vessel
    - Treat with compound
    - Inspect state at multiple points (before advance, after advance)
    - Verify: if death_compound > 0, then compound exists in spine

    If states disagree, we have a causality or consistency bug.
    """
    print("\nTest: Exposure and death state always agree")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_C03"]

    # Treat
    vm.treat_with_compound("P1_C03", "staurosporine", 0.1)

    # Check immediately after treatment
    death_compound = vessel.death_compound
    compound_in_spine = vm.injection_mgr.get_compound_concentration_uM("P1_C03", "staurosporine")

    print(f"After treatment (before advance):")
    print(f"  death_compound: {death_compound:.6f}")
    print(f"  compound (spine): {compound_in_spine:.6f} µM")

    if death_compound > 0 and compound_in_spine == 0:
        print(f"❌ FAIL: Death without exposure (immediate check)")
        return False

    # Advance time
    vm.advance_time(12.0)

    death_compound_after = vessel.death_compound
    compound_in_spine_after = vm.injection_mgr.get_compound_concentration_uM("P1_C03", "staurosporine")

    print(f"\nAfter advance_time(12h):")
    print(f"  death_compound: {death_compound_after:.6f}")
    print(f"  compound (spine): {compound_in_spine_after:.6f} µM")

    # Death can only exist if exposure exists or existed
    if death_compound_after > 0 and compound_in_spine_after == 0:
        # This is actually okay if compound was present then washed out
        # But for this test, we never washed out, so it should still be present
        print(f"❌ FAIL: Death persists but exposure vanished (should not happen without washout)")
        return False

    print(f"✓ PASS: Exposure and death states always consistent")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test: Treatment Causality")
    print("=" * 70)
    print()

    tests = [
        ("Instant kill after exposure delivery", test_treatment_causality_instant_kill_after_exposure),
        ("Treatment timeline consistency", test_treatment_timeline_consistency),
        ("Exposure and death state agreement", test_exposure_state_never_disagrees_with_death),
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
