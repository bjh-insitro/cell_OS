"""
cell_OS Experiment Loop
-----------------------

This script runs the autonomous experimental loop:

1. Select assay (cost aware)
2. Propose experiments via acquisition
3. Execute (simulation or real)
4. Update model and campaign state
5. Iterate until convergence or budget depletion

See:
- docs/architecture/DATA_MODEL.md
- docs/guides/REWARD_FUNCTIONS.md
- docs/architecture/SYSTEM_GLUE.md
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from src.inventory import Inventory
from src.unit_ops import VesselLibrary
from src.modeling import DoseResponseGP
from src.acquisition import AcquisitionFunction
from src.simulation import SimulationEngine
from src.assay_selector import AssaySelector
from src.core.world_model import WorldModel
from src.campaign import Campaign


RESULTS_DIR = Path("results")
EXPERIMENT_LOG = RESULTS_DIR / "experiment_history.csv"


def ensure_results_dirs() -> None:
    """Make sure results directories exist."""
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "logs").mkdir(exist_ok=True)
    (RESULTS_DIR / "figures").mkdir(exist_ok=True)
    (RESULTS_DIR / "model_snapshots").mkdir(exist_ok=True)


def append_experiments_to_csv(records: List[Dict[str, Any]]) -> None:
    """
    Append a batch of experimental records to results/experiment_history.csv.

    This assumes each record is a flat dict whose keys match DATA_MODEL.md.
    Adapt the field list if your schema differs.
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
            row = {k: rec.get(k) for k in fieldnames}
            writer.writerow(row)


def normalize_records(result: Any) -> List[Dict[str, Any]]:
    """
    Convert whatever SimulationEngine.run returns into a list of dict records.

    This is intentionally forgiving.

    Expected common cases:
    - result is already a list of dicts
    - result is a single dict
    - result is a list of objects with .to_dict()
    - result is a single object with .to_dict()
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

    # As a last resort, wrap as a single opaque record
    return [{"raw_result": result}]


def run_campaign(config: Dict[str, Any]) -> Any:
    """
    Top level loop.

    Expected config keys (adjust to match your real config):
      - initial_budget: float
      - max_steps: int
      - cell_lines: list[str]
      - compounds: list[str]
      - dose_grid: list[float]
      - reward: dict (see REWARD_FUNCTIONS.md)
    """
    ensure_results_dirs()

    # Core static resources
    inv = Inventory("data/raw/pricing.yaml")
    vessel_lib = VesselLibrary("data/raw/vessels.yaml")

    # World model knows about cells, vessels, assays, constraints
    # Keep signature matching your current implementation
    # We attempt to pass inventory/vessel_lib if the constructor supports it,
    # otherwise we assume it handles it internally or we update it later.
    try:
        world = WorldModel.from_config(
            config,
            inventory=inv,
            vessel_library=vessel_lib
        )
    except TypeError:
        # Fallback if signature doesn't match yet
        world = WorldModel.from_config(config)

    # Campaign tracks budget and history
    # Your current code uses Campaign(config), so keep that
    campaign = Campaign(config)

    # Modeling: start from an empty GP
    model = DoseResponseGP.empty()

    # Assay selection: which region to explore
    selector = AssaySelector(world, campaign)

    # Acquisition: how to score candidate experiments
    acquisition = AcquisitionFunction(
        reward_config=config.get("reward", {})
    ) if "reward" in config else AcquisitionFunction()

    # Execution engine: simulation for now
    # We attempt to pass world, inventory, vessel_lib if supported
    try:
        sim = SimulationEngine(
            world_model=world,
            inventory=inv,
            vessel_library=vessel_lib
        )
    except TypeError:
        # Fallback to just world if signature differs
        sim = SimulationEngine(world)

    max_steps = config.get("max_steps", 20)

    for step in range(max_steps):
        if hasattr(campaign, "exhausted") and campaign.exhausted():
            print(f"[loop] Stopping at step {step}: campaign exhausted")
            break

        budget_val = getattr(campaign, "budget", None)
        if budget_val is not None:
            print(f"\n[loop] Step {step + 1} / {max_steps}")
            print(f"[loop] Budget remaining: ${budget_val:.2f}")
        else:
            print(f"\n[loop] Step {step + 1} / {max_steps}")

        # 1. Choose assay / region to explore
        assay = selector.choose_assay(model)
        print(f"[loop] Selected assay: {assay}")

        # 2. Ask acquisition to propose the next experiment or batch
        # If your AcquisitionFunction supports batches, you can switch to propose_batch
        proposal = acquisition.propose(model, assay, getattr(campaign, "budget", None))
        print(f"[loop] Proposed experiment: {proposal}")

        # 3. Execute proposal via simulation (or real lab later)
        result = sim.run(proposal)
        records = normalize_records(result)
        print(f"[loop] Executed {len(records)} experimental records")

        # 4. Update modeling with new data
        model.update(records)

        # 5. Update campaign: budget, history, stopping conditions
        campaign.update(records)

        # 6. Persist experimental records to CSV
        append_experiments_to_csv(records)

    # Preserve your existing return type
    return getattr(campaign, "history", campaign)


if __name__ == "__main__":
    # TODO: replace with a real YAML config loader
    example_config: Dict[str, Any] = {
        "initial_budget": 500,
        "max_steps": 20,
        "cell_lines": ["U2OS", "HepG2"],
        "compounds": ["staurosporine", "tunicamycin"],
        "dose_grid": [1e-3, 1e-2, 1e-1, 1.0, 10.0],
        # Optional reward configuration
        # "reward": {
        #     "objective": "viability",
        #     "mode": "balanced",
        #     "w_epi": 0.5,
        #     "w_geo": 0.5,
        #     "lambda_cost": 0.01,
        #     "automation_alpha": 0.6,
        # },
    }

    history = run_campaign(example_config)
    print(history)
