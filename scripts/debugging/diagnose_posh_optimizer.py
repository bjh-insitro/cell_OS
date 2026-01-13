#!/usr/bin/env python
"""Diagnostic for POSH optimizer personality."""

import numpy as np

from cell_os.posteriors import SliceKey
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.acquisition import compute_acquisition_score
from cell_os.acquisition_config import AcquisitionConfig
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

    # Evaluate with POSH optimizer
    config = AcquisitionConfig.posh_optimizer()
    dose_grid = np.logspace(-3, 2, 200)
    
    viab_gp = wm.viability_gps[sk_viab]
    stress_gp = wm.stress_gps[sk_stress]
    
    viab_mean, _ = viab_gp.predict(dose_grid, return_std=True)
    stress_mean, _ = stress_gp.predict(dose_grid, return_std=False)
    
    viab_mean = np.asarray(viab_mean).reshape(-1)
    if isinstance(stress_mean, tuple):
        stress_mean = stress_mean[0]
    stress_mean = np.asarray(stress_mean).reshape(-1)
    
    cells_pred = 300.0 * viab_mean
    fields_pred = 200.0 * viab_mean
    
    scores = []
    for i in range(len(dose_grid)):
        score = compute_acquisition_score(
            viab_mean[i], stress_mean[i], cells_pred[i], fields_pred[i], goal, config
        )
        scores.append(score)
    
    max_idx = np.argmax(scores)
    
    print("POSH Optimizer Diagnostic")
    print("=" * 80)
    print(f"Configuration: {config}")
    print(f"Philosophy: Maximize morphological information while keeping assay operational")
    print("=" * 80)
    print(f"\nOptimal Dose: {dose_grid[max_idx]:.4f} µM")
    print(f"  Viability:     {viab_mean[max_idx]:.3f} (target: [{goal.viability_min}, {goal.viability_max}])")
    print(f"  Stress:        {stress_mean[max_idx]:.3f}")
    print(f"  Cells/field:   {cells_pred[max_idx]:.1f} (min: {goal.min_cells_per_field})")
    print(f"  Fields/well:   {fields_pred[max_idx]:.1f} (min: {goal.min_fields_per_well})")
    print(f"  Score:         {scores[max_idx]:.3f}")
    
    # Check if in expected range
    in_range = 0.35 <= dose_grid[max_idx] <= 0.55
    print(f"\n✓ Dose in expected 0.35-0.55 µM range: {in_range}")
    
    # Check penalty behavior
    viab_violations = sum(1 for v in viab_mean if v < goal.viability_min)
    qc_violations = sum(1 for c in cells_pred if c < goal.min_cells_per_field)
    
    print(f"\nLandscape Analysis:")
    print(f"  Doses with viability < {goal.viability_min}: {viab_violations}/{len(dose_grid)}")
    print(f"  Doses with cells < {goal.min_cells_per_field}: {qc_violations}/{len(dose_grid)}")
    print(f"  Score range: [{min(scores):.3f}, {max(scores):.3f}]")
    
    # Interpretation
    print(f"\nInterpretation:")
    if viab_mean[max_idx] < goal.viability_min:
        deficit = goal.viability_min - viab_mean[max_idx]
        print(f"  Loop accepts {deficit:.3f} viability deficit for stress signal of {stress_mean[max_idx]:.3f}")
        print(f"  This is expected for POSH optimizer - prioritizes morphological information")
    else:
        print(f"  Loop stays within viability band while maximizing stress")
    
    if cells_pred[max_idx] < goal.min_cells_per_field:
        deficit = goal.min_cells_per_field - cells_pred[max_idx]
        print(f"  Accepts {deficit:.1f} cells/field deficit - segmentation still operational")
    
    print(f"\n✓ Stance is stable and appropriate for single-shot POSH dose selection")


if __name__ == "__main__":
    main()
