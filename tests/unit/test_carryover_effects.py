"""
Unit tests for carryover effects.

Tests that:
1. Carryover contamination is sequence-dependent (not geometry-dependent)
2. First well in sequence has no carryover
3. Blank-after-hot calibration updates prior correctly
4. Ridge uncertainty is zero when prior CV is zero
5. Carryover is independent of aspiration/evaporation (no double-counting)
6. Wash efficiency reduces carryover correctly
"""

import numpy as np
import pytest
from src.cell_os.hardware.carryover_effects import (
    calculate_carryover_contamination,
    apply_carryover_to_sequence,
    compute_carryover_ridge_uncertainty,
    sample_carryover_fraction_from_prior,
    CarryoverFractionPrior,
    update_carryover_fraction_prior_from_blank_after_hot,
    get_dispense_sequence_for_plate
)


def test_first_dispense_has_no_carryover():
    """
    First well in sequence should have zero carryover.

    Validates: No contamination when previous_dose = 0.
    """
    carryover_fraction = 0.01  # 1%

    # First dispense (no previous)
    result = calculate_carryover_contamination(
        previous_dose_uM=0.0,
        carryover_fraction=carryover_fraction,
        wash_efficiency=0.0
    )

    assert result['carryover_dose_uM'] == 0.0, "First dispense should have no carryover"
    assert result['effective_carryover_fraction'] == carryover_fraction

    print(f"\nFirst dispense test:")
    print(f"  Previous dose:       0.0 µM")
    print(f"  Carryover fraction:  {carryover_fraction:.2%}")
    print(f"  Carryover dose:      {result['carryover_dose_uM']:.4f} µM")
    print(f"  ✓ No contamination")


def test_carryover_contamination_scales_with_previous_dose():
    """
    Carryover dose should scale linearly with previous dose.

    Validates: carryover_dose = previous_dose × fraction
    """
    carryover_fraction = 0.005  # 0.5%

    # After 1 µM dispense
    result_1uM = calculate_carryover_contamination(
        previous_dose_uM=1.0,
        carryover_fraction=carryover_fraction
    )

    # After 10 µM dispense
    result_10uM = calculate_carryover_contamination(
        previous_dose_uM=10.0,
        carryover_fraction=carryover_fraction
    )

    # Should scale linearly
    expected_1uM = 1.0 * carryover_fraction
    expected_10uM = 10.0 * carryover_fraction

    assert abs(result_1uM['carryover_dose_uM'] - expected_1uM) < 1e-9
    assert abs(result_10uM['carryover_dose_uM'] - expected_10uM) < 1e-9
    assert abs(result_10uM['carryover_dose_uM'] / result_1uM['carryover_dose_uM'] - 10.0) < 1e-9

    print(f"\nLinear scaling test:")
    print(f"  After 1 µM:   {result_1uM['carryover_dose_uM']:.4f} µM carryover")
    print(f"  After 10 µM:  {result_10uM['carryover_dose_uM']:.4f} µM carryover")
    print(f"  Ratio:        {result_10uM['carryover_dose_uM'] / result_1uM['carryover_dose_uM']:.1f}×")
    print(f"  ✓ Linear scaling confirmed")


def test_wash_reduces_carryover():
    """
    Wash efficiency should reduce effective carryover fraction.

    Validates: effective_carryover = fraction × (1 - wash_efficiency)
    """
    previous_dose = 10.0
    carryover_fraction = 0.01  # 1%

    # No wash
    result_no_wash = calculate_carryover_contamination(
        previous_dose_uM=previous_dose,
        carryover_fraction=carryover_fraction,
        wash_efficiency=0.0
    )

    # 50% wash
    result_50pct_wash = calculate_carryover_contamination(
        previous_dose_uM=previous_dose,
        carryover_fraction=carryover_fraction,
        wash_efficiency=0.5
    )

    # 90% wash
    result_90pct_wash = calculate_carryover_contamination(
        previous_dose_uM=previous_dose,
        carryover_fraction=carryover_fraction,
        wash_efficiency=0.9
    )

    # Validate reduction
    assert result_50pct_wash['carryover_dose_uM'] < result_no_wash['carryover_dose_uM']
    assert result_90pct_wash['carryover_dose_uM'] < result_50pct_wash['carryover_dose_uM']

    # Validate exact values
    expected_50 = previous_dose * carryover_fraction * 0.5
    expected_90 = previous_dose * carryover_fraction * 0.1

    assert abs(result_50pct_wash['carryover_dose_uM'] - expected_50) < 1e-9
    assert abs(result_90pct_wash['carryover_dose_uM'] - expected_90) < 1e-9

    print(f"\nWash efficiency test:")
    print(f"  No wash (0%):    {result_no_wash['carryover_dose_uM']:.4f} µM")
    print(f"  50% wash:        {result_50pct_wash['carryover_dose_uM']:.4f} µM")
    print(f"  90% wash:        {result_90pct_wash['carryover_dose_uM']:.4f} µM")
    print(f"  ✓ Wash reduces carryover correctly")


