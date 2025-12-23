"""
Enforcement Test: Instant Kill Guardrail

Guards against:
- Calling _apply_instant_kill during hazard proposal/commit phase
- Double-counting death in ledgers (instant kill + hazard proposal)
- Conservation violations from overlapping death accounting windows

Critical property:
- _apply_instant_kill must ONLY be called outside _step_vessel execution
- During _step_vessel, all death must go through _propose_hazard → _commit_step_death
- Guardrail should raise RuntimeError if violated
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_instant_kill_blocked_during_step():
    """
    Test that _apply_instant_kill raises RuntimeError when called during step.

    This test intentionally triggers the guardrail by monkeypatching
    _step_vessel to call instant_kill during execution.
    """
    print("Test: Instant kill blocked during step execution")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, initial_viability=1.0)

    # Add compound to trigger non-trivial step
    vm.treat_with_compound("P1_A01", "tunicamycin", 1.0)

    # Monkeypatch _update_vessel_growth to try instant_kill during step
    # (called early in _step_vessel, guaranteed to be during proposal phase)
    vessel = vm.vessel_states["P1_A01"]
    original_update_growth = vm._update_vessel_growth

    violation_caught = False
    error_message = None

    def patched_update_growth(vessel, hours):
        nonlocal violation_caught, error_message
        # This should fail because we're inside _step_vessel
        # (_step_hazard_proposals is not None during step)
        try:
            vm._apply_instant_kill(vessel, 0.1, "death_unknown")
            # Should not reach here
        except RuntimeError as e:
            if "during hazard proposal/commit phase" in str(e):
                violation_caught = True
                error_message = str(e)
                # Don't re-raise, let test check the flag
        # Call original
        original_update_growth(vessel, hours)

    vm._update_vessel_growth = patched_update_growth

    # Advance time, which will trigger patched function during step
    vm.advance_time(1.0)

    # Check if guardrail was triggered
    if violation_caught:
        print(f"✓ PASS: Guardrail blocked instant_kill during step")
        print(f"  Error message: {error_message[:100]}...")
        return True
    else:
        print("❌ FAIL: Guardrail did not trigger (instant_kill was allowed during step)")
        return False


def test_instant_kill_allowed_outside_step():
    """
    Test that _apply_instant_kill works normally outside _step_vessel.

    This is the legitimate use case (e.g., treatment instant effect,
    contamination during feed/washout operations).
    """
    print("\nTest: Instant kill allowed outside step execution")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=123)
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, initial_viability=1.0)

    vessel = vm.vessel_states["P1_B02"]
    viability_before = vessel.viability

    print(f"Viability before: {viability_before:.4f}")

    # This should work (we're outside _step_vessel)
    try:
        vm._apply_instant_kill(vessel, 0.15, "death_unknown")
        viability_after = vessel.viability
        death_unknown = vessel.death_unknown

        print(f"Viability after:  {viability_after:.4f}")
        print(f"Death (unknown):  {death_unknown:.4f}")

        # Verify kill was applied
        expected_viability = viability_before * (1.0 - 0.15)
        if abs(viability_after - expected_viability) < 1e-9:
            print(f"✓ PASS: instant_kill applied correctly outside step")
            return True
        else:
            print(f"❌ FAIL: viability mismatch (expected {expected_viability:.4f}, got {viability_after:.4f})")
            return False

    except RuntimeError as e:
        print(f"❌ FAIL: Guardrail blocked legitimate instant_kill: {e}")
        return False


def test_instant_kill_after_step_completes():
    """
    Test that _apply_instant_kill works after _step_vessel completes.

    This verifies the cleanup logic: _step_hazard_proposals is set to None
    at the end of _step_vessel, allowing instant_kill to be called afterward.
    """
    print("\nTest: Instant kill allowed after step completes")
    print("-" * 70)

    vm = BiologicalVirtualMachine(seed=999)
    vm.seed_vessel("P1_C03", "A549", initial_count=1e6, initial_viability=1.0)

    # Run a step (this should complete without error)
    vm.advance_time(1.0)

    vessel = vm.vessel_states["P1_C03"]
    viability_before = vessel.viability

    print(f"Viability after step: {viability_before:.4f}")

    # Now try instant_kill (should work because step completed)
    try:
        vm._apply_instant_kill(vessel, 0.10, "death_unknown")
        viability_after = vessel.viability

        print(f"Viability after instant_kill: {viability_after:.4f}")

        # Verify kill was applied
        expected_viability = viability_before * (1.0 - 0.10)
        if abs(viability_after - expected_viability) < 1e-9:
            print(f"✓ PASS: instant_kill allowed after step completes")
            return True
        else:
            print(f"❌ FAIL: viability mismatch (expected {expected_viability:.4f}, got {viability_after:.4f})")
            return False

    except RuntimeError as e:
        print(f"❌ FAIL: Guardrail incorrectly blocked instant_kill after step: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Enforcement Test: Instant Kill Guardrail")
    print("=" * 70)
    print()

    tests = [
        ("Instant kill blocked during step", test_instant_kill_blocked_during_step),
        ("Instant kill allowed outside step", test_instant_kill_allowed_outside_step),
        ("Instant kill allowed after step completes", test_instant_kill_after_step_completes),
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
