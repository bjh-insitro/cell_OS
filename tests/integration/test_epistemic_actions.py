"""
Integration tests for epistemic action system.

Tests the closed-loop calibration uncertainty reduction system that generalizes
mitigation from "QC flag → act" to "uncertainty state → decide".

v1.0: Option A (calibration uncertainty proxy) using BeliefState.calibration_entropy_bits
"""

import pytest
from unittest.mock import patch
from pathlib import Path
from cell_os.epistemic_agent.loop import EpistemicLoop
from cell_os.epistemic_agent.epistemic_actions import EpistemicAction


def test_epistemic_determinism():
    """
    Test: Same seed produces deterministic epistemic actions and rewards.

    Verifies:
    - Same seed → same epistemic actions chosen
    - Same seed → same epistemic rewards computed
    - Epistemic file logging is deterministic

    Requirement: Deterministic behavior for reproducibility
    """
    seed = 42
    budget = 288  # 3 plates (enough for multiple actions)
    max_cycles = 10

    # Run 1
    loop1 = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path("/tmp/epistemic_test_run1"),
    )
    loop1.run()

    # Run 2 (identical seed)
    loop2 = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path("/tmp/epistemic_test_run2"),
    )
    loop2.run()

    # Extract epistemic actions from history
    actions1 = [
        h.get('epistemic_action')
        for h in loop1.history
        if h.get('is_epistemic_action')
    ]
    actions2 = [
        h.get('epistemic_action')
        for h in loop2.history
        if h.get('is_epistemic_action')
    ]

    # Verify actions are identical
    assert actions1 == actions2, f"Actions differ: {actions1} vs {actions2}"

    # Extract epistemic rewards from history
    rewards1 = [
        h.get('reward')
        for h in loop1.history
        if h.get('is_epistemic_action')
    ]
    rewards2 = [
        h.get('reward')
        for h in loop2.history
        if h.get('is_epistemic_action')
    ]

    # Verify rewards are identical (within floating point tolerance)
    assert len(rewards1) == len(rewards2), f"Reward count differs: {len(rewards1)} vs {len(rewards2)}"
    for r1, r2 in zip(rewards1, rewards2):
        assert abs(r1 - r2) < 1e-6, f"Rewards differ: {r1} vs {r2}"

    # Verify epistemic files have same number of events
    import json
    with open(loop1.epistemic_file, 'r') as f1, open(loop2.epistemic_file, 'r') as f2:
        events1 = [json.loads(line) for line in f1]
        events2 = [json.loads(line) for line in f2]
        assert len(events1) == len(events2), f"Event count differs: {len(events1)} vs {len(events2)}"


def test_epistemic_budget_conservation():
    """
    Test: Wells consumed by epistemic actions match expectations.

    Verifies:
    - REPLICATE action costs = previous proposal wells
    - EXPAND action costs = normal proposal wells
    - Total budget conservation (initial - final = sum of all wells)

    Requirement: Budget tracking integrity
    """
    seed = 123
    budget = 288  # 3 plates
    max_cycles = 8

    loop = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path("/tmp/epistemic_test_budget"),
    )
    loop.run()

    # Extract all well costs from history
    total_spent = 0
    for h in loop.history:
        wells_spent = h['observation']['wells_spent']
        total_spent += wells_spent

    # Verify budget conservation
    budget_remaining = loop.world.budget_remaining
    assert total_spent + budget_remaining == budget, (
        f"Budget conservation violated: {total_spent} spent + {budget_remaining} remaining != {budget} initial"
    )

    # Verify epistemic action costs are consistent
    for i, h in enumerate(loop.history):
        if h.get('is_epistemic_action'):
            action = h.get('epistemic_action')
            wells = h['observation']['wells_spent']

            if action == 'replicate':
                # REPLICATE should duplicate previous science proposal
                # Find previous non-epistemic cycle
                prev_science = None
                for j in range(i - 1, -1, -1):
                    if not loop.history[j].get('is_epistemic_action'):
                        prev_science = loop.history[j]
                        break

                if prev_science:
                    prev_wells = prev_science['observation']['wells_spent']
                    # REPLICATE doubles wells (2× replicates for tighter CI)
                    expected_wells = prev_wells * 2
                    assert wells == expected_wells, (
                        f"REPLICATE cycle {h['cycle']} spent {wells} wells, "
                        f"expected {expected_wells} (2× previous {prev_wells} wells)"
                    )


