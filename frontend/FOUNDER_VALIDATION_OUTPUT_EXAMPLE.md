# Founder Validation Output - Example

## What the Certificate Looks Like

This shows what `checkPhase0V2Design()` returns when run on the actual phase0_v2 founder design.

---

## Scenario 1: Clean Pass (Ideal)

```
═══════════════════════════════════════════════════════════════
  PHASE 0 FOUNDER CALIBRATION REPORT
═══════════════════════════════════════════════════════════════

## Design Stats
  Total wells: 2112
  Sentinel wells: 672 (31.8%)
  Experimental wells: 1440 (68.2%)
  Plates: 24
  Plate format: 96-well

## Invariants Version: 1.0.0
## Timestamp: 2025-01-15T10:30:00Z
## Params Hash: a3f9b2c

## Violations Summary
  Errors: 0
  Warnings: 0

✅ CLEAN PASS - Founder design satisfies all invariants

Interpretation:
  • Thresholds are aligned with reality
  • Founder is the zero point for comparison
  • Future designs should match or exceed this quality

═══════════════════════════════════════════════════════════════
```

**Action**: None. Founder is the baseline. Move forward with confidence.

---

## Scenario 2: Warnings Only (Explainable)

```
═══════════════════════════════════════════════════════════════
  PHASE 0 FOUNDER CALIBRATION REPORT
═══════════════════════════════════════════════════════════════

## Design Stats
  Total wells: 2112
  Sentinel wells: 672 (31.8%)
  Experimental wells: 1440 (68.2%)
  Plates: 24

## Violations Summary
  Errors: 0
  Warnings: 3

⚠️  WARNINGS DETECTED - Review and decide

Interpretation:
  • Either founder is imperfect (possible), OR
  • Invariant encodes policy founder never satisfied (also possible)

## Warnings:

⚠️  WARNING: batch_condition_confounding
  Message: Condition 'tBHQ@1.000000uM' not uniformly distributed across 'timepoint' (global). Max deviation: 1.2 wells (15.0%) at level '48.0' (tolerance 1.0 wells).
  Suggestion: Shuffle compound assignment to break correlation with batch factors.
  Details: {
    "condition": "tBHQ@1.000000uM",
    "factor": "timepoint",
    "scope": "global",
    "maxDeviationCount": "1.2",
    "maxDeviationProportion": "0.150",
    "worstLevel": "48.0",
    "toleranceCount": "1.0"
  }

⚠️  WARNING: batch_table_too_sparse
  Message: Contingency table for 'operator' (global) too sparse for chi-square test: 45/120 cells (37.5%) have expected count < 5. Chi-square may be unreliable. Consider using permutation test or G-test instead.
  Suggestion: Increase sample size, reduce number of conditions, or use a more robust test.

⚠️  WARNING: sentinel_gap_high_variance
  Message: Plate 'A549_Day1_Operator_A_T12.0h': sentinel gap CV is 0.93 (high dispersion).
  Suggestion: Improve placement: reduce uneven spacing between sentinels.

═══════════════════════════════════════════════════════════════
```

**Decision tree**:
1. **batch_condition_confounding**: 15% deviation is slightly above 10% tolerance. Either:
   - Relax tolerance to 15% (founder defines acceptable), OR
   - Accept that founder has minor imperfection (document it)

2. **batch_table_too_sparse**: 30 conditions × 4 batch levels creates sparse table. This is expected for v2 design. Chi-square gated correctly. No action needed.

3. **sentinel_gap_high_variance**: CV 0.93 is just above 0.9 threshold. Either:
   - Relax CV threshold to 1.0, OR
   - Note that founder has slightly uneven sentinel spacing (acceptable for pilot)

**Action**: Document deviations, adjust thresholds if needed, move forward.

---

## Scenario 3: Errors (Allocation Bug)

```
═══════════════════════════════════════════════════════════════
  PHASE 0 FOUNDER CALIBRATION REPORT
═══════════════════════════════════════════════════════════════

## Design Stats
  Total wells: 2112
  Sentinel wells: 672 (31.8%)
  Experimental wells: 1440 (68.2%)
  Plates: 24

## Violations Summary
  Errors: 2
  Warnings: 1

❌ ERRORS DETECTED - Likely allocation or labeling bug

## Errors:

❌ ERROR: batch_marginal_imbalance
  Message: Batch factor 'day' level '1': 800 wells (expected 720.0, deviation 80.0 > tolerance 1). [Note: Marginal balance is necessary but not sufficient - you can be marginally balanced and still confounded.]
  Suggestion: Allocation must balance wells across batch levels. Check compound/dose assignment logic.
  Details: {
    "factor": "day",
    "level": "1",
    "actual": 800,
    "expected": "720.0",
    "deviation": "80.0",
    "tolerance": 1
  }

❌ ERROR: batch_separate_factor_violation
  Message: Batch factor 'cell_line' has policy 'separate' but varies within plate 'A549_Day1_Operator_A_T12.0h': found 2 distinct values [A549, HepG2]. Expected constant within plate (e.g., one cell line per plate).
  Suggestion: Ensure 'cell_line' is constant within each plate. This is typically enforced during allocation by creating separate plates per cell_line level.
  Details: {
    "factor": "cell_line",
    "policy": "separate",
    "plateId": "A549_Day1_Operator_A_T12.0h",
    "valuesFound": ["A549", "HepG2"],
    "countFound": 2,
    "expected": 1
  }

═══════════════════════════════════════════════════════════════
```

