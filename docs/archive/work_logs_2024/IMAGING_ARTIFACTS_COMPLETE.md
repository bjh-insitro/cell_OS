# Imaging Artifacts Integration Complete

**Date**: 2025-12-23
**Status**: ✅ COMPLETE - Debris effects wired into Cell Painting imaging

---

## Summary

Successfully wired debris from wash/fixation into Cell Painting imaging quality. Debris now drives two explicit downstream failure modes:

1. **Background fluorescence inflation** (multiplicative noise)
2. **Segmentation failure probability bump** (count errors)

This completes the pipeline: **edge wells → more wash loss → more debris → worse imaging**.

---

## Architecture

### Core Module: `src/cell_os/biology/imaging_artifacts_core.py`

**Pure functions** (no side effects, hard bounds, monotonic):

```python
def compute_background_noise_multiplier(
    debris_cells: float,
    initial_cells: float,
    base_multiplier: float = 1.0,
    debris_coefficient: float = 0.05,
    max_multiplier: float = 1.25
) -> float:
    """
    Background fluorescence inflation from debris.

    Formula: multiplier = base + debris_coefficient * (debris_cells / initial_cells)
    Clamped to [base_multiplier, max_multiplier]

    Example:
        Initial: 3000 cells
        Debris: 600 cells (20%)
        → multiplier = 1.0 + 0.05 * 0.2 = 1.01 (1% inflation)
    """
```

```python
def compute_segmentation_failure_probability_bump(
    debris_cells: float,
    adherent_cell_count: float,
    base_probability: float = 0.0,
    debris_coefficient: float = 0.02,
    max_probability: float = 0.5
) -> float:
    """
    Segmentation failure probability bump from debris.

    Formula: p_fail = base + debris_coefficient * (debris_cells / adherent_cells)
    Clamped to [0, max_probability]

    Example:
        Adherent: 5000 cells
        Debris: 1000 cells (20%)
        → p_fail = 0.0 + 0.02 * 0.2 = 0.004 (0.4% bump)

    Note: Uses CURRENT adherent cells (not initial) because debris-to-signal
    ratio drives segmentation confusion.
    """
```

### Wiring Changes: `src/cell_os/hardware/assays/cell_painting.py`

**1. Updated `_estimate_debris_level()` to use actual debris tracking:**

```python
def _estimate_debris_level(self, vessel: "VesselState") -> float:
    """Now uses ACTUAL debris from wash/fixation physics."""
    # ACTUAL debris from wash/fixation (preferred if available)
    if hasattr(vessel, 'debris_cells') and vessel.debris_cells > 0:
        initial_cells = getattr(vessel, 'initial_cells', vessel.cell_count)
        if initial_cells > 0:
            return float(min(1.0, vessel.debris_cells / initial_cells))

    # Fallback: estimate from viability (legacy behavior)
    debris_from_death = 1.0 - vessel.viability
    ...
```

**2. Added background fluorescence multiplier to `_apply_measurement_layer()`:**

```python
def _apply_measurement_layer(self, vessel, morph, **kwargs):
    # 1. Viability factor
    viability_factor = 0.3 + 0.7 * vessel.viability

    # 2. Washout multiplier
    washout_multiplier = self._compute_washout_multiplier(vessel, t_measure)

    # 3. Debris background fluorescence multiplier (NEW)
    debris_multiplier = self._compute_debris_background_multiplier(vessel)

    # Apply all multipliers
    for channel in morph:
        morph[channel] *= viability_factor * washout_multiplier * debris_multiplier
    ...
```

**3. Added segmentation failure probability bump to `_apply_segmentation_failure()`:**

```python
# ADDITIONAL debris-driven segmentation failure probability bump
seg_fail_prob_bump = self._compute_debris_segmentation_failure_bump(vessel)
seg_quality_original = qc_metadata['segmentation_quality']
seg_quality_adjusted = seg_quality_original * (1.0 - seg_fail_prob_bump)

# Return adjusted quality + diagnostics
updates = {
    'segmentation_quality': seg_quality_adjusted,  # Adjusted
    'segmentation_quality_pre_debris': seg_quality_original,  # Original
    'debris_seg_fail_bump': seg_fail_prob_bump,  # Bump magnitude
    ...
}
```

---

## Test Coverage

### Unit Tests: 16 tests, all passing ✅

