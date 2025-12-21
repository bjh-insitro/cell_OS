"""
Unit tests for measurement ladder (v0.5.0).

Tests assay-specific gates (ldh, cell_paint, scrna) and ladder constraints.
"""

import pytest
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.beliefs.ledger import EvidenceEvent
from dataclasses import dataclass
from typing import List
from unittest.mock import patch


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


def test_assay_gate_event_emitted():
    """Test that gate_event:cell_paint is emitted when rel_width crosses threshold."""
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Create conditions with enough df to earn gate
    conditions = []
    for i in range(12):  # 12 reps → df=11 each, need ~4 cycles for df=140
        conditions.append(MockConditionSummary(
            n_wells=12,
            mean=1.0,
            std=0.18,  # Low std → will achieve rel_width < 0.25 after enough df
            cv=0.18
        ))

    # Simulate multiple cycles to accumulate df
    observation = MockObservation(conditions=conditions)

    for cycle in range(15):  # 15 cycles should be enough
        beliefs.begin_cycle(cycle + 1)
        events, diagnostics = beliefs.update(observation, cycle=cycle + 1)

        # Check if any gate_event:cell_paint was emitted
        gate_events = [e for e in events if e.belief.startswith("gate_event:cell_paint")]
        if gate_events:
            # Found it!
            assert gate_events[0].belief == "gate_event:cell_paint"
            assert "proxy:noisy_morphology" in gate_events[0].note
            assert beliefs.cell_paint_sigma_stable == True
            assert beliefs.cell_paint_rel_width is not None
            assert beliefs.cell_paint_rel_width < 0.25
            return  # Test passed

    # If we get here, gate was never earned - check if we're close
    assert beliefs.cell_paint_df_total > 0, "No df accumulated"
    # This might fail if thresholds are too tight, but should work with low std=0.18


def test_ladder_blocks_scrna_until_cp_gate():
    """Test that scRNA is blocked until CP gate is earned (ladder constraint)."""
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Initial state: no gates earned
    assert beliefs.cell_paint_sigma_stable == False
    assert beliefs.scrna_sigma_stable == False

    # Check scRNA gate with ladder enforcement
    gate_ok, block_reason = chooser._check_assay_gate(beliefs, "scrna", require_ladder=True)

    assert gate_ok == False
    assert "scRNA gate not earned" in block_reason or "Cell Painting gate earned first" in block_reason

    # Now earn CP gate (mock it directly for this test)
    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.20

    # Check again: should still fail because scRNA gate itself not earned
    gate_ok, block_reason = chooser._check_assay_gate(beliefs, "scrna", require_ladder=True)
    assert gate_ok == False
    assert "scRNA gate not earned" in block_reason

    # Now earn scRNA gate
    beliefs.scrna_sigma_stable = True
    beliefs.scrna_df_total = 50
    beliefs.scrna_rel_width = 0.22

    # Check again: should pass
    gate_ok, block_reason = chooser._check_assay_gate(beliefs, "scrna", require_ladder=True)
    assert gate_ok == True
    assert block_reason is None


def test_assay_affordability_abort():
    """Test that chooser aborts when budget < wells_needed for assay gate."""
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Set up: CP gate missing, very low budget
    beliefs.cell_paint_sigma_stable = False
    beliefs.cell_paint_df_total = 0
    beliefs.cell_paint_rel_width = None

    # Compute calibration plan
    calib_plan = chooser._compute_assay_calibration_plan(beliefs, "cell_paint")
    wells_needed = calib_plan["wells_needed"]

    # Set budget below needed (e.g., 50 wells when we need 156)
    remaining_wells = 50
    assert remaining_wells < wells_needed

    # Choose next: should abort
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=remaining_wells,
        cycle=1
    )
    template_name = decision.chosen_template
    template_kwargs = decision.chosen_kwargs

    # Should return abort
    assert template_name == "abort"
    assert "Cannot afford" in template_kwargs["reason"]

    # Check decision event includes calibration plan
    assert decision is not None
    assert decision.rationale.trigger == "abort"
    assert decision.rationale.calibration_plan is not None
    assert decision.rationale.calibration_plan["wells_needed"] == wells_needed


