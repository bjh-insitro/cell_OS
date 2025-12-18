# Batch Balance: Ready for Founder Validation

## Status: Design Audit Complete

The batch balance invariant is now a **design audit that knows when it's allowed to speak**.

---

## What Changed

### 1. ✅ Factor Policies

**Problem**: Treating all batch factors as equally sacred (cell_line should be CONSTANT per plate, not uniformly distributed).

**Fix**: Added `FactorPolicy` type:

```typescript
export type FactorPolicy =
  | 'orthogonal'  // Must be independent of conditions (day, operator, timepoint)
  | 'separate'    // Must be constant within plate (cell_line)
  | 'ignore';     // No balance checks (plate_id)
```

**Phase0_v2 config**:
```typescript
batchFactors: [
  { name: 'day', extractor: (w) => w.day, policy: 'orthogonal' },
  { name: 'operator', extractor: (w) => w.operator, policy: 'orthogonal' },
  { name: 'timepoint', extractor: (w) => w.timepoint_h, policy: 'orthogonal' },
  { name: 'cell_line', extractor: (w) => w.cell_line, policy: 'separate' },
]
```

### 2. ✅ Separate Factor Checking

**New violation type**: `batch_separate_factor_violation`

**Check**: For factors with `policy: 'separate'`, ensure exactly ONE value per plate.

**Example violation**:
```
❌ ERROR: Batch factor 'cell_line' has policy 'separate' but varies within plate 'plate1':
found 2 distinct values [A549, HepG2]. Expected constant within plate.
```

**Why**: Phase 0 intentionally uses separate plates per cell line. This is correct by design, not confounding.

### 3. ✅ Policy-Aware Checking

- **Orthogonal factors**: Checked for independence (marginal balance, condition independence, chi-square)
- **Separate factors**: Checked for constancy within plate (not independence)
- **Ignore factors**: Not checked (e.g., plate_id)

### 4. ✅ All Sharp Edges Fixed

From previous iteration:
- Dose canonicalization (float trap)
- Sparse table detection (chi-square gating)
- Cramér's V effect size (no p-value theater)
- Per-plate checking (catches local confounding)
- Small count tolerance (max(1, 10% of expected))
- Marginal balance note (reminds not sufficient)
- Scope tagging (global vs plate-specific)

---

## Next Steps (In Order)

### 1. Run on Real Founder

**File**: `validateFounder.ts`

```typescript
import { validateFounderDesign } from './invariants/validateFounder';

const certificate = await validateFounderDesign();
```

**Expected outcomes**:
- **Clean pass**: Thresholds aligned with reality ✅
- **Warnings only**: Review and decide (founder defines acceptable)
- **Errors**: Allocation bug → fix generator

### 2. Interpret Output

See `FOUNDER_VALIDATION_OUTPUT_EXAMPLE.md` for 4 scenarios:
1. Clean pass (ideal)
2. Warnings only (explainable)
3. Errors (allocation bug)
4. Confounding detected (silent killer caught)

**Decision tree**:
- Errors = 0, Warnings = 0 → Perfect
- Errors = 0, Warnings > 0 → Review, possibly adjust thresholds
- Errors > 0 → **STOP, fix generator**

### 3. Add Founder-Derived Thresholds Mode

**Purpose**: Sanity check that thresholds match reality, not religion.

**Implementation** (TODO):
```typescript
export function deriveFounderThresholds(wells: Well[]): FounderThresholds {
  // Compute from actual founder design:
  // - Max per-plate deviation observed
  // - Max Cramér's V observed (global and per-plate)
  // - Percent sparse-table hits

  // Recommend:
  // - Warn if worse than founder + margin (e.g., 20%)
  // - Error if grossly worse than founder (e.g., 2×)
}
```

**Usage**:
```typescript
const founderThresholds = deriveFounderThresholds(founderWells);

// Compare new design to founder
if (newDeviation > founderThresholds.maxDeviation * 1.2) {
  warn('20% worse than founder');
}
```

### 4. Implement inv_sentinelBatchBalance

**File**: `SENTINEL_BATCH_BALANCE_SPEC.md` (already written)

**Why next**: Sentinels are drift thermometer. If sentinel types batch-skewed, you'll "detect drift" that is actually Tuesday.

**Checks**:
1. Sentinel marginal balance (±2 sentinels per type per level)
2. Sentinel type distribution (±20% from expected proportions)
3. No 100% sentinel type confounding

**Separate invariant** because:
- Different tolerance thresholds (looser)
- Different severity (WARNING not ERROR)
- Different purpose (SPC monitoring vs scientific inference)

### 5. Refactor Generator Around Invariants

**Current problem**: Proportional interspersion can introduce confounding.

**Architecture shift**:

```
┌─────────────────────────────────────────────────────────────┐
│ Phase A: Allocation (Constrained Construction)             │
│                                                             │
│ Build token list that is PROVABLY balanced across          │
│ day/operator/timepoint within each plate scope.            │
│                                                             │
│ Output: { tokens[], certificate }                          │
│ If certificate has errors, allocation failed.              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase B: Placement (Spatial Optimization)                  │
│                                                             │
│ Optimize sentinel dispersion and spatial aesthetics.       │
│ CANNOT introduce confounding (allocation baked it in).     │
│                                                             │
│ Output: { wells[], certificate }                           │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: Stop letting "proportional interspersion" decide which condition lands where if it can correlate with token ordering. Use it only AFTER allocation has baked in batch orthogonality.

---

## Files Ready

### Implementation
- ✅ `batchBalance.ts` (550 lines) - Factor policies, all sharp edges fixed
- ✅ `batchBalance.test.ts` (247 lines) - Basic test suite
- ✅ `batchBalance.adversarial.test.ts` (348 lines) - 7 adversarial scenarios
- ✅ `validateFounder.ts` (129 lines) - Runner for actual founder design

### Documentation
- ✅ `BATCH_BALANCE_IMPLEMENTATION.md` - Original implementation docs
- ✅ `BATCH_BALANCE_SHARP_EDGES_FIXED.md` - All 7 sharp edge fixes
- ✅ `FOUNDER_VALIDATION_OUTPUT_EXAMPLE.md` - 4 scenarios with examples
- ✅ `BATCH_BALANCE_READY_FOR_FOUNDER.md` - This file
- ✅ `SENTINEL_BATCH_BALANCE_SPEC.md` - Specification for next invariant

### Next Invariant Spec
- ✅ `SENTINEL_BATCH_BALANCE_SPEC.md` - Ready to implement

---

## Summary

**What we have**:
- Production-ready batch balance invariant
- Factor-aware policies (orthogonal vs separate vs ignore)
- All sharp edges sanded
- Comprehensive adversarial test suite
- Founder validation runner
- Example certificate outputs

**What to do**:
1. Run on actual phase0_v2 founder
2. Review output as calibration report
3. Adjust thresholds if needed (founder defines acceptable)
4. Implement sentinel batch balance
5. Refactor generator to respect invariants

**The uncomfortable question**: Answered.

`cell_line` now has `policy: 'separate'` and checks for constancy within plate (not independence). This is correct by design.

**Status**: Ready to stop polishing guardrails and work on actual design logic.

The invariant is a design audit that knows when it's allowed to speak.
