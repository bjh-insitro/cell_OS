# -*- coding: utf-8 -*-
"""High level wiring for the imaging dose loop.

This module wires together:

  * A world model that exposes GP posteriors
  * The imaging acquisition function
  * An executor that runs imaging experiments

It intentionally knows nothing about real hardware or lab APIs. It only
deals in ExperimentPlan objects and tidy DataFrames.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, Optional

import numpy as np
import pandas as pd

from .goal import ImagingWindowGoal
from .acquisition import ExperimentPlan, propose_imaging_doses
from cell_os.posteriors import DoseResponseGP, SliceKey


class WorldModelLike(Protocol):
    """Minimal protocol for world models used by the ImagingDoseLoop."""

    def get_viability_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        ...

    def get_stress_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        ...

    def get_qc_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        ...

    def update_with_results(self, df: pd.DataFrame) -> None:
        ...


class ExecutorLike(Protocol):
    """Something that can execute a batch of imaging experiments."""

    def run_batch(self, plans: List[ExperimentPlan]) -> pd.DataFrame:
        """
        Execute a batch of ExperimentPlan objects and return a tidy
        DataFrame of results, one row per (slice, dose) with at least
        the viability and stress metrics specified in the goal.
        """
        ...


@dataclass
class BatchPlan:
    """Container for an ordered batch of ExperimentPlan objects."""

    plans: List[ExperimentPlan] = field(default_factory=list)


@dataclass
class ImagingDoseLoop:
    """Controller for the imaging dose selection and execution loop."""

    world_model: WorldModelLike
    executor: ExecutorLike
    goal: ImagingWindowGoal

    def propose(self, dose_grid: Optional[np.ndarray] = None) -> BatchPlan:
        """Propose the next batch of doses given the current world model."""

        viability_gps = self.world_model.get_viability_gps()
        stress_gps = self.world_model.get_stress_gps()
        qc_gps = self.world_model.get_qc_gps()

        plans = propose_imaging_doses(
            viability_gps=viability_gps,
            stress_gps=stress_gps,
            qc_gps=qc_gps,
            goal=self.goal,
            dose_grid=dose_grid,
        )
        return BatchPlan(plans=plans)

    def run_one_cycle(self, dose_grid: Optional[np.ndarray] = None) -> BatchPlan:
        """Single closed loop step: propose, execute, update world model.

        Returns the BatchPlan that was executed.
        """

        batch = self.propose(dose_grid=dose_grid)
        if not batch.plans:
            # Nothing satisfies the goal for the current models
            return batch

        results = self.executor.run_batch(batch.plans)
        self.world_model.update_with_results(results)
        return batch


__all__ = [
    "WorldModelLike",
    "ExecutorLike",
    "BatchPlan",
    "ImagingDoseLoop",
]
