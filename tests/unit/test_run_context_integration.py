"""
Test RunContext integration with batch_effects (Phase 2).

Verifies:
- RunContext.get_biology_modifiers() delegates to profile
- Seeding behavior preserved (seed+999 offset)
- to_dict() serialization works
- Interface unchanged (backward compatibility)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.run_context import RunContext
from src.cell_os.hardware.batch_effects import RunBatchProfile


def test_run_context_delegates_to_profile():
    """Verify RunContext uses RunBatchProfile for multipliers."""
    ctx = RunContext.sample(seed=42)

    # Get multipliers (triggers lazy initialization)
    mods = ctx.get_biology_modifiers()

    # Assert profile was created
    assert ctx._profile is not None, "Profile should be initialized"
    assert isinstance(ctx._profile, RunBatchProfile)

    # Assert multipliers match profile
    profile_mods = ctx._profile.to_multipliers()
    for key in ['ec50_multiplier', 'growth_rate_multiplier', 'hazard_multiplier', 'burden_half_life_multiplier']:
        assert key in mods
        assert abs(mods[key] - profile_mods[key]) < 1e-12, \
            f"{key}: context={mods[key]:.6f} != profile={profile_mods[key]:.6f}"

    print(f"✓ RunContext delegates to profile correctly")


def test_seeding_behavior_preserved():
    """Verify seed+999 offset preserved from v5."""
    ctx = RunContext.sample(seed=42)

    # Get multipliers (triggers lazy initialization)
    mods = ctx.get_biology_modifiers()

    # Profile should have been sampled with seed+999
    assert ctx._profile.seed == 42 + 999, \
        f"Profile seed {ctx._profile.seed} != expected {42 + 999}"

    # Verify determinism: same seed → same multipliers
    ctx2 = RunContext.sample(seed=42)
    mods2 = ctx2.get_biology_modifiers()

    for key in mods:
        assert abs(mods[key] - mods2[key]) < 1e-12, \
            f"Determinism broken: {key} differs"

    print(f"✓ Seeding behavior preserved (seed+999 offset)")


def test_interface_unchanged():
    """Verify RunContext interface is backward compatible."""
    ctx = RunContext.sample(seed=42)

    # get_biology_modifiers() should return dict with expected keys
    mods = ctx.get_biology_modifiers()

    expected_keys = [
        'ec50_multiplier',
        'growth_rate_multiplier',
        'hazard_multiplier',
        'burden_half_life_multiplier',
        'stress_sensitivity'
    ]

    for key in expected_keys:
        assert key in mods, f"Missing key: {key}"
        assert isinstance(mods[key], float), f"{key} should be float"
        assert mods[key] > 0, f"{key} should be positive"

    print(f"✓ Interface unchanged (backward compatible)")


def test_to_dict_serialization():
    """Verify to_dict() produces valid output."""
    ctx = RunContext.sample(seed=42)

    # Get multipliers (triggers lazy initialization)
    ctx.get_biology_modifiers()

    # Serialize
    ctx_dict = ctx.to_dict()

    # Check required keys
    assert 'context_id' in ctx_dict
    assert 'seed' in ctx_dict
    assert 'batch_effects' in ctx_dict
    assert 'measurement_effects' in ctx_dict

    # Check batch_effects structure
    batch = ctx_dict['batch_effects']
    assert batch is not None
    assert 'schema_version' in batch
    assert 'mapping_version' in batch
    assert 'profile' in batch
    assert 'derived_multipliers' in batch
    assert 'profile_hash' in batch

    # Check profile structure
    profile = batch['profile']
    assert 'media_lot' in profile
    assert 'incubator' in profile
    assert 'cell_state' in profile

    # Verify JSON serializable
    import json
    json_str = json.dumps(ctx_dict)
    assert len(json_str) > 0

    print(f"✓ to_dict() serialization works")


def test_multipliers_bounded():
    """Verify multipliers still clamped to [0.5, 2.0]."""
    # Test many seeds to ensure clamping works
    for seed in range(100):
        ctx = RunContext.sample(seed=seed)
        mods = ctx.get_biology_modifiers()

        for key, value in mods.items():
            if key == 'stress_sensitivity':
                continue  # Placeholder, always 1.0
            assert 0.5 <= value <= 2.0, \
                f"Multiplier {key} out of bounds: {value} (seed={seed})"

    print(f"✓ Multipliers bounded [0.5, 2.0] across 100 seeds")


def test_lazy_initialization():
    """Verify profile is sampled lazily (not at construction)."""
    ctx = RunContext.sample(seed=42)

    # Profile should not exist yet
    assert ctx._profile is None, "Profile should not be initialized at construction"
    assert ctx._biology_modifiers is None, "Modifiers should not be cached at construction"

    # Trigger initialization
    mods = ctx.get_biology_modifiers()

    # Now profile should exist
    assert ctx._profile is not None, "Profile should be initialized after first access"
    assert ctx._biology_modifiers is not None, "Modifiers should be cached after first access"

    # Second access should use cache (not resample)
    mods2 = ctx.get_biology_modifiers()
    assert mods is mods2, "Should return same cached dict"

    print(f"✓ Lazy initialization works correctly")


def test_correlation_structure_present():
    """Verify correlation structure is present (not independent sampling)."""
    samples = 100
    ec50_values = []
    hazard_values = []

    for seed in range(samples):
        ctx = RunContext.sample(seed=seed)
        mods = ctx.get_biology_modifiers()
        ec50_values.append(mods['ec50_multiplier'])
        hazard_values.append(mods['hazard_multiplier'])

    # Compute correlation
    import numpy as np
    corr = np.corrcoef(ec50_values, hazard_values)[0, 1]

    # Media lot creates anti-correlation (ec50 up, hazard down)
    # Should be negative correlation (not zero)
    assert corr < -0.1, \
        f"Expected negative correlation due to anti-correlated effects, got {corr:.3f}"

    print(f"✓ Correlation structure present: r(ec50, hazard) = {corr:.3f}")


if __name__ == "__main__":
    print("Running RunContext integration tests (Phase 2)...\n")

    test_run_context_delegates_to_profile()
    test_seeding_behavior_preserved()
    test_interface_unchanged()
    print()

    test_to_dict_serialization()
    print()

    test_multipliers_bounded()
    test_lazy_initialization()
    test_correlation_structure_present()
    print()

    print("\n✓ All RunContext integration tests passed - Phase 2 COMPLETE")
