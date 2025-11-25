import sys
import pandas as pd

# Add project root to path

from cell_os.schema import Phase0WorldModel, SliceKey
from cell_os.modeling import DoseResponseGP, DoseResponseGPConfig

def test_schema():
    print("Testing SliceKey...")
    key = SliceKey("HepG2", "staurosporine", 24)
    assert key.cell_line == "HepG2"
    assert key.compound == "staurosporine"
    assert key.time_h == 24
    print("SliceKey OK.")

    print("Testing Phase0WorldModel...")
    # Create a dummy GP (we won't fit it, just instantiate)
    # We need to mock the internal model or just let it be empty/default for this test
    # DoseResponseGP requires a fit model usually, but let's see if we can instantiate it
    # actually DoseResponseGP.from_dataframe is the main way, but we can construct manually if needed.
    # For this test, let's just check the dictionary holding it.
    
    world = Phase0WorldModel(
        gp_models={},
        noise_df=pd.DataFrame({"col": [1, 2]}),
        drift_df=pd.DataFrame({"plate": ["P1"]})
    )
    
    assert isinstance(world.gp_models, dict)
    assert not world.noise_df.empty
    assert not world.drift_df.empty
    
    # Test get_gp returns None for missing key
    assert world.get_gp("A", "B", 1) is None
    
    print("Phase0WorldModel OK.")

if __name__ == "__main__":
    test_schema()
