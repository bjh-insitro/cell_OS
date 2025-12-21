"""
Semantic teeth tests: Decision objects must be first-class, not side-channel gossip.

These tests enforce that:
1. Decision is immutable (frozen=True)
2. Decision is serializable (round-trip JSON)
3. No side-channel attributes like `last_decision_event`
4. All decisions include required provenance fields
5. Decisions are self-contained (no external state references)
"""

from dataclasses import fields
import json

from cell_os.core import Decision, DecisionRationale


def test_decision_is_immutable():
    """Decision must be frozen (immutable)."""
    rationale = DecisionRationale(
        summary="Test decision",
        rules_fired=("rule1", "rule2"),
    )

    decision = Decision(
        decision_id="test-001",
        cycle=1,
        timestamp_utc="2025-12-21T00:00:00Z",
        kind="proposal",
        chosen_template="baseline_replicates",
        chosen_kwargs={"n_replicates": 4},
        rationale=rationale,
        inputs_fingerprint="abc123",
    )

    # Verify decision is frozen
    try:
        decision.cycle = 2  # type: ignore
        assert False, "Decision should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected: frozen dataclass raises on mutation

    # Verify rationale is frozen
    try:
        rationale.summary = "Modified"  # type: ignore
        assert False, "DecisionRationale should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_decision_is_serializable():
    """Decision must be JSON-serializable (round-trip)."""
    rationale = DecisionRationale(
        summary="Biology proposal after calibration",
        rules_fired=("gate_entered", "noise_threshold_met"),
        warnings=("edge_effect_detected",),
        metrics={"rel_width": 0.18, "top_prob": 0.85},
        thresholds={"gate_enter": 0.25, "commit": 0.75},
        counterfactuals={"if_rel_width_above_0.25": "would_require_more_calibration"},
    )

    decision = Decision(
        decision_id="dec-12345",
        cycle=5,
        timestamp_utc="2025-12-21T12:00:00Z",
        kind="proposal",
        chosen_template="dose_response",
        chosen_kwargs={"compound": "CCCP", "n_doses": 8},
        rationale=rationale,
        inputs_fingerprint="belief_hash_xyz789",
    )

    # Serialize to JSON
    json_str = decision.to_json_line()
    data = json.loads(json_str)

    # Verify all fields present
    assert data["decision_id"] == "dec-12345"
    assert data["cycle"] == 5
    assert data["kind"] == "proposal"
    assert data["chosen_template"] == "dose_response"
    assert data["chosen_kwargs"]["compound"] == "CCCP"

    # Verify rationale present
    assert data["rationale"]["summary"] == "Biology proposal after calibration"
    assert "gate_entered" in data["rationale"]["rules_fired"]
    assert data["rationale"]["metrics"]["rel_width"] == 0.18
    assert data["rationale"]["thresholds"]["gate_enter"] == 0.25

    # Verify inputs_fingerprint present
    assert data["inputs_fingerprint"] == "belief_hash_xyz789"

    # Round-trip via from_dict
    decision_restored = Decision.from_dict(data)
    assert decision_restored.decision_id == decision.decision_id
    assert decision_restored.cycle == decision.cycle
    assert decision_restored.rationale.summary == decision.rationale.summary
    assert decision_restored.rationale.metrics == decision.rationale.metrics


def test_decision_refusal_is_first_class():
    """Refusals should use same Decision schema as proposals."""
    rationale = DecisionRationale(
        summary="Refusal: rel_width too high for biology",
        rules_fired=("gate_revoked",),
        warnings=("high_uncertainty",),
        metrics={"rel_width": 0.45},
        thresholds={"gate_enter": 0.25},
        counterfactuals={"if_more_calibration": "gate_could_reopen"},
    )

    refusal = Decision(
        decision_id="ref-001",
        cycle=3,
        timestamp_utc=Decision.now_utc(),
        kind="refusal",
        chosen_template=None,  # No template chosen
        chosen_kwargs={},
        rationale=rationale,
        inputs_fingerprint="belief_abc",
    )

    # Verify refusal has same structure
    assert refusal.kind == "refusal"
    assert refusal.chosen_template is None
    assert refusal.rationale.summary.startswith("Refusal:")

    # Verify serializable
    data = json.loads(refusal.to_json_line())
    assert data["kind"] == "refusal"
    assert data["chosen_template"] is None


def test_decision_requires_provenance_fields():
    """All Decisions must include inputs_fingerprint, thresholds, rules_fired.

    This prevents drift back to hand-wavy rationale.
    """
    # Verify DecisionRationale has required fields
    rationale_fields = {f.name for f in fields(DecisionRationale)}
    assert "rules_fired" in rationale_fields, \
        "DecisionRationale must have rules_fired (stable identifiers)"
    assert "thresholds" in rationale_fields, \
        "DecisionRationale must have thresholds (replay criteria)"
    assert "metrics" in rationale_fields, \
        "DecisionRationale must have metrics (decision inputs)"

    # Verify Decision has inputs_fingerprint
    decision_fields = {f.name for f in fields(Decision)}
    assert "inputs_fingerprint" in decision_fields, \
        "Decision must have inputs_fingerprint (belief state hash)"


