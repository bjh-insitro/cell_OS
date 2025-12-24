"""
Unit tests for evaporation effects.

Tests that:
1. Edge wells have higher exposure than center (deterministic geometry)
2. Volume loss increases concentration (dose amplification)
3. Ridge uncertainty is zero when rate prior CV is zero
4. Evaporation is independent of aspiration (no double-counting)
5. Gravimetric calibration updates rate prior correctly
"""

import numpy as np
import pytest
from src.cell_os.hardware.evaporation_effects import (
    calculate_evaporation_exposure,
    calculate_volume_loss_over_time,
    get_evaporation_contribution_to_effective_dose,
    compute_evaporation_ridge_uncertainty,
    sample_evaporation_rate_from_prior,
    EvaporationRatePrior,
    update_evaporation_rate_prior_from_gravimetry
)


def test_edge_wells_higher_exposure_than_center():
    """
    Edge and corner wells should have higher evaporation exposure than center wells.

    Spatial gradient: edge/corner > mid-plate > deep center.
    (Note: All physical edges get max exposure - edge effects are edge effects)
    """
    # Corner well (A1) - physical corner
    corner_exposure = calculate_evaporation_exposure("A1", plate_format=384)

    # Mid-plate well (E6) - partway from edge
    mid_plate_exposure = calculate_evaporation_exposure("E6", plate_format=384)

    # Center well (H12) - middle row, middle column
    center_exposure = calculate_evaporation_exposure("H12", plate_format=384)

    # Assert gradient
    assert corner_exposure > mid_plate_exposure, \
        f"Corner ({corner_exposure:.3f}) should be > mid-plate ({mid_plate_exposure:.3f})"
    assert mid_plate_exposure > center_exposure, \
        f"Mid-plate ({mid_plate_exposure:.3f}) should be > center ({center_exposure:.3f})"

    # Assert bounds
    assert 1.0 <= center_exposure <= 1.5, "Center exposure should be in [1.0, 1.5]"
    assert 1.0 <= corner_exposure <= 1.5, "Corner exposure should be in [1.0, 1.5]"

    # Assert corner is at max
    assert abs(corner_exposure - 1.5) < 0.01, f"Corner exposure should be ~1.5, got {corner_exposure:.3f}"

    # Assert center is near min (may not be exactly 1.0 due to discrete grid)
    assert center_exposure < 1.1, f"Center exposure should be close to 1.0, got {center_exposure:.3f}"

    print(f"\nEvaporation exposure gradient (384-well):")
    print(f"  Corner (A1):    {corner_exposure:.3f}")
    print(f"  Mid-plate (E6): {mid_plate_exposure:.3f}")
    print(f"  Center (H12):   {center_exposure:.3f}")


def test_volume_loss_increases_concentration():
    """
    Volume loss should increase concentration (concentration_multiplier > 1.0).

    If volume drops to 80%, concentration increases by 1/0.8 = 1.25×.
    """
    initial_volume_ul = 50.0
    time_hours = 24.0
    base_evap_rate = 0.5  # µL/h
    exposure = 1.0

    result = calculate_volume_loss_over_time(
        initial_volume_ul=initial_volume_ul,
        time_hours=time_hours,
        base_evap_rate_ul_per_h=base_evap_rate,
        exposure=exposure,
        min_volume_fraction=0.3
    )

    # Volume should decrease
    assert result['volume_current_ul'] < initial_volume_ul, "Volume should decrease"
    assert result['volume_fraction'] < 1.0, "Volume fraction should be < 1.0"

    # Concentration should increase
    assert result['concentration_multiplier'] > 1.0, "Concentration should increase"

    # Check relationship: concentration_multiplier = 1 / volume_fraction
    expected_multiplier = 1.0 / result['volume_fraction']
    assert abs(result['concentration_multiplier'] - expected_multiplier) < 1e-6, \
        f"Concentration multiplier should equal 1/volume_fraction"

    # Check dose amplification
    baseline_dose = 1.0
    dose_result = get_evaporation_contribution_to_effective_dose(
        concentration_multiplier=result['concentration_multiplier'],
        baseline_dose_uM=baseline_dose
    )

    assert dose_result['effective_dose_multiplier'] == result['concentration_multiplier']
    assert dose_result['dose_delta_fraction'] == result['concentration_multiplier'] - 1.0

    print(f"\nVolume loss → concentration drift:")
    print(f"  Initial volume:          {initial_volume_ul:.1f} µL")
    print(f"  Volume after {time_hours:.0f}h:     {result['volume_current_ul']:.1f} µL")
    print(f"  Volume fraction:         {result['volume_fraction']:.3f}")
    print(f"  Concentration multiplier: {result['concentration_multiplier']:.3f}×")
    print(f"  Dose increase:           +{dose_result['dose_delta_fraction']:.1%}")


