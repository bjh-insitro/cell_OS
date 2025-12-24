"""
Unit tests: Imaging artifacts monotonicity and bounds

Tests core invariants for debris-driven imaging artifacts:
1. Monotonicity: more debris never improves quality
2. Bounds: multipliers and probabilities always clamped
3. Safeguards: zero/low counts don't cause explosions
"""

import pytest
import numpy as np
from src.cell_os.sim.imaging_artifacts_core import (
    compute_background_noise_multiplier,
    compute_segmentation_failure_probability_bump,
)


def test_background_noise_multiplier_monotonic():
    """More debris → higher multiplier (never improves signal)."""
    initial_cells = 3000.0

    # Test sequence with increasing debris
    debris_levels = [0.0, 300.0, 600.0, 1200.0, 2400.0, 3000.0]
    multipliers = []

    for debris in debris_levels:
        mult = compute_background_noise_multiplier(
            debris_cells=debris,
            initial_cells=initial_cells
        )
        multipliers.append(mult)

    # Multipliers should be monotonically increasing
    for i in range(len(multipliers) - 1):
        assert multipliers[i] <= multipliers[i+1], \
            f"Monotonicity violated: debris={debris_levels[i]} → {multipliers[i]}, " \
            f"debris={debris_levels[i+1]} → {multipliers[i+1]}"


def test_background_noise_multiplier_bounds():
    """Background noise multiplier always in [base, max]."""
    initial_cells = 3000.0

    # Zero debris → base multiplier
    mult_zero = compute_background_noise_multiplier(
        debris_cells=0.0,
        initial_cells=initial_cells,
        base_multiplier=1.0,
        max_multiplier=1.25
    )
    assert mult_zero == 1.0

    # Normal debris → between base and max
    mult_normal = compute_background_noise_multiplier(
        debris_cells=600.0,  # 20% of initial
        initial_cells=initial_cells,
        base_multiplier=1.0,
        max_multiplier=1.25
    )
    assert 1.0 <= mult_normal <= 1.25

    # Extreme debris → clamped at max
    mult_extreme = compute_background_noise_multiplier(
        debris_cells=30000.0,  # 10× initial (should never happen, but guard)
        initial_cells=initial_cells,
        base_multiplier=1.0,
        max_multiplier=1.25
    )
    assert mult_extreme == 1.25  # Clamped


def test_background_noise_multiplier_zero_initial_cells():
    """Zero initial_cells → graceful fallback to base multiplier."""
    mult = compute_background_noise_multiplier(
        debris_cells=100.0,
        initial_cells=0.0,  # Shouldn't happen, but guard
        base_multiplier=1.0
    )
    assert mult == 1.0  # Safe fallback


def test_segmentation_failure_probability_monotonic():
    """More debris → higher failure probability (never improves segmentation)."""
    adherent_cells = 5000.0

    # Test sequence with increasing debris
    debris_levels = [0.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]
    probabilities = []

    for debris in debris_levels:
        prob = compute_segmentation_failure_probability_bump(
            debris_cells=debris,
            adherent_cell_count=adherent_cells
        )
        probabilities.append(prob)

    # Probabilities should be monotonically increasing
    for i in range(len(probabilities) - 1):
        assert probabilities[i] <= probabilities[i+1], \
            f"Monotonicity violated: debris={debris_levels[i]} → {probabilities[i]:.4f}, " \
            f"debris={debris_levels[i+1]} → {probabilities[i+1]:.4f}"


def test_segmentation_failure_probability_bounds():
    """Segmentation failure probability always in [0, max]."""
    adherent_cells = 5000.0

    # Zero debris → base probability
    prob_zero = compute_segmentation_failure_probability_bump(
        debris_cells=0.0,
        adherent_cell_count=adherent_cells,
        base_probability=0.0,
        max_probability=0.5
    )
    assert prob_zero == 0.0

    # Normal debris → between 0 and max
    prob_normal = compute_segmentation_failure_probability_bump(
        debris_cells=1000.0,  # 20% of adherent
        adherent_cell_count=adherent_cells,
        base_probability=0.0,
        max_probability=0.5
    )
    assert 0.0 <= prob_normal <= 0.5

    # Extreme debris → clamped at max
    # 50000/5000 * 0.02 = 0.2, which is < 0.5, so need MORE extreme
    prob_extreme = compute_segmentation_failure_probability_bump(
        debris_cells=150000.0,  # 30× adherent
        adherent_cell_count=adherent_cells,
        base_probability=0.0,
        max_probability=0.5
    )
    # 150000/5000 * 0.02 = 0.6 → clamped to 0.5
    assert prob_extreme == 0.5  # Clamped


