"""
simulation.py

Generates synthetic plate data for Phase 0/1 simulations.
Ported from notebooks/01_phase0_simulation_and_baseline_sandbox.ipynb.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Tuple, Any

import numpy as np
import pandas as pd

# -------------------------------------------------------------------
# Ground Truth Parameters
# -------------------------------------------------------------------

TRUE_IC50 = {
    ("HepG2", "staurosporine"): 0.05,
    ("U2OS",  "staurosporine"): 0.20,
    ("HepG2", "tunicamycin"):   0.80,
    ("U2OS",  "tunicamycin"):   0.30,
    ("HepG2", "H2O2"):          150.0,
    ("U2OS",  "H2O2"):          250.0,
}

HILL_SLOPES = {
    "staurosporine": 1.2,
    "tunicamycin":   1.0,
    "H2O2":          1.5,
}

# Default mapping for row assignment in the "sandbox" layout
COMPOUND_TO_ROW_START = {
    "staurosporine": "A",
    "tunicamycin":   "D",
    "H2O2":          "G",
}


def logistic_viability(dose: float, ic50: float, h: float = 1.0) -> float:
    """
    Standard 4-parameter logistic (fixed min=0, max=1).
    """
    return 1.0 / (1.0 + (dose / ic50) ** h)


class SimulationEngine:
    """
    Execution engine for running simulated experiments.
    """

    def __init__(
        self,
        world_model: Any,
        inventory: Optional[Any] = None,
        vessel_library: Optional[Any] = None,
    ):
        self.world_model = world_model
        self.inventory = inventory
        self.vessel_library = vessel_library

    def run(self, proposal: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Execute a proposed set of experiments.

        Args:
            proposal: DataFrame of experiments to run.

        Returns:
            List of experimental records (dicts).
        """
        records: List[Dict[str, Any]] = []
        rng = np.random.default_rng()

        # Simulation Parameters
        BATCH_CV = 0.05      # 5 percent batch variability
        PIPETTING_CV = 0.02  # 2 percent pipetting error

        # Assign batch IDs if not present
        if "plate_id" not in proposal.columns:
            proposal["plate_id"] = "Sim_Batch_001"

        # Generate batch effects
        batch_ids = proposal["plate_id"].unique()
        batch_effects = {
            bid: rng.normal(loc=1.0, scale=BATCH_CV)
            for bid in batch_ids
        }

        # Iterate over proposed experiments
        for _, row in proposal.iterrows():
            cell = row.get("cell_line", "HepG2")
            compound = row.get("compound", "staurosporine")
            # Accept either 'dose_uM' (from acquisition) or legacy 'dose'
            target_dose = row.get("dose_uM", row.get("dose", 0.0))
            plate_id = row.get("plate_id", "Sim_Batch_001")

            # Apply Pipetting Noise
            if target_dose > 0:
                actual_dose = target_dose * rng.normal(loc=1.0, scale=PIPETTING_CV)
                actual_dose = max(0.0, actual_dose)
            else:
                actual_dose = 0.0

            # Ground truth parameters
            ic50 = TRUE_IC50.get((cell, compound), 1.0)
            h = HILL_SLOPES.get(compound, 1.0)

            # True viability based on ACTUAL dose
            true_viab = logistic_viability(actual_dose, ic50, h)

            # Apply Batch Effect
            batch_factor = batch_effects.get(plate_id, 1.0)
            true_viab *= batch_factor

            # Add Measurement Noise
            raw_viab = rng.normal(loc=true_viab, scale=0.05)
            raw_viab = max(0.0, min(1.5, raw_viab))

            record: Dict[str, Any] = {
                "experiment_id": f"sim_{rng.integers(10000, 99999)}",
                "campaign_id": "sim_campaign",
                "cell_line": cell,
                "compound": compound,
                "dose": target_dose,
                "actual_dose": actual_dose,
                "time_h": row.get("time_h", 24.0),
                "replicate": 1,
                "viability": raw_viab,
                "raw_signal": raw_viab * 10000,
                "noise_estimate": 0.05,
                "cost_usd": row.get("expected_cost_usd", 0.0),
                "unit_ops_used": row.get("unit_ops", []),
                "automation_score": 0.5,
                "timestamp": "2025-11-23T12:00:00",
                "source": "simulation",
                "plate_id": plate_id,
                "batch_effect": batch_factor,
            }
            records.append(record)

        return records


