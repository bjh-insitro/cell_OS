"""
Regression test: Enforce integer, monotonic cycle semantics for mitigation.

This test ensures that mitigation uses proper integer cycle numbers and that
beliefs sees strictly monotonic cycle progression.

If this test fails, someone broke the temporal provenance invariant.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from cell_os.epistemic_agent.loop import EpistemicLoop
from cell_os.epistemic_agent.accountability import AccountabilityConfig
from cell_os.epistemic_agent.observation_aggregator import aggregate_observation


def force_spatial_qc_flag(observation):
    """Inject spatial QC flag into observation (deterministic for testing).

    Real spatial QC detection is probabilistic with partial plates.
    For cycle semantics tests, we need deterministic QC triggering.
    """
    if "spatial_autocorrelation" not in observation.qc_struct:
        observation.qc_struct["spatial_autocorrelation"] = {}

    observation.qc_struct["spatial_autocorrelation"]["morphology.nucleus"] = {
        "morans_i": 0.6,  # Strong spatial autocorrelation
        "z_score": 3.5,
        "p_value": 0.001,
        "flagged": True,
        "n_wells": 96
    }
    return observation


def test_mitigation_uses_integer_cycles():
    """Mitigation must use integer cycles, not floats.

    Enforces:
    1. All cycle numbers are integers
    2. Cycles are monotonically increasing
    3. Mitigation consumes cycle k+1 after flag at cycle k
    """

    # Patch aggregate_observation to inject QC flags
    original_aggregate = aggregate_observation

    def patched_aggregate(*args, **kwargs):
        obs = original_aggregate(*args, **kwargs)
        return force_spatial_qc_flag(obs)

    with patch('cell_os.epistemic_agent.loop.aggregate_observation', patched_aggregate):
        loop = EpistemicLoop(
            budget=96 * 3,
            max_cycles=5,
            log_dir=Path("results/test_cycle_invariants"),
            seed=999,
            strict_quality=False,
            strict_provenance=False
        )

        # Enable mitigation
        loop.agent.accountability = AccountabilityConfig(
            enabled=True,
            spatial_key="morphology.nucleus",
            penalty=8.0
        )

        # Run loop
        loop.run()

    # Parse mitigation log
    mitigation_events = []
    if loop.mitigation_file.exists():
        with open(loop.mitigation_file, 'r') as f:
            for line in f:
                mitigation_events.append(json.loads(line))

    # Assert: At least one mitigation event occurred
    assert len(mitigation_events) > 0, "Test setup failed: no mitigation triggered"

    # INVARIANT 1: All cycle numbers are integers
    for event in mitigation_events:
        cycle = event['cycle']
        assert isinstance(cycle, int), (
            f"Cycle must be int, got {type(cycle)}: {cycle}"
        )

        if 'flagged_cycle' in event:
            flagged_cycle = event['flagged_cycle']
            assert isinstance(flagged_cycle, int), (
                f"Flagged cycle must be int, got {type(flagged_cycle)}: {flagged_cycle}"
            )

    # INVARIANT 2: Cycles are monotonically increasing
    all_cycles = [event['cycle'] for event in mitigation_events]
    for i in range(1, len(all_cycles)):
        assert all_cycles[i] > all_cycles[i-1], (
            f"Non-monotonic cycles: {all_cycles[i]} after {all_cycles[i-1]}"
        )

    # INVARIANT 3: Mitigation cycle = flagged_cycle + 1 (or later)
    for event in mitigation_events:
        if event['cycle_type'] == 'mitigation' and 'flagged_cycle' in event:
            assert event['cycle'] > event['flagged_cycle'], (
                f"Mitigation cycle {event['cycle']} must be after "
                f"flagged cycle {event['flagged_cycle']}"
            )

    # INVARIANT 4: No float contamination in logs
    with open(loop.mitigation_file, 'r') as f:
        raw_text = f.read()
        # Check for common float patterns that would indicate subcycles
        assert '"cycle": 0.5' not in raw_text, "Found float cycle 0.5"
        assert '"cycle": 1.5' not in raw_text, "Found float cycle 1.5"
        assert '"cycle": 2.5' not in raw_text, "Found float cycle 2.5"

    print(f"\n✓ All {len(mitigation_events)} mitigation events use integer cycles")
    print(f"✓ Cycles: {all_cycles}")
    print(f"✓ No float contamination detected")


def test_beliefs_see_monotonic_integers():
    """Beliefs must receive strictly monotonic integer cycles.

    This test validates that begin_cycle() is called with proper integers
    and that mitigation doesn't violate temporal ordering.
    """

    # Patch aggregate_observation to inject QC flags
    original_aggregate = aggregate_observation

    def patched_aggregate(*args, **kwargs):
        obs = original_aggregate(*args, **kwargs)
        return force_spatial_qc_flag(obs)

    with patch('cell_os.epistemic_agent.loop.aggregate_observation', patched_aggregate):
        loop = EpistemicLoop(
            budget=96 * 3,
            max_cycles=3,
            log_dir=Path("results/test_beliefs_cycles"),
            seed=888,
            strict_quality=False,
            strict_provenance=False
        )

        loop.agent.accountability = AccountabilityConfig(
            enabled=True,
            spatial_key="morphology.nucleus",
            penalty=8.0
        )

        # Run loop (TypeError in begin_cycle() will catch violations)
        try:
            loop.run()
        except TypeError as e:
            if "Cycle must be int" in str(e):
                pytest.fail(f"Float cycle passed to beliefs: {e}")
            raise

    # If we get here, all cycles were integers
    print("\n✓ All cycles passed to beliefs were integers")
    print("✓ No TypeError from begin_cycle() guardrail")


def test_mitigation_cycle_sequence():
    """Test specific cycle sequence: science(k) → mitigation(k+1) → science(k+2)."""

    # Patch aggregate_observation to inject QC flags
    original_aggregate = aggregate_observation

    def patched_aggregate(*args, **kwargs):
        obs = original_aggregate(*args, **kwargs)
        return force_spatial_qc_flag(obs)

    with patch('cell_os.epistemic_agent.loop.aggregate_observation', patched_aggregate):
        loop = EpistemicLoop(
            budget=96 * 3,
            max_cycles=4,
            log_dir=Path("results/test_cycle_sequence"),
            seed=777,
            strict_quality=False,
            strict_provenance=False
        )

        loop.agent.accountability = AccountabilityConfig(
            enabled=True,
            spatial_key="morphology.nucleus",
            penalty=8.0
        )

        loop.run()

    # Check history for cycle sequence
    assert len(loop.history) >= 3, "Need at least 3 cycles for test"

    # Find first mitigation cycle
    mitigation_idx = None
    for i, h in enumerate(loop.history):
        if h.get('is_mitigation', False):
            mitigation_idx = i
            break

    if mitigation_idx is not None:
        # Verify sequence
        prev_cycle = loop.history[mitigation_idx - 1]['cycle']
        mitigation_cycle = loop.history[mitigation_idx]['cycle']
        next_cycle = loop.history[mitigation_idx + 1]['cycle'] if mitigation_idx + 1 < len(loop.history) else None

        # Mitigation should be prev_cycle + 1
        assert mitigation_cycle == prev_cycle + 1, (
            f"Mitigation cycle {mitigation_cycle} should be {prev_cycle + 1} "
            f"(flagged cycle + 1)"
        )

        if next_cycle is not None:
            # Next science should be mitigation_cycle + 1
            assert next_cycle == mitigation_cycle + 1, (
                f"Next cycle {next_cycle} should be {mitigation_cycle + 1} "
                f"(mitigation cycle + 1)"
            )

        print(f"\n✓ Cycle sequence verified:")
        print(f"  Science: {prev_cycle}")
        print(f"  Mitigation: {mitigation_cycle}")
        if next_cycle:
            print(f"  Science: {next_cycle}")
    else:
        pytest.fail("No mitigation cycle found despite forcing QC flags")


if __name__ == "__main__":
    print("Running mitigation cycle invariant tests...")

    print("\n" + "="*60)
    print("TEST 1: Integer cycles")
    print("="*60)
    test_mitigation_uses_integer_cycles()

    print("\n" + "="*60)
    print("TEST 2: Beliefs see monotonic integers")
    print("="*60)
    test_beliefs_see_monotonic_integers()

    print("\n" + "="*60)
    print("TEST 3: Cycle sequence")
    print("="*60)
    test_mitigation_cycle_sequence()

    print("\n" + "="*60)
    print("ALL CYCLE INVARIANT TESTS PASSED ✓")
    print("="*60)
