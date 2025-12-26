"""
Expected Information Value (EIV) scoring for action selection.

This module implements decision-theoretic action selection for the epistemic agent.
The agent chooses between CALIBRATE, EXPLORE, and MITIGATE based on EIV scores.

Design principles:
- No "if debt high then calibrate" rules
- Explicit cost/benefit analysis for each action
- Hysteresis to prevent oscillation
- Testable proxies for information value

The uncomfortable truth: most projects die from lying to themselves more convincingly.
This module forces explicit reasoning about action value, not vibes.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EIVParams:
    """Parameters for EIV scoring (tunable constants)."""
    # Uncertainty reduction weight
    k_uncertainty: float = 5.0  # Value per unit uncertainty reduced

    # Health debt reduction weight
    k_debt: float = 2.0  # Value per unit debt reduced
    target_debt: float = 2.0  # Debt target (debt above this is costly)

    # Cost weights
    k_plate: float = 1.0  # Cost per plate used
    k_time: float = 0.1  # Cost per cycle consumed
    k_replicates: float = 0.05  # Cost per replicate

    # Risk weights
    k_health_risk: float = 1.0  # Penalty for expected health risk

    # Hysteresis
    action_switch_penalty: float = 0.5  # Penalty for switching actions

    # Minimum gap between calibrations
    min_calibration_gap: int = 2  # Cycles


@dataclass
class ActionScore:
    """Score for a single action with breakdown."""
    action: str  # "CALIBRATE", "EXPLORE", "MITIGATE"
    value: float  # Expected value (benefit)
    cost: float  # Expected cost
    score: float  # Net score = value - cost
    breakdown: dict  # Components for debugging


def score_calibrate(
    calibration_uncertainty: float,
    health_debt: float,
    cycles_since_calibration: int,
    budget_remaining: int,
    params: EIVParams
) -> ActionScore:
    """
    Score calibration action using EIV proxy.

    EIV(calibrate) = expected reduction in uncertainty + expected reduction in debt - cost

    Args:
        calibration_uncertainty: Current calibration uncertainty [0, 1]
        health_debt: Current health debt (unitless, ~0-10)
        cycles_since_calibration: Cycles since last calibration
        budget_remaining: Remaining budget in wells
        params: EIV parameters

    Returns:
        ActionScore with value, cost, and net score
    """
    # Value component 1: Uncertainty reduction
    # Calibration reduces uncertainty by ~70% (varies with cleanliness, use conservative estimate)
    expected_uncertainty_reduction = calibration_uncertainty * 0.7
    value_uncertainty = params.k_uncertainty * expected_uncertainty_reduction

    # Value component 2: Health debt reduction
    # Calibration modestly reduces debt if calibration is clean (~30% decay)
    # Only valuable if debt is above target
    excess_debt = max(0, health_debt - params.target_debt)
    expected_debt_reduction = excess_debt * 0.3  # Conservative estimate
    value_debt = params.k_debt * expected_debt_reduction

    # Total value
    value = value_uncertainty + value_debt

    # Cost component: 1 plate (96 wells) + 1 cycle time
    cost_plates = params.k_plate * 1.0  # Always 1 plate for calibration
    cost_time = params.k_time * 1.0  # 1 cycle
    cost = cost_plates + cost_time

    # Penalty if calibrated too recently (avoid spam)
    if cycles_since_calibration < params.min_calibration_gap:
        cost += 10.0  # Large penalty to prevent back-to-back calibrations

    # Penalty if insufficient budget
    if budget_remaining < 96:
        cost += 100.0  # Cannot afford calibration

    score = value - cost

    breakdown = {
        "value_uncertainty": value_uncertainty,
        "value_debt": value_debt,
        "cost_plates": cost_plates,
        "cost_time": cost_time,
        "expected_uncertainty_reduction": expected_uncertainty_reduction,
        "expected_debt_reduction": expected_debt_reduction,
    }

    return ActionScore(
        action="CALIBRATE",
        value=value,
        cost=cost,
        score=score,
        breakdown=breakdown
    )


def score_explore(
    expected_epistemic_gain: float,
    expected_health_risk: float,
    expected_cost_wells: int,
    params: EIVParams
) -> ActionScore:
    """
    Score exploration action using EIV proxy.

    EIV(explore) = expected epistemic gain - expected health risk - cost

    Args:
        expected_epistemic_gain: Expected bits of information from exploration
        expected_health_risk: Expected health debt accumulation risk
        expected_cost_wells: Expected cost in wells
        params: EIV parameters

    Returns:
        ActionScore with value, cost, and net score
    """
    # Value: epistemic gain (already in bits)
    value = expected_epistemic_gain

    # Cost component 1: plates used
    cost_plates = params.k_plate * (expected_cost_wells / 96.0)

    # Cost component 2: health risk (expected debt accumulation)
    cost_health_risk = params.k_health_risk * expected_health_risk

    # Cost component 3: time
    cost_time = params.k_time * 1.0  # 1 cycle

    cost = cost_plates + cost_health_risk + cost_time

    score = value - cost

    breakdown = {
        "value_epistemic": value,
        "cost_plates": cost_plates,
        "cost_health_risk": cost_health_risk,
        "cost_time": cost_time,
        "expected_epistemic_gain": expected_epistemic_gain,
        "expected_health_risk": expected_health_risk,
    }

    return ActionScore(
        action="EXPLORE",
        value=value,
        cost=cost,
        score=score,
        breakdown=breakdown
    )


def score_mitigate(
    health_debt: float,
    mitigation_action: str,
    expected_debt_reduction: float,
    expected_cost_wells: int,
    params: EIVParams
) -> ActionScore:
    """
    Score mitigation action using EIV proxy.

    EIV(mitigate) = expected debt reduction - cost

    Args:
        health_debt: Current health debt
        mitigation_action: Mitigation action type (e.g., "REPLATE")
        expected_debt_reduction: Expected debt reduction from mitigation
        expected_cost_wells: Expected cost in wells
        params: EIV parameters

    Returns:
        ActionScore with value, cost, and net score
    """
    # Value: debt reduction (only valuable if debt is high)
    excess_debt = max(0, health_debt - params.target_debt)
    # Scale value by how much debt is above target
    value = params.k_debt * expected_debt_reduction * (excess_debt / max(1.0, health_debt))

    # Cost: plates used + time
    cost_plates = params.k_plate * (expected_cost_wells / 96.0)
    cost_time = params.k_time * 1.0
    cost = cost_plates + cost_time

    score = value - cost

    breakdown = {
        "value_debt": value,
        "cost_plates": cost_plates,
        "cost_time": cost_time,
        "expected_debt_reduction": expected_debt_reduction,
        "excess_debt": excess_debt,
    }

    return ActionScore(
        action=f"MITIGATE_{mitigation_action}",
        value=value,
        cost=cost,
        score=score,
        breakdown=breakdown
    )


def select_action_with_hysteresis(
    scores: list[ActionScore],
    last_action: Optional[str],
    params: EIVParams
) -> ActionScore:
    """
    Select best action with hysteresis to prevent oscillation.

    Hysteresis rule: If switching actions, require score gap > switch_penalty.

    Args:
        scores: List of ActionScore objects
        last_action: Previous action (None if first decision)
        params: EIV parameters

    Returns:
        Selected ActionScore
    """
    if not scores:
        raise ValueError("No actions to score")

    # Sort by score descending
    sorted_scores = sorted(scores, key=lambda s: s.score, reverse=True)
    best = sorted_scores[0]

    # If no previous action, return best
    if last_action is None:
        return best

    # If best action matches last action, return it (no penalty)
    if best.action == last_action:
        return best

    # If switching, apply hysteresis penalty
    # Check if best action score exceeds last action score + penalty
    last_score = next((s for s in scores if s.action == last_action), None)

    if last_score is not None:
        # Require best to beat last by at least switch_penalty
        if best.score < last_score.score + params.action_switch_penalty:
            # Gap not large enough, stick with last action
            return last_score

    # Gap is large enough or last action not found, switch
    return best
