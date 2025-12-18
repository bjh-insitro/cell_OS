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
    """
    # Condition identifiers
    cell_line: str
    compound: str
    dose_uM: float
    time_h: float
    assay: str
    position_tag: str

    # Summary statistics
    n_wells: int                # Number of replicates
    mean: float                 # Mean response (viability or morphology)
    std: float                  # Standard deviation
    sem: float                  # Standard error of mean
    cv: float                   # Coefficient of variation (std/mean)

    # Minimal distribution info (helps detect outliers without raw wells)
    min_val: float
    max_val: float

    # QC flags (agent must interpret these)
    n_failed: int               # Number of wells flagged as failed
    n_outliers: int             # Number detected as outliers (Z>3)

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
    """
    design_id: str
    conditions: List[ConditionSummary]
    wells_spent: int
    budget_remaining: int

    # Coarse QC flags (agent must infer structure)
    qc_flags: List[str] = field(default_factory=list)

    # Optional: if agent requests raw data (costs extra)
    raw_wells: Optional[List[Dict[str, Any]]] = None

    def summary_str(self) -> str:
        """One-line summary."""
        n_conditions = len(self.conditions)
        mean_cv = sum(c.cv for c in self.conditions) / max(n_conditions, 1)
        return (f"{n_conditions} conditions, {self.wells_spent} wells spent, "
                f"{self.budget_remaining} remaining, mean CV={mean_cv:.1%}")
