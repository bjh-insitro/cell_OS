# Batch Balance Implementation - Summary

## What Was Built

Implemented `inv_batchBalance` - the invariant that prevents accidentally building confounding into the Phase 0 founder dataset.

**The one that actually matters.**

## Files Created

### 1. `/invariants/batchBalance.ts` (317 lines)

Complete implementation of batch balance invariant with three levels of checks:

**Check 1: Marginal Balance (ERROR)**
- Ensures each batch factor level has equal well counts (±1 tolerance)
- Checks: day, operator, timepoint, cell_line
- Violation type: `batch_marginal_imbalance`

**Check 2: Condition Independence (WARNING)**
- Ensures each condition uniformly distributed across batch levels
- Tolerance: ≤10% deviation from uniform
- Violation type: `batch_condition_confounding`

**Check 3: Chi-Square Test (WARNING)**
- Statistical test for independence between conditions and batch factors
- Uses contingency table analysis
- Violation type: `batch_condition_dependence`

**Key implementation details**:
- Filters to experimental wells only (sentinels excluded)
- Condition definition: `${compound}@${dose_uM}uM` (ignore replicates)
- All batch factors checked independently
- Includes approximate chi-square p-value calculation

### 2. `/invariants/__tests__/batchBalance.test.ts` (247 lines)

Comprehensive test suite covering:
- Marginal balance: pass/fail scenarios, all factors
- Condition independence: uniform/confounded/partial skew
- Chi-square test: independent/dependent scenarios
- Edge cases: sentinels excluded, zero wells, undefined values, multi-plate

**Test count**: 12 test cases

### 3. `/invariants/index.ts` (updated)

Integrated batch balance into main invariant runner:
```typescript
export function checkPhase0V2Design(wells: Well[]): DesignCertificate {
  violations.push(...inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG));
  violations.push(...inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG));  // NEW
  // ... other invariants
}
```

### 4. Documentation

**Created**:
- `BATCH_BALANCE_IMPLEMENTATION.md` - Complete documentation of implementation
- `BATCH_BALANCE_SUMMARY.md` - This file

**Updated**:
- `INVARIANT_SYSTEM.md` - Added full batch balance section, updated summary

## Configuration

```typescript
export const PHASE0_V2_BATCH_CONFIG: BatchInvariantConfig = {
  batchFactors: [
    { name: 'day', extractor: (w) => w.day },
    { name: 'operator', extractor: (w) => w.operator },
    { name: 'timepoint', extractor: (w) => w.timepoint_h },
    { name: 'cell_line', extractor: (w) => w.cell_line },
  ],
  conditionKey: (w) => `${w.compound}@${w.dose_uM}uM`,
  marginalBalanceTolerance: 1,           // ±1 well
  conditionDistributionTolerance: 0.1,   // ≤10% deviation
  runChiSquareTest: true,
  chiSquareAlpha: 0.05,
};
```

## Why This Matters

### The Problem

If conditions correlate with batch factors, you cannot separate:
1. Biological effects (what you want to measure)
2. Batch effects (systematic variation from day/operator/timepoint)

**Example of confounding**:
```
Day 1: All tBHQ doses
Day 2: All MG132 doses

Result: Cannot tell if differences are:
- Compound pharmacology (biology)
- Day-to-day variation (confounding)
```

This design is **scientifically worthless**.

### Why It's Silent

Unlike other bugs:
- Doesn't crash the generator
- Doesn't look wrong in the UI
- Passes all count checks
- Only discovered during analysis (too late to fix)

**This invariant catches it during design**, not 6 months later.

## What Gets Checked

### Marginal Balance

**Good**:
```
Day 1: 60 experimental wells
Day 2: 60 experimental wells
✓ Balanced within ±1 tolerance
```

**Bad**:
```
Day 1: 80 experimental wells
Day 2: 40 experimental wells
✗ ERROR: Deviation of 20 exceeds tolerance
```

### Condition Independence

**Good**:
```
tBHQ@10uM across days:
Day 1: 2 replicates (50%)
Day 2: 2 replicates (50%)
✓ Uniform distribution
```

**Bad**:
```
tBHQ@10uM across days:
Day 1: 4 replicates (100%)
Day 2: 0 replicates (0%)
✗ WARNING: 100% confounded with day
```

### Chi-Square Test

**Good**:
```
           Day1  Day2
tBHQ@10uM    2     2
H2O2@5uM     2     2

χ² = 0.0, p = 1.0
✓ Independent
```

**Bad**:
```
           Day1  Day2
tBHQ@10uM    4     0
H2O2@5uM     0     4

χ² = 8.0, p = 0.0047
✗ WARNING: Significant dependence (p < 0.05)
```

