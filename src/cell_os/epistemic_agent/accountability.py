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
