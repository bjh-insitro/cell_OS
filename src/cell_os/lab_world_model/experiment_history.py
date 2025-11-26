"""
Experiment History module.
Handles experiment tables, canonicalization, and campaign management.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import pandas as pd

# Simple aliases for readability
CampaignId = str
PathLike = Union[str, Path]

@dataclass
class Campaign:
    """
    A high-level scientific objective.

    Examples:
        id: "PHASE0_SANDBOX"
        name: "Phase 0 Dose Response Sandbox"
        objective: "Learn viability curves for U2OS and HepG2 under stressors"
        primary_readout: "viability"
        workflows: ["WF_PHASE0_DR_V1"]
    """

    id: CampaignId
    name: str
    objective: str
    primary_readout: str
    workflows: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _canonicalize_experiment_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize an experiment table into a canonical schema.

    Tries to be forgiving about upstream differences and supports both
    "raw plate" tables and your simulated experiment_history CSV.

    Canonical columns we try to ensure:
      - campaign_id
      - workflow_id (if present)
      - cell_line
      - compound
      - dose_uM
      - time_h
      - viability                (primary readout for Phase 0)
      - readout_name / readout_value (if using multi-readout rows)
      - replicate
      - plate_id, well_id, timestamp (if present)
    """
    if df.empty:
        return df.copy()

    df = df.copy()

    # ------------------------------------------------------------------
    # Campaign id
    # ------------------------------------------------------------------
    if "campaign_id" not in df.columns:
        # Fallback for older logs or ad hoc imports
        df["campaign_id"] = "UNSPECIFIED_CAMPAIGN"

    # ------------------------------------------------------------------
    # Workflow id
    # ------------------------------------------------------------------
    if "workflow_id" not in df.columns and "workflow" in df.columns:
        df = df.rename(columns={"workflow": "workflow_id"})

    # ------------------------------------------------------------------
    # Dose
    # ------------------------------------------------------------------
    if "dose_uM" in df.columns:
        dose_col = "dose_uM"
    elif "dose" in df.columns:
        df = df.rename(columns={"dose": "dose_uM"})
        dose_col = "dose_uM"
    else:
        # No dose column; create one so downstream code has something to hold
        df["dose_uM"] = pd.NA
        dose_col = "dose_uM"

    df[dose_col] = pd.to_numeric(df[dose_col], errors="coerce")

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------
    if "time_h" in df.columns:
        df["time_h"] = pd.to_numeric(df["time_h"], errors="coerce")

    # ------------------------------------------------------------------
    # Viability / primary readout
    # ------------------------------------------------------------------
    # Strategy:
    #   - If there is already a "viability" column, use it.
    #   - Else, if there is a (readout_name, readout_value) pair,
    #     and some rows have readout_name == "viability", then keep
    #     those rows and rename readout_value -> viability.
    #   - Else, create an empty viability column.
    if "viability" in df.columns:
        df["viability"] = pd.to_numeric(df["viability"], errors="coerce")

    elif "readout_value" in df.columns and "readout_name" in df.columns:
        # Populate viability column where readout_name is "viability"
        # But DO NOT drop other rows (we need them for multi-readout support)
        df["viability"] = pd.NA
        mask_viab = df["readout_name"] == "viability"
        if mask_viab.any():
            # Use loc to set values safely
            df.loc[mask_viab, "viability"] = pd.to_numeric(
                df.loc[mask_viab, "readout_value"], errors="coerce"
            )
    else:
        df["viability"] = pd.NA

    # ------------------------------------------------------------------
    # Replicate
    # ------------------------------------------------------------------
    if "replicate" not in df.columns:
        df["replicate"] = 0
    df["replicate"] = pd.to_numeric(df["replicate"], errors="coerce")

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ------------------------------------------------------------------
    # Stable column ordering for nicer CSVs and debugging
    # ------------------------------------------------------------------
    preferred_order = [
        "experiment_id",
        "campaign_id",
        "workflow_id",
        "plate_id",
        "well_id",
        "cell_line",
        "compound",
        "dose_uM",
        "time_h",
        "viability",
        "readout_name",
        "readout_value",
        "replicate",
        "timestamp",
    ]
    cols = [c for c in preferred_order if c in df.columns] + [
        c for c in df.columns if c not in preferred_order
    ]
    df = df[cols]

    return df


@dataclass
class ExperimentHistory:
    """
    Manages the dynamic state of experiments and campaigns.
    """
    experiments: pd.DataFrame = field(default_factory=pd.DataFrame)
    campaigns: Dict[CampaignId, Campaign] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Enforce invariants after construction.
        """
        if not self.experiments.empty:
            self.experiments = _canonicalize_experiment_frame(self.experiments)

    def add_campaign(self, campaign: Campaign) -> None:
        """Register a new campaign."""
        self.campaigns[campaign.id] = campaign

    def get_campaign(self, campaign_id: CampaignId) -> Optional[Campaign]:
        """Fetch a campaign by id, if present."""
        return self.campaigns.get(campaign_id)

    def list_campaigns(self) -> List[Campaign]:
        """Return all campaigns as a list, sorted by id."""
        return [self.campaigns[k] for k in sorted(self.campaigns.keys())]

    def add_experiments(self, df: pd.DataFrame) -> None:
        """
        Append new experimental records from the lab.
        """
        if df.empty:
            return

        df_norm = _canonicalize_experiment_frame(df)

        if self.experiments.empty:
            self.experiments = df_norm
        else:
            self.experiments = pd.concat(
                [self.experiments, df_norm], ignore_index=True
            )

    def get_experiments_for_campaign(self, campaign_id: CampaignId) -> pd.DataFrame:
        """
        Return all experiment records for a given campaign id.
        """
        if self.experiments.empty:
            return pd.DataFrame(columns=self.experiments.columns)

        if "campaign_id" not in self.experiments.columns:
            return pd.DataFrame(columns=self.experiments.columns)

        mask = self.experiments["campaign_id"] == campaign_id
        return self.experiments.loc[mask].copy()

    def get_experiments_for_workflow(self, workflow_id: str) -> pd.DataFrame:
        """
        Return all experiment records for a given workflow id.
        """
        if self.experiments.empty:
            return pd.DataFrame(columns=self.experiments.columns)

        if "workflow_id" not in self.experiments.columns:
            return pd.DataFrame(columns=self.experiments.columns)

        mask = self.experiments["workflow_id"] == workflow_id
        return self.experiments.loc[mask].copy()

    def get_slice(
        self,
        *,
        campaign_id: Optional[CampaignId] = None,
        cell_line: Optional[str] = None,
        compound: Optional[str] = None,
        time_h: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Filter experiments by a combination of keys.
        """
        df = self.experiments
        if df.empty:
            return df.copy()

        mask = pd.Series(True, index=df.index)

        if campaign_id is not None and "campaign_id" in df.columns:
            mask &= df["campaign_id"] == campaign_id

        if cell_line is not None and "cell_line" in df.columns:
            mask &= df["cell_line"] == cell_line

        if compound is not None and "compound" in df.columns:
            mask &= df["compound"] == compound

        if time_h is not None and "time_h" in df.columns:
            mask &= df["time_h"] == time_h

        return df.loc[mask].copy()
