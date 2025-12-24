"""
Mitigation module: closed-loop QC response with epistemic rewards.

Implements minimal agent capability to:
1. Detect spatial QC flags (Moran's I spatial autocorrelation)
2. Choose mitigation action (REPLATE, REPLICATE, NONE)
3. Compute epistemic reward based on QC resolution

Key principles:
- Reward tied to QC resolution (not accuracy)
- Mitigation consumes full integer cycle (temporal provenance)
- Deterministic with seed (layout_seed for spatial variance)
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from .accountability import MitigationAction
from .schemas import Observation


@dataclass
class MitigationContext:
    """Context for pending mitigation action.

    Tracks the state needed to execute mitigation at cycle k+1
    after QC flag at cycle k.
    """
    cycle_flagged: int                  # Which cycle triggered the flag
    morans_i_before: float              # Moran's I before mitigation
    action: MitigationAction            # Chosen action (REPLATE/REPLICATE/NONE)
    previous_proposal: Any              # Proposal that triggered flag
    rationale: str                      # Why this action was chosen
    qc_details_before: Dict[str, Any]   # Full QC diagnostic context


def get_spatial_qc_summary(observation: Observation) -> Tuple[bool, float, Dict[str, Any]]:
    """Extract spatial QC summary from observation.

    Args:
        observation: Observation with potential QC flags

    Returns:
        (flagged, max_morans_i, details) tuple:
        - flagged: True if any spatial QC flag detected
        - max_morans_i: Maximum Moran's I across all conditions
        - details: Dict with per-condition QC metrics
    """
    # Check if observation has qc_struct with spatial_autocorrelation
    if not hasattr(observation, 'qc_struct') or not observation.qc_struct:
        return (False, 0.0, {})

    spatial_qc = observation.qc_struct.get('spatial_autocorrelation', {})
    if not spatial_qc:
        return (False, 0.0, {})

    # Extract Moran's I values from spatial QC
    # spatial_qc is keyed by channel (e.g., "morphology.nucleus")
    morans_i_values = []
    flagged_channels = []

    for channel_key, channel_metrics in spatial_qc.items():
        if isinstance(channel_metrics, dict):
            # Check for flagged status first
            if channel_metrics.get('flagged', False):
                flagged_channels.append(channel_key)

            # Extract Moran's I if present
            if 'morans_i' in channel_metrics:
                morans_i = channel_metrics['morans_i']
                morans_i_values.append(morans_i)

    # Determine if flagged
    flagged = len(flagged_channels) > 0
    max_morans_i = max(morans_i_values) if morans_i_values else 0.0

    details = {
        'morans_i_values': morans_i_values,
        'max_morans_i': max_morans_i,
        'flagged_channels': flagged_channels,
        'n_channels': len(spatial_qc),
        'n_flagged': len(flagged_channels),
    }

    return (flagged, max_morans_i, details)


def compute_mitigation_reward(
    action: MitigationAction,
    morans_i_before: float,
    morans_i_after: Optional[float],
    flagged_before: bool,
    flagged_after: bool,
    cost: float
) -> float:
    """Compute epistemic reward for mitigation action.

    Reward structure:
    - Resolve QC flag: +10 points (epistemic value of clean data)
    - Fail to resolve: -6 points (wasted resources)
    - Ignore when flagged: -8 points (self-deception penalty)
    - Action cost: -2 * cost (in plate units)
    - Bonus: +2 * delta(Moran's I) for variance reduction

    Args:
        action: Mitigation action taken
        morans_i_before: Moran's I before mitigation
        morans_i_after: Moran's I after mitigation (None if not executed)
        flagged_before: Was QC flagged before?
        flagged_after: Was QC flagged after?
        cost: Action cost in plate units (wells / 96)

    Returns:
        Reward in points (higher = better epistemic outcome)
    """
    if flagged_before:
        # Case 1: QC was flagged, agent took action
        if action == MitigationAction.REPLATE:
            if flagged_after:
                # REPLATE failed to resolve → wasted resources
                base_reward = -6 - 2 * cost
            else:
                # REPLATE resolved QC → epistemic value
                base_reward = 10 - 2 * cost

        elif action == MitigationAction.REPLICATE:
            if flagged_after:
                # REPLICATE failed to resolve → partial value
                base_reward = -3 - 2 * cost
            else:
                # REPLICATE resolved QC → epistemic value
                base_reward = 8 - 2 * cost

        elif action == MitigationAction.NONE:
            # Ignored flag → self-deception penalty
            base_reward = -8

        else:
            base_reward = 0

    else:
        # Case 2: QC was not flagged
        if action in {MitigationAction.REPLATE, MitigationAction.REPLICATE}:
            # Unnecessary mitigation → wasted resources
            base_reward = -4 - 2 * cost
        else:
            # Correctly proceeded → no penalty
            base_reward = 0

    # Bonus: Variance reduction (independent of flag resolution)
    # Reward reduction in spatial autocorrelation even if flag persists
    bonus = 0.0
    if morans_i_after is not None and morans_i_before > morans_i_after:
        delta_i = morans_i_before - morans_i_after
        bonus = 2.0 * delta_i  # 2 points per 0.1 reduction in Moran's I

    return base_reward + bonus
