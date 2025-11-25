# scripts/imaging_loop_report.py
"""Five-cycle imaging loop report to verify scoring behavior."""

import numpy as np
import pandas as pd

from cell_os.posteriors import SliceKey
from cell_os.imaging_goal import ImagingWindowGoal
from cell_os.imaging_world_model import ImagingWorldModel
from cell_os.imaging_loop import ImagingDoseLoop
from cell_os.simulated_executor import SimulatedImagingExecutor
from cell_os.modeling import DoseResponseGP


def main():
    # Slice keys
    sk_viab = SliceKey("U2OS", "TBHP", 24.0, "viability_fraction")
    sk_stress = SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean")

    # Initialize with empty GPs
    viability_gps = {sk_viab: DoseResponseGP.empty()}
    stress_gps = {sk_stress: DoseResponseGP.empty()}

    wm = ImagingWorldModel.from_dicts(
        viability_gps=viability_gps,
        stress_gps=stress_gps,
    )

    goal = ImagingWindowGoal(
        viability_metric="viability_fraction",
        stress_metric="cellrox_mean",
        viability_min=0.8,
        viability_max=1.0,
        min_cells_per_field=280,
        min_fields_per_well=100,
    )

    executor = SimulatedImagingExecutor(goal=goal)
    loop = ImagingDoseLoop(world_model=wm, executor=executor, goal=goal)

    # Seed with a few doses
    print("Seeding model...")
    from cell_os.imaging_acquisition import ExperimentPlan
    seed_doses = [0.01, 0.1, 1.0, 10.0]
    seed_plans = [
        ExperimentPlan(
            slice_key=sk_stress,
            dose_uM=d,
            stress_value=0.0,
        )
        for d in seed_doses
    ]
    seed_results = executor.run_batch(seed_plans)
    wm.update_with_results(seed_results)
    print(f"Seeded with {len(seed_results)} experiments\n")

    # Run 5 cycles
    dose_grid = np.logspace(-3, 2, 100)
    
    print("Cycle | Dose (µM) | Viability | Stress | Cells/Field | Fields/Well | Score")
    print("-" * 85)
    
    for cycle in range(1, 6):
        batch = loop.run_one_cycle(dose_grid=dose_grid)
        
        if batch.plans:
            top = batch.plans[0]
            print(f"{cycle:5d} | {top.dose_uM:9.4f} | {top.viability_value:9.3f} | "
                  f"{top.stress_value:6.3f} | {top.cells_per_field_pred:11.1f} | "
                  f"{top.good_fields_per_well_pred:11.1f} | {top.score:6.3f}")
        else:
            print(f"{cycle:5d} | No valid proposals")
    
    print(f"\nTotal experiments in history: {len(wm.history)}")


if __name__ == "__main__":
    main()
