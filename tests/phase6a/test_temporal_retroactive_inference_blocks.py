"""
Test: Temporal Causality Enforcement - Agent 1

Verifies that beliefs cannot be updated retroactively using future evidence.

Temporal admissibility rule: evidence_time_h >= claim_time_h

This test ensures the system blocks retroactive inference:
- Using 48h data to update 12h mechanism beliefs
- Using late-stage observations to reason about early dynamics

Without this enforcement, agents appear incoherent when they are actually
cheating by using future information to update past beliefs.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.epistemic_agent.beliefs.state import BeliefState
from src.cell_os.epistemic_agent.beliefs.ledger import EvidenceEvent
from src.cell_os.epistemic_agent.exceptions import TemporalCausalityViolation
from src.cell_os.epistemic_agent.schemas import ConditionSummary


def test_temporal_retroactive_inference_blocks():
    """
    Core test: Attempting to claim about 48h state using 12h evidence must be blocked.

    Scenario:
    1. Observe data at 12h
    2. Attempt to update belief about 48h mechanism (future state)
    3. Expect: TemporalCausalityViolation raised
    4. Expect: No belief mutation occurs
    5. Expect: Refusal is logged with clear reason

    Temporal rule: claim_time_h <= evidence_time_h
    (Can only make claims about states at or before observation time)
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Simulate observation at 12h
    beliefs._current_evidence_time_h = 12.0

    # Attempt to update a belief about 48h timepoint (future)
    # This should fail with TemporalCausalityViolation
    try:
        beliefs._set(
            field_name="dose_curvature_seen",
            new_value=True,
            evidence={"mechanism": "ER_STRESS", "fold_change": 2.5},
            supporting_conditions=["A549/tunicamycin@1uM/12h/cell_painting/center"],
            note="Attempting to predict 48h state from 12h data",
            claim_time_h=48.0,  # Claiming about future (48h)
            evidence_time_h=12.0,  # Using past evidence (12h)
        )
        raise AssertionError("Expected TemporalCausalityViolation but none was raised")
    except TemporalCausalityViolation as exc:
        # Verify exception details
        assert exc.belief_name == "dose_curvature_seen"
        assert exc.evidence_time_h == 12.0
        assert exc.claim_time_h == 48.0
        assert exc.violation_delta_h == 48.0 - 12.0  # 36h into future
        assert "future" in exc.message.lower()

    # Verify belief was NOT mutated
    assert beliefs.dose_curvature_seen is False

    # Verify no event was emitted (refusal happened before event creation)
    events = beliefs.end_cycle()
    assert len(events) == 0, "No events should be emitted for refused updates"


def test_temporal_causality_allows_valid_update():
    """
    Verify that valid temporal updates (evidence_time_h >= claim_time_h) are allowed.

    Scenario:
    1. Observe data at 48h
    2. Update belief about 48h mechanism (same time)
    3. Expect: Update succeeds
    4. Expect: Event is logged with temporal provenance
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Simulate observation at 48h
    beliefs._current_evidence_time_h = 48.0

    # Update belief about 48h timepoint (valid: same time)
    beliefs._set(
        field_name="dose_curvature_seen",
        new_value=True,
        evidence={"mechanism": "ER_STRESS", "fold_change": 2.5},
        supporting_conditions=["A549/tunicamycin@1uM/48h/cell_painting/center"],
        note="Detected ER stress signature at 48h",
        claim_time_h=48.0,  # Claiming about 48h
        evidence_time_h=48.0,  # Evidence from 48h
    )

    # Verify belief was updated
    assert beliefs.dose_curvature_seen is True

    # Verify event was logged with temporal provenance
    events = beliefs.end_cycle()
    assert len(events) == 1
    event = events[0]
    assert event.belief == "dose_curvature_seen"
    assert event.evidence_time_h == 48.0
    assert event.claim_time_h == 48.0


def test_temporal_causality_allows_future_to_past():
    """
    Verify that using future evidence for past claims is allowed (valid direction).

    Scenario:
    1. Observe data at 48h
    2. Update belief about 12h mechanism (using later evidence)
    3. Expect: Update succeeds (evidence_time_h > claim_time_h is valid)
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Simulate observation at 48h
    beliefs._current_evidence_time_h = 48.0

    # Update belief about 12h using 48h evidence (valid: future evidence for past claim)
    # This represents learning "by 48h, we know what happened at 12h"
    beliefs._set(
        field_name="time_dependence_seen",
        new_value=True,
        evidence={"time_series": [12.0, 24.0, 48.0], "progression_detected": True},
        supporting_conditions=["A549/tunicamycin@1uM/48h/cell_painting/center"],
        note="Time series analysis confirms 12h is critical window",
        claim_time_h=12.0,  # Claiming about 12h
        evidence_time_h=48.0,  # Using 48h evidence (valid: 48 >= 12)
    )

    # Verify belief was updated
    assert beliefs.time_dependence_seen is True

    # Verify event was logged
    events = beliefs.end_cycle()
    assert len(events) == 1


