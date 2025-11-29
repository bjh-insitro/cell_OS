import sys
import pandas as pd

# Add project root to path

from cell_os.legacy_simulation import simulate_plate_data

def test_simulation():
    print("Testing simulate_plate_data...")
    
    # Generate a small dataset
    df = simulate_plate_data(
        cell_lines=["HepG2"],
        compounds=["staurosporine"],
        n_plates_per_line=1,
        replicates_per_dose=1
    )
    
    print(f"Generated DataFrame with {len(df)} rows.")
    print("Columns:", df.columns.tolist())
    
    # Checks
    assert not df.empty
    assert "viability_norm" in df.columns
    assert "is_control" in df.columns
    
    # Check that we have controls
    n_controls = df[df["is_control"] == 1].shape[0]
    print(f"Number of control wells: {n_controls}")
    assert n_controls > 0
    
    # Check that we have treated wells
    n_treated = df[df["is_control"] == 0].shape[0]
    print(f"Number of treated wells: {n_treated}")
    assert n_treated > 0
    
    # Check normalization range (roughly)
    # Viability should be around 1.0 for controls
    mean_control = df[df["is_control"] == 1]["viability_norm"].mean()
    print(f"Mean control viability: {mean_control:.4f}")
    assert 0.8 < mean_control < 1.2
    
    print("Simulation Logic OK.")

if __name__ == "__main__":
    test_simulation()
