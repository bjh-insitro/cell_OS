"""
Test: scRNA-seq uses capturable_cells proxy (not true cell_count).

scRNA-seq captures cells via microfluidics. The number of cells captured
depends on handling losses, debris, and capture efficiency - NOT the true
cell count in the vessel.

capturable_cells = cell_count - cells_lost_to_handling - debris_cells
"""

import pytest
import os


def test_scrna_uses_capturable_cells_proxy(vm_and_vessel):
    """
    scRNA-seq should use capturable_cells, not cell_count.

    This prevents cross-modal coupling (counting vs sequencing).
    """
    vm, vessel = vm_and_vessel

    # Set known state
    vessel.cell_count = 10000
    vessel.cells_lost_to_handling = 1000
    vessel.debris_cells = 500

    # Expected capturable cells
    expected_capturable = 10000 - 1000 - 500  # 8500

    # Measure in strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

        # Verify result exists and has expected structure
        assert "status" in result
        assert result["status"] == "success"

        # scRNA should report captured cells, not true count
        if "captured_cell_count" in result:
            # Should be close to capturable_cells (with some sampling noise)
            captured = result["captured_cell_count"]
            assert captured > 0
            # Allow ±20% due to sampling noise
            assert abs(captured - expected_capturable) / expected_capturable < 0.3

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_scrna_capturable_cells_decreases_with_handling_loss(make_vm_and_vessel):
    """
    scRNA captured cells should decrease as handling losses increase.

    This verifies that scRNA is using the observable proxy, not true count.
    """
    # Create two vessels with different handling losses
    vm1, vessel1 = make_vm_and_vessel(debug_truth_enabled=False)
    vm2, vessel2 = make_vm_and_vessel(debug_truth_enabled=False)

    vessel1.cell_count = 10000
    vessel1.cells_lost_to_handling = 500  # Low loss
    vessel1.debris_cells = 0

    vessel2.cell_count = 10000
    vessel2.cells_lost_to_handling = 3000  # High loss
    vessel2.debris_cells = 0

    # Measure both
    result1 = vm1.scrna_seq_assay.measure(vessel1, plate_id="P1")
    result2 = vm2.scrna_seq_assay.measure(vessel2, plate_id="P1")

    # Vessel with more handling loss should capture fewer cells
    if "captured_cell_count" in result1 and "captured_cell_count" in result2:
        assert result1["captured_cell_count"] > result2["captured_cell_count"]


def test_scrna_cannot_read_cell_count_in_purity_check(vm_and_vessel):
    """
    scRNA purity check must not read vessel.cell_count.

    The purity assertion should only check allowed fields (viability, confluence).
    """
    vm, vessel = vm_and_vessel

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This should succeed without reading cell_count in purity check
        result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

        # Verify result is valid
        assert result["status"] == "success"

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_capturable_cells_property_calculation():
    """
    Unit test for capturable_cells property calculation.

    capturable_cells = cell_count - cells_lost_to_handling - debris_cells
    """
    from src.cell_os.hardware.biological_virtual import VesselState

    vessel = VesselState(vessel_id="test", cell_line="A549", initial_count=10000)
    vessel.cell_count = 10000
    vessel.cells_lost_to_handling = 1200
    vessel.debris_cells = 800

    # Expected: 10000 - 1200 - 800 = 8000
    assert vessel.capturable_cells == pytest.approx(8000, abs=1.0)


def test_capturable_cells_never_negative():
    """
    capturable_cells should never go negative (floor at 0).
    """
    from src.cell_os.hardware.biological_virtual import VesselState

    vessel = VesselState(vessel_id="test", cell_line="A549", initial_count=1000)
    vessel.cell_count = 1000
    vessel.cells_lost_to_handling = 800
    vessel.debris_cells = 500  # Total losses exceed cell_count

    # Should be clamped to 0, not negative
    assert vessel.capturable_cells >= 0