def test_temporal_causality_atemporal_beliefs():
    """
    Verify that atemporal beliefs (claim_time_h=None) are not subject to temporal checks.

    Scenario:
    1. Observe data at any time
    2. Update atemporal belief (e.g., noise_sigma_stable)
    3. Expect: No temporal validation (claim_time_h=None bypasses check)
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Simulate observation at 48h
    beliefs._current_evidence_time_h = 48.0

    # Update atemporal belief (no claim_time_h)
    # This should succeed regardless of evidence time
    beliefs._set(
        field_name="calibration_reps",
        new_value=32,
        evidence={"n_wells": 32, "pooled_df": 31},
        supporting_conditions=["A549/DMSO@0uM/12h/cell_painting/center"],
        note="Calibration replicates collected",
        claim_time_h=None,  # Atemporal belief
        evidence_time_h=48.0,
    )

    # Verify belief was updated
    assert beliefs.calibration_reps == 32

    # Verify event was logged
    events = beliefs.end_cycle()
    assert len(events) == 1
    event = events[0]
    assert event.claim_time_h is None  # Atemporal


def test_temporal_causality_default_evidence_time():
    """
    Verify that _current_evidence_time_h is used when evidence_time_h not provided.

    Scenario:
    1. Set _current_evidence_time_h during update()
    2. Call _set() without explicit evidence_time_h
    3. Expect: Uses _current_evidence_time_h
    4. Expect: Temporal validation still applies
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Let's try with 12h evidence and 24h claim (should fail)
    beliefs._current_evidence_time_h = 12.0

    try:
        beliefs._set(
            field_name="dose_curvature_seen",
            new_value=True,
            evidence={"mechanism": "ER_STRESS"},
            supporting_conditions=["A549/tunicamycin@1uM/12h/cell_painting/center"],
            note="Claiming about 24h",
            claim_time_h=24.0,  # Claiming about 24h
            # evidence_time_h not provided, should use _current_evidence_time_h (12h)
        )
        raise AssertionError("Expected TemporalCausalityViolation but none was raised")
    except TemporalCausalityViolation as exc:
        assert exc.evidence_time_h == 12.0  # Used _current_evidence_time_h
        assert exc.claim_time_h == 24.0
        assert exc.violation_delta_h == 24.0 - 12.0  # 12h (claim exceeds evidence by 12h)


def test_temporal_provenance_in_ledger():
    """
    Verify that temporal provenance is logged in evidence ledger.

    Scenario:
    1. Perform valid belief updates with temporal metadata
    2. Verify ledger contains evidence_time_h and claim_time_h
    3. Verify downstream audit can distinguish temporal violations from biology
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    beliefs._current_evidence_time_h = 24.0

    # Update 1: Early timepoint
    beliefs._set(
        field_name="dose_curvature_seen",
        new_value=True,
        evidence={"timepoint": "12h", "signal": "present"},
        supporting_conditions=["cond1"],
        claim_time_h=12.0,
        evidence_time_h=24.0,
    )

    # Update 2: Later timepoint
    beliefs._set(
        field_name="time_dependence_seen",
        new_value=True,
        evidence={"timepoint": "24h", "signal": "increased"},
        supporting_conditions=["cond2"],
        claim_time_h=24.0,
        evidence_time_h=24.0,
    )

    events = beliefs.end_cycle()
    assert len(events) == 2

    # Verify temporal metadata in ledger
    assert events[0].evidence_time_h == 24.0
    assert events[0].claim_time_h == 12.0

    assert events[1].evidence_time_h == 24.0
    assert events[1].claim_time_h == 24.0

    # Verify events can be serialized to JSONL (for audit)
    for event in events:
        json_line = event.to_json_line()
        assert "evidence_time_h" in json_line
        assert "claim_time_h" in json_line


def test_temporal_enforcement_during_update():
    """
    Integration test: Verify temporal enforcement during full update cycle.

    This is closer to real usage where update() is called with observations.
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Create fake observation with 12h data
    class FakeCondition:
        def __init__(self, time_h):
            self.time_h = time_h
            self.compound = "tunicamycin"
            self.cell_line = "A549"
            self.dose_uM = 1.0
            self.assay = "cell_painting"
            self.position_tag = "center"
            self.n_wells = 12
            self.mean = 2.5
            self.std = 0.3
            self.sem = 0.087
            self.cv = 0.12
            self.feature_means = {"er": 2.5}

    class FakeObservation:
        def __init__(self, conditions):
            self.conditions = conditions
            self.budget_remaining = 300

    # Observation at 12h
    obs = FakeObservation([FakeCondition(12.0)])

    # This should set _current_evidence_time_h to 12h
    events, diagnostics = beliefs.update(obs, cycle=1)

    # Verify _current_evidence_time_h was set
    assert beliefs._current_evidence_time_h == 12.0

    # Now if we try to update a belief about 48h (future), it should fail
    try:
        beliefs._set(
            field_name="dose_curvature_seen",
            new_value=True,
            evidence={"signal": "test"},
            supporting_conditions=["test"],
            claim_time_h=48.0,  # Future claim (not allowed with 12h evidence)
        )
        raise AssertionError("Expected TemporalCausalityViolation but none was raised")
    except TemporalCausalityViolation:
        pass  # Expected


if __name__ == "__main__":
    # Run tests
    print("Running temporal causality enforcement tests...\n")

    tests = [
        ("Retroactive inference blocks", test_temporal_retroactive_inference_blocks),
        ("Valid temporal update allowed", test_temporal_causality_allows_valid_update),
        ("Future-to-past update allowed", test_temporal_causality_allows_future_to_past),
        ("Atemporal beliefs bypass check", test_temporal_causality_atemporal_beliefs),
        ("Default evidence time used", test_temporal_causality_default_evidence_time),
        ("Temporal provenance logged", test_temporal_provenance_in_ledger),
        ("Integration with update()", test_temporal_enforcement_during_update),
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
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    if failed > 0:
        sys.exit(1)
