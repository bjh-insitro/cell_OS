import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from cell_os.posteriors import SliceKey, DoseResponsePosterior
from cell_os.lab_world_model import LabWorldModel
from cell_os.acquisition import AcquisitionFunction
from cell_os.campaign import StressWindowGoal, PotencyGoal


def test_slice_key_defaults():
    """Test SliceKey backward compatibility."""
    # Old style: 3 args
    k1 = SliceKey("A", "B", 24)
    assert k1.cell_line == "A"
    assert k1.compound == "B"
    assert k1.time_h == 24
    assert k1.readout == "viability"  # Default

    # New style: 4 args
    k2 = SliceKey("A", "B", 24, "posh")
    assert k2.readout == "posh"


def test_posterior_multi_readout():
    """Test building posterior with multiple readouts."""
    # Create dummy experiment data - long format
    df = pd.DataFrame(
        {
            "campaign_id": ["C1"] * 4,
            "cell_line": ["HeLa"] * 4,
            "compound": ["DrugA"] * 4,
            "time_h": [24] * 4,
            "dose_uM": [0.1, 1.0, 0.1, 1.0],
            "readout_name": ["viability", "viability", "posh", "posh"],
            "readout_value": [0.9, 0.1, 0.2, 0.8],
            "plate_id": ["P1"] * 4,
            "replicate": [1] * 4,
        }
    )

    wm = LabWorldModel.empty()
    wm.add_experiments(df)

    # Mock DoseResponseGP.from_dataframe to avoid actual fitting
    with patch("cell_os.posteriors.DoseResponseGP.from_dataframe") as mock_from_df:
        mock_gp = MagicMock()
        mock_from_df.return_value = mock_gp

        # Build posterior for both readouts
        post = DoseResponsePosterior.from_world(
            wm,
            campaign_id="C1",
            readout_names=["viability", "posh"],
        )

        assert len(post.gp_models) == 2

        key_viab = SliceKey("HeLa", "DrugA", 24, "viability")
        key_posh = SliceKey("HeLa", "DrugA", 24, "posh")

        assert key_viab in post.gp_models
        assert key_posh in post.gp_models


def test_acquisition_multi_readout():
    """Test acquisition proposes experiments for all readouts."""
    # Mock world model with 2 GPs
    gp_viab = MagicMock()
    gp_viab.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0]),
        "std": np.array([0.5, 0.5]),
    }
    # Predict used for repeat penalty - return mean, std
    gp_viab.predict.return_value = (np.array([0.5, 0.5]), None)

    gp_posh = MagicMock()
    gp_posh.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0]),
        "std": np.array([0.5, 0.5]),
    }
    gp_posh.predict.return_value = (np.array([0.5, 0.5]), None)

    wm = MagicMock()
    wm.gp_models = {
        SliceKey("HeLa", "DrugA", 24, "viability"): gp_viab,
        SliceKey("HeLa", "DrugA", 24, "posh"): gp_posh,
    }

    acq = AcquisitionFunction()

    # Propose experiments
    proposals = acq.propose(wm, assay=None, n_experiments=10)

    assert "readout" in proposals.columns
    assert "viability" in proposals["readout"].values
    assert "posh" in proposals["readout"].values


def test_stress_window_goal():
    """Test StressWindowGoal."""
    # Mock world model
    gp = MagicMock()

    # Predict linear ramp 0.0 to 1.0 over doses. Return tuple (mean, std).
    def ramp_predict(x, return_std=True):
        x = np.asarray(x)
        mean = np.linspace(0.0, 1.0, len(x))
        std = None
        if return_std:
            return mean, std
        return mean, None  # Must return tuple

    gp.predict.side_effect = ramp_predict

    wm = MagicMock()
    wm.gp_models = {
        SliceKey("HeLa", "Stressor1", 24, "viability"): gp,
    }

    # Goal: find dose where viability is 0.4 to 0.6
    goal = StressWindowGoal(
        cell_line="HeLa",
        stressor="Stressor1",
        readout="viability",
        min_val=0.4,
        max_val=0.6,
    )

    assert goal.is_met(wm)
    assert goal.met_by_dose is not None


def test_potency_goal_readout():
    """Test PotencyGoal with specific readout."""
    gp = MagicMock()
    
    # Predict low values (potent) - return tuple (mean, std)
    # Must handle arbitrary input size (n_grid=200 default)
    def constant_predict(x, return_std=True):
        x = np.asarray(x)
        mean = np.array([0.1] * len(x))
        return mean, None
        
    gp.predict.side_effect = constant_predict

    wm = MagicMock()
    wm.gp_models = {
        SliceKey("HeLa", "DrugA", 24, "posh"): gp,
    }

    # Goal for "posh" readout
    goal = PotencyGoal(
        cell_line="HeLa",
        ic50_threshold_uM=1.0,
        readout="posh",
    )

    assert goal.is_met(wm)
    assert goal.met_by == "DrugA"