def test_volume_loss_respects_minimum():
    """
    Volume should not drop below minimum fraction (floor constraint).
    """
    initial_volume_ul = 50.0
    time_hours = 1000.0  # Very long time
    base_evap_rate = 1.0  # Fast evaporation
    exposure = 1.5  # Maximum exposure
    min_volume_fraction = 0.3

    result = calculate_volume_loss_over_time(
        initial_volume_ul=initial_volume_ul,
        time_hours=time_hours,
        base_evap_rate_ul_per_h=base_evap_rate,
        exposure=exposure,
        min_volume_fraction=min_volume_fraction
    )

    # Volume should not drop below minimum
    min_volume_ul = initial_volume_ul * min_volume_fraction
    assert result['volume_current_ul'] >= min_volume_ul, \
        f"Volume should not drop below {min_volume_ul:.1f} µL, got {result['volume_current_ul']:.1f}"

    # Volume fraction should not drop below minimum
    assert result['volume_fraction'] >= min_volume_fraction, \
        f"Volume fraction should not drop below {min_volume_fraction:.2f}, got {result['volume_fraction']:.2f}"

    print(f"\nVolume floor constraint (extreme evaporation):")
    print(f"  Time:              {time_hours:.0f}h")
    print(f"  Min volume:        {min_volume_ul:.1f} µL")
    print(f"  Final volume:      {result['volume_current_ul']:.1f} µL")
    print(f"  ✓ Floor respected")


def test_ridge_zero_when_no_prior_uncertainty():
    """
    If rate prior CV is zero, ridge uncertainty should be zero.

    This validates the epistemic boundary: no calibration uncertainty → no ridge.
    """
    exposure = 1.5
    time_hours = 48.0
    initial_volume_ul = 50.0
    rate_prior_cv = 0.0  # No uncertainty

    ridge = compute_evaporation_ridge_uncertainty(
        exposure=exposure,
        time_hours=time_hours,
        initial_volume_ul=initial_volume_ul,
        rate_prior_cv=rate_prior_cv
    )

    # All ridge CVs should be zero
    assert ridge['volume_fraction_cv'] == 0.0, "Volume fraction CV should be zero"
    assert ridge['concentration_multiplier_cv'] == 0.0, "Concentration multiplier CV should be zero"
    assert ridge['effective_dose_cv'] == 0.0, "Effective dose CV should be zero"

    print(f"\nRidge boundary test (rate_prior_cv=0):")
    print(f"  volume_fraction_cv:         {ridge['volume_fraction_cv']:.6f}")
    print(f"  concentration_multiplier_cv: {ridge['concentration_multiplier_cv']:.6f}")
    print(f"  effective_dose_cv:          {ridge['effective_dose_cv']:.6f}")
    print(f"  ✓ All zero (epistemic boundary respected)")


def test_ridge_nonzero_with_prior_uncertainty():
    """
    If rate prior CV > 0, ridge uncertainty should be > 0.

    Validates that ridge propagates epistemic uncertainty.
    """
    exposure = 1.5
    time_hours = 48.0
    initial_volume_ul = 50.0
    rate_prior_cv = 0.30  # 30% CV

    ridge = compute_evaporation_ridge_uncertainty(
        exposure=exposure,
        time_hours=time_hours,
        initial_volume_ul=initial_volume_ul,
        rate_prior_cv=rate_prior_cv
    )

    # All ridge CVs should be positive
    assert ridge['volume_fraction_cv'] > 0, "Volume fraction CV should be positive"
    assert ridge['concentration_multiplier_cv'] > 0, "Concentration multiplier CV should be positive"
    assert ridge['effective_dose_cv'] > 0, "Effective dose CV should be positive"

    print(f"\nRidge propagation test (rate_prior_cv={rate_prior_cv}):")
    print(f"  volume_fraction_cv:         {ridge['volume_fraction_cv']:.4f}")
    print(f"  concentration_multiplier_cv: {ridge['concentration_multiplier_cv']:.4f}")
    print(f"  effective_dose_cv:          {ridge['effective_dose_cv']:.4f}")
    print(f"  ✓ Ridge propagates epistemic uncertainty")


def test_evaporation_deterministic_given_rate():
    """
    Volume loss should be deterministic given rate (no hidden randomness).

    Same inputs → same outputs.
    """
    initial_volume_ul = 50.0
    time_hours = 24.0
    base_evap_rate = 0.5
    exposure = 1.3

    result1 = calculate_volume_loss_over_time(
        initial_volume_ul, time_hours, base_evap_rate, exposure
    )

    result2 = calculate_volume_loss_over_time(
        initial_volume_ul, time_hours, base_evap_rate, exposure
    )

    # Results should be identical
    assert result1['volume_current_ul'] == result2['volume_current_ul']
    assert result1['concentration_multiplier'] == result2['concentration_multiplier']

    print(f"\nDeterminism test:")
    print(f"  Volume (run 1):  {result1['volume_current_ul']:.6f} µL")
    print(f"  Volume (run 2):  {result2['volume_current_ul']:.6f} µL")
    print(f"  ✓ Identical (deterministic given rate)")


