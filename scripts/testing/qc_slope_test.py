
import numpy as np
from cell_os.posteriors import SliceKey
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.loop import ImagingDoseLoop
from cell_os.simulation.simulated_executor import SimulatedImagingExecutor

class RealisticGP:
    """GP-like object that returns sigmoid curves matching the SimulatedExecutor."""

    def __init__(self, ld50_uM: float, slope: float, scale: float = 1.0):
        self.ld50_log = np.log10(ld50_uM)
        self.slope = slope
        self.scale = scale

    def predict(self, X, return_std=True):
        X = np.asarray(X, dtype=float)
        doses = X.flatten()
        log_dose = np.log10(doses + 1e-9)
        logits = self.slope * (log_dose - self.ld50_log)
        mean = 1.0 / (1.0 + np.exp(logits))
        mean = mean * self.scale
        if return_std:
            std = np.full_like(mean, 0.05 * self.scale)
            return mean, std
        return mean

def main():
    sk_viab = SliceKey("U2OS", "TBHP", 24.0, "viability_fraction")
    sk_stress = SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean")
    sk_cells = SliceKey("U2OS", "TBHP", 24.0, "cells_per_field")
    sk_fields = SliceKey("U2OS", "TBHP", 24.0, "good_fields_per_well")

    viability_gps = {sk_viab: RealisticGP(ld50_uM=1.0, slope=4.0)}
    stress_gps = {sk_stress: RealisticGP(ld50_uM=0.316, slope=-3.0)}
    qc_gps = {
        sk_cells: RealisticGP(ld50_uM=1.0, slope=4.0, scale=300.0),
        sk_fields: RealisticGP(ld50_uM=1.0, slope=4.0, scale=200.0),
    }

    wm = ImagingWorldModel.from_dicts(
        viability_gps=viability_gps,
        stress_gps=stress_gps,
        qc_gps=qc_gps,
    )

    thresholds = [240, 260, 280]
    print("QC Slope Test Results:")
    print(f"{'Min Cells':<10} | {'Top Dose (uM)':<15} | {'Stress':<10}")
    print("-" * 40)

    for min_cells in thresholds:
        goal = ImagingWindowGoal(
            viability_metric="viability_fraction",
            stress_metric="cellrox_mean",
            viability_min=0.8,
            viability_max=1.0,
            min_cells_per_field=min_cells,
            min_fields_per_well=100,
        )
        # Executor doesn't matter for proposal, only for execution
        executor = SimulatedImagingExecutor(goal=goal)
        loop = ImagingDoseLoop(world_model=wm, executor=executor, goal=goal)
        
        # Use fine grid for better resolution
        dose_grid = np.logspace(-3, 2, 500)
        batch = loop.propose(dose_grid=dose_grid)
        
        if batch.plans:
            top_plan = batch.plans[0]
            print(f"{min_cells:<10} | {top_plan.dose_uM:<15.4f} | {top_plan.stress_value:<10.3f}")
        else:
            print(f"{min_cells:<10} | {'None':<15} | {'N/A':<10}")

if __name__ == "__main__":
    main()
