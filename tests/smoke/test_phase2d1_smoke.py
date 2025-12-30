"""
Phase 2D.1: Contamination Events - Smoke Test

Quick sanity check that contamination integration doesn't crash.
Does NOT test correctness - just checks that the plumbing works.
"""
import pytest
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_contamination_disabled_by_default():
    """Contamination should be disabled by default (backward compatibility)."""
    vm = BiologicalVirtualMachine(seed=42)

    # Contamination config should be None (disabled)
    assert vm.contamination_config is None

    # Seed vessel and advance time (should not crash)
    vm.seed_vessel("well_A1", "A549", vessel_type="96-well", initial_count=5000)
    vm.advance_time(24.0)

    # Vessel should NOT be contaminated
    vessel = vm.vessel_states["well_A1"]
    assert vessel.contaminated == False
    assert vessel.death_contamination == 0.0


def test_contamination_enabled_basic():
    """Contamination can be enabled and doesn't crash."""
    vm = BiologicalVirtualMachine(seed=42)

    # Manually enable contamination (would normally come from thalamus_params)
    vm.contamination_config = {
        'enabled': True,
        'baseline_rate_per_vessel_day': 0.005,
        'type_probs': {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3},
        'severity_lognormal_cv': 0.5,
        'min_severity': 0.25,
        'max_severity': 3.0,
        'phase_params': {
            'bacterial': {'latent_h': 6, 'arrest_h': 6, 'death_rate_per_h': 0.4},
            'fungal': {'latent_h': 12, 'arrest_h': 12, 'death_rate_per_h': 0.2},
            'mycoplasma': {'latent_h': 24, 'arrest_h': 48, 'death_rate_per_h': 0.05},
        },
        'growth_arrest_multiplier': 0.05,
        'morphology_signature_strength': 1.0,
    }

    # Seed vessel and advance time (should not crash)
    vm.seed_vessel("well_A1", "A549", vessel_type="96-well", initial_count=5000)
    vm.advance_time(24.0)

    # Vessel should have contamination fields initialized
    vessel = vm.vessel_states["well_A1"]
    assert hasattr(vessel, 'contaminated')
    assert hasattr(vessel, 'death_contamination')
    assert vessel.death_contamination >= 0.0  # May or may not be contaminated (random event)


def test_contamination_fields_initialized():
    """All contamination VesselState fields should be initialized."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("well_A1", "A549", vessel_type="96-well", initial_count=5000)

    vessel = vm.vessel_states["well_A1"]

    # Check all Phase 2D.1 fields exist
    assert hasattr(vessel, 'contaminated')
    assert hasattr(vessel, 'contamination_type')
    assert hasattr(vessel, 'contamination_onset_h')
    assert hasattr(vessel, 'contamination_phase')
    assert hasattr(vessel, 'contamination_severity')
    assert hasattr(vessel, 'death_contamination')

    # Default values should be clean
    assert vessel.contaminated == False
    assert vessel.contamination_type is None
    assert vessel.contamination_onset_h is None
    assert vessel.contamination_phase is None
    assert vessel.contamination_severity is None
    assert vessel.death_contamination == 0.0


def test_conservation_includes_contamination():
    """Conservation checks should include death_contamination."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("well_A1", "A549", vessel_type="96-well", initial_count=5000)
    vessel = vm.vessel_states["well_A1"]

    # Manually set some death_contamination (would normally come from hazard proposals)
    vessel.death_contamination = 0.05
    vessel.viability = 0.95

    # This should NOT raise conservation violation (0.05 contamination = 0.05 total death)
    vm._assert_conservation(vessel, gate="test")

    # Death mode update should also work
    vm._update_death_mode(vessel)
    assert vessel.death_contamination == 0.05  # Should be preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
