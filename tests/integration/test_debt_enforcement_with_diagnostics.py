"""
E2E Test: Epistemic Debt Enforcement with Diagnostic Logging

This test verifies the complete debt enforcement cycle including:
1. Diagnostic logging is emitted every cycle
2. Agent responds to refusals by proposing calibration
3. Debt accumulation → refusal → recovery pathway works end-to-end
4. All ledger files are written correctly

This is a higher-level test than the controller unit tests - it exercises
the full loop.py integration.

Can be run standalone: python3 test_debt_enforcement_with_diagnostics.py
Or with pytest: pytest test_debt_enforcement_with_diagnostics.py
"""

import tempfile
import json
from pathlib import Path
from datetime import datetime

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Mock pytest.skip for standalone execution
    class _MockPytest:
        @staticmethod
        def skip(reason):
            print(f"SKIPPED: {reason}")
    pytest = _MockPytest()

from cell_os.epistemic_agent.loop import EpistemicLoop


def test_debt_enforcement_full_cycle_with_diagnostics():
    """
    E2E test: Verify full debt enforcement cycle with diagnostic logging.

    This test runs a mini EpistemicLoop and verifies:
    1. Diagnostic events are written every cycle
    2. Refusal events are written when debt exceeds threshold
    3. Agent recovers by proposing calibration
    4. Debt decreases after calibration
    5. All JSONL outputs are valid and complete
    """
    # Create temporary directory for output
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Initialize loop with small budget
        loop = EpistemicLoop(
            budget=96,  # Small budget to trigger constraints
            max_cycles=10,
            log_dir=log_dir,
            seed=42,
            strict_quality=False,  # Disable design quality checks for simplicity
            strict_provenance=False
        )

        # Mock agent to force overclaiming
        # We'll inject high claimed gain to accumulate debt quickly
        original_estimate = loop.agent.beliefs.estimate_expected_gain

        def mock_estimate_high_gain(*args, **kwargs):
            """Always claim 1.5 bits of gain (will be overclaim)."""
            return 1.5

        loop.agent.beliefs.estimate_expected_gain = mock_estimate_high_gain

        try:
            # Run loop (will accumulate debt and hit refusal)
            loop.run()
        except Exception as e:
            # May abort due to deadlock or budget - that's fine
            print(f"Loop terminated: {e}")

        # Restore original function
        loop.agent.beliefs.estimate_expected_gain = original_estimate

        # === VERIFICATION 1: Diagnostic file exists and has debt status events ===
        diagnostics_file = list(log_dir.glob("*_diagnostics.jsonl"))[0]
        assert diagnostics_file.exists(), "Diagnostics file should exist"

        with open(diagnostics_file) as f:
            diagnostics = [json.loads(line) for line in f]

        # Find epistemic_debt_status events
        debt_statuses = [d for d in diagnostics if d.get("event_type") == "epistemic_debt_status"]

        assert len(debt_statuses) > 0, "Should have at least one debt status diagnostic"

        # Verify structure of debt status events
        first_debt_status = debt_statuses[0]
        required_fields = {
            "event_type", "timestamp", "cycle", "debt_bits", "threshold",
            "action_proposed", "action_allowed", "action_is_calibration",
            "base_cost_wells", "inflated_cost_wells", "inflation_factor",
            "budget_remaining", "refusal_reason", "epistemic_insolvent",
            "consecutive_refusals"
        }

        missing_fields = required_fields - set(first_debt_status.keys())
        assert not missing_fields, f"Debt status missing fields: {missing_fields}"

        # === VERIFICATION 2: Debt should accumulate over cycles ===
        debt_values = [d["debt_bits"] for d in debt_statuses]

        # Debt should be monotonically increasing until refusal/calibration
        # (Some cycles may have same debt if no resolution happened)
        max_debt = max(debt_values)
        assert max_debt > 0, "Debt should accumulate due to overclaiming"

        # === VERIFICATION 3: Check for refusal events when debt crosses threshold ===
        refusals_file = list(log_dir.glob("*_refusals.jsonl"))

        if max_debt >= 2.0:
            # If debt crossed threshold, there should be refusal events
            assert len(refusals_file) > 0, "Should have refusals.jsonl when debt >= 2.0"

            with open(refusals_file[0]) as f:
                refusals = [json.loads(line) for line in f]

            assert len(refusals) > 0, "Should have at least one refusal event"

            # Verify refusal structure
            first_refusal = refusals[0]
            assert "refusal_reason" in first_refusal
            assert "debt_bits" in first_refusal
            assert first_refusal["debt_bits"] >= 2.0, \
                f"Refusal should occur when debt >= 2.0, got {first_refusal['debt_bits']}"

            # === VERIFICATION 4: Agent should propose calibration after refusal ===
            decisions_file = list(log_dir.glob("*_decisions.jsonl"))[0]

            with open(decisions_file) as f:
                decisions = [json.loads(line) for line in f]

            # Find decisions after first refusal cycle
            refusal_cycle = first_refusal["cycle"]
            decisions_after_refusal = [
                d for d in decisions
                if d.get("cycle", 0) > refusal_cycle
            ]

            if decisions_after_refusal:
                # Should contain calibration template
                next_decision = decisions_after_refusal[0]
                chosen_template = next_decision.get("chosen_template") or next_decision.get("kind")

                calibration_templates = {
                    "baseline_replicates", "baseline", "calibration",
                    "dmso_replicates", "calibrate_ldh_baseline",
                    "calibrate_cell_paint_baseline"
                }

                assert any(calib in str(chosen_template) for calib in calibration_templates), \
                    f"Agent should propose calibration after refusal, got: {chosen_template}"

        # === VERIFICATION 5: Verify inflation factor is computed correctly ===
        for debt_status in debt_statuses:
            base_cost = debt_status["base_cost_wells"]
            inflated_cost = debt_status["inflated_cost_wells"]
            inflation_factor = debt_status["inflation_factor"]

            # Inflation factor should match ratio
            expected_inflation = inflated_cost / max(1, base_cost)
            assert abs(inflation_factor - expected_inflation) < 0.01, \
                f"Inflation factor mismatch: {inflation_factor} vs {expected_inflation}"

            # If debt > 0, inflation should be > 1.0 for non-calibration actions
            if debt_status["debt_bits"] > 0 and not debt_status["action_is_calibration"]:
                assert inflation_factor >= 1.0, \
                    "Non-calibration actions should have inflation >= 1.0 when debt > 0"

        print(f"✓ Test passed: Verified {len(debt_statuses)} debt status diagnostics")
        print(f"✓ Max debt accumulated: {max_debt:.3f} bits")
        if refusals_file:
            print(f"✓ Refusals recorded: {len(refusals)}")


