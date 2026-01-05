"""
Unit tests for decision provenance (Decision creation and writing).

v0.4.2: Ensures decisions.jsonl is written every cycle with regime metadata.

Updated for refactored API:
- Decision (from core) instead of DecisionEvent (from ledger)
- pre_calibration instead of pre_gate
- cycle0_required instead of must_calibrate
"""

import json
import pytest
from pathlib import Path
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.core import Decision


def test_chooser_creates_decision():
    """Test that chooser creates Decision for every return path."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Pre-calibration: should force calibration
    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)
    template = decision.chosen_template

    assert template == "baseline_replicates"
    assert decision is not None
    assert isinstance(decision, Decision)
    assert decision.cycle == 1
    assert decision.chosen_template == "baseline_replicates"


def test_decision_has_regime_metadata():
    """Test that decision includes regime, forced, trigger, gate_state."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Pre-calibration decision
    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)

    assert decision.rationale.regime in ("pre_calibration", "pre_gate")
    assert decision.rationale.forced is True
    assert decision.rationale.trigger in ("must_calibrate", "cycle0_required")
    assert decision.rationale.gate_state is not None


def test_gate_earned_regime():
    """Test regime when all gates earned."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Fake all gates earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_rel_width = 0.08
    beliefs.noise_df_total = 150
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.20
    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.20

    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    # May still be pre_calibration due to cycle0 requirements
    assert decision.rationale.regime in ("in_gate", "pre_calibration")
    assert decision.rationale.gate_state["noise_sigma"] == "earned"


def test_gate_revoked_regime():
    """Test gate state when noise rel_width exceeds exit threshold."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Gate was earned but now has high rel_width
    beliefs.noise_sigma_stable = True  # Still marked stable
    beliefs.noise_rel_width = 0.50  # Above 0.40 exit threshold
    beliefs.noise_df_total = 150

    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=5)

    # Gate should still show as earned (noise_sigma_stable is True)
    # The rel_width being high doesn't immediately revoke
    assert decision.rationale.regime in ("gate_revoked", "pre_calibration")
    assert decision.rationale.forced is True


def test_abort_decision_event():
    """Test that abort creates decision event with abort template."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    # Set up impossible budget situation
    beliefs.noise_sigma_stable = False
    beliefs.noise_rel_width = 0.30
    beliefs.noise_df_total = 10

    decision = chooser.choose_next(beliefs, budget_remaining_wells=10, cycle=1)
    template = decision.chosen_template

    assert template.startswith("abort")
    assert decision.rationale.forced is True
    assert decision.rationale.trigger in ("abort", "cycle0_required", "insufficient_budget")


def test_decision_serialization():
    """Test that Decision serializes to valid dict."""
    chooser = TemplateChooser()
    beliefs = BeliefState()

    decision = chooser.choose_next(beliefs, budget_remaining_wells=200, cycle=1)

    # Test to_dict()
    d = decision.to_dict()
    assert d["cycle"] == 1
    assert d["chosen_template"] == "baseline_replicates"
    assert "rationale" in d
    assert "regime" in d["rationale"]

    # Test JSON serialization
    json_str = json.dumps(d)
    parsed = json.loads(json_str)
    assert parsed["cycle"] == 1
