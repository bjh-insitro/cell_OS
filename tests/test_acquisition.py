import sys
import os
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.schema import Phase0WorldModel, SliceKey
from src.acquisition import propose_next_experiments
from src.modeling import DoseResponseGP

def test_acquisition():
    print("Testing propose_next_experiments...")
    
    # 1. Mock a DoseResponseGP
    # We need it to return a predictable grid of stds
    mock_gp_1 = MagicMock(spec=DoseResponseGP)
    mock_gp_1.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0, 10.0]),
        "mean": np.array([0.9, 0.5, 0.1]),
        "std": np.array([0.05, 0.05, 0.05])  # Low uncertainty
    }
    
    mock_gp_2 = MagicMock(spec=DoseResponseGP)
    mock_gp_2.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0, 10.0]),
        "mean": np.array([0.9, 0.5, 0.1]),
        "std": np.array([0.2, 0.5, 0.2])  # High uncertainty at 1.0 uM
    }
    
    # 2. Build a World Model
    key1 = SliceKey("CellA", "DrugA", 24)
    key2 = SliceKey("CellA", "DrugB", 24)
    
    world = Phase0WorldModel(
        gp_models={key1: mock_gp_1, key2: mock_gp_2},
        noise_df=pd.DataFrame(),
        drift_df=pd.DataFrame()
    )
    
    # 3. Run acquisition
    # We expect DrugB (high uncertainty) to be prioritized
    df = propose_next_experiments(world, n_experiments=2, dose_grid_size=3)
    
    print("Result DataFrame:")
    print(df)
    
    # 4. Assertions
    assert len(df) == 2
    assert df.iloc[0]["compound"] == "DrugB"
    assert df.iloc[0]["priority_score"] == 0.5  # The highest std we gave
    assert df.iloc[0]["dose_uM"] == 1.0
    
    print("Acquisition Logic OK.")

if __name__ == "__main__":
    test_acquisition()
