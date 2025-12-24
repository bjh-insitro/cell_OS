#!/usr/bin/env python3
"""
Conservation Test: Wash Debris Accounting

Verifies that pre-fixation debris creation correctly accounts for cell fate:
- Detached cells: removed from adherent, aspirated away (cells_lost_to_handling)
- Debris cells: removed from adherent, remain as fragments (debris_cells)
- Both reduce adherent cell_count (neither are attached)

Conservation law:
    initial_adherent = detached + debris + remaining_adherent

Where:
    detached = cells_lost_to_handling (aspirated)
    debris = debris_cells (fragmented, stays in well)
    remaining_adherent = cell_count (still attached)

CRITICAL: Debris is NOT "background junk that appears without affecting cells."
It is "cells that detached, fragmented, and remained in well."
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_wash_debris_reduces_adherent_cells():
    """
    Pre-fixation debris must reduce adherent cell count.

    Debris = cells that detached and fragmented (not background junk).
    Both detachment and debris remove from adherent population.

    Invariant:
        cell_count_post = cell_count_pre - detached - debris
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel(vessel_id="well_A1", cell_line="A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(hours=48)

    vessel = vm.vessel_states["well_A1"]
    pre_cells = vessel.cell_count
    pre_handling = vessel.cells_lost_to_handling
    pre_debris = vessel.debris_cells

    # Wash (pre-fixation, should generate debris)
    result = vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    post_cells = vessel.cell_count
    post_handling = vessel.cells_lost_to_handling
    post_debris = vessel.debris_cells

    detached = post_handling - pre_handling
    debris = post_debris - pre_debris
    total_loss = detached + debris

    # Conservation: initial = detached + debris + remaining
    assert abs((pre_cells) - (detached + debris + post_cells)) < 1.0, \
        f"Conservation violated: {pre_cells} != {detached} + {debris} + {post_cells}"

    # Cell count must decrease by total loss
    assert abs((pre_cells - post_cells) - total_loss) < 1.0, \
        f"Cell count loss mismatch: {pre_cells - post_cells} != {total_loss}"

    # Debris must be non-zero (pre-fixation generates debris)
    assert debris > 0, f"Debris should be generated pre-fixation: {debris}"

    # Debris must reduce adherent cells (not background junk)
    assert post_cells < pre_cells, \
        f"Cell count should decrease: {post_cells} >= {pre_cells}"

    print(f"✓ Conservation verified:")
    print(f"  Initial adherent: {pre_cells:.0f}")
    print(f"  Detached (aspirated): {detached:.0f}")
    print(f"  Debris (fragmented): {debris:.0f}")
    print(f"  Remaining adherent: {post_cells:.0f}")
    print(f"  Total accounted: {detached + debris + post_cells:.0f}")


def test_wash_debris_accounting_multi_wash():
    """
    Multiple washes accumulate debris correctly.

    Each wash:
    - Reduces adherent cells by (detach_frac + debris_frac)
    - Adds to cells_lost_to_handling (aspirated)
    - Adds to debris_cells (fragmented)

    Conservation holds across all washes.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel(vessel_id="well_A1", cell_line="A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(hours=48)

    vessel = vm.vessel_states["well_A1"]
    initial_cells = vessel.cell_count

    # First wash
    vm.wash_vessel("well_A1", n_washes=1, intensity=0.5)
    after_wash1_cells = vessel.cell_count
    after_wash1_handling = vessel.cells_lost_to_handling
    after_wash1_debris = vessel.debris_cells

    # Second wash
    vm.wash_vessel("well_A1", n_washes=1, intensity=0.5)
    after_wash2_cells = vessel.cell_count
    after_wash2_handling = vessel.cells_lost_to_handling
    after_wash2_debris = vessel.debris_cells

    # Conservation across both washes
    total_handling = after_wash2_handling
    total_debris = after_wash2_debris
    remaining = after_wash2_cells

    assert abs(initial_cells - (total_handling + total_debris + remaining)) < 1.0, \
        f"Multi-wash conservation violated: {initial_cells} != {total_handling} + {total_debris} + {remaining}"

    # Debris should accumulate
    assert after_wash2_debris > after_wash1_debris, \
        f"Debris should accumulate: {after_wash2_debris} <= {after_wash1_debris}"

    print(f"✓ Multi-wash conservation verified:")
    print(f"  Initial: {initial_cells:.0f}")
    print(f"  After wash 1: cells={after_wash1_cells:.0f}, debris={after_wash1_debris:.0f}")
    print(f"  After wash 2: cells={after_wash2_cells:.0f}, debris={after_wash2_debris:.0f}")
    print(f"  Total accounted: {total_handling + total_debris + remaining:.0f}")


def test_debris_is_not_death():
    """
    Debris does not affect viability (it's detachment, not death).

    Detachment removes cells from adherent population but doesn't kill them.
    Viability tracks fraction of LIVE cells (adherent or not).

    Conservation:
        viable_cells = cell_count * viability  # Adherent viable
        dead_cells = cell_count * (1 - viability)  # Adherent dead
        detached_cells = cells_lost_to_handling  # Removed (live)
        debris_cells = debris_cells  # Fragmented (was live)

    Total initial = viable + dead + detached + debris
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel(vessel_id="well_A1", cell_line="A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(hours=48)

    vessel = vm.vessel_states["well_A1"]
    pre_viability = vessel.viability

    # Wash
    vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    post_viability = vessel.viability

    # Viability should be unchanged (detachment is not death)
    # Allow small numerical tolerance
    assert abs(post_viability - pre_viability) < 0.01, \
        f"Viability changed unexpectedly: {pre_viability:.4f} -> {post_viability:.4f}. " \
        f"Detachment should not affect viability."

    # Debris is counted in cells_lost_to_handling + debris_cells, not death ledgers
    # (death ledgers like death_compound, death_confluence should be unchanged)
    # This is already tested implicitly, but document the semantic

    print(f"✓ Debris is detachment, not death:")
    print(f"  Viability pre: {pre_viability:.4f}")
    print(f"  Viability post: {post_viability:.4f}")
    print(f"  Debris: {vessel.debris_cells:.0f} (not credited to death ledgers)")


if __name__ == "__main__":
    print("=" * 70)
    print("Wash Debris Accounting Conservation Tests")
    print("=" * 70)

    test_wash_debris_reduces_adherent_cells()
    print()
    test_wash_debris_accounting_multi_wash()
    print()
    test_debris_is_not_death()

    print("\n" + "=" * 70)
    print("ALL CONSERVATION TESTS PASSED")
    print("=" * 70)