def simulate_plate_data(
    cell_lines: List[str] = ("HepG2", "U2OS"),
    compounds: List[str] = ("staurosporine", "tunicamycin", "H2O2"),
    doses_small: np.ndarray = np.array([0, 0.001, 0.01, 0.1, 0.3, 1, 3, 10]),
    doses_large: np.ndarray = np.array([0, 3, 10, 30, 100, 300, 1000, 3000]),
    n_plates_per_line: int = 3,
    replicates_per_dose: int = 3,
    random_seed: int = 42,
    batch_factor_cv: float = 0.0,
    pipetting_cv: float = 0.0,
) -> pd.DataFrame:
    """
    Generate a DataFrame of synthetic plate data.
    Legacy function kept for compatibility.
    """
    rng = np.random.default_rng(random_seed)
    rows: List[Dict[str, Any]] = []
    assay_time_h = 24

    for cell in cell_lines:
        for p in range(1, n_plates_per_line + 1):
            plate_id = f"{cell}_P{p}"
            plate_factor = rng.normal(loc=1.0, scale=0.05)
            batch_effect = 1.0
            if batch_factor_cv > 0:
                batch_effect = rng.normal(loc=1.0, scale=batch_factor_cv)
            total_plate_factor = plate_factor * batch_effect
            date = f"2025-11-0{p}"

            # Controls
            control_signal_mean = 1.0 * total_plate_factor
            for row_char in ["A", "B", "C", "D"]:
                for col_idx in range(9, 13):
                    well_id = f"{row_char}{col_idx:02d}"
                    raw_viab = rng.normal(loc=control_signal_mean, scale=0.05)
                    rows.append(
                        {
                            "plate_id": plate_id,
                            "well_id": well_id,
                            "cell_line": cell,
                            "compound": "DMSO",
                            "dose_uM": 0.0,
                            "time_h": assay_time_h,
                            "raw_signal": raw_viab * 10000,
                            "is_control": 1,
                            "date": date,
                            "incubator_id": "inc1",
                            "liquid_handler_id": "manual",
                        }
                    )

            # Treated
            for compound in compounds:
                if compound == "H2O2":
                    doses = doses_large
                else:
                    doses = doses_small

                start_row_char = COMPOUND_TO_ROW_START.get(compound, "A")

                for dose in doses:
                    for rep in range(replicates_per_dose):
                        row_char = chr(ord(start_row_char) + rep)
                        col_index = int(np.where(doses == dose)[0][0]) + 1
                        well_id = f"{row_char}{col_index:02d}"

                        actual_dose = dose
                        if pipetting_cv > 0 and dose > 0:
                            actual_dose = dose * rng.normal(loc=1.0, scale=pipetting_cv)
                            actual_dose = max(0.0, actual_dose)

                        ic50 = TRUE_IC50.get((cell, compound), 1.0)
                        h = HILL_SLOPES.get(compound, 1.0)

                        true_viab = logistic_viability(actual_dose, ic50, h)
                        true_viab *= total_plate_factor

                        raw_viab = rng.normal(loc=true_viab, scale=0.05)

                        rows.append(
                            {
                                "plate_id": plate_id,
                                "well_id": well_id,
                                "cell_line": cell,
                                "compound": compound,
                                "dose_uM": float(dose),
                                "time_h": assay_time_h,
                                "raw_signal": raw_viab * 10000,
                                "is_control": 0,
                                "date": date,
                                "incubator_id": "inc1",
                                "liquid_handler_id": "manual",
                            }
                        )

    df = pd.DataFrame(rows)

    def normalize_plate(group: pd.DataFrame) -> pd.DataFrame:
        control_mask = group["is_control"] == 1
        if not control_mask.any():
            group["viability_norm"] = group["raw_signal"] / group["raw_signal"].mean()
        else:
            control_mean = group.loc[control_mask, "raw_signal"].mean()
            group["viability_norm"] = group["raw_signal"] / control_mean
        return group

    grouped = df.groupby("plate_id", group_keys=False)
    normalized_groups = []
    for _, g in grouped:
        normalized_groups.append(normalize_plate(g))
    df = pd.concat(normalized_groups, ignore_index=True)

    df["viability_norm"] = df["viability_norm"].clip(lower=0, upper=2.0)

    return df


def simulate_low_fidelity_data(
    cell_lines: List[str],
    compounds: List[str],
    doses: List[float] = (0.001, 0.01, 0.1, 1.0, 10.0),
    time_points: List[int] = (24, 48, 72),
    n_replicates: int = 3,
    bias: float = 0.1,
    noise_scale: float = 0.1,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Simulate low-fidelity data. Legacy function.
    """
    rng = np.random.default_rng(random_seed)
    results: List[Dict[str, Any]] = []

    for cell in cell_lines:
        for cmpd in compounds:
            ic50 = TRUE_IC50.get((cell, cmpd), 1.0)
            h = HILL_SLOPES.get(cmpd, 1.0)

            for t in time_points:
                for d in doses:
                    y_true = logistic_viability(d, ic50, h)

                    for _ in range(n_replicates):
                        y_biased = y_true + bias
                        y_obs = rng.normal(loc=y_biased, scale=noise_scale)
                        y_obs = max(0.0, y_obs)

                        results.append(
                            {
                                "cell_line": cell,
                                "compound": cmpd,
                                "dose_uM": d,
                                "time_h": t,
                                "viability_norm": y_obs,
                                "is_control": 0,
                                "assay_type": "low_fidelity",
                            }
                        )

    return pd.DataFrame(results)
