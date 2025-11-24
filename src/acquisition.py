"""
acquisition.py

Logic for Phase 1: Choosing the next set of experiments.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from src.schema import Phase0WorldModel


class AcquisitionFunction:
    """
    Acquisition function for selecting experiments.
    
    Wraps the logic for proposing experiments based on the current model state,
    constraints, and reward configuration.
    """

    def __init__(self, reward_config: Optional[Dict[str, Any]] = None):
        self.reward_config = reward_config or {}

    def propose(
        self,
        model: Any,  # DoseResponseGP or similar
        assay: Any,  # Assay definition from selector
        budget: Optional[float] = None,
        n_experiments: int = 8,
    ) -> pd.DataFrame:
        """
        Propose a batch of experiments.

        Args:
            model: The current GP model state.
            assay: The selected assay/region to explore.
            budget: Remaining budget (optional constraint).
            n_experiments: Number of experiments to propose.

        Returns:
            DataFrame of proposed experiments with columns matching the schema.
        """
        # For now, we delegate to the existing logic if the model matches
        # the Phase0WorldModel expectation, or we adapt.
        
        # If 'model' is actually the Phase0WorldModel (which it seems to be in legacy code),
        # we can use the old function logic. But in the new loop, 'model' is DoseResponseGP.
        # We need to bridge this.
        
        # ADAPTER LOGIC:
        # The new loop passes DoseResponseGP as 'model'.
        # The old logic expected Phase0WorldModel.
        # For this refactor, we will implement a simplified version of "Max Uncertainty"
        # directly on the DoseResponseGP, consistent with the new architecture.

        candidates = []
        
        # 1. Define search grid based on the selected assay
        # The assay object from AssaySelector likely contains cell_line and compound info
        cell_line = getattr(assay, "cell_line", "Unknown")
        compound = getattr(assay, "compound", "Unknown")
        
        # Use the model to predict on a grid if available
        if hasattr(model, "predict_on_grid"):
            # Predict on a standard grid
            grid_results = model.predict_on_grid(
                num_points=50,
                dose_min=0.001,
                dose_max=10.0
            )
            
            doses = grid_results.get("dose_uM", [])
            stds = grid_results.get("std", [])
            
            if stds is not None:
                for dose, std in zip(doses, stds):
                    candidates.append({
                        "cell_line": cell_line,
                        "compound": compound,
                        "dose": dose,
                        "time_h": 24.0, # Default
                        "priority_score": std, # Max uncertainty
                        "expected_cost_usd": 0.0, # Placeholder
                        "expected_info_gain": std,
                        "unit_ops": ["op_passage", "op_feed", "op_transduce", "op_stain", "op_image"] # Placeholder
                    })

        if not candidates:
            # Fallback if model is empty or no predictions
            # Return a single default experiment to keep the loop moving
            candidates.append({
                "cell_line": cell_line,
                "compound": compound,
                "dose": 1.0,
                "time_h": 24.0,
                "priority_score": 0.0,
                "expected_cost_usd": 0.0,
                "expected_info_gain": 0.0,
                "unit_ops": ["op_passage", "op_feed"]
            })

        # 2. Convert to DataFrame and sort
        df_candidates = pd.DataFrame(candidates)
        df_candidates = df_candidates.sort_values("priority_score", ascending=False)
        
        # 3. Select top N
        selected = df_candidates.head(n_experiments).copy()
        
        # 4. Assign metadata
        selected["plate_id"] = "Phase1_Batch1"
        
        # Assign wells
        rows = "ABCDEFGH"
        cols = range(1, 13)
        well_ids = [f"{r}{c:02d}" for r in rows for c in cols]
        selected["well_id"] = well_ids[:len(selected)]
        
        return selected


def propose_next_experiments(
    world_model: Phase0WorldModel,
    n_experiments: int = 8,
    dose_grid_size: int = 50,
    dose_min: float = 0.001,
    dose_max: float = 10.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Legacy function kept for backward compatibility.
    """
    # This logic is largely superseded by the class above but kept for reference
    # or legacy calls.
    candidates = []
    for key, gp in world_model.gp_models.items():
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
        raise ValueError("No candidates generated.")
        
    df_candidates = pd.DataFrame(candidates)
    df_candidates = df_candidates.sort_values("priority_score", ascending=False)
    selected = df_candidates.head(n_experiments).copy()
    selected["plate_id"] = "Phase1_Batch1"
    rows = "ABCDEFGH"
    cols = range(1, 13)
    well_ids = [f"{r}{c:02d}" for r in rows for c in cols]
    selected["well_id"] = well_ids[:len(selected)]
    
    return selected, df_candidates
