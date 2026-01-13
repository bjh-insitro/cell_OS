# Imaging Artifacts Structured Extension

**Date**: 2025-12-23
**Status**: ✅ CORE + TESTS COMPLETE (not yet wired into Cell Painting)

---

## Summary

Extended `imaging_artifacts_core.py` with three structured artifact functions:

1. **Segmentation failure modes** - Splits scalar failure into merge/split with severities
2. **Channel-weighted background multipliers** - Per-channel sensitivity (RNA/Actin more sensitive)
3. **Spatial debris field** - 3x3 deterministic pattern for locality effects

**CRITICAL**: These are NOT yet wired into Cell Painting assay. Per user instruction:
> "Do it **core + tests now, wiring later**. If you wire it immediately, you'll spend the next week debugging 'why did my morphology manifold move' when the real answer is 'you turned on a new measurement corruption surface.'"

---

## Architecture

### Pure Functions Added to `imaging_artifacts_core.py`

All functions are **pure deterministic math** (no RNG, no side effects):

#### 1. `compute_segmentation_failure_modes()`

```python
def compute_segmentation_failure_modes(
    debris_cells: float,
    adherent_cell_count: float,
    confluence: float = 0.5,
    base_merge: float = 0.0,
    base_split: float = 0.0,
    merge_coefficient: float = 0.03,
    split_coefficient: float = 0.01,
    max_total: float = 0.5
) -> Dict[str, float]:
    """
    Returns:
        {
            'p_merge': float,  # [0, 0.4]
            'p_split': float,  # [0, 0.4]
            'merge_severity': float,  # [2.0, 3.0]
            'split_severity': float,  # [2.0, 3.0]
        }

    Invariants:
        - p_merge + p_split <= max_total (renormalized if needed)
        - High confluence → p_merge/p_split ratio increases
        - Low confluence → p_merge/p_split ratio decreases
    """
```

**Key feature**: Confluence bias
- High confluence (0.9): merge bias 0.95, split bias 1.05
- Low confluence (0.1): merge bias 0.55, split bias 1.45

**Example**:
```python
# High confluence scenario (cells touching)
result = compute_segmentation_failure_modes(
    debris_cells=500, adherent_cell_count=10000, confluence=0.9
)
# → p_merge=0.001425 (0.14%), p_split=0.000525 (0.05%)
# Merge dominates (cells actually touching)

# Low confluence scenario (cells sparse)
result = compute_segmentation_failure_modes(
    debris_cells=500, adherent_cell_count=2000, confluence=0.2
)
# → p_merge=0.0045 (0.45%), p_split=0.0035 (0.35%)
# Split more prominent (debris fragments look like cells)
```

---

#### 2. `compute_background_multipliers_by_channel()`

```python
def compute_background_multipliers_by_channel(
    debris_cells: float,
    initial_cells: float,
    channel_weights: Optional[Dict[str, float]] = None,
    base_multiplier: float = 1.0,
    debris_coefficient: float = 0.05,
    max_multiplier: float = 1.25
) -> Dict[str, float]:
    """
    Returns:
        If channel_weights is None:
            {"__global__": scalar}  # Backward compatible
        Else:
            {'er': 1.01, 'mito': 1.01, 'nucleus': 1.015, 'actin': 1.02, 'rna': 1.025}

    Invariants:
        - All multipliers >= base_multiplier
        - All multipliers <= max_multiplier
        - channel_weights clamped to [0.5, 2.0] (defensive)
    """
```

**Backward compatible**: `channel_weights=None` returns scalar in `"__global__"` key.

**Channel sensitivity** (typical weights):
- RNA: 1.5 (weak signal, more sensitive)
- Actin: 1.3 (intermediate)
- Nucleus: 1.0 (baseline)
- ER: 0.8 (strong signal, less sensitive)
- Mito: 0.8 (strong signal, less sensitive)

**Example**:
```python
# Backward compatible (scalar)
result = compute_background_multipliers_by_channel(
    debris_cells=600, initial_cells=3000, channel_weights=None
)
# → {"__global__": 1.01}

# Per-channel (structured)
weights = {'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
result = compute_background_multipliers_by_channel(
    debris_cells=600, initial_cells=3000, channel_weights=weights
)
# → {'rna': 1.015, 'actin': 1.013, 'nucleus': 1.01, 'er': 1.008, 'mito': 1.008}
```

