# Next Tests: Mechanism Bias + NO_DETECTION

**Status**: Loophole closed, NO_DETECTION action added, mechanism-conditional test ready

---

## What Was Implemented

### 1. NO_DETECTION Terminal Action ✓

**Purpose**: Formalize abstention as legitimate outcome, not exploitation

**Implementation**:
```python
# In BeamNode:
action_type: str = "CONTINUE"  # "CONTINUE", "COMMIT", or "NO_DETECTION"
no_detection_utility: Optional[float] = None

# In BeamSearch.__init__():
self.no_detection_threshold = 0.80  # Higher than COMMIT (require more confidence)
self.w_no_detection_conf = 3.0      # Lower reward than COMMIT (less valuable)
self.w_no_detection_time = 0.15     # Stronger time penalty (should stop earlier)
self.w_no_detection_ops = 0.05

# In _expand_node():
if predicted_axis == "unknown" and cal_conf >= no_detection_threshold:
    no_det_node = BeamNode(
        action_type="NO_DETECTION",
        is_terminal=True,
        no_detection_utility=compute_no_detection_utility(...)
    )
```

**Utility Formula**:
```
NO_DETECTION_utility = w_conf * cal_conf - w_time * elapsed_h - w_ops * ops

Where:
- w_conf = 3.0 (vs 5.0 for COMMIT)  → null result less valuable than discovery
- w_time = 0.15 (vs 0.1 for COMMIT) → stronger penalty, should stop earlier
- w_ops = 0.05 (same as COMMIT)     → operations cost same
```

**Effect**: Planner can now honestly stop when nothing is detectable, without exploiting COMMIT loophole.

### 2. Mechanism-Conditional Test Script ✓

**File**: `test_mechanism_conditional_calibration.py`

**Design**:
- 3 compounds (MT, ER, mito) × 20 seeds = 60 runs
- Extract belief states at multiple timesteps
- Filter to weak-posterior slice: `posterior ∈ [0.35, 0.50]`, `nuisance ∈ [0.4, 0.6]`
- Compare calibrated_conf distributions across mechanisms

**Metrics**:
1. **Mean calibrated_conf per mechanism** (bias check)
2. **Std calibrated_conf per mechanism** (variance check)
3. **Mean boost** (cal_conf - posterior_top_prob)
4. **Empirical accuracy** (is boost justified?)
5. **Overconfidence bins** (cal_conf vs accuracy by bins)

**Pass Condition**: Calibrated_conf distributions overlap, diff < 0.10

**Fail Condition**: One mechanism systematically higher → shortcut learned

---

## The Two Critical Tests

### Test 1: Mechanism-Conditional Calibration (PRIMARY)

**Run**: `python3 test_mechanism_conditional_calibration.py`

**Time**: ~30-60 minutes (60 runs with caching)

**What It Tests**: Is calibrator mechanism-biased or geometry-only?

**Expected Output**:
```
MECHANISM-CONDITIONAL CALIBRATION ANALYSIS

MICROTUBULE:
  Count: 47
  Mean posterior_top_prob: 0.423
  Mean calibrated_conf: 0.872 ± 0.042
  Mean boost: +0.449
  Empirical accuracy: 0.851

ER_STRESS:
  Count: 38
  Mean posterior_top_prob: 0.419
  Mean calibrated_conf: 0.865 ± 0.048
  Mean boost: +0.446
  Empirical accuracy: 0.842

MITOCHONDRIAL:
  Count: 41
  Mean posterior_top_prob: 0.421
  Mean calibrated_conf: 0.868 ± 0.045
  Mean boost: +0.447
  Empirical accuracy: 0.854

BIAS CHECK:
Max calibrated_conf: microtubule (0.872)
Min calibrated_conf: er_stress (0.865)
Difference: 0.007

✓ PASS: Calibrator appears MECHANISM-INVARIANT
```

**If FAIL** (diff > 0.10):
```
⚠️  WARNING: Calibrator appears MECHANISM-BIASED
   Difference 0.173 > 0.10 threshold
   microtubule is favored over er_stress

   AND: Accuracy difference is only 0.009
        Calibrator is overconfident on microtubule without justification
        This is a SHORTCUT LEARNED FROM TRAINING DATA
```

**Remediation if biased**:
1. Retrain calibrator with mechanism-balanced stratification
2. Each (posterior_bin, nuisance_bin) should have equal mechanism counts
3. Or: Include mechanism as explicit feature (but own mechanism-conditional calibration)

### Test 2: Rerun Seed 42 with NO_DETECTION Enabled

