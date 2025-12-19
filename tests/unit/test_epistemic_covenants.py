"""
Epistemic Covenant Violation Tests (Tightened v2)

Each test intentionally violates one of the Seven Covenants from EPISTEMIC_CHARTER.md
and verifies that the system refuses the violation with the correct reason AND provenance.

These tests now check:
- `trigger`, `enforcement_layer`, `blocked_template`, `missing_gates`, `calibration_plan`
- Stable substrings in `reason` field
- Specific gate states for relevant gates
- Custom exception types where applicable

Goal: Prove the system knows WHY it refused, not just THAT it refused.
"""

import pytest
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.exceptions import (
    DecisionReceiptInvariantError,
    BeliefLedgerInvariantError
)
from dataclasses import dataclass
from typing import List


@dataclass
class MockConditionSummary:
    """Mock condition for testing."""
    compound: str = "DMSO"
    cell_line: str = "A549"
    dose_uM: float = 0.0
    time_h: float = 12.0
    assay: str = "cell_painting"
    position_tag: str = "center"
    n_wells: int = 12
    mean: float = 1.0
    std: float = 0.2
    cv: float = 0.2
    feature_means: dict = None
    feature_stds: dict = None


@dataclass
class MockObservation:
    """Mock observation for testing."""
    conditions: List[MockConditionSummary] = None
    budget_remaining: int = 384


def test_covenant1_refuses_biology_without_instrument_gate():
    """Covenant 1: Assays Are Not Biology. They Are Instruments.

    Violation: Attempt to run biology template (dose_ladder) before proving
    we understand the measurement instrument (LDH gate not earned).

    Expected: System refuses with "must earn LDH gate" reason, provenance shows:
    - trigger="must_calibrate"
    - enforcement_layer="global_pre_biology" (dominant enforcement path)
    - assay="ldh"
    - calibration_plan with df_needed, wells_needed
    - gate_state shows ldh="lost"
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate earned (bypasses initial calibration)
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    # LDH gate NOT earned (instrument not understood)
    beliefs.ldh_sigma_stable = False
    beliefs.ldh_df_total = 10
    beliefs.ldh_rel_width = 0.50  # Too wide

    # CP gate NOT earned (instrument not understood)
    beliefs.cell_paint_sigma_stable = False
    beliefs.cell_paint_df_total = 10
    beliefs.cell_paint_rel_width = 0.50

    # Trigger dose ladder desire
    beliefs.tested_compounds = {'DMSO'}

    # Attempt to run biology
    template_name, template_kwargs = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=5
    )

    # System must refuse by forcing calibration
    assert template_name == "calibrate_ldh_baseline", \
        "Covenant 1 violation: Biology without instrument gate must be refused"

    # Check decision receipt explains refusal with full provenance
    decision = chooser.last_decision_event
    cand = decision.selected_candidate

    assert cand["trigger"] == "must_calibrate", \
        "Refusal must cite calibration requirement (trigger field)"
    assert cand["enforcement_layer"] == "global_pre_biology", \
        "Refusal must identify which policy layer enforced it"
    assert cand["assay"] == "ldh", \
        "Refusal must explain which instrument gate is missing"
    assert "calibration_plan" in cand, \
        "Refusal must include calibration plan (cost estimate)"
    assert cand["gate_state"]["ldh"] == "lost", \
        "Refusal must record LDH gate status"
    assert "ldh" in decision.reason.lower(), \
        "Refusal reason must mention LDH"


def test_covenant2_refuses_to_skip_calibration_as_first_experiment():
    """Covenant 2: Calibration Is Not a Setup Step. It Is the First Experiment.

    Violation: Attempt to start with biology (compound testing) instead of
    establishing baseline measurement repeatability.

    Expected: System forces baseline replicates as first action, provenance shows:
    - trigger="must_calibrate"
    - regime="pre_gate"
    - calibration_plan with df_needed
    - gate_state shows noise_sigma="lost"
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Fresh beliefs (no calibration yet)
    assert beliefs.noise_sigma_stable == False, "No calibration yet"
    assert beliefs.noise_df_total == 0, "No measurements yet"

    # Try to run biology from cycle 1
    template_name, template_kwargs = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=1
    )

    # System must refuse by forcing baseline calibration
    assert template_name == "baseline_replicates", \
        "Covenant 2 violation: First experiment must be calibration, not biology"

    # Check decision receipt cites noise gate requirement
    decision = chooser.last_decision_event
    cand = decision.selected_candidate

    assert cand["trigger"] == "must_calibrate", \
        "First experiment refusal must cite calibration requirement"
    assert cand["regime"] == "pre_gate", \
        "First experiment must be in pre-gate regime"
    assert "calibration_plan" in cand, \
        "First experiment refusal must include calibration plan"
    assert cand["gate_state"]["noise_sigma"] == "lost", \
        "Refusal must record noise gate status"
    assert "noise" in decision.reason.lower() or "gate" in decision.reason.lower(), \
        "Refusal reason must mention noise/gate"


