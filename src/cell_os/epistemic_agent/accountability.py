"""
Agent accountability: respond to QC flags or accrue epistemic debt.

This module enforces a constraint: when spatial autocorrelation is flagged,
the agent must take mitigation action (replate or replicate) or accept penalty.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any
import random

from .schemas import Proposal, WellSpec


class MitigationAction(Enum):
    """Actions the agent can take in response to flagged QC."""
    REPLATE = "replate"      # Same conditions, new spatial layout
    REPLICATE = "replicate"  # Increase replicates, same conditions
    NONE = "none"            # Proceed without mitigation (penalized)


@dataclass
class AccountabilityConfig:
    """Configuration for agent accountability to QC flags.

    Attributes:
        enabled: Whether accountability is enforced (default: False)
        spatial_key: Measurement channel to check (default: morphology.nucleus)
        penalty: Epistemic debt penalty for ignoring flags (default: 1.0)
    """
    enabled: bool = False
    spatial_key: str = "morphology.nucleus"
    penalty: float = 1.0


def requires_spatial_mitigation(qc_struct: Dict[str, Any], spatial_key: str) -> bool:
    """Check if spatial QC flag requires mitigation.

    Args:
        qc_struct: Structured QC data from observation
        spatial_key: Channel key to check (e.g., "morphology.nucleus")

    Returns:
        True if spatial autocorrelation is flagged for this channel
    """
    spatial_qc = qc_struct.get("spatial_autocorrelation", {})
    channel_diag = spatial_qc.get(spatial_key, {})
    return channel_diag.get("flagged", False)


def make_replate_proposal(
    previous_proposal: Proposal,
    layout_seed: int,
    reason: str = "spatial QC flag"
) -> Proposal:
    """Create a replate proposal: same conditions, different spatial layout.

    Args:
        previous_proposal: Original proposal to replate
        layout_seed: Seed for spatial layout RNG (world will use this for position assignment)
        reason: Human-readable reason for replate (for audit trail)

    Returns:
        New proposal with layout_seed set for different spatial mapping
    """
    # Create deterministic RNG for well shuffling
    # (Provides additional randomness on top of layout_seed)
    rng = random.Random(layout_seed)

    # Extract wells from previous proposal
    original_wells = previous_proposal.wells

    # Create a shuffled copy of wells
    # Strategy: preserve all well attributes but change implicit spatial ordering
    # Since WellSpec doesn't have explicit well_id assignment at this stage,
    # we shuffle the order in which wells are processed (spatial assignment happens in world)
    shuffled_wells = list(original_wells)
    rng.shuffle(shuffled_wells)

    # Create new proposal with shuffled wells and layout_seed
    from dataclasses import replace

    replate_proposal = replace(
        previous_proposal,
        design_id=f"{previous_proposal.design_id}_replate",
        hypothesis=f"MITIGATION: Replate due to {reason}. Original: {previous_proposal.hypothesis}",
        wells=shuffled_wells,
        layout_seed=layout_seed
    )

    return replate_proposal


def make_replicate_proposal(previous_proposal: Proposal) -> Proposal:
    """Create a replicate proposal: 2× replicates, same conditions.

    NOTE: This creates a proposal that MAY exceed remaining budget.
    Caller must use shrink_proposal_to_budget() to ensure budget compliance.

    Args:
        previous_proposal: Original proposal to replicate

    Returns:
        New proposal with doubled wells (2× replicates)
    """
    from dataclasses import replace

    # Double the wells list (2× replicates for all conditions)
    replicated_wells = previous_proposal.wells + previous_proposal.wells

    replicate_proposal = replace(
        previous_proposal,
        design_id=f"{previous_proposal.design_id}_replicate",
        hypothesis=f"Replicate mitigation: {previous_proposal.hypothesis}",
        wells=replicated_wells,
        budget_limit=previous_proposal.budget_limit  # Keep same budget limit
    )

    return replicate_proposal


def shrink_proposal_to_budget(proposal: Proposal, remaining_wells: int) -> Proposal | None:
    """Shrink proposal to fit remaining budget, or return None if impossible.

    Scaling algorithm (deterministic, preserves as much science as possible):
    1. If proposal fits: return as-is
    2. Else: reduce number of wells (reduces replicates/coverage)
    3. If budget < minimum feasible (e.g., <3 wells): return None

    For replicate proposals specifically: this effectively reduces the replication factor
    from 2× down to whatever fits, maintaining original conditions in order.

    Args:
        proposal: Proposal that may exceed budget
        remaining_wells: Actual remaining well budget

    Returns:
        Shrunk proposal that fits budget, or None if unsatisfiable

    Example:
        Original: 96 wells
        Replicate: 192 wells requested
        Remaining: 144 wells
        Shrunk: 144 wells (1.5× replication instead of 2×)
    """
    from dataclasses import replace

    requested_wells = len(proposal.wells)

    # Case 1: Fits perfectly
    if requested_wells <= remaining_wells:
        return proposal

    # Case 2: Budget too small for minimum science (arbitrary floor: 3 wells)
    # Prevents degenerate proposals that can't yield useful information
    MIN_WELLS = 3
    if remaining_wells < MIN_WELLS:
        return None

    # Case 3: Shrink by taking first N wells that fit
    # This preserves condition ordering and reduces replication factor
    shrunk_wells = proposal.wells[:remaining_wells]

    shrunk_proposal = replace(
        proposal,
        design_id=f"{proposal.design_id}_shrunk",
        hypothesis=f"{proposal.hypothesis} [BUDGET-CONSTRAINED: {requested_wells}→{remaining_wells} wells]",
        wells=shrunk_wells,
        budget_limit=remaining_wells
    )

    return shrunk_proposal
