"""
schema.py

Defines the core data structures for the cell_OS world model.
This acts as the contract between Phase 0 (Modeling) and Phase 1 (Acquisition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, NamedTuple, Optional

import pandas as pd
from src.modeling import DoseResponseGP


class SliceKey(NamedTuple):
    """
    Unique identifier for a single experimental slice.
    A slice is defined by the tuple (cell_line, compound, time_h).
    """
    cell_line: str
    compound: str
    time_h: float


@dataclass
class Phase0WorldModel:
    """
    The frozen result of Phase 0 (Baseline World Modeling).
    
    Contains:
    1. A collection of GP models, one for each (cell, compound, time) slice.
    2. A global noise map (std dev of replicates).
    3. A global drift map (plate control deviations).
    """
    
    # Map from slice key -> trained GP model
    gp_models: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)
    
    # DataFrame with columns: [cell_line, compound, time_h, dose_uM, viability_std, ...]
    noise_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # DataFrame with columns: [plate_id, control_delta, ...]
    drift_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    def get_gp(self, cell_line: str, compound: str, time_h: float) -> Optional[DoseResponseGP]:
        """Retrieve the GP model for a specific slice, if it exists."""
        key = SliceKey(cell_line, compound, float(time_h))
        return self.gp_models.get(key)
