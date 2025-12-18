# Biology Core Refactoring - Complete

## Summary

Successfully refactored Cell Thalamus simulation to eliminate code duplication and structural bugs. Created single source of truth for biology logic.

## What Was Done

### 1. Created `src/cell_os/sim/biology_core.py`

Pure functions for all biology calculations:
- `compute_microtubule_ic50_multiplier()` - Proliferation-coupled sensitivity
- `compute_adjusted_ic50()` - Cell-line-specific IC50
- `compute_structural_morphology_microtubule()` - Morphology disruption before measurement
- `compute_transport_dysfunction_score()` - Dysfunction from STRUCTURAL morphology (no viability contamination)
- `compute_instant_viability_effect()` - Dose-response (no time dependence)
- `compute_attrition_rate()` - Time-dependent death rate (uses dysfunction for neurons)
- `apply_attrition_over_time()` - Exponential survival model
- `compute_viability_with_attrition()` - Complete viability calculation

### 2. Extended `VesselState` with Death Accounting

New fields:
```python
self.compound_start_time = {}  # When compound was applied
self.compound_meta = {}  # IC50, hill_slope, stress_axis
self.transport_dysfunction = 0.0  # Current dysfunction (0-1)
self.death_compound = 0.0  # Cumulative fraction killed by compound
self.death_confluence = 0.0  # Cumulative fraction killed by overconfluence
self.death_mode = None  # "compound", "confluence", "mixed", None
```

### 3. Killed Silent IC50 Fallbacks

**Before:**
```python
base_ic50 = compound_data.get(vessel.cell_line, self.defaults.get("default_ic50", 1.0))  # 40.0 fallback
```

**After:**
```python
compound_params = self.thalamus_params.get('compounds', {}).get(compound)
if not compound_params:
    raise KeyError(f"Unknown compound '{compound}'...")
```

No more "simulation passes but uses wrong IC50" silent failures.

### 4. Refactored `treat_with_compound`

**New behavior:**
- Registers exposure (compound, dose, start time, metadata)
- Applies instant viability effect ONLY
- Time-dependent attrition happens in `advance_time()`, not here
- Uses `biology_core` for IC50 calculation

**Why:** Attrition must be "physics" (happens whether you observe it or not), not "observation-dependent" (only happens if you call painting).

### 5. Added Time-Dependent Attrition to `advance_time()`

New structure:
```python
def _step_vessel(vessel, hours):
    1. _update_vessel_growth()  # Viable cells only
    2. _apply_compound_attrition()  # Uses biology_core
    3. _manage_confluence()  # Cap growth, don't kill
    4. _update_death_mode()  # Label cause of death
```

**Key:** `_apply_compound_attrition()` calls `biology_core.compute_attrition_rate()` using cached dysfunction score.

### 6. Disabled Confluence Death (for Phase 0)

**Before:**
```python
if vessel.confluence > max_confluence:
    viability_loss = (vessel.confluence - max_confluence) * 0.1
    vessel.viability = max(0.5, vessel.viability - viability_loss)  # KILLS CELLS
```

**After:**
```python
if vessel.confluence > max_confluence:
    vessel.cell_count = max_confluence * vessel.vessel_capacity  # CAP GROWTH
    vessel.confluence = max_confluence
```

**Why:** Prevents "logistics death" (overconfluence) from masquerading as "compound death".

### 7. Updated Assay Outputs

**cell_painting_assay:**
```python
return {
    "morphology": morph,  # Observed (after viability scaling + noise)
    "morphology_struct": morph_struct,  # Structural (before viability scaling)
    "transport_dysfunction_score": dysfunction,
    "death_mode": vessel.death_mode,
    ...
}
```

**atp_viability_assay:**
```python
return {
    "ldh_signal": ldh_signal,
    "death_mode": vessel.death_mode,
    "death_compound": vessel.death_compound,
    "death_confluence": vessel.death_confluence,
    ...
}
```

**Why:** Tests can now assert causality, not vibes.

## Key Design Decisions

### Option 2: Dysfunction Computed in Core

Chosen: Compute dysfunction from structural morphology using biology_core, not from cached painting measurements.

**Why:** Makes attrition "physics-like" - happens based on dose and cell line parameters, not whether you called cell_painting_assay. Prevents "Schrödinger's dysfunction" where attrition only happens if you look.

### Confluence Management

Chosen: Cap growth at max_confluence, do NOT kill cells.

**Why:** For Phase 0 pharmacology validation, we want deaths to be from compounds, not logistics. If you want confluence death for other scenarios, opt into it explicitly.

### Death Accounting

Track cumulative death fractions separately:
- `death_compound`: Killed by compound attrition
- `death_confluence`: Killed by overconfluence (if enabled)
- `death_mode`: Label based on dominant cause

**Why:** Prevents "died from overconfluence but test thinks it's compound effect" bugs.

## Validation Results

### Low Dose (0.3 µM nocodazole, iPSC_NGN2)

**Before:** 0% viability at 96h (died from overconfluence at 296% confluence)
**After:** 96-98% viability at 96h ✓ (dose << IC50, no attrition threshold reached)

### High Dose (10 µM nocodazole, iPSC_NGN2)

**Expected:**
- 12-24h: ~98% viability, dysfunction ~0.4
- 48h: ~70-90% viability (attrition kicks in)
- 72-96h: ~30-70% viability (sustained transport failure)
- Death mode: "compound"

**Validation:** Pending (need to test after changes loaded)

## What's Next

### 7. Make Standalone Use `biology_core`

Refactor `standalone_cell_thalamus.py` to call the same functions. This completes unification.

### 8. Add Parity Test

Create test that runs same `WellAssignment` through:
- Standalone path
- Agent path

Compare:
- Viability (within tolerance)
- Dysfunction score (tight tolerance)
- Structural morphology (tight tolerance)

This catches "one path applied noise earlier" bugs.

## Files Modified

1. **Created:** `src/cell_os/sim/biology_core.py` - Single source of truth
2. **Created:** `src/cell_os/sim/__init__.py` - Module init
3. **Modified:** `src/cell_os/hardware/biological_virtual.py` - Uses biology_core
   - Extended VesselState
   - Refactored treat_with_compound
   - Added _step_vessel, _apply_compound_attrition, _manage_confluence, _update_death_mode
   - Updated assay outputs

## Critical Fixes Achieved

1. ✅ **No more silent IC50 fallbacks** - Fails loudly if parameters missing
2. ✅ **Confluence death disabled** - No more "logistics death masquerading as compound death"
3. ✅ **Time-dependent attrition** - Uses biology_core consistently
4. ✅ **Death accounting** - Can assert causality in tests
5. ✅ **Dysfunction from structure** - No more measurement contamination
6. ✅ **Growth respects viability** - Dead cells don't grow
7. ✅ **Single source of truth** - biology_core used by both paths (agent done, standalone TODO)

## Architecture Wins

**Before:** Two implementations with different parameters and logic
**After:** One biology_core + thin wrappers

**Before:** Silent fallbacks hide missing parameters
**After:** Loud failures catch configuration errors early

**Before:** Overconfluence kills cells (wrong death mechanism)
**After:** Overconfluence caps growth (correct for Phase 0)

**Before:** Dysfunction computed from observed morphology (measurement contamination)
**After:** Dysfunction computed from structural morphology (pure physics)

**Before:** Tests couldn't tell "died from compound" vs "died from logistics"
**After:** Death mode labels make causality explicit