## Violation Examples

### 1. Marginal Imbalance (ERROR)

```typescript
{
  type: 'batch_marginal_imbalance',
  severity: 'error',
  message: "Batch factor 'day' level '1': 80 wells (expected 60.0, deviation 20.0 > tolerance 1).",
  suggestion: "Allocation must balance wells across batch levels. Check compound/dose assignment logic.",
  details: {
    factor: 'day',
    level: '1',
    actual: 80,
    expected: '60.0',
    deviation: '20.0',
    tolerance: 1,
  },
}
```

### 2. Condition Confounding (WARNING)

```typescript
{
  type: 'batch_condition_confounding',
  severity: 'warning',
  message: "Condition 'tBHQ@10uM' not uniformly distributed across 'day'. Max deviation: 50.0% at level '1' (tolerance 10%).",
  suggestion: "Shuffle compound assignment to break correlation with batch factors.",
  details: {
    condition: 'tBHQ@10uM',
    factor: 'day',
    maxDeviation: '0.500',
    worstLevel: '1',
    distribution: { '1': '1.000', '2': '0.000' },
    tolerance: 0.1,
  },
}
```

### 3. Chi-Square Dependence (WARNING)

```typescript
{
  type: 'batch_condition_dependence',
  severity: 'warning',
  message: "Conditions not independent of batch factor 'day' (χ²=8.00, df=1, p=0.0047 < α=0.05).",
  suggestion: "Significant dependence detected. Review compound assignment algorithm to ensure orthogonality with batch structure.",
  details: {
    factor: 'day',
    chiSquare: '8.00',
    dof: 1,
    pValue: '0.0047',
    alpha: 0.05,
  },
}
```

## Risk Analysis: Current Generator

### Proportional Interspersion Algorithm

From `DesignCatalogTab.tsx`:

```typescript
// Experimental wells ordered: Compound1 → Compound2 → ... → Compound5
// Proportional interspersion result:
// Positions 0-20:  Mostly Compound1
// Positions 20-40: Compound2-3
// Positions 40-60: Compound4-5
```

**Risk**: If compound assignment varies by batch, creates spatial-batch correlation.

**Critical question**: Are the same 5 compounds always together across all 24 plates?
- ✓ If YES: No batch confounding (deterministic split)
- ✗ If NO: Severe batch confounding

**This invariant will catch it.**

## Test Coverage

Comprehensive test suite with 12 test cases:

1. **Marginal balance**:
   - ✓ Pass when perfectly balanced
   - ✓ Error when imbalanced
   - ✓ Check all factors independently

2. **Condition independence**:
   - ✓ Pass when uniform
   - ✓ Warn when confounded
   - ✓ Detect partial confounding (skewed)
   - ✓ Check all factors for each condition

3. **Chi-square test**:
   - ✓ Pass when independent
   - ✓ Warn when significant dependence

4. **Edge cases**:
   - ✓ Skip sentinels (only check experimental wells)
   - ✓ Handle zero experimental wells
   - ✓ Handle undefined batch factor values
   - ✓ Multi-plate scenarios

## Integration

Added to main invariant system:

```typescript
// In checkPhase0V2Design():
violations.push(...inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG));
violations.push(...inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG));  // NEW
```

Now part of design certificate generation.

## Next Steps

1. **Run on actual phase0_v2 design**:
   ```typescript
   const wells = await fetchDesign('phase0_founder_v2_controls_stratified');
   const certificate = checkPhase0V2Design(wells);
   ```

2. **Check for violations**:
   - Founder design should pass cleanly
   - If violations found, investigate compound split assignment

3. **Fix generator if needed**:
   - Ensure compound assignment independent of batch factors
   - Consider batch-aware shuffling

4. **Re-run until clean**:
   - Zero ERROR violations required
   - Zero WARNING violations preferred for founder

## Status

**Implementation**: ✅ Complete

**Tests**: ✅ Comprehensive (12 test cases)

**Documentation**: ✅ Complete

**Integration**: ✅ Integrated into main invariant system

**Ready for**: Validation against actual phase0_v2 design

## Summary

Built the critical invariant that prevents confounding in Phase 0 founder dataset:

- **Three levels of defense**: Marginal balance (ERROR), condition independence (WARNING), chi-square test (WARNING)
- **All batch factors checked**: day, operator, timepoint, cell_line
- **Sentinels excluded**: Only checks experimental wells
- **Comprehensive tests**: 12 test cases covering all scenarios
- **Production-ready**: Integrated into design certificate generation

The silent killer has been caught.

Now run it on the actual design to validate that the Phase 0 founder is orthogonal.
