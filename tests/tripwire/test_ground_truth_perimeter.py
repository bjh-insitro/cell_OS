"""
Tripwire: Ground truth perimeter enforcement.

Tests that no hidden truth (death labels, internal params, latent states) leaks
into agent-facing outputs.

This is an epistemic security boundary. If these tests fail, agents can cheat
by reading privileged information that wouldn't exist in real experiments.
"""

import pytest
import numpy as np
from src.cell_os.contracts.ground_truth_policy import (
    assert_no_ground_truth,
    ALWAYS_FORBIDDEN_PATTERNS,
)


def test_cell_painting_no_ground_truth_leakage(make_vm_and_vessel):
    """
    Cell Painting measurement must not leak ground truth.

    Forbidden keys (from policy):
    - death_mode, death_compound (attribution labels)
    - er_stress, mito_dysfunction (latent states, not measured)
    - ic50_uM, hill_slope (internal compound params)
    - compounds_uM, compound_meta (exposure spine)
    - cell_count (cross-modal, Cell Painting uses confluence proxy)
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

    # Vessel is already initialized with fields from fixture
    # Manually set death_mode to simulate death (skip actual simulation)
    vessel.death_mode = "compound"
    vessel.death_compound = 0.8
    vessel.er_stress = 0.6
    vessel.mito_dysfunction = 0.3

    # Cell Painting measurement
    result = vm.cell_painting_assay.measure(vessel, well_position='A01', plate_id='P1')

    # Assert: no ground truth patterns anywhere in result tree
    assert_no_ground_truth(
        result,
        patterns=ALWAYS_FORBIDDEN_PATTERNS,
        modality="CellPaintingAssay",
        message="Cell Painting leaked ground truth"
    )


def test_ldh_viability_no_ground_truth_at_top_level(make_vm_and_vessel):
    """
    LDH measurement must not leak ground truth at top level.

    Ground truth (viability, cell_count, death labels) may ONLY appear in
    _debug_truth dict when debug_truth_enabled=True.
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

    # Set ground truth fields manually
    vessel.viability = 0.3
    vessel.cell_count = 5000.0
    vessel.death_mode = "compound"
    vessel.death_compound = 0.9

    # LDH measurement (debug OFF)
    result = vm.atp_viability_assay.measure(vessel, well_position='A01', plate_id='P1')

    # Top-level keys must not include ground truth
    forbidden_top_level = {'viability', 'cell_count', 'death_mode', 'death_compound'}
    leaked = forbidden_top_level & set(result.keys())
    assert not leaked, f"Ground truth leaked at top level: {leaked}"

    # _debug_truth must NOT be present when debug disabled
    assert "_debug_truth" not in result, "_debug_truth present when debug disabled"


def test_ldh_viability_debug_truth_gate_works(make_vm_and_vessel):
    """
    LDH can emit ground truth ONLY in _debug_truth dict when debug enabled.

    This is the allowed escape hatch for validation and debugging.
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=True)

    # Set ground truth fields manually
    vessel.viability = 0.2
    vessel.cell_count = 3000.0
    vessel.death_mode = "compound"
    vessel.death_compound = 0.95

    # LDH measurement (debug ON)
    result = vm.atp_viability_assay.measure(vessel, well_position='A01', plate_id='P1')

    # Top-level must still be clean
    forbidden_top_level = {'viability', 'cell_count', 'death_mode', 'death_compound'}
    leaked = forbidden_top_level & set(result.keys())
    assert not leaked, f"Ground truth leaked at top level even with debug: {leaked}"

    # _debug_truth MUST be present when debug enabled
    assert "_debug_truth" in result, "_debug_truth missing when debug enabled"

    # Ground truth MUST be inside _debug_truth
    debug_truth = result["_debug_truth"]
    assert "viability" in debug_truth, "viability missing from _debug_truth"
    assert "cell_count" in debug_truth, "cell_count missing from _debug_truth"
    assert "death_mode" in debug_truth, "death_mode missing from _debug_truth"


def test_scrna_seq_no_ground_truth_leakage(make_vm_and_vessel):
    """
    scRNA-seq measurement must not leak ground truth.

    Forbidden keys:
    - death_mode, death_compound (attribution labels)
    - cell_count (cross-modal, scRNA uses capturable_cells proxy)
    - compounds, compound_meta (treatment blinding)
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

    # Set stress state manually
    vessel.er_stress = 0.7
    vessel.mito_dysfunction = 0.2
    vessel.death_mode = "er_stress"

    # scRNA-seq measurement (use internal accessor, no well_position/plate_id needed)
    result = vm._scrna_seq_assay.measure(vessel, n_cells=100)

    # Assert: no ground truth patterns anywhere in result tree
    assert_no_ground_truth(
        result,
        patterns=ALWAYS_FORBIDDEN_PATTERNS,
        modality="scRNASeqAssay",
        message="scRNA-seq leaked ground truth"
    )


