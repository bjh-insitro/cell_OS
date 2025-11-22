"""
acquisition.py

Logic for Phase 1: Choosing the next set of experiments.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.schema import Phase0WorldModel, SliceKey


def propose_next_experiments(
    world_model: Phase0WorldModel,
    n_experiments: int = 8,
    dose_grid_size: int = 50,
    dose_min: float = 0.001,
    dose_max: float = 10.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Select the next best experiments to run based on the current world model.
    
    Strategy: "Max Uncertainty" (Epistemic Gain).
    We scan a grid of doses for every (cell, compound) slice and pick the
    points where the GP model is most uncertain (highest standard deviation).
    
    Args:
        world_model: The current belief state (Phase 0 model).
        n_experiments: Number of wells to fill (default 8).
        dose_grid_size: Number of candidate doses to evaluate per slice.
        dose_min: Minimum candidate dose (uM).
        dose_max: Maximum candidate dose (uM).
        
    Returns:
        Tuple of (selected_experiments, all_candidates):
            - selected_experiments: DataFrame of top N choices with plate/well IDs.
            - all_candidates: DataFrame of ALL scored candidates (for reporting).
    """
    candidates = []

    # 1. Generate candidates for every slice
    for key, gp in world_model.gp_models.items():
        # Create a candidate grid
        # We use the helper on the GP object if available, or manual
        # The GP class in modeling.py has predict_on_grid, let's use that
        # but we want to enforce specific bounds for the search
        grid_results = gp.predict_on_grid(
            num_points=dose_grid_size,
            dose_min=dose_min,
            dose_max=dose_max
        )
        doses = grid_results["dose_uM"]
        stds = grid_results["std"]
        
        if stds is None:
            continue
            
        for dose, std in zip(doses, stds):
            candidates.append({
                "cell_line": key.cell_line,
                "compound": key.compound,
                "time_h": key.time_h,
                "dose_uM": dose,
                "priority_score": std
            })
            
    if not candidates:
        raise ValueError("No candidates generated. Is the world model empty?")
        
    # 2. Convert to DataFrame and sort
    df_candidates = pd.DataFrame(candidates)
    df_candidates = df_candidates.sort_values("priority_score", ascending=False)
    
    # 3. Select top N
    selected = df_candidates.head(n_experiments).copy()
    
    # 4. Assign plate/well metadata (placeholders for now)
    # We'll just put them all on "Phase1_Batch1"
    selected["plate_id"] = "Phase1_Batch1"
    
    # Assign wells A01, A02, ...
    # Simple generator for well IDs
    rows = "ABCDEFGH"
    cols = range(1, 13)
    well_ids = [f"{r}{c:02d}" for r in rows for c in cols]
    
    if len(selected) > len(well_ids):
        # Should not happen with n=8, but good to be safe
        raise ValueError(f"Too many experiments selected ({len(selected)}) for one plate.")
        
    selected["well_id"] = well_ids[:len(selected)]
    
    # Reorder columns nicely
    cols_order = [
        "plate_id", "well_id", "cell_line", "compound", 
        "dose_uM", "time_h", "priority_score"
    ]
    return selected[cols_order], df_candidates
