"""
campaign.py

Defines the Campaign Manager and Goal protocols for autonomous scientific campaigns.
"""

from __future__ import annotations

from typing import Protocol, List, Optional, Dict, Any
import numpy as np
import pandas as pd

from cell_os.schema import Phase0WorldModel
from cell_os.acquisition import propose_next_experiments


class CampaignGoal(Protocol):
    """Protocol for a scientific goal."""

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        """Check if the goal has been achieved based on the current world model."""
        ...

    def description(self) -> str:
        """Return a human readable description of the goal."""
        ...


def estimate_ic50_from_gp(
    gp,
    viability_threshold: float = 0.5,
    dose_min: float = 1e-3,
    dose_max: float = 100.0,
    n_grid: int = 200,
) -> Optional[float]:
    """
    Crude IC50 estimator from a dose response GP.

    Strategy:
      * Scan doses on a log10 grid between dose_min and dose_max.
      * Find the first dose where predicted viability drops below the threshold.
      * Linearly interpolate between the bracketing points.

    Assumes:
      * gp.predict(doses) returns a 1D array of viability values.
      * Doses are in uM.
    """
    doses = np.logspace(np.log10(dose_min), np.log10(dose_max), n_grid)
    # gp.predict returns (mean, std) or (mean, None). We only want mean.
    preds, _ = gp.predict(doses, return_std=False)  # type: ignore[attr-defined]

    preds = np.asarray(preds).reshape(-1)
    if preds.shape[0] != doses.shape[0]:
        raise ValueError("GP predict output shape does not match input doses")

    above = preds >= viability_threshold
    below = preds < viability_threshold

    for i in range(1, len(doses)):
        if above[i - 1] and below[i]:
            x1, x2 = doses[i - 1], doses[i]
            y1, y2 = preds[i - 1], preds[i]

            if y1 == y2:
                return float(x2)
            frac = (viability_threshold - y1) / (y2 - y1)
            ic50 = x1 + frac * (x2 - x1)
            return float(ic50)

    return None


def summarize_portfolio(world_model: Phase0WorldModel) -> pd.DataFrame:
    """
    Build a per (cell_line, compound, readout) table with IC50 estimates.

    Returns a DataFrame with columns:
      cell_line, compound, readout, ic50_uM
    """
    rows: List[Dict[str, Any]] = []

    for key, gp in world_model.gp_models.items():
        # Only estimate IC50 for viability-like readouts where 0.5 is meaningful
        # For now, we just calculate it for everything and let the user interpret.
        ic50 = estimate_ic50_from_gp(gp, viability_threshold=0.5)
        readout = getattr(key, "readout", "viability")
        
        rows.append(
            {
                "cell_line": key.cell_line,
                "compound": key.compound,
                "readout": readout,
                "ic50_uM": ic50,
            }
        )

    df = pd.DataFrame(rows)
    return df


class PotencyGoal:
    """
    Goal: Find a compound with an IC50 below a certain threshold for a specific cell line.
    """

    def __init__(
        self,
        cell_line: str,
        ic50_threshold_uM: float = 1.0,
        readout: str = "viability",
    ):
        self.cell_line = cell_line
        self.threshold = ic50_threshold_uM
        self.readout = readout
        self.met_by: Optional[str] = None  # Store which compound met the goal

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        """
        Check if any compound for the target cell line has IC50 < threshold.

        Uses a simple IC50 estimator based on the GP dose response curve.
        """
        best_ic50: Optional[float] = None
        best_compound: Optional[str] = None

        for key, gp in world_model.gp_models.items():
            if key.cell_line != self.cell_line:
                continue
            
            # Check readout match
            key_readout = getattr(key, "readout", "viability")
            if key_readout != self.readout:
                continue

            ic50 = estimate_ic50_from_gp(
                gp,
                viability_threshold=0.5,
                dose_min=1e-3,
                dose_max=100.0,
            )
            if ic50 is None:
                continue

            if ic50 < self.threshold:
                if best_ic50 is None or ic50 < best_ic50:
                    best_ic50 = ic50
                    best_compound = key.compound

        if best_ic50 is not None:
            self.met_by = best_compound
            return True

        return False

    def description(self) -> str:
        return (
            f"Find a compound for {self.cell_line} ({self.readout}) "
            f"with IC50 < {self.threshold} uM"
        )


