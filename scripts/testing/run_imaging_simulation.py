"""
A reusable simulation runner for the Imaging Dose Loop.

This module encapsulates the core autonomous agent logic to run a fixed number
of simulation cycles and returns the experiment history as a pandas DataFrame.
All configuration is externalized to the SIM_CONFIG dictionary.
"""
import numpy as np
import pandas as pd
import sys
import os

# Add src to path so we can import cell_os modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Assuming these are accessible via the project PYTHONPATH
from cell_os.posteriors import SliceKey
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.archive.imaging_world_model import ImagingWorldModel
from cell_os.imaging.loop import ImagingDoseLoop
from cell_os.simulated_executor import SimulatedImagingExecutor
from cell_os.modeling import DoseResponseGP


# --- CONFIGURATION (Ideally loaded from a config/ file) ---
# NOTE: In a real refactor, this dict would be loaded from a YAML file (e.g., config/imaging_sim.yaml)
SIM_CONFIG = {
    "slice_key": {
        "cell_line": "U2OS",
        "compound": "TBHP",
        "time_hr": 24.0,
        "viability_metric": "viability_fraction",
        "stress_metric": "cellrox_mean",
    },
    "goal": {
        "viability_min": 0.8,
        "viability_max": 1.0,
        "min_cells_per_field": 280,
        "min_fields_per_well": 100,
    },
    "simulation": {
        "cycles": 5,
        "seed_doses_uM": [0.01, 0.1, 1.0, 10.0],
        "dose_grid_uM": np.logspace(-3, 2, 100),
    }
}


def run_simulation(config: dict = SIM_CONFIG) -> pd.DataFrame:
    """
    Runs the full Imaging Dose Loop simulation based on the provided configuration.

    Args:
        config: A dictionary containing all simulation parameters.

    Returns:
        A pandas DataFrame containing the history of all proposals and scores.
    """
    # 1. Setup Slice Keys and Goals
    sk_conf = config["slice_key"]
    sk_viab = SliceKey(sk_conf["cell_line"], sk_conf["compound"], sk_conf["time_hr"], sk_conf["viability_metric"])
    sk_stress = SliceKey(sk_conf["cell_line"], sk_conf["compound"], sk_conf["time_hr"], sk_conf["stress_metric"])

    goal_conf = config["goal"]
    goal = ImagingWindowGoal(
        viability_metric=sk_conf["viability_metric"],
        stress_metric=sk_conf["stress_metric"],
        **goal_conf,
    )

    # 2. Initialize World Model, Executor, and Loop
    viability_gps = {sk_viab: DoseResponseGP.empty()}
    stress_gps = {sk_stress: DoseResponseGP.empty()}

    wm = ImagingWorldModel.from_dicts(
        viability_gps=viability_gps,
        stress_gps=stress_gps,
    )
    executor = SimulatedImagingExecutor(goal=goal)
    loop = ImagingDoseLoop(world_model=wm, executor=executor, goal=goal)

    # 3. Seed the model with initial data
    print("Seeding model...")
    # 3. Seed the model with initial data
    print("Seeding model...")
    from cell_os.imaging.acquisition import ExperimentPlan
    seed_doses = config["simulation"]["seed_doses_uM"]
    seed_plans = [
        ExperimentPlan(slice_key=sk_stress, dose_uM=d, stress_value=0.0)
        for d in seed_doses
    ]
    seed_results = executor.run_batch(seed_plans)
    wm.update_with_results(seed_results)
    print(f"Seeded with {len(seed_results)} experiments")

    # 4. Run Cycles and Capture History
    all_history = []
    dose_grid = config["simulation"]["dose_grid_uM"]
    cycles = config["simulation"]["cycles"]

    for cycle in range(1, cycles + 1):
        batch = loop.run_one_cycle(dose_grid=dose_grid)

        if batch.plans:
            top_plan = batch.plans[0]
            # Capture the full state into a structured dictionary
            history_entry = {
                "cycle": cycle,
                "dose_uM": top_plan.dose_uM,
                "viability_value": top_plan.viability_value,
                "stress_value": top_plan.stress_value,
                "cells_per_field_pred": top_plan.cells_per_field_pred,
                "good_fields_per_well_pred": top_plan.good_fields_per_well_pred,
                "score": top_plan.score,
                # Add a marker to show if the proposal was executed (for real-world data)
                "is_simulated": True,
            }
            all_history.append(history_entry)
        else:
             # Log that no valid proposal was found
             all_history.append({"cycle": cycle, "score": np.nan, "dose_uM": np.nan})

    print(f"\nTotal experiments in history: {len(wm.history)}")
    return pd.DataFrame(all_history)


if __name__ == "__main__":
    # Provides clean console output when run standalone
    history_df = run_simulation()
    
    # Print the resulting DataFrame using a clean string representation
    print("\n--- SIMULATION HISTORY REPORT ---")
    print(history_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}" if x > 1e-3 or x == 0 else f"{x:.2e}"
    ))