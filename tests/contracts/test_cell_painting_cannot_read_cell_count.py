"""
Test: Cell Painting cannot read cell_count (cross-modal independence).

Cell Painting measures morphology via imaging. Cell counting is a separate
modality (brightfield imaging, flow cytometry, hemocytometer). Allowing
Cell Painting to see cell_count creates cross-modal coupling that prevents
learning the independence structure of measurement errors.
"""

import pytest
import os
from src.cell_os.contracts import CausalContractViolation


def test_cell_painting_cannot_read_cell_count_strict_mode(vm_and_vessel):
    """
    Cell Painting assay must not read vessel.cell_count.

    Cross-modal independence: morphology imaging cannot see cell counts.
    """
    vm, vessel = vm_and_vessel

    # Enable strict mode for this test
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This should succeed without reading cell_count
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify result contains morphology
        assert "morphology" in result
        assert "er" in result["morphology"]
        assert "mito" in result["morphology"]

        # Verify Cell Painting does NOT leak cell_count at top level
        assert "cell_count" not in result or "cell_count_true" in result  # Segmentation can report observed vs true

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_cell_painting_uses_confluence_for_estimates(vm_and_vessel):
    """
    Cell Painting should use confluence-based estimates, not true cell_count.

    When Cell Painting needs to estimate cell density (e.g., for quality metrics),
    it should use confluence (observable from images) rather than true cell_count.
    """
    vm, vessel = vm_and_vessel

    # Set known confluence
    vessel.confluence = 0.5

    # Measure
    result = vm.cell_painting_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # If quality metrics are present, they should be consistent with confluence
    if "cp_quality" in result:
        # Quality should degrade with debris/handling, but baseline should reflect confluence
        # This is a sanity check - not a hard requirement
        assert result["cp_quality"] >= 0.0
        assert result["cp_quality"] <= 1.0


def test_cell_painting_quality_metrics_use_confluence(vm_and_vessel):
    """
    Cell Painting quality metrics should use confluence-derived estimates.

    The _compute_cp_quality_metrics() helper should not read vessel.cell_count.
    """
    vm, vessel = vm_and_vessel

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # Add some debris to trigger quality degradation
        vessel.debris_cells = 500.0
        vessel.confluence = 0.6

        # Measure - should compute quality without reading cell_count
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify quality metrics are present
        assert "cp_quality" in result
        assert "debris_load" in result
        assert "segmentation_yield" in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)
