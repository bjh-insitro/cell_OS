
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from cell_os.acquisition import AcquisitionFunction, propose_next_experiments
from cell_os.schema import Phase0WorldModel

# Mock GP class to simulate predict_on_grid
class MockGP:
    def __init__(self, cell_line="HeLa", compound="DrugA", time_h=24.0):
        self.cell_line = cell_line
        self.compound = compound
        self.time_h = time_h
        self.X_train = np.array([[0.0]]) # Dummy
        
    def predict_on_grid(self, num_points=50, dose_min=0.001, dose_max=10.0):
        # Return dummy grid with high uncertainty
        doses = np.linspace(dose_min, dose_max, num_points)
        return {
            "dose_uM": doses,
            "mean": np.zeros_like(doses),
            "std": np.ones_like(doses) * 0.5  # Constant uncertainty
        }

def test_budget_constraint():
    """Test that n_experiments is capped by budget."""
    # Cost per well = $10. Budget = $50. Should propose max 5 experiments.
    acq = AcquisitionFunction(reward_config={"cost_per_well_usd": 10.0})
    
    # Mock model
    gp = MockGP()
    
    # Request 100 experiments
    df = acq.propose(model=gp, assay=None, budget=50.0, n_experiments=100)
    
    assert len(df) <= 5
    assert len(df) > 0
    assert df["expected_cost_usd"].sum() <= 50.0

def test_budget_insufficient():
    """Test that insufficient budget returns empty DataFrame."""
    acq = AcquisitionFunction(reward_config={"cost_per_well_usd": 100.0})
    gp = MockGP()
    
    # Budget $50 < Cost $100
    df = acq.propose(model=gp, assay=None, budget=50.0, n_experiments=8)
    
    assert len(df) == 0
    assert "cell_line" in df.columns

def test_scoring_mode_max_uncertainty():
    """Test max_uncertainty scoring mode."""
    acq = AcquisitionFunction(reward_config={"mode": "max_uncertainty"})
    
    # base_std=0.5, penalty=0.1, cost=10
    # score = 0.5 - 0.1 = 0.4
    score = acq._score_candidate(base_std=0.5, penalty=0.1, cost=10.0)
    assert score == pytest.approx(0.4)

def test_scoring_mode_ig_per_cost():
    """Test ig_per_cost scoring mode."""
    acq = AcquisitionFunction(reward_config={"mode": "ig_per_cost"})
    
    # base_std=0.5, penalty=0.1, cost=10
    # score = (0.5 - 0.1) / 10 = 0.04
    score = acq._score_candidate(base_std=0.5, penalty=0.1, cost=10.0)
    assert score == pytest.approx(0.04)

def test_legacy_wrapper():
    """Test that propose_next_experiments wrapper works."""
    # Create a mock world model
    wm = MagicMock(spec=Phase0WorldModel)
    gp1 = MockGP(cell_line="A", compound="B", time_h=24)
    wm.gp_models = {gp1: gp1} # Key is same as value for simple mock
    
    selected, candidates = propose_next_experiments(wm, n_experiments=2)
    
    assert isinstance(selected, pd.DataFrame)
    assert isinstance(candidates, pd.DataFrame)
    assert len(selected) <= 2
    assert "plate_id" in selected.columns
    assert "well_id" in selected.columns

def test_fallback_logic():
    """Test fallback when GP fails or returns no candidates."""
    acq = AcquisitionFunction()
    
    # Mock GP that raises error on predict
    bad_gp = MockGP()
    bad_gp.predict_on_grid = MagicMock(side_effect=Exception("GP Error"))
    
    # Should not crash, should return default fallback
    df = acq.propose(model=bad_gp, assay=None, n_experiments=1)
    
    assert len(df) == 1
    assert df.iloc[0]["priority_score"] == 0.0
    assert df.iloc[0]["dose_uM"] == 1.0 # Default fallback dose