def test_sequence_dependence_not_geometry():
    """
    Carryover depends on DISPENSE ORDER, not spatial position.

    Validates: Same dose sequence → same contamination, regardless of well IDs.
    """
    dose_sequence = [10.0, 0.0, 10.0, 0.0]
    carryover_fraction = 0.005

    # Apply to sequence
    effective_doses = apply_carryover_to_sequence(
        dose_sequence_uM=dose_sequence,
        carryover_fraction=carryover_fraction
    )

    # Check pattern:
    # Position 0: 10.0 + 0 (no previous) = 10.0
    # Position 1: 0.0 + 0.05 (10 × 0.005) = 0.05
    # Position 2: 10.0 + 0 (0 × 0.005) = 10.0
    # Position 3: 0.0 + 0.05 (10 × 0.005) = 0.05

    assert abs(effective_doses[0] - 10.0) < 1e-9, "First hot should be clean"
    assert abs(effective_doses[1] - 0.05) < 1e-9, "First blank after hot should be contaminated"
    assert abs(effective_doses[2] - 10.0) < 1e-9, "Second hot should be clean"
    assert abs(effective_doses[3] - 0.05) < 1e-9, "Second blank after hot should be contaminated"

    # Same contamination for both blanks (same previous dose)
    assert abs(effective_doses[1] - effective_doses[3]) < 1e-9

    print(f"\nSequence dependence test:")
    print(f"  Sequence: {dose_sequence}")
    print(f"  Effective: {[f'{d:.4f}' for d in effective_doses]}")
    print(f"  ✓ Contamination is sequence-dependent, not position-dependent")


def test_ridge_zero_when_no_prior_uncertainty():
    """
    If prior CV is zero, ridge uncertainty should be zero.

    Validates epistemic boundary: no calibration uncertainty → no ridge.
    """
    previous_dose = 10.0
    frac_prior_cv = 0.0  # No uncertainty

    ridge = compute_carryover_ridge_uncertainty(
        previous_dose_uM=previous_dose,
        frac_prior_cv=frac_prior_cv
    )

    assert ridge['carryover_dose_cv'] == 0.0, "Ridge should be zero when prior CV is zero"

    print(f"\nRidge boundary test (frac_prior_cv=0):")
    print(f"  carryover_dose_cv: {ridge['carryover_dose_cv']:.6f}")
    print(f"  ✓ Epistemic boundary respected")


def test_ridge_nonzero_with_prior_uncertainty():
    """
    If prior CV > 0, ridge uncertainty should be > 0.

    Validates ridge propagation.
    """
    previous_dose = 10.0
    frac_prior_cv = 0.40  # 40% CV

    ridge = compute_carryover_ridge_uncertainty(
        previous_dose_uM=previous_dose,
        frac_prior_cv=frac_prior_cv
    )

    assert ridge['carryover_dose_cv'] > 0, "Ridge should be positive when prior CV > 0"

    print(f"\nRidge propagation test (frac_prior_cv={frac_prior_cv}):")
    print(f"  carryover_dose_cv: {ridge['carryover_dose_cv']:.4f}")
    print(f"  ✓ Ridge propagates epistemic uncertainty")


