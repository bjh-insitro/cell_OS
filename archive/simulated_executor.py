# -*- coding: utf-8 -*-
"""Simulated imaging executor for the ImagingDoseLoop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from cell_os.imaging_acquisition import ExperimentPlan
from cell_os.imaging_goal import ImagingWindowGoal
from cell_os.imaging_loop import ExecutorLike


@dataclass
class SimulatedImagingExecutor(ExecutorLike):
    """Simulated executor for imaging-based dose experiments."""

    goal: ImagingWindowGoal
    rng: np.random.Generator = field(
        default_factory=lambda: np.random.default_rng(seed=1234)
    )

    # --- internal curves ----------------------------------------------------

    def _viability_true(self, dose_uM: float) -> float:
        x = np.log10(dose_uM + 1e-9)
        return float(1.0 / (1.0 + np.exp(4.0 * (x - 0.0))))  # LD50 ~ 1 µM

    def _stress_true(self, dose_uM: float) -> float:
        x = np.log10(dose_uM + 1e-9)
        return float(1.0 / (1.0 + np.exp(-3.0 * (x + 0.5))))  # rises earlier

    # --- ExecutorLike API ---------------------------------------------------

    def run_batch(self, plans: List[ExperimentPlan]) -> pd.DataFrame:
        rows = []

        for plan in plans:
            sk = plan.slice_key
            dose = float(plan.dose_uM)

            # True curves
            v_true = self._viability_true(dose)
            s_true = self._stress_true(dose)

            # Add noise
            v_obs = v_true + self.rng.normal(scale=0.03)
            s_obs = s_true + self.rng.normal(scale=0.05)

            # Clip to plausible ranges
            v_obs = float(np.clip(v_obs, 0.0, 1.0))
            s_obs = float(np.clip(s_obs, 0.0, 2.0))

            # Segmentation QC
            cells_per_field = int(np.round(300 * v_obs + self.rng.normal(scale=10)))
            cells_per_field = max(cells_per_field, 0)

            total_fields = 200
            good_fields = int(np.round(total_fields * v_obs))
            good_fields = max(min(good_fields, total_fields), 0)

            rows.append(
                {
                    "cell_line": sk.cell_line,
                    "compound": sk.compound,
                    "time_h": getattr(sk, "time_h", 24.0),
                    "dose_uM": dose,
                    self.goal.viability_metric: v_obs,
                    self.goal.stress_metric: s_obs,
                    "cells_per_field": cells_per_field,
                    "good_fields_per_well": good_fields,
                }
            )

        return pd.DataFrame(rows)
