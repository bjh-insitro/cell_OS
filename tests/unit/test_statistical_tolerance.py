"""
Tests for statistical tolerance utilities (Issue #10).
"""

import pytest
import numpy as np

# Add helpers to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))

from statistical_tolerance import (
    assert_passes_k_of_n,
    assert_in_statistical_range,
    assert_proportion_in_range,
    run_with_multiple_seeds,
    MultiTrialResult,
)


class TestMultiTrialAssertion:
    """Test assert_passes_k_of_n."""

    def test_all_pass(self):
        """All trials pass -> overall pass."""
        result = assert_passes_k_of_n(lambda: True, n_trials=5, min_successes=5)
        assert result.passed
        assert result.successes == 5
        assert result.success_rate == 1.0

    def test_all_fail(self):
        """All trials fail -> overall fail."""
        result = assert_passes_k_of_n(lambda: False, n_trials=5, min_successes=3)
        assert not result.passed
        assert result.successes == 0

    def test_partial_pass(self):
        """8/10 pass when 8 required -> overall pass."""
        counter = [0]
        def sometimes_pass():
            counter[0] += 1
            return counter[0] <= 8  # First 8 pass

        result = assert_passes_k_of_n(sometimes_pass, n_trials=10, min_successes=8)
        assert result.passed
        assert result.successes == 8

    def test_partial_fail(self):
        """7/10 pass when 8 required -> overall fail."""
        counter = [0]
        def sometimes_pass():
            counter[0] += 1
            return counter[0] <= 7  # First 7 pass

        result = assert_passes_k_of_n(sometimes_pass, n_trials=10, min_successes=8)
        assert not result.passed
        assert result.successes == 7


class TestStatisticalRange:
    """Test assert_in_statistical_range."""

    def test_value_at_mean(self):
        """Value at mean passes."""
        assert_in_statistical_range(100.0, expected_mean=100.0, expected_std=10.0)

    def test_value_within_range(self):
        """Value within 3-sigma passes."""
        assert_in_statistical_range(120.0, expected_mean=100.0, expected_std=10.0, n_sigma=3)

    def test_value_outside_range(self):
        """Value outside 3-sigma fails."""
        with pytest.raises(AssertionError) as exc:
            assert_in_statistical_range(150.0, expected_mean=100.0, expected_std=10.0, n_sigma=3)
        assert "outside" in str(exc.value)

    def test_custom_n_sigma(self):
        """Custom n_sigma works."""
        # Within 2-sigma
        assert_in_statistical_range(115.0, expected_mean=100.0, expected_std=10.0, n_sigma=2)
        # Outside 1-sigma
        with pytest.raises(AssertionError):
            assert_in_statistical_range(115.0, expected_mean=100.0, expected_std=10.0, n_sigma=1)


class TestProportionRange:
    """Test assert_proportion_in_range."""

    def test_expected_proportion(self):
        """Observed matches expected."""
        assert_proportion_in_range(50, 100, expected_p=0.5)

    def test_reasonable_deviation(self):
        """Small deviation from expected passes."""
        assert_proportion_in_range(55, 100, expected_p=0.5, alpha=0.01)

    def test_extreme_deviation(self):
        """Extreme deviation fails."""
        with pytest.raises(AssertionError):
            assert_proportion_in_range(80, 100, expected_p=0.5, alpha=0.01)


class TestMultipleSeedsRunner:
    """Test run_with_multiple_seeds."""

    def test_all_seeds_pass(self):
        """All seeds pass -> overall pass."""
        result = run_with_multiple_seeds(lambda seed: True)
        assert result.passed

    def test_seed_dependent(self):
        """Seed-dependent test captures failures."""
        # Pass for even seeds only
        result = run_with_multiple_seeds(
            lambda seed: seed % 2 == 0,
            seeds=[2, 4, 6, 8, 10],  # All even
        )
        assert result.passed

        result = run_with_multiple_seeds(
            lambda seed: seed % 2 == 0,
            seeds=[1, 3, 5, 7, 9],  # All odd
        )
        assert not result.passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
