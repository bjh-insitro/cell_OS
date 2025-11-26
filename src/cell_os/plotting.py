"""
plotting.py

Visualize the results of the autonomous loop.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from cell_os.simulation import TRUE_IC50, HILL_SLOPES, logistic_viability

def plot_simulation_results(csv_path: str, output_dir: str = "results/figures"):
    """
    Plot the dose-response curves and the sampled points.
    """
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)

    # Group by slice
    slices = df.groupby(["cell_line", "compound", "time_h"])

    for (cell, cmpd, time), sub_df in slices:
        plt.figure(figsize=(8, 6))
        
        # 1. Plot Ground Truth Curve
        ic50 = TRUE_IC50.get((cell, cmpd), 1.0)
        h = HILL_SLOPES.get(cmpd, 1.0)
        
        dose_grid = np.logspace(-4, 2, 200) # 0.0001 to 100 uM
        true_viab = [logistic_viability(d, ic50, h) for d in dose_grid]
        
        plt.plot(dose_grid, true_viab, "k--", label="True Curve", alpha=0.6)
        
        # 2. Plot Observed Data
        # Color by "Phase" (we can infer phase from 'date' or just order, 
        # but let's assume we can distinguish Phase 0 from later cycles).
        # In our simulation, Phase 0 has date '2025-11-0X', later cycles '2025-11-22'.
        
        phase0 = sub_df[sub_df["date"].str.contains("2025-11-0")]
        cycles = sub_df[~sub_df["date"].str.contains("2025-11-0")]
        
        plt.scatter(
            phase0["dose_uM"], 
            phase0["viability_norm"], 
            c="gray", alpha=0.5, label="Phase 0 (Baseline)"
        )
        
        if not cycles.empty:
            plt.scatter(
                cycles["dose_uM"], 
                cycles["viability_norm"], 
                c="red", s=50, edgecolors="black", label="Agent Selected"
            )
            
        plt.xscale("log")
        plt.xlabel("Dose (µM)")
        plt.ylabel("Viability (Normalized)")
        plt.title(f"{cell} + {cmpd} (Time: {time}h)")
        plt.legend()
        plt.grid(True, which="both", alpha=0.3)
        
        filename = f"{cell}_{cmpd}_{time}h.png"
        save_path = os.path.join(output_dir, filename)
        plt.savefig(save_path)
        plt.close()
        print(f"Saved plot to {save_path}")

if __name__ == "__main__":
    plot_simulation_results("results/experiment_history.csv")
