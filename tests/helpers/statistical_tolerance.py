"""
Statistical tolerance utilities for stochastic tests (Issue #10).

Provides utilities for writing tests that are robust to random variation:
1. Multi-trial assertions that pass if K of N trials succeed
2. Statistical range checks with confidence intervals
3. Seed-diverse testing utilities

USAGE GUIDE (for test authors):
================================

When to use these utilities:
1. Tests with hardcoded success rates like `assert 0.8 <= rate <= 1.0`
2. Tests that occasionally fail due to random variation
3. Tests comparing variances or distributions across conditions
4. Any test that might be seed-sensitive

Example: Converting a brittle test to use multi-trial:

BEFORE (brittle):
    def test_classifier_accuracy():
        result = classifier.predict(noisy_data)
        assert result == expected  # Fails ~10% of time due to noise

AFTER (robust):
    from tests.helpers.statistical_tolerance import assert_passes_k_of_n

    def test_classifier_accuracy():
        result = assert_passes_k_of_n(
            lambda: classifier.predict(noisy_data) == expected,
            n_trials=10,
            min_successes=8  # 80% success rate required
        )
        assert result.passed, str(result)

Tests that SHOULD use these utilities (TODO for test authors):
- tests/phase6a/test_state_dependent_noise.py - variance comparisons
- tests/phase6a/test_multiplicative_noise.py - noise distribution tests
- tests/phase6a/test_run_context_variability.py - seed sensitivity tests
- Any test with `@pytest.mark.flaky` or similar annotations
"""

import numpy as np
from typing import Callable, Any, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MultiTrialResult:
    """Result of a multi-trial test."""
    passed: bool
    successes: int
    trials: int
    success_rate: float
    required_rate: float
    failures: List[str]

    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"MultiTrialResult({status}: {self.successes}/{self.trials} "
            f"({self.success_rate:.0%} >= {self.required_rate:.0%} required))"
        )


def assert_passes_k_of_n(
    test_fn: Callable[[], bool],
    n_trials: int = 10,
    min_successes: int = 8,
    seed_offset: int = 0,
) -> MultiTrialResult:
    """Run test multiple times, pass if K of N trials succeed.

    Use this for tests that may fail occasionally due to random variation.

    Args:
        test_fn: Function returning True if test passes
        n_trials: Number of trials to run
        min_successes: Minimum successes required to pass
        seed_offset: Offset added to seed for reproducibility

    Returns:
        MultiTrialResult with outcome

    Example:
        def test_classification_accuracy():
            # This test might fail 10-20% of time due to noise
            result = assert_passes_k_of_n(
                lambda: classifier.predict(data) == expected,
                n_trials=10,
                min_successes=8
            )
            assert result.passed, str(result)
    """
    successes = 0
    failures = []

    for i in range(n_trials):
        try:
            if test_fn():
                successes += 1
            else:
                failures.append(f"Trial {i}: returned False")
        except AssertionError as e:
            failures.append(f"Trial {i}: {str(e)[:100]}")

    success_rate = successes / n_trials
    required_rate = min_successes / n_trials
    passed = successes >= min_successes

    return MultiTrialResult(
        passed=passed,
        successes=successes,
        trials=n_trials,
        success_rate=success_rate,
        required_rate=required_rate,
        failures=failures[:5],  # Keep first 5 failures
    )


def assert_in_statistical_range(
    value: float,
    expected_mean: float,
    expected_std: float,
    n_sigma: float = 3.0,
    name: str = "value",
) -> None:
    """Assert value is within n-sigma of expected.

    Args:
        value: Observed value
        expected_mean: Expected mean
        expected_std: Expected standard deviation
        n_sigma: Number of standard deviations for tolerance (default: 3)
        name: Name for error message

    Raises:
        AssertionError: If value outside range
    """
    low = expected_mean - n_sigma * expected_std
    high = expected_mean + n_sigma * expected_std

    if not (low <= value <= high):
        raise AssertionError(
            f"{name}={value:.4f} outside {n_sigma}-sigma range "
            f"[{low:.4f}, {high:.4f}] (mean={expected_mean:.4f}, std={expected_std:.4f})"
        )


def assert_proportion_in_range(
    successes: int,
    trials: int,
    expected_p: float,
    alpha: float = 0.01,
    name: str = "proportion",
) -> None:
    """Assert observed proportion is consistent with expected (binomial CI).

    Uses normal approximation for large n.

    Args:
        successes: Number of successes
        trials: Number of trials
        expected_p: Expected probability
        alpha: Significance level (default: 0.01 for 99% CI)
        name: Name for error message
    """
    from scipy import stats

    observed_p = successes / trials

    # Normal approximation CI
    se = np.sqrt(expected_p * (1 - expected_p) / trials)
    z = stats.norm.ppf(1 - alpha / 2)

    low = expected_p - z * se
    high = expected_p + z * se

    if not (low <= observed_p <= high):
        raise AssertionError(
            f"{name}={observed_p:.3f} ({successes}/{trials}) outside "
            f"{100*(1-alpha):.0f}% CI [{low:.3f}, {high:.3f}] for p={expected_p:.3f}"
        )


def run_with_multiple_seeds(
    test_fn: Callable[[int], Any],
    seeds: List[int] = None,
    min_pass_rate: float = 0.9,
) -> MultiTrialResult:
    """Run test with multiple seeds, pass if enough succeed.

    Args:
        test_fn: Function taking seed and returning True if passes
        seeds: List of seeds (default: [42, 123, 456, 789, 1001])
        min_pass_rate: Minimum fraction that must pass (default: 0.9)

    Returns:
        MultiTrialResult with outcome
    """
    if seeds is None:
        seeds = [42, 123, 456, 789, 1001]

    successes = 0
    failures = []

    for seed in seeds:
        try:
            if test_fn(seed):
                successes += 1
            else:
                failures.append(f"Seed {seed}: returned False")
        except AssertionError as e:
            failures.append(f"Seed {seed}: {str(e)[:100]}")

    n_trials = len(seeds)
    min_successes = int(np.ceil(min_pass_rate * n_trials))
    success_rate = successes / n_trials
    passed = successes >= min_successes

    return MultiTrialResult(
        passed=passed,
        successes=successes,
        trials=n_trials,
        success_rate=success_rate,
        required_rate=min_pass_rate,
        failures=failures[:5],
    )
