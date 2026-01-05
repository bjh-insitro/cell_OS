"""
Property-based tests for conservation laws using Hypothesis.

These tests generate random scenarios and verify that invariants hold:
1. Death conservation: viable + Σ(death_modes) = 1.0 ± DEATH_EPS
2. All death is attributed (no silent renormalization)
3. Viability bounds: 0.0 ≤ viability ≤ 1.0

Unlike example-based tests, these explore the edge case space automatically.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from cell_os.hardware.biological_virtual import (
    BiologicalVirtualMachine,
    DEATH_EPS,
    TRACKED_DEATH_FIELDS,
)


# Strategies for generating test inputs
reasonable_dose = st.floats(min_value=0.01, max_value=100.0, allow_nan=False)
reasonable_time = st.floats(min_value=0.1, max_value=72.0, allow_nan=False)
seed_value = st.integers(min_value=0, max_value=100000)

# Compound names from the simulation (excluding DMSO - it's a control, not a treatment)
compound_names = st.sampled_from([
    "tBHQ", "H2O2", "tunicamycin", "thapsigargin",
    "rotenone", "staurosporine", "paclitaxel", "nocodazole"
])

# Cell lines
cell_lines = st.sampled_from(["A549", "HepG2"])


def get_death_total(vessel) -> float:
    """Sum all tracked death modes."""
    total = 0.0
    for field in TRACKED_DEATH_FIELDS:
        total += getattr(vessel, field, 0.0)
    return total


def assert_conservation(vessel, tolerance=DEATH_EPS * 10):
    """Assert conservation law holds for vessel."""
    death_total = get_death_total(vessel)
    viable = vessel.viability

    # Conservation: viable + death_total should equal 1.0
    accounting_sum = viable + death_total

    assert abs(accounting_sum - 1.0) < tolerance, (
        f"Conservation violated: viable={viable:.9f}, death_total={death_total:.9f}, "
        f"sum={accounting_sum:.9f}, expected=1.0, diff={abs(accounting_sum - 1.0):.2e}"
    )

    # Viability bounds
    assert -DEATH_EPS <= viable <= 1.0 + DEATH_EPS, (
        f"Viability out of bounds: {viable}"
    )

    # Death bounds (each mode should be non-negative)
    for field in TRACKED_DEATH_FIELDS:
        val = getattr(vessel, field, 0.0)
        assert val >= -DEATH_EPS, f"{field} is negative: {val}"


class TestConservationUnderTreatment:
    """Test conservation holds after compound treatment."""

    @given(
        seed=seed_value,
        compound=compound_names,
        dose=reasonable_dose,
        time_h=reasonable_time
    )
    @settings(max_examples=25, deadline=5000)  # Reduced for CI speed
    def test_single_treatment_conserves(self, seed, compound, dose, time_h):
        """Single compound treatment should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        # Use proper plate_well format: P1_A01
        vm.seed_vessel("P1_A01", "A549", 1e6)

        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)
        vm.advance_time(time_h)

        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)

    @given(
        seed=seed_value,
        compound1=compound_names,
        compound2=compound_names,
        dose1=reasonable_dose,
        dose2=reasonable_dose,
        time1=st.floats(min_value=0.5, max_value=24.0),
        time2=st.floats(min_value=0.5, max_value=24.0)
    )
    @settings(max_examples=15, deadline=10000)  # Reduced for CI speed
    def test_sequential_treatments_conserve(
        self, seed, compound1, compound2, dose1, dose2, time1, time2
    ):
        """Multiple sequential treatments should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # First treatment
        vm.treat_with_compound("P1_A01", compound1, dose_uM=dose1)
        vm.advance_time(time1)
        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)

        # Second treatment
        vm.treat_with_compound("P1_A01", compound2, dose_uM=dose2)
        vm.advance_time(time2)
        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)


class TestConservationUnderStress:
    """Test conservation holds under extreme stress conditions."""

    @given(
        seed=seed_value,
        dose=st.floats(min_value=50.0, max_value=1000.0),  # High dose
        time_h=st.floats(min_value=24.0, max_value=72.0)   # Long time
    )
    @settings(max_examples=15, deadline=5000)  # Reduced for CI speed
    def test_high_dose_long_time_conserves(self, seed, dose, time_h):
        """High dose + long time (near-total kill) should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Use a potent compound
        vm.treat_with_compound("P1_A01", "staurosporine", dose_uM=dose)
        vm.advance_time(time_h)

        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)

        # Viability should be low but conservation must hold
        # (This tests the edge case where nearly all cells are dead)

    @given(
        seed=seed_value,
        initial_viability=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=15, deadline=5000)  # Reduced for CI speed
    def test_partial_viability_seeding_conserves(self, seed, initial_viability):
        """Seeding with partial viability should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6, initial_viability=initial_viability)

        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)

        # Advance time without treatment
        vm.advance_time(24.0)
        vessel = vm.vessel_states["P1_A01"]
        assert_conservation(vessel)


class TestConservationAcrossMultipleWells:
    """Test conservation holds independently for multiple wells."""

    @given(
        seed=seed_value,
        n_wells=st.integers(min_value=2, max_value=10),
        doses=st.lists(reasonable_dose, min_size=2, max_size=10)
    )
    @settings(max_examples=10, deadline=10000)  # Reduced for CI speed
    def test_multiple_wells_independent_conservation(self, seed, n_wells, doses):
        """Each well should independently maintain conservation."""
        assume(len(doses) >= n_wells)

        vm = BiologicalVirtualMachine(seed=seed)

        # Generate well IDs like P1_A01, P1_A02, etc.
        well_ids = [f"P1_A{i+1:02d}" for i in range(n_wells)]

        # Seed multiple wells
        for well_id in well_ids:
            vm.seed_vessel(well_id, "A549", 1e6)

        # Treat each with different doses
        for i, well_id in enumerate(well_ids):
            vm.treat_with_compound(well_id, "tunicamycin", dose_uM=doses[i])

        vm.advance_time(24.0)

        # Check conservation for each well
        for well_id in well_ids:
            vessel = vm.vessel_states[well_id]
            assert_conservation(vessel)


class TestDeathModeAttribution:
    """Test that death is always attributed to specific modes."""

    @given(
        seed=seed_value,
        compound=compound_names,
        dose=reasonable_dose,
        time_h=reasonable_time
    )
    @settings(max_examples=15, deadline=5000)  # Reduced for CI speed
    def test_all_death_attributed(self, seed, compound, dose, time_h):
        """All death should be attributed to tracked modes, not lost."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)
        vm.advance_time(time_h)

        vessel = vm.vessel_states["P1_A01"]

        # Calculate expected death
        expected_death = 1.0 - vessel.viability
        actual_death = get_death_total(vessel)

        # All death should be attributed
        assert abs(expected_death - actual_death) < DEATH_EPS * 100, (
            f"Death attribution mismatch: expected={expected_death:.9f}, "
            f"attributed={actual_death:.9f}"
        )


class TestConservationDeterminism:
    """Test that conservation is deterministic with same seed."""

    @given(seed=seed_value, dose=reasonable_dose, time_h=reasonable_time)
    @settings(max_examples=10, deadline=10000)  # Reduced for CI speed
    def test_same_seed_same_result(self, seed, dose, time_h):
        """Same seed should produce identical conservation state."""
        results = []

        for _ in range(2):
            vm = BiologicalVirtualMachine(seed=seed)
            vm.seed_vessel("P1_A01", "A549", 1e6)
            vm.treat_with_compound("P1_A01", "tunicamycin", dose_uM=dose)
            vm.advance_time(time_h)

            vessel = vm.vessel_states["P1_A01"]
            results.append({
                "viability": vessel.viability,
                "death_total": get_death_total(vessel)
            })

        # Results should be identical
        assert results[0]["viability"] == results[1]["viability"], (
            f"Non-deterministic viability: {results[0]['viability']} vs {results[1]['viability']}"
        )
        assert results[0]["death_total"] == results[1]["death_total"], (
            f"Non-deterministic death: {results[0]['death_total']} vs {results[1]['death_total']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
