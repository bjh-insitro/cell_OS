"""
Lab World Model package.
Real world state representation for cell_OS.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import pandas as pd

from cell_os.posteriors import DoseResponsePosterior

from .cell_registry import CellRegistry
from .resource_costs import ResourceCosts
from .workflow_index import WorkflowIndex
from .experiment_history import ExperimentHistory, Campaign, CampaignId, PathLike
from .resource_accounting import ResourceAccounting

__all__ = [
    "LabWorldModel",
    "Campaign",
    "CampaignId",
]

@dataclass
class LabWorldModel:
    """
    Real world state for cell_OS.
    
    Orchestrator that composes:
    - CellRegistry (static biological knowledge)
    - ResourceCosts (economic info)
    - WorkflowIndex (workflow definitions)
    - ExperimentHistory (dynamic state)
    - ResourceAccounting (cost calculations)
    
    And manages beliefs (posteriors).
    """
    
    # Components
    cell_registry: CellRegistry = field(default_factory=CellRegistry)
    resource_costs: ResourceCosts = field(default_factory=ResourceCosts)
    workflow_index: WorkflowIndex = field(default_factory=WorkflowIndex)
    experiment_history: ExperimentHistory = field(default_factory=ExperimentHistory)
    resource_accounting: ResourceAccounting = field(init=False)
    
    # Beliefs (modeling products) - kept here as it's the "mind" part
    posteriors: Dict[CampaignId, DoseResponsePosterior] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize components that depend on others."""
        self.resource_accounting = ResourceAccounting(resource_costs=self.resource_costs)

    # ------------------------------------------------------------------
    # Cost Accounting (Delegate to ResourceAccounting)
    # ------------------------------------------------------------------

    def compute_cost(self, usage_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute total cost and breakdown from a usage log.
        
        Args:
            usage_log: List of dicts with 'resource_id' and 'quantity'
            
        Returns:
            Dict with 'total_cost_usd' and 'breakdown'
        """
        return self.resource_accounting.aggregate_costs(usage_log)


    # ------------------------------------------------------------------
    # Properties for backward compatibility (delegation)
    # ------------------------------------------------------------------
    
    @property
    def cell_lines(self) -> pd.DataFrame:
        return self.cell_registry.cell_lines
    
    @cell_lines.setter
    def cell_lines(self, value: pd.DataFrame):
        self.cell_registry.cell_lines = value

    @property
    def assays(self) -> pd.DataFrame:
        return self.cell_registry.assays
    
    @assays.setter
    def assays(self, value: pd.DataFrame):
        self.cell_registry.assays = value

    @property
    def workflows(self) -> pd.DataFrame:
        return self.workflow_index.workflows
    
    @workflows.setter
    def workflows(self, value: pd.DataFrame):
        self.workflow_index.workflows = value

    @property
    def pricing(self) -> pd.DataFrame:
        return self.resource_costs.pricing
    
    @pricing.setter
    def pricing(self, value: pd.DataFrame):
        self.resource_costs.pricing = value

    @property
    def campaigns(self) -> Dict[CampaignId, Campaign]:
        return self.experiment_history.campaigns
    
    @campaigns.setter
    def campaigns(self, value: Dict[CampaignId, Campaign]):
        self.experiment_history.campaigns = value

    @property
    def experiments(self) -> pd.DataFrame:
        return self.experiment_history.experiments
    
    @experiments.setter
    def experiments(self, value: pd.DataFrame):
        self.experiment_history.experiments = value
        # Ensure canonicalization if set directly (though setter might bypass init check)
        # The component handles canonicalization in its post_init, but direct assignment 
        # to the dataframe attribute doesn't trigger that. 
        # However, the original LWM allowed direct assignment. 
        # Ideally we'd wrap this but for now direct assignment is what it is.
        pass

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
        """
        return cls(
            cell_registry=CellRegistry(
                cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
                assays=assays.copy() if assays is not None else pd.DataFrame(),
            ),
            workflow_index=WorkflowIndex(
                workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            ),
            resource_costs=ResourceCosts(
                pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
            ),
            experiment_history=ExperimentHistory()
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
        """
        p = Path(experiment_csv)
        if not p.exists():
            raise FileNotFoundError(f"Experiment CSV not found: {p}")

        if p.suffix.lower() != ".csv":
            raise ValueError(f"Unsupported experiment file type: {p.suffix}")

        raw = pd.read_csv(p)
        # Canonicalization happens inside ExperimentHistory
        
        return cls(
            cell_registry=CellRegistry(
                cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
                assays=assays.copy() if assays is not None else pd.DataFrame(),
            ),
            workflow_index=WorkflowIndex(
                workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            ),
            resource_costs=ResourceCosts(
                pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
            ),
            experiment_history=ExperimentHistory(experiments=raw)
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
        """
        # We can let ExperimentHistory handle this, or do it here.
        # Since ExperimentHistory takes a DF, let's concat here.
        # Actually, let's reuse the logic from legacy but adapt it.
        from .experiment_history import _canonicalize_experiment_frame
        
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
            cell_registry=CellRegistry(
                cell_lines=cell_lines.copy() if cell_lines is not None else pd.DataFrame(),
                assays=assays.copy() if assays is not None else pd.DataFrame(),
            ),
            workflow_index=WorkflowIndex(
                workflows=workflows.copy() if workflows is not None else pd.DataFrame(),
            ),
            resource_costs=ResourceCosts(
                pricing=pricing.copy() if pricing is not None else pd.DataFrame(),
            ),
            experiment_history=ExperimentHistory(experiments=experiments)
        )

    # ------------------------------------------------------------------
    # Campaign management (Delegate to ExperimentHistory)
    # ------------------------------------------------------------------

    def add_campaign(self, campaign: Campaign) -> None:
        self.experiment_history.add_campaign(campaign)

    def get_campaign(self, campaign_id: CampaignId) -> Optional[Campaign]:
        return self.experiment_history.get_campaign(campaign_id)

    def list_campaigns(self) -> List[Campaign]:
        return self.experiment_history.list_campaigns()

    # ------------------------------------------------------------------
    # Experiment log (Delegate to ExperimentHistory)
    # ------------------------------------------------------------------

    def add_experiments(self, df: pd.DataFrame) -> None:
        self.experiment_history.add_experiments(df)

    def get_experiments_for_campaign(self, campaign_id: CampaignId) -> pd.DataFrame:
        return self.experiment_history.get_experiments_for_campaign(campaign_id)

    def get_experiments_for_workflow(self, workflow_id: str) -> pd.DataFrame:
        return self.experiment_history.get_experiments_for_workflow(workflow_id)

    def get_slice(
        self,
        *,
        campaign_id: Optional[CampaignId] = None,
        cell_line: Optional[str] = None,
        compound: Optional[str] = None,
        time_h: Optional[float] = None,
    ) -> pd.DataFrame:
        return self.experiment_history.get_slice(
            campaign_id=campaign_id,
            cell_line=cell_line,
            compound=compound,
            time_h=time_h
        )

    # ------------------------------------------------------------------
    # Static knowledge helpers (Delegate to components)
    # ------------------------------------------------------------------

    def get_cell_line(self, cell_line: str) -> Optional[pd.Series]:
        return self.cell_registry.get_cell_line(cell_line)

    def get_workflow_row(self, workflow_id: str) -> Optional[pd.Series]:
        return self.workflow_index.get_workflow_row(workflow_id)

    def get_workflow_cost(self, workflow_id: str) -> Optional[float]:
        return self.workflow_index.get_workflow_cost(workflow_id)

    # ------------------------------------------------------------------
    # Posterior attachment (Keep in Orchestrator)
    # ------------------------------------------------------------------

    def attach_posterior(
        self,
        campaign_id: CampaignId,
        posterior: DoseResponsePosterior,
    ) -> None:
        self.posteriors[campaign_id] = posterior

    def get_posterior(self, campaign_id: CampaignId) -> Optional[DoseResponsePosterior]:
        return self.posteriors.get(campaign_id)

    def build_dose_response_posterior(
        self,
        campaign_id: CampaignId,
        readout_name: str = "viability",
    ) -> DoseResponsePosterior:
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