**Interpretation**:
1. **batch_marginal_imbalance**: Day 1 has 80 more wells than expected. This is an allocation bug in the generator. Wells not balanced across days.

2. **batch_separate_factor_violation**: Plate contains multiple cell lines. This violates the "separate plates per cell line" policy. Generator should create distinct plates for each cell line.

**Action**: **DO NOT PROCEED**. Fix generator allocation logic. Re-run until errors = 0.

---

## Scenario 4: Confounding Detected (Silent Killer Caught)

```
═══════════════════════════════════════════════════════════════
  PHASE 0 FOUNDER CALIBRATION REPORT
═══════════════════════════════════════════════════════════════

## Violations Summary
  Errors: 0
  Warnings: 4

## Warnings:

⚠️  WARNING: batch_condition_confounding
  Message: Condition 'tBHQ@10.000000uM' not uniformly distributed across 'day' (global). Max deviation: 4.0 wells (100.0%) at level '1' (tolerance 1.0 wells).
  Suggestion: Shuffle compound assignment to break correlation with batch factors.
  Details: {
    "condition": "tBHQ@10.000000uM",
    "factor": "day",
    "scope": "global",
    "maxDeviationCount": "4.0",
    "maxDeviationProportion": "1.000",
    "worstLevel": "1"
  }

⚠️  WARNING: batch_condition_dependence
  Message: Conditions not independent of batch factor 'day' (global): χ²=48.32, df=29, p=0.0129 < α=0.05. Effect size: Cramér's V=0.581 (large).
  Suggestion: Large effect size detected (V=0.581 > 0.3). This is not just statistically significant but practically important. Review compound assignment algorithm to ensure orthogonality with batch structure.
  Details: {
    "factor": "day",
    "scope": "global",
    "chiSquare": "48.32",
    "dof": 29,
    "pValue": "0.0129",
    "cramersV": "0.581",
    "effectSize": "large"
  }

⚠️  WARNING: batch_condition_confounding
  Message: Condition 'tBHQ@10.000000uM' not uniformly distributed across 'day' (plate A549_Day1_Operator_A_T12.0h). Max deviation: 2.0 wells (100.0%) at level '1' (tolerance 1.0 wells).

⚠️  WARNING: batch_condition_confounding
  Message: Condition 'tBHQ@10.000000uM' not uniformly distributed across 'day' (plate A549_Day1_Operator_A_T24.0h). Max deviation: 2.0 wells (100.0%) at level '1' (tolerance 1.0 wells).

═══════════════════════════════════════════════════════════════
```

**Interpretation**:
- Some conditions (tBHQ@10uM) appear ONLY in Day 1 (100% confounded)
- Chi-square confirms significant dependence with LARGE effect size (V=0.581)
- Detected both globally and per-plate

**This is the silent killer**: Marginally balanced but confounded. Cannot separate compound effects from day effects.

**Action**: **FIX GENERATOR**. Shuffle compound assignment to break correlation with batch factors. This is scientifically worthless data.

---

## How to Use This

### 1. Run on Actual Founder

```typescript
import { validateFounderDesign } from './invariants/validateFounder';

const certificate = await validateFounderDesign();
```

### 2. Interpret Output

- **Errors = 0, Warnings = 0**: Perfect. Thresholds aligned.
- **Errors = 0, Warnings > 0**: Review warnings. Decide if founder defines acceptable or if thresholds need adjustment.
- **Errors > 0**: **STOP**. Fix allocation bugs before proceeding.

### 3. Adjust Thresholds (If Needed)

If founder has warnings that are explainable and acceptable:

```typescript
// Before: strict
conditionDistributionTolerance: 0.1, // 10%

// After: founder-derived
conditionDistributionTolerance: 0.15, // 15% (founder max + margin)
```

Document why you relaxed threshold: "Founder design has 15% max deviation at T48h due to X, which is acceptable because Y."

### 4. Set Founder as Baseline

```typescript
// Future designs should be compared to founder:
// - Warn if worse than founder + margin
// - Error if grossly worse than founder

if (newDesignDeviationCount > founderDeviationCount * 1.2) {
  // Warn: 20% worse than founder
}

if (newDesignDeviationCount > founderDeviationCount * 2.0) {
  // Error: 2× worse than founder
}
```

---

## Next Steps

1. **Run on actual phase0_v2 design** from catalog
2. **Review violations** with team
3. **Adjust thresholds** if founder defines different acceptable ranges
4. **Document deviations** in design spec
5. **Use founder as zero point** for all future comparisons

The output should be treated as a calibration report, not a pass/fail test.
