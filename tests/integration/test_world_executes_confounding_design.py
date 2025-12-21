"""
Integration test: World executes confounded designs.

This test proves:
1. World executes any physically valid design (doesn't validate quality)
2. QualityChecker warns about confounding
3. Agent can choose to refuse (but world doesn't care)

This is the "architecture teeth" test.
"""

import pytest
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
from src.cell_os.epistemic_agent.world import ExperimentalWorld
from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation
from src.cell_os.epistemic_agent.design_quality import DesignQualityChecker


def test_world_executes_confluence_confounded_design():
    """
    World executes a design where treatment and control have different timepoints.

    This is scientifically stupid (confluence will differ), but physically valid.
    """

    # Create deliberately confounded design
    # Control: 12h timepoint (low confluence)
    # Treatment: 48h timepoint (high confluence)
    # This confounds treatment effect with density

    wells = []

    # Control: DMSO at 12h (8 wells, center)
    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='DMSO',
            dose_uM=0.0,
            time_h=12.0,  # ← Low confluence
            assay='cell_painting',
            position_tag='center'
        ))

    # Treatment: tunicamycin at 48h (8 wells, center)
    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='tunicamycin',
            dose_uM=2.0,
            time_h=48.0,  # ← High confluence (confounded!)
            assay='cell_painting',
            position_tag='center'
        ))

    proposal = Proposal(
        design_id='confounded_test',
        hypothesis='Testing if world executes confounded designs',
        wells=wells,
        budget_limit=100
    )

    # 1. Quality checker should warn
    checker = DesignQualityChecker(strict_mode=False)
    report = checker.check(proposal)

    assert report.has_warnings, "QualityChecker should warn about timepoint confounding"
    assert any(w.category == 'confluence_confounding' for w in report.warnings), \
        "Should specifically flag confluence confounding"

    # Find the confluence warning
    confluence_warning = next(w for w in report.warnings if w.category == 'confluence_confounding')
    assert confluence_warning.severity == 'high', "Timepoint confounding is high severity"

    print(f"\n✓ QualityChecker detected confounding:")
    print(f"  {confluence_warning}")

    # 2. World executes WITHOUT raising
    world = ExperimentalWorld(budget_wells=100, seed=42)

    try:
        raw_results = world.run_experiment(proposal)
        observation = aggregate_observation(
            proposal=proposal,
            raw_results=raw_results,
            budget_remaining=world.budget_remaining
        )
        print(f"\n✓ World executed confounded design")
        print(f"  Returned {len(observation.conditions)} conditions")
    except Exception as e:
        pytest.fail(f"World should execute confounded designs, but raised: {e}")

    # 3. Observation is returned (even if scientifically misleading)
    assert observation is not None
    assert observation.design_id == 'confounded_test'
    assert len(observation.conditions) == 2  # Control and treatment

    # The data will be confounded (can't tell if effect is treatment or density)
    # But that's the agent's problem, not the world's

    print(f"\n✓ Test passed: World executes confounded designs")


def test_agent_can_refuse_based_on_quality():
    """
    Agent (via loop) can refuse designs based on quality report.

    This is a POLICY decision, not a physics constraint.
    """

    # Same confounded design
    wells = []
    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='DMSO',
            dose_uM=0.0,
            time_h=12.0,
            assay='cell_painting',
            position_tag='center'
        ))

    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='tunicamycin',
            dose_uM=2.0,
            time_h=48.0,
            assay='cell_painting',
            position_tag='center'
        ))

    proposal = Proposal(
        design_id='confounded_test_strict',
        hypothesis='Testing agent refusal',
        wells=wells,
        budget_limit=100
    )

    # In strict mode, agent refuses
    checker_strict = DesignQualityChecker(strict_mode=True)
    report_strict = checker_strict.check(proposal)

    assert report_strict.blocks_execution, \
        "In strict mode, high-severity warnings should block execution"

    # In permissive mode, agent allows (but logs warnings)
    checker_permissive = DesignQualityChecker(strict_mode=False)
    report_permissive = checker_permissive.check(proposal)

    assert not report_permissive.blocks_execution, \
        "In permissive mode, agent allows risky designs"

    print(f"\n✓ Agent can enforce quality policy via strict_mode")


def test_world_executes_position_confounded_design():
    """
    World executes design where treatment is on edge, control in center.

    Edge wells have different growth (evaporation, temperature).
    This confounds treatment with position artifact.
    """

    wells = []

    # Control: center position
    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='DMSO',
            dose_uM=0.0,
            time_h=24.0,
            assay='cell_painting',
            position_tag='center'  # ← Good position
        ))

    # Treatment: edge position (confounded!)
    for i in range(8):
        wells.append(WellSpec(
            cell_line='A549',
            compound='tunicamycin',
            dose_uM=2.0,
            time_h=24.0,
            assay='cell_painting',
            position_tag='edge'  # ← Confounded with position artifacts
        ))

    proposal = Proposal(
        design_id='position_confounded',
        hypothesis='Testing position confounding',
        wells=wells,
        budget_limit=100
    )

    # Quality checker warns
    checker = DesignQualityChecker()
    report = checker.check(proposal)

    assert report.has_warnings
    # Should detect position imbalance
    assert any('position' in w.message.lower() or 'edge' in w.message.lower()
               for w in report.warnings)

    # World still executes
    world = ExperimentalWorld(budget_wells=100, seed=42)
    observation = world.run_experiment(proposal)

    assert observation is not None
    print(f"\n✓ World executed position-confounded design")


def test_world_refuses_only_physical_violations():
    """
    World refuses only physical impossibilities, not scientific stupidity.
    """

    # This is physically invalid (exceeds budget)
    wells = []
    for i in range(500):  # Way over budget
        wells.append(WellSpec(
            cell_line='A549',
            compound='DMSO',
            dose_uM=0.0,
            time_h=12.0,
            assay='cell_painting',
            position_tag='center'
        ))

    proposal = Proposal(
        design_id='over_budget',
        hypothesis='Testing budget constraint',
        wells=wells,
        budget_limit=500
    )

    world = ExperimentalWorld(budget_wells=100, seed=42)

    # World refuses (physical constraint)
    with pytest.raises(ValueError, match="Insufficient budget"):
        world.run_experiment(proposal)

    print(f"\n✓ World refuses physical violations (budget)")


if __name__ == '__main__':
    test_world_executes_confluence_confounded_design()
    test_agent_can_refuse_based_on_quality()
    test_world_executes_position_confounded_design()
    test_world_refuses_only_physical_violations()
    print("\n" + "="*70)
    print("All tests passed: World is dumb, agent is smart")
    print("="*70)
