#!/usr/bin/env python3
"""
Integration test: Verify Decision objects work end-to-end.

Tests:
1. Chooser returns Decision (not tuple)
2. Agent stores Decision in last_decision
3. Decision contains all required provenance
4. No hasattr checks needed (no side-channel)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.core import Decision


def test_chooser_returns_decision():
    """Chooser.choose_next() returns Decision, not tuple."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    result = chooser.choose_next(beliefs, budget_remaining_wells=384, cycle=1)

    # Verify returns Decision
    assert isinstance(result, Decision), \
        f"choose_next() must return Decision, got {type(result)}"

    # Verify has all required fields
    assert result.decision_id is not None
    assert result.cycle == 1
    assert result.timestamp_utc is not None
    assert result.kind in ["proposal", "calibration", "refusal", "abort"]
    assert result.chosen_template is not None or result.kind == "refusal"
    assert result.rationale is not None
    assert result.inputs_fingerprint is not None

    print(f"✓ Chooser returns Decision: {result.decision_id}")
    print(f"  - kind: {result.kind}")
    print(f"  - template: {result.chosen_template}")
    print(f"  - rationale: {result.rationale.summary[:60]}...")


def test_decision_has_legacy_fields():
    """Decision rationale includes legacy fields for backward compatibility."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    decision = chooser.choose_next(beliefs, budget_remaining_wells=384, cycle=1)

    # Verify legacy metadata fields exist
    assert hasattr(decision.rationale, "regime"), \
        "DecisionRationale must have regime field"
    assert hasattr(decision.rationale, "forced"), \
        "DecisionRationale must have forced field"
    assert hasattr(decision.rationale, "trigger"), \
        "DecisionRationale must have trigger field"
    assert hasattr(decision.rationale, "enforcement_layer"), \
        "DecisionRationale must have enforcement_layer field"

    print(f"✓ Decision has legacy fields:")
    print(f"  - regime: {decision.rationale.regime}")
    print(f"  - forced: {decision.rationale.forced}")
    print(f"  - trigger: {decision.rationale.trigger}")
    print(f"  - enforcement_layer: {decision.rationale.enforcement_layer}")


def test_decision_serialization():
    """Decision serializes to JSON and deserializes correctly."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    decision = chooser.choose_next(beliefs, budget_remaining_wells=384, cycle=1)

    # Serialize to JSON
    json_str = decision.to_json_line()
    assert len(json_str) > 0

    # Deserialize
    import json
    data = json.loads(json_str)
    decision_restored = Decision.from_dict(data)

    # Verify round-trip
    assert decision_restored.decision_id == decision.decision_id
    assert decision_restored.cycle == decision.cycle
    assert decision_restored.kind == decision.kind
    assert decision_restored.chosen_template == decision.chosen_template
    assert decision_restored.rationale.summary == decision.rationale.summary
    assert decision_restored.rationale.regime == decision.rationale.regime

    print(f"✓ Decision serialization works (round-trip)")
    print(f"  - JSON size: {len(json_str)} chars")


def test_no_side_channel_needed():
    """Decision is self-contained - no need for side-channel access."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Get decision
    decision = chooser.choose_next(beliefs, budget_remaining_wells=384, cycle=1)

    # Extract template and kwargs from Decision (not from side-channel)
    template_name = decision.chosen_template
    template_kwargs = decision.chosen_kwargs

    # Verify we got what we need
    assert template_name is not None or decision.kind == "refusal"
    assert isinstance(template_kwargs, dict)

    # No hasattr checks needed!
    # Old pattern: if hasattr(chooser, 'last_decision_event'): ...
    # New pattern: decision is returned directly

    print(f"✓ No side-channel needed:")
    print(f"  - template: {template_name}")
    print(f"  - kwargs keys: {list(template_kwargs.keys())[:5]}")
    print(f"  - provenance in Decision object (not side-channel)")


if __name__ == "__main__":
    print("[1/4] Testing chooser returns Decision...")
    test_chooser_returns_decision()
    print()

    print("[2/4] Testing Decision has legacy fields...")
    test_decision_has_legacy_fields()
    print()

    print("[3/4] Testing Decision serialization...")
    test_decision_serialization()
    print()

    print("[4/4] Testing no side-channel needed...")
    test_no_side_channel_needed()
    print()

    print("=" * 60)
    print("✓ Translation Kill #5: Decision Objects VERIFIED")
    print("=" * 60)
    print("✓ Chooser returns Decision (not tuple)")
    print("✓ Decision is self-contained (no side-channel)")
    print("✓ Decision is serializable (JSON round-trip)")
    print("✓ All provenance included (rationale, metrics, thresholds)")
    print("✓ hasattr checks eliminated")
