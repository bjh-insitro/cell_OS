
import sys
import os
import pandas as pd
import numpy as np

from cell_os.simulation import SimulationEngine

def test_simulation_realism():
    print("Testing simulation realism...")
    
    sim = SimulationEngine(world_model=None)
    
    # Create a proposal with multiple batches
    proposal = pd.DataFrame([
        {"cell_line": "HepG2", "compound": "staurosporine", "dose": 1.0, "plate_id": "Batch_A"},
        {"cell_line": "HepG2", "compound": "staurosporine", "dose": 1.0, "plate_id": "Batch_A"},
        {"cell_line": "HepG2", "compound": "staurosporine", "dose": 1.0, "plate_id": "Batch_B"},
        {"cell_line": "HepG2", "compound": "staurosporine", "dose": 1.0, "plate_id": "Batch_B"},
    ])
    
    records = sim.run(proposal)
    df = pd.DataFrame(records)
    
    print("Columns:", df.columns)
    
    # Verify Pipetting Noise
    # dose should not equal actual_dose (mostly)
    diffs = np.abs(df["dose"] - df["actual_dose"])
    print(f"Mean dose difference: {diffs.mean()}")
    if diffs.mean() == 0:
        raise ValueError("No pipetting noise detected!")
        
    # Verify Batch Effects
    # batch_effect should be recorded
    print("Batch effects:", df["batch_effect"].unique())
    if len(df["batch_effect"].unique()) < 2:
        raise ValueError("No batch variability detected across batches!")
        
    print("Simulation verification passed!")

if __name__ == "__main__":
    test_simulation_realism()
