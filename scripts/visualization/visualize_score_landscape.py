#!/usr/bin/env python
"""Visualize acquisition score landscape across dose grid."""

import numpy as np
import matplotlib.pyplot as plt

from cell_os.posteriors import SliceKey
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.acquisition import compute_acquisition_score
from cell_os.modeling import DoseResponseGP
from cell_os.simulated_executor import SimulatedImagingExecutor


def main():
    # Setup
    sk_viab = SliceKey("U2OS", "TBHP", 24.0, "viability_fraction")
    sk_stress = SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean")

    viability_gps = {sk_viab: DoseResponseGP.empty()}
    stress_gps = {sk_stress: DoseResponseGP.empty()}
    wm = ImagingWorldModel.from_dicts(viability_gps, stress_gps)

    goal = ImagingWindowGoal(
        viability_min=0.8,
        viability_max=1.0,
        min_cells_per_field=280,
        min_fields_per_well=100,
    )

    # Seed the model
    executor = SimulatedImagingExecutor(goal=goal)
    from cell_os.imaging.acquisition import ExperimentPlan
    seed_plans = [
        ExperimentPlan(sk_stress, d, 0.0) for d in [0.01, 0.1, 1.0, 10.0]
    ]
    wm.update_with_results(executor.run_batch(seed_plans))

    # Evaluate across dose grid
    dose_grid = np.logspace(-3, 2, 200)
    
    viab_gp = wm.viability_gps[sk_viab]
    stress_gp = wm.stress_gps[sk_stress]
    
    viab_mean, _ = viab_gp.predict(dose_grid, return_std=True)
    stress_mean, _ = stress_gp.predict(dose_grid, return_std=False)
    
    viab_mean = np.asarray(viab_mean).reshape(-1)
    if isinstance(stress_mean, tuple):
        stress_mean = stress_mean[0]
    stress_mean = np.asarray(stress_mean).reshape(-1)
    
    # Compute QC and penalties
    cells_pred = 300.0 * viab_mean
    fields_pred = 200.0 * viab_mean
    
    scores = []
    viab_penalties = []
    qc_penalties = []
    
    for i in range(len(dose_grid)):
        # Compute penalties manually to track them
        if viab_mean[i] < goal.viability_min:
            dv = goal.viability_min - viab_mean[i]
            viab_pen = dv * dv
        elif viab_mean[i] > goal.viability_max:
            dv = viab_mean[i] - goal.viability_max
            viab_pen = dv * dv
        else:
            viab_pen = 0.0
        
        qc_pen = 0.0
        if cells_pred[i] < goal.min_cells_per_field:
            dc = goal.min_cells_per_field - cells_pred[i]
            qc_pen += (dc / goal.min_cells_per_field) ** 2
        if fields_pred[i] < goal.min_fields_per_well:
            df = goal.min_fields_per_well - fields_pred[i]
            qc_pen += (df / goal.min_fields_per_well) ** 2
        
        score = compute_acquisition_score(
            viab_mean[i], stress_mean[i], cells_pred[i], fields_pred[i], goal
        )
        
        scores.append(score)
        viab_penalties.append(viab_pen)
        qc_penalties.append(qc_pen)
    
    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Top: predictions
    ax1 = axes[0]
    ax1.plot(dose_grid, viab_mean, 'b-', label='Viability', linewidth=2)
    ax1.plot(dose_grid, stress_mean, 'r-', label='Stress', linewidth=2)
    ax1.axhline(goal.viability_min, color='b', linestyle='--', alpha=0.5, label='Viab Min')
    ax1.axhline(goal.viability_max, color='b', linestyle='--', alpha=0.5, label='Viab Max')
    ax1.set_ylabel('Predicted Value')
    ax1.set_ylim(-0.1, 1.1)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.set_title('Acquisition Score Landscape')
    
    # Bottom: score and penalties
    ax2 = axes[1]
    ax2.plot(dose_grid, scores, 'k-', label='Score', linewidth=2.5)
    ax2.plot(dose_grid, viab_penalties, 'b--', label='Viab Penalty', alpha=0.7)
    ax2.plot(dose_grid, qc_penalties, 'g--', label='QC Penalty', alpha=0.7)
    ax2.axhline(0, color='gray', linestyle='-', alpha=0.3)
    ax2.set_xlabel('Dose (µM)')
    ax2.set_ylabel('Score / Penalty')
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    
    # Mark the maximum score
    max_idx = np.argmax(scores)
    ax2.axvline(dose_grid[max_idx], color='red', linestyle=':', alpha=0.5, 
                label=f'Max Score @ {dose_grid[max_idx]:.3f} µM')
    
    plt.xscale('log')
    plt.tight_layout()
    plt.savefig('acquisition_score_landscape.png', dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: acquisition_score_landscape.png")
    
    # Print summary
    print(f"\nScore Landscape Summary:")
    print(f"  Max score: {max(scores):.3f} at {dose_grid[max_idx]:.4f} µM")
    print(f"  Viability at max: {viab_mean[max_idx]:.3f}")
    print(f"  Stress at max: {stress_mean[max_idx]:.3f}")
    print(f"  Cells/field at max: {cells_pred[max_idx]:.1f}")
    print(f"  Viab penalty at max: {viab_penalties[max_idx]:.4f}")
    print(f"  QC penalty at max: {qc_penalties[max_idx]:.4f}")


if __name__ == "__main__":
    main()
