"""
posteriors.py

Posterior objects for dose-response modeling.

Historically this lived in schema.py as Phase0WorldModel. We now keep
the posterior separate from the lab world state (see lab_world_model.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, NamedTuple

import pandas as pd

from cell_os.modeling import DoseResponseGP


class SliceKey(NamedTuple):
    """
    Unique identifier for a single experimental slice.
    A slice is defined by the tuple (cell_line, compound, time_h, readout).
    """
    cell_line: str
    compound: str
    time_h: float
    readout: str = "viability"


@dataclass
class DoseResponsePosterior:
    """
    Posterior over dose-response relationships for a campaign.

    Contains:
      - gp_models: GP fits for each (cell_line, compound, time_h, readout) slice
      - noise_df: replicate variability across dose
      - drift_df: plate control drift

    This is a pure belief object: it does not know about inventory,
    workflows, or costs. It only summarizes what the model believes
    given the experiment log.
    """

    gp_models: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)
    noise_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    drift_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # --------------------------------------------------------
    # Accessors
    # --------------------------------------------------------
    def get_gp(
        self,
        cell_line: str,
        compound: str,
        time_h: float,
        readout: str = "viability",
    ) -> Optional[DoseResponseGP]:
        """
        Retrieve the GP model for a specific slice, if it exists.
        """
        key = SliceKey(cell_line, compound, float(time_h), readout)
        return self.gp_models.get(key)

    # --------------------------------------------------------
    # Constructors
    # --------------------------------------------------------
    @classmethod
    def from_components(
        cls,
        gp_models: Dict[SliceKey, DoseResponseGP],
        noise_df: Optional[pd.DataFrame] = None,
        drift_df: Optional[pd.DataFrame] = None,
    ) -> "DoseResponsePosterior":
        """
        Simple constructor if you already have all the pieces.
        """
        return cls(
            gp_models=gp_models,
            noise_df=noise_df.copy() if noise_df is not None else pd.DataFrame(),
            drift_df=drift_df.copy() if drift_df is not None else pd.DataFrame(),
        )

    @classmethod
    def from_world(
        cls,
        world,
        campaign_id: str,
        readout_names: Union[str, List[str]] = "viability",
        time_h: float = 24.0,
    ) -> "DoseResponsePosterior":
        """
        Build a posterior from a LabWorldModel experiment log.

        Args:
            world: LabWorldModel instance
            campaign_id: Campaign ID to filter by
            readout_names: Single string or list of readout columns to model
            time_h: Time point to filter by

        Assumes world.experiments has at least:
          - campaign_id
          - cell_line
          - compound
          - dose_uM
          - time_h
          - readout_name (if using long format) OR the columns specified in readout_names
          - readout_value (if using long format)
        """
        df_campaign = world.get_experiments_for_campaign(campaign_id)
        if df_campaign.empty:
            raise ValueError(f"No experiments found for campaign_id={campaign_id!r}")

        # Normalize readout_names to list
        if isinstance(readout_names, str):
            readout_names = [readout_names]

        gp_models: Dict[SliceKey, DoseResponseGP] = {}
        
        # We need to handle two data formats:
        # 1. Wide format: columns like "viability", "posh_score" exist directly
        # 2. Long format: columns "readout_name" and "readout_value" exist
        
        is_long_format = "readout_name" in df_campaign.columns and "readout_value" in df_campaign.columns

        for readout in readout_names:
            # Filter data for this specific readout
            if is_long_format:
                df_slice = df_campaign[df_campaign["readout_name"] == readout].copy()
                val_col = "readout_value"
            else:
                if readout not in df_campaign.columns:
                    # Skip if column missing
                    continue
                df_slice = df_campaign.copy()
                val_col = readout

            # Filter by time
            df_slice = df_slice[df_slice["time_h"] == float(time_h)]
            
            if df_slice.empty:
                continue

            # Fit a GP for each (cell_line, compound) slice
            for (cell_line, compound), sub in df_slice.groupby(["cell_line", "compound"]):
                # Drop zero-dose points to keep log10(dose) happy
                # Ensure dose_uM is numeric
                sub["dose_uM"] = pd.to_numeric(sub["dose_uM"], errors="coerce")
                sub_pos = sub[sub["dose_uM"] > 0].copy()
                
                if sub_pos.empty:
                    continue

                try:
                    gp = DoseResponseGP.from_dataframe(
                        sub_pos,
                        cell_line=cell_line,
                        compound=compound,
                        time_h=float(time_h),
                        dose_col="dose_uM",
                        viability_col=val_col,
                    )
                except Exception:
                    # For now, skip failing slices. Later you can log or raise.
                    continue

                key = SliceKey(cell_line, compound, float(time_h), readout)
                gp_models[key] = gp

        # Noise and drift are harder to generalize to N readouts in one dataframe
        # without making the structure complex. For Phase 0, we'll just compute
        # them for the *first* readout if available, or skip.
        # Ideally, noise_df should be keyed by readout too.
        # For now, let's just leave them empty or simple to avoid breaking changes.
        noise_df = pd.DataFrame()
        drift_df = pd.DataFrame()

        return cls(
            gp_models=gp_models,
            noise_df=noise_df,
            drift_df=drift_df,
        )


# Backwards compat for older code that still imports Phase0WorldModel
Phase0WorldModel = DoseResponsePosterior