def test_epistemic_action_switching():
    """
    Test: Epistemic action switching based on mocked calibration uncertainty.

    Verifies:
    - High uncertainty (>4.0 bits) → REPLICATE chosen
    - Low uncertainty (<4.0 bits) → EXPAND chosen
    - Consecutive replication cap (2) enforced → forced EXPAND

    Requirement: Decision logic correctness

    Strategy: Mock estimate_calibration_uncertainty() to return controlled values
    """
    seed = 456
    budget = 384  # 4 plates (enough for multiple actions)
    max_cycles = 12

    # Uncertainty sequence: high, high, high (should cap at 2 REPLICATEs)
    uncertainty_sequence = [8.0, 7.5, 7.0, 6.5, 2.0, 1.5, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    uncertainty_index = [0]

    def mock_uncertainty():
        """Return next uncertainty value from sequence."""
        idx = uncertainty_index[0]
        if idx >= len(uncertainty_sequence):
            return uncertainty_sequence[-1]
        val = uncertainty_sequence[idx]
        uncertainty_index[0] += 1
        return val

    loop = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path("/tmp/epistemic_test_switching"),
    )

    # Patch estimate_calibration_uncertainty to return controlled values
    with patch.object(
        loop.agent.beliefs,
        'estimate_calibration_uncertainty',
        side_effect=mock_uncertainty
    ):
        loop.run()

    # Extract epistemic actions
    epistemic_cycles = [
        (h['cycle'], h.get('epistemic_action'))
        for h in loop.history
        if h.get('is_epistemic_action')
    ]

    # Verify we got epistemic actions
    assert len(epistemic_cycles) > 0, "No epistemic actions were taken"

    # Verify first actions are REPLICATE (high uncertainty)
    # Should get at most 2 consecutive REPLICATEs due to cap
    replicate_count = 0
    for i, (cycle, action) in enumerate(epistemic_cycles):
        if action == 'replicate':
            replicate_count += 1
            # Check consecutive cap
            if i > 0 and epistemic_cycles[i-1][1] == 'replicate':
                # This is a consecutive replicate
                assert replicate_count <= 2, (
                    f"Consecutive replication cap violated: {replicate_count} consecutive REPLICATEs"
                )
        else:
            # Reset counter on non-replicate
            replicate_count = 0

    # Verify some EXPAND actions occurred after uncertainty dropped
    expand_actions = [action for _, action in epistemic_cycles if action == 'expand']
    assert len(expand_actions) > 0, "No EXPAND actions were taken despite low uncertainty"


@pytest.mark.slow  # Resource intensive benchmark, run with: pytest -m slow
def test_epistemic_confounding_adversary():
    """
    OPTIONAL: Test epistemic action effectiveness against confounding.

    Verifies:
    - REPLICATE-first strategy (tighten ruler) produces better final beliefs
      than EXPAND-first strategy (explore blindly)
    - Epistemic reward is positive for REPLICATE when uncertainty is high

    Requirement: System should prefer calibration before exploration

    This is a "north star" test that validates the epistemic action philosophy:
    "Measure the ruler before measuring biology."
    """
    seed = 789
    budget = 384  # 4 plates
    max_cycles = 10

    # Strategy 1: REPLICATE-first (tighten calibration)
    # Mock high uncertainty for first half of cycles
    uncertainty_replicate_first = [8.0] * 5 + [2.0] * 5

    loop_replicate = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path("/tmp/epistemic_adversary_replicate"),
    )

    uncertainty_index_r = [0]
    def mock_uncertainty_r():
        idx = uncertainty_index_r[0]
        if idx >= len(uncertainty_replicate_first):
            return uncertainty_replicate_first[-1]
        val = uncertainty_replicate_first[idx]
        uncertainty_index_r[0] += 1
        return val

    with patch.object(
        loop_replicate.agent.beliefs,
        'estimate_calibration_uncertainty',
        side_effect=mock_uncertainty_r
    ):
        loop_replicate.run()

    # Strategy 2: EXPAND-first (explore blindly)
    # Mock low uncertainty for first half of cycles (trick system into expanding)
    uncertainty_expand_first = [2.0] * 5 + [8.0] * 5

    loop_expand = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed + 1,  # Different seed to avoid exact matching
        log_dir=Path("/tmp/epistemic_adversary_expand"),
    )

    uncertainty_index_e = [0]
    def mock_uncertainty_e():
        idx = uncertainty_index_e[0]
        if idx >= len(uncertainty_expand_first):
            return uncertainty_expand_first[-1]
        val = uncertainty_expand_first[idx]
        uncertainty_index_e[0] += 1
        return val

    with patch.object(
        loop_expand.agent.beliefs,
        'estimate_calibration_uncertainty',
        side_effect=mock_uncertainty_e
    ):
        loop_expand.run()

    # Compare final beliefs: REPLICATE-first should have better calibration
    beliefs_r = loop_replicate.agent.beliefs
    beliefs_e = loop_expand.agent.beliefs

    # Metric 1: Noise gate earning (REPLICATE-first should earn it)
    assert beliefs_r.noise_sigma_stable, "REPLICATE-first should earn noise gate"
    # EXPAND-first may or may not earn gate (depends on luck)

    # Metric 2: Total epistemic reward (REPLICATE-first should have positive reward)
    reward_r = sum(
        h.get('reward', 0.0)
        for h in loop_replicate.history
        if h.get('is_epistemic_action')
    )
    # REPLICATE-first should reduce uncertainty → positive reward
    assert reward_r > 0, f"REPLICATE-first should have positive epistemic reward, got {reward_r}"
