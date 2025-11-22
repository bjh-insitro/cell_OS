"""
simulation.py

Generates synthetic plate data for Phase 0/1 simulations.
Ported from notebooks/01_phase0_simulation_and_baseline_sandbox.ipynb.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Tuple

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


def simulate_plate_data(
    cell_lines: List[str] = ("HepG2", "U2OS"),
    compounds: List[str] = ("staurosporine", "tunicamycin", "H2O2"),
    doses_small: np.ndarray = np.array([0, 0.001, 0.01, 0.1, 0.3, 1, 3, 10]),
    doses_large: np.ndarray = np.array([0, 3, 10, 30, 100, 300, 1000, 3000]),
    n_plates_per_line: int = 3,
    replicates_per_dose: int = 3,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a DataFrame of synthetic plate data.
    
    Args:
        cell_lines: List of cell lines to simulate.
        compounds: List of compounds to simulate.
        doses_small: Dose grid for potent compounds.
        doses_large: Dose grid for weak compounds (like H2O2).
        n_plates_per_line: Number of plates to generate per cell line.
        replicates_per_dose: Number of technical replicates per condition.
        random_seed: Seed for reproducibility.
        
    Returns:
        pd.DataFrame with columns matching the project schema.
    """
    rng = np.random.default_rng(random_seed)
    rows = []
    assay_time_h = 24
    
    for cell in cell_lines:
        for p in range(1, n_plates_per_line + 1):
            plate_id = f"{cell}_P{p}"
            
            # Plate-level multiplicative noise (e.g. pipetting error, cell count diffs)
            plate_factor = rng.normal(loc=1.0, scale=0.05)
            date = f"2025-11-0{p}"
            
            # -------------------------------------------------------
            # 1. Generate Control Wells (DMSO)
            # -------------------------------------------------------
            # Pretend 4 rows * 4 cols = 16 controls (simplified from notebook)
            control_signal_mean = 1.0 * plate_factor
            
            for row_char in ["A", "B", "C", "D"]:
                for col_idx in range(9, 13): # Cols 9-12
                    well_id = f"{row_char}{col_idx:02d}"
                    # Measurement noise
                    raw_viab = rng.normal(loc=control_signal_mean, scale=0.05)
                    
                    rows.append({
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
                        "liquid_handler_id": "manual"
                    })

            # -------------------------------------------------------
            # 2. Generate Treated Wells
            # -------------------------------------------------------
            for compound in compounds:
                # Select appropriate dose grid
                if compound == "H2O2":
                    doses = doses_large
                else:
                    doses = doses_small
                
                start_row_char = COMPOUND_TO_ROW_START.get(compound, "A")
                
                for dose in doses:
                    for rep in range(replicates_per_dose):
                        # Determine row: A,B,C... based on start row + replicate index
                        row_char = chr(ord(start_row_char) + rep)
                        
                        # Determine col: 1-based index of dose
                        # Note: np.where returns tuple of arrays
                        col_index = np.where(doses == dose)[0][0] + 1
                        well_id = f"{row_char}{col_index:02d}"
                        
                        # Get Ground Truth
                        ic50 = TRUE_IC50.get((cell, compound), 1.0)
                        h = HILL_SLOPES.get(compound, 1.0)
                        
                        true_viab = logistic_viability(dose, ic50, h)
                        true_viab *= plate_factor
                        
                        # Add measurement noise
                        raw_viab = rng.normal(loc=true_viab, scale=0.05)
                        
                        rows.append({
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
                            "liquid_handler_id": "manual"
                        })

    df = pd.DataFrame(rows)
    
    # -------------------------------------------------------
    # 3. Normalize (Simple Plate Normalization)
    # -------------------------------------------------------
    # This mimics the notebook's preprocessing step
    def normalize_plate(group):
        control_mask = group["is_control"] == 1
        if not control_mask.any():
            # Fallback if no controls (shouldn't happen in this sim)
            group["viability_norm"] = group["raw_signal"] / group["raw_signal"].mean()
        else:
            control_mean = group.loc[control_mask, "raw_signal"].mean()
            group["viability_norm"] = group["raw_signal"] / control_mean
        return group

    df = df.groupby("plate_id", group_keys=False).apply(normalize_plate)
    df["viability_norm"] = df["viability_norm"].clip(lower=0, upper=2.0)
    
    return df
