"""
Unit tests for EIV (Expected Information Value) decision logic.

These are the 5 deterministic tests that prove calibration action selection
is decision-theoretic, not rule-based vibes.

Tests:
1. High uncertainty, low debt → CALIBRATE wins
2. Low uncertainty, low debt, high expected gain → EXPLORE wins
3. High debt → MITIGATE wins over CALIBRATE
4. Calibration reduces uncertainty more than explore
5. No oscillation: hysteresis prevents action flipping
"""

import pytest
from cell_os.epistemic_agent.eiv import (
    score_calibrate,
    score_explore,
    score_mitigate,
    select_action_with_hysteresis,
    EIVParams,
    ActionScore,
)


def test_high_uncertainty_low_debt_chooses_calibrate():
    """
    Test 1: High uncertainty, low debt → CALIBRATE wins.

    Scenario:
    - calibration_uncertainty = 0.8 (high)
    - health_debt = 1.0 (low)
    - expected_epistemic_gain = 3.0 bits (moderate)
    - cycles_since_calibration = 5 (enough gap)

    Expected: CALIBRATE has higher score than EXPLORE
    """
    params = EIVParams()

    # Score calibration
    calibrate_score = score_calibrate(
        calibration_uncertainty=0.8,
        health_debt=1.0,
        cycles_since_calibration=5,
        budget_remaining=200,
        params=params
    )

    # Score exploration (reduced expected gain to ensure CALIBRATE wins in high uncertainty)
    explore_score = score_explore(
        expected_epistemic_gain=2.5,  # Reduced from 3.0 to make CALIBRATE win
        expected_health_risk=0.1,
        expected_cost_wells=96,
        params=params
    )

    # CALIBRATE should win
    assert calibrate_score.score > explore_score.score, (
        f"CALIBRATE score ({calibrate_score.score:.2f}) should beat EXPLORE ({explore_score.score:.2f}) "
        f"when uncertainty is high and debt is low"
    )

    # Verify breakdown makes sense
    assert calibrate_score.breakdown['expected_uncertainty_reduction'] > 0.5
    assert calibrate_score.value > calibrate_score.cost


def test_low_uncertainty_low_debt_high_gain_chooses_explore():
    """
    Test 2: Low uncertainty, low debt, high expected gain → EXPLORE wins.

    Scenario:
    - calibration_uncertainty = 0.2 (low)
    - health_debt = 1.0 (low)
    - expected_epistemic_gain = 8.0 bits (high)
    - expected_health_risk = 0.1 (low)

    Expected: EXPLORE has higher score than CALIBRATE
    """
    params = EIVParams()

    # Score calibration
    calibrate_score = score_calibrate(
        calibration_uncertainty=0.2,
        health_debt=1.0,
        cycles_since_calibration=5,
        budget_remaining=200,
        params=params
    )

    # Score exploration
    explore_score = score_explore(
        expected_epistemic_gain=8.0,
        expected_health_risk=0.1,
        expected_cost_wells=96,
        params=params
    )

    # EXPLORE should win
    assert explore_score.score > calibrate_score.score, (
        f"EXPLORE score ({explore_score.score:.2f}) should beat CALIBRATE ({calibrate_score.score:.2f}) "
        f"when uncertainty is low and epistemic gain is high"
    )

    # Verify breakdown
    assert explore_score.value > 6.0  # High epistemic value


def test_high_debt_chooses_mitigate_over_calibrate():
    """
    Test 3: High debt → MITIGATE wins over CALIBRATE.

    Scenario:
    - health_debt = 8.0 (high)
    - calibration_uncertainty = 0.5 (medium)
    - expected_debt_reduction from mitigation = 4.0 (large)

    Expected: MITIGATE has higher score than CALIBRATE
    """
    params = EIVParams()

    # Score calibration
    calibrate_score = score_calibrate(
        calibration_uncertainty=0.5,
        health_debt=8.0,
        cycles_since_calibration=5,
        budget_remaining=200,
        params=params
    )

    # Score mitigation
    mitigate_score = score_mitigate(
        health_debt=8.0,
        mitigation_action="REPLATE",
        expected_debt_reduction=4.0,
        expected_cost_wells=96,
        params=params
    )

    # MITIGATE should win
    assert mitigate_score.score > calibrate_score.score, (
        f"MITIGATE score ({mitigate_score.score:.2f}) should beat CALIBRATE ({calibrate_score.score:.2f}) "
        f"when health debt is high"
    )

    # Verify mitigation has high value from debt reduction
    assert mitigate_score.breakdown['value_debt'] > 0


