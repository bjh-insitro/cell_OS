# Seeding Density Fix - December 22, 2025

## Problem

The 384-well plate simulations were using **absurdly high** seeding densities:

- **A549**: 1,000,000 cells/well (NOMINAL)
- **HepG2**: 1,000,000 cells/well (NOMINAL)

These values are **200-333x too high** for 384-well plates and would result in:
1. Massive overconfluence immediately upon seeding
2. Cells stacked on top of each other (physically impossible monolayer)
3. Rapid cell death from contact inhibition and nutrient depletion

## Physical Reality

384-well plate specifications:
- **Surface area**: ~0.112 cm²
- **Well volume**: ~80-100 µL
- **At confluence**: ~15,000 cells/well (130-140 cells/cm²)

The old seeding density of 1M cells/well would require **67 layers** of cells stacked on top of each other!

## Solution

Created a proper configuration system for seeding densities:

### New Configuration File
`src/cell_os/config/seeding_densities.py`

Provides:
- Format-aware seeding densities (384-well, 96-well, 6-well)
- Cell-line-specific densities (based on growth rates)
- Density level support (LOW, NOMINAL, HIGH)
- Expected confluence calculations

### New Seeding Densities (384-well)

#### A549 (fast-growing lung cancer)
- **LOW**: 2,100 cells/well → 63.5% confluence at 48h
- **NOMINAL**: 3,000 cells/well → 90.7% confluence at 48h
- **HIGH**: 3,900 cells/well → 100% confluence at 48h

#### HepG2 (slower hepatoma)
- **LOW**: 3,500 cells/well → 62.1% confluence at 48h
- **NOMINAL**: 5,000 cells/well → 88.7% confluence at 48h
- **HIGH**: 6,500 cells/well → 100% confluence at 48h

### Rationale

1. **A549 seeded lower** (3,000) because it grows faster (~22h doubling time)
2. **HepG2 seeded higher** (5,000) because it grows slower (~34h doubling time)
3. Both reach similar confluence (~90%) at 48h measurement timepoint
4. LOW/NOMINAL levels allow adequate growth headroom (60-90% confluence)
5. HIGH level is intentionally stressful (~100% confluence) for calibration

## Changes Made

### 1. Created Configuration Module
**File**: `src/cell_os/config/seeding_densities.py`
- `NOMINAL_SEEDING_DENSITY`: Dictionary mapping format → cell_line → cells
- `get_seeding_density()`: Function to retrieve density with scale multipliers
- `get_expected_confluence()`: Estimate confluence at timepoint

### 2. Updated Plate Executor
**File**: `src/cell_os/plate_executor.py`

**Before**:
```python
initial_cells = int(1e6 * density_scale)  # WRONG!
```

**After**:
```python
initial_cells = get_seeding_density(
    plate_format=str(plate_format),
    cell_line=pw.cell_line,
    density_level=pw.cell_density
)
```

### 3. Created Verification Script
**File**: `scripts/verify_seeding_densities.py`
- Checks all density levels are in realistic range
- Calculates expected confluence at 48h
- Compares old vs new values
- Validates against physical constraints

## Verification Results

✓ All seeding densities in realistic range (2,000-10,000 cells/well)
✓ Expected confluence at 48h is appropriate (60-90% for LOW/NOMINAL)
✓ HIGH density correctly shows overconfluence warning
✓ Adequate growth headroom (67-80% spare capacity)
✓ Values match industry standard screening densities

## Impact

### Before Fix
- Wells massively overconfluent from t=0
- Cell death from contact inhibition
- Nutrient depletion within hours
- Unrealistic morphology signals
- Confluence >1000% (physically impossible)

### After Fix
- Realistic starting density (20-33% of capacity)
- Adequate growth headroom
- Appropriate confluence at readout (60-90%)
- Realistic morphology and viability dynamics
- Matches real-world screening conditions

## Testing

Run verification script:
```bash
python scripts/verify_seeding_densities.py
```

Expected output shows:
- ✓ A549: 3,000 cells/well (NOMINAL) → 90.7% confluence at 48h
- ✓ HepG2: 5,000 cells/well (NOMINAL) → 88.7% confluence at 48h
- ✓ 200-333x reduction from old values

## Related Files

- `src/cell_os/config/seeding_densities.py` - Configuration module
- `src/cell_os/plate_executor.py` - Updated executor
- `scripts/verify_seeding_densities.py` - Verification script
- `docs/SEEDING_DENSITY_FIX.md` - This document

## Notes

- The old value (1e6) likely came from T-flask protocols where 1M cells is typical for a T75 flask (~75 cm²)
- A 384-well has only ~0.112 cm², which is **670x smaller** than a T75
- The fix makes the simulation match real-world high-content screening protocols
