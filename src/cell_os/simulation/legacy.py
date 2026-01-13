"""
Legacy simulation utilities used by older CLI workflows and tests.

The new WorkflowExecutor stack now covers most simulation needs, but several
scripts/tests still depend on the original SimulationEngine + helper functions.
This module provides a lightweight reimplementation so those consumers keep
working while the newer infrastructure matures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Hard-coded logistic model parameters for a few common cell line / compound pairs.
_GROUND_TRUTH: Dict[Tuple[str, str], Dict[str, float]] = {
    ("HepG2", "staurosporine"): {"ic50": 0.05, "hill": 1.1},
    ("HepG2", "tunicamycin"): {"ic50": 0.8, "hill": 1.0},
    ("U2OS", "staurosporine"): {"ic50": 0.15, "hill": 1.0},
    ("U2OS", "tunicamycin"): {"ic50": 1.5, "hill": 0.9},
    ("HEK293T", "staurosporine"): {"ic50": 0.12, "hill": 1.05},
}


def _get_ground_truth(cell_line: str, compound: str) -> Dict[str, float]:
    """Fallback parameters if a pair is missing."""
    return _GROUND_TRUTH.get(
        (cell_line, compound),
        {"ic50": 1.0, "hill": 1.0},
    )


def _simulate_viability(
    cell_line: str,
    compound: str,
    dose_uM: float,
    rng: np.random.Generator,
) -> float:
    """Simple 4-parameter logistic model with Gaussian noise."""
    params = _get_ground_truth(cell_line, compound)
    ic50 = max(params["ic50"], 1e-6)
    hill = params["hill"]
    min_viability = 0.05
    max_viability = 1.05
    response = min_viability + (max_viability - min_viability) / (
        1.0 + (dose_uM / ic50) ** hill
    )
    noisy = response + rng.normal(0, 0.05)
    return float(np.clip(noisy, 0.0, 1.2))


def simulate_plate_data(
    cell_lines: Sequence[str],
    compounds: Sequence[str],
    n_plates_per_line: int = 1,
    replicates_per_dose: int = 2,
    dose_grid: Optional[Sequence[float]] = None,
    controls_per_plate: int = 3,
    random_state: Optional[int] = None,
) -> pd.DataFrame:
    """
    Generate a synthetic plate-level dataset for viability assays.

    Returns columns compatible with the historical tests:
    `viability_norm`, `is_control`, `cell_line`, `compound`, `dose_uM`, etc.
    """
    if not cell_lines or not compounds:
        return pd.DataFrame()

    if dose_grid is None:
        dose_grid = (0.001, 0.01, 0.1, 1.0, 5.0)

    rng = np.random.default_rng(random_state)
    rows: List[Dict[str, Any]] = []
    plate_counter = 0

    for cell in cell_lines:
        for plate_idx in range(n_plates_per_line):
            plate_counter += 1
            plate_id = f"{cell}_PLATE_{plate_counter:02d}"

            for compound in compounds:
                # Controls
                for ctrl_idx in range(controls_per_plate):
                    viability = 1.0 + rng.normal(0, 0.02)
                    rows.append(
                        {
                            "plate_id": plate_id,
                            "well_id": f"{plate_idx:02d}-{ctrl_idx:02d}",
                            "cell_line": cell,
                            "compound": compound,
                            "dose_uM": 0.0,
                            "is_control": 1,
                            "replicate": ctrl_idx + 1,
                            "viability_norm": float(np.clip(viability, 0.8, 1.2)),
                            "raw_signal": viability + rng.normal(0, 0.01),
                        }
                    )

                # Treated wells across the dose grid
                for dose in dose_grid:
                    for rep in range(replicates_per_dose):
                        viability = _simulate_viability(cell, compound, dose, rng)
                        rows.append(
                            {
                                "plate_id": plate_id,
                                "well_id": f"{plate_idx:02d}-{replicates_per_dose:02d}",
                                "cell_line": cell,
                                "compound": compound,
                                "dose_uM": float(dose),
                                "is_control": 0,
                                "replicate": rep + 1,
                                "viability_norm": viability,
                                "raw_signal": viability + rng.normal(0, 0.02),
                            }
                        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["time_h"] = 72.0
        df["cost_usd"] = 2.5
    return df


@dataclass
class SimulationEngine:
    """
    Minimal legacy simulator that mirrors the previous public API.

    It accepts either a pandas DataFrame or an iterable of dicts describing
    experiments and returns a list of dict records ready for downstream use.
    """

    world_model: Optional[Any] = None
    inventory: Optional[Any] = None
    vessel_library: Optional[Any] = None
    random_state: Optional[int] = None

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.random_state)

    def run(self, proposal: Any) -> List[Dict[str, Any]]:
        if proposal is None:
            return []

        if isinstance(proposal, pd.DataFrame):
            df = proposal.copy()
        elif isinstance(proposal, Mapping):
            df = pd.DataFrame([proposal])
        elif isinstance(proposal, Iterable):
            df = pd.DataFrame(list(proposal))
        else:
            raise TypeError("Unsupported proposal type for SimulationEngine")

        if df.empty:
            return []

        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            cell = row.get("cell_line", "Unknown")
            compound = row.get("compound", "DMSO")
            dose = float(row.get("dose_uM", row.get("dose", 0.0)))
            time_h = float(row.get("time_h", 72.0))
            replicate = int(row.get("replicate", 1))

            viability = _simulate_viability(cell, compound, dose, self._rng)
            record = {
                "cell_line": cell,
                "compound": compound,
                "dose": dose,
                "dose_uM": dose,
                "time_h": time_h,
                "replicate": replicate,
                "viability": viability,
                "viability_norm": viability,
                "raw_signal": viability + self._rng.normal(0, 0.02),
                "is_control": int(dose == 0.0),
                "cost_usd": float(row.get("cost_usd", 2.5)),
                "source": "legacy_simulation",
            }

            # Pass through any identifiers already attached to the proposal
            for key in ("experiment_id", "campaign_id", "unit_ops_used"):
                if key in row:
                    record[key] = row[key]

            records.append(record)

        return records

