# scripts/imaging_loop_smoketest.py

import numpy as np

from cell_os.posteriors import SliceKey
from cell_os.imaging_goal import ImagingWindowGoal
from cell_os.imaging_world_model import ImagingWorldModel
from cell_os.imaging_loop import ImagingDoseLoop
from cell_os.simulated_executor import SimulatedImagingExecutor


class RealisticGP:
    """GP-like object that returns sigmoid curves matching the SimulatedExecutor."""

    def __init__(self, ld50_uM: float, slope: float, scale: float = 1.0):
        self.ld50_log = np.log10(ld50_uM)
        self.slope = slope
        self.scale = scale

    def predict(self, X, return_std=True):
        X = np.asarray(X, dtype=float)
        # Handle (N, 1) or (N,)
        doses = X.flatten()
        log_dose = np.log10(doses + 1e-9)

        # Sigmoid logic matching SimulatedExecutor
        # slope > 0 -> Decreasing (Viability)
        # slope < 0 -> Increasing (Stress)
        logits = self.slope * (log_dose - self.ld50_log)
        mean = 1.0 / (1.0 + np.exp(logits))
        
        # Apply scaling (e.g. for cell counts)
        mean = mean * self.scale

        # Scikit-learn GPs return flat mean.
        if return_std:
            std = np.full_like(mean, 0.05 * self.scale)
            return mean, std
        return mean


from cell_os.modeling import DoseResponseGP
from cell_os.imaging_acquisition import ExperimentPlan

def main():
    # Slice keys for a single (cell_line, compound, time_h) pair
    sk_viab = SliceKey("U2OS", "TBHP", 24.0, "viability_fraction")
    sk_stress = SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean")
    sk_cells = SliceKey("U2OS", "TBHP", 24.0, "cells_per_field")
    sk_fields = SliceKey("U2OS", "TBHP", 24.0, "good_fields_per_well")

    # Initialize with empty GPs
    viability_gps = {sk_viab: DoseResponseGP.empty()}
    stress_gps = {sk_stress: DoseResponseGP.empty()}
    qc_gps = {
        sk_cells: DoseResponseGP.empty(),
        sk_fields: DoseResponseGP.empty(),
    }

    wm = ImagingWorldModel.from_dicts(
        viability_gps=viability_gps,
        stress_gps=stress_gps,
        qc_gps=qc_gps,
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

    loop = ImagingDoseLoop(
        world_model=wm,
        executor=executor,
        goal=goal,
    )

    # 1. Seed the model with a few manual experiments
    print("Seeding model with manual experiments...")
    seed_doses = [0.01, 0.1, 1.0, 10.0]
    seed_plans = [
        ExperimentPlan(
            slice_key=sk_stress, # SliceKey doesn't matter much for executor, it uses dose
            dose_uM=d,
            stress_value=0.0 # Dummy value
        )
        for d in seed_doses
    ]
    
    seed_results = executor.run_batch(seed_plans)
    print("Seed results:")
    print(seed_results[["dose_uM", "viability_fraction", "cellrox_mean", "cells_per_field"]])
    
    wm.update_with_results(seed_results)
    print("Model refitted.")

    # 2. Run one cycle of the loop
    dose_grid = np.logspace(-3, 2, 50)
    batch = loop.run_one_cycle(dose_grid=dose_grid)

    print("\nTop proposed doses (Cycle 1):")
    for p in batch.plans[:5]:
        print(f"  dose = {p.dose_uM:.4f} uM, stress_pred = {p.stress_value:.3f}")

    print("\nHistory head:")
    print(wm.history.head())
    print("\nHistory rows:", len(wm.history))


if __name__ == "__main__":
    main()
