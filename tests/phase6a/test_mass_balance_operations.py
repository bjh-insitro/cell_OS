"""
Property-based tests for mass balance under operations.

These tests verify that conservation laws hold under various operations:
- Feed: Adding nutrients shouldn't violate death accounting
- Washout: Removing compounds shouldn't violate death accounting
- Time advancement: Evaporation/nutrient depletion maintains conservation

The key invariant is always: viable + Σ(death_fields) = 1.0 ± DEATH_EPS
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.constants import (
    DEATH_EPS,
    TRACKED_DEATH_FIELDS,
    DEFAULT_MEDIA_GLUCOSE_mM,
    DEFAULT_MEDIA_GLUTAMINE_mM,
)

# Import shared strategies
import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from strategies import (
    seed_strategy,
    reasonable_dose,
    reasonable_time,
    all_compounds,
    short_time,
)


def get_death_total(vessel) -> float:
    """Sum all tracked death modes."""
    return sum(getattr(vessel, f, 0.0) for f in TRACKED_DEATH_FIELDS)


def assert_conservation(vessel, tolerance=DEATH_EPS * 10):
    """Assert conservation law holds for vessel."""
    death_total = get_death_total(vessel)
    viable = vessel.viability
    accounting_sum = viable + death_total

    assert abs(accounting_sum - 1.0) < tolerance, (
        f"Conservation violated: viable={viable:.9f}, death_total={death_total:.9f}, "
        f"sum={accounting_sum:.9f}, expected=1.0"
    )


@pytest.mark.hypothesis
class TestConservationUnderFeed:
    """Test conservation holds after feeding operations."""

    @given(
        seed=seed_strategy,
        time_before_feed=st.floats(min_value=1.0, max_value=48.0),
        glucose=st.floats(min_value=5.0, max_value=50.0),
        glutamine=st.floats(min_value=1.0, max_value=10.0),
    )
    @settings(max_examples=20, deadline=10000)
    def test_feed_preserves_conservation(
        self, seed, time_before_feed, glucose, glutamine
    ):
        """Feeding vessel should not violate conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Let cells grow/deplete nutrients
        vm.advance_time(time_before_feed)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Feed the vessel
        vm.feed_vessel("P1_A01", glucose_mM=glucose, glutamine_mM=glutamine)

        # Conservation should still hold
        assert_conservation(vm.vessel_states["P1_A01"])

        # Advance more time after feeding
        vm.advance_time(12.0)
        assert_conservation(vm.vessel_states["P1_A01"])

    @given(
        seed=seed_strategy,
        n_feeds=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=15, deadline=15000)
    def test_multiple_feeds_preserve_conservation(self, seed, n_feeds):
        """Multiple feeding cycles should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        for i in range(n_feeds):
            # Time between feeds
            vm.advance_time(12.0)
            assert_conservation(vm.vessel_states["P1_A01"])

            # Feed
            vm.feed_vessel("P1_A01")
            assert_conservation(vm.vessel_states["P1_A01"])


@pytest.mark.hypothesis
class TestConservationUnderWashout:
    """Test conservation holds after washout operations."""

    @given(
        seed=seed_strategy,
        compound=all_compounds,
        dose=reasonable_dose,
        time_before_wash=st.floats(min_value=4.0, max_value=24.0),
    )
    @settings(max_examples=20, deadline=15000)
    def test_washout_preserves_conservation(
        self, seed, compound, dose, time_before_wash
    ):
        """Washing out compound should not violate conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Treat with compound
        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)
        vm.advance_time(time_before_wash)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Washout
        vm.washout_compound("P1_A01", compound)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Advance time after washout (stress should decay)
        vm.advance_time(12.0)
        assert_conservation(vm.vessel_states["P1_A01"])

    @given(
        seed=seed_strategy,
        compound1=all_compounds,
        compound2=all_compounds,
        dose1=reasonable_dose,
        dose2=reasonable_dose,
    )
    @settings(max_examples=15, deadline=20000)
    def test_sequential_treat_washout_cycles(
        self, seed, compound1, compound2, dose1, dose2
    ):
        """Multiple treat-washout cycles should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # First cycle
        vm.treat_with_compound("P1_A01", compound1, dose_uM=dose1)
        vm.advance_time(12.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        vm.washout_compound("P1_A01", compound1)
        vm.advance_time(6.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Second cycle
        vm.treat_with_compound("P1_A01", compound2, dose_uM=dose2)
        vm.advance_time(12.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        vm.washout_compound("P1_A01", compound2)
        vm.advance_time(6.0)
        assert_conservation(vm.vessel_states["P1_A01"])


@pytest.mark.hypothesis
class TestConservationUnderNutrientDepletion:
    """Test conservation as nutrients deplete over time."""

    @given(
        seed=seed_strategy,
        total_time=st.floats(min_value=24.0, max_value=96.0),
    )
    @settings(max_examples=15, deadline=15000)
    def test_long_term_depletion_conserves(self, seed, total_time):
        """Long-term nutrient depletion should maintain conservation."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Advance in chunks, checking conservation at each step
        n_steps = max(1, int(total_time / 12))
        for _ in range(n_steps):
            vm.advance_time(12.0)
            vessel = vm.vessel_states["P1_A01"]
            assert_conservation(vessel)

            # Verify viability bounds
            assert -DEATH_EPS <= vessel.viability <= 1.0 + DEATH_EPS

    @given(
        seed=seed_strategy,
        low_glucose=st.floats(min_value=0.5, max_value=2.0),
        low_glutamine=st.floats(min_value=0.1, max_value=0.5),
    )
    @settings(max_examples=15, deadline=15000)
    def test_starvation_conditions_conserve(self, seed, low_glucose, low_glutamine):
        """Even under starvation, conservation should hold."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Start with low nutrients
        vm.feed_vessel("P1_A01", glucose_mM=low_glucose, glutamine_mM=low_glutamine)

        # Let cells starve
        for _ in range(6):  # 72 hours total
            vm.advance_time(12.0)
            assert_conservation(vm.vessel_states["P1_A01"])


@pytest.mark.hypothesis
class TestConservationUnderCombinedOperations:
    """Test conservation under realistic multi-operation protocols."""

    @given(
        seed=seed_strategy,
        compound=all_compounds,
        dose=reasonable_dose,
    )
    @settings(max_examples=15, deadline=25000)
    def test_full_experimental_protocol(self, seed, compound, dose):
        """Realistic experimental protocol should maintain conservation throughout."""
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("P1_A01", "A549", 1e6)

        # Day 0: Seed and let attach
        vm.advance_time(4.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Day 0: Treat
        vm.treat_with_compound("P1_A01", compound, dose_uM=dose)

        # Day 1: First checkpoint
        vm.advance_time(24.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Day 1: Feed
        vm.feed_vessel("P1_A01")
        assert_conservation(vm.vessel_states["P1_A01"])

        # Day 2: Second checkpoint
        vm.advance_time(24.0)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Day 2: Washout if needed
        vm.washout_compound("P1_A01", compound)
        assert_conservation(vm.vessel_states["P1_A01"])

        # Day 3: Final checkpoint
        vm.advance_time(24.0)
        assert_conservation(vm.vessel_states["P1_A01"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
