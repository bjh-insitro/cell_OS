"""
Test ledger conservation under mixed mechanisms + instant events.

This is the "keeper of honesty" test: ensures conservation holds when:
- Initial viability < 1 (death_unknown nonzero at start)
- Instant kill from compound treatment
- Time-dependent hazards from multiple mechanisms
- Passage with stateful transfer

If someone "just adds a little hazard" without proper accounting, this catches it.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine, DEATH_EPS


def test_conservation_with_mixed_mechanisms():
    """
    Test conservation law holds under mixed instant + time-dependent death.

    Setup:
    - Seed with imperfect viability (death_unknown starts nonzero)
    - Apply compound (instant kill + attrition)
    - Advance time to trigger ER stress, starvation, mitotic hazards
    - Verify conservation at every step

    Invariant: sum(death_* including unattributed) == 1 - viability ± DEATH_EPS
    """
    vm = BiologicalVirtualMachine(seed=42)

    # Seed with imperfect viability to start with nonzero death_unknown
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=0.95)
    vessel = vm.vessel_states["test_well"]

    print(f"Initial state:")
    print(f"  viability: {vessel.viability:.4f}")
    print(f"  death_unknown: {vessel.death_unknown:.4f}")

    # Check initial conservation
    total_dead = 1.0 - vessel.viability
    tracked = vessel.death_unknown + vessel.death_unattributed
    if abs(tracked - total_dead) > DEATH_EPS:
        print(f"❌ FAIL: Initial conservation violated")
        return False

    # Apply compound (instant kill + attrition)
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)

    print(f"\nAfter compound treatment:")
    print(f"  viability: {vessel.viability:.4f}")
    print(f"  death_compound: {vessel.death_compound:.4f}")
    print(f"  death_unknown: {vessel.death_unknown:.4f}")

    # Check conservation after instant kill
    total_dead = 1.0 - vessel.viability
    tracked = (
        vessel.death_compound +
        vessel.death_unknown +
        vessel.death_unattributed
    )
    if abs(tracked - total_dead) > DEATH_EPS:
        print(f"❌ FAIL: Conservation violated after instant kill")
        print(f"  total_dead={total_dead:.6f}, tracked={tracked:.6f}")
        return False

    # Advance time to trigger multiple hazards
    for step in range(3):
        vm.advance_time(8.0)  # 8h steps

        total_dead = 1.0 - vessel.viability
        tracked = (
            vessel.death_compound +
            vessel.death_starvation +
            vessel.death_mitotic_catastrophe +
            vessel.death_er_stress +
            vessel.death_mito_dysfunction +
            vessel.death_confluence +
            vessel.death_unknown +
            vessel.death_unattributed
        )

        print(f"\nAfter step {step+1} (t={vm.simulated_time:.1f}h):")
        print(f"  viability: {vessel.viability:.4f}")
        print(f"  total_dead: {total_dead:.4f}")
        print(f"  tracked: {tracked:.4f}")
        print(f"  compound={vessel.death_compound:.4f}, er={vessel.death_er_stress:.4f}, "
              f"starvation={vessel.death_starvation:.4f}")

        # Check conservation
        if abs(tracked - total_dead) > DEATH_EPS:
            print(f"❌ FAIL: Conservation violated at step {step+1}")
            print(f"  total_dead={total_dead:.6f}, tracked={tracked:.6f}, diff={tracked-total_dead:.9f}")
            return False

        # Check no negative unattributed
        if vessel.death_unattributed < -DEATH_EPS:
            print(f"❌ FAIL: Negative death_unattributed ({vessel.death_unattributed:.6f})")
            return False

        # Check tracked_known <= total_dead + eps
        tracked_known = (
            vessel.death_compound +
            vessel.death_starvation +
            vessel.death_mitotic_catastrophe +
            vessel.death_er_stress +
            vessel.death_mito_dysfunction +
            vessel.death_confluence +
            vessel.death_unknown
        )
        if tracked_known > total_dead + DEATH_EPS:
            print(f"❌ FAIL: Ledger overflow at step {step+1}")
            print(f"  tracked_known={tracked_known:.6f} > total_dead={total_dead:.6f}")
            return False

    print(f"\n✓ PASS: Conservation held through all steps")
    return True


def test_conservation_through_passage():
    """
    Test that conservation holds through passage with stateful transfer.

    Setup:
    - Create stressed vessel with mixed death causes
    - Passage to new vessel
    - Verify conservation in both source and target
    - Verify attribution history preserved
    """
    vm = BiologicalVirtualMachine(seed=50)
    vm.seed_vessel("source", "A549", 1e6, initial_viability=0.90)

    # Create mixed death scenario
    vm.treat_with_compound("source", "tunicamycin", dose_uM=1.5)
    vm.advance_time(18.0)

    source = vm.vessel_states["source"]

    print(f"Source before passage:")
    print(f"  viability: {source.viability:.4f}")
    print(f"  death_compound: {source.death_compound:.4f}")
    print(f"  death_er_stress: {source.death_er_stress:.4f}")
    print(f"  death_unknown: {source.death_unknown:.4f}")

    # Check source conservation
    total_dead_source = 1.0 - source.viability
    tracked_source = (
        source.death_compound +
        source.death_starvation +
        source.death_mitotic_catastrophe +
        source.death_er_stress +
        source.death_mito_dysfunction +
        source.death_confluence +
        source.death_unknown +
        source.death_unattributed
    )
    if abs(tracked_source - total_dead_source) > DEATH_EPS:
        print(f"❌ FAIL: Source conservation violated before passage")
        return False

    # Passage
    result = vm.passage_cells("source", "target", split_ratio=4.0)

    if result["status"] != "success":
        print(f"❌ FAIL: Passage failed: {result}")
        return False

    target = vm.vessel_states["target"]

    print(f"\nTarget after passage:")
    print(f"  viability: {target.viability:.4f}")
    print(f"  death_compound: {target.death_compound:.4f}")
    print(f"  death_er_stress: {target.death_er_stress:.4f}")
    print(f"  death_unknown: {target.death_unknown:.4f} (includes passage stress)")

    # Check target conservation (passage_cells calls _update_death_mode, so this should pass)
    total_dead_target = 1.0 - target.viability
    tracked_target = (
        target.death_compound +
        target.death_starvation +
        target.death_mitotic_catastrophe +
        target.death_er_stress +
        target.death_mito_dysfunction +
        target.death_confluence +
        target.death_unknown +
        target.death_unattributed
    )

    print(f"  total_dead: {total_dead_target:.4f}")
    print(f"  tracked: {tracked_target:.4f}")

    if abs(tracked_target - total_dead_target) > DEATH_EPS:
        print(f"❌ FAIL: Target conservation violated after passage")
        print(f"  total_dead={total_dead_target:.6f}, tracked={tracked_target:.6f}")
        return False

    # Check attribution history preserved (death_compound should carry over)
    if target.death_compound == 0.0 and source.death_compound > 0.01:
        print(f"❌ FAIL: Attribution history lost (death_compound not transferred)")
        return False

    print(f"✓ PASS: Conservation held through passage, attribution preserved")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Mixed Mechanisms Conservation (Keeper of Honesty)")
    print("=" * 70)
    print()

    tests = [
        ("Conservation with mixed mechanisms", test_conservation_with_mixed_mechanisms),
        ("Conservation through passage", test_conservation_through_passage),
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
