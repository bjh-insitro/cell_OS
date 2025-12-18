# Design Generator Test Cases

## Critical Invariants

These invariants MUST hold for the generator to be considered correct.

### 1. Available Wells Agreement

**Invariant**: `computeAvailableWellPositions().length === getAvailableWellCount()`

**Test**:
```typescript
const positions = computeAvailableWellPositions(plateFormat, exclusions);
const count = getAvailableWellCount(plateFormat, exclusions);
assert(positions.length === count, 'Position count must match calculated count');
```

**Why**: Prevents drift between "math" and "actual placement". If these disagree, the preview will lie.

---

### 2. Well Position Uniqueness

**Invariant**: No duplicate well positions within a single plate

**Test**:
```typescript
for (const [plateId, wells] of Object.entries(plateWellsMap)) {
  const positions = wells.map(w => w.well_pos);
  const unique = new Set(positions);
  assert(positions.length === unique.size, `Duplicate positions in ${plateId}`);
}
```

**Why**: Duplicate positions mean wells overwrite each other, data loss.

---

### 3. Sentinel Interspersion

**Invariant**: Sentinels should be distributed throughout the plate, not grouped

**Test**:
```typescript
const wells = plateWellsMap[plateId];
const sentinelIndices = wells
  .map((w, i) => w.is_sentinel ? i : -1)
  .filter(i => i >= 0);

// Check that sentinels aren't all clustered at the end
const maxGap = Math.max(...sentinelIndices.map((idx, i, arr) =>
  i > 0 ? idx - arr[i-1] : idx
));

// Max gap should not be > 2x average gap
const avgGap = wells.length / sentinelIndices.length;
assert(maxGap < avgGap * 2.5, 'Sentinels should be evenly distributed');
```

**Why**: Sentinels are for QC monitoring - they must be spatially distributed.

---

### 4. Plate Capacity Never Exceeded

**Invariant**: `wells.length <= availableWells` for every plate

**Test**:
```typescript
for (const [plateId, wells] of Object.entries(plateWellsMap)) {
  const availableWells = getAvailableWellCount(plateFormat, exclusions);
  assert(wells.length <= availableWells,
    `${plateId} has ${wells.length} wells but only ${availableWells} available`);
}
```

**Why**: If we silently truncate, user thinks design is complete but wells are missing.

---

### 5. Excluded Wells Never Used

**Invariant**: No well uses a position that should be excluded

**Test**:
```typescript
const availablePositions = new Set(computeAvailableWellPositions(plateFormat, exclusions));
for (const [plateId, wells] of Object.entries(plateWellsMap)) {
  for (const well of wells) {
    assert(availablePositions.has(well.well_pos),
      `${plateId} uses excluded position ${well.well_pos}`);
  }
}
```

**Why**: Excluded wells (corners, edges) are excluded for QC reasons. Using them invalidates the design.

---

### 6. IC50 Dose Calculation

**Invariant**: `dose_uM === dose_multiplier × compound_IC50`

**Test**:
```typescript
for (const well of wells) {
  if (well.is_sentinel) continue; // Sentinels have fixed doses

  const ic50 = COMPOUND_METADATA[well.compound].ic50_uM;
  const expectedDose = well.dose_multiplier * ic50;

  // Allow small floating point tolerance
  assert(Math.abs(well.dose_uM - expectedDose) < 0.01,
    `${well.compound} dose mismatch: expected ${expectedDose}, got ${well.dose_uM}`);
}
```

**Why**: Dose calculation is the core of dose-response experiments. Wrong doses = invalid science.

---

### 7. V2 Defaults Detection

**Invariant**: When form matches v2 params exactly, `matchesV2Defaults === true`

**Test**:
```typescript
// Set all form fields to v2 defaults
setSelectedCellLines(['A549', 'HepG2']);
setSelectedCompounds(ALL_10_COMPOUNDS);
setDoseMultipliers('0.1, 0.3, 1.0, 3.0, 10.0, 30.0');
// ... set all other v2 params

// Wait for debounce
await waitFor(400);

assert(matchesV2Defaults === true, 'Should match v2 defaults');
assert(phase0V2Design !== null, 'Should load v2 design');
```

**Why**: V2 match triggers loading the actual v2 file instead of generating. If detection breaks, users get wrong design.

---

## Edge Cases

### 1. Zero Compounds
- Input: `selectedCompounds = []`
- Expected: Empty preview, no crash

### 2. Zero Sentinels
- Input: All sentinel counts = 0
- Expected: Only experimental wells, no crash

### 3. Malformed Input
- Input: `doseMultipliers = "1,2,,"` (trailing comma)
- Expected: Parses as `[1, 2]`, no NaN

### 4. Single Everything
- Input: 1 compound, 1 dose, 1 rep, 1 day, 1 operator, 1 timepoint
- Expected: Minimal design, correct plate count

### 5. Massive Overflow
- Input: 10 compounds × 8 doses × 5 reps = 400 wells needed, 88 available
- Expected: `fits = false`, empty preview, warning shown

---

## Regression Tests

### Issue: Sentinels Grouped at End
**Date**: 2025-12-17
**Fix**: Replaced interval-based interspersion with proportional algorithm
**Test**: Run invariant #3 (Sentinel Interspersion)

### Issue: Edge Exclusion Math Wrong
**Date**: 2025-12-17
**Fix**: 96-well edges now correctly calculates 60 wells (was 48)
**Test**:
```typescript
const count = getAvailableWellCount(96, { excludeEdges: true, ... });
assert(count === 60, 'Edge exclusion for 96-well should leave 60 wells');
```

### Issue: Doesn't Fit Shows Truncated Preview
**Date**: 2025-12-17
**Fix**: Return empty preview when `!fits`
**Test**:
```typescript
// Set params that don't fit
setSelectedCompounds(ALL_10_COMPOUNDS);
// ... 148 wells needed, 88 available

await waitFor(400);
assert(wellStats.fits === false, 'Should not fit');
assert(Object.keys(previewWells).length === 0, 'Should show empty preview');
```

---

## Performance Tests

### 1. Memoization Works
**Test**: Change unrelated state (e.g., hover tooltip), verify `generatePreviewWells` doesn't rerun
**How**: Add console.log inside `generatePreviewWells`, check console

### 2. Debounce Works
**Test**: Type in dose multipliers field, verify calculation waits 300ms
**How**: Add timestamp logging in memos, check delays

---

## Manual Testing Checklist

- [ ] Load page, see v2 design by default
- [ ] Uncheck "Exclude Mid-Row Wells", see available wells change 88→92
- [ ] Remove 5 compounds, see sentinels interspersed (not grouped)
- [ ] Click "Auto-fix: Switch to 384-well", see fits=true
- [ ] Type in dose field, see preview update after 300ms delay (not instantly)
- [ ] Add trailing comma to operators field, see it parse correctly
- [ ] Switch to 384-well, see more plates rendered
- [ ] Check browser console for warnings (duplicate IDs, etc.)

---

## Future Tests (When Implemented)

### V2 Split Mode
```typescript
// When mode = 'v2_split' and 10 compounds selected
assert(maxCompoundsPerPlate === 5, 'V2 split should use max 5 compounds per plate');
assert(nPlates === expectedPlates * 2, 'V2 split should double plate count');
```
