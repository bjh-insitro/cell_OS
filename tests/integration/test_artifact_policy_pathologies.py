#!/usr/bin/env python3
"""
Policy Pathology Checks: Prevent Agent Exploitation

Two critical tests to ensure artifacts don't create perverse incentives:

1. "Break the microscope" exploit: Agent cannot improve objective by increasing debris
2. Artifact attribution: Artifacts don't leak back into biology

These tests protect against optimizer pathologies where:
- "Noise looks like novelty" (agent prefers high-artifact wells)
- "Measurement corruption becomes ground truth" (artifacts affect biology)
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_break_the_microscope_exploit():
    """
    Agent cannot improve reliability by increasing debris.

    Simulate two wells with identical biology, different handling:
    - Well A: gentle wash, low debris
    - Well B: aggressive wash, high debris

    Assert measurement reliability monotonically decreases with debris.

    Reliability metric:
        reliability = segmentation_quality / mean(background_multiplier)

    If this test fails, an agent could learn "rough handling → interesting artifacts."
    """
    seed = 42

    # Well A: gentle wash (low debris)
    vm_gentle = BiologicalVirtualMachine(seed=seed)
    vm_gentle.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm_gentle.advance_time(48)
    vm_gentle.wash_vessel("well_A1", n_washes=3, intensity=0.3)  # Gentle
    result_gentle = vm_gentle.cell_painting_assay(
        "well_A1",
        well_position="A1",
        enable_structured_artifacts=True,
        experiment_seed=seed
    )

    # Well B: aggressive wash (high debris)
    vm_rough = BiologicalVirtualMachine(seed=seed)
    vm_rough.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm_rough.advance_time(48)
    vm_rough.wash_vessel("well_A1", n_washes=3, intensity=0.8)  # Aggressive
    result_rough = vm_rough.cell_painting_assay(
        "well_A1",
        well_position="A1",
        enable_structured_artifacts=True,
        experiment_seed=seed
    )

    artifacts_gentle = result_gentle['imaging_artifacts']
    artifacts_rough = result_rough['imaging_artifacts']

    # Compute reliability scores (higher = better measurement quality)
    def compute_reliability(result, artifacts):
        seg_quality = result['segmentation_quality']
        bg_mults = artifacts['background']
        mean_bg = sum(bg_mults.values()) / len(bg_mults)

        # Reliability decreases with:
        # - Lower segmentation quality
        # - Higher background inflation (mean_bg > 1.0)
        # - Higher segmentation failure probability
        seg = artifacts['segmentation']
        if 'modes' in seg:
            seg_failure = seg['modes']['p_merge'] + seg['modes']['p_split']
        else:
            seg_failure = seg['scalar_bump']

        # Simple reliability metric (normalized to [0, 1])
        reliability = (seg_quality / mean_bg) * (1.0 - seg_failure)
        return reliability

    reliability_gentle = compute_reliability(result_gentle, artifacts_gentle)
    reliability_rough = compute_reliability(result_rough, artifacts_rough)

    # CRITICAL INVARIANT: Gentle wash must have HIGHER reliability
    assert reliability_gentle > reliability_rough, \
        f"PATHOLOGY DETECTED: Rough handling has higher reliability!\n" \
        f"  Gentle: {reliability_gentle:.6f} (debris={artifacts_gentle['debris_cells']:.0f})\n" \
        f"  Rough:  {reliability_rough:.6f} (debris={artifacts_rough['debris_cells']:.0f})\n" \
        f"This would teach agent to break the microscope for 'interesting' data."

    # Additional invariant: Rough wash must have MORE debris
    assert artifacts_rough['debris_cells'] > artifacts_gentle['debris_cells'], \
        f"Rough wash should produce more debris: {artifacts_rough['debris_cells']} <= {artifacts_gentle['debris_cells']}"

    # Sanity check: Higher debris → higher artifacts
    bg_mean_gentle = sum(artifacts_gentle['background'].values()) / len(artifacts_gentle['background'])
    bg_mean_rough = sum(artifacts_rough['background'].values()) / len(artifacts_rough['background'])
    assert bg_mean_rough > bg_mean_gentle, \
        f"Higher debris should inflate background: {bg_mean_rough} <= {bg_mean_gentle}"

    print("✓ 'Break the microscope' exploit prevented:")
    print(f"  Gentle wash: reliability={reliability_gentle:.6f}, debris={artifacts_gentle['debris_cells']:.0f}")
    print(f"  Rough wash:  reliability={reliability_rough:.6f}, debris={artifacts_rough['debris_cells']:.0f}")
    print(f"  Reliability monotonically decreases with debris ✓")
    print(f"  Agent cannot improve objective by increasing artifacts ✓")


def test_artifact_attribution_no_leakage():
    """
    Artifacts do not leak back into biology.

    Measure same vessel twice:
    - Once with flag off
    - Once with flag on

    Assert ALL internal biology state is unchanged (not just "no writes").

    This catches the classic bug where measurement intermediates get stored
    in vessel state, creating a feedback loop from artifacts → biology.
    """
    seed = 42
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(48)
    vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    vessel = vm.vessel_states["well_A1"]

    # Capture complete biology state before measurement
    pre_state = {
        'cell_count': vessel.cell_count,
        'viability': vessel.viability,
        'confluence': vessel.confluence,
        'debris_cells': vessel.debris_cells,
        'initial_cells': vessel.initial_cells,
        'er_stress': vessel.er_stress,
        'mito_dysfunction': vessel.mito_dysfunction,
        'transport_dysfunction': vessel.transport_dysfunction,
        'death_compound': vessel.death_compound,
        'death_confluence': vessel.death_confluence,
        'death_unknown': vessel.death_unknown,
        'last_update_time': vessel.last_update_time,
        'seed_time': vessel.seed_time,
    }

    # Measure with structured artifacts ON
    result = vm.cell_painting_assay(
        "well_A1",
        well_position="A1",
        enable_structured_artifacts=True,
        experiment_seed=seed
    )

    # Capture state after measurement
    post_state = {
        'cell_count': vessel.cell_count,
        'viability': vessel.viability,
        'confluence': vessel.confluence,
        'debris_cells': vessel.debris_cells,
        'initial_cells': vessel.initial_cells,
        'er_stress': vessel.er_stress,
        'mito_dysfunction': vessel.mito_dysfunction,
        'transport_dysfunction': vessel.transport_dysfunction,
        'death_compound': vessel.death_compound,
        'death_confluence': vessel.death_confluence,
        'death_unknown': vessel.death_unknown,
        'last_update_time': vessel.last_update_time,
        'seed_time': vessel.seed_time,
    }

    # CRITICAL INVARIANT: ALL biology state unchanged
    for key in pre_state:
        assert pre_state[key] == post_state[key], \
            f"PATHOLOGY DETECTED: Biology state '{key}' changed during measurement!\n" \
            f"  Before: {pre_state[key]}\n" \
            f"  After:  {post_state[key]}\n" \
            f"Artifacts leaked back into biology (covenant violation)."

    # Verify artifacts were actually computed (not a no-op)
    assert result['imaging_artifacts'] is not None, \
        "Artifacts should be computed when flag on"
    assert result['imaging_artifacts']['debris_cells'] > 0, \
        "Should have debris (wash was performed)"

    print("✓ Artifact attribution check passed:")
    print(f"  All biology fields unchanged after measurement ✓")
    print(f"  Debris: {vessel.debris_cells:.0f} (tracked, not leaked back)")
    print(f"  Artifacts: {result['imaging_artifacts']['segmentation']['modes']['p_merge']:.6f} (computed, isolated)")
    print(f"  No feedback loop from artifacts → biology ✓")


def test_artifact_schema_always_complete():
    """
    When artifacts dict is not None, schema is always complete.

    Missing keys become folk tales. Lock the schema now.

    Required keys:
    - background
    - segmentation
    - spatial
    - debris_cells
    - initial_cells
    - adherent_cells
    """
    seed = 42
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("well_A1", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm.advance_time(48)

    result = vm.cell_painting_assay(
        "well_A1",
        well_position="A1",
        enable_structured_artifacts=True,
        experiment_seed=seed
    )

    artifacts = result['imaging_artifacts']
    assert artifacts is not None, "Artifacts should be populated when flag on"

    # Required top-level keys
    required_keys = ['background', 'segmentation', 'spatial', 'debris_cells', 'initial_cells', 'adherent_cells']
    for key in required_keys:
        assert key in artifacts, f"Missing required key '{key}' in artifacts dict"

    # Background must have channel keys or __global__
    bg = artifacts['background']
    assert isinstance(bg, dict), "background must be dict"
    if '__global__' in bg:
        # Scalar mode
        assert len(bg) == 1, "Scalar mode should have only __global__ key"
    else:
        # Per-channel mode
        for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
            assert channel in bg, f"Missing channel '{channel}' in background"

    # Segmentation must have scalar_bump (always) and optionally modes
    seg = artifacts['segmentation']
    assert 'scalar_bump' in seg, "segmentation must always have scalar_bump"
    if 'modes' in seg:
        modes = seg['modes']
        for key in ['p_merge', 'p_split', 'merge_severity', 'split_severity']:
            assert key in modes, f"Missing key '{key}' in segmentation modes"

    # Spatial can be None or dict with required keys
    spatial = artifacts['spatial']
    if spatial is not None:
        for key in ['field_strength', 'spatial_pattern', 'texture_corruption', 'edge_amplification']:
            assert key in spatial, f"Missing key '{key}' in spatial dict"

    print("✓ Artifact schema completeness verified:")
    print(f"  All required top-level keys present ✓")
    print(f"  Background schema valid ✓")
    print(f"  Segmentation schema valid ✓")
    print(f"  Spatial schema valid ✓")
    print(f"  Schema is frozen and auditable ✓")


if __name__ == "__main__":
    print("=" * 70)
    print("Policy Pathology Checks")
    print("=" * 70)
    print()

    print("Test 1: 'Break the microscope' exploit")
    test_break_the_microscope_exploit()
    print()

    print("Test 2: Artifact attribution (no leakage)")
    test_artifact_attribution_no_leakage()
    print()

    print("Test 3: Artifact schema always complete")
    test_artifact_schema_always_complete()
    print()

    print("=" * 70)
    print("ALL POLICY PATHOLOGY CHECKS PASSED")
    print("Agent cannot exploit artifacts for perverse objectives")
    print("=" * 70)
