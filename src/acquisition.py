"""
acquisition.py

Logic for Phase 1: Choosing the next set of experiments.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import logging
import numpy as np
import pandas as pd

from src.schema import Phase0WorldModel

logger = logging.getLogger(__name__)


class AcquisitionFunction:
    """
    Acquisition function for selecting experiments.

    Wraps the logic for proposing experiments based on the current model state,
    constraints, and reward configuration.

    Key ideas:
      - If given a world model (Phase0WorldModel / DoseResponsePosterior),
        do max-uncertainty across all slices, filtered by the selected assay.
      - If given a single GP, do max-uncertainty over dose for that slice.
      - Penalize doses that have already been run many times for that slice
        using the GP's training data (X_train) as a proxy for history.

    Reward config keys (optional):
      - dose_grid_size: int, number of grid points for dose (default 50)
      - dose_min: float, minimum dose (uM, default 0.001)
      - dose_max: float, maximum dose (uM, default 10.0)
      - cost_per_well_usd: float, used for budget constraints and reporting (default 1.0)
      - repeat_penalty: float, penalty factor per repeat (default 0.02)
      - repeat_tol_fraction: float, fractional tolerance for repeats (default 0.05)
      - plate_id: str, ID to assign to proposed experiments (default "Phase1_Batch1")
      - mode: str, "max_uncertainty" or "ig_per_cost" (default "max_uncertainty")
    """

    def __init__(self, reward_config: Optional[Dict[str, Any]] = None):
        self.reward_config = reward_config or {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def propose(
        self,
        model: Any,
        assay: Any,
        budget: Optional[float] = None,
        n_experiments: int = 8,
    ) -> pd.DataFrame:
        """
        Propose a batch of experiments.

        Args:
            model:
                Either:
                  - a Phase0WorldModel / DoseResponsePosterior (has `gp_models`)
                  - a single DoseResponseGP (has `predict_on_grid`)
            assay:
                The selected assay / slice to explore.
            budget:
                Remaining budget in USD (optional constraint).
                If provided, caps the number of experiments based on
                cost_per_well_usd in reward_config.
            n_experiments:
                Maximum number of experiments to propose.

        Returns:
            DataFrame of proposed experiments (ranked and truncated to budget).
        """
        # Assay metadata
        cell_line = getattr(assay, "cell_line", "Unknown")
        compound = getattr(assay, "compound", "Unknown")
        time_h = getattr(assay, "time_h", 24.0)

        # Apply budget constraint if provided
        cost_per_well = float(self.reward_config.get("cost_per_well_usd", 1.0))
        if budget is not None:
            max_by_budget = int(budget // max(cost_per_well, 1e-9))
            if max_by_budget <= 0:
                logger.info(
                    "Budget (%.2f USD) insufficient for any experiments at %.2f USD/well.",
                    budget,
                    cost_per_well,
                )
                return pd.DataFrame(
                    columns=[
                        "cell_line",
                        "compound",
                        "dose_uM",
                        "time_h",
                        "priority_score",
                        "expected_cost_usd",
                        "expected_info_gain",
                        "unit_ops",
                        "plate_id",
                        "well_id",
                    ]
                )
            n_experiments = min(n_experiments, max_by_budget)

        if n_experiments <= 0:
            # Nothing requested
            return pd.DataFrame(
                columns=[
                    "cell_line",
                    "compound",
                    "dose_uM",
                    "time_h",
                    "priority_score",
                    "expected_cost_usd",
                    "expected_info_gain",
                    "unit_ops",
                    "plate_id",
                    "well_id",
                ]
            )

        # If we got a world model (posterior with many GPs), do max-uncertainty
        # across slices, restricted to the selected assay where possible.
        if hasattr(model, "gp_models"):
            selected = self._propose_from_world(
                world_model=model,
                assay=assay,
                n_experiments=n_experiments,
                return_all=False,
            )
            return selected

        # Otherwise treat it as a single GP and do 1D max-uncertainty over dose.
        candidates = []

        grid_results: Dict[str, Any] = {}
        if hasattr(model, "predict_on_grid"):
            try:
                grid_results = model.predict_on_grid(
                    num_points=self.reward_config.get("dose_grid_size", 50),
                    dose_min=self.reward_config.get("dose_min", 0.001),
                    dose_max=self.reward_config.get("dose_max", 10.0),
                )
            except Exception as e:
                logger.warning("[AcquisitionFunction] predict_on_grid failed: %s", e)

        doses = grid_results.get("dose_uM", [])
        stds = grid_results.get("std", [])

        # Build a repeat-penalty map from the GP training data
        dose_repeat_penalty = self._compute_repeat_penalty_for_gp(model, doses)

        if len(doses) and len(stds):
            for dose, std in zip(doses, stds):
                base_std = float(std)
                penalty = dose_repeat_penalty.get(float(dose), 0.0)
                cost = float(cost_per_well)
                effective_score = self._score_candidate(base_std, penalty, cost)

                candidates.append(
                    {
                        "cell_line": cell_line,
                        "compound": compound,
                        "dose_uM": float(dose),
                        "time_h": float(time_h),
                        "priority_score": float(effective_score),
                        "expected_cost_usd": cost,
                        "expected_info_gain": base_std,
                        "unit_ops": [
                            "op_passage",
                            "op_feed",
                            "op_transduce",
                            "op_stain",
                            "op_image",
                        ],
                    }
                )

        # Fallback: no usable GP info - pick a default point so the loop moves.
        if not candidates:
            logger.info(
                "No candidates generated from GP; falling back to default experiment."
            )
            candidates.append(
                {
                    "cell_line": cell_line,
                    "compound": compound,
                    "dose_uM": 1.0,
                    "time_h": float(time_h),
                    "priority_score": 0.0,
                    "expected_cost_usd": cost_per_well,
                    "expected_info_gain": 0.0,
                    "unit_ops": ["op_passage", "op_feed"],
                }
            )

        df_candidates = pd.DataFrame(candidates)
        df_candidates = df_candidates.sort_values("priority_score", ascending=False)

        selected = df_candidates.head(n_experiments).copy()
        plate_id = self.reward_config.get("plate_id", "Phase1_Batch1")
        selected = self._assign_plate_and_wells(selected, plate_id=plate_id)

        return selected

    # ------------------------------------------------------------------ #
    # World-model aware acquisition
    # ------------------------------------------------------------------ #

    def _propose_from_world(
        self,
        world_model: Phase0WorldModel,
        assay: Any,
        n_experiments: int,
        return_all: bool = False,
    ) -> Any:
        """
        Use the full posterior (Phase0WorldModel) to select experiments by
        maximum predictive uncertainty across slices.

        If an assay is provided, we restrict to matching cell line / compound.

        Args:
            world_model: Phase0WorldModel with gp_models dict.
            assay: object with optional cell_line, compound, time_h attributes.
            n_experiments: number of experiments to select.
            return_all: if True, return (selected, df_candidates_full),
                        otherwise return selected only.

        Returns:
            selected: DataFrame of selected experiments.
            If return_all=True: (selected, df_candidates_full)
        """
        dose_grid_size = self.reward_config.get("dose_grid_size", 50)
        dose_min = self.reward_config.get("dose_min", 0.001)
        dose_max = self.reward_config.get("dose_max", 10.0)
        cost_per_well = float(self.reward_config.get("cost_per_well_usd", 1.0))

        assay_cell = getattr(assay, "cell_line", None)
        assay_cmpd = getattr(assay, "compound", None)
        assay_time = getattr(assay, "time_h", None)

        candidates = []

        for key, gp in world_model.gp_models.items():
            # Optional filter: only slices matching the selected assay
            if assay_cell is not None and key.cell_line != assay_cell:
                continue
            if assay_cmpd is not None and key.compound != assay_cmpd:
                continue
            if assay_time is not None:
                try:
                    if abs(float(key.time_h) - float(assay_time)) > 1e-6:
                        continue
                except Exception:
                    # If time_h cannot be compared as floats, fall back to equality
                    if key.time_h != assay_time:
                        continue

            try:
                grid_results = gp.predict_on_grid(
                    num_points=dose_grid_size,
                    dose_min=dose_min,
                    dose_max=dose_max,
                )
            except Exception as e:
                logger.warning(
                    "[AcquisitionFunction] world-level predict_on_grid "
                    "failed for %s: %s",
                    key,
                    e,
                )
                continue

            doses = grid_results.get("dose_uM", [])
            stds = grid_results.get("std", None)

            if stds is None or len(doses) == 0:
                continue

            # Repeat penalty based on GP training data for this slice
            dose_repeat_penalty = self._compute_repeat_penalty_for_gp(gp, doses)

            for dose, std in zip(doses, stds):
                base_std = float(std)
                penalty = dose_repeat_penalty.get(float(dose), 0.0)
                cost = float(cost_per_well)
                effective_score = self._score_candidate(base_std, penalty, cost)

                candidates.append(
                    {
                        "cell_line": key.cell_line,
                        "compound": key.compound,
                        "time_h": key.time_h,
                        "dose_uM": float(dose),
                        "priority_score": float(effective_score),
                        "expected_cost_usd": cost,
                        "expected_info_gain": base_std,
                        "unit_ops": [
                            "op_passage",
                            "op_feed",
                            "op_transduce",
                            "op_stain",
                            "op_image",
                        ],
                    }
                )

        if not candidates:
            # No GPs yet or nothing matched assay; fall back to single default
            cell_line = assay_cell or "Unknown"
            compound = assay_cmpd or "Unknown"
            time_h = assay_time if assay_time is not None else 24.0
            logger.info(
                "No candidates generated from world model; "
                "falling back to default experiment."
            )
            candidates.append(
                {
                    "cell_line": cell_line,
                    "compound": compound,
                    "time_h": float(time_h),
                    "dose_uM": 1.0,
                    "priority_score": 0.0,
                    "expected_cost_usd": cost_per_well,
                    "expected_info_gain": 0.0,
                    "unit_ops": ["op_passage", "op_feed"],
                }
            )

        df_candidates = pd.DataFrame(candidates)
        df_candidates = df_candidates.sort_values("priority_score", ascending=False)

        selected = df_candidates.head(n_experiments).copy()
        plate_id = self.reward_config.get("plate_id", "Phase1_Batch1")
        selected = self._assign_plate_and_wells(selected, plate_id=plate_id)

        if return_all:
            return selected, df_candidates
        return selected

    # ------------------------------------------------------------------ #
    # Scoring / helpers
    # ------------------------------------------------------------------ #

    def _score_candidate(
        self,
        base_std: float,
        penalty: float,
        cost: float,
    ) -> float:
        """
        Compute a scalar acquisition score for a candidate.

        Modes:
          - "max_uncertainty": score = base_std - penalty
          - "ig_per_cost":     score = (base_std - penalty) / cost
        """
        mode = self.reward_config.get("mode", "max_uncertainty")
        adjusted = base_std - penalty

        if mode == "max_uncertainty":
            return adjusted
        elif mode == "ig_per_cost":
            return adjusted / max(cost, 1e-9)
        else:
            raise ValueError(f"Unknown acquisition mode: {mode}")

    def _compute_repeat_penalty_for_gp(
        self,
        gp: Any,
        grid_doses: Any,
    ) -> Dict[float, float]:
        """
        Build a simple "repeat penalty" for each dose on the candidate grid,
        based on how many times that dose (or a very similar one) has already
        been observed in the GP training data.

        Idea:
          - Look at gp.X_train (log10 dose space), or gp.X_train_ as fallback.
          - Convert to dose_uM.
          - For each grid dose, count how many training doses fall within a
            small tolerance (fractional).
          - penalty(dose) = penalty_factor * n_repeats

        Returns:
          Mapping from float(dose_uM) -> penalty.
        """
        # Try both X_train and sklearn-style X_train_
        train_log10 = getattr(gp, "X_train", None)
        if train_log10 is None:
            train_log10 = getattr(gp, "X_train_", None)

        if train_log10 is None:
            return {}

        try:
            if train_log10.size == 0:
                return {}
            train_doses = 10.0 ** np.asarray(train_log10).flatten()
        except Exception as e:
            logger.debug(
                "Failed to interpret GP training data as log10 doses: %s", e
            )
            return {}

        grid_doses = np.asarray(grid_doses, dtype=float)
        if grid_doses.size == 0:
            return {}

        # How aggressively to penalize repeats
        penalty_factor = float(self.reward_config.get("repeat_penalty", 0.02))
        # Relative tolerance: doses within this fraction are treated as repeats
        rel_tol = float(self.reward_config.get("repeat_tol_fraction", 0.05))

        penalties: Dict[float, float] = {}

        for d in grid_doses:
            if d <= 0:
                penalties[float(d)] = 0.0
                continue

            # Count how many training doses are "close" to this candidate
            # in fractional terms: |train - d| / d < rel_tol
            frac_diff = np.abs(train_doses - d) / d
            n_repeats = int((frac_diff < rel_tol).sum())

            penalties[float(d)] = penalty_factor * n_repeats

        return penalties

    @staticmethod
    def _assign_plate_and_wells(
        df: pd.DataFrame,
        plate_id: str = "Phase1_Batch1",
    ) -> pd.DataFrame:
        """
        Assign plate_id and well_id in a simple row-major fashion for a 96-well plate.
        """
        df = df.copy()
        df["plate_id"] = plate_id
        rows = "ABCDEFGH"
        cols = range(1, 13)
        well_ids = [f"{r}{c:02d}" for r in rows for c in cols]

        if len(df) > len(well_ids):
            raise ValueError(
                f"Not enough wells in 96-well layout for {len(df)} experiments."
            )

        df["well_id"] = well_ids[: len(df)]
        return df


# ---------------------------------------------------------------------- #
# Legacy API (backward compatibility)
# ---------------------------------------------------------------------- #


def propose_next_experiments(
    world_model: Phase0WorldModel,
    n_experiments: int = 8,
    dose_grid_size: int = 50,
    dose_min: float = 0.001,
    dose_max: float = 10.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Legacy function kept for backward compatibility.

    Strategy: "Max Uncertainty" across all GP slices in the Phase0WorldModel.

    Returns:
        selected: top-n experiments as DataFrame with plate/well assignments.
        df_candidates: full candidate ranking (all slices x doses).
    """
    acq = AcquisitionFunction(
        reward_config={
            "dose_grid_size": dose_grid_size,
            "dose_min": dose_min,
            "dose_max": dose_max,
        }
    )

    class _Assay:
        """Minimal assay stub for legacy call path."""

        cell_line: Optional[str] = None
        compound: Optional[str] = None
        time_h: Optional[float] = None

    selected, df_candidates = acq._propose_from_world(
        world_model=world_model,
        assay=_Assay(),
        n_experiments=n_experiments,
        return_all=True,
    )

    return selected, df_candidates
