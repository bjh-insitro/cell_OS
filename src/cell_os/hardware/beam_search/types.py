"""
Type definitions for beam search.

Dataclasses for nodes, results, and episode tracking.
"""

from dataclasses import dataclass
from typing import List, Optional, Set

from ..episode import Action, Policy, EpisodeReceipt
from ...epistemic_agent.governance import Blocker
from .action_bias import ActionIntent


@dataclass
class PrefixRolloutResult:
    """Result of prefix rollout to current timestep."""
    viability: float
    actin_fold: float
    classifier_margin: float  # top1_score - top2_score from Phase5 classifier
    predicted_axis: Optional[str]
    washout_count: int
    feed_count: int
    # Full state for debugging
    actin_struct: float
    baseline_actin: float

    # NEW: Belief state (Bayesian posterior + calibration)
    mito_fold: float = 1.0
    er_fold: float = 1.0
    posterior_top_prob: float = 0.0
    posterior_margin: float = 0.0
    nuisance_fraction: float = 0.0  # v2: stores nuisance_probability (observation-aware)
    calibrated_confidence: float = 0.0

    # Forensics: nuisance model components
    nuisance_mean_shift_mag: float = 0.0  # ||mean_shift||
    nuisance_var_inflation: float = 0.0   # Total variance inflation

    # CAUSAL ATTRIBUTION: Full posterior for split-ledger accounting
    posterior: Optional[object] = None  # MechanismPosterior object
    attribution_source: Optional[str] = None  # "evidence" | "nuisance_reweight" | "both" | "none"


@dataclass
class BeamNode:
    """
    Node in beam search.

    Stores:
    - Current timestep
    - Action sequence so far
    - Intervention counts
    - Current observations (viability, readouts)
    - Exploration heuristic score (for beam ranking, not terminal reward)
    - Optional terminal commit utility (for early COMMIT nodes)
    """
    t_step: int  # 0..n_steps
    schedule: List[Action]

    # Action semantics
    action_type: str = "CONTINUE"  # "CONTINUE", "COMMIT", or "NO_DETECTION"
    is_terminal: bool = False

    # Constraint tracking
    washout_count: int = 0
    feed_count: int = 0

    # Current state (from prefix rollout)
    viability_current: float = 1.0
    actin_fold_current: float = 1.0

    # Exploration proxy (Phase5 classifier margin: top1 - top2)
    confidence_margin_current: float = 0.0

    # Reality layer / belief state summaries (populated in rollout_prefix)
    posterior_top_prob_current: float = 0.0
    posterior_margin_current: float = 0.0
    nuisance_frac_current: float = 0.0
    calibrated_confidence_current: float = 0.0
    predicted_axis_current: str = "UNKNOWN"

    # Forensics: nuisance components
    nuisance_mean_shift_mag_current: float = 0.0
    nuisance_var_inflation_current: float = 0.0

    # Heuristic score for beam ranking (NON-TERMINAL nodes)
    heuristic_score: float = 0.0

    # Terminal utilities (different for COMMIT vs NO_DETECTION)
    commit_utility: Optional[float] = None
    commit_target: Optional[str] = None
    no_detection_utility: Optional[float] = None

    # Terminal reward (legacy path: only set at t=n_steps)
    terminal_reward: Optional[float] = None

    # For debugging
    dominated: bool = False


@dataclass
class NoCommitEpisode:
    """
    Track a single NO_COMMIT episode for cost-aware closed-loop analysis.

    An episode is a window from NO_COMMIT decision to resolution (commit/detection) or timeout.
    """
    episode_id: str  # Unique identifier
    t_start: int  # Timestep when NO_COMMIT fired
    blockers_start: Set[Blocker]  # Which blockers caused NO_COMMIT
    posterior_gap_start: float
    nuisance_gap_start: float

    # Actions taken to resolve (window of k steps)
    actions_taken: List[ActionIntent]  # Sequence of intents chosen
    costs_incurred: List[float]  # Cost per action

    # Outcome after k steps
    t_end: int
    blockers_end: Set[Blocker]  # Which blockers remain
    posterior_gap_end: float
    nuisance_gap_end: float

    # Derived metrics
    @property
    def total_cost(self) -> float:
        return sum(self.costs_incurred)

    @property
    def posterior_gap_reduction(self) -> float:
        return self.posterior_gap_start - self.posterior_gap_end

    @property
    def nuisance_gap_reduction(self) -> float:
        return self.nuisance_gap_start - self.nuisance_gap_end

    @property
    def gap_reduction_per_cost(self) -> float:
        """Primary KPI: information-optimal metric."""
        if self.total_cost == 0:
            return 0.0
        total_reduction = self.posterior_gap_reduction + self.nuisance_gap_reduction
        return total_reduction / self.total_cost

    @property
    def resolved(self) -> bool:
        """Did we resolve at least one blocker?"""
        return len(self.blockers_end) < len(self.blockers_start)


@dataclass
class BeamSearchResult:
    """Result of beam search."""
    best_schedule: List[Action]
    best_policy: Policy
    best_reward: float
    best_receipt: EpisodeReceipt

    # Diagnostics
    nodes_expanded: int
    nodes_pruned_death: int
    nodes_pruned_interventions: int
    nodes_pruned_dominated: int

    # Comparison to baseline
    smart_policy_reward: Optional[float] = None
    beats_smart: bool = False

    # Governance forensics (what the contract decided and why)
    governance_action: Optional[str] = None  # "COMMIT", "NO_COMMIT", "NO_DETECTION"
    governance_reason: Optional[str] = None
    governance_mechanism: Optional[str] = None  # Approved mechanism if COMMIT
    governance_posterior_top: Optional[float] = None
    governance_nuisance_prob: Optional[float] = None
    governance_evidence_strength: Optional[float] = None

    # Distance to commit tracking (closed-loop KPI)
    governance_posterior_gap: Optional[float] = None  # max(0, threshold - posterior_top)
    governance_nuisance_gap: Optional[float] = None  # max(0, nuisance - threshold)