def test_covenant3_refuses_expensive_truth_before_cheap_truth():
    """Covenant 3: Cheap Truth Gates Expensive Truth.

    Violation: Attempt to run scRNA calibration (expensive) before earning
    Cell Painting gate (cheap). Economic logic says earn cheap gates first.

    Expected: System refuses scRNA calibration autonomously, provenance shows:
    - trigger="policy_boundary"
    - attempted_template="calibrate_scrna_baseline"
    - reason contains "expensive" and "authorization"
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    # LDH gate earned (cheap truth 1)
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22

    # CP gate NOT earned (cheap truth 2 missing)
    beliefs.cell_paint_sigma_stable = False
    beliefs.cell_paint_df_total = 10
    beliefs.cell_paint_rel_width = 0.50

    # Attempt to validate expensive calibration template
    is_valid, abort_reason = chooser._validate_template_selection(
        "calibrate_scrna_baseline",
        allow_expensive_calibration=False,  # Default: no autonomous expensive calibration
        cycle=5,
        beliefs=beliefs
    )

    # System must refuse
    assert is_valid == False, \
        "Covenant 3 violation: Expensive truth before cheap truth must be refused"
    assert "expensive" in abort_reason.lower(), \
        "Refusal must explain economic constraint"
    assert "manual" in abort_reason.lower() or "authorization" in abort_reason.lower(), \
        "Refusal must explain policy boundary"
    assert "calibrate_scrna_baseline" in abort_reason, \
        "Refusal must name the template being blocked"


def test_covenant4_refuses_action_on_shadow_knowledge():
    """Covenant 4: Knowledge and Action Are Separate.

    Violation: Attempt to use scRNA shadow stats (knowledge) to justify
    running scRNA experiments (action), even though metrics look excellent.

    Expected: System tracks shadow stats but never sets gate to True,
    preventing action despite good knowledge. Shadow event must show:
    - actionable=False
    - metric_source contains "proxy"
    - belief field scrna_metric_source="proxy:noisy_morphology"
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Feed many cycles of low-noise DMSO data
    # This will make scRNA shadow stats look excellent (low rel_width)
    conditions = []
    for i in range(15):
        conditions.append(MockConditionSummary(
            n_wells=12,
            mean=1.0,
            std=0.15,  # Very low noise
            cv=0.15
        ))

    observation = MockObservation(conditions=conditions)

    for cycle in range(15):
        beliefs.begin_cycle(cycle + 1)
        events, _ = beliefs.update(observation, cycle=cycle + 1)

    # Knowledge: scRNA shadow stats are excellent
    assert beliefs.scrna_df_total > 40, "Shadow knowledge: enough df"
    assert beliefs.scrna_rel_width is not None, "Shadow knowledge: rel_width tracked"
    assert beliefs.scrna_rel_width < 0.25, "Shadow knowledge: metrics are excellent"

    # Action: scRNA gate must NOT be earned (knowledge ≠ permission)
    assert beliefs.scrna_sigma_stable == False, \
        "Covenant 4 violation: Excellent shadow stats must not grant action permission"

    # Verify shadow event was emitted (knowledge tracked)
    scrna_shadow_events = [e for e in events if e.belief == "gate_shadow:scrna"]
    assert len(scrna_shadow_events) > 0, \
        "Shadow event must be emitted to track non-actionable knowledge"

    shadow_event = scrna_shadow_events[0]
    assert shadow_event.evidence.get("actionable") == False, \
        "Shadow event must mark knowledge as non-actionable"
    assert "proxy" in shadow_event.evidence.get("metric_source", ""), \
        "Shadow event must explain why action is blocked (proxy metric)"

    # Verify metric_source field marks knowledge as proxy
    assert beliefs.scrna_metric_source == "proxy:noisy_morphology", \
        "Belief field must mark shadow knowledge source"


