"""
Enforcement Test B1: Operation Scheduler Order Invariance

Asserts that event submission order doesn't affect final result.

Guards against:
- Ordering ambiguity (first-come-first-serve leaking through)
- Priority policy not working
- Non-deterministic tie-breaking

Tests:
1. Same events, different submission order → identical event log order
2. Final concentrations match exactly (same seed, same events → same outcome)
3. Priority policy enforced (WASHOUT → FEED → TREAT within same timestep)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_order_invariance_priority_policy():
    """
    Test that event submission order doesn't affect final execution order.

    Setup:
    - Submit 3 events at same time but different order:
      Run A: TREAT → FEED → WASHOUT
      Run B: WASHOUT → FEED → TREAT
    - Both should execute in priority order: WASHOUT → FEED → TREAT
    - Verify event logs match exactly
    """
    print("Test: Order invariance with priority policy")
    print("-" * 70)

    # Run A: submit in reverse priority order (TREAT → FEED → WASHOUT)
    print("Run A: Submit TREAT → FEED → WASHOUT (reverse priority)")
    vm_a = BiologicalVirtualMachine(seed=42)
    vm_a.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    # All events at time 0, but submission order reversed
    # These queue without immediate delivery
    vm_a.treat_with_compound("P1_A01", "tunicamycin", 1.0)
    vm_a.feed_vessel("P1_A01", glucose_mM=25.0, glutamine_mM=4.0)
    vm_a.washout_compound("P1_A01", "tunicamycin")

    # Deliver at boundary (priority ordering enforced here)
    vm_a.flush_operations_now()
    vm_a.advance_time(1.0)

    event_log_a = vm_a.injection_mgr.get_event_log()

    # Run B: submit in forward priority order (WASHOUT → FEED → TREAT)
    print("\nRun B: Submit WASHOUT → FEED → TREAT (forward priority)")
    vm_b = BiologicalVirtualMachine(seed=42)
    vm_b.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    # Same events, different submission order
    # These queue without immediate delivery
    vm_b.washout_compound("P1_A01", "tunicamycin")
    vm_b.feed_vessel("P1_A01", glucose_mM=25.0, glutamine_mM=4.0)
    vm_b.treat_with_compound("P1_A01", "tunicamycin", 1.0)

    # Deliver at boundary (priority ordering enforced here)
    vm_b.flush_operations_now()
    vm_b.advance_time(1.0)

    event_log_b = vm_b.injection_mgr.get_event_log()

    print(f"\nEvent log comparison:")
    print(f"  Run A events: {len(event_log_a)}")
    print(f"  Run B events: {len(event_log_b)}")

    # Event logs should have same length
    if len(event_log_a) != len(event_log_b):
        print(f"❌ FAIL: Event log length mismatch ({len(event_log_a)} vs {len(event_log_b)})")
        return False

    # Event logs should match exactly (same order)
    mismatches = []
    for i, (evt_a, evt_b) in enumerate(zip(event_log_a, event_log_b)):
        if evt_a['event_type'] != evt_b['event_type']:
            mismatches.append(f"  Event {i}: {evt_a['event_type']} vs {evt_b['event_type']}")

    if mismatches:
        print(f"❌ FAIL: Event order mismatch:")
        for m in mismatches:
            print(m)
        return False

    # Verify final concentrations match
    c_a = vm_a.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")
    c_b = vm_b.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")

    print(f"\nFinal concentrations:")
    print(f"  Run A: {c_a:.6f} µM")
    print(f"  Run B: {c_b:.6f} µM")
    print(f"  Difference: {abs(c_a - c_b):.9f}")

    if abs(c_a - c_b) > 1e-9:
        print(f"❌ FAIL: Final concentrations differ (c_a={c_a}, c_b={c_b})")
        return False

    print(f"✓ PASS: Event logs and final concentrations match exactly")
    print(f"  Order invariance verified (submission order doesn't matter)")
    return True


def test_priority_policy_execution_order():
    """
    Test that priority policy is enforced: WASHOUT(10) → FEED(20) → TREAT(30).

    Setup:
    - Submit events in random order at same time
    - Verify execution order matches priority (lower priority executes first)
    """
    print("\nTest: Priority policy execution order")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    # Establish baseline compound (must flush AND step to mirror into VesselState)
    vm.treat_with_compound("P1_B02", "tunicamycin", 2.0)
    vm.flush_operations_now()
    vm.advance_time(0.0)  # Trigger mirroring without advancing time

    # Submit in chaotic order (these queue without immediate delivery)
    print("Submitting events in order: TREAT → WASHOUT → FEED")
    vm.treat_with_compound("P1_B02", "staurosporine", 0.5)  # Different compound
    vm.washout_compound("P1_B02", "tunicamycin")  # Washout existing compound
    vm.feed_vessel("P1_B02", glucose_mM=25.0, glutamine_mM=4.0)

    # Deliver at boundary (priority ordering enforced)
    vm.flush_operations_now()
    vm.advance_time(1.0)

    event_log = vm.injection_mgr.get_event_log()

    # Filter to just the 3 events in the chaotic batch (after baseline establishment)
    # Event log has: SEED, TREAT (baseline), then TREAT/WASHOUT/FEED (batch)
    ops_events = event_log[2:]  # Skip SEED and baseline TREAT

    print(f"\nExecution order (chaotic batch):")
    for i, evt in enumerate(ops_events):
        print(f"  {i+1}. {evt['event_type']}")

    # Expected order: WASHOUT → FEED → TREAT (priority ordering)
    expected_order = ['WASHOUT_COMPOUND', 'FEED_VESSEL', 'TREAT_COMPOUND']
    actual_order = [e['event_type'] for e in ops_events]

    if actual_order == expected_order:
        print(f"✓ PASS: Priority policy enforced (WASHOUT → FEED → TREAT)")
        return True
    else:
        print(f"❌ FAIL: Priority policy violated")
        print(f"  Expected: {expected_order}")
        print(f"  Actual: {actual_order}")
        return False


def test_event_id_stable_tiebreaker():
    """
    Test that event_id provides stable tie-breaking when time and priority match.

    Setup:
    - Submit multiple TREAT events at same time (same priority)
    - Verify they execute in submission order (event_id ascending)
    """
    print("\nTest: event_id stable tie-breaker")
    print("-" * 70)

    # Run A: submit compounds in order A → B → C
    print("Run A: Submit compounds in order A → B → C")
    vm_a = BiologicalVirtualMachine(seed=999)
    vm_a.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    vm_a.treat_with_compound("P1_C03", "staurosporine", 0.1)
    vm_a.treat_with_compound("P1_C03", "tunicamycin", 0.5)
    vm_a.treat_with_compound("P1_C03", "nocodazole", 0.2)

    # Deliver at boundary
    vm_a.flush_operations_now()
    vm_a.advance_time(1.0)

    log_a = vm_a.injection_mgr.get_event_log()
    treat_events_a = [e for e in log_a if e['event_type'] == 'TREAT_COMPOUND']
    compounds_a = [e['payload']['compound'] for e in treat_events_a]

    # Run B: submit compounds in reverse order C → B → A
    print("\nRun B: Submit compounds in reverse order C → B → A")
    vm_b = BiologicalVirtualMachine(seed=999)
    vm_b.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    vm_b.treat_with_compound("P1_C03", "nocodazole", 0.2)
    vm_b.treat_with_compound("P1_C03", "tunicamycin", 0.5)
    vm_b.treat_with_compound("P1_C03", "staurosporine", 0.1)

    # Deliver at boundary
    vm_b.flush_operations_now()
    vm_b.advance_time(1.0)

    log_b = vm_b.injection_mgr.get_event_log()
    treat_events_b = [e for e in log_b if e['event_type'] == 'TREAT_COMPOUND']
    compounds_b = [e['payload']['compound'] for e in treat_events_b]

    print(f"\nExecution order comparison:")
    print(f"  Run A: {compounds_a}")
    print(f"  Run B: {compounds_b}")

    # Order should reflect submission order (event_id tie-breaker)
    # Run A should be [stauro, tunica, nocoda], Run B should be [nocoda, tunica, stauro]
    if compounds_a == ['staurosporine', 'tunicamycin', 'nocodazole'] and \
       compounds_b == ['nocodazole', 'tunicamycin', 'staurosporine']:
        print(f"✓ PASS: event_id provides stable tie-breaking (submission order preserved)")
        return True
    else:
        print(f"❌ FAIL: event_id tie-breaking not working as expected")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test B1: Operation Scheduler Order Invariance")
    print("=" * 70)
    print()

    tests = [
        ("Order invariance with priority policy", test_order_invariance_priority_policy),
        ("Priority policy execution order", test_priority_policy_execution_order),
        ("event_id stable tie-breaker", test_event_id_stable_tiebreaker),
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
