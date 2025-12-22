"""
Data schemas for epistemic agent interface.

Clean separation between what agent proposes and what world returns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class WellSpec:
    """Specification for a single well experiment.

    Agent proposes these without knowing plate positions or batch structure.
    """
    cell_line: str          # 'A549' or 'HepG2'
    compound: str           # Name from available compounds
    dose_uM: float          # Micromolar concentration
    time_h: float           # Hours post-treatment
    assay: str              # 'cell_painting' or 'ldh_cytotoxicity'
    position_tag: str       # 'edge', 'center', or 'any'


@dataclass
class Proposal:
    """Agent's experiment proposal."""
    design_id: str                  # Unique ID for this batch
    hypothesis: str                 # What is this testing? (for narration)
    wells: List[WellSpec]          # Batch of wells to run
    budget_limit: int               # Max wells agent thinks it has

    def __post_init__(self):
        """Validation."""
        if len(self.wells) > self.budget_limit:
            raise ValueError(f"Proposal exceeds budget: {len(self.wells)} > {self.budget_limit}")


@dataclass
class ConditionSummary:
    """Summary statistics for a unique experimental condition.

    Condition = unique (cell_line, compound, dose, time, assay, position_tag) tuple.
    Agent only sees aggregates, not raw well values.

    Aggregation transparency (Agent 3 hardening):
    - n_wells_total: All wells for this condition (before any filtering)
    - n_wells_used: Wells that contributed to mean/std (after filtering)
    - n_wells_dropped: Wells excluded from aggregation
    - drop_reasons: Explicit counts by exclusion reason
    - aggregation_penalty_applied: Flag if CI should be wider due to drops
    """
    # Condition identifiers
    cell_line: str
    compound: str
    dose_uM: float
    time_h: float
    assay: str
    position_tag: str

    # Summary statistics (scalar convenience)
    n_wells: int                # DEPRECATED: use n_wells_total
    mean: float                 # Mean response (scalar: average of all morphology channels)
    std: float                  # Standard deviation
    sem: float                  # Standard error of mean
    cv: float                   # Coefficient of variation (std/mean)

    # Minimal distribution info (helps detect outliers without raw wells)
    min_val: float
    max_val: float

    # Multivariate features (morphology channels)
    # Agent can discover channel-specific effects, edge artifacts, compound signatures
    feature_means: Dict[str, float]  # {'er': 0.98, 'mito': 1.02, 'nucleus': 1.01, ...}
    feature_stds: Dict[str, float]   # Per-channel variability

    # QC flags (agent must interpret these)
    n_failed: int               # Number of wells flagged as failed
    n_outliers: int             # Number detected as outliers (Z>3)

    # Agent 3: Aggregation transparency (explicit information loss tracking)
    n_wells_total: int = 0              # All wells measured (before filtering)
    n_wells_used: int = 0               # Wells used in mean/std computation
    n_wells_dropped: int = 0            # Wells excluded from aggregation
    drop_reasons: Dict[str, int] = field(default_factory=dict)  # {'zscore_outlier': 3, 'qc_failed': 1}
    aggregation_penalty_applied: bool = False  # True if drops widened CI
    mad: Optional[float] = None         # Median absolute deviation (robust dispersion metric)
    iqr: Optional[float] = None         # Interquartile range (robust dispersion metric)

    # Agent 2: Canonical representation (prevents aggregation races)
    # These are the ACTUAL grouping keys (integers, no floats)
    # dose_uM and time_h above are derived from these for backward compat
    canonical_dose_nM: Optional[int] = None    # Integer nanomolar (1000 nM = 1 µM)
    canonical_time_min: Optional[int] = None   # Integer minutes (60 min = 1 h)

    @property
    def condition_key(self) -> tuple:
        """Unique key for this condition."""
        return (self.cell_line, self.compound, self.dose_uM,
                self.time_h, self.assay, self.position_tag)

    def __str__(self) -> str:
        """Human-readable description."""
        return (f"{self.cell_line}/{self.compound}@{self.dose_uM}µM/"
                f"{self.time_h}h/{self.assay}/{self.position_tag}")


@dataclass
class Observation:
    """World's response to agent's proposal.

    Contains only summary statistics and coarse QC flags.
    No raw well values, no internal simulator parameters.

    Agent 3 hardening:
    - aggregation_strategy: How summaries were produced (transparency requirement)
    """
    design_id: str
    conditions: List[ConditionSummary]
    wells_spent: int
    budget_remaining: int

    # Coarse QC flags (agent must infer structure)
    qc_flags: List[str] = field(default_factory=list)

    # Agent 3: Strategy transparency (same data + different strategy = different Observation)
    aggregation_strategy: str = "default_per_channel"

    # Cell line normalization mode (Agent 4: Nuisance Control)
    # none: Raw values (agent must discover cell line confound)
    # fold_change: Normalize by cell line baseline (removes 77% variance)
    # zscore: Standardize by vehicle statistics (requires vehicle controls)
    normalization_mode: str = "none"

    # Cell line normalization metadata (transparency)
    normalization_metadata: Optional[Dict[str, Any]] = None

    # Agent 2: Near-duplicate detection (conditions that merged due to canonicalization)
    # List of diagnostic events where multiple raw (dose, time) pairs collapsed to same key
    near_duplicate_merges: List[Dict[str, Any]] = field(default_factory=list)

    # Execution integrity state from QC checks (plate map errors, dose inversions, etc.)
    # Produced at aggregation boundary, consumed by BeliefState
    # This is QC infrastructure output, not agent-facing data
    execution_integrity: Optional['ExecutionIntegrityState'] = None  # Forward reference to avoid circular import

    # Optional: if agent requests raw data (costs extra)
    raw_wells: Optional[List[Dict[str, Any]]] = None

    def summary_str(self) -> str:
        """One-line summary."""
        n_conditions = len(self.conditions)
        mean_cv = sum(c.cv for c in self.conditions) / max(n_conditions, 1)
        return (f"{n_conditions} conditions, {self.wells_spent} wells spent, "
                f"{self.budget_remaining} remaining, mean CV={mean_cv:.1%}")