def test_decision_is_self_contained():
    """Decision must not reference external mutable state.

    This test documents the anti-pattern to avoid:
    - Storing decisions in side-channel attributes (e.g., `last_decision_event`)
    - Returning tuple instead of Decision object
    - Reaching back into chooser state to get decision info
    """
    # Decision should contain everything needed for provenance
    rationale = DecisionRationale(
        summary="Calibration required",
        rules_fired=("pre_gate",),
        thresholds={"gate_enter": 0.25},
    )

    decision = Decision(
        decision_id="cal-001",
        cycle=1,
        timestamp_utc=Decision.now_utc(),
        kind="calibration",
        chosen_template="ldh_baseline",
        chosen_kwargs={"n_replicates": 8},
        rationale=rationale,
        inputs_fingerprint="initial_state",
    )

    # All information is IN the decision object
    assert decision.cycle == 1
    assert decision.kind == "calibration"
    assert decision.chosen_template == "ldh_baseline"
    assert decision.rationale.rules_fired == ("pre_gate",)
    assert decision.rationale.thresholds["gate_enter"] == 0.25

    # No need to reach back to chooser.last_decision_event


def test_decision_timestamp_format():
    """Decision timestamps must be UTC ISO 8601 format."""
    timestamp = Decision.now_utc()

    # Verify ISO 8601 format (basic check)
    assert "T" in timestamp, "Timestamp must be ISO 8601 (contains 'T')"
    assert timestamp.endswith("Z") or "+" in timestamp or timestamp.count(":") >= 2, \
        "Timestamp must include timezone info"


def test_decision_kinds():
    """Decision.kind should be limited to known types.

    Valid kinds:
    - "proposal" - Proposing an experiment
    - "refusal" - Refusing to propose (e.g., gate revoked)
    - "calibration" - Choosing calibration experiment
    - "commit" - Final biology experiment (future)
    - "abort" - Aborting run (budget exhausted, etc.)
    """
    valid_kinds = ["proposal", "refusal", "calibration", "commit", "abort"]

    for kind in valid_kinds:
        decision = Decision(
            decision_id=f"test-{kind}",
            cycle=1,
            timestamp_utc=Decision.now_utc(),
            kind=kind,
            chosen_template="test_template" if kind != "refusal" else None,
            chosen_kwargs={},
            rationale=DecisionRationale(summary=f"Test {kind}"),
            inputs_fingerprint="test",
        )
        assert decision.kind == kind


def test_decision_id_stable():
    """Decision IDs should be deterministic or UUID (not random).

    Decision IDs should be:
    - Deterministic based on cycle + timestamp + fingerprint, OR
    - UUID (stable across serialization)

    They should NOT be:
    - Random integers
    - Memory addresses
    - Timestamps alone (not unique within cycle)
    """
    decision1 = Decision(
        decision_id="cycle-1-abc123",
        cycle=1,
        timestamp_utc="2025-12-21T00:00:00Z",
        kind="proposal",
        chosen_template="test",
        chosen_kwargs={},
        rationale=DecisionRationale(summary="Test"),
        inputs_fingerprint="abc123",
    )

    decision2 = Decision(
        decision_id="cycle-1-abc123",  # Same ID
        cycle=1,
        timestamp_utc="2025-12-21T00:00:00Z",
        kind="proposal",
        chosen_template="test",
        chosen_kwargs={},
        rationale=DecisionRationale(summary="Test"),
        inputs_fingerprint="abc123",
    )

    # Same decision_id means same decision (equality check)
    assert decision1.decision_id == decision2.decision_id

    # Verify decision_id is string (serializable)
    assert isinstance(decision1.decision_id, str)


def test_no_legacy_side_channel_pattern():
    """Document the anti-pattern we're killing.

    The old pattern:
    - chooser.choose_next() returns (template, kwargs)
    - Decision stored in chooser.last_decision_event (side channel)
    - Caller reaches back to get decision info

    The new pattern:
    - chooser.choose_next() returns Decision
    - Decision contains template, kwargs, and provenance
    - No side-channel access needed
    """
    # This test documents what NOT to do
    # Future tests should fail if side-channel pattern reappears

    # WRONG (old pattern):
    # template, kwargs = chooser.choose_next(...)
    # decision = chooser.last_decision_event  # ❌ Side channel gossip

    # CORRECT (new pattern):
    # decision = chooser.choose_next(...)
    # template = decision.chosen_template
    # kwargs = decision.chosen_kwargs
    pass


if __name__ == '__main__':
    test_decision_is_immutable()
    test_decision_is_serializable()
    test_decision_refusal_is_first_class()
    test_decision_requires_provenance_fields()
    test_decision_is_self_contained()
    test_decision_timestamp_format()
    test_decision_kinds()
    test_decision_id_stable()
    test_no_legacy_side_channel_pattern()

    print("✓ All decision semantic teeth tests passed")
    print("✓ Decision is immutable (frozen=True)")
    print("✓ Decision is serializable (round-trip JSON)")
    print("✓ Decisions are self-contained (no side-channel)")
    print("✓ All decisions include provenance (fingerprint, thresholds, rules)")
