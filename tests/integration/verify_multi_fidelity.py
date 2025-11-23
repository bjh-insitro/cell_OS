"""
Verification script for Multi-Fidelity Learning.

Demonstrates that using a cheap, low-fidelity model (Imaging) as a prior
improves the performance of a high-fidelity model (RNA-seq) when data is scarce.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from src.simulation import simulate_plate_data, simulate_low_fidelity_data
from src.modeling import DoseResponseGP, DoseResponseGPConfig

def verify_transfer_learning():
    print("=" * 70)
    print("MULTI-FIDELITY LEARNING VERIFICATION")
    print("=" * 70)
    
    cell_line = "HepG2"
    compound = "staurosporine"
    time_h = 24
    
    # 1. Generate Data
    print("\n[1] Generating Data...")
    
    # Low-Fidelity Data (Cheap, Abundant, Biased)
    # Simulate 3 plates of imaging data (dense dose grid)
    print("  Generating Low-Fidelity Data (Imaging)...")
    df_low_fi = simulate_low_fidelity_data(
        cell_lines=[cell_line],
        compounds=[compound],
        doses=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
        time_points=[time_h],
        n_replicates=3,
        bias=0.15,       # Significant bias
        noise_scale=0.1  # Higher noise
    )
    print(f"  -> {len(df_low_fi)} data points")
    
    # High-Fidelity Data (Expensive, Scarce, Ground Truth)
    # Simulate 1 plate of RNA-seq data (sparse dose grid for training)
    print("  Generating High-Fidelity Data (RNA-seq)...")
    df_high_fi_all = simulate_plate_data(
        cell_lines=[cell_line],
        compounds=[compound],
        doses_small=np.array([0.001, 0.01, 0.1, 1.0, 10.0]), # Sparse
        n_plates_per_line=1,
        replicates_per_dose=1, # Single replicate!
        random_seed=123
    )
    
    # Split High-Fi into Train (Scarce) and Test (Ground Truth)
    # We'll use a very small training set to simulate scarcity
    df_train = df_high_fi_all.sample(n=5, random_state=42) # Only 5 points!
    
    # Generate a dense ground truth test set
    df_test = simulate_plate_data(
        cell_lines=[cell_line],
        compounds=[compound],
        doses_small=np.array([0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]),
        n_plates_per_line=5, # Lots of data for testing
        replicates_per_dose=3,
        random_seed=999
    )
    # Filter for specific condition
    df_test = df_test[
        (df_test["cell_line"] == cell_line) & 
        (df_test["compound"] == compound) & 
        (df_test["time_h"] == time_h) &
        (df_test["is_control"] == 0)
    ]
    
    print(f"  -> Training Set: {len(df_train)} points")
    print(f"  -> Test Set: {len(df_test)} points")
    
    # 2. Train Low-Fidelity Model (The Prior)
    print("\n[2] Training Low-Fidelity Prior...")
    gp_prior = DoseResponseGP.from_dataframe(
        df_low_fi,
        cell_line=cell_line,
        compound=compound,
        time_h=time_h,
        viability_col="viability_norm"
    )
    
    # 3. Train Standard GP (No Transfer)
    print("\n[3] Training Standard GP (Baseline)...")
    gp_standard = DoseResponseGP.from_dataframe(
        df_train,
        cell_line=cell_line,
        compound=compound,
        time_h=time_h,
        viability_col="viability_norm"
    )
    
    # 4. Train Transfer GP (With Prior)
    print("\n[4] Training Transfer GP (Multi-Fidelity)...")
    gp_transfer = DoseResponseGP.from_dataframe(
        df_train,
        cell_line=cell_line,
        compound=compound,
        time_h=time_h,
        viability_col="viability_norm",
        prior_model=gp_prior
    )
    
    # 5. Evaluate
    print("\n[5] Evaluation...")
    
    X_test = df_test["dose_uM"].values
    y_test = df_test["viability_norm"].values
    
    # Standard Prediction
    y_pred_std, _ = gp_standard.predict(X_test)
    rmse_std = np.sqrt(mean_squared_error(y_test, y_pred_std))
    
    # Transfer Prediction
    y_pred_trans, _ = gp_transfer.predict(X_test)
    rmse_trans = np.sqrt(mean_squared_error(y_test, y_pred_trans))
    
    print(f"\nResults (RMSE on Test Set):")
    print(f"  Standard GP: {rmse_std:.4f}")
    print(f"  Transfer GP: {rmse_trans:.4f}")
    
    improvement = (rmse_std - rmse_trans) / rmse_std * 100
    print(f"  Improvement: {improvement:.1f}%")
    
    if rmse_trans < rmse_std:
        print("\nSUCCESS: Transfer learning improved performance!")
    else:
        print("\nFAILURE: Transfer learning did not improve performance.")

if __name__ == "__main__":
    verify_transfer_learning()
