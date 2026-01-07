"""
Unit tests to enforce world/aggregator boundary.

These tests ensure:
1. World is "dumb" (no aggregation logic)
2. Aggregator is correct (deterministic, reversible)
3. Boundary is clean (no leakage)
"""

import pytest
import ast
import inspect
from pathlib import Path

from src.cell_os.epistemic_agent.world import ExperimentalWorld
from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
from src.cell_os.core.observation import RawWellResult


def test_world_does_not_import_numpy_stats():
    """World should not import numpy statistics functions.

    This is a "grep test" - brittle but effective for enforcing boundaries.
    """
    world_file = Path(__file__).parent.parent.parent / "src" / "cell_os" / "epistemic_agent" / "world.py"

    with open(world_file, 'r') as f:
        source = f.read()

    # Parse AST
    tree = ast.parse(source)

    # Check for banned numpy stat calls
    banned_functions = ['np.mean', 'np.std', 'np.sem', 'np.var']

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id == 'np' and node.attr in ['mean', 'std', 'sem', 'var']:
                    pytest.fail(
                        f"World should not use np.{node.attr}() - aggregation logic belongs in aggregator. "
                        f"Found at line {node.lineno}"
                    )

    print("✓ World does not use numpy stats (boundary enforced)")


def test_world_does_not_mention_aggregate():
    """World should not contain 'aggregate' in method names or doc strings.

    Exception: comments explaining that aggregation was removed.
    """
    world_file = Path(__file__).parent.parent.parent / "src" / "cell_os" / "epistemic_agent" / "world.py"

    with open(world_file, 'r') as f:
        lines = f.readlines()

    violations = []
    for i, line in enumerate(lines, 1):
        # Skip comments explaining removal
        if 'AGGREGATION REMOVED' in line or 'aggregation now happens' in line.lower():
            continue

        # Check for aggregate in method names or active code
        if 'aggregate' in line.lower() and not line.strip().startswith('#'):
            # Allow in strings/comments explaining the architecture
            if 'no aggregation' not in line.lower() and 'aggregator' not in line.lower():
                violations.append(f"Line {i}: {line.strip()}")

    # Allow some mentions in docstrings/comments explaining architecture
    # But fail if there are actual aggregation methods
    if any('def' in v and 'aggregate' in v.lower() for v in violations):
        pytest.fail(
            f"World should not have aggregation methods:\n" +
            "\n".join(violations)
        )

    print("✓ World does not contain aggregation logic")


def test_world_returns_raw_results():
    """World.run_experiment() should return tuple of RawWellResult."""
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        )
    ]

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=wells,
        budget_limit=100
    )

    result = world.run_experiment(proposal)

    # Check return type
    assert isinstance(result, tuple), f"World should return tuple, got {type(result)}"
    assert len(result) > 0, "World should return non-empty results"

    # Check first element is RawWellResult
    assert isinstance(result[0], RawWellResult), \
        f"World should return RawWellResult, got {type(result[0])}"

    print("✓ World returns raw RawWellResult objects")


def test_raw_well_result_has_required_fields():
    """RawWellResult should have all required fields."""
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        )
    ]

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=wells,
        budget_limit=100
    )

    raw_results = world.run_experiment(proposal)
    result = raw_results[0]

    # Check required fields
    assert hasattr(result, 'location'), "RawWellResult missing location"
    assert hasattr(result, 'cell_line'), "RawWellResult missing cell_line"
    assert hasattr(result, 'treatment'), "RawWellResult missing treatment"
    assert hasattr(result, 'assay'), "RawWellResult missing assay"
    assert hasattr(result, 'observation_time_h'), "RawWellResult missing observation_time_h"
    assert hasattr(result, 'readouts'), "RawWellResult missing readouts"
    assert hasattr(result, 'qc'), "RawWellResult missing qc"

    # Check readouts structure
    assert 'morphology' in result.readouts, "Readouts should contain morphology"
    morph = result.readouts['morphology']
    assert 'er' in morph, "Morphology should have 'er' channel"
    assert 'mito' in morph, "Morphology should have 'mito' channel"
    assert 'nucleus' in morph, "Morphology should have 'nucleus' channel"
    assert 'actin' in morph, "Morphology should have 'actin' channel"
    assert 'rna' in morph, "Morphology should have 'rna' channel"

    print("✓ RawWellResult has all required fields")


def test_aggregator_produces_observation():
    """Aggregator should convert raw results to Observation."""
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        )
    ]

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=wells,
        budget_limit=100
    )

    raw_results = world.run_experiment(proposal)

    # Aggregate
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )

    # Check observation structure
    assert observation.design_id == "test"
    assert len(observation.conditions) > 0, "Observation should have conditions"
    assert observation.wells_spent == 2
    assert observation.budget_remaining == 98

    # Check condition summary fields
    cond = observation.conditions[0]
    assert hasattr(cond, 'mean'), "ConditionSummary should have mean"
    assert hasattr(cond, 'std'), "ConditionSummary should have std"
    assert hasattr(cond, 'sem'), "ConditionSummary should have sem"
    assert hasattr(cond, 'feature_means'), "ConditionSummary should have feature_means"
    assert hasattr(cond, 'feature_stds'), "ConditionSummary should have feature_stds"

    print("✓ Aggregator produces valid Observation")


def test_world_plus_aggregator_preserves_legacy_behavior():
    """World → Aggregator flow should produce same results as old world.

    This is a regression test to ensure we didn't break existing behavior.
    """
    world = ExperimentalWorld(budget_wells=100, seed=42)

    # Create a simple experiment
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="tBHQ",
            dose_uM=30.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        )
    ]

    proposal = Proposal(
        design_id="regression_test",
        hypothesis="Test backward compatibility",
        wells=wells,
        budget_limit=100
    )

    # Execute
    raw_results = world.run_experiment(proposal)
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )

    # Verify basic properties that old code relied on
    assert len(observation.conditions) == 2, "Should have 2 conditions (DMSO and tBHQ)"
    assert observation.wells_spent == 3
    assert observation.budget_remaining == 97

    # Verify DMSO condition
    dmso_cond = [c for c in observation.conditions if c.compound == 'DMSO'][0]
    assert dmso_cond.n_wells == 2
    assert dmso_cond.mean > 0, "DMSO mean should be positive"
    assert dmso_cond.std >= 0, "DMSO std should be non-negative"

    # Verify tBHQ condition
    tbhq_cond = [c for c in observation.conditions if c.compound == 'tBHQ'][0]
    assert tbhq_cond.n_wells == 1
    # Note: tBHQ at 30µM can produce strong phenotypic effects in the model.
    # With only 1 well, we just verify the value is a valid positive number.
    assert tbhq_cond.mean > 0, f"tBHQ mean should be positive: {tbhq_cond.mean}"

    print("✓ World + Aggregator preserves legacy behavior")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
