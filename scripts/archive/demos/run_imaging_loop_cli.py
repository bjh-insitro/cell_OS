#!/usr/bin/env python
"""Simple text-based dashboard for imaging loop state.

Visualizes GP predictions, score landscape, and proposed doses.
"""

import numpy as np

from cell_os.posteriors import SliceKey
from cell_os.imaging_goal import ImagingWindowGoal
from cell_os.imaging_world_model import ImagingWorldModel
from cell_os.imaging_loop import ImagingDoseLoop
from cell_os.simulated_executor import SimulatedImagingExecutor
from cell_os.acquisition_config import AcquisitionConfig
from cell_os.modeling import DoseResponseGP
from cell_os.imaging_cost import calculate_imaging_cost


def plot_ascii_curve(x, y, width=60, height=15, title=""):
    """Create ASCII plot of a curve."""
    if len(x) == 0:
        return ""
    
    # Normalize to plot dimensions
    x_min, x_max = min(x), max(x)
    y_min, y_max = min(y), max(y)
    
    if x_max == x_min or y_max == y_min:
        return f"{title}\n(Flat curve - no variation)"
    
    # Create grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Plot curve
    for i in range(len(x)):
        x_norm = int((x[i] - x_min) / (x_max - x_min) * (width - 1))
        y_norm = int((y[i] - y_min) / (y_max - y_min) * (height - 1))
        y_norm = height - 1 - y_norm  # Flip y-axis
        if 0 <= x_norm < width and 0 <= y_norm < height:
            grid[y_norm][x_norm] = '●'
    
    # Convert to string
    lines = [title] if title else []
    lines.append('┌' + '─' * width + '┐')
    for row in grid:
        lines.append('│' + ''.join(row) + '│')
    lines.append('└' + '─' * width + '┘')
    lines.append(f"  {x_min:.2e}" + " " * (width - 20) + f"{x_max:.2e}")
    
    return '\n'.join(lines)


def main():
    print("\n" + "=" * 80)
    print(" " * 25 + "IMAGING LOOP DASHBOARD")
    print("=" * 80 + "\n")
    
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
    
    config = AcquisitionConfig.posh_optimizer()
    executor = SimulatedImagingExecutor(goal=goal)
    loop = ImagingDoseLoop(world_model=wm, executor=executor, goal=goal)
    
    # Seed
    from cell_os.imaging_acquisition import ExperimentPlan
    seed_plans = [ExperimentPlan(sk_stress, d, 0.0) for d in [0.01, 0.1, 1.0, 10.0]]
    wm.update_with_results(executor.run_batch(seed_plans))
    
    # Evaluate landscape
    dose_grid = np.logspace(-3, 2, 100)
    viab_gp = wm.viability_gps[sk_viab]
    stress_gp = wm.stress_gps[sk_stress]
    
    viab_mean, viab_std = viab_gp.predict(dose_grid, return_std=True)
    stress_mean, _ = stress_gp.predict(dose_grid, return_std=False)
    
    viab_mean = np.asarray(viab_mean).reshape(-1)
    viab_std = np.asarray(viab_std).reshape(-1)
    if isinstance(stress_mean, tuple):
        stress_mean = stress_mean[0]
    stress_mean = np.asarray(stress_mean).reshape(-1)
    
    # Get proposal
    batch = loop.propose(dose_grid=dose_grid)
    top_plan = batch.plans[0] if batch.plans else None
    
    # Display
    print("📊 MODEL STATE")
    print("-" * 80)
    print(f"History size: {len(wm.history)} experiments")
    print(f"Acquisition config: {config.personality}")
    print(f"Goal: Viability [{goal.viability_min}, {goal.viability_max}], "
          f"Min cells/field: {goal.min_cells_per_field}")
    print()
    
    if top_plan:
        print("🎯 TOP PROPOSAL")
        print("-" * 80)
        print(f"Dose:              {top_plan.dose_uM:.4f} µM")
        print(f"Predicted viability: {top_plan.viability_value:.3f}")
        print(f"Predicted stress:    {top_plan.stress_value:.3f}")
        print(f"Cells/field:         {top_plan.cells_per_field_pred:.1f}")
        print(f"Acquisition score:   {top_plan.score:.3f}")
        
        # Cost
        cost = calculate_imaging_cost(top_plan, wells_per_dose=3)
        print(f"\nEstimated cost:      ${cost.total_cost_usd:.2f}")
        print(f"  Reagents:          ${cost.reagent_cost_usd:.2f}")
        print(f"  Consumables:       ${cost.consumable_cost_usd:.2f}")
        print(f"  Instrument:        ${cost.instrument_cost_usd:.2f}")
        print()
    
    print("📈 DOSE-RESPONSE CURVES")
    print("-" * 80)
    
    # Plot viability
    print(plot_ascii_curve(
        np.log10(dose_grid), viab_mean,
        title="Viability vs log10(Dose)"
    ))
    print()
    
    # Plot stress
    print(plot_ascii_curve(
        np.log10(dose_grid), stress_mean,
        title="Stress vs log10(Dose)"
    ))
    print()
    
    # Summary stats
    print("📋 LANDSCAPE SUMMARY")
    print("-" * 80)
    print(f"Viability range:     [{viab_mean.min():.3f}, {viab_mean.max():.3f}]")
    print(f"Stress range:        [{stress_mean.min():.3f}, {stress_mean.max():.3f}]")
    print(f"Uncertainty (avg):   {viab_std.mean():.3f}")
    
    viable_doses = dose_grid[(viab_mean >= goal.viability_min) & (viab_mean <= goal.viability_max)]
    print(f"Viable dose range:   [{viable_doses.min():.4f}, {viable_doses.max():.4f}] µM" 
          if len(viable_doses) > 0 else "Viable dose range:   None")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
