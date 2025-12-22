"""
Response Pattern Belief Updater

Detects dose-response curvature and time-dependence in biological responses.
Uses noise floor to distinguish real patterns from measurement noise.
"""

from typing import List, Dict, Tuple

from .base import BaseBeliefUpdater
from ..ledger import cond_key


class ResponseBeliefUpdater(BaseBeliefUpdater):
    """
    Updates response pattern beliefs (dose curves, time-dependence).

    Tracks:
    - Dose-response curvature (nonlinear patterns in dose ladders)
    - Time-dependence (temporal trends at fixed dose)
    """

    def update(self, conditions: List) -> None:
        """
        Update response pattern beliefs from conditions.

        Args:
            conditions: List of ConditionSummary objects
        """
        self._detect_dose_curvature(conditions)
        self._detect_time_dependence(conditions)

    def _detect_dose_curvature(self, conditions: List):
        """Detect nonlinear dose-response patterns."""
        dose_groups = self._group_by_dose_series(conditions)

        for key, conds in dose_groups.items():
            if len(conds) < 3:
                continue  # Need 3+ doses to detect curvature

            conds_sorted = sorted(conds, key=lambda c: c.dose_uM)

            # Check for non-linear pattern (adjacent jumps differ significantly)
            diffs = []
            for i in range(len(conds_sorted) - 1):
                diff = abs(conds_sorted[i+1].mean - conds_sorted[i].mean)
                diffs.append(diff)

            if len(diffs) < 2:
                continue

            min_diff = min(diffs)
            max_diff = max(diffs)

            # If max jump is >2x min jump, we see curvature
            # Also require effect is larger than noise floor
            noise_sigma = self.beliefs.noise_sigma_hat or 0.05
            min_effect_threshold = 3 * noise_sigma

            if max_diff > min_effect_threshold and max_diff > 2.0 * min_diff:
                compound = key[0]

                self.beliefs._set(
                    "dose_curvature_seen",
                    True,
                    evidence={
                        "n_curves": 1,
                        "max_diff_ratio": max_diff / min_diff if min_diff > 0 else 0,
                        "threshold_ratio": 2.0,
                        "examples": [{
                            "compound": compound,
                            "min_diff": min_diff,
                            "max_diff": max_diff,
                            "ratio": max_diff / min_diff if min_diff > 0 else 0,
                            "noise_sigma": noise_sigma,
                            "min_effect_threshold": min_effect_threshold,
                        }]
                    },
                    supporting_conditions=[cond_key(c) for c in conds_sorted],
                    note=f"Nonlinear dose-response detected in {len(dose_groups)} conditions",
                )
                break  # Only need to detect once

    def _detect_time_dependence(self, conditions: List):
        """Detect temporal trends in responses."""
        time_groups = self._group_by_time_series(conditions)

        for key, conds in time_groups.items():
            if len(conds) < 3:
                continue  # Need 3+ timepoints

            conds_sorted = sorted(conds, key=lambda c: c.time_h)

            # Check for temporal trend (mean changes over time)
            means = [c.mean for c in conds_sorted]
            mean_range = max(means) - min(means)

            noise_sigma = self.beliefs.noise_sigma_hat or 0.05
            threshold = 3 * noise_sigma

            if mean_range > threshold:
                compound = key[0]
                dose = key[1]

                self.beliefs._set(
                    "time_dependence_seen",
                    True,
                    evidence={
                        "compound": compound,
                        "dose_uM": dose,
                        "mean_range": mean_range,
                        "threshold": threshold,
                        "n_timepoints": len(conds_sorted),
                    },
                    supporting_conditions=[cond_key(c) for c in conds_sorted],
                    note=f"Time-dependent response detected for {compound} @ {dose}µM",
                )
                break  # Only need to detect once

    def _group_by_dose_series(self, conditions: List) -> Dict[Tuple, List]:
        """Group conditions by (compound, time, cell_line) for dose ladder detection."""
        dose_groups = {}
        for cond in conditions:
            if cond.compound == 'DMSO':
                continue
            key = (cond.compound, cond.time_h, cond.cell_line)
            if key not in dose_groups:
                dose_groups[key] = []
            dose_groups[key].append(cond)
        return dose_groups

    def _group_by_time_series(self, conditions: List) -> Dict[Tuple, List]:
        """Group conditions by (compound, dose, cell_line) for time series detection."""
        time_groups = {}
        for cond in conditions:
            if cond.compound == 'DMSO':
                continue
            key = (cond.compound, cond.dose_uM, cond.cell_line)
            if key not in time_groups:
                time_groups[key] = []
            time_groups[key].append(cond)
        return time_groups
