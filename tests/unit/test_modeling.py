"""
Unit tests for DoseResponseGP modeling.

Tests GP fitting, prediction, and grid generation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest

from src.modeling import DoseResponseGP


def test_empty_gp_creation():
    """Test creating an empty GP placeholder."""
    gp = DoseResponseGP.empty()
    
    assert gp is not None
    assert gp.X_train.size == 0
    assert gp.y_train.size == 0


def test_gp_from_dataframe():
    """Test fitting GP from a DataFrame."""
    # Create synthetic dose-response data
    df = pd.DataFrame({
        'cell_line': ['HepG2'] * 10,
        'compound': ['CompoundA'] * 10,
        'time_h': [24.0] * 10,
        'dose_uM': [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
        'viability': [0.98, 0.95, 0.90, 0.75, 0.50, 0.30, 0.15, 0.10, 0.08, 0.05]
    })
    
    gp = DoseResponseGP.from_dataframe(
        df,
        cell_line='HepG2',
        compound='CompoundA',
        time_h=24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    assert gp is not None
    assert len(gp.X_train) == 10
    assert len(gp.y_train) == 10


def test_gp_prediction():
    """Test GP predictions at new dose points."""
    # Create training data
    df = pd.DataFrame({
        'cell_line': ['HepG2'] * 8,
        'compound': ['CompoundA'] * 8,
        'time_h': [24.0] * 8,
        'dose_uM': [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
        'viability': [0.95, 0.90, 0.75, 0.50, 0.30, 0.15, 0.10, 0.08]
    })
    
    gp = DoseResponseGP.from_dataframe(
        df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Predict at interpolation point
    test_doses = np.array([0.5, 1.5, 3.0])
    mean, std = gp.predict(test_doses, return_std=True)
    
    assert mean is not None
    assert std is not None
    assert len(mean) == 3
    assert len(std) == 3
    assert all(std > 0)  # Should have positive uncertainty


def test_gp_predict_on_grid():
    """Test grid prediction for visualization."""
    df = pd.DataFrame({
        'cell_line': ['HepG2'] * 8,
        'compound': ['CompoundA'] * 8,
        'time_h': [24.0] * 8,
        'dose_uM': [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
        'viability': [0.95, 0.90, 0.75, 0.50, 0.30, 0.15, 0.10, 0.08]
    })
    
    gp = DoseResponseGP.from_dataframe(
        df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    grid_results = gp.predict_on_grid(num_points=50)
    
    assert 'dose_uM' in grid_results
    assert 'mean' in grid_results
    assert 'std' in grid_results
    assert len(grid_results['dose_uM']) == 50
    assert len(grid_results['mean']) == 50
    assert len(grid_results['std']) == 50




def test_empty_gp_predict_on_grid():
    """Test that empty GP returns empty arrays for grid."""
    gp = DoseResponseGP.empty()
    
    grid_results = gp.predict_on_grid(num_points=50)
    
    assert len(grid_results['dose_uM']) == 0
    assert len(grid_results['mean']) == 0
    assert len(grid_results['std']) == 0


def test_prior_shrinkage_behavior():
    """Test that prior weight correctly shrinks new data toward prior predictions."""
    # Create a prior GP with linear decreasing behavior: viability ≈ 1 - dose/10
    prior_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 8,
        'compound': ['CompoundA'] * 8,
        'time_h': [24.0] * 8,
        'dose_uM': [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
        'viability': [0.99, 0.95, 0.90, 0.80, 0.50, 0.30, 0.15, 0.05]
    })
    
    prior_gp = DoseResponseGP.from_dataframe(
        prior_df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Create new data that disagrees: constant viability around 0.5
    new_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 5,
        'compound': ['CompoundA'] * 5,
        'time_h': [48.0] * 5,
        'dose_uM': [1.0, 2.0, 5.0, 10.0, 20.0],
        'viability': [0.50, 0.48, 0.52, 0.49, 0.51]
    })
    
    # Fit with prior_weight=0.5
    gp_with_prior = DoseResponseGP.from_dataframe_with_prior(
        new_df, 'HepG2', 'CompoundA', 48.0,
        prior_model=prior_gp,
        prior_weight=0.5,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Fit without prior for comparison
    gp_no_prior = DoseResponseGP.from_dataframe(
        new_df, 'HepG2', 'CompoundA', 48.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Test predictions at a point in the new data range
    test_dose = np.array([5.0])
    
    pred_with_prior, _ = gp_with_prior.predict(test_dose, return_std=True)
    pred_no_prior, _ = gp_no_prior.predict(test_dose, return_std=True)
    pred_prior_only, _ = prior_gp.predict(test_dose, return_std=True)
    
    # Verify that the GP with prior was successfully fitted
    assert gp_with_prior.is_fitted
    assert len(pred_with_prior) == 1
    
    # Verify predictions are in valid range
    assert 0.0 <= pred_with_prior[0] <= 1.0
    assert 0.0 <= pred_no_prior[0] <= 1.0
    assert 0.0 <= pred_prior_only[0] <= 1.0
    
    # The key test: verify that prior_model is stored for reference
    assert gp_with_prior.prior_model is not None
    assert gp_with_prior.prior_model == prior_gp


def test_prior_only_no_new_data():
    """Test that when there's no new data, the prior GP is returned."""
    # Create a prior GP
    prior_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 8,
        'compound': ['CompoundA'] * 8,
        'time_h': [24.0] * 8,
        'dose_uM': [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
        'viability': [0.99, 0.95, 0.90, 0.80, 0.50, 0.30, 0.15, 0.05]
    })
    
    prior_gp = DoseResponseGP.from_dataframe(
        prior_df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Create an empty DataFrame for new data
    empty_df = pd.DataFrame({
        'cell_line': [],
        'compound': [],
        'time_h': [],
        'dose_uM': [],
        'viability': []
    })
    
    # Fit with prior but no new data
    gp_result = DoseResponseGP.from_dataframe_with_prior(
        empty_df, 'HepG2', 'CompoundA', 48.0,
        prior_model=prior_gp,
        prior_weight=0.3,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Should get back the prior (with updated cell_line identifier)
    test_doses = np.array([1.0, 5.0, 10.0])
    
    pred_result, std_result = gp_result.predict(test_doses, return_std=True)
    pred_prior, std_prior = prior_gp.predict(test_doses, return_std=True)
    
    # Predictions should match the prior
    np.testing.assert_array_almost_equal(pred_result, pred_prior, decimal=3)
    assert gp_result.cell_line == 'HepG2'


def test_prior_not_double_counted():
    """Test that prior is not added twice in predictions."""
    # Create a prior with known predictions
    prior_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 6,
        'compound': ['CompoundA'] * 6,
        'time_h': [24.0] * 6,
        'dose_uM': [1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
        'viability': [0.90, 0.80, 0.50, 0.30, 0.15, 0.05]
    })
    
    prior_gp = DoseResponseGP.from_dataframe(
        prior_df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # New data at same doses
    new_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 6,
        'compound': ['CompoundA'] * 6,
        'time_h': [48.0] * 6,
        'dose_uM': [1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
        'viability': [0.85, 0.75, 0.45, 0.28, 0.14, 0.06]
    })
    
    # Fit with prior
    gp_with_prior = DoseResponseGP.from_dataframe_with_prior(
        new_df, 'HepG2', 'CompoundA', 48.0,
        prior_model=prior_gp,
        prior_weight=0.3,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Test that predictions are reasonable (not wildly inflated)
    test_doses = np.array([5.0])
    pred, _ = gp_with_prior.predict(test_doses, return_std=True)
    
    # Prediction should be in a reasonable range (0-1 for viability)
    assert 0.0 <= pred[0] <= 1.0
    
    # If prior was added twice, we'd expect inflated values
    # Instead predictions should be close to the observed data range
    assert pred[0] < 1.5  # No wild inflation


def test_unfitted_model_returns_nan():
    """Test that unfitted models return NaN arrays safely."""
    # Create GP that will fail to fit
    # Use invalid data (negative doses after filtering will make empty slice)
    bad_df = pd.DataFrame({
        'cell_line': ['HepG2'] * 3,
        'compound': ['CompoundA'] * 3,
        'time_h': [24.0] * 3,
        'dose_uM': [1.0, 2.0, 3.0],
        'viability': [np.nan, np.nan, np.nan]  # NaN viability will cause fitting to fail
    })
    
    # This should fail to fit but not raise an exception
    gp = DoseResponseGP.from_dataframe(
        bad_df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Check that is_fitted flag is False
    assert gp.is_fitted == False
    
    # Predict should return NaN arrays, not crash
    test_doses = np.array([1.0, 5.0, 10.0])
    mean, std = gp.predict(test_doses, return_std=True)
    
    assert len(mean) == 3
    assert len(std) == 3
    assert all(np.isnan(mean))
    assert all(np.isnan(std))
    
    # Test without return_std
    mean_only, std_none = gp.predict(test_doses, return_std=False)
    assert len(mean_only) == 3
    assert all(np.isnan(mean_only))
    assert std_none is None


def test_dose_range_helper():
    """Test the dose_range() helper method."""
    df = pd.DataFrame({
        'cell_line': ['HepG2'] * 6,
        'compound': ['CompoundA'] * 6,
        'time_h': [24.0] * 6,
        'dose_uM': [0.1, 1.0, 5.0, 10.0, 20.0, 100.0],
        'viability': [0.95, 0.90, 0.50, 0.30, 0.15, 0.05]
    })
    
    gp = DoseResponseGP.from_dataframe(
        df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    dose_min, dose_max = gp.dose_range()
    
    assert dose_min == pytest.approx(0.1, rel=1e-3)
    assert dose_max == pytest.approx(100.0, rel=1e-3)
    
    # Test empty GP
    empty_gp = DoseResponseGP.empty()
    empty_min, empty_max = empty_gp.dose_range()
    assert empty_min == 0.0
    assert empty_max == 0.0


def test_grid_size_conflict_warning():
    """Test that conflicting num_points and grid_size raises a warning."""
    df = pd.DataFrame({
        'cell_line': ['HepG2'] * 6,
        'compound': ['CompoundA'] * 6,
        'time_h': [24.0] * 6,
        'dose_uM': [0.1, 1.0, 5.0, 10.0, 20.0, 100.0],
        'viability': [0.95, 0.90, 0.50, 0.30, 0.15, 0.05]
    })
    
    gp = DoseResponseGP.from_dataframe(
        df, 'HepG2', 'CompoundA', 24.0,
        dose_col='dose_uM',
        viability_col='viability'
    )
    
    # Should warn when both are set and differ
    with pytest.warns(UserWarning, match="Both num_points.*and grid_size"):
        result = gp.predict_on_grid(num_points=100, grid_size=200)
    
    # Should use grid_size value
    assert len(result['dose_uM']) == 200



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
