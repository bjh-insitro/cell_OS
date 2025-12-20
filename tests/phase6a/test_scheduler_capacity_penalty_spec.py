"""
Enforcement Test B2: Scheduler Capacity Penalty Spec (xfail)

Specifies future behavior: operations serialize and create handling exposure gradient.

Guards against:
- "Batch everything instantly" exploit
- Unrealistic parallel operations
- Zero-cost liquid handling

THIS TEST IS EXPECTED TO FAIL until Injection B capacity/duration model is implemented.

Future behavior spec:
1. Operations have duration (handling time)
2. Capacity limits force serialization
3. Later operations expose cells longer (outside incubator)
4. Biology reads handling_exposure_h from scheduler metadata
5. Stress penalty proportional to exposure time
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_capacity_serialization_creates_gradient():
    """
    SPEC TEST (expected to fail): 96 operations should serialize and create exposure gradient.

    Setup:
    - Submit 96 TREAT operations at t=0 (one per well in 96-well plate)
    - Each operation has duration = 30s (0.0083h)
    - With capacity=1, operations serialize: well 1 at t=0, well 96 at t=0.8h
    - Verify wells processed later have higher handling_exposure_h
    - Verify biology applies stress penalty proportional to exposure

    Current behavior: All operations execute instantly (no serialization)
    Future behavior: Operations serialize, later wells accumulate handling stress
    """
    print("SPEC TEST: Capacity serialization creates exposure gradient")
    print("-" * 70)
    print("⚠ EXPECTED TO FAIL: Capacity/duration model not implemented")
    print()

    vm = BiologicalVirtualMachine(seed=42)

    # Create 96 wells (8 rows × 12 columns)
    wells = [f"P1_{chr(65+r)}{str(c+1).zfill(2)}" for r in range(8) for c in range(12)]
    print(f"Created {len(wells)} wells")

    # Seed all wells
    for well in wells:
        vm.seed_vessel(well, "A549", initial_count=1e6, initial_viability=1.0)

    # Submit 96 TREAT operations at t=0 with duration=30s
    print(f"\nSubmitting {len(wells)} TREAT operations at t=0...")
    for well in wells:
        vm.scheduler.submit_intent(
            vessel_id=well,
            event_type="TREAT_COMPOUND",
            requested_time_h=0.0,
            payload={"compound": "tunicamycin", "dose_uM": 1.0},
            duration_h=0.0083,  # 30 seconds per operation
            metadata={"operator_id": "OP1"}
        )

    print(f"Pending events: {vm.scheduler.get_pending_count()}")

    # Flush with capacity limit (future: this will serialize)
    print(f"\nFlushing events...")
    vm.scheduler.flush_due_events(now_h=0.0, injection_mgr=vm.injection_mgr)

    # SPEC: Check that wells have different handling_exposure_h
    # In future implementation, scheduler would track:
    # - Well 1: handling_exposure_h = 0.0083 (processed first)
    # - Well 96: handling_exposure_h = 96 * 0.0083 = 0.80h (processed last)

    # For now, check that scheduler has metadata support (even if not enforced yet)
    pending_events = vm.scheduler.get_pending_events()
    if pending_events and hasattr(pending_events[0], 'metadata'):
        print(f"✓ Scheduler supports metadata field (ready for future)")
    else:
        print(f"❌ Scheduler doesn't support metadata (implementation gap)")

    # SPEC: Verify biology can read handling_exposure from metadata
    # Future: biology would read vm.scheduler.get_handling_exposure(vessel_id, now_h)
    # and apply stress penalty: stress_mult = 1.0 + 0.02 * handling_exposure_h

    # SPEC: Verify wells processed later have lower viability (handling stress)
    # For now, all wells have same viability (instant processing)
    viability_first = vm.vessel_states[wells[0]].viability
    viability_last = vm.vessel_states[wells[-1]].viability

    print(f"\nViability comparison (first vs last well):")
    print(f"  Well 1 ({wells[0]}): {viability_first:.6f}")
    print(f"  Well 96 ({wells[-1]}): {viability_last:.6f}")
    print(f"  Difference: {abs(viability_first - viability_last):.6f}")

    # SPEC: Expect viability_last < viability_first (handling stress penalty)
    # Current: viability_first ≈ viability_last (instant processing)
    if abs(viability_first - viability_last) > 0.001:
        print(f"✓ PASS: Handling exposure gradient detected")
        print(f"  (Future implementation working)")
        return True
    else:
        print(f"❌ FAIL (EXPECTED): No handling exposure gradient")
        print(f"  Current: instant processing (no serialization)")
        print(f"  Future: operations serialize, later wells get handling stress")
        raise AssertionError("Capacity/duration model not implemented (expected xfail)")


def test_duration_tracking_in_scheduler():
    """
    SPEC TEST (expected to fail): Scheduler should track operation durations.

    Future behavior:
    - Each event has duration_h field
    - Scheduler computes completion_time_h = scheduled_time_h + duration_h
    - Next operation can't start until previous completes (capacity limit)
    """
    print("\nSPEC TEST: Duration tracking in scheduler")
    print("-" * 70)
    print("⚠ EXPECTED TO FAIL: Duration tracking not enforced")
    print()

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    # Submit two operations with duration
    print("Submitting two operations with 0.5h duration each...")
    ev1 = vm.scheduler.submit_intent(
        vessel_id="P1_A01",
        event_type="TREAT_COMPOUND",
        requested_time_h=0.0,
        payload={"compound": "tunicamycin", "dose_uM": 1.0},
        duration_h=0.5
    )

    ev2 = vm.scheduler.submit_intent(
        vessel_id="P1_A01",
        event_type="FEED_VESSEL",
        requested_time_h=0.0,
        payload={"nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}},
        duration_h=0.5
    )

    print(f"Event 1: scheduled_time={ev1.scheduled_time_h}, duration={ev1.duration_h}")
    print(f"Event 2: scheduled_time={ev2.scheduled_time_h}, duration={ev2.duration_h}")

    # SPEC: With capacity=1, ev2 should be delayed until ev1 completes
    # Expected: ev1 completes at t=0.5h, ev2 starts at t=0.5h, completes at t=1.0h
    # Current: Both execute at t=0 (instant)

    flushed = vm.scheduler.flush_due_events(now_h=0.0, injection_mgr=vm.injection_mgr)
    print(f"\nFlushed {len(flushed)} events at t=0")

    # SPEC: Check if duration is tracked in event metadata
    if hasattr(ev1, 'duration_h') and ev1.duration_h > 0:
        print(f"✓ Duration field present (ev1.duration_h={ev1.duration_h})")
    else:
        print(f"❌ Duration field missing or zero")

    # SPEC: Future scheduler would delay ev2 until ev1.completion_time_h
    # Current: no delay (both execute instantly)
    print(f"\n❌ FAIL (EXPECTED): Duration not enforced in flush")
    print(f"  Current: all events flush instantly")
    print(f"  Future: capacity limits serialize operations")
    raise AssertionError("Duration enforcement not implemented (expected xfail)")


def test_handling_stress_biology_response():
    """
    SPEC TEST (expected to fail): Biology should respond to handling exposure.

    Future behavior:
    - Biology reads handling_exposure_h from scheduler metadata
    - Applies stress penalty: stress_mult = 1.0 + handling_stress_rate * exposure_h
    - Default handling_stress_rate = 0.02 (2% viability loss per hour outside incubator)
    """
    print("\nSPEC TEST: Handling stress biology response")
    print("-" * 70)
    print("⚠ EXPECTED TO FAIL: Handling stress biology not implemented")
    print()

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    # Manually inject handling exposure metadata (simulating future scheduler)
    # In future: scheduler would set this automatically based on serialization
    vm.scheduler.submit_intent(
        vessel_id="P1_B02",
        event_type="TREAT_COMPOUND",
        requested_time_h=0.0,
        payload={"compound": "tunicamycin", "dose_uM": 1.0},
        duration_h=0.0,
        metadata={"handling_exposure_h": 1.0}  # 1 hour outside incubator
    )

    vm.scheduler.flush_due_events(now_h=0.0, injection_mgr=vm.injection_mgr)

    # Mirror for biology compatibility
    vessel = vm.vessel_states["P1_B02"]
    vessel.compounds = vm.injection_mgr.get_all_compounds_uM("P1_B02")

    # SPEC: Biology should read handling_exposure_h and apply stress
    # Expected: viability = 1.0 * (1 - 0.02 * 1.0) = 0.98 (2% penalty for 1h exposure)
    # Current: viability = 1.0 (handling stress not implemented)

    vm.advance_time(0.1)  # Small step to trigger biology update

    viability = vessel.viability
    print(f"\nViability after 1h simulated handling exposure:")
    print(f"  Measured: {viability:.6f}")
    print(f"  Expected (with stress): ~0.98 (2% penalty)")
    print(f"  Current: ~1.0 (no handling stress)")

    if viability < 0.99:
        print(f"✓ PASS: Handling stress penalty detected")
        return True
    else:
        print(f"❌ FAIL (EXPECTED): No handling stress penalty")
        print(f"  Biology doesn't read scheduler metadata yet")
        raise AssertionError("Handling stress biology not implemented (expected xfail)")


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test B2: Scheduler Capacity Penalty Spec (xfail)")
    print("=" * 70)
    print()
    print("⚠ WARNING: ALL TESTS IN THIS FILE ARE EXPECTED TO FAIL")
    print("This file specifies future behavior for Injection B capacity model.")
    print("Tests will pass once duration tracking and handling stress are implemented.")
    print("=" * 70)
    print()

    tests = [
        ("Capacity serialization creates gradient", test_capacity_serialization_creates_gradient),
        ("Duration tracking in scheduler", test_duration_tracking_in_scheduler),
        ("Handling stress biology response", test_handling_stress_biology_response),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except AssertionError as e:
            # Expected failure
            print(f"\n✓ EXPECTED FAILURE: {e}")
            results.append((name, "xfail"))
        except Exception as e:
            print(f"\n❌ UNEXPECTED EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r is True)
    xfailed = sum(1 for _, r in results if r == "xfail")
    failed = sum(1 for _, r in results if r is False)
    total = len(results)

    for name, result in results:
        if result is True:
            status = "✓ PASS"
        elif result == "xfail":
            status = "⚠ XFAIL (expected)"
        else:
            status = "❌ FAIL (unexpected)"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed} passed, {xfailed} expected failures, {failed} unexpected failures")
    print("=" * 70)

    # Exit 0 if all tests are either passing or expected failures
    sys.exit(0 if failed == 0 else 1)