class SelectivityGoal:
    """
    Goal: Find a compound that is potent against a target cell line (IC50 < threshold)
    and safe for a reference cell line (IC50 > safety_threshold).
    """

    def __init__(
        self,
        target_cell: str,
        safe_cell: str,
        potency_threshold_uM: float = 1.0,
        safety_threshold_uM: float = 1.0,
        readout: str = "viability",
    ):
        self.target_cell = target_cell
        self.safe_cell = safe_cell
        self.potency_threshold = potency_threshold_uM
        self.safety_threshold = safety_threshold_uM
        self.readout = readout
        self.met_by: Optional[str] = None

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        """
        Check if any compound meets the selectivity criterion:
          target IC50 < potency_threshold and safe cell IC50 > safety_threshold.
        """
        compounds = set(k.compound for k in world_model.gp_models.keys())

        for compound in compounds:
            target_key = next(
                (
                    k
                    for k in world_model.gp_models
                    if k.compound == compound 
                    and k.cell_line == self.target_cell
                    and getattr(k, "readout", "viability") == self.readout
                ),
                None,
            )
            safe_key = next(
                (
                    k
                    for k in world_model.gp_models
                    if k.compound == compound 
                    and k.cell_line == self.safe_cell
                    and getattr(k, "readout", "viability") == self.readout
                ),
                None,
            )

            if not target_key or not safe_key:
                continue

            gp_target = world_model.gp_models[target_key]
            gp_safe = world_model.gp_models[safe_key]

            target_ic50 = estimate_ic50_from_gp(gp_target, viability_threshold=0.5)
            safe_ic50 = estimate_ic50_from_gp(gp_safe, viability_threshold=0.5)

            if target_ic50 is None or safe_ic50 is None:
                continue

            is_potent = target_ic50 < self.potency_threshold
            is_safe = safe_ic50 > self.safety_threshold

            if is_potent and is_safe:
                self.met_by = compound
                return True

        return False

    def description(self) -> str:
        return (
            f"Find compound: {self.target_cell} IC50 < {self.potency_threshold} uM "
            f"AND {self.safe_cell} IC50 > {self.safety_threshold} uM "
            f"({self.readout})"
        )


class StressWindowGoal:
    """
    Goal: Find a dose window for a specific (cell_line, stressor) where the
    readout is within [min_val, max_val].
    
    Useful for tuning stressor doses for screens (e.g. finding LD30-LD70).
    """
    def __init__(
        self,
        cell_line: str,
        stressor: str,
        readout: str,
        min_val: float,
        max_val: float,
    ):
        self.cell_line = cell_line
        self.stressor = stressor
        self.readout = readout
        self.min_val = min_val
        self.max_val = max_val
        self.met_by_dose: Optional[float] = None

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        # Find the specific GP
        target_key = next(
            (
                k
                for k in world_model.gp_models
                if k.cell_line == self.cell_line
                and k.compound == self.stressor
                and getattr(k, "readout", "viability") == self.readout
            ),
            None,
        )
        
        if not target_key:
            return False
            
        gp = world_model.gp_models[target_key]
        
        # Scan grid to find a dose in range
        doses = np.logspace(-3, 2, 100) # 0.001 to 100 uM
        # gp.predict returns (mean, std). We only want mean.
        preds, _ = gp.predict(doses, return_std=False)
        
        # Check if any prediction falls in window
        for d, p in zip(doses, preds):
            if self.min_val <= p <= self.max_val:
                self.met_by_dose = float(d)
                return True
                
        return False
        
    def description(self) -> str:
        return (
            f"Find dose for {self.cell_line}/{self.stressor} where "
            f"{self.readout} is in [{self.min_val}, {self.max_val}]"
        )


class Campaign:
    """
    Manages the execution of a scientific campaign.
    """

    def __init__(self, goal: CampaignGoal, max_cycles: int = 5):
        self.goal = goal
        self.max_cycles = max_cycles
        self.current_cycle = 0
        self.is_complete = False
        self.success = False
        self.history: List[Dict[str, Any]] = []

    def check_goal(self, world_model: Phase0WorldModel) -> bool:
        """Check if the goal is met and update status."""
        if self.goal.is_met(world_model):
            self.success = True
            self.is_complete = True
            return True

        if self.current_cycle >= self.max_cycles:
            self.is_complete = True
            return False

        return False

    def run_cycle(
        self,
        world_model: Phase0WorldModel,
        n_experiments: int = 8,
        dose_grid_size: int = 50,
        dose_min: float = 0.001,
        dose_max: float = 10.0,
    ) -> pd.DataFrame:
        """
        Decide the next set of experiments, record the decision, and advance the cycle.

        Returns:
            DataFrame of proposed experiments for this cycle.

        The caller is responsible for:
          * Executing these experiments in the lab or simulator.
          * Ingesting new data and updating the world model.
          * Calling check_goal(world_model) after the update.
        """
        if self.is_complete:
            raise RuntimeError("Campaign is already complete")

        proposals, debug_df = propose_next_experiments(
            world_model,
            n_experiments=n_experiments,
            dose_grid_size=dose_grid_size,
            dose_min=dose_min,
            dose_max=dose_max,
        )

        self.current_cycle += 1

        self.history.append(
            {
                "cycle": self.current_cycle,
                "n_experiments": len(proposals),
                "goal_description": self.goal.description(),
                "goal_met_before_cycle": self.goal.is_met(world_model),
            }
        )

        return proposals
