#!/usr/bin/env python
"""Compare acquisition behavior across three personalities."""

import numpy as np

from cell_os.posteriors import SliceKey
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.acquisition import compute_acquisition_score
from cell_os.acquisition_config import AcquisitionConfig
from cell_os.modeling import DoseResponseGP
from cell_os.simulated_executor import SimulatedImagingExecutor


def evaluate_personality(config: AcquisitionConfig, wm, goal, dose_grid):
    """Evaluate score landscape for a given personality."""
    sk_viab = SliceKey("U2OS", "TBHP", 24.0, "viability_fraction")
    sk_stress = SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean")
    
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
    return {
        'dose': dose_grid[max_idx],
        'viability': viab_mean[max_idx],
        'stress': stress_mean[max_idx],
        'cells': cells_pred[max_idx],
        'score': scores[max_idx],
    }


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

    dose_grid = np.logspace(-3, 2, 200)
    
    # Compare personalities
    personalities = [
        AcquisitionConfig.ambitious_postdoc(),
        AcquisitionConfig.balanced(),
        AcquisitionConfig.cautious_operator(),
    ]
    
    print("Personality Comparison: How Different Stances Choose Doses")
    print("=" * 90)
    print(f"Goal: Viability [{goal.viability_min}, {goal.viability_max}], "
          f"Min Cells: {goal.min_cells_per_field}")
    print("=" * 90)
    print(f"{'Personality':<20} | {'Dose (µM)':>10} | {'Viability':>10} | "
          f"{'Stress':>8} | {'Cells/F':>8} | {'Score':>7}")
    print("-" * 90)
    
    for config in personalities:
        result = evaluate_personality(config, wm, goal, dose_grid)
        
        # Mark violations
        viab_ok = "✓" if result['viability'] >= goal.viability_min else "✗"
        cells_ok = "✓" if result['cells'] >= goal.min_cells_per_field else "✗"
        
        print(f"{config.personality:<20} | {result['dose']:10.4f} | "
              f"{result['viability']:10.3f} {viab_ok} | {result['stress']:8.3f} | "
              f"{result['cells']:8.1f} {cells_ok} | {result['score']:7.3f}")
    
    print("=" * 90)
    print("\nInterpretation:")
    print("  Ambitious Postdoc: Pushes into stress-rich region, accepts violations")
    print("  Balanced: Moderate tradeoffs (current default)")
    print("  Cautious Operator: Stays safe, prioritizes QC over stress signal")
    print("\nUse AcquisitionConfig.ambitious_postdoc() for POSH stress calibration")
    print("Use AcquisitionConfig.cautious_operator() for production screens")


if __name__ == "__main__":
    main()