---

#### 3. `compute_debris_field_modifiers()`

```python
def compute_debris_field_modifiers(
    debris_cells: float,
    initial_cells: float,
    is_edge: bool,
    well_id: str,
    experiment_seed: int,
    field_resolution: int = 3
) -> Dict[str, Any]:
    """
    Returns:
        {
            'field_strength': float,  # [0, 1]
            'spatial_pattern': np.ndarray,  # 3x3 with mean 1.0, bounded [0.7, 1.3]
            'texture_corruption': float,  # [0, 0.3]
            'edge_amplification': float,  # [1.0, 1.4] if edge, else 1.0
        }

    Invariants:
        - spatial_pattern.mean() ≈ 1.0 (±1e-6)
        - spatial_pattern values in [0.7, 1.3]
        - Deterministic: same inputs → same pattern
        - Edge wells have higher pattern variance
    """
```

**Deterministic pattern**: Uses `hashlib.sha256(f"{experiment_seed}_{well_id}_{is_edge}")` to seed RNG. This is NOT per-measurement randomness - it's a fixed spatial pattern for this well in this plate instance.

**Edge amplification**:
- Interior: spatial_cv = 0.08 (low variance)
- Edge: spatial_cv = 0.15 (high variance, meniscus effects)

**Example**:
```python
# Interior well, low debris
result = compute_debris_field_modifiers(
    debris_cells=100, initial_cells=3000, is_edge=False,
    well_id="B03", experiment_seed=42
)
# → field_strength=0.033, spatial_pattern=[[0.98, 1.02, 0.99], ...],
#   texture_corruption=0.01, edge_amplification=1.0

# Edge well, high debris
result = compute_debris_field_modifiers(
    debris_cells=1000, initial_cells=3000, is_edge=True,
    well_id="A01", experiment_seed=42
)
# → field_strength=0.333, spatial_pattern=[[0.85, 1.15, 0.95], ...],
#   texture_corruption=0.10, edge_amplification=1.13
```

---

## Test Coverage: 11 tests, all passing ✅

### Segmentation Failure Modes (4 tests)

1. ✅ **Monotonicity**: More debris → higher p_merge and p_split
2. ✅ **Bounds**: p_merge, p_split ∈ [0, 0.4]; severities ∈ [2.0, 3.0]
3. ✅ **Max total renormalization**: p_merge + p_split ≤ max_total, ratio preserved
4. ✅ **Confluence bias**: High confluence → merge dominates, low → split more prominent

### Background Multipliers (3 tests)

5. ✅ **Backward compatible**: `channel_weights=None` returns `{"__global__": scalar}`
6. ✅ **Per-channel ordering**: Higher weight → higher multiplier (rna > actin > nucleus > er ≈ mito)
7. ✅ **Bounds**: All channels ≤ max_multiplier, weights clamped to [0.5, 2.0]

### Spatial Debris Field (4 tests)

8. ✅ **Determinism**: Same (experiment_seed, well_id, is_edge) → identical pattern
9. ✅ **Edge variance**: is_edge=True → higher pattern variance + edge_amplification
10. ✅ **Strength monotonic**: More debris → higher field_strength and texture_corruption
11. ✅ **Spatial pattern invariants**: mean ≈ 1.0 (±1e-6), values ∈ [0.7, 1.3], shape=(3,3)

---

## Design Principles (Preserved from Phase 1)

✅ **Pure functions**: No side effects, no RNG (except deterministic hash for spatial pattern)
✅ **Hard bounds**: Clamps prevent explosion
✅ **Monotonic**: More debris never improves quality
✅ **Deterministic**: Stable outputs given inputs
✅ **Composable**: Modifiers stack without interference

---

## Covenant (Unchanged)

**Artifacts affect MEASUREMENTS, never BIOLOGY.**

- Wash/fixation → debris → imaging quality degradation
- Compounds → stress program → morphology program
- Never let measurement corruption create stress-like morphology

