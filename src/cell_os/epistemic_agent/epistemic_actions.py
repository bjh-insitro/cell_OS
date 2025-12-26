"""
Epistemic action logic for calibration uncertainty reduction.

Generalizes mitigation pattern from "QC flag → mitigate" to
"calibration uncertainty → replicate vs expand".

Key principle: This tracks uncertainty about MEASUREMENT QUALITY (the ruler),
not biological parameters (IC50, mechanism). Uses calibration_entropy_bits
from BeliefState as the uncertainty metric.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EpistemicAction(Enum):
    """Epistemic actions for calibration uncertainty reduction."""
    REPLICATE = "replicate"  # Reduce uncertainty by replicating previous proposal
    EXPAND = "expand"        # Advance exploration (normal policy)
    CALIBRATE = "calibrate"  # Run control-only calibration plate to reduce measurement uncertainty
    NONE = "none"            # No epistemic action needed


@dataclass
class EpistemicContext:
    """Context for pending epistemic action.

    Tracks the state needed to execute epistemic action at cycle k+1
    after uncertainty check at cycle k.
    """
    cycle_flagged: int                  # Which cycle triggered the action
    uncertainty_before: float           # Calibration uncertainty before action (bits)
    action: EpistemicAction             # Chosen action (REPLICATE/EXPAND)
    previous_proposal: Any              # Proposal from cycle that triggered action
    previous_observation: Any           # Observation from cycle that triggered action
    rationale: str                      # Why this action was chosen
    consecutive_replications: int = 0   # Count of consecutive REPLICATE actions


def compute_epistemic_reward(
    action: EpistemicAction,
    uncertainty_before: float,
    uncertainty_after: float,
    cost_wells: int
) -> float:
    """
    Compute epistemic reward: uncertainty reduction per plate-equivalent cost.

    Formula:
        reward = (uncertainty_before - uncertainty_after) / (cost_wells / 96.0)

    Positive reward: action reduced calibration uncertainty
    Negative reward: action increased uncertainty (e.g., expansion added confounding)
    Zero cost: returns 0.0 (safety check)

    Args:
        action: Epistemic action taken
        uncertainty_before: Calibration uncertainty before action (bits)
        uncertainty_after: Calibration uncertainty after action (bits)
        cost_wells: Action cost in wells

    Returns:
        Reward in bits per plate-equivalent
    """
    if cost_wells == 0:
        return 0.0

    cost_plates = cost_wells / 96.0
    delta_uncertainty = uncertainty_before - uncertainty_after
    reward = delta_uncertainty / cost_plates

    return reward
