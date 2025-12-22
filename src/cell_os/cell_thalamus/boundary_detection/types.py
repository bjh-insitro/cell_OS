"""
Data Types for Boundary Detection

Core dataclasses and type aliases used across the boundary detection system.
"""

import numpy as np
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

# Type aliases
ConditionKey = Tuple[str, str, float, str]  # (cell_line, compound, dose_uM, timepoint)


@dataclass
class WellRecord:
    """Individual well with embedding and metadata."""
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint: str
    embedding: np.ndarray
    viability: Optional[float] = None
    qc_pass: bool = True
    plate_id: str = ""
    batch_id: str = ""
    operator: Optional[str] = None
    day: Optional[str] = None
    is_sentinel: bool = False

    @property
    def condition(self) -> ConditionKey:
        return (self.cell_line, self.compound, self.dose_uM, self.timepoint)


@dataclass
class SentinelSpec:
    """Specification for a sentinel archetype."""
    name: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint: Optional[str] = None  # None means all timepoints
    min_reps_per_batch: int = 6

    def matches(self, well: WellRecord) -> bool:
        """Check if a well matches this sentinel spec."""
        if self.timepoint is not None and well.timepoint != self.timepoint:
            return False
        return (
            well.cell_line == self.cell_line and
            well.compound == self.compound and
            abs(well.dose_uM - self.dose_uM) < 0.001
        )


@dataclass
class BatchFrame:
    """Batch-specific normalization frame anchored by sentinels."""
    batch_id: str
    vehicle_mu: np.ndarray
    vehicle_sigma: Optional[np.ndarray] = None
    sentinel_mus: Optional[Dict[str, np.ndarray]] = None
    sentinel_mus_centered: Optional[Dict[str, np.ndarray]] = None  # After centering by vehicle
    quality: Optional[Dict[str, float]] = None
    n_vehicle_wells: int = 0
    n_sentinel_wells: Dict[str, int] = None

    # Nuisance diagnostics
    vehicle_drift_magnitude: Optional[float] = None  # |mu_veh(batch) - mu_veh(global)|
    sentinel_residual_drifts: Optional[Dict[str, float]] = None  # Post-centering drift per sentinel
    geometry_preservation: Optional[float] = None  # Correlation of pairwise distances

    def __post_init__(self):
        if self.sentinel_mus is None:
            self.sentinel_mus = {}
        if self.sentinel_mus_centered is None:
            self.sentinel_mus_centered = {}
        if self.quality is None:
            self.quality = {}
        if self.n_sentinel_wells is None:
            self.n_sentinel_wells = {}
        if self.sentinel_residual_drifts is None:
            self.sentinel_residual_drifts = {}
