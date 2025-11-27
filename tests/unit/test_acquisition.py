import sys
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

# Add project root to path

from cell_os.schema import Phase0WorldModel, SliceKey
from cell_os.acquisition import propose_next_experiments
from cell_os.modeling import DoseResponseGP


def test_acquisition():
    print("Testing propose_next_experiments...")

    # 1. Mock a DoseResponseGP
    # We need it to return a predictable grid of stds
    mock_gp_1 = MagicMock(spec=DoseResponseGP)
    mock_gp_1.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0, 10.0]),
        "mean": np.array([0.9, 0.5, 0.1]),
        "std": np.array([0.05, 0.05, 0.05]),  # Low uncertainty
    }

    mock_gp_2 = MagicMock(spec=DoseResponseGP)
    mock_gp_2.predict_on_grid.return_value = {
        "dose_uM": np.array([0.1, 1.0, 10.0]),
        "mean": np.array([0.9, 0.5, 0.1]),
        "std": np.array([0.2, 0.5, 0.2]),  # High uncertainty at 1.0 uM
    }

    # 2. Build a World Model
    key1 = SliceKey("CellA", "DrugA", 24)
    key2 = SliceKey("CellA", "DrugB", 24)

    world = Phase0WorldModel(
        gp_models={key1: mock_gp_1, key2: mock_gp_2},
        noise_df=pd.DataFrame(),
        drift_df=pd.DataFrame(),
    )

    # 3. Run acquisition
    # We expect DrugB (high uncertainty) to be prioritized
    # NOTE: propose_next_experiments now returns (plate_df, priorities_df)
    plate_df, priorities_df = propose_next_experiments(
        world, n_experiments=2, dose_grid_size=3
    )

    print("Plate-level DataFrame (top experiments):")
    print(plate_df)
    print("Full priority table:")
    print(priorities_df)

    # 4. Assertions on the plate-level selection
    assert len(plate_df) == 2

    top = plate_df.iloc[0]
    assert top["compound"] == "DrugB"
    assert top["priority_score"] == 0.5  # The highest std we gave
    assert top["dose_uM"] == 1.0

    print("Acquisition Logic OK.")


if __name__ == "__main__":
    test_acquisition()