**Run**: Same test script, but with NO_DETECTION action active

**What It Tests**: Does planner prefer NO_DETECTION over wasting time?

**Expected**:
- **Before**: 24 blocked abstentions → forced busywork
- **After**: ~15-20 NO_DETECTION nodes created → honest null results

**Check logs for**:
```
NO_DETECTION node created at t=X:
  predicted_axis=unknown
  calibrated_conf=0.967
  no_detection_utility=2.450
  threshold=0.80
```

**Compare utilities**:
- COMMIT utility: 3.8-4.2 (high)
- NO_DETECTION utility: 2.0-2.5 (moderate, but honest)
- Exploration heuristic: 1.5-2.0 (lower)

NO_DETECTION should be preferred over continued exploration when confident in null.

---

## Why These Tests Matter

### The Surviving COMMIT Is Suspicious

From seed 42 loophole-closed run:
- Posterior: 41.6%
- Calibrated: 89.1%
- Boost: +47.5 points

This is either:
1. **Legitimate**: Posterior is conservative, calibrator learned geometry
2. **Shortcut**: Calibrator learned "microtubule is common in training"

**Test 1 decides which.**

### The Planner Is a Null-Result Machine

24 blocked abstentions across all timesteps shows:
- Planner repeatedly tries to commit to "unknown"
- No honest terminal action available
- Forced into busywork

**Test 2 fixes this.**

---

## What Success Looks Like

### Test 1 Success (Mechanism-Invariant)

**Output**:
```
Max - Min calibrated_conf: 0.008
✓ PASS: Calibrator appears MECHANISM-INVARIANT

OVERCONFIDENCE CHECK:
MICROTUBULE:
  [0.8, 0.9): n= 32  cal_conf=0.851  accuracy=0.844  diff=+0.007 ✓
  [0.9, 1.0): n= 15  cal_conf=0.923  accuracy=0.933  diff=-0.010 ✓
```

**Interpretation**: Calibrator learned "this geometry is conservative," not "microtubule happens a lot."

The weak-posterior boost is **legitimate learned judgment**.

### Test 1 Failure (Mechanism-Biased)

**Output**:
```
Max - Min calibrated_conf: 0.184
⚠️  WARNING: Calibrator appears MECHANISM-BIASED
microtubule (0.912) vs er_stress (0.728)

Accuracy difference: 0.011
Calibrator overconfident on microtubule without justification
SHORTCUT LEARNED FROM TRAINING DATA
```

**Interpretation**: Calibrator learned mechanism frequency, not geometry.

Need to **retrain with balanced data**.

### Test 2 Success (NO_DETECTION Works)

**Output**:
```
NO_DETECTION nodes created: 18
COMMIT nodes created: 2
Blocked abstentions: 0

NO_DETECTION utilities: 2.1-2.6 (honest null results)
COMMIT utilities: 3.8-4.1 (real discoveries)

Planner prefers NO_DETECTION over busywork when confident in null.
```

**Interpretation**: Planner can now be honest about null results.

---

## Current Status

**Loophole**: Closed ✓
**NO_DETECTION**: Implemented ✓
**Test script**: Ready ✓

**Next**: Run Test 1 (60 seeds, ~30-60 minutes)

**Expected**: Either validation or falsification of calibrator boost.

Either way: **Falsifiable science**, not vibes.

---

## The Question That Matters

**When calibrator boosts weak posterior from 41.6% to 89.1%**:

Is it learning:
- "This geometry pattern is usually right" (geometry-only, good)
- "Microtubule is common when posterior is weak" (mechanism shortcut, bad)

**Test 1 answers this definitively.**

If geometry-only: The paradox regime is real, calibrator does real work.

If mechanism shortcut: The paradox regime was training data leakage.

---

## One More Question

**Why is UNKNOWN so dominant in "clean paclitaxel microtubule" runs?**

Possible explanations:
1. Paclitaxel signature is weak/delayed at early timepoints (6-12h)
2. Nuisance model too aggressive, eating signal
3. Posterior covariance signatures misaligned

**Check after Test 1**: If ER/mito also show high UNKNOWN rates → simulator issue, not calibrator bias.

If only microtubule → maybe paclitaxel is actually weak in this simulation.

---

## Ready to Run

**Command**: `python3 test_mechanism_conditional_calibration.py`

**Time**: 30-60 minutes

**Output**: Saved to `/tmp/mechanism_conditional_results.pkl` + console summary

**Then**: Paste results, I'll tell you if it's intelligence or shortcut.
