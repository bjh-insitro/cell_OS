"""
posteriors.py

Holds statistical inference artifacts produced by Phase 0 and later phases.
These describe what the OS *believes* about the world, not the world itself.

This file replaces the old `schema.py` contents that stored the
Phase0WorldModel. The naming is now explicit: this is a posterior,
computed *from* experiment data, not a representation of the real world.

`Phase0WorldModel` is kept as an alias for backwards compatibility.
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
class DoseResponsePosterior:
    """
    Posterior over dose-response relationships for a campaign.

    Contains:
    1. A collection of GP models, one for each (cell, compound, time) slice.
    2. A global noise map (std dev of replicates).
    3. A global drift map (plate control deviations).

    This is purely a *belief* object — it is computed from experiment data.
    It does not represent the physical world, workflows, costs, or inventory.
    """

    # Map from slice key -> trained GP model
    gp_models: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)

    # DataFrame with columns: [cell_line, compound, time_h, dose_uM, viability_std, ...]
    noise_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # DataFrame with columns: [plate_id, control_delta, ...]
    drift_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    def get_gp(self, cell_line: str, compound: str, time_h: float) -> Optional[DoseResponseGP]:
        """
        Retrieve the GP model for a specific slice, if it exists.
        """
        key = SliceKey(cell_line, compound, float(time_h))
        return self.gp_models.get(key)


# -------------------------------------------------------------------------
# Backwards Compatibility Layer
# -------------------------------------------------------------------------
# Many parts of the existing repo expect `Phase0WorldModel`.
# We keep this alias so nothing breaks, and you can migrate gradually.
# -------------------------------------------------------------------------

Phase0WorldModel = DoseResponsePosterior
