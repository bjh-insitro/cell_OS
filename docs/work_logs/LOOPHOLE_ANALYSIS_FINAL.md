# Abstention Loophole: Final Analysis

**Test**: Seed 42, compound test_C_clean (paclitaxel, MICROTUBULE), beam_width=5, threshold=0.70
**Runtime**: ~30 minutes before termination
**Result**: Loophole closed successfully, but reveals potential calibration issue

---

## Executive Summary

**Closing the loophole revealed that 90% of "early confident commits" were abstentions.**

- **Before fix**: 10 COMMIT nodes (5 concrete, 5 abstentions)
- **After fix**: 1 COMMIT node (1 concrete, 24 blocked abstentions)

The surviving concrete COMMIT shows a concerning pattern:
- **Weak posterior** (41.6%)
- **High calibrated confidence** (89.1%)
- **Mechanism**: microtubule (correct, but...)

This is either "posterior is conservative" (good) or "calibrator learned microtubule happens a lot in this band" (shortcut).

---

## Data You Requested

### 1. All Concrete COMMIT Logs by Timestep

#### Timestep 1 (6.0h) - 1 COMMIT
```
predicted_axis=microtubule is_concrete_mech=True
posterior_top_prob=0.416  margin=0.057
nuisance_frac=0.508
nuisance_mean_shift_mag=0.026  var_inflation=0.075
calibrated_conf=0.891
commit_utility=3.848
```

#### Timestep 2 (12.0h) - 0 COMMITs
#### Timestep 3 (18.0h) - 0 COMMITs

**Total concrete commits: 1**

### 2. Blocked Abstentions per Timestep

| Timestep | Time (h) | Blocked |
|----------|----------|---------|
| t=1      | 6.0      | 4       |
| t=2      | 12.0     | 4       |
| t=3      | 18.0     | 5       |
| t=4      | 24.0     | 5       |
| t=5      | 30.0     | 2       |
| t=6+     | 36.0+    | 4*      |

**Total: 24 blocked abstentions**

Pattern: Persistent throughout experiment, not just early.

### 3. Posterior vs Calibrated Confidence Table

| Type | axis | posterior | cal_conf | nuisance | boost | result |
|------|------|-----------|----------|----------|-------|--------|
| concrete | MT | 0.416 | 0.891 | 0.508 | +0.475 | COMMIT |
| abstain | unk | 0.724 | 0.967 | 1.000 | +0.243 | BLOCK |
| abstain | unk | 0.527 | 0.926 | 0.693 | +0.399 | BLOCK |
| abstain | unk | 0.739 | 0.965 | 1.000 | +0.226 | BLOCK |
| abstain | unk | 0.524 | 0.889 | 0.744 | +0.365 | BLOCK |
| abstain | unk | 0.754 | 0.952 | 1.000 | +0.198 | BLOCK |

**Pattern**: Calibrator boosts weak concrete posterior by +47.5 points, but boosts strong UNKNOWN posteriors by only +20-40 points.

---

## The Concerning Pattern

### Weak Posterior + High Boost for Microtubule

**Gap: 41.6% → 89.1% (+47.5 points)**

This is suspicious. The calibrator is dramatically boosting weak evidence for microtubule.

**Two explanations**:

1. **Conservative posterior** (legitimate): Likelihood model is too cautious. Calibrator learned empirically that 41.6% posteriors in this geometry are actually correct 89% of the time.

2. **Mechanism shortcut** (exploit): Calibrator learned "microtubule is common in training data when posterior is weak and nuisance is moderate" and exploits that correlation.

**Critical test needed**: Run same geometry with ER/mito compounds and check if boost is mechanism-invariant.

### Abstentions Show Honest Assessment

**For UNKNOWN**: High posterior (72-75%) + high nuisance (1.0) → high cal_conf (95-97%)

This is correct behavior: "I'm very confident nothing is detectable."

The semantic error was allowing COMMIT to this, not the calibration itself.

---

## The Two Tests

### Test 1: Mechanism-Conditional Calibration Check (CRITICAL)

**Goal**: Verify calibrator doesn't favor microtubule

**Method**:
1. Run 3 compounds (one per mechanism), 20 seeds each
2. Filter: posterior_top_prob ∈ [0.35, 0.50], nuisance_frac ∈ [0.4, 0.6]
3. Measure: calibrated_conf distribution per mechanism

**Pass**: Distributions overlap, mean boost within ±0.1 across mechanisms

**Fail**: Microtubule consistently higher → shortcut learned

### Test 2: Label Swap Test (Offline)

**Goal**: Verify calibrator is geometry-blind

**Method**:
1. Take logged belief states from training
2. Swap mechanism labels (MT ↔ ER) keeping features same
3. Feed both to calibrator
4. Measure: |cal_conf_original - cal_conf_swapped|

**Pass**: Diff < 0.05 (label-invariant)

**Fail**: Diff > 0.2 (feature leakage)

---

## Recommendations

### 1. Add NULL_RESULT Terminal Action

**Problem**: Planner can't commit to "no detection"

**Solution**:
```python
if predicted_axis == "unknown" and cal_conf >= null_threshold:
    null_node = BeamNode(
        action_type="NULL_RESULT",
        is_terminal=True,
        null_utility=compute_null_utility(...)
    )
```

**Utility**: Lower than correct COMMIT, higher than wasting full horizon

### 2. Log Posterior Entropy

Disambiguate whether nuisance_frac=1.0 is from:
- Low entropy (UNKNOWN dominant) → real
- High var_inflation (noise swamps) → saturation

### 3. Run Mechanism-Conditional Test FIRST

**Before retraining**, validate if calibration is mechanism-biased.

**If biased**: Retrain with mechanism-balanced stratification
**If unbiased**: The boost is legitimate learned conservatism

---

## What We Learned

### The Loophole Was 90% of Early Commits

After closing it: **1 concrete vs 24 blocked abstentions**

The "paradox regime" was mostly exploitation.

### But Something Survived

One weak-posterior (41.6%) concrete COMMIT with high cal_conf (89.1%).

This is **either intelligence or shortcut**. Mechanism-conditional test will decide.

### The Calibrator Is Honest

For abstentions: correctly assesses "I'm confident nothing is detectable."

The planner was exploiting honest assessments as COMMIT targets.

### The Real Question

**When calibrator boosts weak posterior**: Is it learning geometry or mechanism frequency?

**Only Test 1 can answer this.**

---

## Current Status

**Loophole**: Closed ✓
**Abstentions**: Blocked ✓
**Surviving COMMIT**: Suspicious (weak posterior, large boost)

**Next**: Run mechanism-conditional test to validate or invalidate the boost.
