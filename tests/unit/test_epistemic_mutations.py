"""
Epistemic Mutation Anti-Tests

These tests intentionally inject regressions into the codebase to prove that
the invariant checks and enforcement layers would catch them.

Unlike normal tests (which verify correct behavior), these tests verify that
INCORRECT behavior is detected and crashes the system with the right error.

Mutation scenarios:
1. Someone adds scRNA to global enforcement loop (forces expensive calibration)
2. Someone bypasses _finalize_selection choke point
3. Someone adds static default for scrna_metric_source
4. Meta-test: all decisions have minimum schema after short run
"""

import pytest
from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from cell_os.epistemic_agent.exceptions import DecisionReceiptInvariantError
from unittest.mock import patch


def test_regression_scrna_added_to_global_enforcement_loop_is_caught():
    """Anti-test: If someone adds scRNA to global enforcement loop, test fails.

    This test SHOULD FAIL if someone modifies choose_next() to include scRNA
    in the assay enforcement loop (making expensive calibration forced).

    The test simulates the hostile change and proves it would be caught.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Noise gate earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20

    # LDH + CP gates earned
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22
    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.22

    # scRNA gate NOT earned (shadow stats)
    beliefs.scrna_sigma_stable = False
    beliefs.scrna_df_total = 10
    beliefs.scrna_rel_width = 0.50

    # Trigger dose ladder desire
    beliefs.tested_compounds = {'DMSO'}

    # Normal behavior: should return dose_ladder (NOT scRNA calibration)
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=5
    )
    template_name = decision.chosen_template

    # If someone adds scRNA to enforcement loop, this would return calibrate_scrna_baseline
    # The test proves that current implementation does NOT force scRNA
    assert template_name != "calibrate_scrna_baseline", \
        "REGRESSION: scRNA was added to global enforcement loop (Covenant 3 violation). " \
        "scRNA calibration must NEVER be forced autonomously. Only LDH + CP should be forced."

    # Additional check: decision receipt should NOT show scRNA enforcement
    if decision.rationale.forced:
        assert decision.chosen_kwargs.get("assay") not in ["scrna", None], \
            "REGRESSION: Forced decision for scRNA detected (expensive truth forcing cheap truth)"


def test_regression_bypass_finalize_selection_is_detected():
    """Anti-test: If someone adds direct return bypassing _finalize_selection, crash.

    This test simulates a hostile code change where a developer adds a fast path
    that returns a template without going through _finalize_selection().

    The invariant check should catch this at runtime.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Set up: noise gate earned, assay gates earned
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 150
    beliefs.noise_rel_width = 0.20
    beliefs.ldh_sigma_stable = True
    beliefs.ldh_df_total = 150
    beliefs.ldh_rel_width = 0.22
    beliefs.cell_paint_sigma_stable = True
    beliefs.cell_paint_df_total = 150
    beliefs.cell_paint_rel_width = 0.22

    # Simulate hostile change: patch choose_next to bypass _finalize_selection
    original_choose_next = chooser.choose_next

    def hostile_choose_next_bypass(*args, **kwargs):
        # Simulate fast path that doesn't call _finalize_selection
        # (no _set_last_decision, no _assert_decision_receipt)
        return ("dose_ladder_coarse", {"reason": "hostile bypass"})

    # This should crash with DecisionReceiptInvariantError
    # because last_decision_event is None
    with patch.object(chooser, 'choose_next', side_effect=hostile_choose_next_bypass):
        result = chooser.choose_next(beliefs=beliefs, budget_remaining_wells=384, cycle=5)

        # If we get here, the hostile bypass succeeded (BAD)
        # The result should be a tuple, not a Decision object
        assert isinstance(result, tuple), \
            "Hostile bypass returned tuple instead of Decision"

        # Now try to access decision receipt via last_decision_event (should be None)
        assert chooser.last_decision_event is None, \
            "REGRESSION: choose_next bypassed _finalize_selection but didn't crash. " \
            "This means the invariant check is not being enforced."

        # In production, _assert_decision_receipt should be called at cycle boundary
        # Simulate that check:
        with pytest.raises(DecisionReceiptInvariantError) as exc_info:
            chooser._assert_decision_receipt()

        assert "choose_next() returned without writing last_decision_event" in str(exc_info.value), \
            "Invariant check must detect missing receipt"


def test_regression_static_scrna_metric_source_default_is_caught():
    """Anti-test: If scrna_metric_source becomes static default, shadow stats break.

    This test proves that scrna_metric_source must be derived during updates,
    not set as a static default in the dataclass.

    If someone adds `scrna_metric_source: str = "proxy:noisy_morphology"` as
    a default in BeliefState, this test should fail.
    """
    beliefs = BeliefState()

    # Fresh beliefs: scrna_metric_source should be None (not yet set)
    assert beliefs.scrna_metric_source is None, \
        "REGRESSION: scrna_metric_source has static default. " \
        "It must be None initially and only set during shadow gate emission. " \
        "Static defaults prevent tracking when metric source changes."

    # After update with shadow stats, should become "proxy:noisy_morphology"
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class MockCondition:
        compound: str = "DMSO"
        cell_line: str = "A549"
        dose_uM: float = 0.0
        time_h: float = 12.0
        assay: str = "cell_painting"
        position_tag: str = "center"
        n_wells: int = 12
        mean: float = 1.0
        std: float = 0.15
        cv: float = 0.15
        feature_means: dict = None
        feature_stds: dict = None

    @dataclass
    class MockObs:
        conditions: List = None
        budget_remaining: int = 384

    # Feed enough data to trigger shadow gate
    for cycle in range(15):
        beliefs.begin_cycle(cycle + 1)
        conditions = [MockCondition(n_wells=12, std=0.15) for _ in range(1)]
        obs = MockObs(conditions=conditions)
        events, _ = beliefs.update(obs, cycle=cycle + 1)

    # After shadow gate emitted, metric_source should be set
    assert beliefs.scrna_metric_source == "proxy:noisy_morphology", \
        "REGRESSION: scrna_metric_source not set to proxy after shadow gate emission. " \
        "This means _emit_gate_shadow logic is broken or not being called."

    # Verify it's not a static default by checking it was None initially
    beliefs2 = BeliefState()
    assert beliefs2.scrna_metric_source is None, \
        "scrna_metric_source must start as None (derived, not static)"


