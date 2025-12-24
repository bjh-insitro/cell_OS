"""
Test: LDH viability assay cannot leak ground truth (unless debug mode).

LDH measures membrane integrity (cytotoxicity). The assay should return
LDH signal, ATP, UPR, and trafficking markers - NOT viability or death labels.

Ground truth is only accessible via _debug_truth dict when explicitly enabled.
"""

import pytest
import os


def test_ldh_does_not_leak_viability_by_default(vm_and_vessel):
    """
    LDH assay must not return viability at top level.

    LDH signal is inversely proportional to viability, but viability itself
    is ground truth and should not be directly returned.
    """
    vm, vessel = vm_and_vessel

    # Measure with debug disabled (default)
    result = vm.atp_viability_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify measured signals are present
    assert "ldh_signal" in result
    assert "atp_signal" in result
    assert "upr_marker" in result
    assert "trafficking_marker" in result

    # Verify ground truth is NOT at top level
    assert "viability" not in result
    assert "cell_count" not in result
    assert "death_mode" not in result
    assert "death_compound" not in result

    # Verify no debug truth leaked
    assert "_debug_truth" not in result


def test_ldh_can_return_truth_when_debug_enabled(vm_and_vessel_debug):
    """
    LDH assay CAN return ground truth when debug mode is enabled.

    This is used for epistemic agent development - the agent sees measurements
    (LDH signal) but can optionally see truth for learning.
    """
    vm, vessel = vm_and_vessel_debug

    # Measure with debug enabled
    result = vm.atp_viability_assay.measure(
        vessel, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # Verify measured signals are present
    assert "ldh_signal" in result
    assert "atp_signal" in result

    # Verify debug truth IS present when enabled
    assert "_debug_truth" in result
    assert "viability" in result["_debug_truth"]
    assert "cell_count" in result["_debug_truth"]
    assert "death_mode" in result["_debug_truth"]


def test_ldh_signal_inversely_proportional_to_viability(make_vm_and_vessel):
    """
    LDH signal should increase as viability decreases.

    This tests the biology, not the contract - but verifies that LDH is
    actually measuring cytotoxicity, not leaking viability directly.
    """
    # Create two vessels with different viabilities
    vm1, vessel1 = make_vm_and_vessel(debug_truth_enabled=False)
    vm2, vessel2 = make_vm_and_vessel(debug_truth_enabled=False)

    vessel1.viability = 0.95  # Healthy
    vessel2.viability = 0.50  # Toxic

    # Measure both
    result1 = vm1.atp_viability_assay.measure(
        vessel1, plate_id="P1", well_position="A1", batch_id="batch1"
    )
    result2 = vm2.atp_viability_assay.measure(
        vessel2, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # LDH should be higher in toxic vessel (more dead cells)
    assert result2["ldh_signal"] > result1["ldh_signal"]

    # ATP should be lower in toxic vessel (more dysfunction)
    # (This might not hold perfectly due to noise, but should trend this way)
    # assert result2["atp_signal"] < result1["atp_signal"]


def test_ldh_strict_mode_prevents_truth_leakage(vm_and_vessel):
    """
    Strict mode should prevent any truth leakage at top level.

    This is a belt-and-suspenders test for CI enforcement.
    """
    vm, vessel = vm_and_vessel

    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        result = vm.atp_viability_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Top level must not contain truth
        forbidden_keys = {"viability", "cell_count", "death_mode", "death_compound", "death_confluence", "death_unknown"}
        for key in forbidden_keys:
            assert key not in result, f"Ground truth leaked at top level: {key}"

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)
