"""
cell_OS Experiment Loop
-----------------------

This script runs the autonomous experimental loop:

1. Select assay (cost aware)
2. Propose experiments via acquisition
3. Execute (simulation or real)
4. Update model and campaign state
5. Iterate until convergence or budget depletion
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary
from cell_os.modeling import DoseResponseGP
from cell_os.acquisition import AcquisitionFunction
from cell_os.legacy_simulation import SimulationEngine
from cell_os.assay_selector import AssaySelector
from cell_os.lab_world_model import LabWorldModel as WorldModel
from cell_os.campaign import Campaign, PotencyGoal, SelectivityGoal
from cell_os.schema import Phase0WorldModel, SliceKey


RESULTS_DIR = Path("results")
EXPERIMENT_LOG = RESULTS_DIR / "experiment_history.csv"


class ActiveLearner:
    """
    Manages the online learning process.
    Holds the current belief (Phase0WorldModel) and updates it with new data.
    """

    def __init__(self) -> None:
        self.history: List[Dict[str, Any]] = []
        self.posterior = Phase0WorldModel()

    def update(self, records: List[Dict[str, Any]]) -> None:
        """
        Update the model with new experimental records.
        """
        self.history.extend(records)
        self._rebuild_posterior()

    def _rebuild_posterior(self) -> None:
        """
        Re fit GPs based on all history.
        """
        if not self.history:
            return

        df = pd.DataFrame(self.history)

        # Ensure numeric types
        df["dose"] = pd.to_numeric(df["dose"], errors="coerce")
        df["viability"] = pd.to_numeric(df["viability"], errors="coerce")
        df["time_h"] = pd.to_numeric(df["time_h"], errors="coerce")

        gp_models: Dict[SliceKey, DoseResponseGP] = {}

        if "compound" not in df.columns or "cell_line" not in df.columns:
            return

        for (cell, cmpd, time_h), sub in df.groupby(["cell_line", "compound", "time_h"]):
            valid_sub = sub[sub["dose"] > 0].copy()
            if len(valid_sub) < 2:
                continue

            try:
                gp = DoseResponseGP.from_dataframe(
                    valid_sub,
                    cell_line=cell,
                    compound=cmpd,
                    time_h=float(time_h),
                    dose_col="dose",
                    viability_col="viability",
                )
                key = SliceKey(cell, cmpd, float(time_h))
                gp_models[key] = gp
            except Exception as e:
                print(f"[ActiveLearner] Failed to fit GP for {cell} {cmpd}: {e}")
                continue

        self.posterior = Phase0WorldModel(gp_models=gp_models)

    @property
    def gp_models(self) -> Dict[SliceKey, DoseResponseGP]:
        return self.posterior.gp_models

    def predict_on_grid(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Legacy stub kept for backwards compatibility.
        AcquisitionFunction no longer calls this on the learner.
        """
        return {}


def ensure_results_dirs() -> None:
    """Make sure results directories exist."""
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "logs").mkdir(exist_ok=True)
    (RESULTS_DIR / "figures").mkdir(exist_ok=True)
    (RESULTS_DIR / "model_snapshots").mkdir(exist_ok=True)


def append_experiments_to_csv(records: List[Dict[str, Any]]) -> None:
    """
    Append a batch of experimental records to results/experiment_history.csv.
    """
    if not records:
        return

    fieldnames = [
        "experiment_id",
        "campaign_id",
        "cell_line",
        "compound",
        "dose",
        "time_h",
        "replicate",
        "viability",
        "raw_signal",
        "noise_estimate",
        "cost_usd",
        "unit_ops_used",
        "automation_score",
        "timestamp",
        "source",
    ]

    file_exists = EXPERIMENT_LOG.exists()

    with EXPERIMENT_LOG.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for rec in records:
            # Filter to only known fields
            row = {k: rec.get(k) for k in fieldnames}
            writer.writerow(row)


def normalize_records(result: Any) -> List[Dict[str, Any]]:
    """
    Convert whatever SimulationEngine.run returns into a list of dict records.
    """
    if result is None:
        return []

    # Already a list of dicts
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result

    # Single dict
    if isinstance(result, dict):
        return [result]

    # List of objects with to_dict
    if isinstance(result, list) and result and hasattr(result[0], "to_dict"):
        return [r.to_dict() for r in result]  # type: ignore

    # Single object with to_dict
    if hasattr(result, "to_dict"):
        return [result.to_dict()]  # type: ignore

    # Last resort
    return [{"raw_result": result}]


