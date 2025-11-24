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
from typing import Any, Dict, List, Optional

import pandas as pd

from src.posteriors import DoseResponsePosterior


# Simple alias for readability
CampaignId = str


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
             "replicate"]

        This method is intentionally simple and permissive. Validation can be
        added later once the schema is fully stabilized.
        """
        if df.empty:
            return

        if self.experiments.empty:
            self.experiments = df.copy()
        else:
            self.experiments = pd.concat(
                [self.experiments, df], ignore_index=True
            )

    def get_experiments_for_campaign(self, campaign_id: CampaignId) -> pd.DataFrame:
        """
        Return all experiment records for a given campaign id.

        If there are no experiments or no matching rows, returns an empty DataFrame.
        """
        if self.experiments.empty:
            return pd.DataFrame(columns=self.experiments.columns)

        mask = self.experiments.get("campaign_id") == campaign_id
        if mask is None:
            # No campaign_id column yet
            return pd.DataFrame(columns=self.experiments.columns)

        return self.experiments.loc[mask].copy()

    def get_experiments_for_workflow(self, workflow_id: str) -> pd.DataFrame:
        """
        Return all experiment records for a given workflow id.
        """
        if self.experiments.empty:
            return pd.DataFrame(columns=self.experiments.columns)

        mask = self.experiments.get("workflow_id") == workflow_id
        if mask is None:
            return pd.DataFrame(columns=self.experiments.columns)

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

    def attach_posterior(self, campaign_id: CampaignId, posterior: DoseResponsePosterior) -> None:
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
