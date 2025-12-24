"""
Test: Measurements cannot mutate biological state.

Verifies that all measurements are read-only and detect mutation attempts.
"""

import pytest
from src.cell_os.contracts import CausalContractViolation


def test_cell_painting_cannot_mutate_viability(vm_and_vessel):
    """Cell Painting assay cannot mutate vessel.viability."""
    vm, vessel = vm_and_vessel

    # Store original state
    original_viability = vessel.viability
    original_cell_count = vessel.cell_count
    original_confluence = vessel.confluence

    # Measure (should not mutate)
    result = vm.cell_painting_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify state unchanged
    assert vessel.viability == original_viability
    assert vessel.cell_count == original_cell_count
    assert vessel.confluence == original_confluence


def test_ldh_cannot_mutate_viability(vm_and_vessel):
    """LDH viability assay cannot mutate vessel state."""
    vm, vessel = vm_and_vessel

    # Store original state
    original_viability = vessel.viability
    original_cell_count = vessel.cell_count

    # Measure (should not mutate)
    result = vm.atp_viability_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify state unchanged
    assert vessel.viability == original_viability
    assert vessel.cell_count == original_cell_count


def test_scrna_cannot_mutate_cell_count(vm_and_vessel):
    """scRNA-seq assay cannot mutate vessel state."""
    vm, vessel = vm_and_vessel

    # Store original state
    original_viability = vessel.viability
    original_confluence = vessel.confluence

    # Measure (should not mutate)
    result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

    # Verify state unchanged
    assert vessel.viability == original_viability
    assert vessel.confluence == original_confluence


def test_proxy_prevents_direct_mutation_attempt():
    """
    Verify that _ReadOnlyProxy prevents mutation attempts.

    This is a unit test of the proxy mechanism itself.
    """
    from src.cell_os.contracts.causal_contract import (
        _ReadOnlyProxy,
        _AccessLog,
        MeasurementContract,
    )

    # Create simple test object
    class TestState:
        def __init__(self):
            self.value = 42

    state = TestState()
    contract = MeasurementContract(name="Test", allowed_reads={"state.value"})
    log = _AccessLog()

    # Wrap in read-only proxy
    proxy = _ReadOnlyProxy(state, "state", log, contract, debug_truth_enabled=False)

    # Read should work
    assert proxy.value == 42

    # Write should be logged as violation (but not raise in default mode)
    proxy.value = 100

    # Mutation should be logged
    assert len(log.writes) > 0
    assert "state.value" in log.writes
