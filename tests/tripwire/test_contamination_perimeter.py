"""
Tripwire test: Contamination fields must never leak to measurements.

Validates that contamination labels (contaminated, contamination_type, etc.)
are forbidden from all agent-facing outputs.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext
from src.cell_os.contracts.ground_truth_policy import validate_no_ground_truth, ALWAYS_FORBIDDEN_PATTERNS


def test_cell_painting_no_contamination_leak():
    """
    Cell Painting must not leak contamination labels, even when contaminated.
    """
    vm = BiologicalVirtualMachine()
    vm.run_context = RunContext.sample(seed=42)
    vm.rng_assay = np.random.default_rng(1000)
    vm.rng_biology = np.random.default_rng(2000)
    vm._load_cell_thalamus_params()

    # Enable contamination
    vm.contamination_config = {
        'enabled': True,
        'baseline_rate_per_vessel_day': 0.0,  # Manual trigger only
    }

    vessel_id = "TestPlate_A01"
    vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
    vessel = vm.vessel_states[vessel_id]

    # Manually contaminate vessel (simulate operational event)
    vessel.contaminated = True
    vessel.contamination_type = "bacterial"
    vessel.contamination_onset_h = 24.0
    vessel.contamination_severity = 1.5
    vessel.contamination_phase = "death"

    # Advance time to trigger biological effects
    vm.advance_time(48.0)

    # Measure with Cell Painting
    result = vm._cell_painting_assay.measure(vessel, well_position='A01', plate_id='TestPlate')

    # Assert: No contamination labels leak
    validate_no_ground_truth(result, patterns=ALWAYS_FORBIDDEN_PATTERNS, modality="CellPaintingAssay")

    # Verify contamination fields explicitly forbidden
    assert 'contaminated' not in result
    assert 'contamination_type' not in result
    assert 'contamination_onset_h' not in result
    assert 'contamination_severity' not in result
    assert 'contamination_phase' not in result

    # Verify morphology is present (measurement happened)
    assert 'morphology' in result
    assert len(result['morphology']) == 5  # 5 channels: er, mito, nucleus, actin, rna


def test_ldh_viability_no_contamination_leak():
    """
    LDH viability assay must not leak contamination labels.
    """
    vm = BiologicalVirtualMachine()
    vm.run_context = RunContext.sample(seed=42)
    vm.rng_assay = np.random.default_rng(1000)
    vm.rng_biology = np.random.default_rng(2000)
    vm._load_cell_thalamus_params()

    vm.contamination_config = {'enabled': True, 'baseline_rate_per_vessel_day': 0.0}

    vessel_id = "TestPlate_A01"
    vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
    vessel = vm.vessel_states[vessel_id]

    # Contaminate
    vessel.contaminated = True
    vessel.contamination_type = "fungal"
    vessel.contamination_onset_h = 0.0
    vessel.contamination_severity = 1.0
    vessel.contamination_phase = "death"

    vm.advance_time(48.0)

    # Measure viability
    result = vm._ldh_viability_assay.measure(vessel, well_position='A01')

    # Assert: No contamination labels leak
    validate_no_ground_truth(result, patterns=ALWAYS_FORBIDDEN_PATTERNS, modality="LDHViabilityAssay")

    assert 'contaminated' not in result
    assert 'contamination_type' not in result


def test_contamination_affects_biology_not_measurement():
    """
    Contamination should affect biology (death hazards), not measurement code.

    Verify: contaminated vessels die more (biology), but measurements don't see labels.
    """
    # Clean vessel
    vm_clean = BiologicalVirtualMachine()
    vm_clean.run_context = RunContext.sample(seed=42)
    vm_clean.rng_assay = np.random.default_rng(1000)
    vm_clean.rng_biology = np.random.default_rng(2000)
    vm_clean._load_cell_thalamus_params()

    vessel_id = "P1_A01"
    vm_clean.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
    vm_clean.advance_time(48.0)
    viability_clean = vm_clean.vessel_states[vessel_id].viability

    # Contaminated vessel
    vm_contam = BiologicalVirtualMachine()
    vm_contam.run_context = RunContext.sample(seed=42)
    vm_contam.rng_assay = np.random.default_rng(1000)
    vm_contam.rng_biology = np.random.default_rng(2000)
    vm_contam._load_cell_thalamus_params()
    vm_contam.contamination_config = {'enabled': True, 'baseline_rate_per_vessel_day': 0.0}

    vessel_id = "P1_A01"
    vm_contam.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
    vessel_contam = vm_contam.vessel_states[vessel_id]

    # Manually contaminate with death phase
    vessel_contam.contaminated = True
    vessel_contam.contamination_type = "bacterial"
    vessel_contam.contamination_onset_h = 0.0
    vessel_contam.contamination_severity = 2.0
    vessel_contam.contamination_phase = "death"

    vm_contam.advance_time(48.0)
    viability_contam = vessel_contam.viability

    # Assert: Contamination affects viability (biology)
    assert viability_contam < viability_clean * 0.8, \
        f"Contamination should reduce viability (clean={viability_clean:.3f}, contam={viability_contam:.3f})"

    # Measure with Cell Painting - verify no label leak
    result = vm_contam._cell_painting_assay.measure(vessel_contam, well_position='A01', plate_id='P1')
    validate_no_ground_truth(result, patterns=ALWAYS_FORBIDDEN_PATTERNS, modality="CellPaintingAssay")

    # Morphology should differ (biology changed), but labels shouldn't leak
    assert 'contaminated' not in result
