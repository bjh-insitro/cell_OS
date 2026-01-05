"""
New methods to add to BeamSearch class for calibrated confidence integration.

Add these methods to the BeamSearch class in beam_search.py:
1. _populate_node_from_prefix - Helper to populate node fields from rollout result
2. _compute_commit_utility - Compute terminal utility for COMMIT decisions
3. _expand_node - Complete replacement with COMMIT support
"""

# Method 1: Add this helper to BeamSearch class
def _populate_node_from_prefix(self, node, pr) -> None:
    """
    Populate BeamNode cached fields from a PrefixRolloutResult-like object.
    Keeps naming in one place to prevent nuisance_frac vs nuisance_fraction drift.
    """
    node.viability_current = pr.viability
    node.actin_fold_current = pr.actin_fold
    node.confidence_margin_current = pr.classifier_margin

    node.posterior_top_prob_current = pr.posterior_top_prob
    node.posterior_margin_current = pr.posterior_margin
    node.nuisance_frac_current = pr.nuisance_fraction
    node.calibrated_confidence_current = pr.calibrated_confidence
    node.predicted_axis_current = pr.predicted_axis


# Method 2: Add this utility method to BeamSearch class
def _compute_commit_utility(
    self,
    calibrated_conf: float,
    elapsed_time_h: float,
    ops_penalty: int,
    viability: float
) -> float:
    """
    Compute terminal utility for COMMIT decision.

    Separate from exploration heuristic. Answers:
    "Should we commit now, or keep exploring?"

    Does NOT use classifier_margin. Only calibrated confidence.

    Args:
        calibrated_conf: P(correct | belief_state) from calibrator
        elapsed_time_h: Time elapsed so far
        ops_penalty: Number of interventions used
        viability: Current viability (soft penalty for commit-by-death)

    Returns:
        Commit utility (higher = better to commit now)
    """
    # Weights (add to __init__ if not present)
    w_commit_conf = getattr(self, 'w_commit_conf', 5.0)
    w_commit_time = getattr(self, 'w_commit_time', 0.1)
    w_commit_ops = getattr(self, 'w_commit_ops', 0.05)
    w_commit_viability = getattr(self, 'w_commit_viability', 0.1)

    # Core: reward confident commits
    conf_reward = w_commit_conf * calibrated_conf

    # Penalize late commits (earlier better, if confident)
    time_penalty = w_commit_time * elapsed_time_h

    # Penalize expensive commits
    ops_cost = w_commit_ops * ops_penalty

    # Soft penalty for low viability (discourage commit-by-murder)
    viability_penalty = w_commit_viability * (1.0 - viability)

    commit_utility = conf_reward - time_penalty - ops_cost - viability_penalty

    return commit_utility


# Method 3: Complete replacement for _expand_node
# (See separate file for full implementation due to length)
