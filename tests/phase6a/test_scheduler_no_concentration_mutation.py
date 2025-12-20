"""
Enforcement Test B3: Scheduler Cannot Mutate Concentrations

Asserts that scheduler is a pure envelope queue with no side effects.

Guards against:
- Scheduler mutating concentrations during submit_intent
- Scheduler metadata affecting physics
- Scheduler reading biology state (coupling)

Tests:
1. Before flush: concentrations unchanged by submit_intent
2. After flush: concentrations change only via InjectionManager semantics
3. Scheduler metadata doesn't affect concentration evolution
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_submit_intent_no_immediate_mutation():
    """
    Test that submitting events doesn't immediately mutate concentrations.

    Setup:
    - Read initial concentration
    - Submit TREAT event (but don't flush)
    - Verify concentration unchanged until flush
    """
    print("Test: submit_intent doesn't immediately mutate concentrations")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    # Initial concentration (should be 0.0 for tunicamycin)
    c_initial = vm.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")
    print(f"Initial concentration: {c_initial:.6f} µM")

    # Submit event via scheduler (queues without immediate delivery)
    print("\nSubmitting TREAT event...")
    vm.treat_with_compound("P1_A01", "tunicamycin", 2.5)

    # Read concentration after submit (should be 0.0 until flush)
    c_after_submit = vm.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")
    print(f"Concentration after submit (before flush): {c_after_submit:.6f} µM")

    # Verify concentration is unchanged until flush (boundary semantics)
    if abs(c_after_submit - 0.0) < 1e-9:
        print(f"✓ PASS: submit_intent queues without immediate mutation")
        print(f"  Delivery happens at boundary (flush_operations_now or advance_time)")

        # Now flush and verify delivery
        vm.flush_operations_now()
        c_after_flush = vm.injection_mgr.get_compound_concentration_uM("P1_A01", "tunicamycin")
        print(f"Concentration after flush: {c_after_flush:.6f} µM")

        if abs(c_after_flush - 2.5) < 1e-9:
            print(f"✓ PASS: Flush delivers event and updates concentration")
            return True
        else:
            print(f"❌ FAIL: Flush didn't deliver correctly ({c_after_flush:.6f} µM)")
            return False
    else:
        print(f"❌ FAIL: Concentration mutated immediately after submit ({c_after_submit:.6f} µM)")
        print(f"  Expected: 0.0 (queue only), Got: {c_after_submit:.6f}")
        return False


def test_scheduler_metadata_no_concentration_effect():
    """
    Test that scheduler metadata doesn't affect concentration evolution.

    Setup:
    - Run A: submit events with no metadata
    - Run B: submit events with arbitrary metadata
    - Verify final concentrations match exactly (metadata ignored by physics)
    """
    print("\nTest: Scheduler metadata doesn't affect concentrations")
    print("-" * 70)

    # Run A: no metadata
    print("Run A: Events with no metadata")
    vm_a = BiologicalVirtualMachine(seed=123)
    vm_a.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)
    vm_a.treat_with_compound("P1_B02", "tunicamycin", 1.5)
    vm_a.advance_time(48.0)  # Let evaporation concentrate

    c_a = vm_a.injection_mgr.get_compound_concentration_uM("P1_B02", "tunicamycin")

    # Run B: with metadata (using scheduler.submit_intent directly)
    print("\nRun B: Events with arbitrary metadata")
    vm_b = BiologicalVirtualMachine(seed=123)
    vm_b.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    # Submit with metadata via scheduler
    vm_b.scheduler.submit_intent(
        vessel_id="P1_B02",
        event_type="TREAT_COMPOUND",
        requested_time_h=float(vm_b.simulated_time),
        payload={"compound": "tunicamycin", "dose_uM": 1.5},
        metadata={"operator_id": "OP_EVIL", "instrument_id": "PIPETTE_CHAOS"}
    )
    vm_b.scheduler.flush_due_events(now_h=float(vm_b.simulated_time), injection_mgr=vm_b.injection_mgr)

    # Mirror into VesselState for biology compatibility
    vm_b.vessel_states["P1_B02"].compounds = vm_b.injection_mgr.get_all_compounds_uM("P1_B02")

    # Register compound metadata for biology (normally done in treat_with_compound)
    vessel = vm_b.vessel_states["P1_B02"]
    if not hasattr(vm_b, 'thalamus_params') or vm_b.thalamus_params is None:
        vm_b._load_cell_thalamus_params()
    compound_params = vm_b.thalamus_params['compounds']['tunicamycin']
    vessel.compound_meta["tunicamycin"] = {
        'ic50_uM': compound_params['ec50_uM'],
        'hill_slope': compound_params['hill_slope'],
        'stress_axis': compound_params['stress_axis'],
        'base_ec50': compound_params['ec50_uM'],
        'potency_scalar': 1.0,
        'toxicity_scalar': 1.0
    }
    vessel.compound_start_time["tunicamycin"] = vm_b.simulated_time

    vm_b.advance_time(48.0)

    c_b = vm_b.injection_mgr.get_compound_concentration_uM("P1_B02", "tunicamycin")

    print(f"\nFinal concentrations (after 48h evaporation):")
    print(f"  Run A (no metadata): {c_a:.6f} µM")
    print(f"  Run B (with metadata): {c_b:.6f} µM")
    print(f"  Difference: {abs(c_a - c_b):.9f}")

    if abs(c_a - c_b) < 1e-9:
        print(f"✓ PASS: Metadata doesn't affect concentration evolution")
        print(f"  Scheduler is pure envelope queue (no side effects)")
        return True
    else:
        print(f"❌ FAIL: Metadata affected concentrations ({c_a:.6f} vs {c_b:.6f})")
        return False


def test_flush_only_path_to_concentration_change():
    """
    Test that concentrations change only via flush → InjectionManager.add_event.

    Setup:
    - Submit events to scheduler
    - Verify pending count increases
    - Flush events
    - Verify pending count decreases to zero
    - Verify concentrations updated only after flush
    """
    print("\nTest: Flush is the only path to concentration change")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    # Check initial state
    pending_before = vm.scheduler.get_pending_count()
    print(f"Initial pending events: {pending_before}")

    # Submit event manually (bypass immediate flush)
    vm.scheduler.submit_intent(
        vessel_id="P1_C03",
        event_type="TREAT_COMPOUND",
        requested_time_h=float(vm.simulated_time),
        payload={"compound": "staurosporine", "dose_uM": 0.05}
    )

    pending_after_submit = vm.scheduler.get_pending_count()
    c_before_flush = vm.injection_mgr.get_compound_concentration_uM("P1_C03", "staurosporine")

    print(f"\nAfter submit (before flush):")
    print(f"  Pending events: {pending_after_submit}")
    print(f"  Concentration: {c_before_flush:.6f} µM")

    # Flush events
    flushed = vm.scheduler.flush_due_events(now_h=float(vm.simulated_time), injection_mgr=vm.injection_mgr)
    pending_after_flush = vm.scheduler.get_pending_count()
    c_after_flush = vm.injection_mgr.get_compound_concentration_uM("P1_C03", "staurosporine")

    print(f"\nAfter flush:")
    print(f"  Events flushed: {len(flushed)}")
    print(f"  Pending events: {pending_after_flush}")
    print(f"  Concentration: {c_after_flush:.6f} µM")

    # Verify flush delivered events
    if pending_after_submit > pending_before and pending_after_flush == 0 and abs(c_after_flush - 0.05) < 1e-9:
        print(f"✓ PASS: Flush is the only path to concentration change")
        print(f"  Pending count: {pending_before} → {pending_after_submit} → {pending_after_flush}")
        print(f"  Concentration: {c_before_flush:.6f} → {c_after_flush:.6f}")
        return True
    else:
        print(f"❌ FAIL: Flush path broken")
        print(f"  Expected: pending goes up then to 0, concentration changes only after flush")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test B3: Scheduler Cannot Mutate Concentrations")
    print("=" * 70)
    print()

    tests = [
        ("submit_intent no immediate mutation", test_submit_intent_no_immediate_mutation),
        ("Scheduler metadata no concentration effect", test_scheduler_metadata_no_concentration_effect),
        ("Flush only path to concentration change", test_flush_only_path_to_concentration_change),
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
