# Imaging Artifacts Wiring Design

**Status**: DESIGN ONLY (not implemented)
**Date**: 2025-12-23

---

## Overview

How to wire structured imaging artifacts into Cell Painting assay without poisoning determinism or creating a second simulator inside the artifact module.

**Core principle**: Three layers, single adapter, explicit flag, byte-identical default.

---

## Layer A: Single Adapter Function

Create **one function** in `cell_painting.py` that assembles all artifacts:

```python
def _compute_structured_imaging_artifacts(
    self,
    vessel: VesselState,
    well_position: str,
    experiment_seed: int,
    enable_channel_weights: bool = True,
    enable_segmentation_modes: bool = True,
    enable_spatial_field: bool = True
) -> Dict[str, Any]:
    """
    Compute all structured imaging artifacts from vessel state.

    This is the ONLY place that calls the three core functions.
    Does NOT apply artifacts - just reports them.
    Does NOT touch RNG.

    Args:
        vessel: Vessel state with debris tracking
        well_position: Well ID like "A01" (for spatial field)
        experiment_seed: Seed for this plate instance (for spatial field)
        enable_channel_weights: Return per-channel background (default True)
        enable_segmentation_modes: Return merge/split modes (default True)
        enable_spatial_field: Return spatial pattern (default True)

    Returns:
        {
            # Background fluorescence
            'background': {
                '__global__': 1.01  # If channel_weights disabled
                # OR
                'er': 1.008, 'mito': 1.008, 'nucleus': 1.01,
                'actin': 1.013, 'rna': 1.015
            },

            # Segmentation failures
            'segmentation': {
                'scalar_bump': 0.0004,  # Old scalar (always computed for backward compat)
                'modes': {  # If modes enabled
                    'p_merge': 0.0002,
                    'p_split': 0.0001,
                    'merge_severity': 2.1,
                    'split_severity': 2.05
                }
            },

            # Spatial field
            'spatial': {  # If spatial enabled
                'field_strength': 0.033,
                'spatial_pattern': np.ndarray,  # 3x3
                'texture_corruption': 0.01,
                'edge_amplification': 1.0
            },

            # Diagnostics
            'debris_cells': 122.0,
            'initial_cells': 3000.0,
            'adherent_cells': 5653.0
        }

    Contract:
        - Pure function (no state mutation)
        - No RNG consumption
        - Stable schema (callers can depend on keys)
        - Backward compatible (scalar always present)
    """
    from ...sim.imaging_artifacts_core import (
        compute_background_multipliers_by_channel,
        compute_segmentation_failure_modes,
        compute_segmentation_failure_probability_bump,
        compute_debris_field_modifiers,
    )

    debris_cells = float(getattr(vessel, 'debris_cells', 0.0))
    initial_cells = float(getattr(vessel, 'initial_cells', 1.0))
    adherent_cells = float(max(1.0, vessel.cell_count))
    confluence = float(vessel.confluence)

    # Determine if edge well
    is_edge = self.vm._is_edge_well(well_position) if hasattr(self, 'vm') else False

    # Background multipliers
    if enable_channel_weights:
        # Per-channel weights (RNA/Actin more sensitive)
        channel_weights = {
            'rna': 1.5,
            'actin': 1.3,
            'nucleus': 1.0,
            'er': 0.8,
            'mito': 0.8
        }
        bg_mults = compute_background_multipliers_by_channel(
            debris_cells=debris_cells,
            initial_cells=initial_cells,
            channel_weights=channel_weights
        )
    else:
        # Scalar (backward compatible)
        bg_mults = compute_background_multipliers_by_channel(
            debris_cells=debris_cells,
            initial_cells=initial_cells,
            channel_weights=None
        )

    # Segmentation failures
    seg_scalar = compute_segmentation_failure_probability_bump(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells
    )

    seg_result = {'scalar_bump': seg_scalar}
    if enable_segmentation_modes:
        seg_modes = compute_segmentation_failure_modes(
            debris_cells=debris_cells,
            adherent_cell_count=adherent_cells,
            confluence=confluence
        )
        seg_result['modes'] = seg_modes

    # Spatial field
    spatial_result = None
    if enable_spatial_field:
        spatial_result = compute_debris_field_modifiers(
            debris_cells=debris_cells,
            initial_cells=initial_cells,
            is_edge=is_edge,
            well_id=well_position,
            experiment_seed=experiment_seed
        )

    return {
        'background': bg_mults,
        'segmentation': seg_result,
        'spatial': spatial_result,
        'debris_cells': debris_cells,
        'initial_cells': initial_cells,
        'adherent_cells': adherent_cells,
    }
```

---

## Layer B: Two Application Points

Apply artifacts at **exactly two points**, nowhere else:

### Application Point 1: Background Multipliers

In `_apply_measurement_layer()`:

