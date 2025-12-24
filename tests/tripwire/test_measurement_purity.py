"""
Tripwire Test: Measurement Purity

Enforces STATE_MAP.md Section 2: Mutation Rules

Verifies measurement functions NEVER mutate world state.
Observer independence is a core invariant.

FAILURE MODE: If this test fails, measurements are backacting on physics.
Breaks counterfactual reasoning and makes the simulator non-physical.
"""

import pytest
from tests.tripwire._harness import make_vm, seed_vm_vessel, get_vessel_state


def test_count_cells_does_not_mutate():
    """
    Verify count_cells() does not mutate vessel state.

    STATE_MAP.md: Measurements are read-only (enforced by assertions).
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    vessel = get_vessel_state(vm, 'v1')

    # Snapshot state before measurement
    state_before = {
        'cell_count': vessel.cell_count,
        'viability': vessel.viability,
        'confluence': vessel.confluence,
    }

    # Perform measurement
    result = vm.count_cells('v1')

    # Verify state unchanged
    assert vessel.cell_count == state_before['cell_count'], \
        "count_cells() mutated cell_count"
    assert vessel.viability == state_before['viability'], \
        "count_cells() mutated viability"
    assert vessel.confluence == state_before['confluence'], \
        "count_cells() mutated confluence"


def test_cell_painting_does_not_mutate():
    """
    Verify cell_painting_assay() does not mutate vessel state.

    Most complex measurement (segmentation artifacts). Must not backact.
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    vessel = get_vessel_state(vm, 'v1')

    # Snapshot state
    state_before = {
        'cell_count': vessel.cell_count,
        'viability': vessel.viability,
    }

    # Perform measurement
    result = vm.cell_painting_assay('v1')

    # Verify state unchanged
    assert vessel.cell_count == state_before['cell_count'], \
        "cell_painting_assay() mutated cell_count"
    assert vessel.viability == state_before['viability'], \
        "cell_painting_assay() mutated viability"


def test_measurement_order_independence():
    """
    Verify measurement order does not affect world state.

    Observer independence requires measurements to commute.
    """
    # Run 1: Measure A then B
    vm1 = make_vm(seed=0)
    seed_vm_vessel(vm1, 'v1')
    vm1.treat_with_compound('v1', compound='staurosporine', dose_uM=1.0)
    vm1.advance_time(hours=24.0)

    vm1.count_cells('v1')
    vm1.atp_viability_assay('v1')

    state1 = get_vessel_state(vm1, 'v1')

    # Run 2: Measure B then A
    vm2 = make_vm(seed=0)
    seed_vm_vessel(vm2, 'v1')
    vm2.treat_with_compound('v1', compound='staurosporine', dose_uM=1.0)
    vm2.advance_time(hours=24.0)

    vm2.atp_viability_assay('v1')
    vm2.count_cells('v1')

    state2 = get_vessel_state(vm2, 'v1')

    # Verify order independence
    assert state1.cell_count == state2.cell_count, \
        "Measurement order affected cell_count (backaction detected)"
    assert state1.viability == state2.viability, \
        "Measurement order affected viability (backaction detected)"


def test_wash_and_fixation_are_not_measurements():
    """
    Verify wash and fixation ARE allowed to mutate (they're not measurements).

    STATE_MAP.md: Handling physics (wash, fix) removes cells, changes adhesion.
    This is intentional backaction, not observer violation.
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    vessel = get_vessel_state(vm, 'v1')

    # Check if wash_vessel exists (may not be in all VM versions)
    if hasattr(vm, 'wash_vessel'):
        # Wash (should remove cells - this is intentional)
        vm.wash_vessel('v1', wash_volume_ml=0.2, n_washes=3)

        # Verify cells were removed (handling physics, not measurement)
        assert vessel.cells_lost_to_handling > 0, \
            "Wash should remove cells (this is handling physics, not measurement)"

    # Check if fix_vessel exists
    if hasattr(vm, 'fix_vessel'):
        # Fixation (should destroy vessel - this is intentional)
        vm.fix_vessel('v1')

        # Verify vessel is destroyed (handling physics, not measurement)
        assert vessel.is_destroyed, \
            "Fixation should destroy vessel (this is handling physics, not measurement)"
    else:
        pytest.skip("wash_vessel and fix_vessel not available in this VM version")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