def test_segmentation_failure_low_cell_count_amplification():
    """Low cell count amplifies debris effect (debris-to-signal ratio)."""
    debris = 500.0

    # High cell count → low ratio → small effect
    prob_high_cells = compute_segmentation_failure_probability_bump(
        debris_cells=debris,
        adherent_cell_count=5000.0,  # 500/5000 = 10%
        debris_coefficient=0.02
    )

    # Low cell count → high ratio → larger effect
    prob_low_cells = compute_segmentation_failure_probability_bump(
        debris_cells=debris,
        adherent_cell_count=500.0,  # 500/500 = 100%
        debris_coefficient=0.02
    )

    # Low cells should have higher failure probability
    assert prob_low_cells > prob_high_cells


def test_segmentation_failure_very_low_cells():
    """Very low cell count → max probability (well is trashed)."""
    prob = compute_segmentation_failure_probability_bump(
        debris_cells=100.0,
        adherent_cell_count=1.0,  # Almost no cells left
        max_probability=0.5
    )
    assert prob == 0.5  # Clamped to max (well is unusable)


def test_parameter_customization():
    """Custom parameters respected (for tuning/testing)."""
    # Custom background noise parameters
    mult = compute_background_noise_multiplier(
        debris_cells=1000.0,
        initial_cells=1000.0,  # 100% debris ratio
        base_multiplier=1.5,   # Different base
        debris_coefficient=0.1,  # 2× default sensitivity
        max_multiplier=2.0     # Higher ceiling
    )

    expected = 1.5 + 0.1 * 1.0  # 1.5 + 0.1 = 1.6
    assert mult == pytest.approx(expected)

    # Custom segmentation failure parameters
    prob = compute_segmentation_failure_probability_bump(
        debris_cells=500.0,
        adherent_cell_count=1000.0,  # 50% debris ratio
        base_probability=0.05,       # Start at 5%
        debris_coefficient=0.04,     # 2× default sensitivity
        max_probability=0.8          # Higher ceiling
    )

    expected = 0.05 + 0.04 * 0.5  # 0.05 + 0.02 = 0.07
    assert prob == pytest.approx(expected)


def test_background_noise_typical_values():
    """Typical Cell Painting workflow produces reasonable multipliers."""
    initial_cells = 3000.0

    # Gentle workflow: ~3% loss, 20% becomes debris
    cells_lost_gentle = initial_cells * 0.03  # 90 cells
    debris_gentle = cells_lost_gentle * 0.20  # 18 debris
    mult_gentle = compute_background_noise_multiplier(
        debris_cells=debris_gentle,
        initial_cells=initial_cells
    )
    # 18/3000 * 0.05 = 0.0003, so mult = 1.0003 (negligible)
    assert 1.0 <= mult_gentle <= 1.001

    # Standard workflow: ~19% loss (from demo)
    debris_standard = initial_cells * 0.19 * 0.20  # 19% loss, 20% debris = 114 debris
    mult_standard = compute_background_noise_multiplier(
        debris_cells=debris_standard,
        initial_cells=initial_cells
    )
    # 114/3000 * 0.05 = 0.0019, so mult ≈ 1.002 (small)
    assert 1.001 <= mult_standard <= 1.005

    # Rough workflow: ~30% loss
    debris_rough = initial_cells * 0.30 * 0.20  # 180 debris
    mult_rough = compute_background_noise_multiplier(
        debris_cells=debris_rough,
        initial_cells=initial_cells
    )
    # 180/3000 * 0.05 = 0.003, so mult ≈ 1.003
    assert 1.002 <= mult_rough <= 1.01


def test_segmentation_failure_typical_values():
    """Typical Cell Painting workflow produces reasonable failure probabilities."""
    # Post-growth typical: 6000 cells
    adherent_cells = 6000.0

    # Standard workflow: 19% loss, 20% debris
    debris_standard = 1170.0 * 0.20  # From demo: 1169 cells lost → 234 debris
    prob_standard = compute_segmentation_failure_probability_bump(
        debris_cells=debris_standard,
        adherent_cell_count=adherent_cells
    )
    # 234/6000 * 0.02 = 0.00078, so prob ≈ 0.08% bump (small)
    assert prob_standard < 0.01  # Less than 1% bump

    # Rough workflow: more loss, fewer cells remaining
    adherent_rough = 4000.0  # Lower post-wash
    debris_rough = 2000.0 * 0.20  # 400 debris
    prob_rough = compute_segmentation_failure_probability_bump(
        debris_cells=debris_rough,
        adherent_cell_count=adherent_rough
    )
    # 400/4000 * 0.02 = 0.002, so prob ≈ 0.2% bump
    assert 0.001 <= prob_rough <= 0.01