def test_carryover_deterministic_given_fraction():
    """
    Carryover should be deterministic given fraction (no hidden randomness).

    Same inputs → same outputs.
    """
    previous_dose = 5.0
    carryover_fraction = 0.008

    result1 = calculate_carryover_contamination(previous_dose, carryover_fraction)
    result2 = calculate_carryover_contamination(previous_dose, carryover_fraction)

    assert result1['carryover_dose_uM'] == result2['carryover_dose_uM']
    assert result1['effective_carryover_fraction'] == result2['effective_carryover_fraction']

    print(f"\nDeterminism test:")
    print(f"  Carryover (run 1): {result1['carryover_dose_uM']:.6f} µM")
    print(f"  Carryover (run 2): {result2['carryover_dose_uM']:.6f} µM")
    print(f"  ✓ Identical (deterministic given fraction)")


def test_carryover_independent_of_aspiration_evaporation():
    """
    Carryover calculation should not depend on aspiration or evaporation parameters.

    Validates separation: carryover is sequence-only, independent of spatial artifacts.
    """
    previous_dose = 10.0
    carryover_fraction = 0.005

    # Calculate carryover (no aspiration/evaporation parameters)
    result = calculate_carryover_contamination(
        previous_dose_uM=previous_dose,
        carryover_fraction=carryover_fraction
    )

    # Verify result depends only on sequence
    expected = previous_dose * carryover_fraction
    assert abs(result['carryover_dose_uM'] - expected) < 1e-9

    # Function signature doesn't accept aspiration/evaporation args (separation by design)
    print(f"\nSeparation test (carryover independent of spatial artifacts):")
    print(f"  Previous dose: {previous_dose:.1f} µM")
    print(f"  Carryover:     {result['carryover_dose_uM']:.4f} µM")
    print(f"  ✓ No aspiration/evaporation coupling (function signatures separate)")


def test_blank_after_hot_calibration_updates_prior():
    """
    Blank-after-hot evidence should update carryover fraction prior.

    Validates Bayesian calibration hook.
    """
    # Start with default prior
    prior = CarryoverFractionPrior()  # mean=0.5%, CV=0.40

    # Simulate blank-after-hot measurement
    hot_dose_uM = 10.0
    true_fraction = 0.008  # 0.8%
    blank_observed_dose_uM = hot_dose_uM * true_fraction  # 0.08 µM

    # Update prior with this evidence
    updated_prior, report = update_carryover_fraction_prior_from_blank_after_hot(
        prior=prior,
        hot_dose_uM=hot_dose_uM,
        blank_observed_dose_uM=blank_observed_dose_uM,
        measurement_uncertainty_uM=0.01,
        plate_id="CAL_TEST"
    )

    # Posterior mean should shift toward evidence
    assert updated_prior.mean > prior.mean, \
        f"Posterior mean should increase (evidence suggests higher fraction), got {prior.mean:.4f} → {updated_prior.mean:.4f}"

    # Posterior CV should narrow (more evidence → less uncertainty)
    assert updated_prior.cv < prior.cv, \
        f"Posterior CV should decrease, got {prior.cv:.3f} → {updated_prior.cv:.3f}"

    # Check provenance
    assert len(updated_prior.calibration_history) == 1, "Should have one calibration entry"
    assert updated_prior.calibration_history[0]['plate_id'] == "CAL_TEST"
    assert updated_prior.calibration_history[0]['source'] == 'blank_after_hot'

    print(f"\nBlank-after-hot calibration test:")
    print(f"  Prior:     mean={prior.mean:.4f}, CV={prior.cv:.3f}")
    print(f"  Evidence:  hot={hot_dose_uM:.1f}µM, blank_obs={blank_observed_dose_uM:.3f}µM")
    print(f"  Posterior: mean={updated_prior.mean:.4f}, CV={updated_prior.cv:.3f}")
    print(f"  Sigma reduction: {report['sigma_reduction']:.1%}")
    print(f"  ✓ Prior updated correctly")


