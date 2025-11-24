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
      - gp_models: GP fits for each (cell_line, compound, time_h) slice
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
    def get_gp(self, cell_line: str, compound: str, time_h: float) -> Optional[DoseResponseGP]:
        """
        Retrieve the GP model for a specific slice, if it exists.
        """
        key = SliceKey(cell_line, compound, float(time_h))
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
        readout_name: str,
        time_h: float,
    ) -> "DoseResponsePosterior":
        """
        Build a posterior from a LabWorldModel experiment log.

        Assumes world.experiments has at least:
          - campaign_id
          - cell_line
          - compound
          - dose_uM
          - time_h
          - readout_name
          - readout_value
          - plate_id
        """
        df = world.get_experiments_for_campaign(campaign_id)
        if df.empty:
            raise ValueError(f"No experiments found for campaign_id={campaign_id!r}")

        df = df[df["readout_name"] == readout_name].copy()
        df = df[df["time_h"] == float(time_h)].copy()

        if df.empty:
            raise ValueError(
                f"No matching rows for campaign_id={campaign_id!r}, "
                f"readout_name={readout_name!r}, time_h={time_h}"
            )

        gp_models: Dict[SliceKey, DoseResponseGP] = {}

        # Fit a GP for each (cell_line, compound) slice
        for (cell_line, compound), sub in df.groupby(["cell_line", "compound"]):
            # Drop zero-dose points to keep log10(dose) happy
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
                    viability_col="readout_value",
                )
            except Exception:
                # For now, skip failing slices. Later you can log or raise.
                continue

            key = SliceKey(cell_line, compound, float(time_h))
            gp_models[key] = gp

        # Noise: replicate variability per (cell_line, compound, dose)
        noise_df = (
            df.groupby(["cell_line", "compound", "dose_uM"])
            ["readout_value"]
            .std()
            .reset_index()
            .rename(columns={"readout_value": "viability_std"})
        )

        # Plate drift: control mean per plate relative to global
        controls = df[df["compound"] == "DMSO"].copy()
        if not controls.empty:
            drift_df = (
                controls.groupby("plate_id")["readout_value"]
                .mean()
                .reset_index()
                .rename(columns={"readout_value": "control_mean"})
            )
            global_mean = drift_df["control_mean"].mean()
            drift_df["control_delta"] = drift_df["control_mean"] - global_mean
        else:
            drift_df = pd.DataFrame(columns=["plate_id", "control_mean", "control_delta"])

        return cls(
            gp_models=gp_models,
            noise_df=noise_df,
            drift_df=drift_df,
        )


# Backwards compat for older code that still imports Phase0WorldModel
Phase0WorldModel = DoseResponsePosterior