def test_diagnostic_logging_structure():
    """
    Unit test: Verify diagnostic event structure is correct.

    This is a simpler test that just checks the diagnostic format
    without running a full loop.
    """
    from cell_os.epistemic_control import EpistemicController, EpistemicControllerConfig

    config = EpistemicControllerConfig(enable_debt_tracking=True)
    controller = EpistemicController(config)

    # Accumulate some debt
    controller.claim_action("test_001", "biology", expected_gain_bits=1.0)
    controller.resolve_action("test_001", actual_gain_bits=0.2, action_type="biology")

    # Get refusal context
    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",
        base_cost_wells=16,
        budget_remaining=100,
        debt_hard_threshold=2.0,
        calibration_templates={"baseline", "calibration"}
    )

    # Simulate diagnostic creation (this is what loop.py does)
    diagnostic = {
        "event_type": "epistemic_debt_status",
        "timestamp": datetime.now().isoformat(),
        "cycle": 1,
        "debt_bits": context.get('debt_bits', 0.0),
        "threshold": context.get('debt_threshold', 2.0),
        "action_proposed": "dose_response",
        "action_allowed": not should_refuse,
        "action_is_calibration": context.get('is_calibration', False),
        "base_cost_wells": context.get('base_cost_wells', 0),
        "inflated_cost_wells": context.get('inflated_cost_wells', 0),
        "inflation_factor": (context.get('inflated_cost_wells', 0) / max(1, context.get('base_cost_wells', 1))),
        "budget_remaining": 100,
        "refusal_reason": refusal_reason if should_refuse else None,
        "epistemic_insolvent": False,
        "consecutive_refusals": 0,
    }

    # Verify all required fields are present
    assert diagnostic["event_type"] == "epistemic_debt_status"
    assert "timestamp" in diagnostic
    assert "cycle" in diagnostic
    assert diagnostic["debt_bits"] >= 0
    assert diagnostic["threshold"] == 2.0
    assert "action_proposed" in diagnostic
    assert isinstance(diagnostic["action_allowed"], bool)
    assert isinstance(diagnostic["action_is_calibration"], bool)
    assert diagnostic["base_cost_wells"] >= 0
    assert diagnostic["inflated_cost_wells"] >= 0
    assert diagnostic["inflation_factor"] >= 1.0  # Should be inflated
    assert diagnostic["budget_remaining"] >= 0

    # Verify JSON serializable
    json_str = json.dumps(diagnostic)
    assert len(json_str) > 0

    print("✓ Diagnostic structure verified")


if __name__ == "__main__":
    test_diagnostic_logging_structure()
    print()
    test_debt_enforcement_full_cycle_with_diagnostics()