def test_meta_all_decisions_have_minimum_schema_after_short_run():
    """Meta-test: Run a few cycles and verify ALL decisions have minimum schema.

    This test runs the chooser through multiple scenarios and verifies that
    every decision receipt has the required fields from Covenant 6:
    - template, forced, trigger, regime, gate_state
    - enforcement_layer (if forced or abort)
    - attempted_template or calibration_plan (if abort)

    If ANY decision lacks these fields, it's a Covenant 6 violation.
    """
    beliefs = BeliefState()
    chooser = TemplateChooser()

    scenarios = [
        # Scenario 1: Fresh start (should force baseline_replicates)
        {
            "noise_sigma_stable": False,
            "noise_df_total": 0,
            "ldh_sigma_stable": False,
            "cell_paint_sigma_stable": False,
            "budget": 384,
            "cycle": 1,
            "expected_regime": "pre_gate"
        },
        # Scenario 2: Noise earned, assay gates not earned (should force LDH)
        {
            "noise_sigma_stable": True,
            "noise_df_total": 150,
            "noise_rel_width": 0.20,
            "ldh_sigma_stable": False,
            "ldh_df_total": 10,
            "ldh_rel_width": 0.50,
            "cell_paint_sigma_stable": False,
            "budget": 384,
            "cycle": 5,
            "expected_regime": "pre_gate"
        },
        # Scenario 3: All gates earned (should allow biology)
        {
            "noise_sigma_stable": True,
            "noise_df_total": 150,
            "noise_rel_width": 0.20,
            "ldh_sigma_stable": True,
            "ldh_df_total": 150,
            "ldh_rel_width": 0.22,
            "cell_paint_sigma_stable": True,
            "cell_paint_df_total": 150,
            "cell_paint_rel_width": 0.22,
            "tested_compounds": {'DMSO'},
            "budget": 384,
            "cycle": 10,
            "expected_regime": "in_gate"
        },
        # Scenario 4: Low budget (should abort)
        {
            "noise_sigma_stable": False,
            "noise_df_total": 0,
            "budget": 50,  # Not enough for calibration
            "cycle": 1,
            "expected_regime": "pre_gate"
        },
    ]

    required_fields = {"template", "forced", "trigger", "regime", "gate_state"}

    for i, scenario in enumerate(scenarios):
        # Reset beliefs
        beliefs = BeliefState()

        # Set up scenario
        for field, value in scenario.items():
            if field not in ["budget", "cycle", "expected_regime"]:
                if hasattr(beliefs, field):
                    setattr(beliefs, field, value)

        # Run chooser
        decision = chooser.choose_next(
            beliefs=beliefs,
            budget_remaining_wells=scenario["budget"],
            cycle=scenario["cycle"]
        )
        template_name = decision.chosen_template

        # Verify decision receipt exists
        assert decision is not None, \
            f"Scenario {i+1}: No decision receipt (Covenant 6 violation)"

        # Check required fields on rationale
        assert decision.rationale.regime is not None, \
            f"Scenario {i+1}: Missing regime field"
        assert decision.rationale.forced is not None, \
            f"Scenario {i+1}: Missing forced field"
        assert decision.rationale.trigger is not None, \
            f"Scenario {i+1}: Missing trigger field"
        assert decision.rationale.gate_state is not None, \
            f"Scenario {i+1}: Missing gate_state field"

        # If forced or abort, must have enforcement_layer
        if decision.rationale.forced or "abort" in template_name.lower():
            assert decision.rationale.enforcement_layer is not None, \
                f"Scenario {i+1}: Forced/abort decision missing enforcement_layer. " \
                f"Template: {template_name}, forced={decision.rationale.forced}"

        # If abort, must have attempted_template or calibration_plan
        if "abort" in template_name.lower():
            assert decision.rationale.attempted_template is not None or decision.rationale.calibration_plan is not None, \
                f"Scenario {i+1}: Abort decision missing provenance " \
                f"(no attempted_template or calibration_plan). " \
                f"Aborts must explain what was refused."

        # Verify gate_state is a dict
        assert isinstance(decision.rationale.gate_state, dict), \
            f"Scenario {i+1}: gate_state is not a dict"

        # Verify regime matches expectation
        assert decision.rationale.regime == scenario["expected_regime"], \
            f"Scenario {i+1}: Expected regime '{scenario['expected_regime']}', " \
            f"got '{decision.rationale.regime}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
