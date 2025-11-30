"""
Integration tests for LV Titration Wrapper.
"""

import pytest
import pandas as pd
import numpy as np
from cell_os.simulation.titration_wrapper import simulate_titration, TitrationResultBundle

def test_simulate_titration_success():
    """Test that titration simulation returns a successful result bundle."""
    result = simulate_titration(
        cell_line="U2OS",
        true_titer_tu_ml=1.0e8,
        target_transduction_efficiency=0.30,
        cells_per_well=100000,
        replicates=2
    )
    
    assert result.success
    assert result.cell_line == "U2OS"
    assert isinstance(result.data, pd.DataFrame)
    assert not result.data.empty
    assert "fraction_bfp" in result.data.columns
    assert result.model is not None
    assert result.r_squared > 0.9 # Synthetic data should fit well
    
    # Check that fitted titer is close to true titer (within 20%)
    # Note: true_titer is passed in TU/mL, result has fitted_titer_tu_ml
    assert np.isclose(result.fitted_titer_tu_ml, 1.0e8, rtol=0.2)
    
    # Check recommendation
    assert result.recommended_vol_ul > 0

def test_simulate_titration_low_titer():
    """Test simulation with a lower titer."""
    true_titer = 1.0e6
    result = simulate_titration(
        cell_line="HepG2",
        true_titer_tu_ml=true_titer,
        target_transduction_efficiency=0.10,
        cells_per_well=50000
    )
    
    assert result.success
    assert np.isclose(result.fitted_titer_tu_ml, true_titer, rtol=0.2)
    
    # Lower titer should require higher volume for same effect
    # Compared to previous test (1e8 titer), this should need ~100x more volume
    # But cells_per_well is half, so ~50x more volume
    assert result.recommended_vol_ul > 1.0 # Likely high volume

def test_simulate_titration_custom_volumes():
    """Test with custom volume range."""
    vols = [0.01, 0.02, 0.05]
    result = simulate_titration(
        cell_line="A549",
        true_titer_tu_ml=1.0e9,
        vol_range_ul=vols
    )
    
    assert result.success
    assert len(result.data) == len(vols) * 2 # 2 replicates default
    assert set(result.data["volume_ul"].unique()) == set(vols)

def test_simulate_titration_reproducibility():
    """Test that random seed produces identical results."""
    seed = 12345
    res1 = simulate_titration("U2OS", random_seed=seed)
    res2 = simulate_titration("U2OS", random_seed=seed)
    
    pd.testing.assert_frame_equal(res1.data, res2.data)
    assert res1.fitted_titer_tu_ml == res2.fitted_titer_tu_ml
