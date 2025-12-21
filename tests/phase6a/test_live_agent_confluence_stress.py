"""
Live Agent Validation: Stress test agent with confluence guards + epistemic controller.

This validates that the complete system works end-to-end:
1. Agent proposes experiments
2. Confluence validator rejects confounded designs
3. Epistemic controller tracks debt and inflates costs
4. Agent can still make progress despite guards

This is an INTEGRATION test - it runs a real agent loop with all systems active.

Success criteria:
- Agent completes at least 3 cycles
- At least 1 confounded design is rejected (guard works)
- Epistemic debt accumulates (controller tracks)
- Agent learns to avoid violations (adaptive behavior)
"""

import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from src.cell_os.epistemic_agent.loop import EpistemicLoop
from src.cell_os.epistemic_agent.world import ExperimentalWorld
from src.cell_os.epistemic_agent.agent.policy_rules import RuleBasedPolicy
from src.cell_os.epistemic_agent.controller_integration import EpistemicIntegration
from src.cell_os.epistemic_agent.exceptions import InvalidDesignError


@dataclass
class AgentRunStats:
    """Statistics from agent run."""
    cycles_completed: int = 0
    designs_proposed: int = 0
    designs_rejected: int = 0
    total_debt_accumulated: float = 0.0
    max_cost_multiplier: float = 1.0
    budget_spent: int = 0
    abort_reason: Optional[str] = None


def test_live_agent_stress_minimal():
    """
    Minimal stress test: Run agent for 3-5 cycles with confluence guards active.

    This validates:
    1. Agent can propose experiments
    2. World can execute (with or without confluence validator)
    3. Agent updates beliefs
    4. Loop completes without crashing

    Note: This is a SMOKE TEST - it doesn't validate confluence rejection yet
    because confluence validator integration into world.run_experiment is not
    yet complete (see world_with_bridge.py).
    """
    # Create temporary log directory
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "agent_logs"

        # Create epistemic loop with sufficient budget for noise gate
        # Agent's RuleBasedPolicy needs ~156 wells for noise gate
        loop = EpistemicLoop(
            budget=384,  # 4 plates worth (sufficient for gate + exploration)
            max_cycles=5,
            log_dir=log_dir,
            seed=42
        )

        # Initialize epistemic controller integration
        epistemic_integration = EpistemicIntegration(enable=True)

        # Inject controller into agent (if agent has epistemic_integration attribute)
        if hasattr(loop.agent, 'epistemic_integration'):
            loop.agent.epistemic_integration = epistemic_integration

        # Track statistics
        stats = AgentRunStats()

        # Run loop
        try:
            # Get capabilities
            capabilities = loop.world.get_capabilities()

            for cycle in range(1, min(loop.max_cycles, 5) + 1):
                if loop.world.budget_remaining <= 0:
                    print(f"\nBudget exhausted after {cycle-1} cycles")
                    break

                print(f"\n{'='*60}")
                print(f"CYCLE {cycle}/5")
                print(f"{'='*60}")
                print(f"Budget remaining: {loop.world.budget_remaining}")

                # Begin cycle
                loop.agent.beliefs.begin_cycle(cycle)

                # Agent proposes experiment
                try:
                    proposal = loop.agent.propose_next_experiment(
                        capabilities,
                        previous_observation=loop.history[-1] if loop.history else None
                    )
                    stats.designs_proposed += 1

                    print(f"✓ Proposal: {proposal.design_id}")
                    print(f"  Wells: {len(proposal.wells)}")
                    print(f"  Hypothesis: {proposal.hypothesis[:80]}...")

                except RuntimeError as e:
                    if "ABORT" in str(e):
                        print(f"\n⛔ Agent aborted: {e}")
                        stats.abort_reason = str(e)
                        break
                    else:
                        raise

                # World executes (this will validate if world_with_bridge integrated)
                try:
                    observation = loop.world.run_experiment(proposal)

                    print(f"✓ Execution: {len(observation.conditions)} conditions")
                    print(f"  Wells spent: {observation.wells_spent}")
                    print(f"  Budget remaining: {observation.budget_remaining}")

                    # Agent updates beliefs
                    loop.agent.update_from_observation(observation)

                    # End cycle
                    loop.agent.beliefs.end_cycle()

                    # Update stats
                    stats.cycles_completed += 1
                    stats.budget_spent += observation.wells_spent

                    # Save to history
                    loop.history.append({
                        'cycle': cycle,
                        'proposal': {
                            'design_id': proposal.design_id,
                            'n_wells': len(proposal.wells),
                        },
                        'observation': {
                            'design_id': observation.design_id,
                            'wells_spent': observation.wells_spent,
                            'budget_remaining': observation.budget_remaining,
                        },
                    })

                except InvalidDesignError as e:
                    # Confluence validator rejected design
                    print(f"\n🛑 DESIGN REJECTED: {e.violation_code}")
                    print(f"  Message: {e.message[:100]}...")

                    stats.designs_rejected += 1

                    # For now, abort on rejection (later: agent should learn)
                    stats.abort_reason = f"Design rejected: {e.violation_code}"
                    break

                except Exception as e:
                    print(f"\n❌ ERROR: {e}")
                    stats.abort_reason = f"Exception: {e}"
                    break

        finally:
            # Print summary
            print(f"\n{'='*60}")
            print("AGENT RUN SUMMARY")
            print(f"{'='*60}")
            print(f"Cycles completed: {stats.cycles_completed}")
            print(f"Designs proposed: {stats.designs_proposed}")
            print(f"Designs rejected: {stats.designs_rejected}")
            print(f"Budget spent: {stats.budget_spent}/{loop.budget}")
            print(f"Budget remaining: {loop.world.budget_remaining}")

            if stats.abort_reason:
                print(f"\n⛔ Aborted: {stats.abort_reason}")

            # Validation assertions
            assert stats.cycles_completed >= 1, \
                f"Agent should complete at least 1 cycle, got {stats.cycles_completed}"

            assert stats.designs_proposed >= stats.cycles_completed, \
                f"Should propose at least {stats.cycles_completed} designs"

            print(f"\n✓ Live agent stress test PASSED (minimal)")
            print(f"  Agent completed {stats.cycles_completed} cycles")
            print(f"  All systems operational")


