"""
Verification script for Advanced Simulation Robustness.

Tests the impact of batch effects and pipetting noise on the simulation
and the GP model's ability to handle it.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from cell_os.simulation import simulate_plate_data
from cell_os.modeling import DoseResponseGP

def verify_robustness():
    print("=" * 70)
    print("SIMULATION ROBUSTNESS VERIFICATION")
    print("=" * 70)
    
    cell_line = "HepG2"
    compound = "staurosporine"
    time_h = 24
    
    # 1. Baseline: Low Noise
    print("\n[1] Baseline Simulation (Low Noise)...")
    df_base = simulate_plate_data(
        cell_lines=[cell_line],
        compounds=[compound],
        n_plates_per_line=3,
        random_seed=42,
        batch_factor_cv=0.0, # No batch effect
        pipetting_cv=0.0     # No pipetting error
    )
    
    # Filter out zero doses for GP fitting
    df_base_fit = df_base[df_base["dose_uM"] > 0].copy()
    
    gp_base = DoseResponseGP.from_dataframe(
        df_base_fit, cell_line, compound, time_h, viability_col="viability_norm"
    )
    noise_base = np.exp(gp_base.model.kernel_.theta[-1]) # WhiteKernel noise level
    print(f"  Estimated Noise Level (Log-Likelihood): {noise_base:.4f}")
    
    # 2. High Noise: Batch Effects + Pipetting Error
    print("\n[2] High Noise Simulation (Batch + Pipetting)...")
    df_noisy = simulate_plate_data(
        cell_lines=[cell_line],
        compounds=[compound],
        n_plates_per_line=3,
        random_seed=42,
        batch_factor_cv=0.2, # 20% batch variation
        pipetting_cv=0.1     # 10% pipetting error
    )
    
    # Filter out zero doses
    df_noisy_fit = df_noisy[df_noisy["dose_uM"] > 0].copy()
    
    gp_noisy = DoseResponseGP.from_dataframe(
        df_noisy_fit, cell_line, compound, time_h, viability_col="viability_norm"
    )
    noise_noisy = np.exp(gp_noisy.model.kernel_.theta[-1])
    print(f"  Estimated Noise Level (Log-Likelihood): {noise_noisy:.4f}")
    
    # 3. Comparison
    print("\n[3] Comparison...")
    if noise_noisy > noise_base:
        print("  SUCCESS: GP correctly estimated higher noise in the noisy simulation.")
        print(f"  Ratio (Noisy/Base): {noise_noisy/noise_base:.2f}x")
    else:
        print("  WARNING: GP did not estimate higher noise. Check simulation parameters.")

if __name__ == "__main__":
    verify_robustness()
