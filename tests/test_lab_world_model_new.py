
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from src.lab_world_model import LabWorldModel, Campaign
from src.posteriors import DoseResponsePosterior

def test_lab_world_model_initialization():
    """Test basic initialization and empty state."""
    wm = LabWorldModel.empty()
    assert wm.cell_lines.empty
    assert wm.experiments.empty
    assert wm.campaigns == {}
    assert wm.posteriors == {}

def test_from_static_tables():
    """Test initialization from static tables."""
    cell_lines = pd.DataFrame({"cell_line": ["A", "B"], "tissue": ["Lung", "Liver"]})
    workflows = pd.DataFrame({"workflow_id": ["WF1"], "cost_usd": [100.0]})
    
    wm = LabWorldModel.from_static_tables(cell_lines=cell_lines, workflows=workflows)
    
    assert not wm.cell_lines.empty
    assert len(wm.cell_lines) == 2
    assert not wm.workflows.empty
    assert wm.workflows.iloc[0]["workflow_id"] == "WF1"

def test_add_experiments_canonicalization():
    """Test that adding experiments canonicalizes columns."""
    wm = LabWorldModel.empty()
    
    # Raw data with non-canonical names
    raw_df = pd.DataFrame({
        "workflow": ["WF1"],
        "dose": [1.0],
        "readout_name": ["viability"],
        "readout_value": [0.8],
        "extra_col": ["ignore"]
    })
    
    wm.add_experiments(raw_df)
    
    assert not wm.experiments.empty
    cols = wm.experiments.columns
    assert "workflow_id" in cols # Renamed from workflow
    assert "dose_uM" in cols     # Renamed from dose
    assert "viability" in cols   # Extracted from readout_value
    assert wm.experiments.iloc[0]["viability"] == 0.8

def test_get_workflow_cost():
    """Test cost lookup with different column names."""
    # Case 1: cost_usd
    wm1 = LabWorldModel.from_static_tables(
        workflows=pd.DataFrame({"workflow_id": ["WF1"], "cost_usd": [50.0]})
    )
    assert wm1.get_workflow_cost("WF1") == 50.0
    
    # Case 2: estimated_cost_usd
    wm2 = LabWorldModel.from_static_tables(
        workflows=pd.DataFrame({"id": ["WF2"], "estimated_cost_usd": [75.0]})
    )
    assert wm2.get_workflow_cost("WF2") == 75.0
    
    # Case 3: Missing
    assert wm1.get_workflow_cost("WF_MISSING") is None

def test_get_slice():
    """Test filtering experiments."""
    wm = LabWorldModel.empty()
    df = pd.DataFrame({
        "campaign_id": ["C1", "C1", "C2"],
        "cell_line": ["A", "B", "A"],
        "compound": ["D1", "D1", "D1"],
        "time_h": [24, 24, 48],
        "viability": [0.5, 0.6, 0.7]
    })
    wm.add_experiments(df)
    
    # Filter by campaign
    s1 = wm.get_slice(campaign_id="C1")
    assert len(s1) == 2
    
    # Filter by cell line
    s2 = wm.get_slice(cell_line="A")
    assert len(s2) == 2
    
    # Filter by multiple
    s3 = wm.get_slice(campaign_id="C1", cell_line="A")
    assert len(s3) == 1
    assert s3.iloc[0]["viability"] == 0.5

def test_build_dose_response_posterior():
    """Test building and attaching a posterior."""
    wm = LabWorldModel.empty()
    
    # Add some dummy data
    df = pd.DataFrame({
        "campaign_id": ["C1"],
        "cell_line": ["A"],
        "compound": ["D1"],
        "dose_uM": [1.0],
        "viability": [0.5],
        "time_h": [24]
    })
    wm.add_experiments(df)
    
    # Mock DoseResponsePosterior.from_world
    with patch("src.posteriors.DoseResponsePosterior.from_world") as mock_from_world:
        mock_posterior = MagicMock(spec=DoseResponsePosterior)
        mock_from_world.return_value = mock_posterior
        
        post = wm.build_dose_response_posterior("C1")
        
        assert post == mock_posterior
        assert wm.get_posterior("C1") == mock_posterior
        mock_from_world.assert_called_once()

def test_add_campaign():
    """Test adding and retrieving campaigns."""
    wm = LabWorldModel.empty()
    c = Campaign(id="C1", name="Test", objective="Obj", primary_readout="viability")
    
    wm.add_campaign(c)
    assert wm.get_campaign("C1") == c
    assert len(wm.list_campaigns()) == 1
