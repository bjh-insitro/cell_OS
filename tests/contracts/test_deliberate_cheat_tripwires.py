"""
Deliberate cheat regression tests.

These tests verify that specific cheating patterns are caught by the contract.
They're tripwires: if they start passing, someone broke the enforcement.
"""

import os
import pytest
from src.cell_os.contracts import CausalContractViolation


def test_cell_painting_cannot_read_compounds_regression(vm_and_vessel):
    """
    TRIPWIRE: Cell Painting reading state.compounds must be caught.

    This was a real bug. Don't let it come back.
    """
    vm, vessel = vm_and_vessel

    # Add treatment (forbidden to read)
    vessel.compounds = {"staurosporine": 1.0}
    vessel.compound_meta = {"staurosporine": {"ic50_uM": 0.1}}

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This must succeed without reading compounds
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify no compound identity in result
        assert "compounds" not in result
        assert "compound_meta" not in result

        # If we get here, Cell Painting is properly blind to treatment
        assert "morphology" in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_cell_painting_cannot_read_cell_count_regression(vm_and_vessel):
    """
    TRIPWIRE: Cell Painting reading state.cell_count must be caught.

    Cross-modal independence: morphology imaging cannot see cell counts.
    This was a real bug. Don't let it come back.
    """
    vm, vessel = vm_and_vessel

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This must succeed without reading cell_count
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify Cell Painting does NOT leak cell_count at top level
        # (cell_count_observed is OK from segmentation, but not ground truth)
        if "cell_count" in result:
            # If present, it must be estimated/observed, not ground truth
            assert "cell_count_estimated" in result or "cell_count_observed" in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_cell_painting_cannot_read_death_mode_regression(vm_and_vessel):
    """
    TRIPWIRE: Cell Painting reading state.death_mode must be caught.

    Measurements cannot branch on categorical ground truth labels.
    This was a real bug. Don't let it come back.
    """
    vm, vessel = vm_and_vessel

    # Set death mode (forbidden to read)
    vessel.death_mode = "apoptosis"

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This must succeed without reading death_mode
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify no death_mode at top level
        assert "death_mode" not in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_ldh_cannot_leak_viability_at_top_level_regression(vm_and_vessel):
    """
    TRIPWIRE: LDH leaking viability at top level must be caught.

    Viability is ground truth, must be behind _debug_truth gate.
    This was a real bug. Don't let it come back.
    """
    vm, vessel = vm_and_vessel

    # Measure with debug disabled (default)
    result = vm.atp_viability_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify ground truth NOT at top level
    assert "viability" not in result, "viability leaked at top level (must be in _debug_truth)"
    assert "cell_count" not in result, "cell_count leaked at top level (must be in _debug_truth)"
    assert "death_mode" not in result, "death_mode leaked at top level (must be in _debug_truth)"

    # Verify measured signals ARE present
    assert "ldh_signal" in result
    assert "atp_signal" in result


def test_ldh_can_return_debug_truth_when_enabled_regression(vm_and_vessel_debug):
    """
    TRIPWIRE: LDH debug truth must work when explicitly enabled.

    This is the deliberate escape hatch. Make sure it still works.
    """
    vm, vessel = vm_and_vessel_debug

    # Measure with debug enabled
    result = vm.atp_viability_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify debug truth IS present when enabled
    assert "_debug_truth" in result
    assert "viability" in result["_debug_truth"]
    assert "cell_count" in result["_debug_truth"]


def test_scrna_cannot_read_cell_count_regression(vm_and_vessel):
    """
    TRIPWIRE: scRNA reading state.cell_count must be caught.

    scRNA must use capturable_cells proxy (observable), not true count.
    This was a real bug. Don't let it come back.
    """
    vm, vessel = vm_and_vessel

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This must succeed without reading cell_count
        result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

        # Verify result is valid
        assert result["status"] == "success"

        # Verify no top-level cell_count leak
        # (captured_cell_count is OK, it's the observable proxy)
        if "cell_count" in result:
            assert "captured_cell_count" in result or "capturable_cells" in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_scrna_uses_capturable_cells_not_true_count_regression(vm_and_vessel):
    """
    TRIPWIRE: scRNA must use capturable_cells, not cell_count.

    The observable proxy accounts for handling losses and debris.
    """
    vm, vessel = vm_and_vessel

    # Set known state with losses
    vessel.cell_count = 10000
    vessel.cells_lost_to_handling = 1000
    vessel.debris_cells = 500

    # Expected capturable
    expected = 10000 - 1000 - 500  # 8500

    # Verify capturable_cells property works
    assert vessel.capturable_cells == pytest.approx(expected, abs=1.0)

    # Measure (should use capturable_cells internally)
    result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

    # If captured_cell_count is returned, it should reflect losses
    if "captured_cell_count" in result:
        # Allow ±30% due to sampling noise
        captured = result["captured_cell_count"]
        assert abs(captured - expected) / expected < 0.3


def test_contract_violations_are_caught_in_strict_mode():
    """
    TRIPWIRE: CELL_OS_STRICT_CAUSAL_CONTRACT=1 must raise on violations.

    This verifies that strict mode enforcement is working.
    """
    from src.cell_os.contracts.causal_contract import _strict_mode, _violation

    # Temporarily enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # Verify strict mode is enabled
        assert _strict_mode() is True

        # A violation should raise
        with pytest.raises(CausalContractViolation):
            _violation("test violation")

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_contract_violations_are_recorded_in_record_mode():
    """
    TRIPWIRE: CELL_OS_CONTRACT_RECORD=1 must collect violations without raising.

    This verifies that record mode (used by audit test) is working.
    """
    from src.cell_os.contracts.causal_contract import (
        _record_mode,
        _violation,
        get_recorded_contract_violations,
        clear_recorded_contract_violations
    )

    # Temporarily enable record mode
    os.environ["CELL_OS_CONTRACT_RECORD"] = "1"

    try:
        # Clear any previous violations
        clear_recorded_contract_violations()

        # Verify record mode is enabled
        assert _record_mode() is True

        # A violation should NOT raise, but should be recorded
        _violation("test violation 1")
        _violation("test violation 2")

        violations = get_recorded_contract_violations()
        assert "test violation 1" in violations
        assert "test violation 2" in violations

    finally:
        os.environ.pop("CELL_OS_CONTRACT_RECORD", None)
        clear_recorded_contract_violations()
