"""
Integration test for episode-level governance and system closure.

Tests that EpisodeSummary correctly tracks:
- Budget spending (wells, plates, calibration vs exploration)
- Epistemic learning (gain, variance reduction, gates)
- Health sacrifices (debt accumulation, mitigation timeline)

This is the "prevent death by 1000 locally-optimal choices" test.
"""

import json
from pathlib import Path
import pytest
from cell_os.epistemic_agent.loop import EpistemicLoop
from cell_os.epistemic_agent.episode_summary import EpisodeSummary


def test_episode_summary_generation():
    """Test that episode summary is generated and tracks spending/learning/sacrifices."""
    # Run short episode
    loop = EpistemicLoop(budget=192, max_cycles=5, seed=42)
    loop.run()

    # Verify episode summary was created
    assert loop.episode_summary is not None
    summary = loop.episode_summary

    # Check metadata
    assert summary.run_id == loop.run_id
    assert summary.seed == 42
    assert summary.cycles_completed > 0
    assert summary.start_time != ""
    assert summary.end_time != ""

    # Check spending section
    assert summary.spending.total_wells > 0
    assert summary.spending.total_plates > 0
    assert summary.spending.total_wells == (192 - loop.world.budget_remaining)
    assert summary.spending.total_plates == summary.spending.total_wells / 96.0

    # Check learning section
    # Should have positive epistemic gain (entropy reduced)
    assert summary.learning.total_gain_bits >= 0
    assert summary.learning.final_calibration_entropy >= 0

    # Check sacrifices section
    # Health debt should be tracked
    assert summary.sacrifices.health_debt_accumulated >= 0
    assert summary.sacrifices.health_debt_repaid >= 0

    # Check aggregate metrics computed
    assert summary.efficiency_bits_per_plate is not None
    assert summary.health_balance is not None
    assert summary.exploration_ratio is not None

    # Verify summary was written to file
    summary_file = loop.log_dir / f"{loop.run_id}_episode_summary.json"
    assert summary_file.exists()

    # Verify JSON is valid
    with open(summary_file, 'r') as f:
        summary_data = json.load(f)

    assert summary_data['run_id'] == loop.run_id
    assert 'spending' in summary_data
    assert 'learning' in summary_data
    assert 'sacrifices' in summary_data
    assert 'efficiency_bits_per_plate' in summary_data


def test_episode_summary_tracks_mitigation():
    """Test that episode summary captures mitigation timeline."""
    # Run with longer budget to allow mitigation triggers
    loop = EpistemicLoop(budget=384, max_cycles=10, seed=123)
    loop.run()

    summary = loop.episode_summary
    assert summary is not None

    # If any mitigation cycles occurred, they should be tracked
    # (Not guaranteed with seed, so check conditionally)
    if summary.sacrifices.mitigation_actions:
        assert len(summary.mitigation_timeline) > 0
        for event in summary.mitigation_timeline:
            assert event.cycle > 0
            assert event.action in ["REPLATE", "REPLICATE", "replicate", "expand"]
            assert event.cost_wells > 0


def test_episode_summary_tracks_gates():
    """Test that gates earned/lost are tracked in episode summary."""
    loop = EpistemicLoop(budget=192, max_cycles=5, seed=42)
    loop.run()

    summary = loop.episode_summary
    assert summary is not None

    # Gates should be tracked (may or may not be earned depending on seed)
    assert isinstance(summary.learning.gates_earned, list)
    assert isinstance(summary.learning.gates_lost, list)

    # If noise gate earned during episode, should appear in gates_earned
    if loop.agent.beliefs.noise_sigma_stable:
        # May or may not be in gates_earned depending on when it was earned
        # (Could have been earned before episode started in Cycle 0)
        pass


def test_health_debt_accumulation_and_decay():
    """Test that health debt accumulates from QC violations and decays with mitigation."""
    loop = EpistemicLoop(budget=192, max_cycles=5, seed=42)

    # Manually test health debt accumulation
    beliefs = loop.agent.beliefs

    # Initially zero
    assert beliefs.health_debt == 0.0
    assert len(beliefs.health_debt_history) == 0

    # Accumulate debt from QC violation
    debt_added = beliefs.accumulate_health_debt(
        morans_i=0.25,  # Excess over 0.15 threshold
        nuclei_cv=0.30,  # Excess over 0.20 threshold
    )

    assert debt_added > 0
    assert beliefs.health_debt > 0
    assert len(beliefs.health_debt_history) == 1

    # Check debt pressure
    pressure = beliefs.get_health_debt_pressure()
    assert pressure in ["low", "medium", "high"]

    # Decay debt (simulate high-quality run)
    repayment = beliefs.decay_health_debt(decay_rate=0.3, reason="high_quality_run")

    assert repayment > 0
    assert beliefs.health_debt < debt_added
    assert len(beliefs.health_debt_history) == 2


def test_episode_summary_budget_breakdown():
    """Test that episode summary correctly breaks down budget spending."""
    loop = EpistemicLoop(budget=384, max_cycles=8, seed=99)
    loop.run()

    summary = loop.episode_summary
    assert summary is not None

    # Budget breakdown should sum correctly
    wells_by_type = summary.spending.wells_by_action_type
    total_by_type = sum(wells_by_type.values())

    # Total should match actual spending
    assert total_by_type == summary.spending.total_wells

    # Calibration + exploration should also sum to total
    assert (summary.spending.calibration_wells + summary.spending.exploration_wells) == summary.spending.total_wells


def test_episode_summary_with_abort():
    """Test that episode summary handles aborted runs gracefully."""
    loop = EpistemicLoop(budget=48, max_cycles=1, seed=42)  # Very limited budget
    loop.run()

    summary = loop.episode_summary
    assert summary is not None

    # Should still have valid summary even if run was short
    assert summary.cycles_completed >= 0
    assert summary.spending.total_wells >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