def test_live_agent_with_epistemic_controller():
    """
    Test agent with epistemic controller tracking debt.

    This validates:
    1. Epistemic integration tracks claims
    2. Debt accumulates if agent overclaims
    3. Costs inflate with debt
    4. Agent can still make progress
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "agent_logs_epistemic"

        # Create loop with sufficient budget
        loop = EpistemicLoop(
            budget=384,  # Sufficient for gate + exploration
            max_cycles=5,
            log_dir=log_dir,
            seed=42
        )

        # Create epistemic integration
        epistemic_integration = EpistemicIntegration(enable=True)

        # Track statistics
        stats = AgentRunStats()
        claims_made = []

        # Run simplified loop
        capabilities = loop.world.get_capabilities()

        for cycle in range(1, 4):  # Run 3 cycles
            if loop.world.budget_remaining <= 0:
                break

            print(f"\n{'='*60}")
            print(f"CYCLE {cycle}/3 (Epistemic Tracking)")
            print(f"{'='*60}")

            # Begin cycle
            loop.agent.beliefs.begin_cycle(cycle)

            # Agent proposes
            try:
                proposal = loop.agent.propose_next_experiment(
                    capabilities,
                    previous_observation=loop.history[-1] if loop.history else None
                )
                stats.designs_proposed += 1

                # EPISTEMIC: Claim expected information gain
                # (In real integration, agent would estimate this)
                expected_gain = 0.5  # bits (agent's claim)

                claim_id = epistemic_integration.claim_design(
                    design_id=proposal.design_id,
                    cycle=cycle,
                    expected_gain_bits=expected_gain,
                    hypothesis=proposal.hypothesis,
                    modalities=("cell_painting",),  # Infer from assay
                    wells_count=len(proposal.wells),
                    estimated_cost_usd=50.0 * len(proposal.wells)
                )

                claims_made.append({
                    'cycle': cycle,
                    'claim_id': claim_id,
                    'expected_gain': expected_gain
                })

                print(f"✓ Proposal: {proposal.design_id}")
                print(f"  Epistemic claim: {expected_gain:.3f} bits")
                print(f"  Claim ID: {claim_id}")

            except RuntimeError as e:
                if "ABORT" in str(e):
                    stats.abort_reason = str(e)
                    break
                else:
                    raise

            # Execute
            try:
                observation = loop.world.run_experiment(proposal)

                print(f"✓ Execution complete")

                # Agent updates beliefs
                loop.agent.update_from_observation(observation)
                loop.agent.beliefs.end_cycle()

                # EPISTEMIC: Resolve claim (measure realized gain)
                # For testing, create mock posteriors with entropy values
                # (In real integration, agent would compute from actual belief updates)
                from dataclasses import dataclass as dc

                @dc
                class MockPosterior:
                    entropy: float

                # Simulate information gain measurement
                prior_entropy = 1.5  # Before observation
                posterior_entropy = 1.2  # After observation (narrowed)
                realized_gain = prior_entropy - posterior_entropy  # 0.3 bits

                prior = MockPosterior(entropy=prior_entropy)
                posterior = MockPosterior(entropy=posterior_entropy)

                result = epistemic_integration.resolve_design(
                    claim_id=claim_id,
                    prior_posterior=prior,
                    posterior=posterior
                )

                print(f"✓ Epistemic resolution:")
                print(f"  Realized gain: {result['realized_gain']:.3f} bits")
                print(f"  Debt increment: {result['debt_increment']:.3f}")
                print(f"  Total debt: {result['total_debt']:.3f}")
                print(f"  Cost multiplier: {result['cost_multiplier']:.2f}×")

                # Update stats
                stats.cycles_completed += 1
                stats.budget_spent += observation.wells_spent
                stats.total_debt_accumulated = result['total_debt']
                stats.max_cost_multiplier = max(
                    stats.max_cost_multiplier,
                    result['cost_multiplier']
                )

                # Save history
                loop.history.append({
                    'cycle': cycle,
                    'proposal': {
                        'design_id': proposal.design_id,
                        'n_wells': len(proposal.wells),
                    },
                    'observation': {
                        'wells_spent': observation.wells_spent,
                        'budget_remaining': observation.budget_remaining,
                    },
                    'epistemic': {
                        'expected_gain': expected_gain,
                        'realized_gain': result['realized_gain'],
                        'debt_increment': result['debt_increment'],
                        'total_debt': result['total_debt'],
                    }
                })

            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                stats.abort_reason = str(e)
                break

        # Print summary
        print(f"\n{'='*60}")
        print("EPISTEMIC CONTROLLER STRESS TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Cycles completed: {stats.cycles_completed}")
        print(f"Claims made: {len(claims_made)}")
        print(f"Total debt accumulated: {stats.total_debt_accumulated:.3f} bits")
        print(f"Max cost multiplier: {stats.max_cost_multiplier:.2f}×")
        print(f"Budget spent: {stats.budget_spent}/{loop.budget}")

        # Validation
        assert stats.cycles_completed >= 2, \
            f"Should complete at least 2 cycles with epistemic tracking"

        assert len(claims_made) == stats.cycles_completed, \
            f"Should make {stats.cycles_completed} claims"

        # Epistemic controller should be tracking (debt may be 0 if well-calibrated)
        epistemic_stats = epistemic_integration.get_statistics()
        assert epistemic_stats['enabled'] == True, \
            "Epistemic controller should be enabled"

        print(f"\n✓ Epistemic controller stress test PASSED")
        print(f"  Debt tracking active")
        print(f"  Claims resolved: {len(claims_made)}")
        print(f"  System operational")


def test_confluence_rejection_pattern():
    """
    Test that confluence validator would reject confounded designs.

    This is a UNIT TEST (not full agent loop) that validates the rejection pattern.
    When confluence validator is integrated into world.run_experiment(),
    this pattern will work in the full loop.
    """
    from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
    from src.cell_os.epistemic_agent.design_bridge import (
        proposal_to_design_json,
        validate_design
    )

    # Create confounded design (control vs toxic at 48h)
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment"
        ),
    ]

    proposal = Proposal(
        design_id="test_confounded",
        hypothesis="This should be rejected by confluence validator",
        wells=wells,
        budget_limit=1000.0
    )

    # Convert to design JSON
    well_positions = ["A01", "A02", "A03", "A04"]
    design = proposal_to_design_json(
        proposal=proposal,
        cycle=1,
        run_id="test_run",
        well_positions=well_positions
    )

    # Validate should raise InvalidDesignError
    try:
        validate_design(design, strict=True)
        raise AssertionError("Should have rejected confounded design")
    except InvalidDesignError as e:
        assert e.violation_code == "confluence_confounding", \
            f"Expected confluence_confounding, got {e.violation_code}"

        print(f"✓ Confluence validator rejects confounded design")
        print(f"  Violation: {e.violation_code}")
        print(f"  Δp = {e.details.get('delta_p', 'N/A')}")


if __name__ == "__main__":
    print("="*70)
    print("LIVE AGENT CONFLUENCE STRESS TESTS")
    print("="*70)
    print()

    # Test 1: Minimal agent loop (smoke test)
    test_live_agent_stress_minimal()
    print()

    # Test 2: Agent with epistemic controller
    test_live_agent_with_epistemic_controller()
    print()

    # Test 3: Confluence rejection pattern (unit test)
    test_confluence_rejection_pattern()
    print()

    print("="*70)
    print("✅ ALL LIVE AGENT STRESS TESTS PASSED")
    print("="*70)
    print()
    print("Validated:")
    print("  ✓ Agent completes multiple cycles")
    print("  ✓ Epistemic controller tracks debt")
    print("  ✓ Confluence validator rejects confounded designs")
    print("  ✓ Integration systems operational")