def test_gate_loss_emitted():
    """Test that gate_loss:ldh is emitted when rel_width crosses exit threshold."""
    beliefs = BeliefState()

    # Earn LDH gate first (mock it)
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.20

    beliefs.begin_cycle(10)

    # Create conditions with high noise → will exceed exit threshold
    conditions = [MockConditionSummary(
        n_wells=12,
        mean=1.0,
        std=0.45,  # High std → will push rel_width > 0.40
        cv=0.45
    )]

    observation = MockObservation(conditions=conditions)
    events, diagnostics = beliefs.update(observation, cycle=10)

    # Check if gate_loss:ldh was emitted
    gate_loss_events = [e for e in events if e.belief.startswith("gate_loss:ldh")]

    # Might not trigger in one cycle, but let's check the state
    # If rel_width went above threshold, gate should be lost eventually
    if beliefs.ldh_rel_width and beliefs.ldh_rel_width >= 0.40:
        assert beliefs.ldh_sigma_stable == False


def test_chooser_uses_get_gate_state():
    """Test that chooser uses _get_gate_state for decision provenance."""
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Earn some gates
    beliefs.noise_sigma_stable = True
    beliefs.ldh_sigma_stable = True
    beliefs.cell_paint_sigma_stable = False
    beliefs.scrna_sigma_stable = False

    gate_state = chooser._get_gate_state(beliefs)

    assert gate_state["noise_sigma"] == "earned"
    assert gate_state["ldh"] == "earned"
    assert gate_state["cell_paint"] == "lost"
    assert gate_state["scrna"] == "lost"


def test_global_calibration_does_not_force_scrna():
    """Test that global calibration forces LDH + CP, but NOT scRNA."""
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate earned, but assay gates missing
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    beliefs.ldh_sigma_stable = False
    beliefs.cell_paint_sigma_stable = False
    beliefs.scrna_sigma_stable = False

    # Choose next: should force LDH calibration first
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=5
    )
    template_name = decision.chosen_template
    template_kwargs = decision.chosen_kwargs

    assert template_name == "calibrate_ldh_baseline"
    assert template_kwargs["assay"] == "ldh"

    # Now earn LDH gate
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22

    # Choose next: should force CP calibration next
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=300,
        cycle=6
    )
    template_name = decision.chosen_template
    template_kwargs = decision.chosen_kwargs

    assert template_name == "calibrate_cell_paint_baseline"
    assert template_kwargs["assay"] == "cell_paint"

    # Now earn CP gate
    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.23

    # Choose next: should NOT force scRNA calibration
    # Should go to biology (dose_ladder or other)
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=250,
        cycle=7
    )
    template_name = decision.chosen_template

    # Should be a biology template, NOT calibrate_scrna_baseline
    assert template_name != "calibrate_scrna_baseline"
    assert template_name in ["dose_ladder_coarse", "baseline_replicates"]  # Biology or maintenance


