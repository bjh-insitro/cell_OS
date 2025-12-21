"""
Agent 1.5: Temporal Provenance Enforcement - Canary Tests

These tests prove that the silent bypass hole is closed.

Without these enforcement mechanisms, temporal causality checks could be
bypassed silently by omitting time metadata. These tests ensure that
such omissions crash loudly rather than silently corrupting the system.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.epistemic_agent.beliefs.state import BeliefState
from src.cell_os.epistemic_agent.beliefs.ledger import EvidenceEvent, append_events_jsonl
from src.cell_os.epistemic_agent.exceptions import TemporalProvenanceError, TemporalCausalityViolation
from src.cell_os.epistemic_agent.schemas import ConditionSummary


def test_missing_time_in_conditions_crashes():
    """
    Canary Test A: Missing time_h in conditions must crash.

    Without this enforcement, temporal causality would be bypassed silently.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Create fake observation with condition missing time_h
    class FakeCondition:
        def __init__(self, has_time):
            # Intentionally omit time_h or set to None
            if has_time:
                self.time_h = None  # Present but None (should crash)
            # else: no time_h attribute at all (should also crash)
            self.compound = "tunicamycin"
            self.cell_line = "A549"
            self.feature_means = {"er": 2.5}

    class FakeObservation:
        def __init__(self, conditions):
            self.conditions = conditions

    # Test 1: time_h = None
    obs_with_none = FakeObservation([FakeCondition(has_time=True)])

    try:
        beliefs.update(obs_with_none, cycle=1)
        raise AssertionError("Expected TemporalProvenanceError but none was raised (time_h=None)")
    except TemporalProvenanceError as e:
        assert "missing time_h" in e.message.lower() or "cannot derive evidence_time_h" in e.message.lower()
        assert e.missing_field == "time_h"
        assert e.context == "BeliefState.update()"

    # Test 2: No time_h attribute
    beliefs2 = BeliefState()
    beliefs2.begin_cycle(1)

    class ConditionNoTimeAttr:
        def __init__(self):
            # No time_h attribute at all
            self.compound = "DMSO"
            self.cell_line = "A549"
            self.feature_means = {}

    obs_no_attr = FakeObservation([ConditionNoTimeAttr()])

    try:
        beliefs2.update(obs_no_attr, cycle=1)
        raise AssertionError("Expected TemporalProvenanceError but none was raised (no time_h attr)")
    except TemporalProvenanceError as e:
        assert "missing time_h" in e.message.lower()
        assert e.missing_field == "time_h"


def test_empty_conditions_crashes():
    """
    Canary Test B: Empty conditions list must crash.

    Cannot derive evidence_time_h from zero conditions.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    class FakeObservation:
        def __init__(self):
            self.conditions = []  # Empty!

    obs = FakeObservation()

    try:
        beliefs.update(obs, cycle=1)
        raise AssertionError("Expected TemporalProvenanceError but none was raised (empty conditions)")
    except TemporalProvenanceError as e:
        assert "no conditions" in e.message.lower()
        assert e.missing_field == "time_h"
        assert e.context == "BeliefState.update()"


def test_retroactive_inference_still_blocked():
    """
    Canary Test C: Retroactive inference must still be blocked.

    This test ensures that the strengthened checks don't break
    existing temporal causality enforcement.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Manually set evidence_time_h (simulating that update() ran)
    beliefs._current_evidence_time_h = 12.0

    # Try to make a claim about 48h (future) - should fail
    try:
        beliefs._set(
            field_name="dose_curvature_seen",
            new_value=True,
            evidence={"test": "data"},
            supporting_conditions=["cond1"],
            claim_time_h=48.0,  # Future claim
        )
        raise AssertionError("Expected TemporalCausalityViolation but none was raised")
    except TemporalCausalityViolation as e:
        assert e.claim_time_h == 48.0
        assert e.evidence_time_h == 12.0
        assert e.violation_delta_h == 36.0