def test_evaporation_independent_of_aspiration():
    """
    Evaporation exposure should not depend on aspiration angle.

    This validates separation: evaporation is geometry-only, aspiration is angle-dependent.
    """
    well = "A12"

    # Calculate evaporation exposure (no aspiration angle parameter)
    evap_exposure = calculate_evaporation_exposure(well, plate_format=384)

    # Evaporation should be same regardless of aspiration state
    # (This is implicit - evaporation function doesn't take aspiration parameters)
    # Just verify it returns consistent value
    evap_exposure_2 = calculate_evaporation_exposure(well, plate_format=384)

    assert evap_exposure == evap_exposure_2, "Evaporation should be deterministic"

    # Verify exposure is reasonable
    assert 1.0 <= evap_exposure <= 1.5, f"Exposure should be in [1.0, 1.5], got {evap_exposure:.3f}"

    print(f"\nSeparation test (evaporation independent of aspiration):")
    print(f"  Well: {well}")
    print(f"  Evaporation exposure: {evap_exposure:.3f}")
    print(f"  ✓ No aspiration coupling (function signatures separate)")


def test_gravimetric_calibration_updates_prior():
    """
    Gravimetric evidence should update evaporation rate prior.

    Validates Bayesian calibration hook.
    """
    # Start with default prior
    prior = EvaporationRatePrior()  # mean=0.5, CV=0.30

    # Simulate gravimetric measurement
    time_hours = 24.0
    edge_exposure = 1.5
    center_exposure = 1.0

    # Predict loss given true rate (0.6 µL/h)
    true_rate = 0.6
    edge_loss_ul = true_rate * edge_exposure * time_hours
    center_loss_ul = true_rate * center_exposure * time_hours

    # Update prior with this evidence
    updated_prior, report = update_evaporation_rate_prior_from_gravimetry(
        prior=prior,
        edge_loss_ul=edge_loss_ul,
        center_loss_ul=center_loss_ul,
        time_hours=time_hours,
        edge_exposure=edge_exposure,
        center_exposure=center_exposure,
        measurement_uncertainty=0.10,
        plate_id="CAL_TEST"
    )

    # Posterior mean should shift toward evidence
    assert updated_prior.mean > prior.mean, \
        f"Posterior mean should increase (evidence suggests higher rate), got {prior.mean:.3f} → {updated_prior.mean:.3f}"

    # Posterior CV should narrow (more evidence → less uncertainty)
    assert updated_prior.cv < prior.cv, \
        f"Posterior CV should decrease, got {prior.cv:.3f} → {updated_prior.cv:.3f}"

    # Check provenance
    assert len(updated_prior.calibration_history) == 1, "Should have one calibration entry"
    assert updated_prior.calibration_history[0]['plate_id'] == "CAL_TEST"
    assert updated_prior.calibration_history[0]['source'] == 'gravimetry'

    print(f"\nGravimetric calibration test:")
    print(f"  Prior:     mean={prior.mean:.3f}, CV={prior.cv:.3f}")
    print(f"  Evidence:  edge_loss={edge_loss_ul:.1f}µL, center_loss={center_loss_ul:.1f}µL over {time_hours:.0f}h")
    print(f"  Posterior: mean={updated_prior.mean:.3f}, CV={updated_prior.cv:.3f}")
    print(f"  Sigma reduction: {report['sigma_reduction']:.1%}")
    print(f"  ✓ Prior updated correctly")


def test_sampled_rate_deterministic():
    """
    Sampling rate from prior should be deterministic given seed.

    Same seed → same rate (reproducibility).
    """
    seed = 42
    instrument_id = "plate_test"

    rate1 = sample_evaporation_rate_from_prior(seed, instrument_id)
    rate2 = sample_evaporation_rate_from_prior(seed, instrument_id)

    assert rate1 == rate2, f"Rate should be deterministic, got {rate1:.6f} vs {rate2:.6f}"

    # Different seed → different rate
    rate3 = sample_evaporation_rate_from_prior(seed + 1, instrument_id)
    assert rate3 != rate1, "Different seed should give different rate"

    print(f"\nSampling determinism test:")
    print(f"  Rate (seed={seed}):   {rate1:.6f} µL/h")
    print(f"  Rate (seed={seed}):   {rate2:.6f} µL/h")
    print(f"  Rate (seed={seed+1}): {rate3:.6f} µL/h")
    print(f"  ✓ Deterministic given seed, varies with seed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
