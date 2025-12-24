"""
Test fixtures for contract enforcement tests.

Provides production-like vessel initialization to prevent fixture explosions.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine, VesselState
from src.cell_os.hardware.run_context import RunContext


@pytest.fixture
def make_vm_and_vessel():
    """
    Factory fixture for creating VM + vessel with all required fields.

    This fixture ensures vessels are initialized with all fields that assays
    might access, preventing AttributeError explosions during contract testing.
    """
    def _make(debug_truth_enabled: bool = False):
        # Create VM with run context
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=42)
        vm.run_context.debug_truth_enabled = debug_truth_enabled

        # Initialize RNG streams
        vm.rng_assay = np.random.default_rng(1001)
        vm.rng_biology = np.random.default_rng(1002)

        # Load thalamus params (lazy load will handle this, but we can pre-init)
        vm._load_cell_thalamus_params()

        # Expose assay instances for direct testing (bypass VM methods)
        vm.cell_painting_assay = vm._cell_painting_assay
        vm.atp_viability_assay = vm._ldh_viability_assay
        vm.scrna_seq_assay = vm._scrna_seq_assay

        # Create vessel with all required fields
        vessel = VesselState(vessel_id="test_vessel_1", cell_line="A549")
        vessel.cell_count = 10000
        vessel.viability = 0.95
        vessel.confluence = 0.8
        vessel.initial_cells = 10000
        vessel.well_position = "A1"

        # Latent stress states
        vessel.er_stress = 0.1
        vessel.mito_dysfunction = 0.05
        vessel.transport_dysfunction = 0.02
        vessel.contact_pressure = 0.3

        # Subpopulations
        vessel.subpopulations = {
            'typical': {'fraction': 0.85, 'viability': 0.95},
            'resistant': {'fraction': 0.10, 'viability': 0.98},
            'sensitive': {'fraction': 0.05, 'viability': 0.85},
        }

        # Persistent well biology
        rng_well = np.random.default_rng(42)
        vessel.well_biology = {
            "er_baseline_shift": float(rng_well.normal(0.0, 0.08)),
            "mito_baseline_shift": float(rng_well.normal(0.0, 0.10)),
            "rna_baseline_shift": float(rng_well.normal(0.0, 0.06)),
            "nucleus_baseline_shift": float(rng_well.normal(0.0, 0.04)),
            "actin_baseline_shift": float(rng_well.normal(0.0, 0.05)),
            "stress_susceptibility": float(rng_well.lognormal(mean=0.0, sigma=0.15)),
        }

        # Temporal state
        vessel.last_update_time = 48.0
        vessel.seed_time = 0.0
        vessel.compound_start_time = {}  # No compounds

        # Measurement artifacts
        vessel.last_washout_time = None
        vessel.washout_artifact_until_time = None
        vessel.washout_artifact_magnitude = 0.0
        vessel.plating_context = {
            'seeding_density_error': 0.0,
            'post_dissociation_stress': 0.0,
            'clumpiness': 0.0,
            'tau_recovery_h': 12.0,
        }

        # Debris and handling
        vessel.debris_cells = 0.0
        vessel.cells_lost_to_handling = 0.0
        vessel.edge_damage_score = 0.0

        # Death labels (ground truth)
        vessel.death_mode = None
        vessel.death_compound = None
        vessel.death_confluence = None
        vessel.death_unknown = 0.0

        # Treatment state (forbidden)
        vessel.compounds = {}  # Empty - no treatments
        vessel.compound_meta = {}

        return vm, vessel

    return _make


@pytest.fixture
def vm_and_vessel(make_vm_and_vessel):
    """Convenience fixture for non-debug tests."""
    return make_vm_and_vessel(debug_truth_enabled=False)


@pytest.fixture
def vm_and_vessel_debug(make_vm_and_vessel):
    """Convenience fixture for debug truth tests."""
    return make_vm_and_vessel(debug_truth_enabled=True)
