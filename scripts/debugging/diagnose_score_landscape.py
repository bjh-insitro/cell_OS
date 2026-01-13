#!/usr/bin/env python
"""Diagnose acquisition score landscape across dose grid (text output)."""

import numpy as np

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
    dose_grid = np.logspace(-3, 2, 50)  # Fewer points for readability
    
    viab_gp = wm.viability_gps[sk_viab]
    stress_gp = wm.stress_gps[sk_stress]
    
    viab_mean, _ = viab_gp.predict(dose_grid, return_std=True)
    stress_mean, _ = stress_gp.predict(dose_grid, return_std=False)
    
    viab_mean = np.asarray(viab_mean).reshape(-1)
    if isinstance(stress_mean, tuple):
        stress_mean = stress_mean[0]
    stress_mean = np.asarray(stress_mean).reshape(-1)
    
    # Compute scores and penalties
    cells_pred = 300.0 * viab_mean
    fields_pred = 200.0 * viab_mean
    
    print("Acquisition Score Landscape Diagnostic")
    print("=" * 100)
    print(f"Goal: Viability [{goal.viability_min}, {goal.viability_max}], "
          f"Min Cells/Field: {goal.min_cells_per_field}, Min Fields/Well: {goal.min_fields_per_well}")
    print("=" * 100)
    print(f"{'Dose (µM)':>10} | {'Viability':>10} | {'Stress':>8} | {'Cells/F':>8} | "
          f"{'V_Pen':>7} | {'QC_Pen':>7} | {'Score':>7} | Notes")
    print("-" * 100)
    
    scores = []
    for i in range(len(dose_grid)):
        # Compute penalties manually
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
        
        # Notes
        notes = []
        if viab_mean[i] < goal.viability_min:
            notes.append("LOW_VIAB")
        if cells_pred[i] < goal.min_cells_per_field:
            notes.append("LOW_CELLS")
        if viab_mean[i] >= goal.viability_min and viab_mean[i] <= goal.viability_max and cells_pred[i] >= goal.min_cells_per_field:
            notes.append("VALID")
        
        # Print every 5th row for readability
        if i % 5 == 0 or score == max(scores):
            marker = " <-- MAX" if score == max(scores) else ""
            print(f"{dose_grid[i]:10.4f} | {viab_mean[i]:10.3f} | {stress_mean[i]:8.3f} | "
                  f"{cells_pred[i]:8.1f} | {viab_pen:7.4f} | {qc_pen:7.4f} | "
                  f"{score:7.3f} | {','.join(notes)}{marker}")
    
    print("=" * 100)
    
    # Summary
    max_idx = np.argmax(scores)
    print(f"\nSummary:")
    print(f"  Max score: {max(scores):.3f} at {dose_grid[max_idx]:.4f} µM")
    print(f"  Viability at max: {viab_mean[max_idx]:.3f} (target: [{goal.viability_min}, {goal.viability_max}])")
    print(f"  Stress at max: {stress_mean[max_idx]:.3f}")
    print(f"  Cells/field at max: {cells_pred[max_idx]:.1f} (min: {goal.min_cells_per_field})")
    
    # Check if score landscape makes sense
    print(f"\nDiagnostics:")
    valid_scores = [s for i, s in enumerate(scores) if viab_mean[i] >= goal.viability_min and cells_pred[i] >= goal.min_cells_per_field]
    if valid_scores:
        print(f"  Score range in valid region: [{min(valid_scores):.3f}, {max(valid_scores):.3f}]")
    else:
        print(f"  WARNING: No doses satisfy hard constraints!")
    
    # Check if penalties dominate
    viab_penalties = [(goal.viability_min - v)**2 if v < goal.viability_min else 0.0 for v in viab_mean]
    max_viab_pen = max(viab_penalties)
    max_stress = max(stress_mean)
    if max_viab_pen > 2 * max_stress:
        print(f"  WARNING: Viability penalty ({max_viab_pen:.3f}) >> stress term ({max_stress:.3f})")
    
    print(f"\nInterpretation:")
    if viab_mean[max_idx] < goal.viability_min:
        deficit = goal.viability_min - viab_mean[max_idx]
        print(f"  Loop is accepting {deficit:.2f} viability deficit for stress gain of {stress_mean[max_idx]:.3f}")
    elif viab_mean[max_idx] >= goal.viability_min:
        print(f"  Loop is safely within viability band, maximizing stress")


if __name__ == "__main__":
    main()
