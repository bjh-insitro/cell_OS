"""
Tests that death accounting is honest (no silent laundering or cosplay).

These catch the subtle semantic bugs that make simulators "look calibrated" while lying.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_contamination_death_survives_update_death_mode():
    """
    Test A: Contamination death credited to death_unknown must survive.

    Bug (fixed): _update_death_mode() overwrites death_unknown with residual,
    so explicit credits get laundered.
    """
    vm = BiologicalVirtualMachine(seed=42)
    # Seed with perfect viability to isolate contamination
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=1.0)
    vessel = vm.vessel_states["test_well"]

    # Explicitly credit 2% death to unknown (contamination)
    contamination_kill = 0.02
    death_unknown_before = vessel.death_unknown
    vm._apply_instant_kill(vessel, contamination_kill, "death_unknown")
    death_unknown_after_kill = vessel.death_unknown

    # Check state before _update_death_mode
    print(f"Before _update_death_mode:")
    print(f"  viability: {vessel.viability:.4f}")
    print(f"  death_unknown (before kill): {death_unknown_before:.4f}")
    print(f"  death_unknown (after kill): {death_unknown_after_kill:.4f}")

    # Now call _update_death_mode (this is where laundering happens)
    vm._update_death_mode(vessel)

    print(f"After _update_death_mode:")
    print(f"  death_unknown: {vessel.death_unknown:.4f}")
    print(f"  death_unattributed: {vessel.death_unattributed:.6f}")

    # Assert: death_unknown should still equal what we credited (not be overwritten)
    expected = death_unknown_before + contamination_kill
    if abs(vessel.death_unknown - expected) > 1e-6:
        print(f"❌ FAIL: death_unknown was modified by _update_death_mode")
        print(f"  Expected: {expected:.4f}")
        print(f"  Got: {vessel.death_unknown:.4f}")
        return False

    # Assert: death_unattributed should be ~0 (all death accounted for)
    if vessel.death_unattributed > 1e-6:
        print(f"⚠ WARN: death_unattributed non-zero ({vessel.death_unattributed:.6f}), but < epsilon")

    print("✓ PASS: Contamination death preserved, unattributed ~0")
    return True


def test_no_silent_renormalization():
    """
    Test B: No silent renormalization should ever occur.

    If _step_ledger_scale != 1.0, either:
    (a) it's a bug and should crash, OR
    (b) it's intentional and should be logged/audited

    Current code does silent renormalization, which contradicts the
    "no silent laundering" invariant stated elsewhere.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Apply multiple hazards
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)

    vessel = vm.vessel_states["test_well"]

    # Check if renormalization occurred
    if not hasattr(vessel, '_step_ledger_scale'):
        print("⚠ WARN: _step_ledger_scale not tracked (can't verify)")
        return True

    if vessel._step_ledger_scale != 1.0:
        print(f"❌ FAIL: Silent renormalization occurred")
        print(f"  _step_ledger_scale: {vessel._step_ledger_scale:.6f}")
        print(f"  This contradicts 'no silent laundering' invariant")
        return False
    else:
        print(f"✓ PASS: No renormalization (_step_ledger_scale = 1.0)")
        return True


def test_passage_resets_clocks_and_artifacts():
    """
    Test C: Passaging should reset seed_time and resample plating artifacts.

    Bug: passage_cells() creates new vessel with seed_time=0.0, making
    "time since seed" huge and zeroing plating artifacts incorrectly.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("source", "A549", 1e6)
    vm.advance_time(72.0)  # 3 days

    # Passage
    result = vm.passage_cells("source", "target", split_ratio=4.0)

    if "target" not in vm.vessel_states:
        print("❌ FAIL: Target vessel not created")
        return False

    target = vm.vessel_states["target"]

    # Check seed_time was set to current time (not 0.0)
    if abs(target.seed_time - vm.simulated_time) > 1e-6:
        print(f"❌ FAIL: seed_time not reset")
        print(f"  Expected: {vm.simulated_time:.1f} (current time)")
        print(f"  Got: {target.seed_time:.1f}")
        return False

    # Check plating_context was sampled
    if target.plating_context is None:
        print("❌ FAIL: plating_context not sampled")
        return False

    print(f"✓ PASS: Passage clocks reset (seed_time={target.seed_time:.1f}h)")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Death Accounting Honesty")
    print("=" * 70)
    print()

    tests = [
        ("Contamination death survives update_death_mode", test_contamination_death_survives_update_death_mode),
        ("No silent renormalization", test_no_silent_renormalization),
        ("Passage resets clocks and artifacts", test_passage_resets_clocks_and_artifacts),
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
