"""
Test: Measurements cannot read treatment identity (compound names/doses).

All assays should be blinded to:
- vessel.compounds (compound identity and dose)
- vessel.compound_meta (EC50, hill slope, potency)
- vessel.compound_start_time (treatment timing details)

Assays CAN read:
- time_since_last_perturbation_h (temporal duration, not identity)
- Latent biological states (er_stress, mito_dysfunction, transport_dysfunction)

This prevents "the assay knows you're on drug X" leakage.
"""

import pytest
import os


def test_cell_painting_cannot_read_compounds(vm_and_vessel):
    """
    Cell Painting assay must not read vessel.compounds.

    Morphology should reflect latent biological states (ER stress, mito dysfunction),
    not compound identity.
    """
    vm, vessel = vm_and_vessel

    # Add compound treatment (forbidden to read)
    vessel.compounds = {"staurosporine": 1.0}  # 1 uM
    vessel.compound_start_time = {"staurosporine": 24.0}
    vessel.er_stress = 0.5  # Latent state (allowed to read)

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This should succeed without reading compounds
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify morphology is present
        assert "morphology" in result
        assert result["morphology"]["er"] > 0  # Should reflect ER stress, not compound name

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_ldh_cannot_read_compounds(vm_and_vessel):
    """
    LDH viability assay must not read vessel.compounds.

    LDH signal should scale with death fraction, not compound identity.
    """
    vm, vessel = vm_and_vessel

    # Add compound treatment
    vessel.compounds = {"tunicamycin": 5.0}  # 5 uM
    vessel.viability = 0.7  # Observable state (allowed)

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        result = vm.atp_viability_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        # Verify LDH signal is present
        assert "ldh_signal" in result
        assert result["ldh_signal"] > 0

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_scrna_cannot_read_compounds(vm_and_vessel):
    """
    scRNA-seq assay must not read vessel.compounds.

    Gene expression profiles should reflect biological states, not compound names.
    """
    vm, vessel = vm_and_vessel

    # Add compound treatment
    vessel.compounds = {"nocodazole": 0.5}  # 0.5 uM
    vessel.transport_dysfunction = 0.6  # Latent state (allowed)

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        result = vm.scrna_seq_assay.measure(vessel, plate_id="P1")

        # Verify result is valid
        assert result["status"] == "success"

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_measurements_can_read_temporal_durations(vm_and_vessel):
    """
    Measurements CAN read temporal durations (time since perturbation).

    This is allowed because it's observable (time elapsed), not identity.
    """
    vm, vessel = vm_and_vessel

    # Add compound with known start time
    vessel.compounds = {"drug_x": 1.0}
    vessel.compound_start_time = {"drug_x": 24.0}
    vessel.last_update_time = 48.0

    # Expected time since perturbation: 48 - 24 = 24 hours
    expected_duration = 24.0

    # Measurements can access time_since_last_perturbation_h
    assert vessel.time_since_last_perturbation_h == pytest.approx(expected_duration)

    # Enable strict mode
    os.environ["CELL_OS_STRICT_CAUSAL_CONTRACT"] = "1"

    try:
        # This should succeed - temporal duration is allowed
        result = vm.cell_painting_assay.measure(
            vessel, plate_id="P1", well_position="A1", batch_id="batch1"
        )

        assert "morphology" in result

    finally:
        os.environ.pop("CELL_OS_STRICT_CAUSAL_CONTRACT", None)


def test_measurements_use_latent_states_not_compounds(make_vm_and_vessel):
    """
    Measurements should use latent biological states, not compound identity.

    Two different compounds that cause ER stress should produce similar
    morphology because both elevate the ER stress latent variable.
    """
    # Create two vessels with different compounds but same latent state
    vm1, vessel1 = make_vm_and_vessel(debug_truth_enabled=False)
    vm2, vessel2 = make_vm_and_vessel(debug_truth_enabled=False)

    # Different compounds
    vessel1.compounds = {"tunicamycin": 5.0}
    vessel2.compounds = {"thapsigargin": 1.0}

    # Same latent ER stress
    vessel1.er_stress = 0.6
    vessel2.er_stress = 0.6

    # Measure both
    result1 = vm1.cell_painting_assay.measure(
        vessel1, plate_id="P1", well_position="A1", batch_id="batch1"
    )
    result2 = vm2.cell_painting_assay.measure(
        vessel2, plate_id="P1", well_position="A1", batch_id="batch1"
    )

    # ER channel should be similar (within noise) because latent state is same
    er1 = result1["morphology"]["er"]
    er2 = result2["morphology"]["er"]

    # Allow 50% difference due to measurement noise, but should be same order of magnitude
    ratio = max(er1, er2) / (min(er1, er2) + 1e-9)
    assert ratio < 2.0, f"ER morphology should be similar for same latent state: {er1} vs {er2}"
