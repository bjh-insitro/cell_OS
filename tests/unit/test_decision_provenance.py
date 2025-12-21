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
    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)
    template = decision.chosen_template

    assert template == "baseline_replicates"
    assert decision is not None
    assert isinstance(decision, DecisionEvent)
    assert decision.cycle == 1
    assert decision.chosen_template == "baseline_replicates"


def test_decision_has_regime_metadata():
    """Test that decision event includes regime, forced, trigger, gate_state."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Pre-gate decision
    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)

    assert decision.rationale.regime == "pre_gate"
    assert decision.rationale.forced is True
    assert decision.rationale.trigger == "must_calibrate"
    assert decision.rationale.gate_state is not None


def test_gate_earned_regime():
    """Test that in-gate regime is set when gate earned."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Fake gate earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_rel_width = 0.08  # Well below 0.25
    beliefs.noise_df_total = 50

    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    assert decision.rationale.regime == "in_gate"
    assert decision.rationale.forced is False
    assert decision.rationale.trigger == "scoring"
    assert decision.rationale.gate_state["noise_sigma"] == "earned"


def test_gate_revoked_regime():
    """Test that gate_revoked regime is set when gate lost."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Gate was earned but now lost
    beliefs.noise_sigma_stable = True
    beliefs.noise_rel_width = 0.50  # Above 0.40 exit threshold
    beliefs.noise_df_total = 50

    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    assert decision.rationale.regime == "gate_revoked"
    assert decision.rationale.forced is True
    assert decision.rationale.trigger == "gate_lock"
    assert decision.rationale.gate_state["noise_sigma"] == "lost"


def test_abort_decision_event():
    """Test that abort creates decision event with abort regime."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Set up impossible budget situation
    beliefs.noise_sigma_stable = False
    beliefs.noise_rel_width = 0.30
    beliefs.noise_df_total = 10

    decision = chooser.choose_next(beliefs, budget_remaining_wells=10, cycle=1)
    template = decision.chosen_template

    assert template == "abort"
    assert decision.chosen_template.startswith("abort_") or decision.chosen_template == "abort"
    assert decision.rationale.regime in ["aborted", "pre_gate"]
    assert decision.rationale.forced is True
    assert decision.rationale.trigger == "abort"


def test_decision_event_serialization():
    """Test that DecisionEvent serializes to valid JSON."""
    from cell_os.epistemic_agent.beliefs.ledger import DecisionRationale

    rationale = DecisionRationale(
        summary="Earn noise gate",
        trigger="must_calibrate",
        regime="pre_gate",
        forced=True,
        gate_state={"noise_sigma": "lost", "edge_effect": "unknown"}
    )

    event = DecisionEvent(
        cycle=1,
        candidates=[],
        chosen_template="baseline_replicates",
        chosen_kwargs={"n_reps": 12},
        chosen_score=1.0,
        rationale=rationale
    )

    # Test to_dict()
    d = event.to_dict()
    assert d["cycle"] == 1
    assert d["chosen_template"] == "baseline_replicates"
    assert d["rationale"]["regime"] == "pre_gate"

    # Test to_json_line()
    json_line = event.to_json_line()
    parsed = json.loads(json_line)
    assert parsed["cycle"] == 1
    assert parsed["rationale"]["forced"] is True
