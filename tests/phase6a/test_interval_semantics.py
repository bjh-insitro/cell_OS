"""
Enforcement Test: Interval Semantics (Events Affect Their Interval)

Guards against:
- Events scheduled at t0 not affecting physics over [t0, t0+dt)
- Unclear interval boundaries (closed vs half-open)
- Physics running with wrong concentrations

Critical property:
- If you treat at t=0 and advance_time(12), the compound must be present
  during attrition/latent induction over [0, 12), not "appear after the fact"
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_events_affect_their_interval():
    """
    Test that events scheduled at t0 affect physics over [t0, t0+dt).

    Setup:
    - Seed vessel at t=0
    - Treat with ER-stress compound at t=0
    - Advance time by 24h
    - Verify ER stress accumulated during the interval (not after)

    If interval semantics are wrong, ER stress would be 0 because compound
    would be "delivered after" the 24h interval completes.
    """
    print("Test: Events affect their interval (left-closed [t0, t0+dt))")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    print(f"t=0: Seeded vessel")

    # Schedule compound treatment at t=0
    print(f"t=0: Scheduling tunicamycin treatment (ER stress axis)")
    vm.treat_with_compound("P1_A01", "tunicamycin", 1.5)

    # Advance time by 24h
    # With correct semantics: compound delivered at t=0, affects [0, 24)
    # With broken semantics: compound delivered at t=24, affects [24, ...]
    print(f"\nAdvancing 24 hours...")
    vm.advance_time(24.0)

    vessel = vm.vessel_states["P1_A01"]
    er_stress = vessel.er_stress
    death_er = vessel.death_er_stress
    viability = vessel.viability

    print(f"\nState after 24h:")
    print(f"  ER stress: {er_stress:.4f}")
    print(f"  Death (ER): {death_er:.4f}")
    print(f"  Viability: {viability:.4f}")

    # With correct interval semantics, ER stress should accumulate
    # Tunicamycin at 1.5µM for 24h should induce significant ER stress
    if er_stress > 0.5:
        print(f"✓ PASS: ER stress accumulated during interval ({er_stress:.4f})")
        print(f"  Compound was present during [0, 24) as expected")
        return True
    else:
        print(f"❌ FAIL: ER stress too low ({er_stress:.4f})")
        print(f"  Expected > 0.5 after 24h exposure to 1.5µM tunicamycin")
        print(f"  This suggests event was delivered AFTER the interval, not before")
        return False


def test_attrition_uses_delivered_concentration():
    """
    Test that attrition (death) uses compound concentration delivered at interval start.

    Setup:
    - Seed vessel at t=0
    - Treat with high-dose compound at t=0
    - Advance time by 48h
    - Verify significant death from compound attrition

    If compound isn't delivered before physics, attrition won't see it.
    """
    print("\nTest: Attrition uses delivered concentration")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    print(f"t=0: Seeded vessel")

    # High dose for significant attrition
    print(f"t=0: Scheduling high-dose tunicamycin treatment")
    vm.treat_with_compound("P1_B02", "tunicamycin", 3.0)

    # Record state after instant kill
    vessel = vm.vessel_states["P1_B02"]
    viability_after_instant = vessel.viability
    print(f"\nViability after instant kill: {viability_after_instant:.4f}")

    # Advance time (attrition accumulates if compound is present)
    print(f"\nAdvancing 48 hours...")
    vm.advance_time(48.0)

    viability_final = vessel.viability
    death_compound = vessel.death_compound
    survival_ratio = viability_final / viability_after_instant

    print(f"\nFinal state after 48h:")
    print(f"  Viability: {viability_final:.4f}")
    print(f"  Death (compound total): {death_compound:.4f}")
    print(f"  Survival ratio: {survival_ratio:.4f}")

    # With correct interval semantics, attrition should cause additional death
    # Survival ratio < 0.95 indicates attrition happened
    if survival_ratio < 0.95:
        print(f"✓ PASS: Attrition occurred during interval (survival={survival_ratio:.4f})")
        print(f"  Compound concentration was used by biology during [0, 48)")
        return True
    else:
        print(f"❌ FAIL: No significant attrition (survival={survival_ratio:.4f})")
        print(f"  Expected survival < 0.95 from high-dose compound")
        print(f"  This suggests biology didn't see compound during interval")
        return False


def test_multiple_events_at_same_time():
    """
    Test that multiple events scheduled at t0 all affect the same interval.

    Setup:
    - Seed vessel
    - Schedule TREAT at t=0
    - Schedule FEED at t=0
    - Advance time
    - Verify both events affected the interval

    This tests priority ordering + interval semantics together.
    """
    print("\nTest: Multiple events at same time affect interval")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    print(f"t=0: Seeded vessel")

    # Schedule two operations at t=0 in reverse priority order
    print(f"t=0: Scheduling TREAT (priority=30)")
    vm.treat_with_compound("P1_C03", "tunicamycin", 1.0)

    print(f"t=0: Scheduling FEED (priority=20)")
    vm.feed_vessel("P1_C03", glucose_mM=30.0, glutamine_mM=5.0)

    # Advance time
    print(f"\nAdvancing 12 hours...")
    vm.advance_time(12.0)

    vessel = vm.vessel_states["P1_C03"]
    glucose = vessel.media_glucose_mM
    compound_conc = vm.injection_mgr.get_compound_concentration_uM("P1_C03", "tunicamycin")

    print(f"\nState after 12h:")
    print(f"  Glucose: {glucose:.2f} mM")
    print(f"  Compound: {compound_conc:.3f} µM")

    # Both events should have been delivered at t=0
    # Feed should have refreshed glucose to 30.0 (then depleted a bit)
    # Treat should have set compound to 1.0 (then concentrated by evaporation)
    if glucose > 29.0 and compound_conc > 0.95:
        print(f"✓ PASS: Both events affected interval [0, 12)")
        print(f"  FEED refreshed glucose, TREAT added compound")
        print(f"  Priority ordering worked (FEED before TREAT)")
        return True
    else:
        print(f"❌ FAIL: Events didn't both affect interval")
        print(f"  Expected glucose > 29, compound > 0.95")
        print(f"  Got glucose={glucose:.2f}, compound={compound_conc:.3f}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test: Interval Semantics")
    print("=" * 70)
    print()

    tests = [
        ("Events affect their interval", test_events_affect_their_interval),
        ("Attrition uses delivered concentration", test_attrition_uses_delivered_concentration),
        ("Multiple events at same time", test_multiple_events_at_same_time),
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