---

## Files Created/Modified

### Modified
- `src/cell_os/biology/imaging_artifacts_core.py` (added 3 new functions, ~370 lines)

### Created
- `tests/unit/test_imaging_artifacts_structured.py` (11 tests, ~550 lines)
- `docs/IMAGING_ARTIFACTS_STRUCTURED_EXTENSION.md` (this document)

---

## NOT Done (Intentionally)

- ❌ **Cell Painting wiring**: Not integrated into `cell_painting.py` yet
- ❌ **Flag in Cell Painting**: No placeholder flag (wait for wiring design)
- ❌ **Integration test**: No end-to-end test (wait for wiring)

**Reason**: User's explicit instruction:
> "If you wire it immediately, you'll spend the next week debugging 'why did my morphology manifold move' when the real answer is 'you turned on a new measurement corruption surface.' That is not science. That's astrology with unit tests."

---

## How to Wire (Future Work)

When ready to integrate into Cell Painting:

### Option 1: Replace scalar with structured (breaking change)
```python
# In cell_painting.py _apply_measurement_layer()
modes = compute_segmentation_failure_modes(
    debris_cells=vessel.debris_cells,
    adherent_cell_count=vessel.cell_count,
    confluence=vessel.confluence
)
# Apply merge/split distortions to cell count
```

### Option 2: Add flag with backward compat (safe)
```python
# In cell_painting.py measure()
if kwargs.get('enable_structured_artifacts', False):
    # Use new functions
    modes = compute_segmentation_failure_modes(...)
    channel_mults = compute_background_multipliers_by_channel(...)
    field = compute_debris_field_modifiers(...)
else:
    # Use existing scalar functions
    bg_mult = compute_background_noise_multiplier(...)
    seg_bump = compute_segmentation_failure_probability_bump(...)
```

### Option 3: Always compute, flag controls application
```python
# Always compute structured (cheap)
modes = compute_segmentation_failure_modes(...)
channel_mults = compute_background_multipliers_by_channel(...)

# Flag controls whether to apply
if enable_structured_segmentation:
    apply_merge_split_distortions(morph, modes)
else:
    apply_scalar_segmentation_bump(morph, seg_bump)
```

**Recommendation**: Option 2 (flag with backward compat) for initial integration. Switch to Option 3 once validated.

---

## Validation Before Wiring

Before wiring into Cell Painting, validate:

1. **Typical effects**: Run standalone validation script to check magnitudes
   - Standard wash: seg modes should be negligible (<0.1%)
   - Aggressive wash: seg modes should be small (<1%)
   - Trashed well: seg modes should be significant (>5%)

2. **Edge correlation**: Verify edge wells show higher artifacts
   - Compare edge vs interior in 384-well plate simulation
   - Check spatial pattern variance amplification

3. **Backward compatibility**: Ensure scalar behavior preserved
   - `channel_weights=None` must match old `compute_background_noise_multiplier()`
   - No morphology manifold shift when flag=False

4. **Determinism**: Same seed → same artifacts
   - Run twice with same experiment_seed → identical spatial patterns
   - Verify pattern is NOT per-measurement random

---

## Status

✅ **CORE + TESTS COMPLETE**

- Pure functions implemented with hard bounds
- 11 tests validate all invariants
- Backward compatible APIs
- Deterministic spatial patterns
- No Cell Painting wiring (intentional)

**Ready for validation and wiring design.**

The simulator now has STRUCTURED artifact models that lock:
- Segmentation failure modes (merge/split)
- Channel-specific background sensitivity
- Spatial debris heterogeneity

Next step: Design wiring strategy with explicit flag, validate typical effects, then integrate into Cell Painting when ready.

---

## References

- **Phase 1 scalar artifacts**: `docs/IMAGING_ARTIFACTS_COMPLETE.md`
- **Core module**: `src/cell_os/biology/imaging_artifacts_core.py`
- **Wash/fixation physics**: `docs/WASH_FIXATION_INTEGRATION_COMPLETE.md`
- **Test suite**: `tests/unit/test_imaging_artifacts_structured.py`
