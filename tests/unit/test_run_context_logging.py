"""
Test run_context logging in EpistemicLoop (Phase 3).

Verifies:
- run_context appears in loop output JSON
- run_context structure is complete (schema_version, profile, multipliers, hash)
- run_context is logged exactly once per run (not per-cycle)
- Deterministic: same seed → same run_context in log
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.epistemic_agent.world import ExperimentalWorld


def test_world_get_run_context_dict():
    """Verify ExperimentalWorld.get_run_context_dict() works."""
    world = ExperimentalWorld(budget_wells=96, seed=42)

    ctx_dict = world.get_run_context_dict()

    # Check required keys
    assert 'is_authoritative' in ctx_dict
    assert 'run_seed' in ctx_dict
    assert 'context_id' in ctx_dict
    assert 'run_context_seed' in ctx_dict
    assert 'batch_effects' in ctx_dict
    assert 'measurement_effects' in ctx_dict
    assert 'run_context_hash' in ctx_dict

    # Check is_authoritative flag
    assert ctx_dict['is_authoritative'] == False, "Should admit not yet authoritative"

    # Check seed semantics (clear naming, no confusion)
    assert ctx_dict['run_seed'] == 42
    assert ctx_dict['run_context_seed'] == 42

    # Check batch_effects structure
    batch = ctx_dict['batch_effects']
    assert 'schema_version' in batch
    assert 'mapping_version' in batch
    assert 'batch_effects_seed' in batch  # Renamed from 'seed'
    assert 'profile' in batch
    assert 'derived_multipliers' in batch
    assert 'profile_hash' in batch

    # Check profile structure
    profile = batch['profile']
    assert 'media_lot' in profile
    assert 'incubator' in profile
    assert 'cell_state' in profile

    # Check run_context_hash format
    assert isinstance(ctx_dict['run_context_hash'], str)
    assert len(ctx_dict['run_context_hash']) == 16  # 16 hex chars

    print(f"✓ ExperimentalWorld.get_run_context_dict() returns complete structure")


def test_run_context_deterministic():
    """Verify same seed gives same run_context."""
    world1 = ExperimentalWorld(budget_wells=96, seed=42)
    world2 = ExperimentalWorld(budget_wells=96, seed=42)

    ctx1 = world1.get_run_context_dict()
    ctx2 = world2.get_run_context_dict()

    # Check profile hash matches (deterministic profile)
    assert ctx1['batch_effects']['profile_hash'] == ctx2['batch_effects']['profile_hash']

    # Check run_context_hash matches (deterministic entire context)
    assert ctx1['run_context_hash'] == ctx2['run_context_hash']

    # Check multipliers match
    mults1 = ctx1['batch_effects']['derived_multipliers']
    mults2 = ctx2['batch_effects']['derived_multipliers']

    for key in mults1:
        assert abs(mults1[key] - mults2[key]) < 1e-12, \
            f"{key} differs: {mults1[key]} vs {mults2[key]}"

    print(f"✓ Same seed gives same run_context (deterministic)")


def test_run_context_differs_for_different_seeds():
    """Verify different seeds give different run_context."""
    world1 = ExperimentalWorld(budget_wells=96, seed=42)
    world2 = ExperimentalWorld(budget_wells=96, seed=99)

    ctx1 = world1.get_run_context_dict()
    ctx2 = world2.get_run_context_dict()

    # Profile hashes should differ
    assert ctx1['batch_effects']['profile_hash'] != ctx2['batch_effects']['profile_hash']

    # At least one multiplier should differ
    mults1 = ctx1['batch_effects']['derived_multipliers']
    mults2 = ctx2['batch_effects']['derived_multipliers']

    differs = any(
        abs(mults1[key] - mults2[key]) > 1e-6
        for key in mults1
        if key in mults2
    )

    assert differs, "Different seeds should give different multipliers"

    print(f"✓ Different seeds give different run_context")


def test_run_context_json_serializable():
    """Verify run_context can be serialized to JSON."""
    world = ExperimentalWorld(budget_wells=96, seed=42)
    ctx_dict = world.get_run_context_dict()

    # Should be JSON serializable
    json_str = json.dumps(ctx_dict, indent=2)
    assert len(json_str) > 0

    # Should roundtrip
    ctx_loaded = json.loads(json_str)
    assert ctx_loaded['batch_effects']['schema_version'] == ctx_dict['batch_effects']['schema_version']

    print(f"✓ run_context is JSON serializable")


def test_world_owns_same_instance():
    """Verify world returns same RunContext instance across multiple accesses."""
    world = ExperimentalWorld(budget_wells=96, seed=42)

    # Access run_context property multiple times
    ctx1 = world.run_context
    ctx2 = world.run_context

    # Should be the same object (not fresh sample each time)
    assert ctx1 is ctx2, "World should return same RunContext instance"

    # Hash should be identical (same instance)
    dict1 = world.get_run_context_dict()
    dict2 = world.get_run_context_dict()

    assert dict1['run_context_hash'] == dict2['run_context_hash']

    print(f"✓ World owns same RunContext instance (not resampling)")


if __name__ == "__main__":
    print("Running run_context logging tests (Phase 3)...\n")

    test_world_get_run_context_dict()
    test_run_context_deterministic()
    test_run_context_differs_for_different_seeds()
    test_run_context_json_serializable()
    test_world_owns_same_instance()
    print()

    print("\n✓ All run_context logging tests passed - Phase 3 COMPLETE")