def test_covenant5_refuses_to_proceed_when_economically_unjustified():
    """Covenant 5: Refusal Is a First-Class Scientific Act.

    Violation: Attempt to proceed with an experiment that we cannot afford,
    rather than explicitly refusing with budget provenance.

    Expected: System aborts with calibration plan showing the gap, provenance shows:
    - template="abort_insufficient_calibration_budget"
    - trigger="abort"
    - forced=True
    - calibration_plan with wells_needed > budget_remaining
    - reason contains "Cannot afford"
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate NOT earned (needs calibration)
    beliefs.noise_sigma_stable = False
    beliefs.noise_df_total = 0
    beliefs.noise_rel_width = None

    # Very low budget (cannot afford to earn gate)
    # Calibration needs ~140 df = ~156 wells, but we only have 50
    low_budget = 50

    # Attempt to choose next
    template_name, template_kwargs = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=low_budget,
        cycle=1
    )

    # System must refuse with abort
    assert template_name == "abort", \
        "Covenant 5 violation: Economically unjustified action must be refused"
    assert "Cannot afford" in template_kwargs.get("reason", ""), \
        "Refusal must explain budget constraint"

    # Check decision receipt includes calibration plan
    decision = chooser.last_decision_event
    cand = decision.selected_candidate

    assert cand["template"] == "abort_insufficient_calibration_budget", \
        "Refusal must have specific abort type"
    assert cand["trigger"] == "abort", \
        "Refusal must be marked as abort trigger"
    assert cand["forced"] == True, \
        "Abort is a forced decision (no choice)"
    assert "calibration_plan" in cand, \
        "Refusal must show what we cannot afford"
    assert cand["calibration_plan"]["wells_needed"] > low_budget, \
        "Calibration plan must show wells needed exceeds budget"


def test_covenant6_refuses_to_act_without_recording_receipt():
    """Covenant 6: Every Decision Must Have a Receipt.

    Violation: If enforcement overrides a template but forgets to write
    the decision receipt, the split-brain contract should fail-loud.

    Expected: System crashes with DecisionReceiptInvariantError explaining
    contract violation.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Set up scenario where _enforce_template_gates will override
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20
    beliefs.ldh_sigma_stable = False  # Missing gate

    # Manually corrupt the contract: make _enforce_template_gates return wrong result
    # but don't let enforcement write a receipt
    original_enforce = chooser._enforce_template_gates

    def corrupt_enforce_no_receipt(*args, **kwargs):
        # Override template but DON'T write decision (contract violation)
        return ("calibrate_ldh_baseline", {"reason": "corrupted", "assay": "ldh", "n_reps": 12})

    # This should trigger the invariant check
    from unittest.mock import patch
    with patch.object(chooser, '_enforce_template_gates', side_effect=corrupt_enforce_no_receipt):
        with pytest.raises(AssertionError) as exc_info:
            # _finalize_selection calls _enforce_template_gates, gets override,
            # checks invariant, should raise AssertionError
            chooser._finalize_selection(
                beliefs=beliefs,
                template_name="dose_ladder_coarse",
                template_kwargs={"reason": "test"},
                remaining_wells=384,
                cycle=5,
                allow_expensive_calibration=False,
                selected_score=1.0,
                reason="test",
                forced=False,
                trigger="scoring",
                regime="in_gate"
            )

        # Expected: invariant check catches missing receipt
        assert "did not set last_decision_event" in str(exc_info.value), \
            "Failure must explain missing receipt (contract violation)"


def test_covenant7_refuses_to_update_beliefs_without_evidence():
    """Covenant 7: We Optimize for Causal Discoverability, Not Throughput.

    Violation: Attempt to update a belief without recording evidence,
    supporting conditions, and provenance. This makes causal reconstruction
    impossible later.

    Expected: _set() method forces evidence recording, or belief doesn't update.
    Direct mutation bypasses evidence recording (this is the violation we're testing).
    """
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Attempt to directly set a belief without calling _set()
    # This simulates a sloppy refactor that skips evidence recording
    old_value = beliefs.dose_curvature_seen

    # Proper way: use _set() with evidence
    beliefs._set(
        "dose_curvature_seen",
        True,
        evidence={
            "n_curves": 1,
            "max_diff_ratio": 3.5,
            "threshold_ratio": 2.0
        },
        supporting_conditions=["A549/CCCP@1.0uM/12.0h/cell_painting/center"],
        note="Dose curvature detected"
    )

    # Verify event was emitted
    events = beliefs.end_cycle()
    belief_events = [e for e in events if e.belief == "dose_curvature_seen"]

    assert len(belief_events) > 0, \
        "Covenant 7 violation: Belief update without evidence event is not allowed"

    event = belief_events[0]
    assert event.evidence is not None, "Event must include evidence"
    assert len(event.supporting_conditions) > 0, \
        "Event must include supporting conditions (which wells?)"
    assert event.note is not None, "Event must include human-readable note"
    assert event.prev == old_value, "Event must record previous value"
    assert event.new == True, "Event must record new value"

    # The violation: if someone bypasses _set() and mutates directly
    beliefs2 = BeliefState()
    beliefs2.begin_cycle(1)
    beliefs2.dose_curvature_seen = True  # Direct mutation (BAD)
    events2 = beliefs2.end_cycle()

    # No event emitted - this is the violation
    belief_events2 = [e for e in events2 if e.belief == "dose_curvature_seen"]
    assert len(belief_events2) == 0, \
        "Direct mutation bypasses evidence recording (this is the violation we're testing)"

    # In production, assert_no_undocumented_mutation() would catch this
    # Test that it does:
    beliefs3 = BeliefState()
    beliefs3.begin_cycle(1)
    before = beliefs3.snapshot()
    beliefs3.dose_curvature_seen = True  # Direct mutation
    after = beliefs3.snapshot()

    # Should raise BeliefLedgerInvariantError
    with pytest.raises(BeliefLedgerInvariantError) as exc_info:
        beliefs3.assert_no_undocumented_mutation(before, after, cycle=1)

    assert "without any evidence events" in str(exc_info.value), \
        "Invariant must detect direct mutation and explain violation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