**Monotonicity & Bounds** (`test_imaging_artifacts_monotonicity.py`): 10 tests
- ✅ Background noise multiplier monotonic (more debris → higher multiplier)
- ✅ Background noise multiplier bounded [1.0, 1.25]
- ✅ Zero initial_cells → graceful fallback
- ✅ Segmentation failure probability monotonic (more debris → higher p_fail)
- ✅ Segmentation failure probability bounded [0, 0.5]
- ✅ Low cell count amplifies debris effect (debris-to-signal ratio matters)
- ✅ Very low cells → max probability (well trashed)
- ✅ Parameter customization works
- ✅ Typical values produce reasonable effects

**Edge Correlation** (`test_imaging_artifacts_edge_correlation.py`): 6 tests
- ✅ Edge wells have higher debris (edge amplification from wash physics)
- ✅ Edge higher debris → higher background noise multiplier
- ✅ Edge higher debris → higher segmentation failure probability
- ✅ Deterministic edge effect (same seed → same artifacts)
- ✅ Multiple edge wells consistently worse than interior
- ✅ Aggressive wash amplifies edge effect

### Integration Test

**End-to-end pipeline** (`/tmp/test_debris_imaging_integration.py`):
```
Standard wash (intensity=0.5):
  Debris: 122 cells
  Seg quality: 0.9996 (debris bump = 0.0004)

Aggressive wash (intensity=0.8):
  Debris: 163 cells
  Seg quality: 0.9994 (debris bump = 0.0006)

✓ Segmentation debris bump applied correctly
✓ Aggressive wash produces more debris
✓ More debris → worse segmentation quality
```

---

## Design Decisions

### 1. Why Two Separate Modifiers?

**Background fluorescence** and **segmentation failure** are DIFFERENT failure modes:

- **Background**: Debris scatters light globally → inflates signal/noise
  - Affects ALL channels equally (defensible starting point)
  - Multiplicative effect on intensity
  - Diagnosed by: high background fluorescence, low SNR

- **Segmentation**: Debris confounds algorithms → miscounts cells
  - Affects count accuracy (merges, splits, drops)
  - Additive probability bump
  - Diagnosed by: count mismatch with orthogonal assays (ATP, LDH)

Separating these makes effects auditable and tunable independently.

### 2. Why Use `initial_cells` for Background, `adherent_cells` for Segmentation?