def test_nested_ground_truth_caught(make_vm_and_vessel):
    """
    Recursive validator must catch ground truth in nested dicts.

    This prevents leaks like:
        {"metadata": {"death_mode": "compound"}}
        {"qc": {"internal_params": {"ic50_uM": 10.0}}}
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

    # Manually construct a result dict with nested leak
    malicious_result = {
        "status": "success",
        "morphology": {"er": 10.0, "mito": 8.0},
        "metadata": {
            "well_id": "A01",
            "death_mode": "compound",  # LEAK: nested in metadata
        },
        "qc": {
            "flags": [],
            "internal_params": {
                "ic50_uM": 10.0,  # LEAK: nested in qc.internal_params
            }
        }
    }

    # Assert: validator catches nested leaks
    with pytest.raises(AssertionError, match="death_mode"):
        assert_no_ground_truth(
            malicious_result,
            patterns=ALWAYS_FORBIDDEN_PATTERNS,
            message="Test should catch nested leak"
        )

    with pytest.raises(AssertionError, match="ic50_uM"):
        assert_no_ground_truth(
            malicious_result,
            patterns=ALWAYS_FORBIDDEN_PATTERNS,
            message="Test should catch nested leak"
        )


def test_debug_truth_exception_works():
    """
    _debug_truth dict is exempt from ground truth ban.

    When debug_truth_enabled=True, LDH can emit {"_debug_truth": {"death_mode": ...}}
    This should NOT raise, even though death_mode is forbidden elsewhere.
    """
    allowed_result = {
        "status": "success",
        "ldh_signal": 75000.0,
        "_debug_truth": {
            "viability": 0.3,
            "cell_count": 5000.0,
            "death_mode": "compound",  # OK: inside _debug_truth
        }
    }

    # Should NOT raise (debug_truth is exempt)
    assert_no_ground_truth(
        allowed_result,
        patterns=ALWAYS_FORBIDDEN_PATTERNS,
        message="_debug_truth should be exempt"
    )


def test_dose_uM_is_not_banned():
    """
    dose_uM is NOT a ground truth leak (agent chose it).

    This test documents that we do NOT ban dose_uM globally, even though it
    looks sensitive. The agent selected the dose, so seeing it is memory,
    not leakage.
    """
    agent_memory = {
        "action": "treat",
        "compound": "paclitaxel",
        "dose_uM": 1.0,  # Agent-selected dose (NOT a leak)
        "well_id": "C05",
    }

    # Should NOT raise (dose_uM is allowed in agent action history)
    assert_no_ground_truth(
        agent_memory,
        patterns=ALWAYS_FORBIDDEN_PATTERNS,
        message="dose_uM should be allowed in agent context"
    )


def test_modality_specific_bans_enforced(make_vm_and_vessel):
    """
    Modality-specific bans (cross-modal privileged info) are enforced.

    Example: cell_count is forbidden for Cell Painting, but allowed for LDH.
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

    # Cell Painting result with cell_count (forbidden)
    cp_result = {
        "morphology": {"er": 10.0},
        "cell_count": 8000.0,  # LEAK: Cell Painting shouldn't see this
    }

    with pytest.raises(AssertionError, match="cell_count"):
        assert_no_ground_truth(
            cp_result,
            patterns=ALWAYS_FORBIDDEN_PATTERNS,
            modality="CellPaintingAssay",
            message="Cell Painting should not see cell_count"
        )

    # LDH result with cell_count inside _debug_truth (allowed if debug enabled)
    # Note: This test doesn't validate LDH contract, just that modality-specific
    # rules don't ban cell_count everywhere