def test_claim_with_null_evidence_crashes():
    """
    Canary Test D: Making temporal claim without evidence_time_h must crash.

    This is the core bypass that Agent 1.5 closes.
    If evidence_time_h is None, we cannot enforce temporal causality.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Manually set _current_evidence_time_h to None (simulating bypass)
    beliefs._current_evidence_time_h = None

    # Try to make a temporal claim
    try:
        beliefs._set(
            field_name="time_dependence_seen",
            new_value=True,
            evidence={"signal": "test"},
            supporting_conditions=["test"],
            claim_time_h=24.0,  # Temporal claim
            evidence_time_h=None,  # Explicitly None
        )
        raise AssertionError("Expected TemporalProvenanceError but none was raised")
    except TemporalProvenanceError as e:
        assert "evidence_time_h is None" in e.message
        assert e.missing_field == "evidence_time_h"
        assert e.context == "BeliefState._set()"
        assert e.details["claim_time_h"] == 24.0


def test_ledger_refuses_null_evidence_time():
    """
    Canary Test E: Ledger must refuse to write belief_update with null evidence_time_h.

    This is the final backstop. Even if somehow a belief update occurs with
    null evidence_time_h, the ledger must refuse to write it.
    """
    import tempfile
    import os

    # Create temporary ledger file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        ledger_path = f.name

    try:
        # Create event with null evidence_time_h
        event = EvidenceEvent(
            cycle=1,
            belief="dose_curvature_seen",  # Regular belief (not gate event)
            prev=False,
            new=True,
            evidence={"test": "data"},
            supporting_conditions=["cond1"],
            note="Test event",
            evidence_time_h=None,  # NULL!
            claim_time_h=None,
        )

        # Try to write - should crash
        try:
            append_events_jsonl(ledger_path, [event])
            raise AssertionError("Expected TemporalProvenanceError but ledger wrote null evidence_time_h")
        except TemporalProvenanceError as e:
            assert "evidence_time_h=None" in e.message
            assert e.missing_field == "evidence_time_h"
            assert e.context == "ledger.append_events_jsonl()"

        # Verify file is empty (nothing written)
        with open(ledger_path, 'r') as f:
            content = f.read()
            assert len(content) == 0, "Ledger should not have written anything"

    finally:
        # Cleanup
        if os.path.exists(ledger_path):
            os.unlink(ledger_path)


def test_gate_events_exempted():
    """
    Test F: Gate events are exempted from evidence_time_h requirement.

    Gate events (gate_event:*, gate_loss:*) are about system state transitions,
    not about biological observations, so they don't need evidence_time_h.
    """
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        ledger_path = f.name

    try:
        # Gate event with null evidence_time_h (should be allowed)
        gate_event = EvidenceEvent(
            cycle=1,
            belief="gate_event:noise_sigma",  # Gate event
            prev=False,
            new=True,
            evidence={"gate": "noise_sigma"},
            supporting_conditions=[],
            note="Gate earned",
            evidence_time_h=None,  # NULL but OK for gate events
            claim_time_h=None,
        )

        # Should succeed without error
        append_events_jsonl(ledger_path, [gate_event])

        # Verify file has content
        with open(ledger_path, 'r') as f:
            content = f.read()
            assert len(content) > 0, "Gate event should have been written"
            assert "gate_event:noise_sigma" in content

    finally:
        if os.path.exists(ledger_path):
            os.unlink(ledger_path)


def test_aggregator_enforces_time_presence():
    """
    Test G: Aggregator must enforce time_h presence in raw results.

    This test verifies that the aggregator layer also enforces temporal
    provenance before belief updates even see the data.
    """
    from src.cell_os.epistemic_agent.observation_aggregator import _aggregate_per_channel
    from src.cell_os.epistemic_agent.schemas import Proposal

    # Create proposal
    proposal = Proposal(
        design_id="test_design",
        hypothesis="test",
        wells=[],
        budget_limit=100
    )

    # Test 1: Zero raw results
    try:
        from cell_os.epistemic_agent.exceptions import TemporalProvenanceError
        _aggregate_per_channel(proposal, [], budget_remaining=100)
        raise AssertionError("Expected TemporalProvenanceError for zero raw_results")
    except TemporalProvenanceError as e:
        assert "zero raw_results" in e.message.lower()
        assert e.missing_field == "observation_time_h"


def test_atemporal_beliefs_still_allowed():
    """
    Test H: Atemporal beliefs (claim_time_h=None) are still allowed.

    Not all beliefs are about specific timepoints. System state beliefs
    like calibration_reps are atemporal and should still work.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Manually set evidence_time_h (simulating that update() ran)
    beliefs._current_evidence_time_h = 24.0

    # Update atemporal belief (claim_time_h=None)
    beliefs._set(
        field_name="calibration_reps",
        new_value=32,
        evidence={"n_wells": 32},
        supporting_conditions=["test"],
        claim_time_h=None,  # Atemporal
    )

    # Should succeed
    assert beliefs.calibration_reps == 32


if __name__ == "__main__":
    print("Running Agent 1.5 Temporal Provenance Enforcement canary tests...\n")

    tests = [
        ("Missing time in conditions crashes", test_missing_time_in_conditions_crashes),
        ("Empty conditions crashes", test_empty_conditions_crashes),
        ("Retroactive inference still blocked", test_retroactive_inference_still_blocked),
        ("Claim with null evidence crashes", test_claim_with_null_evidence_crashes),
        ("Ledger refuses null evidence time", test_ledger_refuses_null_evidence_time),
        ("Gate events exempted", test_gate_events_exempted),
        ("Aggregator enforces time presence", test_aggregator_enforces_time_presence),
        ("Atemporal beliefs still allowed", test_atemporal_beliefs_still_allowed),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All canary tests passed - the hole is closed!")