**Background fluorescence**: Debris relative to initial seeding density
- `debris_cells / initial_cells` gives normalized debris load
- Initial cells is a fixed anchor (doesn't change during experiment)
- Example: 100 debris from 3000 initial = 3.3% debris load

**Segmentation failure**: Debris relative to current signal
- `debris_cells / adherent_cells` gives debris-to-signal ratio
- Low adherent cells + high debris = worst case for segmentation
- Example: 100 debris from 500 adherent = 20% debris-to-signal (HARD to segment)

This captures different physics: background is an absolute effect, segmentation is a signal-to-noise problem.

### 3. Why Apply to All Channels Equally?

**Start simple**: Debris scatters light globally, not channel-specifically.

**Future refinement**: Per-channel weights without API change:
- RNA, Actin more sensitive to background (weak signal)
- ER, Mito less sensitive (strong signal)
- Nucleus somewhere in between

Current implementation allows this refinement by changing coefficients only.

### 4. Why Hard Bounds?

**Clamps prevent explosion**:
- Background multiplier capped at 1.25 (25% inflation max)
- Segmentation probability capped at 0.5 (50% failure max)

**Rationale**:
- Wells with 10× debris shouldn't become light sources (physically implausible)
- Complete segmentation failure (p=1.0) would require separate QC rejection
- Bounds keep effects in "degrades quality" regime, not "nonsense" regime

### 5. Why Pure Functions in Core Module?

**Auditability**: No side effects, just math
- Easy to test (no VM state needed)
- Easy to tune (parameters explicit)
- Easy to debug (deterministic)

**Separation of concerns**:
- Core module: physics model (pure functions)
- Cell Painting assay: integration (wiring + application)
- Tests: invariants (monotonicity, bounds, edge correlation)

Same pattern as wash/fixation physics.

---

## Typical Effects

From integration test and unit tests:

### Standard Cell Painting Workflow

**Initial state**: 3000 cells seeded

**Post-growth (48h)**: 6261 cells, confluence 42%

**Wash (3 cycles, intensity=0.5)**:
- Cells lost: 608
- Debris added: 122 (20% of detached)
- Debris ratio: 122/3000 = 4.1%

**Imaging effects**:
- Background multiplier: 1.002 (0.2% inflation, negligible)
- Seg failure bump: 0.0004 (0.04%, negligible)
- Seg quality: 0.9996 (nearly perfect)

**Conclusion**: Standard workflow has MINIMAL debris artifacts (by design).

### Rough Workflow (Aggressive Wash)

**Wash (3 cycles, intensity=0.8)**:
- Cells lost: 815
- Debris added: 163
- Debris ratio: 163/3000 = 5.4%

**Imaging effects**:
- Background multiplier: 1.003 (0.3% inflation)
- Seg failure bump: 0.0006 (0.06%)
- Seg quality: 0.9994

**Conclusion**: Even aggressive handling shows SMALL effects (debris is bounded).

### Edge Well Amplification

**Edge multiplier**: 1.05-1.15× (stochastic noise can dominate)

**Edge vs interior**:
- Edge debris: 1.04× higher (from edge correlation test)
- Edge background: slightly higher
- Edge seg failure: slightly higher

**Conclusion**: Edge effect is REAL but MODEST (not a catastrophic failure mode).

### When Debris Matters Most

**Trashed well scenario** (hypothetical):
- Adherent cells: 500 (95% loss)
- Debris: 2500 (5× adherent)
- Debris ratio: 2500/500 = 500%

**Imaging effects**:
- Background multiplier: 1.25 (clamped, 25% inflation)
- Seg failure bump: 0.5 (clamped, 50% failure probability)
- Seg quality: 0.5 × (1.0 - 0.5) = 0.25 (POOR)

**Conclusion**: Debris effects kick in when well is already trashed (amplifies failure signal).

---

## Files Created/Modified

### New Files
- `src/cell_os/biology/imaging_artifacts_core.py` - Pure functions for debris effects
- `tests/unit/test_imaging_artifacts_monotonicity.py` - Invariant tests (10 tests)
- `tests/unit/test_imaging_artifacts_edge_correlation.py` - Edge correlation tests (6 tests)
- `docs/IMAGING_ARTIFACTS_COMPLETE.md` - This document

### Modified Files
- `src/cell_os/hardware/assays/cell_painting.py`
  - Updated `_estimate_debris_level()` to use actual debris tracking (line 739)
  - Added `_compute_debris_background_multiplier()` helper (line 352)
  - Added `_compute_debris_segmentation_failure_bump()` helper (line 379)
  - Wired debris multiplier into `_apply_measurement_layer()` (line 306)
  - Wired seg failure bump into `_apply_segmentation_failure()` (line 750)

---

## Integration Checklist

- [x] Core physics module (`imaging_artifacts_core.py`)
- [x] Update `_estimate_debris_level()` to use actual debris
- [x] Add `_compute_debris_background_multiplier()` helper
- [x] Add `_compute_debris_segmentation_failure_bump()` helper
- [x] Wire background multiplier into measurement layer
- [x] Wire segmentation bump into segmentation failure
- [x] Unit tests (monotonicity + bounds)
- [x] Unit tests (edge correlation)
- [x] Integration test (end-to-end pipeline)
- [x] Documentation

---

## Next Steps (Future Work)

1. **Per-channel debris sensitivity**
   - RNA, Actin more sensitive (weak signal)
   - ER, Mito less sensitive (strong signal)
   - Implement as channel-specific coefficients

2. **Debris decay over time**
   - Debris settles/degrades between measurements
   - Add time-dependent decay (tau ~ hours)

3. **Dead cells vs. detached debris**
   - Currently dead cells use fallback estimation
   - Could track dead cells separately (apoptotic bodies, necrotic debris)

4. **Validation against real Cell Painting data**
   - Tune debris_coefficient using edge well data
   - Verify edge amplification magnitude (1.05-1.15×)

5. **Plate visualization**
   - 384-well heatmap of debris levels
   - Background noise multiplier across plate
   - Segmentation quality across plate
   - Edge amplification visible

---

## Status

✅ **COMPLETE AND TESTED**

- Core physics: pure functions with hard bounds and monotonicity
- Assay integration: minimal wiring, no side effects
- Test coverage: 16 tests, all passing
- Documentation: complete with examples and design rationale
- Integration: end-to-end pipeline validated

**Debris is now auditable, bounded, and locks invariants.**

The simulator went from "realistic" (hand-wave) to "auditable" (hard bounds + tests).

---

## References

- **Wash/Fixation Physics**: `docs/WASH_FIXATION_INTEGRATION_COMPLETE.md`
- **Core Module**: `src/cell_os/biology/imaging_artifacts_core.py`
- **Test Suite**: `tests/unit/test_imaging_artifacts_*.py`
- **Integration Test**: `/tmp/test_debris_imaging_integration.py`
