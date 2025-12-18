"""
Unit tests for decision provenance (DecisionEvent creation and writing).

v0.4.2: Ensures decisions.jsonl is written every cycle with regime metadata.
"""

import json
import pytest
from pathlib import Path
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.epistemic_agent.beliefs.ledger import DecisionEvent


def test_chooser_creates_decision_event():
    """Test that chooser creates DecisionEvent for every return path."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Pre-gate: should force calibration
    template, kwargs = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)

    assert template == "baseline_replicates"
    assert chooser.last_decision_event is not None
    assert isinstance(chooser.last_decision_event, DecisionEvent)
    assert chooser.last_decision_event.cycle == 1
    assert chooser.last_decision_event.selected == "baseline_replicates"


def test_decision_has_regime_metadata():
    """Test that decision event includes regime, forced, trigger, gate_state."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Pre-gate decision
    template, kwargs = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)

    candidate = chooser.last_decision_event.selected_candidate
    assert "regime" in candidate
    assert "forced" in candidate
    assert "trigger" in candidate
    assert "gate_state" in candidate
    assert candidate["regime"] == "pre_gate"
    assert candidate["forced"] is True
    assert candidate["trigger"] == "must_calibrate"


def test_gate_earned_regime():
    """Test that in-gate regime is set when gate earned."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Fake gate earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_rel_width = 0.08  # Well below 0.25
    beliefs.noise_df_total = 50

    template, kwargs = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    candidate = chooser.last_decision_event.selected_candidate
    assert candidate["regime"] == "in_gate"
    assert candidate["forced"] is False
    assert candidate["trigger"] == "scoring"
    assert candidate["gate_state"]["noise_sigma"] == "earned"


def test_gate_revoked_regime():
    """Test that gate_revoked regime is set when gate lost."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Gate was earned but now lost
    beliefs.noise_sigma_stable = True
    beliefs.noise_rel_width = 0.50  # Above 0.40 exit threshold
    beliefs.noise_df_total = 50

    template, kwargs = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    candidate = chooser.last_decision_event.selected_candidate
    assert candidate["regime"] == "gate_revoked"
    assert candidate["forced"] is True
    assert candidate["trigger"] == "gate_lock"
    assert candidate["gate_state"]["noise_sigma"] == "lost"


def test_abort_decision_event():
    """Test that abort creates decision event with abort regime."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Set up impossible budget situation
    beliefs.noise_sigma_stable = False
    beliefs.noise_rel_width = 0.30
    beliefs.noise_df_total = 10

    template, kwargs = chooser.choose_next(beliefs, budget_remaining_wells=10, cycle=1)

    assert template == "abort"
    assert chooser.last_decision_event.selected.startswith("abort_")
    candidate = chooser.last_decision_event.selected_candidate
    assert candidate["regime"] in ["aborted", "pre_gate"]
    assert candidate["forced"] is True
    assert candidate["trigger"] == "abort"


def test_decision_event_serialization():
    """Test that DecisionEvent serializes to valid JSON."""
    event = DecisionEvent(
        cycle=1,
        candidates=[],
        selected="baseline_replicates",
        selected_score=1.0,
        selected_candidate={
            "template": "baseline_replicates",
            "regime": "pre_gate",
            "forced": True,
            "trigger": "must_calibrate",
            "gate_state": {"noise_sigma": "lost", "edge_effect": "unknown"}
        },
        reason="Earn noise gate",
    )

    # Test to_dict()
    d = event.to_dict()
    assert d["cycle"] == 1
    assert d["selected"] == "baseline_replicates"
    assert d["selected_candidate"]["regime"] == "pre_gate"

    # Test to_json_line()
    json_line = event.to_json_line()
    parsed = json.loads(json_line)
    assert parsed["cycle"] == 1
    assert parsed["selected_candidate"]["forced"] is True
