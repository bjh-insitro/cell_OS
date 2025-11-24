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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