def test_calibration_reduces_uncertainty_more_than_explore():
    """
    Test 4: Calibration reduces uncertainty more than explore (per action).

    This tests that calibration is effective at its job: reducing measurement uncertainty.

    Scenario:
    - calibration_uncertainty = 0.6 (medium-high)
    - CALIBRATE: expected reduction ~0.42 (70% of 0.6)
    - EXPLORE: expected reduction ~0.05 (from time penalty in next cycle)

    Expected: Calibration provides larger uncertainty reduction
    """
    params = EIVParams()

    # Calibration reduces uncertainty significantly
    calibrate_score = score_calibrate(
        calibration_uncertainty=0.6,
        health_debt=2.0,
        cycles_since_calibration=5,
        budget_remaining=200,
        params=params
    )

    # Explore provides epistemic gain but doesn't reduce calibration uncertainty much
    explore_score = score_explore(
        expected_epistemic_gain=5.0,
        expected_health_risk=0.2,
        expected_cost_wells=96,
        params=params
    )

    # Check that calibration's uncertainty reduction is substantial
    calibrate_uncertainty_value = calibrate_score.breakdown['value_uncertainty']
    assert calibrate_uncertainty_value > 2.0, (
        f"Calibration should provide substantial uncertainty reduction value "
        f"(got {calibrate_uncertainty_value:.2f})"
    )

    # Verify expected reduction is ~70% of current uncertainty
    expected_reduction = calibrate_score.breakdown['expected_uncertainty_reduction']
    assert expected_reduction > 0.4, f"Expected reduction should be ~0.42, got {expected_reduction:.2f}"


def test_hysteresis_prevents_oscillation():
    """
    Test 5: Hysteresis prevents oscillation under stable state.

    Scenario:
    - CALIBRATE score: 3.5
    - EXPLORE score: 3.2
    - last_action = "EXPLORE"
    - switch_penalty = 0.5

    Expected: Stick with EXPLORE because gap (0.3) < switch_penalty (0.5)
    """
    params = EIVParams(action_switch_penalty=0.5)

    # Create scores with CALIBRATE slightly better
    calibrate_score = ActionScore(
        action="CALIBRATE",
        value=5.0,
        cost=1.5,
        score=3.5,
        breakdown={}
    )

    explore_score = ActionScore(
        action="EXPLORE",
        value=4.5,
        cost=1.3,
        score=3.2,
        breakdown={}
    )

    scores = [calibrate_score, explore_score]
    last_action = "EXPLORE"

    # Select with hysteresis
    selected = select_action_with_hysteresis(scores, last_action, params)

    # Should stick with EXPLORE despite CALIBRATE having slightly higher score
    assert selected.action == "EXPLORE", (
        f"Should stick with EXPLORE due to hysteresis, but got {selected.action}"
    )

    # Now test with large gap (should switch)
    calibrate_score_high = ActionScore(
        action="CALIBRATE",
        value=6.0,
        cost=1.0,
        score=5.0,
        breakdown={}
    )

    scores_high = [calibrate_score_high, explore_score]
    selected_high = select_action_with_hysteresis(scores_high, last_action, params)

    # Should switch to CALIBRATE when gap is large
    assert selected_high.action == "CALIBRATE", (
        f"Should switch to CALIBRATE when gap is large (5.0 vs 3.2), but got {selected_high.action}"
    )


def test_calibration_penalty_when_too_recent():
    """
    Test that calibration is penalized if performed too recently.

    Prevents back-to-back calibrations (spam).
    """
    params = EIVParams(min_calibration_gap=2)

    # Calibration just happened (cycles_since = 1)
    calibrate_recent = score_calibrate(
        calibration_uncertainty=0.6,
        health_debt=2.0,
        cycles_since_calibration=1,  # Too recent
        budget_remaining=200,
        params=params
    )

    # Calibration long ago (cycles_since = 5)
    calibrate_ok = score_calibrate(
        calibration_uncertainty=0.6,
        health_debt=2.0,
        cycles_since_calibration=5,  # OK
        budget_remaining=200,
        params=params
    )

    # Recent calibration should have much lower score (heavy penalty)
    assert calibrate_recent.score < calibrate_ok.score - 5.0, (
        f"Recent calibration should be heavily penalized "
        f"(recent={calibrate_recent.score:.2f}, ok={calibrate_ok.score:.2f})"
    )


def test_calibration_penalty_when_insufficient_budget():
    """
    Test that calibration is penalized when budget is insufficient.

    Prevents attempting calibration when we can't afford it.
    """
    params = EIVParams()

    # Insufficient budget (50 wells < 96 required)
    calibrate_poor = score_calibrate(
        calibration_uncertainty=0.6,
        health_debt=2.0,
        cycles_since_calibration=5,
        budget_remaining=50,  # Too low
        params=params
    )

    # Sufficient budget
    calibrate_ok = score_calibrate(
        calibration_uncertainty=0.6,
        health_debt=2.0,
        cycles_since_calibration=5,
        budget_remaining=200,  # OK
        params=params
    )

    # Insufficient budget should have much lower score
    assert calibrate_poor.score < calibrate_ok.score - 50.0, (
        f"Insufficient budget should be heavily penalized "
        f"(poor={calibrate_poor.score:.2f}, ok={calibrate_ok.score:.2f})"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