def run_campaign(config: Dict[str, Any]) -> Any:
    """
    Top level loop.
    """
    ensure_results_dirs()

    # Core static resources
    inv = Inventory("data/raw/pricing.yaml")
    vessel_lib = VesselLibrary("data/raw/vessels.yaml")

    # World model (static knowledge)
    try:
        world = WorldModel.from_config(
            config,
            inventory=inv,
            vessel_library=vessel_lib,
        )
    except TypeError:
        world = WorldModel.from_config(config)

    # Campaign goal and budget
    goal_config = config.get("goal", {"type": "potency"})
    goal_type = goal_config.get("type", "potency")

    if goal_type == "selectivity":
        goal = SelectivityGoal(
            target_cell=goal_config.get("target_cell", "HepG2"),
            safe_cell=goal_config.get("safe_cell", "U2OS"),
            potency_threshold_uM=goal_config.get("potency_threshold", 1.0),
            safety_threshold_uM=goal_config.get("safety_threshold", 10.0),
        )
    else:
        goal = PotencyGoal(
            cell_line=goal_config.get("cell_line", "HepG2"),
            ic50_threshold_uM=goal_config.get("threshold", 1.0),
        )

    campaign = Campaign(goal=goal, max_cycles=config.get("max_steps", 20))
    campaign.budget = config.get("initial_budget", 1000.0)

    # Online learner and agents
    learner = ActiveLearner()
    selector = AssaySelector(world, campaign)

    if "reward" in config:
        acquisition = AcquisitionFunction(reward_config=config["reward"])
    else:
        acquisition = AcquisitionFunction()

    # Execution engine
    try:
        sim = SimulationEngine(
            world_model=world,
            inventory=inv,
            vessel_library=vessel_lib,
        )
    except TypeError:
        sim = SimulationEngine(world)

    max_steps = config.get("max_steps", 20)
    batch_size = config.get("batch_size", 8)

    for step in range(max_steps):
        if campaign.is_complete:
            print(f"[loop] Stopping at step {step}: campaign complete (Success={campaign.success})")
            break

        if campaign.budget <= 0:
            print(f"[loop] Stopping at step {step}: budget exhausted")
            break

        print(f"\n[loop] Step {step + 1} / {max_steps}")
        print(f"[loop] Budget remaining: ${campaign.budget:.2f}")

        # 1. Choose assay or region to explore
        assay = selector.choose_assay(learner.posterior)
        print(f"[loop] Selected assay: {assay.recipe.name}")

        # 2. Ask acquisition to propose the next batch
        # Always pass the *posterior* (world model), not the learner object itself
        proposal = acquisition.propose(
            model=learner.posterior,
            assay=assay,
            budget=campaign.budget,
            n_experiments=batch_size,
        )
        print(f"[loop] Proposed {len(proposal)} experiments")

        with pd.option_context("display.max_rows", 10, "display.max_columns", None):
            print(
                proposal[["cell_line", "compound", "dose_uM", "time_h", "priority_score"]]
                .head()
                .to_string(index=False)
            )

        # 3. Execute proposal via simulation
        result = sim.run(proposal)
        records = normalize_records(result)
        print(f"[loop] Executed {len(records)} experimental records")

        # 4. Update budget
        step_cost = sum(r.get("cost_usd", 0.0) for r in records)
        campaign.budget -= step_cost
        print(f"[loop] Step cost: ${step_cost:.2f} - New budget: ${campaign.budget:.2f}")

        # 5. Update learner with new data
        learner.update(records)

        # 6. Update campaign status
        campaign.check_goal(learner.posterior)

        # 7. Persist to CSV
        append_experiments_to_csv(records)

    return learner.history


if __name__ == "__main__":
    example_config: Dict[str, Any] = {
        "initial_budget": 500,
        "max_steps": 20,
        "cell_lines": ["U2OS", "HepG2"],
        "compounds": ["staurosporine", "tunicamycin"],
        "dose_grid": [1e-3, 1e-2, 1e-1, 1.0, 10.0],
        "goal": {
            "type": "potency",
            "cell_line": "HepG2",
            "threshold": 0.5,
        },
        "reward": {
            # Cost model
            "cost_per_well_usd": 2.5,
            # GP dose grid for acquisition
            "dose_grid_size": 50,
            "dose_min": 0.001,
            "dose_max": 10.0,
            # Repeat penalty controls
            "repeat_penalty": 0.02,
            "repeat_tol_fraction": 0.05,
        },
        "batch_size": 8,
    }

    history = run_campaign(example_config)
    print(f"Campaign finished with {len(history)} records.")
