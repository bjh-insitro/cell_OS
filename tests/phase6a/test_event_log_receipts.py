"""
Enforcement Test B3: Event Log Receipts (Debugging Time Machine)

Tests that InjectionManager maintains a complete, ordered event log
suitable for forensics and decision receipts.

Assertions:
- Event sequence is recorded in order
- Events have monotonic sequence numbers
- Per-event affected vessels are recorded
- Timestamps are consistent
- Event log is replayable (schema-valid throughout)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_event_log_receipts():
    """
    Run protocol and verify event log captures all operations.
    """
    print("=" * 70)
    print("Enforcement Test B3: Event Log Receipts")
    print("=" * 70)
    print()

    vm = BiologicalVirtualMachine(seed=42)

    vessel1 = "Plate1_A01"
    vessel2 = "Plate1_B02"

    # Run protocol that generates events
    print("Running Protocol...")
    print("-" * 70)

    vm.seed_vessel(vessel1, "A549", initial_count=1e6)
    print(f"1. seed_vessel({vessel1})")

    vm.seed_vessel(vessel2, "A549", initial_count=1e6)
    print(f"2. seed_vessel({vessel2})")

    vm.treat_with_compound(vessel1, "tunicamycin", 1.0)
    print(f"3. treat_with_compound({vessel1}, tunicamycin, 1.0)")

    vm.treat_with_compound(vessel2, "staurosporine", 0.5)
    print(f"4. treat_with_compound({vessel2}, staurosporine, 0.5)")

    vm.feed_vessel(vessel1, glucose_mM=25.0, glutamine_mM=4.0)
    print(f"5. feed_vessel({vessel1})")

    vm.washout_compound(vessel2, "staurosporine")
    print(f"6. washout_compound({vessel2}, staurosporine)")

    print()

    # ========== Retrieve Event Log ==========
    print("Retrieving Event Log...")
    print("-" * 70)

    event_log = vm.injection_mgr.get_event_log()

    print(f"Total events logged: {len(event_log)}")
    print()

    # ========== Assert Event Sequence ==========
    print("Assertion 1: Event Sequence Recorded")
    print("-" * 70)

    expected_sequence = [
        ("SEED_VESSEL", vessel1),
        ("SEED_VESSEL", vessel2),
        ("TREAT_COMPOUND", vessel1),
        ("TREAT_COMPOUND", vessel2),
        ("FEED_VESSEL", vessel1),
        ("WASHOUT_COMPOUND", vessel2),
    ]

    violations = []

    if len(event_log) != len(expected_sequence):
        violations.append(f"Event count mismatch: expected {len(expected_sequence)}, got {len(event_log)}")

    for i, (expected_type, expected_vessel) in enumerate(expected_sequence):
        if i >= len(event_log):
            violations.append(f"Event {i}: missing (expected {expected_type})")
            continue

        event = event_log[i]
        actual_type = event.get("event_type")
        actual_vessel = event.get("vessel_id")

        if actual_type != expected_type:
            violations.append(f"Event {i}: type mismatch (expected {expected_type}, got {actual_type})")
        if actual_vessel != expected_vessel:
            violations.append(f"Event {i}: vessel mismatch (expected {expected_vessel}, got {actual_vessel})")

        print(f"  {i}. {actual_type:20s} vessel={actual_vessel:15s} ✓")

    print()

    # ========== Assert Monotonic Sequence Numbers ==========
    print("Assertion 2: Monotonic Sequence Numbers")
    print("-" * 70)

    for i, event in enumerate(event_log):
        seq = event.get("_seq")
        if seq != i:
            violations.append(f"Event {i}: sequence number mismatch (expected {i}, got {seq})")

    print(f"  Sequence numbers: {[e.get('_seq') for e in event_log]}")
    if not violations:
        print(f"  ✓ All sequence numbers monotonic")
    print()

    # ========== Assert Timestamps Consistent ==========
    print("Assertion 3: Timestamps Consistent")
    print("-" * 70)

    for i, event in enumerate(event_log):
        time_h = event.get("time_h")
        if time_h is None:
            violations.append(f"Event {i}: missing time_h")
        elif time_h < 0:
            violations.append(f"Event {i}: negative time_h ({time_h})")

    print(f"  Timestamps: {[e.get('time_h') for e in event_log]}")
    if not violations:
        print(f"  ✓ All timestamps >= 0")
    print()

    # ========== Assert Event Schema Valid (Replayable) ==========
    print("Assertion 4: Events Are Replayable (Schema Valid)")
    print("-" * 70)

    for i, event in enumerate(event_log):
        try:
            # Schema validation happens during add_event, but double-check
            vm.injection_mgr.validate_event(event)
        except Exception as e:
            violations.append(f"Event {i}: schema invalid ({e})")

    if not violations:
        print(f"  ✓ All {len(event_log)} events pass schema validation")
    print()

    # ========== Assert Payload Completeness ==========
    print("Assertion 5: Payload Completeness")
    print("-" * 70)

    # Check specific payloads
    # Event 2: TREAT_COMPOUND vessel1 should have compound="tunicamycin", dose_uM=1.0
    event_treat_v1 = event_log[2]
    payload = event_treat_v1.get("payload", {})
    if payload.get("compound") != "tunicamycin":
        violations.append(f"Event 2: compound mismatch (expected tunicamycin, got {payload.get('compound')})")
    if abs(payload.get("dose_uM", 0) - 1.0) > 1e-6:
        violations.append(f"Event 2: dose mismatch (expected 1.0, got {payload.get('dose_uM')})")

    # Event 4: FEED_VESSEL vessel1 should have nutrients payload
    event_feed = event_log[4]
    payload_feed = event_feed.get("payload", {})
    nutrients = payload_feed.get("nutrients_mM", {})
    if abs(nutrients.get("glucose", 0) - 25.0) > 0.1:
        violations.append(f"Event 4: glucose mismatch (expected 25.0, got {nutrients.get('glucose')})")

    print(f"  Event 2 payload: {event_treat_v1.get('payload')}")
    print(f"  Event 4 payload: {event_feed.get('payload')}")
    if not violations:
        print(f"  ✓ Payload contents match protocol")
    print()

    # ========== Summary ==========
    print("=" * 70)
    print("Summary: Event Log Receipts")
    print("=" * 70)

    if violations:
        print(f"❌ FAIL: {len(violations)} violation(s) detected")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print("✓ PASS: Event log is complete and replayable")
        print("  - Event sequence recorded in order")
        print("  - Sequence numbers monotonic")
        print("  - Timestamps consistent")
        print("  - All events schema-valid")
        print("  - Payloads complete")
        print()
        print("The event log is a debugging time machine.")
        return True


if __name__ == "__main__":
    success = test_event_log_receipts()
    sys.exit(0 if success else 1)