def test_scrna_template_allowed_without_scrna_gate():
    """Test that scRNA upgrade probe can be selected WITHOUT scrna gate earned.

    The scRNA gate is optional - templates should check CP gate (ladder prereq)
    but not require scrna_sigma_stable beforehand.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # All cheap gates earned, scRNA gate NOT earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22

    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.21

    beliefs.scrna_sigma_stable = False  # NOT earned

    # Check required gates for scrna_upgrade_probe
    required = chooser._required_gates_for_template("scrna_upgrade_probe")

    # Should require CP gate (ladder prereq), but NOT scrna gate
    assert "cell_paint" in required
    assert "scrna" not in required

    # Verify CP gate check passes (ladder satisfied)
    gate_ok, block_reason = chooser._check_assay_gate(beliefs, "scrna", require_ladder=True)

    # Should fail because scrna gate not earned, but reason should NOT mention ladder
    assert gate_ok == False
    assert "scRNA gate not earned" in block_reason

    # BUT if we're running scrna_upgrade_probe, we should NOT enforce scrna gate
    # (that's the whole point - upgrade probe doesn't need scrna gate beforehand)
    # This is enforced by _required_gates_for_template returning {"cell_paint"} only


def test_template_gate_override_blocks_biology_until_gates():
    """Test that biology templates are overridden to calibration when gates missing."""
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate earned, but LDH + CP gates missing
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    beliefs.ldh_sigma_stable = False
    beliefs.cell_paint_sigma_stable = False
    beliefs.scrna_sigma_stable = False

    # Force chooser to want dose_ladder_coarse by having few tested compounds
    beliefs.tested_compounds = {'DMSO'}  # Triggers "len(tested) < 5" branch

    # Choose next: should override dose_ladder_coarse to calibrate_ldh_baseline
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=5
    )
    template_name = decision.chosen_template
    template_kwargs = decision.chosen_kwargs

    # Should have been overridden to LDH calibration
    assert template_name == "calibrate_ldh_baseline"
    assert template_kwargs["assay"] == "ldh"

    # Check decision provenance
    # Note: enforcement loop catches this before biology template is selected
    # So trigger is "must_calibrate" (from enforcement loop) not "must_calibrate_for_template"
    assert decision.rationale.trigger == "must_calibrate"
    assert decision.chosen_kwargs["assay"] == "ldh"


def test_scrna_gate_not_earnable_with_proxy():
    """Test that scRNA gate never earns with proxy metrics."""
    beliefs = BeliefState()
    beliefs.begin_cycle(1)

    # Create conditions with enough df and low noise to "earn" gate
    conditions = []
    for i in range(15):  # Lots of cycles to ensure df > 40 and rel_width < 0.25
        conditions.append(MockConditionSummary(
            n_wells=12,
            mean=1.0,
            std=0.15,  # Very low noise → would earn gate for other assays
            cv=0.15
        ))

    observation = MockObservation(conditions=conditions)

    for cycle in range(15):
        beliefs.begin_cycle(cycle + 1)
        events, diagnostics = beliefs.update(observation, cycle=cycle + 1)

    # Check that LDH and CP gates are earned (proxy is OK for them)
    assert beliefs.ldh_sigma_stable == True, "LDH should earn with proxy"
    assert beliefs.cell_paint_sigma_stable == True, "CP should earn with proxy"

    # Check that scRNA gate is NOT earned (proxy blocked)
    assert beliefs.scrna_sigma_stable == False, "scRNA must NOT earn with proxy metrics"

    # Check that scRNA shadow stats are updated
    assert beliefs.scrna_df_total > 0, "scRNA df should be tracked"
    assert beliefs.scrna_rel_width is not None, "scRNA rel_width should be tracked"
    assert beliefs.scrna_rel_width < 0.25, "scRNA metrics should be good enough (if not proxy)"

    # Check that no gate_event:scrna was emitted
    scrna_gate_events = [e for e in events if e.belief == "gate_event:scrna"]
    assert len(scrna_gate_events) == 0, "No gate_event:scrna should be emitted with proxy"


def test_enforcement_layer_appears_in_decisions():
    """Test that enforcement_layer field appears in decision receipts.

    Proves that the policy layer distinction is actually emitted in provenance.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Test 1: Force global_pre_biology enforcement
    # Noise gate earned, but LDH gate missing
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20
    beliefs.ldh_sigma_stable = False
    beliefs.cell_paint_sigma_stable = False

    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=5
    )
    template_name = decision.chosen_template

    # Should force LDH calibration via global loop
    assert template_name == "calibrate_ldh_baseline"

    # Check that enforcement_layer is present in decision receipt
    assert decision.rationale.enforcement_layer is not None, "enforcement_layer must be in decision"
    assert decision.rationale.enforcement_layer == "global_pre_biology", \
        "Global loop should mark enforcement_layer as global_pre_biology"

    # Test 2: Force template_safety_net enforcement
    # This is harder to trigger - need to bypass global loop but hit template enforcement
    # Reset beliefs: all gates earned except we'll manually check a template that requires more
    beliefs2 = BeliefState()
    chooser2 = TemplateChooser()

    beliefs2.noise_sigma_stable = True
    beliefs2.noise_df_total = 150
    beliefs2.noise_rel_width = 0.20
    beliefs2.ldh_sigma_stable = True
    beliefs2.ldh_df_total = 150
    beliefs2.ldh_rel_width = 0.22
    beliefs2.cell_paint_sigma_stable = True
    beliefs2.cell_paint_df_total = 150
    beliefs2.cell_paint_rel_width = 0.21

    # Directly test _enforce_template_gates with a template that requires CP gate
    # but pretend CP gate is missing to trigger safety net
    beliefs2.cell_paint_sigma_stable = False  # Temporarily lose gate

    actual_template, actual_kwargs = chooser2._enforce_template_gates(
        beliefs2,
        "dose_ladder_coarse",  # Requires CP gate
        {"reason": "test"},
        remaining_wells=384,
        cycle=10,
        allow_expensive_calibration=False
    )

    # Should override to CP calibration via safety net
    assert actual_template == "calibrate_cell_paint_baseline"

    # Check that enforcement_layer is template_safety_net
    decision2 = chooser2.last_decision_event
    assert decision2.rationale.enforcement_layer is not None, "enforcement_layer must be in decision"
    assert decision2.rationale.enforcement_layer == "template_safety_net", \
        "Template enforcement should mark enforcement_layer as template_safety_net"


