# -*- coding: utf-8 -*-
"""Imaging goal definitions for multi-channel dose loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ImagingWindowGoal:
    """Goal for the ImagingDoseLoop.

    Channels:
      * viability_metric – name of the viability readout
        (for example "viability_fraction" from Hoechst/PI).
      * stress_metric – name of the stress readout
        (for example "cellrox_mean").

    Constraints:
      * viability_min / viability_max – inclusive viability band.
      * stress_min – optional minimum stress level.
      * min_cells_per_field – nuclei per field for segmentation to count.
      * min_fields_per_well – good fields per well.
      * max_std – optional max predicted viability std inside the band.

    Scope:
      * max_slices – optional cap on number of slices to consider.
    """

    viability_metric: str = "viability_fraction"
    stress_metric: str = "cellrox_mean"

    viability_min: float = 0.8
    viability_max: float = 1.0

    stress_min: Optional[float] = None

    min_cells_per_field: int = 100
    min_fields_per_well: int = 100

    max_std: Optional[float] = 0.15
    max_slices: Optional[int] = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.viability_min <= self.viability_max <= 1.0):
            raise ValueError("viability bounds must be within [0, 1] and min <= max")

    def description(self) -> str:
        stress_part = (
            f" and {self.stress_metric} ≥ {self.stress_min}" if self.stress_min is not None else f" and maximise {self.stress_metric}"
        )
        return (
            f"Find doses where {self.viability_metric} ∈ [{self.viability_min}, {self.viability_max}]"
            f"{stress_part} (QC: ≥{self.min_cells_per_field} cells/field, ≥{self.min_fields_per_well} fields)"
        )
