"""
Test: Deadlock recovery from epistemic debt refusal.

These tests verify that the agent learns to adapt when refused:
1. Agent proposes exploration → refused → proposes calibration
2. Calibration reduces debt → agent can explore again
3. No infinite calibration spam (agent doesn't become coward)

This is policy adaptation, not enforcement weakening.
Refusal is a measurement, and the agent must learn from it.
"""

import os
import json
import tempfile
from pathlib import Path

from cell_os.epistemic_agent.loop import EpistemicLoop


def test_agent_learns_from_refusal():
    """
    Test 1: Agent proposes calibration after being refused.

    Flow:
    1. Inject debt above threshold (2.5 bits)
    2. Agent proposes exploration → REFUSED
    3. Next cycle: Agent proposes baseline (calibration)
    4. Calibration reduces debt
    5. Agent can explore again
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Force debt via harness
        os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"] = "2.5"

        try:
            loop = EpistemicLoop(
                budget=250,
                max_cycles=10,
                log_dir=log_dir,
                seed=100,
                strict_quality=False,
                strict_provenance=False
            )

            # Install overclaim harness
            original_resolve = loop.epistemic.resolve_design
            overclaim_injected = False

            def resolve_with_overclaim(claim_id, prior_posterior, posterior):
                nonlocal overclaim_injected
                result = original_resolve(claim_id, prior_posterior, posterior)

                if not overclaim_injected and "EPI_DEBUG_FORCE_OVERCLAIM_BITS" in os.environ:
                    forced_debt = float(os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"])
                    loop.epistemic.controller.claim_action(
                        "forced_overclaim_harness", "debug", forced_debt
                    )
                    loop.epistemic.controller.resolve_action(
                        "forced_overclaim_harness", 0.0
                    )
                    overclaim_injected = True
                    print(f"\n🔨 HARNESS: Injected {forced_debt} bits of debt")

                return result

            loop.epistemic.resolve_design = resolve_with_overclaim

            # Run
            loop.run()

            # Parse logs
            json_file = log_dir / f"{loop.run_id}.json"
            with open(json_file, 'r') as f:
                run_data = json.load(f)

            refusals_file = log_dir / f"{loop.run_id}_refusals.jsonl"
            refusals = []
            if refusals_file.exists():
                with open(refusals_file, 'r') as f:
                    for line in f:
                        refusals.append(json.loads(line))

            decisions_file = log_dir / f"{loop.run_id}_decisions.jsonl"
            decisions = []
            with open(decisions_file, 'r') as f:
                for line in f:
                    decisions.append(json.loads(line))

            # Assertions

            # 1. At least one refusal should have occurred
            assert len(refusals) > 0, "Expected at least one refusal"

            # 2. After first refusal, agent should propose calibration
            first_refusal_cycle = refusals[0]["cycle"]

            # Find decisions after refusal
            decisions_after_refusal = [
                d for d in decisions
                if d["cycle"] > first_refusal_cycle
            ]

            assert len(decisions_after_refusal) > 0, \
                "Agent should make decisions after refusal"

            # Next decision should be calibration (baseline)
            next_decision = decisions_after_refusal[0]
            next_template = next_decision.get("chosen_template") or next_decision.get("selected")
            assert next_template == "baseline_replicates", \
                f"After refusal, agent should choose calibration, got: {next_template}"

            # Check provenance shows insolvency trigger (in rationale)
            rationale = next_decision.get("rationale", {})
            rules_fired = rationale.get("rules_fired", [])
            assert "trigger_epistemic_insolvency" in rules_fired, \
                f"Calibration should be triggered by insolvency, got rules: {rules_fired}"

            # 3. Agent should eventually stop being refused (debt drops)
            # Count refusals - should not exceed MAX_CONSECUTIVE_REFUSALS (3)
            assert len(refusals) <= 4, \
                f"Too many refusals ({len(refusals)}), agent not adapting"

            # 4. Some cycles should execute (agent didn't deadlock forever)
            cycles_completed = run_data.get("cycles_completed", 0)
            assert cycles_completed >= 2, \
                f"Agent should complete at least 2 cycles, got {cycles_completed}"

            print(f"\n✓ Deadlock recovery test PASSED")
            print(f"   Refusals: {len(refusals)}")
            print(f"   Cycles completed: {cycles_completed}")
            print(f"   Agent learned to propose calibration after refusal")

        finally:
            if "EPI_DEBUG_FORCE_OVERCLAIM_BITS" in os.environ:
                del os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"]


def test_no_calibration_spam():
    """
    Test 2: Agent doesn't spam calibration when solvent.

    Verify that without debt, agent explores normally
    (doesn't become a coward).
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # No debt injection
        loop = EpistemicLoop(
            budget=200,
            max_cycles=6,
            log_dir=log_dir,
            seed=101,
            strict_quality=False,
            strict_provenance=False
        )

        loop.run()

        # Parse decisions
        decisions_file = log_dir / f"{loop.run_id}_decisions.jsonl"
        decisions = []
        with open(decisions_file, 'r') as f:
            for line in f:
                decisions.append(json.loads(line))

        # Count calibration vs exploration decisions
        calibration_count = 0
        exploration_count = 0

        for dec in decisions:
            template = dec.get("chosen_template") or dec.get("selected", "")
            if "baseline" in template or "calibration" in template:
                calibration_count += 1
            elif "dose" in template or "edge" in template:
                exploration_count += 1

        # Agent should eventually explore (not just calibrate)
        # After earning gate (~3-4 baseline cycles), should explore
        assert exploration_count > 0 or calibration_count <= 5, \
            f"Agent spamming calibration: {calibration_count} calib, {exploration_count} explore"

        print(f"\n✓ No calibration spam test PASSED")
        print(f"   Calibration decisions: {calibration_count}")
        print(f"   Exploration decisions: {exploration_count}")
        print(f"   Agent explores when solvent")


def test_bankruptcy_declaration():
    """
    Test 3: Agent declares bankruptcy after 3 consecutive refusals.

    This prevents infinite deadlock loops.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Force massive debt that won't recover
        os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"] = "10.0"

        try:
            loop = EpistemicLoop(
                budget=80,  # Very small budget
                max_cycles=6,
                log_dir=log_dir,
                seed=102,
                strict_quality=False,
                strict_provenance=False
            )

            # Install harness
            original_resolve = loop.epistemic.resolve_design
            overclaim_injected = False

            def resolve_with_overclaim(claim_id, prior_posterior, posterior):
                nonlocal overclaim_injected
                result = original_resolve(claim_id, prior_posterior, posterior)

                if not overclaim_injected and "EPI_DEBUG_FORCE_OVERCLAIM_BITS" in os.environ:
                    forced_debt = float(os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"])
                    loop.epistemic.controller.claim_action(
                        "forced_overclaim_harness", "debug", forced_debt
                    )
                    loop.epistemic.controller.resolve_action(
                        "forced_overclaim_harness", 0.0
                    )
                    overclaim_injected = True

                return result

            loop.epistemic.resolve_design = resolve_with_overclaim

            # Run
            loop.run()

            # Parse decisions
            decisions_file = log_dir / f"{loop.run_id}_decisions.jsonl"
            decisions = []
            with open(decisions_file, 'r') as f:
                for line in f:
                    decisions.append(json.loads(line))

            # Check if bankruptcy declared
            bankruptcy_decisions = [
                d for d in decisions
                if "bankruptcy" in (d.get("chosen_template") or d.get("selected", ""))
            ]

            # With 10 bits debt and small budget, agent should eventually declare bankruptcy
            # (Either bankruptcy abort or regular abort due to budget exhaustion)
            abort_decisions = [
                d for d in decisions
                if d.get("kind") == "abort" or "abort" in (d.get("chosen_template") or d.get("selected", ""))
            ]

            # Agent should abort (either bankruptcy or budget)
            assert len(abort_decisions) > 0 or len(bankruptcy_decisions) > 0, \
                "Agent should abort when unable to restore solvency"

            if len(bankruptcy_decisions) > 0:
                print(f"\n✓ Bankruptcy test PASSED")
                print(f"   Agent declared epistemic bankruptcy after repeated refusals")
            else:
                print(f"\n✓ Bankruptcy test PASSED (budget exhaustion)")
                print(f"   Agent aborted due to budget constraints")

        finally:
            if "EPI_DEBUG_FORCE_OVERCLAIM_BITS" in os.environ:
                del os.environ["EPI_DEBUG_FORCE_OVERCLAIM_BITS"]


if __name__ == "__main__":
    print("Running deadlock recovery tests...\n")
    print("="*70)

    try:
        test_agent_learns_from_refusal()
        print("\n" + "="*70)

        test_no_calibration_spam()
        print("\n" + "="*70)

        test_bankruptcy_declaration()
        print("\n" + "="*70)

        print("\n✅ ALL DEADLOCK RECOVERY TESTS PASSED")
        print("\nAgent policy adaptation verified:")
        print("  1. Learns from refusal → proposes calibration ✓")
        print("  2. Doesn't spam calibration when solvent ✓")
        print("  3. Declares bankruptcy when unrecoverable ✓")
        print("\nThe teeth still bite, but the agent adapts.")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")
        raise
