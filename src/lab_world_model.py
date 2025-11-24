"""
lab_world_model.py

Real world state representation for cell_OS.

This file defines the objects that describe the physical lab and its history:
- cell lines and assays
- workflows and unit operations
- pricing and cost-related tables
- campaigns and experiments
- links to inference artifacts (posteriors)

It does NOT define any simulation logic and does NOT fit models.
Modeling products live in `posteriors.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from src.posteriors import DoseResponsePosterior


# Simple aliases for readability
CampaignId = str
PathLike = Union[str, Path]


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


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
    #   - If there's already a "viability" column, use it.
    #   - Else, if there is a (readout_name, readout_value) pair,
    #     and some rows have readout_name == "viability", then keep
    #     those rows and rename readout_value -> viability.
    #   - Else, leave viability as NaN.
    if "viability" in df.columns:
        df["viability"] = pd.to_numeric(df["viability"], errors="coerce")

    elif "readout_value" in df.columns and "readout_name" in df.columns:
        mask_viab = df["readout_name"] == "viability"
        if mask_viab.any():
            df = df.loc[mask_viab].copy()
            df = df.rename(columns={"readout_value": "viability"})
            df["viability"] = pd.to_numeric(df["viability"], errors="coerce")
        else:
            # No explicit viability readout; keep table as-is
            pass
    else:
        # No viability or readout_value; create an empty viability column
        df["viability"] = pd.NA

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df


# ----------------------------------------------------------------------
# Core objects
# ----------------------------------------------------------------------


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


@dataclass
class LabWorldModel:
    """
    Real world state for cell_OS.

    This is the shared substrate that both:
    - Phase 0 (modeling) and
    - Phase 1 (acquisition, planning)

    should talk to.

    It separates three kinds of information:

    1. Static knowledge:
        - cell_lines: cell line metadata (from cell_line_database)
        - assays: assay definitions and limits of detection
        - workflows: workflow catalog (graph of unit operations)
        - pricing: economic information (from pricing.yaml and related tables)

    2. Dynamic state:
        - campaigns: known campaigns and their goals
        - experiments: log of real experiments, typically one row per well or plate

    3. Beliefs about the world:
        - posteriors: statistical inference artifacts, keyed by campaign
    """

    # Static knowledge
    cell_lines: pd.DataFrame = field(default_factory=pd.DataFrame)
    assays: pd.DataFrame = field(default_factory=pd.DataFrame)
    workflows: pd.DataFrame = field(default_factory=pd.DataFrame)
    pricing: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Dynamic state
    campaigns: Dict[CampaignId, Campaign] = field(default_factory=dict)
    experiments: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Beliefs (modeling products)
    posteriors: Dict[CampaignId, DoseResponsePosterior] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> "LabWorldModel":
        """Return an empty world model with no knowledge or experiments."""
        return cls()

    @classmethod
    def from_static_tables(
        cls,
        cell_lines: Optional[pd.DataFrame] = None,
        assays: Optional[pd.DataFrame] = None,
        workflows: Optional[pd.DataFrame] = None,
        pricing: Optional[pd.DataFrame] = None,
    ) -> "LabWorldModel":
        """
        Build a LabWorldModel from pre-computed static tables.

        Each argument is optional. Missing tables default to empty DataFrames.
        This is a convenient hook to connect to:
          - src.cell_line_database
          - src.workflows
          - src.inventory (pricing.yaml)
        without hard coupling those modules here.
        """
        return cls(
            cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
            assays=assays.copy() if assays is not None else pd.DataFrame(),
            workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
        )

    @classmethod
    def from_experiment_csv(
        cls,
        experiment_csv: PathLike,
        *,
        cell_lines: Optional[pd.DataFrame] = None,
        assays: Optional[pd.DataFrame] = None,
        workflows: Optional[pd.DataFrame] = None,
        pricing: Optional[pd.DataFrame] = None,
    ) -> "LabWorldModel":
        """
        Build a LabWorldModel directly from a single experiment CSV.

        This is ideal for loading your `results/experiment_history.csv` and
        then attaching posteriors on top.
        """
        p = Path(experiment_csv)
        if not p.exists():
            raise FileNotFoundError(f"Experiment CSV not found: {p}")

        if p.suffix.lower() != ".csv":
            raise ValueError(f"Unsupported experiment file type: {p.suffix}")

        raw = pd.read_csv(p)
        experiments = _canonicalize_experiment_frame(raw)

        return cls(
            cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
            assays=assays.copy() if assays is not None else pd.DataFrame(),
            workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
            experiments=experiments,
        )

    @classmethod
    def from_experiment_files(
        cls,
        experiment_files: Sequence[PathLike],
        *,
        cell_lines: Optional[pd.DataFrame] = None,
        assays: Optional[pd.DataFrame] = None,
        workflows: Optional[pd.DataFrame] = None,
        pricing: Optional[pd.DataFrame] = None,
    ) -> "LabWorldModel":
        """
        Build a LabWorldModel from multiple experiment CSVs.

        Each file is canonicalized and then concatenated.
        """
        frames: List[pd.DataFrame] = []
        for f in experiment_files:
            p = Path(f)
            if not p.exists():
                raise FileNotFoundError(f"Experiment file not found: {p}")
            if p.suffix.lower() != ".csv":
                raise ValueError(f"Unsupported experiment file type: {p.suffix}")
            raw = pd.read_csv(p)
            frames.append(_canonicalize_experiment_frame(raw))

        experiments = (
            pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        )

        return cls(
            cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
            assays=assays.copy() if assays is not None else pd.DataFrame(),
            workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
            experiments=experiments,
        )

    # ------------------------------------------------------------------
    # Campaign management
    # ------------------------------------------------------------------

    def add_campaign(self, campaign: Campaign) -> None:
        """Register a new campaign."""
        self.campaigns[campaign.id] = campaign

    def get_campaign(self, campaign_id: CampaignId) -> Optional[Campaign]:
        """Fetch a campaign by id, if present."""
        return self.campaigns.get(campaign_id)

    def list_campaigns(self) -> List[Campaign]:
        """Return all campaigns as a list, sorted by id."""
        return [self.campaigns[k] for k in sorted(self.campaigns.keys())]

    # ------------------------------------------------------------------
    # Experiment log
    # ------------------------------------------------------------------

    def add_experiments(self, df: pd.DataFrame) -> None:
        """
        Append new experimental records from the lab.

        Recommended columns (not enforced):
            ["experiment_id",
             "campaign_id",
             "workflow_id",
             "plate_id",
             "well_id",
             "cell_line",
             "compound",
             "dose_uM",
             "time_h",
             "readout_name",
             "readout_value",
             "viability",
             "replicate"]

        Incoming frames are canonicalized before being stored.
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

        If there are no experiments or no matching rows, returns an empty DataFrame.
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

    # ------------------------------------------------------------------
    # Static knowledge helpers
    # ------------------------------------------------------------------

    def get_cell_line(self, cell_line: str) -> Optional[pd.Series]:
        """
        Return metadata for a single cell line as a row, if present.

        Expects `cell_lines` to have a column named "cell_line" or "id".
        Uses "cell_line" if present, otherwise falls back to "id".
        """
        if self.cell_lines.empty:
            return None

        key_col = None
        if "cell_line" in self.cell_lines.columns:
            key_col = "cell_line"
        elif "id" in self.cell_lines.columns:
            key_col = "id"

        if key_col is None:
            return None

        subset = self.cell_lines[self.cell_lines[key_col] == cell_line]
        if subset.empty:
            return None

        return subset.iloc[0]

    def get_workflow_row(self, workflow_id: str) -> Optional[pd.Series]:
        """
        Return the row in `workflows` corresponding to the given workflow id.

        Expects a column named "workflow_id" or "id".
        """
        if self.workflows.empty:
            return None

        key_col = None
        if "workflow_id" in self.workflows.columns:
            key_col = "workflow_id"
        elif "id" in self.workflows.columns:
            key_col = "id"

        if key_col is None:
            return None

        subset = self.workflows[self.workflows[key_col] == workflow_id]
        if subset.empty:
            return None

        return subset.iloc[0]

    def get_workflow_cost(self, workflow_id: str) -> Optional[float]:
        """
        Return an estimated cost for a workflow if available.

        This method assumes that `workflows` has either:
          - a column "estimated_cost_usd", or
          - a column "cost_usd"

        If neither is present or the row is missing, returns None.
        """
        row = self.get_workflow_row(workflow_id)
        if row is None:
            return None

        for col in ("estimated_cost_usd", "cost_usd"):
            if col in row.index and pd.notna(row[col]):
                try:
                    return float(row[col])
                except (TypeError, ValueError):
                    return None

        return None

    # ------------------------------------------------------------------
    # Posterior attachment
    # ------------------------------------------------------------------

    def attach_posterior(
        self,
        campaign_id: CampaignId,
        posterior: DoseResponsePosterior,
    ) -> None:
        """
        Attach a modeling posterior (for example a DoseResponsePosterior)
        to a given campaign.
        """
        self.posteriors[campaign_id] = posterior

    def get_posterior(self, campaign_id: CampaignId) -> Optional[DoseResponsePosterior]:
        """
        Retrieve a posterior for a given campaign id, if present.
        """
        return self.posteriors.get(campaign_id)

    def build_dose_response_posterior(
        self,
        campaign_id: CampaignId,
        readout_name: str = "viability",
    ) -> DoseResponsePosterior:
        """
        Convenience helper: build a DoseResponsePosterior from this world
        and attach it under the given campaign id.

        This assumes DoseResponsePosterior exposes a constructor like:
            DoseResponsePosterior.from_world(world, campaign_id, readout_name=...)

        If the signature differs slightly in your code, adjust here.
        """
        df = self.get_experiments_for_campaign(campaign_id)
        if df.empty:
            raise ValueError(
                f"No experiments found for campaign {campaign_id!r}; "
                "cannot build dose-response posterior."
            )

        posterior = DoseResponsePosterior.from_world(
            world=self,
            campaign_id=campaign_id,
            readout_name=readout_name,
        )
        self.attach_posterior(campaign_id, posterior)
        return posterior