def test_sampled_fraction_deterministic():
    """
    Sampling fraction from prior should be deterministic given seed.

    Same seed → same fraction (reproducibility).
    """
    seed = 42
    tip_id = "tip_test"

    frac1 = sample_carryover_fraction_from_prior(seed, tip_id)
    frac2 = sample_carryover_fraction_from_prior(seed, tip_id)

    assert frac1 == frac2, f"Fraction should be deterministic, got {frac1:.6f} vs {frac2:.6f}"

    # Different seed → different fraction
    frac3 = sample_carryover_fraction_from_prior(seed + 1, tip_id)
    assert frac3 != frac1, "Different seed should give different fraction"

    print(f"\nSampling determinism test:")
    print(f"  Fraction (seed={seed}):   {frac1:.6f}")
    print(f"  Fraction (seed={seed}):   {frac2:.6f}")
    print(f"  Fraction (seed={seed+1}): {frac3:.6f}")
    print(f"  ✓ Deterministic given seed, varies with seed")


def test_dispense_sequence_patterns():
    """
    Test row-wise and column-wise dispense patterns for 96 and 384-well plates.

    Validates sequence generation utilities.
    """
    # 96-well row-wise
    seq_96_row = get_dispense_sequence_for_plate(plate_format=96, dispense_pattern="row_wise")
    assert len(seq_96_row) == 96, "96-well should have 96 wells"
    assert seq_96_row[0] == "A1", "Row-wise should start at A1"
    assert seq_96_row[1] == "A2", "Row-wise should go A1→A2"
    assert seq_96_row[12] == "B1", "Row-wise should wrap at row end"

    # 96-well column-wise
    seq_96_col = get_dispense_sequence_for_plate(plate_format=96, dispense_pattern="column_wise")
    assert len(seq_96_col) == 96
    assert seq_96_col[0] == "A1", "Column-wise should start at A1"
    assert seq_96_col[1] == "B1", "Column-wise should go A1→B1"
    assert seq_96_col[8] == "A2", "Column-wise should wrap at column end"

    # 384-well row-wise
    seq_384_row = get_dispense_sequence_for_plate(plate_format=384, dispense_pattern="row_wise")
    assert len(seq_384_row) == 384, "384-well should have 384 wells"
    assert seq_384_row[0] == "A1"
    assert seq_384_row[24] == "B1"

    # 384-well column-wise
    seq_384_col = get_dispense_sequence_for_plate(plate_format=384, dispense_pattern="column_wise")
    assert len(seq_384_col) == 384
    assert seq_384_col[16] == "A2"

    print(f"\nDispense sequence test:")
    print(f"  96-well row-wise:    {seq_96_row[0]} → {seq_96_row[1]} → ... → {seq_96_row[-1]}")
    print(f"  96-well column-wise: {seq_96_col[0]} → {seq_96_col[1]} → ... → {seq_96_col[-1]}")
    print(f"  384-well row-wise:   {seq_384_row[0]} → {seq_384_row[1]} → ... → {seq_384_row[-1]}")
    print(f"  384-well column-wise: {seq_384_col[0]} → {seq_384_col[1]} → ... → {seq_384_col[-1]}")
    print(f"  ✓ Sequence generation correct")


def test_blank_after_blank_stays_clean():
    """
    Blank dispensed after blank should remain clean (no carryover).

    Validates: carryover only happens when previous dose > 0.
    """
    dose_sequence = [10.0, 0.0, 0.0, 0.0]  # Hot, blank, blank, blank
    carryover_fraction = 0.01  # 1%

    effective_doses = apply_carryover_to_sequence(dose_sequence, carryover_fraction)

    # Position 0: 10.0 (no carryover)
    # Position 1: 0.0 + 0.1 (10 × 0.01) = 0.1
    # Position 2: 0.0 + 0.0 (0 × 0.01) = 0.0
    # Position 3: 0.0 + 0.0 (0 × 0.01) = 0.0

    assert abs(effective_doses[0] - 10.0) < 1e-9
    assert abs(effective_doses[1] - 0.1) < 1e-9
    assert abs(effective_doses[2] - 0.0) < 1e-9
    assert abs(effective_doses[3] - 0.0) < 1e-9

    print(f"\nBlank-after-blank test:")
    print(f"  Sequence: {dose_sequence}")
    print(f"  Effective: {[f'{d:.4f}' for d in effective_doses]}")
    print(f"  ✓ Blanks after blanks stay clean")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