```python
def _apply_measurement_layer(self, vessel, morph, **kwargs):
    # ... existing viability_factor, washout_multiplier ...

    # Debris background fluorescence multiplier
    if kwargs.get('enable_structured_artifacts', False):
        artifacts = self._structured_artifacts  # Cached from measure()
        bg_mults = artifacts['background']

        if '__global__' in bg_mults:
            # Scalar mode (backward compatible)
            global_mult = bg_mults['__global__']
            for channel in morph:
                morph[channel] *= global_mult
        else:
            # Per-channel mode
            for channel in morph:
                mult = bg_mults.get(channel, 1.0)
                morph[channel] *= mult
    else:
        # Old scalar (Phase 1)
        debris_multiplier = self._compute_debris_background_multiplier(vessel)
        for channel in morph:
            morph[channel] *= debris_multiplier

    return morph
```

### Application Point 2: Segmentation Failures

In `_apply_segmentation_failure()`:

```python
def _apply_segmentation_failure(self, vessel, morph, qc_metadata, **kwargs):
    # ... existing segmentation quality computation ...

    if kwargs.get('enable_structured_artifacts', False):
        artifacts = self._structured_artifacts  # Cached from measure()
        seg = artifacts['segmentation']

        # Apply modes if available
        if 'modes' in seg:
            modes = seg['modes']
            # Apply merge distortion (reduces count, increases mean area)
            # Apply split distortion (increases count, decreases mean area, inflates texture)
            # TODO: Implement distortion application
            seg_quality_adjusted = seg_quality_original * (1.0 - modes['p_merge'] - modes['p_split'])
        else:
            # Fall back to scalar
            seg_quality_adjusted = seg_quality_original * (1.0 - seg['scalar_bump'])
    else:
        # Old scalar (Phase 1)
        seg_fail_bump = self._compute_debris_segmentation_failure_bump(vessel)
        seg_quality_adjusted = seg_quality_original * (1.0 - seg_fail_bump)

    return seg_quality_adjusted
```

**CRITICAL**: Do NOT let spatial field leak into global background multiplier. Keep it as **texture-local corruption only** (modulate texture/granularity features, not channel intensities).

---

## Layer C: Feature Flag

Add flag to `measure()` signature:

```python
def measure(self, vessel: VesselState, **kwargs) -> Dict[str, Any]:
    """
    Simulate Cell Painting morphology assay.

    Args:
        enable_structured_artifacts: Enable structured artifacts (default False)
            If False: uses Phase 1 scalar artifacts (backward compatible)
            If True: uses Phase 2 structured artifacts (merge/split, per-channel, spatial)
    """
    enable_structured = kwargs.get('enable_structured_artifacts', False)

    if enable_structured:
        # Compute artifacts once, cache for application points
        self._structured_artifacts = self._compute_structured_imaging_artifacts(
            vessel=vessel,
            well_position=kwargs.get('well_position', 'A01'),
            experiment_seed=kwargs.get('experiment_seed', 0),
        )
    else:
        self._structured_artifacts = None

    # ... rest of measurement pipeline ...
    # Application points use kwargs.get('enable_structured_artifacts') to branch
```

---

## Integration Tests (When Wiring)

### Test 1: Off-by-Default Identity

```python
def test_structured_artifacts_off_by_default_identity():
    """
    Flag off produces byte-identical output to Phase 1 pipeline.

    This is the most important test. If it fails, you broke backward compatibility.
    """
    seed = 42
    vm1 = BiologicalVirtualMachine(seed=seed)
    vm1.seed_vessel("well_A1", "A549", vessel_type="384-well")
    vm1.advance_time(48)
    vm1.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    # Measure with flag off (should use Phase 1 scalar)
    result1 = vm1.cell_painting_assay("well_A1", enable_structured_artifacts=False)

    # Measure again with same seed
    vm2 = BiologicalVirtualMachine(seed=seed)
    vm2.seed_vessel("well_A1", "A549", vessel_type="384-well")
    vm2.advance_time(48)
    vm2.wash_vessel("well_A1", n_washes=3, intensity=0.5)
    result2 = vm2.cell_painting_assay("well_A1", enable_structured_artifacts=False)

    # Must be byte-identical
    for channel in result1['morphology']:
        assert result1['morphology'][channel] == result2['morphology'][channel], \
            f"Non-determinism detected in {channel}"
```

### Test 2: On Changes Only Measurements

```python
def test_structured_artifacts_measurement_only():
    """
    Structured artifacts affect measurements, not biology.

    Covenant: artifacts corrupt measurements, never affect vessel state.
    """
    seed = 42
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("well_A1", "A549", vessel_type="384-well")
    vm.advance_time(48)
    vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)

    vessel = vm.vessel_states["well_A1"]
    pre_state = (vessel.cell_count, vessel.viability, vessel.debris_cells)

    # Measure with structured artifacts on
    result = vm.cell_painting_assay("well_A1", enable_structured_artifacts=True)

    post_state = (vessel.cell_count, vessel.viability, vessel.debris_cells)

    # Biology state must be unchanged
    assert pre_state == post_state, \
        "Structured artifacts mutated vessel state (covenant violation)"

    # Measurements should be affected (more debris → worse quality)
    assert 'imaging_artifacts' in result, \
        "Artifact dict missing (should be top-level key)"
```

