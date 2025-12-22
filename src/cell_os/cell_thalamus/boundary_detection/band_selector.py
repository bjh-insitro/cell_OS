"""
Boundary Band Selector - High-Uncertainty Region Selection

Identifies wells/conditions in the boundary band where decisions are uncertain.
"""

import numpy as np
from typing import List, Dict, Optional, Literal

from .types import WellRecord, ConditionKey


class BoundaryBandSelector:
    """
    Select wells/conditions in the boundary band where decisions are uncertain.
    """

    def __init__(
        self,
        mode: Literal["entropy", "margin"] = "entropy",
        band_params: Optional[Dict] = None
    ):
        self.mode = mode
        self.band_params = band_params or {}

        # Default thresholds
        if mode == "entropy":
            self.entropy_threshold = self.band_params.get("entropy_threshold", 0.5)
        elif mode == "margin":
            self.margin_threshold = self.band_params.get("margin_threshold", 0.15)

    def select_wells(
        self,
        wells: List[WellRecord],
        proba: np.ndarray,
        uncertainty: np.ndarray
    ) -> List[WellRecord]:
        """
        Select wells in the boundary band.

        Args:
            wells: All wells
            proba: Class probabilities (n_wells, n_classes)
            uncertainty: Per-well uncertainty (n_wells,)

        Returns:
            Wells in boundary band
        """
        if self.mode == "entropy":
            # High entropy = uncertain decision
            mask = uncertainty > self.entropy_threshold

        elif self.mode == "margin":
            # Low margin = close to decision boundary
            # Margin = p_top - p_second
            proba_sorted = np.sort(proba, axis=1)
            margins = proba_sorted[:, -1] - proba_sorted[:, -2]
            mask = margins < self.margin_threshold

        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        return [well for well, in_band in zip(wells, mask) if in_band]

    def score_conditions(
        self,
        wells_in_band: List[WellRecord],
        covariance_traces: Dict[ConditionKey, float],
        death_flags: Dict[ConditionKey, bool]
    ) -> Dict[ConditionKey, float]:
        """
        Aggregate per-well band membership into per-condition boundary score.

        Score = mean_uncertainty × sqrt(covariance) × (1 - is_death)

        Args:
            wells_in_band: Wells in boundary band
            covariance_traces: Per-condition covariance from Phase 1
            death_flags: Per-condition death flags from Phase 1

        Returns:
            Dict mapping condition -> boundary score
        """
        # Group by condition
        condition_wells = {}
        for well in wells_in_band:
            cond = well.condition
            if cond not in condition_wells:
                condition_wells[cond] = []
            condition_wells[cond].append(well)

        # Compute scores
        scores = {}
        for cond, wells in condition_wells.items():
            # Mean uncertainty (could also use max)
            mean_uncertainty = 1.0  # Placeholder - would need to pass uncertainty values

            # Covariance weight
            cov_weight = np.sqrt(covariance_traces.get(cond, 1.0))

            # Death penalty
            death_penalty = 0.0 if death_flags.get(cond, False) else 1.0

            score = mean_uncertainty * cov_weight * death_penalty * len(wells)
            scores[cond] = score

        return scores
