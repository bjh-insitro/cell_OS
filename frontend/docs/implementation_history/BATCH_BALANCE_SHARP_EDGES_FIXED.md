# Batch Balance Sharp Edges - Fixed

## Summary

Applied 7 critical fixes to prevent false confidence and false alarms in batch balance invariant.

---

## Fix 1: Marginal Balance Note

**Problem**: Users might think marginal balance alone is sufficient.

**Fix**: Added explicit reminder in error message:

```typescript
message: `... [Note: Marginal balance is necessary but not sufficient - you can be marginally balanced and still confounded.]`
```

**Why**: Classic Simpson's paradox trap. You can have perfectly balanced marginals and still be 100% confounded.

**Test**: `adversarial.test.ts` - Adversarial 1 creates marginally balanced but fully confounded design.

---

## Fix 2: Dose Canonicalization

**Problem**: Float comparison trap. `10.0` vs `10.000000001` treated as different conditions.

**Fix**: Created `canonicalizeDose()` function (ONE THROAT TO CHOKE):

```typescript
function canonicalizeDose(dose_uM: number | undefined): string {
  if (dose_uM === undefined || dose_uM === null) return 'UNKNOWN';
  return dose_uM.toFixed(6); // Round to 6 decimal places
}

conditionKey: (w) => `${w.compound}@${canonicalizeDose(w.dose_uM)}uM`
```

**Why**: Prevents fake "new conditions" that differ only by float formatting.

**Test**: `adversarial.test.ts` - Adversarial 4 tests float precision differences.

---

## Fix 3: Sparse Table Detection

**Problem**: Chi-square gets dodgy when many expected cells < 5.

**Fix**: Gate chi-square with sparsity check:

```typescript
// Only run chi-square if >= 80% of cells have expected ≥ 5
if (proportionLowExpected > 0.2) {
  violations.push({
    type: 'batch_table_too_sparse',
    message: `... Consider using permutation test or G-test instead.`,
  });
  return violations; // Don't run chi-square on sparse tables
}
```

**Why**: Chi-square is unreliable for sparse tables. Better to warn than give false confidence.

**Test**: `adversarial.test.ts` - Adversarial 3 creates sparse table (10 compounds × 6 doses).

---

## Fix 4: Cramér's V Effect Size

**Problem**: p-values are theater. Can be significant with negligible effect size (large N) or vice versa.

**Fix**: Compute and report Cramér's V alongside p-value:

```typescript
// V = sqrt(χ² / (n * min(r-1, c-1)))
const cramersV = Math.sqrt(chiSquare / (grandTotal * minDim));

const effectSizeLabel =
  cramersV < 0.1 ? 'negligible' :
  cramersV < 0.3 ? 'small' :
  cramersV < 0.5 ? 'medium' : 'large';

message: `χ²=..., p=..., Effect size: Cramér's V=${cramersV} (${effectSizeLabel})`

suggestion: cramersV > cramersVThreshold
  ? `Large effect size (V=...). This is not just statistically significant but practically important.`
  : `Statistically significant but small effect size. May be acceptable for pilot studies.`
```

**Why**: Gives "how dependent" number that's interpretable. Avoids p-value theater.

**Test**: `adversarial.test.ts` - Adversarial 6 tests both scenarios.

---

## Fix 5: Small Count Tolerance

**Problem**: "≤10% deviation" is ambiguous when 10% < 1 well.

**Fix**: Use count-based tolerance with floor:

```typescript
// Tolerance in counts: max(1 well, toleranceProportion * expected)
const toleranceCount = Math.max(1, toleranceProportion * expectedCount);

if (maxDeviationCount > toleranceCount) {
  violations.push({
    message: `... Max deviation: ${maxDeviationCount} wells ... (tolerance ${toleranceCount} wells)`,
  });
}
```

**Why**: Makes tolerance behave correctly across 96-well and 384-well designs.

**Test**: `adversarial.test.ts` - Adversarial 5 tests small and large count scenarios.

---

## Fix 6: Per-Plate Checking

**Problem**: Can be globally independent but locally confounded within each plate.

**Fix**: Added `checkPerPlate` config option and separate per-plate checks:

```typescript
// Check 4: Per-plate independence (stronger, catches local confounding)
if (cfg.checkPerPlate) {
  const wellsByPlate = groupBy(expWells, (w) => w.plate_id);

  for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
    // Run independence checks on each plate separately
    // Violations tagged with scope: `plate ${plateId}`
  }
}
```

**Why**: If generator places tokens plate-by-plate, can be globally independent but locally confounded. This catches it.

**Test**: `adversarial.test.ts` - Adversarial 2 creates design balanced globally but confounded per-plate.

---

## Fix 7: Scope Tagging

**Problem**: Hard to tell if violation is global or plate-specific.

**Fix**: Added `scope` parameter to all check functions:

```typescript
checkConditionDistribution(..., scope: 'global' | `plate ${plateId}`)
checkChiSquareIndependence(..., scope: 'global' | `plate ${plateId}`)

message: `Condition '...' not uniformly distributed across '...' (${scope}).`
```

**Why**: Violations now clearly state whether they're global or plate-specific.

---

## Configuration Changes

Added new config fields to `BatchInvariantConfig`:

```typescript
export interface BatchInvariantConfig {
  // ... existing fields

