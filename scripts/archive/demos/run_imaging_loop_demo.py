# scripts/run_imaging_loop_demo.py
from __future__ import annotations

import numpy as np
import pandas as pd

from cell_os.posteriors import SliceKey, DoseResponseGP
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.loop import ImagingDoseLoop
from cell_os.simulated_executor import SimulatedImagingExecutor

# ----------------------------------------------------------------------
# 1. Make fake GP models (just linear mocks for now)
# ----------------------------------------------------------------------

class FakeGP(DoseResponseGP):
    """Minimal mock: returns a sigmoid-ish curve for testing."""

    def __init__(self, offset=0.0):
        self.offset = offset

    def predict(self, doses, return_std=True):
        doses = np.asarray(doses)
        x = np.log10(doses + 1e-9)
        mean = 1.0 / (1.0 + np.exp(3.0 * (x - self.offset)))
        if return_std:
            return mean, np.full_like(mean, 0.05)
        return mean


# ----------------------------------------------------------------------
# 2. Build the GP dictionaries
# ----------------------------------------------------------------------

sk_viab = SliceKey(
    cell_line="U2OS",
    compound="TBHP",
    time_h=24.0,
    readout="viability_fraction",
)

sk_stress = SliceKey(
    cell_line="U2OS",
    compound="TBHP",
    time_h=24.0,
    readout="cellrox_mean",
)

viability_gps = {sk_viab: FakeGP(offset=0.0)}
stress_gps = {sk_stress: FakeGP(offset=-0.5)}

# ----------------------------------------------------------------------
# 3. Create the world model
# ----------------------------------------------------------------------

wm = ImagingWorldModel.from_dicts(viability_gps, stress_gps)

# ----------------------------------------------------------------------
# 4. Goal + Executor + Loop
# ----------------------------------------------------------------------

goal = ImagingWindowGoal(
    viability_metric="viability_fraction",
    stress_metric="cellrox_mean",
    viability_min=0.8,
    viability_max=1.0,
)

executor = SimulatedImagingExecutor(goal=goal)

loop = ImagingDoseLoop(
    world_model=wm,
    executor=executor,
    goal=goal
)

# ----------------------------------------------------------------------
# 5. Run one cycle
# ----------------------------------------------------------------------

batch = loop.run_one_cycle()

print("\n=== Proposed Experiments ===")
for p in batch.plans[:10]:
    print(f"dose={p.dose_uM:.4f} µM   stress={p.stress_value:.3f}")

print("\n=== Executor Output ===")
df = executor.run_batch(batch.plans)
print(df.head())

print("\n=== World Model History Rows ===", len(wm.history))
