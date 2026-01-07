#!/usr/bin/env python3
"""
Unit Tests: Structured Imaging Artifacts

Tests the structured artifact extensions to imaging_artifacts_core:
1. Segmentation failure modes (merge/split)
2. Channel-weighted background multipliers
3. Spatial debris field

These are PURE MATH tests - no VM, no vessels, just function invariants.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

import pytest
import numpy as np
from cell_os.sim.imaging_artifacts_core import (
    compute_segmentation_failure_modes,
    compute_background_multipliers_by_channel,
    compute_debris_field_modifiers,
)


# =============================================================================
# SEGMENTATION FAILURE MODES TESTS
# =============================================================================

def test_segmentation_modes_monotonicity():
    """
    More debris → higher p_merge and p_split (monotonic).

    Invariant: Increasing debris_cells should never decrease failure probabilities.
    """
    adherent_cells = 5000.0
    confluence = 0.5

    # Test sequence with increasing debris
    debris_levels = [0.0, 100.0, 500.0, 1000.0, 2000.0]

    prev_p_merge = 0.0
    prev_p_split = 0.0

    for debris in debris_levels:
        result = compute_segmentation_failure_modes(
            debris_cells=debris,
            adherent_cell_count=adherent_cells,
            confluence=confluence
        )

        p_merge = result['p_merge']
        p_split = result['p_split']

        # Monotonicity: more debris → higher probabilities
        assert p_merge >= prev_p_merge, f"p_merge not monotonic: {p_merge} < {prev_p_merge}"
        assert p_split >= prev_p_split, f"p_split not monotonic: {p_split} < {prev_p_split}"

        prev_p_merge = p_merge
        prev_p_split = p_split


def test_segmentation_modes_bounds():
    """
    Probabilities and severities clamped to ranges.

    Invariants:
    - p_merge, p_split in [0, 0.4]
    - merge_severity, split_severity in [2.0, 3.0]
    """
    # Extreme debris scenario (should clamp)
    result_extreme = compute_segmentation_failure_modes(
        debris_cells=50000.0,  # 10× adherent
        adherent_cell_count=5000.0,
        confluence=0.9
    )

    assert 0.0 <= result_extreme['p_merge'] <= 0.4
    assert 0.0 <= result_extreme['p_split'] <= 0.4
    assert 2.0 <= result_extreme['merge_severity'] <= 3.0
    assert 2.0 <= result_extreme['split_severity'] <= 3.0

    # Zero debris (should give zeros)
    result_zero = compute_segmentation_failure_modes(
        debris_cells=0.0,
        adherent_cell_count=5000.0,
        confluence=0.5
    )

    assert result_zero['p_merge'] == 0.0
    assert result_zero['p_split'] == 0.0
    assert 2.0 <= result_zero['merge_severity'] <= 3.0  # Severity still bounded
    assert 2.0 <= result_zero['split_severity'] <= 3.0


def test_segmentation_modes_max_total_renormalization():
    """
    p_merge + p_split <= max_total, renormalized preserving ratio.

    Invariant: Total failure probability never exceeds max_total.
    If raw sum exceeds max_total, probabilities are renormalized proportionally.
    """
    # High debris + high confluence → likely to exceed max_total
    result = compute_segmentation_failure_modes(
        debris_cells=10000.0,  # 2× adherent
        adherent_cell_count=5000.0,
        confluence=0.95,
        max_total=0.3  # Tight budget
    )

    total = result['p_merge'] + result['p_split']

    # Total must not exceed max_total
    assert total <= 0.3 + 1e-9, f"Total {total} exceeds max_total 0.3"

    # Both probabilities should be non-zero (renormalized, not clamped to zero)
    assert result['p_merge'] > 0.0
    assert result['p_split'] > 0.0

    # Ratio should be approximately merge_coefficient / split_coefficient
    # (0.03 / 0.01 = 3.0, so merge should be ~3× split)
    ratio = result['p_merge'] / max(result['p_split'], 1e-9)
    assert 2.0 < ratio < 4.0, f"Ratio {ratio} outside expected range for renormalization"


def test_segmentation_modes_confluence_bias():
    """
    High confluence → p_merge/p_split increases.
    Low confluence → p_merge/p_split decreases.

    Invariant: Confluence modulates failure mode balance.
    """
    debris_cells = 1000.0
    adherent_cells = 5000.0

    # High confluence scenario (cells touching)
    result_high_conf = compute_segmentation_failure_modes(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        confluence=0.95
    )

    # Low confluence scenario (cells sparse)
    result_low_conf = compute_segmentation_failure_modes(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        confluence=0.1
    )

    # High confluence → merge dominates
    ratio_high = result_high_conf['p_merge'] / max(result_high_conf['p_split'], 1e-9)

    # Low confluence → split more prominent
    ratio_low = result_low_conf['p_merge'] / max(result_low_conf['p_split'], 1e-9)

    # High confluence should have higher merge/split ratio
    assert ratio_high > ratio_low, \
        f"Confluence bias failed: high_conf ratio {ratio_high} <= low_conf ratio {ratio_low}"

    # Sanity checks
    assert result_high_conf['p_merge'] > result_low_conf['p_merge'], \
        "High confluence should increase merge probability"
    assert result_low_conf['p_split'] > result_high_conf['p_split'], \
        "Low confluence should increase split probability"


# =============================================================================
# BACKGROUND MULTIPLIERS TESTS
# =============================================================================

def test_background_multipliers_backward_compatible():
    """
    channel_weights=None returns scalar in "__global__" key.

    Invariant: Preserves backward compatibility with existing scalar code.
    """
    debris_cells = 600.0
    initial_cells = 3000.0

    # No weights → scalar
    result = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=None
    )

    # Must return dict with "__global__" key only
    assert "__global__" in result
    assert len(result) == 1

    # Value should match scalar compute_background_noise_multiplier
    from cell_os.sim.imaging_artifacts_core import compute_background_noise_multiplier
    expected = compute_background_noise_multiplier(
        debris_cells=debris_cells,
        adherent_cells=initial_cells  # For backward compat test, use initial_cells as adherent
    )

    assert abs(result["__global__"] - expected) < 1e-9, \
        f"Backward compat failed: {result['__global__']} != {expected}"


def test_background_multipliers_per_channel_ordering():
    """
    Channel weights reflected in multiplier ordering.

    Invariant: Higher weight → higher multiplier (proportional to delta).
    """
    debris_cells = 900.0  # 30% of initial
    initial_cells = 3000.0

    # Per-channel weights (rna most sensitive, mito least)
    weights = {
        'rna': 1.5,
        'actin': 1.3,
        'nucleus': 1.0,
        'er': 0.8,
        'mito': 0.8
    }

    result = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=weights
    )

    # All channels present
    assert set(result.keys()) == set(weights.keys())

    # Ordering: rna > actin > nucleus > er ≈ mito
    assert result['rna'] > result['actin']
    assert result['actin'] > result['nucleus']
    assert result['nucleus'] > result['er']
    # er and mito should be approximately equal (same weight)
    assert abs(result['er'] - result['mito']) < 1e-6

    # All should exceed baseline (1.0)
    for channel, mult in result.items():
        assert mult > 1.0, f"Channel {channel} multiplier {mult} not above baseline"


def test_background_multipliers_bounds():
    """
    No channel exceeds max_multiplier.

    Invariant: All channels bounded by max_multiplier, even with extreme weights.
    """
    debris_cells = 3000.0  # 100% of initial (extreme)
    initial_cells = 3000.0
    max_mult = 1.15  # Tight bound

    # Extreme weights (should get clamped to [0.5, 2.0] then bounded by max_mult)
    weights = {
        'rna': 5.0,  # Will be clamped to 2.0
        'actin': 3.0,  # Will be clamped to 2.0
        'nucleus': 1.0,
        'er': 0.1,  # Will be clamped to 0.5
        'mito': 0.2  # Will be clamped to 0.5
    }

    result = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=weights,
        max_multiplier=max_mult
    )

    # All channels must respect max_multiplier
    for channel, mult in result.items():
        assert mult <= max_mult + 1e-9, \
            f"Channel {channel} multiplier {mult} exceeds max_multiplier {max_mult}"
        assert mult >= 1.0, \
            f"Channel {channel} multiplier {mult} below baseline 1.0"


# =============================================================================
# SPATIAL DEBRIS FIELD TESTS
# =============================================================================

def test_debris_field_determinism():
    """
    Same (experiment_seed, well_id, is_edge) → identical pattern.

    Invariant: Spatial pattern is deterministic, not stochastic.
    """
    debris_cells = 500.0
    initial_cells = 3000.0
    well_id = "B03"
    experiment_seed = 42
    is_edge = False

    # Compute twice with same inputs
    result1 = compute_debris_field_modifiers(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        is_edge=is_edge,
        well_id=well_id,
        experiment_seed=experiment_seed
    )

    result2 = compute_debris_field_modifiers(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        is_edge=is_edge,
        well_id=well_id,
        experiment_seed=experiment_seed
    )

    # All fields must match exactly
    assert result1['field_strength'] == result2['field_strength']
    assert result1['texture_corruption'] == result2['texture_corruption']
    assert result1['edge_amplification'] == result2['edge_amplification']
    assert np.array_equal(result1['spatial_pattern'], result2['spatial_pattern'])


def test_debris_field_edge_variance():
    """
    is_edge=True → higher pattern variance than interior.

    Invariant: Edge wells have more heterogeneous debris patterns (meniscus effects).
    """
    debris_cells = 800.0
    initial_cells = 3000.0
    well_id = "B03"
    experiment_seed = 42

    # Interior well
    result_interior = compute_debris_field_modifiers(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        is_edge=False,
        well_id=well_id,
        experiment_seed=experiment_seed
    )

    # Edge well (same debris, different is_edge)
    result_edge = compute_debris_field_modifiers(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        is_edge=True,
        well_id=well_id,
        experiment_seed=experiment_seed
    )

    # Edge well should have higher edge_amplification (when debris present)
    assert result_edge['edge_amplification'] > result_interior['edge_amplification'], \
        f"Edge amplification not higher for edge: {result_edge['edge_amplification']} <= {result_interior['edge_amplification']}"

    # Patterns should differ (is_edge affects hash)
    assert not np.array_equal(result_interior['spatial_pattern'], result_edge['spatial_pattern']), \
        "Edge and interior patterns should differ"

    # Edge pattern should have higher variance (std dev)
    var_interior = np.std(result_interior['spatial_pattern'])
    var_edge = np.std(result_edge['spatial_pattern'])

    assert var_edge > var_interior, \
        f"Edge pattern variance {var_edge} not higher than interior {var_interior}"


def test_debris_field_strength_monotonic():
    """
    More debris → higher field_strength and texture_corruption.

    Invariant: field_strength and texture_corruption are monotonic in debris_cells.
    """
    initial_cells = 3000.0
    well_id = "B03"
    experiment_seed = 42
    is_edge = False

    # Test sequence with increasing debris
    debris_levels = [0.0, 300.0, 900.0, 1500.0, 3000.0]

    prev_strength = 0.0
    prev_corruption = 0.0

    for debris in debris_levels:
        result = compute_debris_field_modifiers(
            debris_cells=debris,
            adherent_cells=initial_cells,
            is_edge=is_edge,
            well_id=well_id,
            experiment_seed=experiment_seed
        )

        strength = result['field_strength']
        corruption = result['texture_corruption']

        # Monotonicity
        assert strength >= prev_strength, \
            f"field_strength not monotonic: {strength} < {prev_strength}"
        assert corruption >= prev_corruption, \
            f"texture_corruption not monotonic: {corruption} < {prev_corruption}"

        # Bounds
        assert 0.0 <= strength <= 1.0, f"field_strength {strength} out of bounds"
        assert 0.0 <= corruption <= 0.3, f"texture_corruption {corruption} out of bounds"

        prev_strength = strength
        prev_corruption = corruption


def test_debris_field_spatial_pattern_invariants():
    """
    Spatial pattern mean ≈ 1.0, values in [0.7, 1.3].

    Invariants:
    - Pattern mean is 1.0 (±1e-6)
    - All pattern values in [0.7, 1.3]
    """
    result = compute_debris_field_modifiers(
        debris_cells=1000.0,
        adherent_cells=3000.0,
        is_edge=True,
        well_id="A01",
        experiment_seed=123
    )

    pattern = result['spatial_pattern']

    # Mean should be very close to 1.0 (renormalized)
    pattern_mean = pattern.mean()
    assert abs(pattern_mean - 1.0) < 1e-6, \
        f"Spatial pattern mean {pattern_mean} not normalized to 1.0"

    # All values must be in [0.7, 1.3]
    assert pattern.min() >= 0.7 - 1e-9, \
        f"Spatial pattern min {pattern.min()} below 0.7"
    assert pattern.max() <= 1.3 + 1e-9, \
        f"Spatial pattern max {pattern.max()} above 1.3"

    # Pattern should be 3x3 by default
    assert pattern.shape == (3, 3), f"Pattern shape {pattern.shape} not (3, 3)"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Running Structured Imaging Artifacts Tests")
    print("=" * 70)

    # Segmentation modes tests
    print("\n1. SEGMENTATION FAILURE MODES")
    test_segmentation_modes_monotonicity()
    print("   ✓ Monotonicity")
    test_segmentation_modes_bounds()
    print("   ✓ Bounds")
    test_segmentation_modes_max_total_renormalization()
    print("   ✓ Max total renormalization")
    test_segmentation_modes_confluence_bias()
    print("   ✓ Confluence bias")

    # Background multipliers tests
    print("\n2. BACKGROUND MULTIPLIERS")
    test_background_multipliers_backward_compatible()
    print("   ✓ Backward compatible")
    test_background_multipliers_per_channel_ordering()
    print("   ✓ Per-channel ordering")
    test_background_multipliers_bounds()
    print("   ✓ Bounds")

    # Spatial field tests
    print("\n3. SPATIAL DEBRIS FIELD")
    test_debris_field_determinism()
    print("   ✓ Determinism")
    test_debris_field_edge_variance()
    print("   ✓ Edge variance")
    test_debris_field_strength_monotonic()
    print("   ✓ Strength monotonic")
    test_debris_field_spatial_pattern_invariants()
    print("   ✓ Spatial pattern invariants")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED (11 tests)")
    print("=" * 70)