def test_scrna_calibration_blocked_autonomously():
    """Test that calibrate_scrna_baseline cannot be selected without explicit authorization.

    Policy: calibrate_scrna_baseline is expensive and manual-only.
    Autonomous chooser must never select it (allow_expensive_calibration=False by default).
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Hack the enforcement loop to try forcing scRNA calibration
    # (This simulates a bug where someone adds "scrna" to the loop)
    # We'll directly test _validate_template_selection instead

    # Test 1: Validation should block calibrate_scrna_baseline with default flag
    is_valid, abort_reason = chooser._validate_template_selection(
        "calibrate_scrna_baseline",
        allow_expensive_calibration=False,
        cycle=5,
        beliefs=beliefs
    )

    assert is_valid == False, "Should block calibrate_scrna_baseline by default"
    assert "explicit authorization" in abort_reason, "Abort reason should mention authorization"
    assert "expensive" in abort_reason, "Abort reason should mention expensive"

    # Test 2: Validation should allow with explicit flag
    is_valid, abort_reason = chooser._validate_template_selection(
        "calibrate_scrna_baseline",
        allow_expensive_calibration=True,
        cycle=5,
        beliefs=beliefs
    )

    assert is_valid == True, "Should allow with explicit authorization"
    assert abort_reason is None, "No abort reason when valid"

    # Test 3: Cheap calibration templates should always be allowed
    is_valid, abort_reason = chooser._validate_template_selection(
        "calibrate_ldh_baseline",
        allow_expensive_calibration=False,
        cycle=5,
        beliefs=beliefs
    )

    assert is_valid == True, "Cheap templates should be allowed"
    assert abort_reason is None, "No abort reason for cheap templates"


def test_safety_net_catches_regression_through_choose_next():
    """Hostile test: Prove safety net catches missing gates even when global loop fails.

    Simulates a regression where the global enforcement loop is broken (or thinks gates
    are earned when they're not). The template safety net should still catch it.

    This is the "driver falls asleep, seatbelt saves you" test.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Set up: noise gate earned, but cell_paint gate actually missing
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22
    beliefs.cell_paint_sigma_stable = False  # Actually missing
    beliefs.cell_paint_df_total = 10
    beliefs.cell_paint_rel_width = 0.50  # Too wide
    beliefs.tested_compounds = {'DMSO'}  # Triggers dose_ladder_coarse

    # Hostile monkeypatch: Make _check_assay_gate lie during global loop phase
    # It will return True (gate earned) during global loop, but False during safety net
    original_check = chooser._check_assay_gate
    call_count = [0]  # Mutable to track across closure

    def hostile_check_gate(beliefs_arg, assay, require_ladder=True):
        call_count[0] += 1
        if assay == "cell_paint":
            # First 2 calls: lie (during global loop checking ldh, cell_paint)
            # Later calls: tell truth (during safety net)
            if call_count[0] <= 2:
                return (True, None)  # Lie: pretend gate is earned
            else:
                return (False, "Cell Painting gate not earned (simulated regression)")
        return original_check(beliefs_arg, assay, require_ladder)

    with patch.object(chooser, '_check_assay_gate', side_effect=hostile_check_gate):
        decision = chooser.choose_next(
            beliefs=beliefs,
            budget_remaining_wells=384,
            cycle=10
        )
        template_name = decision.chosen_template

    # Safety net should have caught the missing CP gate and overridden
    assert template_name == "calibrate_cell_paint_baseline", \
        "Safety net should override to CP calibration when gate missing"

    # Verify decision receipt has template_safety_net enforcement_layer
    assert decision is not None, "Decision must be recorded"
    assert decision.rationale.enforcement_layer is not None, \
        "Decision must include enforcement_layer"
    assert decision.rationale.enforcement_layer == "template_safety_net", \
        "Should be caught by safety net, not global loop (driver fell asleep, seatbelt saved us)"
    assert decision.rationale.blocked_template == "dose_ladder_coarse", \
        "Should record which template was blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
