# -*- coding: utf-8 -*-
"""Imaging acquisition utilities.

Provides data structures and a function to propose imaging doses based on
viability and stress Gaussian‑process models and an :class:`ImagingWindowGoal`.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

from .goal import ImagingWindowGoal
from cell_os.posteriors import DoseResponseGP, SliceKey
from cell_os.acquisition_config import AcquisitionConfig


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExperimentPlan:
    """A single proposed experiment.

    Attributes
    ----------
    slice_key: SliceKey
        The slice (cell_line, compound, time_h, readout) for which the dose
        is being proposed. In practice the ``readout`` will be the stress metric.
    dose_uM: float
        Dose in micromolar.
    stress_value: float
        Predicted value of the stress metric at ``dose_uM``.
    viability_value: float
        Predicted viability at ``dose_uM``.
    cells_per_field_pred: float
        Predicted cells per field (for QC).
    good_fields_per_well_pred: float
        Predicted good fields per well (for QC).
    score: float
        Multi-objective acquisition score (higher is better).
    """

    slice_key: SliceKey
    dose_uM: float
    stress_value: float
    viability_value: float = 0.0
    cells_per_field_pred: float = 0.0
    good_fields_per_well_pred: float = 0.0
    score: float = 0.0


@dataclass
class ExperimentResult:
    """The result of a single experiment.

    Attributes
    ----------
    slice_key: SliceKey
        The slice (cell_line, compound, time_h, readout) for which the dose
        was tested.
    dose_uM: float
        Dose in micromolar.
    stress_value: float
        Observed value of the stress metric.
    viability_value: float
        Observed viability.
    cells_per_field_observed: float
        Observed cells per field.
    good_fields_per_well_observed: float
        Observed good fields per well.
    """
    slice_key: SliceKey
    dose_uM: float
    stress_value: float
    viability_value: float
    cells_per_field_observed: float
    good_fields_per_well_observed: float



# ---------------------------------------------------------------------------
# Core proposal function
# ---------------------------------------------------------------------------

def compute_acquisition_score(
    viability_mean: float,
    stress_mean: float,
    cells_per_field_pred: float,
    good_fields_pred: float,
    goal: ImagingWindowGoal,
    config: Optional[AcquisitionConfig] = None,
) -> float:
    """Compute multi-objective acquisition score.

    Higher is better. Balances stress maximization with viability and QC constraints.

    Parameters
    ----------
    viability_mean: float
        Predicted viability (0-1).
    stress_mean: float
        Predicted stress metric value.
    cells_per_field_pred: float
        Predicted cells per field.
    good_fields_pred: float
        Predicted good fields per well.
    goal: ImagingWindowGoal
        Goal containing constraints and thresholds.

    Returns
    -------
    score: float
        Acquisition score (higher = better candidate).
    """
    # 1. Stress term, normalized to [0, 1] by assumption
    stress_term = stress_mean

    # 2. Viability penalty, zero inside band, quadratic outside
    if viability_mean < goal.viability_min:
        dv = goal.viability_min - viability_mean
        viab_penalty = dv * dv
    elif viability_mean > goal.viability_max:
        dv = viability_mean - goal.viability_max
        viab_penalty = dv * dv
    else:
        viab_penalty = 0.0

    # 3. QC slack penalty, penalize if below thresholds
    qc_penalty = 0.0
    if cells_per_field_pred < goal.min_cells_per_field:
        dc = goal.min_cells_per_field - cells_per_field_pred
        qc_penalty += (dc / goal.min_cells_per_field) ** 2
    if good_fields_pred < goal.min_fields_per_well:
        df = goal.min_fields_per_well - good_fields_pred
        qc_penalty += (df / goal.min_fields_per_well) ** 2

    # 4. Get weights from config (or use defaults)
    if config is None:
        config = AcquisitionConfig.balanced()
    w_stress = config.w_stress
    w_viab = config.w_viab
    w_qc = config.w_qc

    score = (
        w_stress * stress_term
        - w_viab * viab_penalty
        - w_qc * qc_penalty
    )
    return float(score)


def _apply_viability_constraints(
    gp: DoseResponseGP,
    grid: np.ndarray,
    goal: ImagingWindowGoal,
) -> np.ndarray:
    """Return a boolean mask of doses that satisfy viability constraints.

    Parameters
    ----------
    gp: DoseResponseGP
        GP model for the viability read‑out.
    grid: np.ndarray
        1‑D array of dose values (µM) on which to evaluate the GP.
    goal: ImagingWindowGoal
        Goal object containing viability band and optional max_std.
    """
    mean, std = gp.predict(grid, return_std=True)  # type: ignore[arg-type]
    mean = np.asarray(mean).reshape(-1)
    mask = (mean >= goal.viability_min) & (mean <= goal.viability_max)
    if goal.max_std is not None:
        std = np.asarray(std).reshape(-1)
        mask &= std <= goal.max_std
    return mask


def propose_imaging_doses(
    viability_gps: Dict[SliceKey, DoseResponseGP],
    stress_gps: Dict[SliceKey, DoseResponseGP],
    goal: ImagingWindowGoal,
    qc_gps: Dict[SliceKey, DoseResponseGP] = {},
    dose_grid: Optional[np.ndarray] = None,
) -> List[ExperimentPlan]:
    """Propose imaging doses respecting an ``ImagingWindowGoal``.

    The function:

    1. Builds a log‑spaced dose grid (default 200 points from 1e‑3 to 1e2 µM).
    2. For each slice present in ``viability_gps`` it filters the grid to
       doses whose predicted viability lies inside ``goal.viability_min`` /
       ``goal.viability_max`` and, if ``goal.max_std`` is set, whose predicted
       standard deviation is below that threshold.
    3. Looks up the matching stress GP (same cell line, compound, time_h and
       ``goal.stress_metric`` as readout). If ``goal.stress_min`` is set, it
       discards doses with stress below that value.
    4. Checks for QC GPs (readout="cells_per_field" and "good_fields_per_well").
       If present, filters out doses where predictions are below ``goal.min_cells_per_field``
       or ``goal.min_fields_per_well``.
    5. Creates an :class:`ExperimentPlan` for every remaining dose and sorts
       the list by ``stress_value`` descending (higher stress first).
    """
    if dose_grid is None:
        dose_grid = np.logspace(-3, 2, 200)  # 0.001 – 100 µM

    plans: List[ExperimentPlan] = []

    for slice_key, viab_gp in viability_gps.items():
        # Get viability predictions for full grid
        viab_mean, viab_std = viab_gp.predict(dose_grid, return_std=True)  # type: ignore[arg-type]
        viab_mean = np.asarray(viab_mean).reshape(-1)
        
        # Find the corresponding stress GP
        stress_slice = SliceKey(
            cell_line=slice_key.cell_line,
            compound=slice_key.compound,
            time_h=slice_key.time_h,
            readout=goal.stress_metric,
        )
        stress_gp = stress_gps.get(stress_slice)
        if stress_gp is None:
            continue

        # Predict stress on full grid
        stress_pred = stress_gp.predict(dose_grid, return_std=False)  # type: ignore[arg-type]
        if isinstance(stress_pred, tuple):
            stress_mean = stress_pred[0]
        else:
            stress_mean = stress_pred
        stress_mean = np.asarray(stress_mean).reshape(-1)
        
        # Get QC predictions (simple proxy for now: cells ~ 300 * viability, fields ~ 200 * viability)
        # Later can be replaced with actual QC GPs
        cells_per_field_pred = 300.0 * viab_mean
        good_fields_pred = 200.0 * viab_mean
        
        # Compute score for each dose
        for i, dose in enumerate(dose_grid):
            score = compute_acquisition_score(
                viability_mean=viab_mean[i],
                stress_mean=stress_mean[i],
                cells_per_field_pred=cells_per_field_pred[i],
                good_fields_pred=good_fields_pred[i],
                goal=goal,
            )
            
            plan = ExperimentPlan(
                slice_key=SliceKey(
                    cell_line=slice_key.cell_line,
                    compound=slice_key.compound,
                    time_h=slice_key.time_h,
                    readout=goal.stress_metric,
                ),
                dose_uM=float(dose),
                stress_value=float(stress_mean[i]),
                viability_value=float(viab_mean[i]),
                cells_per_field_pred=float(cells_per_field_pred[i]),
                good_fields_per_well_pred=float(good_fields_pred[i]),
                score=score,
            )
            plans.append(plan)

    plans.sort(key=lambda p: p.score, reverse=True)
    return plans

# End of module
