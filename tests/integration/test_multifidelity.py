"""
Integration tests for multi-fidelity learning.

Tests transfer learning from cheap to expensive assays.
"""

import sys
import os
sys.path.append(os.getcwd())

import numpy as np
import pandas as pd
import pytest

from src.modeling import DoseResponseGP


def test_multifidelity_reduces_uncertainty():
    """Test that prior knowledge reduces uncertainty in expensive assay."""
    
    # Create cheap assay data (10 doses)
    cheap_doses = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    cheap_viability = [0.98, 0.95, 0.85, 0.70, 0.50, 0.30, 0.15, 0.10, 0.08, 0.05]
    
    df_cheap = pd.DataFrame({
        'cell_line': ['Reporter'] * 10,
        'compound': ['CompoundA'] * 10,
        'time_h': [24.0] * 10,
        'dose': cheap_doses,
        'viability': cheap_viability
    })
    
    # Train cheap assay GP
    cheap_gp = DoseResponseGP.from_dataframe(
        df_cheap, 'Reporter', 'CompoundA', 24.0,
        dose_col='dose', viability_col='viability'
    )
    
    # Create small expensive assay data (only 3 doses!)
    expensive_doses = [0.5, 5.0, 50.0]
    expensive_viability = [0.80, 0.25, 0.07]
    
    df_expensive = pd.DataFrame({
        'cell_line': ['PrimaryCell'] * 3,
        'compound': ['CompoundA'] * 3,
        'time_h': [24.0] * 3,
        'dose': expensive_doses,
        'viability': expensive_viability
    })
    
    # Train without prior
    expensive_gp_no_prior = DoseResponseGP.from_dataframe(
        df_expensive, 'PrimaryCell', 'CompoundA', 24.0,
        dose_col='dose', viability_col='viability'
    )
    
    # Train with prior (transfer learning)
    expensive_gp_with_prior = DoseResponseGP.from_dataframe_with_prior(
        df_expensive, 'PrimaryCell', 'CompoundA', 24.0,
        prior_model=cheap_gp,
        prior_weight=0.3,
        dose_col='dose', viability_col='viability'
    )
    
    # Compare uncertainty at interpolation point
    test_dose = [2.0]
    
    _, std_no_prior = expensive_gp_no_prior.predict(test_dose, return_std=True)
    _, std_with_prior = expensive_gp_with_prior.predict(test_dose, return_std=True)
    
    # Prior should reduce uncertainty
    assert std_with_prior[0] < std_no_prior[0], \
        "Transfer learning should reduce uncertainty"
    
    print(f"✓ Uncertainty reduced: {std_no_prior[0]:.3f} → {std_with_prior[0]:.3f}")


def test_multifidelity_with_no_data():
    """Test that prior alone can provide predictions when no new data."""
    
    # Train prior on cheap assay
    df_cheap = pd.DataFrame({
        'cell_line': ['Reporter'] * 6,
        'compound': ['CompoundB'] * 6,
        'time_h': [24.0] * 6,
        'dose': [0.1, 1.0, 5.0, 10.0, 50.0, 100.0],
        'viability': [0.95, 0.80, 0.50, 0.30, 0.10, 0.05]
    })
    
    cheap_gp = DoseResponseGP.from_dataframe(
        df_cheap, 'Reporter', 'CompoundB', 24.0,
        dose_col='dose', viability_col='viability'
    )
    
    # Empty expensive assay data
    df_empty = pd.DataFrame({
        'cell_line': [],
        'compound': [],
        'time_h': [],
        'dose': [],
        'viability': []
    })
    
    # Should use prior when no data
    gp = DoseResponseGP.from_dataframe_with_prior(
        df_empty, 'PrimaryCell', 'CompoundB', 24.0,
        prior_model=cheap_gp,
        dose_col='dose', viability_col='viability'
    )
    
    # Should still make predictions
    mean, std = gp.predict([1.0, 10.0], return_std=True)
    
    assert len(mean) == 2
    assert all(std > 0)
    print("✓ Prior alone provides predictions")


def test_prior_weight_sensitivity():
    """Test that prior weight controls influence."""
    
    # Cheap assay suggests low potency (IC50 ~50)
    df_cheap = pd.DataFrame({
        'cell_line': ['Reporter'] * 5,
        'compound': ['CompoundC'] * 5,
        'time_h': [24.0] * 5,
        'dose': [1.0, 10.0, 50.0, 100.0, 200.0],
        'viability': [0.90, 0.70, 0.50, 0.30, 0.15]
    })
    
    cheap_gp = DoseResponseGP.from_dataframe(
        df_cheap, 'Reporter', 'CompoundC', 24.0,
        dose_col='dose', viability_col='viability'
    )
    
    # Expensive assay suggests high potency (IC50 ~5)
    df_expensive = pd.DataFrame({
        'cell_line': ['PrimaryCell'] * 4,
        'compound': ['CompoundC'] * 4,
        'time_h': [24.0] * 4,
        'dose': [1.0, 5.0, 10.0, 50.0],
        'viability': [0.85, 0.50, 0.25, 0.10]
    })
    
    # Low prior weight (trust expensive data more)
    gp_low_weight = DoseResponseGP.from_dataframe_with_prior(
        df_expensive, 'PrimaryCell', 'CompoundC', 24.0,
        prior_model=cheap_gp,
        prior_weight=0.1,
        dose_col='dose', viability_col='viability'
    )
    
    # High prior weight (trust prior more)
    gp_high_weight = DoseResponseGP.from_dataframe_with_prior(
        df_expensive, 'PrimaryCell', 'CompoundC', 24.0,
        prior_model=cheap_gp,
        prior_weight=0.8,
        dose_col='dose', viability_col='viability'
    )
    
    # Predictions should differ based on weight
    mean_low, _ = gp_low_weight.predict([5.0], return_std=True)
    mean_high, _ = gp_high_weight.predict([5.0], return_std=True)
    
    # They should be different
    assert abs(mean_low[0] - mean_high[0]) > 0.01, \
        "Prior weight should affect predictions"
    
    print(f"✓ Prior weight effect: low={mean_low[0]:.3f}, high={mean_high[0]:.3f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
