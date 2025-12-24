"""
Regression test: Agent must respond to spatial QC flags or accrue epistemic debt.

This test establishes the contract:
- When spatial_autocorrelation is flagged for a measurement channel
- The agent MUST produce a replate proposal (same conditions, new layout)
- OR accrue epistemic debt penalty

This is a true regression test: it fails until agent cycle wiring exists.
"""

import pytest
from collections import Counter
from cell_os.epistemic_agent.world import ExperimentalWorld
from cell_os.epistemic_agent.schemas import WellSpec, Proposal
from cell_os.epistemic_agent.observation_aggregator import aggregate_observation
from cell_os.epistemic_agent.agent.policy_rules import RuleBasedPolicy
from cell_os.adversarial import AdversarialPlateConfig, AdversarySpec
from cell_os.epistemic_agent.accountability import AccountabilityConfig


def test_agent_produces_replate_when_spatial_qc_flagged():
    """Agent produces replate proposal when spatial autocorrelation is flagged."""

    # Setup: world with strong spatial gradient
    adversarial_config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {
                "target_channel": "morphology.nucleus",
                "axis": "both",
                "strength": 0.3,
                "direction": 1
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(
        budget_wells=384,
        seed=42,
        adversarial_plate_config=adversarial_config
    )

    # Create agent with accountability enabled
    accountability_config = AccountabilityConfig(
        enabled=True,
        spatial_key="morphology.nucleus",
        penalty=1.0
    )
    agent = RuleBasedPolicy(budget=384, accountability=accountability_config, seed=42)

    # Run first cycle: agent proposes initial experiment
    capabilities = world.get_capabilities()
    initial_proposal = agent.propose_next_experiment(capabilities, previous_observation=None)

    # Execute initial experiment
    raw_results = world.run_experiment(initial_proposal)

    # Aggregate observation with QC
    observation = aggregate_observation(
        proposal=initial_proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining,
        cycle=0
    )

    # Manually force spatial flag for this test
    # (Real flagging is probabilistic with partial plates)
    if "spatial_autocorrelation" not in observation.qc_struct:
        observation.qc_struct["spatial_autocorrelation"] = {}
    if "morphology.nucleus" not in observation.qc_struct["spatial_autocorrelation"]:
        observation.qc_struct["spatial_autocorrelation"]["morphology.nucleus"] = {
            "morans_i": 0.5,
            "z_score": 3.0,
            "p_value": 0.01,
            "flagged": True,
            "n_wells": len(raw_results)
        }
    else:
        observation.qc_struct["spatial_autocorrelation"]["morphology.nucleus"]["flagged"] = True

    # Update agent budget
    agent.budget_remaining = observation.budget_remaining

    # ACT: Agent proposes next experiment (should be replate due to spatial flag)
    # Convert observation to dict for agent API
    from dataclasses import asdict
    observation_dict = asdict(observation)

    next_proposal = agent.propose_next_experiment(capabilities, previous_observation=observation_dict)

    # ASSERT: Next proposal is a replate (same conditions, different ordering)

    # Extract condition signatures from both proposals
    def condition_signature(well):
        return (well.cell_line, well.compound, well.dose_uM, well.time_h, well.assay)

    initial_conditions = sorted([condition_signature(w) for w in initial_proposal.wells])
    next_conditions = sorted([condition_signature(w) for w in next_proposal.wells])

    # Same conditions (multiset equality)
    assert initial_conditions == next_conditions, (
        "Replate proposal must preserve conditions exactly. "
        f"Initial condition count: {Counter(initial_conditions)}, "
        f"Next condition count: {Counter(next_conditions)}"
    )

    # Well count must match
    assert len(next_proposal.wells) == len(initial_proposal.wells), (
        "Replate proposal must preserve well count. "
        f"Initial: {len(initial_proposal.wells)}, Next: {len(next_proposal.wells)}"
    )

    # Replate signal: layout_seed must be set (indicates spatial variance)
    assert next_proposal.layout_seed is not None, (
        "Replate proposal must have layout_seed set for spatial variance. "
        f"Got: {next_proposal.layout_seed}"
    )

    # Initial proposal should NOT have layout_seed (normal generation)
    assert initial_proposal.layout_seed is None, (
        "Initial proposal should not have layout_seed. "
        f"Got: {initial_proposal.layout_seed}"
    )

    # SUCCESS: Agent produced replate proposal in response to spatial QC flag


def test_agent_proceeds_normally_when_accountability_disabled():
    """With accountability disabled, agent proceeds normally even with spatial flags."""

    adversarial_config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {
                "target_channel": "morphology.nucleus",
                "axis": "both",
                "strength": 0.3,
                "direction": 1
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(
        budget_wells=384,
        seed=42,
        adversarial_plate_config=adversarial_config
    )

    # Create agent WITHOUT accountability (default)
    agent = RuleBasedPolicy(budget=384, seed=42)

    # Run one cycle
    capabilities = world.get_capabilities()
    proposal = agent.propose_next_experiment(capabilities, previous_observation=None)

    # Execute
    raw_results = world.run_experiment(proposal)
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining,
        cycle=0
    )

    # Force flag
    if "spatial_autocorrelation" not in observation.qc_struct:
        observation.qc_struct["spatial_autocorrelation"] = {}
    observation.qc_struct["spatial_autocorrelation"]["morphology.nucleus"] = {
        "flagged": True,
        "morans_i": 0.5,
        "z_score": 3.0,
        "p_value": 0.01,
        "n_wells": len(raw_results)
    }

    # Update agent budget
    agent.budget_remaining = observation.budget_remaining

    # Next proposal should be normal (not replate) because accountability disabled
    from dataclasses import asdict
    observation_dict = asdict(observation)
    next_proposal = agent.propose_next_experiment(capabilities, previous_observation=observation_dict)

    # Should NOT be a replate
    assert "replate" not in next_proposal.design_id.lower(), (
        "Without accountability, agent should not produce replate proposals"
    )


def test_agent_fallback_when_no_previous_proposal():
    """Agent falls back to normal proposal when spatial flagged but no previous proposal exists."""

    adversarial_config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {
                "target_channel": "morphology.nucleus",
                "axis": "both",
                "strength": 0.3,
                "direction": 1
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(
        budget_wells=384,
        seed=42,
        adversarial_plate_config=adversarial_config
    )

    # Create agent with accountability enabled
    accountability_config = AccountabilityConfig(
        enabled=True,
        spatial_key="morphology.nucleus",
        penalty=1.0
    )
    agent = RuleBasedPolicy(budget=384, accountability=accountability_config, seed=42)

    # Fabricate a spatial-flagged observation WITHOUT running an initial experiment
    # (simulates the case where we have QC data but no _last_proposal)
    fake_observation_dict = {
        "qc_struct": {
            "spatial_autocorrelation": {
                "morphology.nucleus": {
                    "flagged": True,
                    "morans_i": 0.5,
                    "z_score": 3.0
                }
            }
        }
    }

    # Agent has no _last_proposal yet (first cycle)
    assert agent._last_proposal is None

    # Propose with spatial flag but no previous proposal
    capabilities = world.get_capabilities()
    proposal = agent.propose_next_experiment(capabilities, previous_observation=fake_observation_dict)

    # Should NOT crash, should fall back to normal proposal
    assert proposal is not None
    assert "replate" not in proposal.design_id.lower(), (
        "Should not replate when no previous proposal exists"
    )
    assert proposal.layout_seed is None, (
        "Fallback proposal should not have layout_seed"
    )
