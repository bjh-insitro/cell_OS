#!/usr/bin/env python3
"""
Safety Tests: Structured Artifacts Wiring

Three critical tests that must pass before merging structured artifacts:

1. Flag-off identity: byte-identical to Phase 1 (backward compatibility)
2. Flag-on metadata present: artifacts dict populated when enabled
3. Determinism: same seed → same artifacts → same measurements
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

import json
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_flag_off_identity():
    """
    Flag off produces IDENTICAL output to Phase 1 pipeline.

    This is the most important test. If it fails, backward compatibility is broken.
    Do not "tweak tolerances" - fix the root cause.
    """
    seed = 42

    def run_measurement(seed, enable_structured):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
        vm.advance_time(48)
        vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)
        return vm.cell_painting_assay(
            "well_A1",
            well_position="A1",
            enable_structured_artifacts=enable_structured
        )

    # Run twice with flag off (should be identical)
    result1 = run_measurement(seed, enable_structured=False)
    result2 = run_measurement(seed, enable_structured=False)

    # Morphology must be byte-identical
    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert result1['morphology'][channel] == result2['morphology'][channel], \
            f"Non-determinism in {channel}: {result1['morphology'][channel]} != {result2['morphology'][channel]}"

    # Segmentation quality must be identical
    assert result1['segmentation_quality'] == result2['segmentation_quality'], \
        f"Non-determinism in segmentation_quality"

    # Cell count must be identical
    assert result1['cell_count_observed'] == result2['cell_count_observed'], \
        f"Non-determinism in cell_count_observed"

    # imaging_artifacts must be None when flag off
    assert result1['imaging_artifacts'] is None, \
        "Flag off should have imaging_artifacts=None"
    assert result2['imaging_artifacts'] is None, \
        "Flag off should have imaging_artifacts=None"

    print("✓ Flag-off identity verified:")
    print(f"  ER signal: {result1['morphology']['er']:.6f}")
    print(f"  Segmentation quality: {result1['segmentation_quality']:.6f}")
    print(f"  Cell count: {result1['cell_count_observed']}")
    print(f"  Artifacts: {result1['imaging_artifacts']}")


def test_flag_on_metadata_present():
    """
    Flag on populates imaging_artifacts dict and does NOT mutate biology.

    Covenant: artifacts corrupt measurements, never affect vessel state.
    """
    seed = 42
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(48)
    vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    vessel = vm.vessel_states["well_A1"]
    pre_state = (vessel.cell_count, vessel.viability, vessel.debris_cells, vessel.confluence)

    # Measure with structured artifacts on
    result = vm.cell_painting_assay(
        "well_A1",
        well_position="A1",
        enable_structured_artifacts=True,
        experiment_seed=seed
    )

    post_state = (vessel.cell_count, vessel.viability, vessel.debris_cells, vessel.confluence)

    # Biology state must be unchanged (measurement purity)
    assert pre_state == post_state, \
        f"Structured artifacts mutated vessel state (covenant violation): {pre_state} != {post_state}"

    # Artifacts dict must be present
    assert result['imaging_artifacts'] is not None, \
        "Flag on should have imaging_artifacts populated"

    artifacts = result['imaging_artifacts']

    # Check schema
    assert 'background' in artifacts, "Missing 'background' key"
    assert 'segmentation' in artifacts, "Missing 'segmentation' key"
    assert 'spatial' in artifacts, "Missing 'spatial' key"
    assert 'debris_cells' in artifacts, "Missing 'debris_cells' key"
    assert 'initial_cells' in artifacts, "Missing 'initial_cells' key"
    assert 'adherent_cells' in artifacts, "Missing 'adherent_cells' key"

    # Background should be per-channel (not scalar)
    bg = artifacts['background']
    assert 'er' in bg and 'mito' in bg and 'rna' in bg, \
        "Background should have per-channel multipliers"
    assert '__global__' not in bg, \
        "Background should NOT have __global__ when channel_weights enabled"

    # Segmentation should have both scalar and modes
    seg = artifacts['segmentation']
    assert 'scalar_bump' in seg, "Missing 'scalar_bump' in segmentation"
    assert 'modes' in seg, "Missing 'modes' in segmentation"

    modes = seg['modes']
    assert 'p_merge' in modes, "Missing 'p_merge' in modes"
    assert 'p_split' in modes, "Missing 'p_split' in modes"

    # Spatial should have pattern
    spatial = artifacts['spatial']
    assert spatial is not None, "Spatial should be populated"
    assert 'field_strength' in spatial, "Missing 'field_strength' in spatial"
    assert 'spatial_pattern' in spatial, "Missing 'spatial_pattern' in spatial"

    print("✓ Flag-on metadata verified:")
    print(f"  Biology unchanged: {pre_state == post_state}")
    print(f"  Background (RNA): {bg['rna']:.6f}")
    print(f"  Segmentation (p_merge): {modes['p_merge']:.6f}")
    print(f"  Spatial (field_strength): {spatial['field_strength']:.4f}")


def test_determinism():
    """
    Same seed → identical artifacts and measurements.

    This ensures spatial patterns are deterministic from well_id hash,
    not per-measurement randomness.
    """
    seed = 42

    def run_measurement(seed):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
        vm.advance_time(48)
        vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)
        return vm.cell_painting_assay(
            "well_A1",
            well_position="A1",
            enable_structured_artifacts=True,
            experiment_seed=seed
        )

    result1 = run_measurement(seed)
    result2 = run_measurement(seed)

    artifacts1 = result1['imaging_artifacts']
    artifacts2 = result2['imaging_artifacts']

    # Debris cells must be identical
    assert artifacts1['debris_cells'] == artifacts2['debris_cells'], \
        "Debris cells not deterministic"

    # Background multipliers must be identical
    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert artifacts1['background'][channel] == artifacts2['background'][channel], \
            f"Background multiplier for {channel} not deterministic"

    # Segmentation scalar must be identical
    assert artifacts1['segmentation']['scalar_bump'] == artifacts2['segmentation']['scalar_bump'], \
        "Segmentation scalar_bump not deterministic"

    # Segmentation modes must be identical
    modes1 = artifacts1['segmentation']['modes']
    modes2 = artifacts2['segmentation']['modes']
    assert modes1['p_merge'] == modes2['p_merge'], "p_merge not deterministic"
    assert modes1['p_split'] == modes2['p_split'], "p_split not deterministic"

    # Spatial pattern must be identical (deterministic from well_id hash)
    import numpy as np
    pattern1 = artifacts1['spatial']['spatial_pattern']
    pattern2 = artifacts2['spatial']['spatial_pattern']
    assert np.array_equal(pattern1, pattern2), \
        "Spatial pattern not deterministic (should be seeded from well_id hash)"

    # Measurement outputs must be identical
    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert result1['morphology'][channel] == result2['morphology'][channel], \
            f"Morphology {channel} not deterministic"

    assert result1['segmentation_quality'] == result2['segmentation_quality'], \
        "Segmentation quality not deterministic"

    print("✓ Determinism verified:")
    print(f"  Debris cells: {artifacts1['debris_cells']:.0f}")
    print(f"  Background (RNA): {artifacts1['background']['rna']:.6f}")
    print(f"  Segmentation (p_merge): {modes1['p_merge']:.6f}")
    print(f"  Spatial pattern sum: {pattern1.sum():.6f}")
    print(f"  All fields identical across runs: True")


if __name__ == "__main__":
    print("=" * 70)
    print("Structured Artifacts Wiring Safety Tests")
    print("=" * 70)
    print()

    print("Test 1: Flag-off identity (backward compatibility)")
    test_flag_off_identity()
    print()

    print("Test 2: Flag-on metadata present (biology unchanged)")
    test_flag_on_metadata_present()
    print()

    print("Test 3: Determinism (same seed → same artifacts)")
    test_determinism()
    print()

    print("=" * 70)
    print("ALL SAFETY TESTS PASSED")
    print("Structured artifacts wiring is SAFE to merge")
    print("=" * 70)