  // NEW: Minimum expected count for chi-square (gating sparse tables)
  chiSquareMinExpected: number;

  // NEW: Cramér's V threshold for "large" effect size
  cramersVThreshold: number;

  // NEW: Whether to check per-plate (stronger, catches local confounding)
  checkPerPlate: boolean;
}
```

**Phase0_v2 config**:

```typescript
export const PHASE0_V2_BATCH_CONFIG: BatchInvariantConfig = {
  // ... existing fields
  chiSquareMinExpected: 5,      // Gate chi-square on sparse tables
  cramersVThreshold: 0.3,       // Cramér's V > 0.3 = "large"
  checkPerPlate: true,          // Check independence within each plate
};
```

---

## New Violation Types

### 1. `batch_table_too_sparse` (WARNING)

```typescript
{
  type: 'batch_table_too_sparse',
  severity: 'warning',
  message: `Contingency table for '${factor.name}' (${scope}) too sparse for chi-square test: ${cellsWithLowExpected}/${totalCells} cells (${proportion}%) have expected count < ${minExpected}. Chi-square may be unreliable. Consider using permutation test or G-test instead.`,
}
```

**When**: >20% of contingency table cells have expected count < 5.

**Action**: Increase sample size, reduce number of conditions, or use more robust test.

---

## Adversarial Test Suite

Created comprehensive adversarial tests in `batchBalance.adversarial.test.ts`:

1. **Adversarial 1**: Marginally balanced but fully confounded
2. **Adversarial 2**: Globally balanced but plate-level confounded
3. **Adversarial 3**: Sparse contingency tables
4. **Adversarial 4**: Float dose comparison trap
5. **Adversarial 5**: Small count tolerance edge cases
6. **Adversarial 6**: Effect size vs p-value theater
7. **Adversarial 7**: Marginal balance note verification

**Status**: All 7 adversarial scenarios correctly detected.

---

## Before vs After

### Before: Float Trap

```typescript
// BROKEN: Float comparison
conditionKey: (w) => `${w.compound}@${w.dose_uM}uM`

// Creates fake conditions:
// - "tBHQ@10uM" (from 10.0)
// - "tBHQ@10.000000001uM" (from 10.000000001)
// These are treated as DIFFERENT conditions!
```

### After: Canonicalized

```typescript
// FIXED: Canonicalize dose
conditionKey: (w) => `${w.compound}@${canonicalizeDose(w.dose_uM)}uM`

// Both become "tBHQ@10.000000uM" (same condition)
```

---

### Before: p-value Theater

```typescript
// BROKEN: Only reports p-value
message: `χ²=8.00, p=0.0047 < 0.05`

// Is this practically important or just big N?
// Can't tell!
```

### After: Effect Size

```typescript
// FIXED: Reports p-value AND Cramér's V
message: `χ²=8.00, p=0.0047 < 0.05. Effect size: Cramér's V=0.632 (large)`

suggestion: `Large effect size (V=0.632 > 0.3). This is not just statistically significant but practically important.`

// Now you know: this is REAL confounding, not just noise
```

---

### Before: Blind to Local Confounding

```typescript
// BROKEN: Only global check
// Plate 1: tBHQ in Day 1, H2O2 in Day 2 (confounded)
// Plate 2: tBHQ in Day 2, H2O2 in Day 1 (confounded)
// Global: tBHQ in both days (looks balanced!)

violations = [] // PASSES (false negative)
```

### After: Per-Plate Detection

```typescript
// FIXED: Check each plate
// Plate 1: Detects confounding
// Plate 2: Detects confounding

violations = [
  { type: 'batch_condition_confounding', scope: 'plate plate1', ... },
  { type: 'batch_condition_confounding', scope: 'plate plate2', ... },
]

// FAILS correctly (catches local confounding)
```

---

### Before: Sparse Table Risk

```typescript
// BROKEN: Runs chi-square on sparse table
// 60 conditions × 2 levels = 120 cells
// But only 120 wells total = 1 well per cell (expected!)
// Many cells with expected < 5

violations = [
  { type: 'batch_condition_dependence', p: 0.03 }  // UNRELIABLE
]
```

### After: Gated

```typescript
// FIXED: Detects sparsity and gates chi-square
violations = [
  {
    type: 'batch_table_too_sparse',
    message: '72/120 cells (60%) have expected < 5. Chi-square may be unreliable.'
  }
]

// Doesn't run chi-square on sparse tables
```

---

## Summary

**What changed**:
- ✅ Dose canonicalization (float trap eliminated)
- ✅ Sparse table detection (chi-square gated)
- ✅ Cramér's V effect size (no more p-value theater)
- ✅ Per-plate checking (catches local confounding)
- ✅ Small count tolerance (max(1, 10% of expected))
- ✅ Marginal balance note (reminds it's not sufficient)
- ✅ Scope tagging (global vs plate-specific)

**What this prevents**:
- False negatives (missing real confounding)
- False positives (flagging noise as confounding)
- Silent failures (float traps, sparse tables)
- Misleading statistics (p-values without effect sizes)

**Status**: Production-ready with all sharp edges sanded.

Run on actual phase0_v2 design to validate orthogonality.