### Test 3: Determinism

```python
def test_structured_artifacts_determinism():
    """
    Same seed → identical artifacts and measurements.
    """
    seed = 42

    def run_measurement(seed):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("well_A1", "A549", vessel_type="384-well")
        vm.advance_time(48)
        vm.wash_vessel("well_A1", n_washes=3, intensity=0.5)
        return vm.cell_painting_assay(
            "well_A1",
            enable_structured_artifacts=True,
            experiment_seed=seed
        )

    result1 = run_measurement(seed)
    result2 = run_measurement(seed)

    # Artifact dict must be identical
    artifacts1 = result1['imaging_artifacts']
    artifacts2 = result2['imaging_artifacts']

    assert artifacts1['debris_cells'] == artifacts2['debris_cells']
    assert artifacts1['segmentation']['scalar_bump'] == artifacts2['segmentation']['scalar_bump']

    # Spatial pattern must be identical (deterministic from well_id hash)
    if artifacts1['spatial'] and artifacts2['spatial']:
        import numpy as np
        assert np.array_equal(
            artifacts1['spatial']['spatial_pattern'],
            artifacts2['spatial']['spatial_pattern']
        )
```

---

## Metadata Logging (Audit Trail)

When wiring, log artifact dict into measurement output:

```python
# In measure(), after computing artifacts:
if enable_structured:
    result['imaging_artifacts'] = self._structured_artifacts
else:
    # Log scalar artifacts for consistency (top-level key)
    result['imaging_artifacts'] = {
        'background': {'__global__': debris_bg_mult},
        'segmentation': {'scalar_bump': seg_fail_bump},
        'spatial': None,
        'debris_cells': vessel.debris_cells,
        'initial_cells': vessel.initial_cells,
        'adherent_cells': vessel.cell_count,
    }
```

**Why log artifacts?**

When agent does something weird, you need to prove whether it exploited:
- Biology (compound mechanism, confluence, etc.)
- Measurement corruption (debris artifacts)

Without artifact metadata in measurement output, you can't audit decisions. This is not pretty, but it's essential for post-hoc analysis.

**Example audit query**:
```python
# Did agent select wells with high debris?
high_artifact_wells = [
    w for w in measurements
    if w['imaging_artifacts']['segmentation']['scalar_bump'] > 0.01
]
# If yes → agent exploited measurement corruption (bad)
# If no → agent used biological signal (good)
```

---

## Current Cell Painting Output Schema

**Actual schema** (flat, no nested metadata):

```python
{
    # Core outputs
    'morphology': {'er': float, 'mito': float, 'nucleus': float, 'actin': float, 'rna': float},
    'cell_count_observed': int,
    'viability': float,

    # QC fields
    'segmentation_quality': float,
    'segmentation_quality_pre_debris': float,
    'debris_seg_fail_bump': float,
    'segmentation_qc_passed': bool,

    # Artifact diagnostics
    'debris_load': float,
    'handling_loss_fraction': float,
    'noise_mult': float,
    'artifact_level': float,

    # ... many other flat fields ...
}
```

**Recommendation**: Add artifact dict as **top-level key** (not nested):

```python
result['imaging_artifacts'] = {
    'background': {...},
    'segmentation': {...},
    'spatial': {...},
    'debris_cells': float,
    'initial_cells': float,
    'adherent_cells': float,
}
```

This keeps it separate from existing flat diagnostics while remaining auditable.

---

## Implementation Checklist

When ready to wire:

- [ ] Create `_compute_structured_imaging_artifacts()` adapter
- [ ] Add `enable_structured_artifacts` flag to `measure()` signature (default False)
- [ ] Wire background multipliers in `_apply_measurement_layer()`
- [ ] Wire segmentation modes in `_apply_segmentation_failure()`
- [ ] Do NOT wire spatial field to global background (texture-local only)
- [ ] Add artifact dict to `result['imaging_artifacts']` (top-level key)
- [ ] Write Test 1: Off-by-default identity (byte-identical)
- [ ] Write Test 2: Measurement-only (biology unchanged)
- [ ] Write Test 3: Determinism (same seed → same artifacts)
- [ ] Validate typical effects (standard wash: negligible, rough: small, trashed: amplified)
- [ ] Document wiring in `IMAGING_ARTIFACTS_COMPLETE.md` (Phase 3 section)

---

## Status

✅ **DESIGN COMPLETE** (not implemented)

- Three-layer architecture defined
- Single adapter function specified
- Two explicit application points identified
- Feature flag contract defined
- Three integration tests specified
- Metadata logging strategy defined

**Next step**: Implement when ready, using this design as blueprint.

**Anti-pattern to avoid**: Cramming logic directly into measurement pipeline. Use adapter + flag + tests.
