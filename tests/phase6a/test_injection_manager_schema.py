"""
Enforcement Test 1: Intent Mismatch (Schema Strictness)

Asserts that InjectionManager rejects payloads that don't match event_type.

Guards against:
- Accidentally mixing event payloads (FEED with compound, TREAT with nutrients)
- Silent schema errors that lead to undefined behavior
- Parallel truth sources (intent vs reality)
"""

import sys
from src.cell_os.hardware.injection_manager import InjectionManager, InjectionSchemaError


def test_injection_schema_feed_with_compound_rejected():
    """
    Test that FEED_VESSEL with compound payload is rejected.

    This prevents accidentally treating feed as dose.
    """
    mgr = InjectionManager(is_edge_well_fn=lambda _: False)

    # Seed ok
    mgr.add_event({
        "event_type": "SEED_VESSEL",
        "time_h": 0.0,
        "vessel_id": "Plate1_B02",
        "payload": {"initial_nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}}
    })

    # Wrong payload for FEED_VESSEL (has compound fields)
    try:
        mgr.add_event({
            "event_type": "FEED_VESSEL",
            "time_h": 1.0,
            "vessel_id": "Plate1_B02",
            "payload": {"compound": "tunicamycin", "dose_uM": 0.8}  # INVALID
        })
        print("❌ FAIL: FEED_VESSEL with compound payload was accepted (should reject)")
        return False
    except InjectionSchemaError as e:
        print(f"✓ PASS: FEED_VESSEL with compound payload rejected: {e}")
        return True


def test_injection_schema_treat_with_nutrients_rejected():
    """
    Test that TREAT_COMPOUND with nutrients payload is rejected.

    This prevents accidentally treating dose as feed.
    """
    mgr = InjectionManager(is_edge_well_fn=lambda _: False)

    # Seed ok
    mgr.add_event({
        "event_type": "SEED_VESSEL",
        "time_h": 0.0,
        "vessel_id": "Plate1_B03",
        "payload": {"initial_nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}}
    })

    # Wrong payload for TREAT_COMPOUND (has nutrient fields)
    try:
        mgr.add_event({
            "event_type": "TREAT_COMPOUND",
            "time_h": 1.0,
            "vessel_id": "Plate1_B03",
            "payload": {"nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}}  # INVALID
        })
        print("❌ FAIL: TREAT_COMPOUND with nutrients payload was accepted (should reject)")
        return False
    except InjectionSchemaError as e:
        print(f"✓ PASS: TREAT_COMPOUND with nutrients payload rejected: {e}")
        return True


def test_injection_schema_missing_required_fields():
    """
    Test that events with missing required fields are rejected.
    """
    mgr = InjectionManager(is_edge_well_fn=lambda _: False)

    # Missing payload
    try:
        mgr.add_event({
            "event_type": "SEED_VESSEL",
            "time_h": 0.0,
            "vessel_id": "Plate1_B04",
            # Missing "payload"
        })
        print("❌ FAIL: Event with missing payload was accepted")
        return False
    except InjectionSchemaError as e:
        print(f"✓ PASS: Event with missing payload rejected: {e}")
        return True


def test_injection_schema_valid_sequence():
    """
    Test that valid event sequence passes.

    This ensures schema validation doesn't reject valid events.
    """
    mgr = InjectionManager(is_edge_well_fn=lambda _: False)

    try:
        # Seed
        mgr.add_event({
            "event_type": "SEED_VESSEL",
            "time_h": 0.0,
            "vessel_id": "Plate1_C05",
            "payload": {"initial_nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}}
        })

        # Treat
        mgr.add_event({
            "event_type": "TREAT_COMPOUND",
            "time_h": 12.0,
            "vessel_id": "Plate1_C05",
            "payload": {"compound": "tunicamycin", "dose_uM": 0.8}
        })

        # Feed
        mgr.add_event({
            "event_type": "FEED_VESSEL",
            "time_h": 24.0,
            "vessel_id": "Plate1_C05",
            "payload": {"nutrients_mM": {"glucose": 25.0, "glutamine": 4.0}}
        })

        # Washout
        mgr.add_event({
            "event_type": "WASHOUT_COMPOUND",
            "time_h": 36.0,
            "vessel_id": "Plate1_C05",
            "payload": {"compound": "tunicamycin"}
        })

        print("✓ PASS: Valid event sequence accepted")
        return True

    except InjectionSchemaError as e:
        print(f"❌ FAIL: Valid event sequence rejected: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test 1: InjectionManager Schema Validation")
    print("=" * 70)
    print()

    tests = [
        ("FEED with compound rejected", test_injection_schema_feed_with_compound_rejected),
        ("TREAT with nutrients rejected", test_injection_schema_treat_with_nutrients_rejected),
        ("Missing required fields rejected", test_injection_schema_missing_required_fields),
        ("Valid sequence accepted", test_injection_schema_valid_sequence),
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
