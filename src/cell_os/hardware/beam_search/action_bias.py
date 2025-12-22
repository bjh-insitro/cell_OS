"""
Action intent classification and governance-driven biasing.

Maps actions to coarse intent categories and computes bias multipliers
based on governance blockers to prioritize actions that resolve issues.
"""

from enum import Enum
from typing import Set, Dict

from ..episode import Action
from ...epistemic_agent.governance import Blocker


class ActionIntent(str, Enum):
    """
    Coarse intent tags for actions.

    Used by governance-driven action biasing to prioritize actions that resolve blockers.
    """
    DISCRIMINATE = "DISCRIMINATE"  # Actions likely to separate mechanisms
    REDUCE_NUISANCE = "REDUCE_NUISANCE"  # Washout, wait, replicate, context reset
    AMPLIFY_SIGNAL = "AMPLIFY_SIGNAL"  # Increase dose, extend duration
    OBSERVE = "OBSERVE"  # Measure, readout at a timepoint


def classify_action_intent(action: Action, has_dosed: bool) -> ActionIntent:
    """
    Classify an action's coarse intent.

    This is not perfect taxonomy. It's consistent taxonomy.
    """
    # Washout = reduce nuisance (clear confounders)
    if action.washout:
        return ActionIntent.REDUCE_NUISANCE

    # Feed = reduce nuisance (refresh medium, reduce contact pressure artifacts)
    if action.feed:
        return ActionIntent.REDUCE_NUISANCE

    # No dose = observe (just measure current state)
    if action.dose_fraction == 0.0:
        return ActionIntent.OBSERVE

    # Higher dose after already dosing = amplify signal
    if has_dosed and action.dose_fraction > 0.5:
        return ActionIntent.AMPLIFY_SIGNAL

    # First dose or low dose = discriminate (establish baseline response)
    return ActionIntent.DISCRIMINATE


def action_intent_cost(intent: ActionIntent) -> float:
    """
    Cost model for action intents.

    Returns normalized cost (1.0 = baseline observation).
    These are constants for now, can be refined with empirical data later.

    Cost reflects:
      - TIME: How long does it take?
      - REAGENT: How expensive is it?
      - RISK: How much viability/quality risk?
    """
    costs = {
        ActionIntent.OBSERVE: 1.0,  # Baseline: just measure
        ActionIntent.REDUCE_NUISANCE: 1.5,  # Intervention (washout/feed) + measure
        ActionIntent.DISCRIMINATE: 2.0,  # Dose + measure + analysis
        ActionIntent.AMPLIFY_SIGNAL: 2.5,  # High dose + risk + measure
    }
    return costs[intent]


def compute_action_bias(
    blockers: Set[Blocker],
    evidence_strength: float,
) -> Dict[ActionIntent, float]:
    """
    Map governance blockers to action intent bias multipliers.

    Returns weight multipliers for each ActionIntent (1.0 = neutral, >1.0 = boost, <1.0 = downweight).

    Heuristics:
      - HIGH_NUISANCE → boost REDUCE_NUISANCE, downweight AMPLIFY_SIGNAL (don't make it worse)
      - LOW_POSTERIOR_TOP → boost DISCRIMINATE and OBSERVE
      - Both blockers → prioritize nuisance reduction first (confounded discrimination is useless)
    """
    if not blockers:
        # No blockers: neutral bias
        return {intent: 1.0 for intent in ActionIntent}

    bias = {intent: 1.0 for intent in ActionIntent}

    # Blocker: HIGH_NUISANCE
    if Blocker.HIGH_NUISANCE in blockers:
        bias[ActionIntent.REDUCE_NUISANCE] = 3.0  # Strong boost
        bias[ActionIntent.OBSERVE] = 1.5  # Moderate boost (observe after cleanup)
        bias[ActionIntent.AMPLIFY_SIGNAL] = 0.3  # Downweight (don't escalate into noise)
        bias[ActionIntent.DISCRIMINATE] = 0.5  # Downweight (confounded discrimination is misleading)

    # Blocker: LOW_POSTERIOR_TOP
    if Blocker.LOW_POSTERIOR_TOP in blockers:
        # If nuisance is ALSO high, prioritize nuisance first (already handled above)
        if Blocker.HIGH_NUISANCE not in blockers:
            bias[ActionIntent.DISCRIMINATE] = 2.5  # Strong boost
            bias[ActionIntent.OBSERVE] = 2.0  # Boost observation
            # If evidence is weak, might need signal amplification
            if evidence_strength < 0.5:
                bias[ActionIntent.AMPLIFY_SIGNAL] = 1.5

    return bias
