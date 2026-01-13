"""
Property-based tests for monotonicity invariants.

These tests verify that certain properties only change in one direction:
- Death fields: monotone non-decreasing (death accumulates, never reverses)
- Viability: monotone non-increasing under stress (cells don't spontaneously revive)

These are fundamental biological constraints that must hold regardless of
the specific treatment protocol or simulation parameters.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.constants import DEATH_EPS, TRACKED_DEATH_FIELDS

# Import shared strategies
import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from strategies import (
    seed_strategy,
    treatment_protocol,
    reasonable_dose,
    reasonable_time,
    all_compounds,
)


@pytest.mark.hypothesis
class TestDeathFieldMonotonicity:
    """Test that death fields are monotone non-decreasing."""

    @given(
        seed=seed_strategy,
        compound=all_compounds,
        dose=reasonable_dose,
        time_h=reasonable_time,
    )
    @settings(max_examples=25, deadline=10000)
    def test_death_fields_never_decrease_single_treatment(
        self, seed, compound, dose, time_h
    ):
        """Death fields should never decrease during treatment."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)
        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)

        # Track death fields over time
        prev_deaths = {f: 0.0 for f in TRACKED_DEATH_FIELDS}
        n_steps = max(1, int(time_h))

        for _ in range(n_steps):
            vm.advance_time(1.0)
            vessel = vm.vessel_states["P1_A01"]

            for field in TRACKED_DEATH_FIELDS:
                current = getattr(vessel, field, 0.0)
                assert current >= prev_deaths[field] - DEATH_EPS, (
                    f"Monotonicity violated: {field} decreased from "
                    f"{prev_deaths[field]:.9f} to {current:.9f}"
                )
                prev_deaths[field] = current

    @given(
        seed=seed_strategy,
        compound1=all_compounds,
        compound2=all_compounds,
        dose1=reasonable_dose,
        dose2=reasonable_dose,
    )
    @settings(max_examples=15, deadline=15000)
    def test_death_fields_monotone_across_treatments(
        self, seed, compound1, compound2, dose1, dose2
    ):
        """Death fields should remain monotone across sequential treatments."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        prev_deaths = {f: 0.0 for f in TRACKED_DEATH_FIELDS}

        # First treatment
        vm.treat_with_compound("P1_A01", compound1, dose_uM=dose1)
        vm.advance_time(12.0)

        vessel = vm.vessel_states["P1_A01"]
        for field in TRACKED_DEATH_FIELDS:
            current = getattr(vessel, field, 0.0)
            assert current >= prev_deaths[field] - DEATH_EPS
            prev_deaths[field] = current

        # Second treatment
        vm.treat_with_compound("P1_A01", compound2, dose_uM=dose2)
        vm.advance_time(12.0)

        vessel = vm.vessel_states["P1_A01"]
        for field in TRACKED_DEATH_FIELDS:
            current = getattr(vessel, field, 0.0)
            assert current >= prev_deaths[field] - DEATH_EPS, (
                f"Monotonicity violated after second treatment: {field} "
                f"decreased from {prev_deaths[field]:.9f} to {current:.9f}"
            )


@pytest.mark.hypothesis
class TestViabilityMonotonicity:
    """Test that viability is monotone non-increasing under continuous stress."""

    @given(
        seed=seed_strategy,
        compound=all_compounds,
        dose=st.floats(min_value=10.0, max_value=500.0),  # Meaningful dose
    )
    @settings(max_examples=20, deadline=10000)
    def test_viability_decreases_or_stable_under_stress(self, seed, compound, dose):
        """Viability should not spontaneously increase under stress."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)
        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)

        prev_viability = 1.0
        tolerance = DEATH_EPS * 100  # Allow small numerical noise

        for _ in range(24):  # 24 hours in 1h steps
            vm.advance_time(1.0)
            vessel = vm.vessel_states["P1_A01"]

            # Viability should not increase beyond tolerance
            assert vessel.viability <= prev_viability + tolerance, (
                f"Viability increased: {prev_viability:.6f} -> {vessel.viability:.6f}"
            )
            prev_viability = vessel.viability

    @given(
        seed=seed_strategy,
        dose=st.floats(min_value=50.0, max_value=1000.0),  # High dose
        time_h=st.floats(min_value=24.0, max_value=72.0),  # Long time
    )
    @settings(max_examples=15, deadline=10000)
    def test_high_stress_viability_trends_down(self, seed, dose, time_h):
        """Under high stress, viability should trend downward (not necessarily monotone due to dt)."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Use a potent compound
        vm.treat_with_compound("P1_A01", "staurosporine", dose_uM=dose)

        initial_viability = vm.vessel_states["P1_A01"].viability
        vm.advance_time(time_h)
        final_viability = vm.vessel_states["P1_A01"].viability

        # Final should be less than or equal to initial (with tolerance)
        assert final_viability <= initial_viability + DEATH_EPS * 10, (
            f"Viability increased under high stress: "
            f"{initial_viability:.6f} -> {final_viability:.6f}"
        )


@pytest.mark.hypothesis
class TestStressFieldMonotonicity:
    """Test that certain stress fields are monotone under specific conditions."""

    @given(
        seed=seed_strategy,
        time_h=st.floats(min_value=1.0, max_value=48.0),
    )
    @settings(max_examples=15, deadline=10000)
    def test_nutrient_depletion_increases_over_time(self, seed, time_h):
        """Without feeding, nutrient levels should decrease (stress increases)."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Get initial nutrient levels
        vessel = vm.vessel_states["P1_A01"]
        initial_glucose = getattr(vessel, "glucose_mM", 25.0)

        # Advance time without feeding
        n_steps = max(1, int(time_h / 4))
        for _ in range(n_steps):
            vm.advance_time(4.0)

        vessel = vm.vessel_states["P1_A01"]
        final_glucose = getattr(vessel, "glucose_mM", 25.0)

        # Glucose should decrease (or stay same if consumption is 0)
        assert final_glucose <= initial_glucose + DEATH_EPS, (
            f"Glucose increased without feeding: {initial_glucose:.2f} -> {final_glucose:.2f}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
