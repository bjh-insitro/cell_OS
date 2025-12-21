# Agent 3: Mechanism Posterior Calibration Tracking (ECE) - COMPLETE

**Mission**: Add mechanism posterior calibration tracking so the system can detect and surface overconfidence, not just wrong answers.

**Status**: ✅ CORE INSTRUMENTATION COMPLETE

**Date**: 2025-12-21

---

## Executive Summary

Agent 3 has successfully instrumented **mechanism posterior calibration tracking** using Expected Calibration Error (ECE). The system can now answer:

> **"When the agent says '90% sure', is it actually right ~90% of the time?"**

This is **pure instrumentation** - no policy changes, no accuracy improvements, just honest measurement of confidence calibration.

---

## What Was Built

### Core Infrastructure ✅

**Location**: `src/cell_os/hardware/mechanism_posterior_v2.py`

1. **CalibrationEvent** (dataclass)
   - Records: `confidence` (max posterior), `correct` (bool)
   - Validates bounds: confidence ∈ [0,1]

2. **MechanismCalibrationTracker** (class)
   - Accumulates classification events
   - Computes ECE with small-sample guardrails
   - Returns statistics for diagnostics

3. **compute_ece** (pure function)
   - Canonical ECE implementation
   - Bins by confidence, weights by bin size
   - Deterministic, no side effects

---

## ECE Formula (Implemented)

```
ECE = Σ_k (|B_k| / N) · |acc(B_k) - conf(B_k)|
```

Where:
- `B_k` = bin k (confidence range)
- `acc(B_k)` = accuracy in bin k (fraction correct)
- `conf(B_k)` = mean confidence in bin k
- `N` = total samples

**Defaults**:
- `n_bins = 10` (evenly spaced in [0, 1])
- `min_samples_for_stability = 30`
- Ignore empty bins

---

## Test Results ✅

All tests **PASS**:

### Test 1: Overconfidence Detection ✅
**Scenario**:
- Agent: "95% confident"
- Reality: 60% correct
- **ECE = 0.35** (HIGH - catastrophic miscalibration)

### Test 2: Underconfidence Detection ✅
**Scenario**:
- Agent: "55% confident"
- Reality: 90% correct
- **ECE = 0.35** (HIGH - conservative bias)

### Test 3: Well-Calibrated Case ✅
**Scenario**:
- 90% confident → 90% correct
- 70% confident → 70% correct
- 50% confident → 50% correct
- **ECE = 0.00** (LOW - ideal calibration)

### Test 4: Small Sample Warning ✅
**Scenario**:
- Only 10 events (< 30 minimum)
- **`is_stable = False`** (prevents false alarms)

### Additional Tests ✅
- Tracker record mechanism
- Statistics computation
- Edge cases (empty, perfect confidence = 1.0)
- Determinism
- Mixed confidence bins

---

## Usage Example

```python
from cell_os.hardware.mechanism_posterior_v2 import (
    MechanismCalibrationTracker,
    Mechanism
)

# Initialize tracker
tracker = MechanismCalibrationTracker(min_samples_for_stability=30)

# After each classification
posterior = {"ER_STRESS": 0.72, "MITO": 0.18, "MICRO": 0.10}
predicted = max(posterior, key=posterior.get)
true_mechanism = "ER_STRESS"  # From simulator

tracker.record(
    predicted=predicted,
    true_mechanism=true_mechanism,
    posterior=posterior
)

# Check calibration
ece, is_stable = tracker.compute_ece()
if is_stable and ece > 0.15:
    logger.warning(f"Mechanism posteriors miscalibrated: ECE={ece:.3f}")

# Get full statistics
stats = tracker.get_statistics()
# {
#   "n_samples": 50,
#   "mean_confidence": 0.75,
#   "accuracy": 0.68,
#   "ece": 0.12,
#   "is_stable": True
# }
```

---

## What This Enables

### Before Agent 3:
- System could be **confidently wrong**
- No visibility into confidence calibration
- Accuracy alone doesn't catch overconfidence
- Example: 67% accurate but claiming 95% confidence

### After Agent 3:
- **Overconfidence is MEASURABLE**
- ECE metric quantifies calibration gap
- Logs can show: "Agent is overconfident by 0.35"
- Human reviewers can detect miscalibration

---

## Design Decisions

### 1. Why ECE (not Brier score, log loss)?
- **Interpretable**: Gap between claimed and realized confidence
- **Robust**: Bins smooth out noise
- **Standard**: Well-understood metric in calibration literature

### 2. Why 30 samples minimum?
- ECE is unstable at low n (high variance)
- 30 is a reasonable heuristic for basic stability
- Below 30: compute but mark `is_stable=False`

### 3. Why 10 bins?
- Standard in calibration literature
- Too few bins: poor resolution
- Too many bins: sparse, unstable
- 10 is a good balance

### 4. Why pure function `compute_ece()`?
- Testable in isolation
- No side effects
- Deterministic
- Can be used in analysis scripts

### 5. Why separate tracker class?
- Decouples calibration from posterior logic
- Easier to add/remove without touching inference
- Clear lifecycle (one tracker per run)

---

## Non-Goals (Intentionally Not Done)

❌ **Did not** add learning/optimization
❌ **Did not** renormalize posteriors
❌ **Did not** "fix" miscalibration
❌ **Did not** change decision policies
❌ **Did not** couple to epistemic debt

**This is instrumentation only.** Detection, not correction.

---

## Pending Work (For Integration)

The core ECE computation is **COMPLETE**. To fully integrate:

### Step 2: Emit Calibration Events (pending)
- Wire `tracker.record()` into mechanism classification pipeline
- Call on EVERY classification (no filtering)
- Location: wherever `classify_mechanism()` happens

### Step 5: JSONL Logging (pending)
```json
{
  "event": "mechanism_calibration",
  "ece": 0.22,
  "n_samples": 64,
  "n_bins": 10,
  "unstable": false,
  "timestamp": 123.4
}
```

### Step 6: Alerting (pending)
```python
ECE_ALERT_THRESHOLD = 0.15

if ece > ECE_ALERT_THRESHOLD and is_stable:
    emit_diagnostic({
        "event": "mechanism_calibration_alert",
        "ece": ece,
        "threshold": ECE_ALERT_THRESHOLD,
        "message": "Mechanism posteriors appear miscalibrated"
    })
```

**Note**: These are integration tasks, not core algorithm changes.

---

## Files Changed

### Modified:
1. **`src/cell_os/hardware/mechanism_posterior_v2.py`**
   - Added `CalibrationEvent` dataclass
   - Added `MechanismCalibrationTracker` class
   - Added `compute_ece()` pure function
   - ~250 lines of new code

### New:
1. **`tests/epistemic/test_mechanism_calibration.py`**
   - 10 comprehensive tests
   - All tests PASS ✅
   - Proves overconfidence/underconfidence detection

2. **`docs/AGENT_3_CALIBRATION_TRACKING_COMPLETE.md`** (this file)

---

## Acceptance Criteria (Met)

✅ **ECE is computed deterministically**
- Pure function, no side effects

✅ **Overconfidence is detectable in tests**
- Test 1: ECE = 0.35 for 95% conf / 60% accuracy

✅ **No runtime behavior changes**
- Pure instrumentation, no policy coupling

✅ **No coupling to policy or debt**
- Separate tracker class, decoupled

✅ **Reviewer can answer: "Is the agent honest about confidence?"**
- Yes, via ECE metric and statistics

---

## The Final Check

> **If the agent confidently hallucinated mechanisms for 100 cycles, would this patch make that obvious to a human reading logs?**

**YES.**

With ECE tracking:
- Overconfidence: ECE ~ 0.3-0.4 (HIGH)
- Logs show: `"ece": 0.35, "mean_confidence": 0.95, "accuracy": 0.60`
- Human sees: Agent claims 95% but is only 60% right
- **Miscalibration is VISIBLE**

Without ECE tracking:
- Only accuracy visible (60%)
- Can't tell if agent is overconfident or just uncertain
- **Miscalibration is HIDDEN**

---

## Test Output

```
============================================================
Test 1: Overconfidence Detection
============================================================
Overconfidence test: ECE = 0.350
✓ PASS

============================================================
Test 2: Underconfidence Detection
============================================================
Underconfidence test: ECE = 0.350
✓ PASS

============================================================
Test 3: Well-Calibrated Case
============================================================
Well-calibrated test: ECE = 0.000
✓ PASS

============================================================
Test 4: Small Sample Warning
============================================================
Small sample test: n=10, ECE=0.350, stable=False
✓ PASS
```

---

## Comparison to Mission Brief

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Compute ECE deterministically | ✅ | `compute_ece()` pure function |
| Overconfidence detectable | ✅ | Test 1: ECE = 0.35 |
| No runtime behavior changes | ✅ | Pure instrumentation |
| No coupling to policy/debt | ✅ | Separate tracker class |
| Small-sample guardrails | ✅ | `is_stable` flag < 30 samples |
| Tests: overconfidence | ✅ | Test 1 PASS |
| Tests: underconfidence | ✅ | Test 2 PASS |
| Tests: well-calibrated | ✅ | Test 3 PASS |
| Tests: small sample | ✅ | Test 4 PASS |

---

## Next Steps (Integration)

To complete the full mission:

1. **Wire tracker into classification pipeline**
   - Call `tracker.record()` after every mechanism classification
   - Ensure `true_mechanism` is available from simulator metadata

2. **Add JSONL logging**
   - Emit `"mechanism_calibration"` event every N cycles
   - Log to `diagnostics.jsonl` (not `evidence.jsonl`)

3. **Add non-blocking alerts**
   - Check `ece > 0.15` and `is_stable`
   - Emit `"mechanism_calibration_alert"` event
   - Do NOT block execution

These are integration tasks (plumbing), not algorithm changes (logic).

---

## Lessons Learned

1. **Pure functions are testable**: `compute_ece()` can be tested exhaustively without mocking

2. **Small-sample guardrails matter**: ECE is garbage at n < 30, must be explicit

3. **Determinism is a feature**: Same events → same ECE (always)

4. **Separation of concerns wins**: Tracker is separate from posterior, easier to test/maintain

5. **Tests prove detection**: Without tests, "detection" is just hopeful comments

---

## Conclusion

Agent 3 has successfully instrumented **mechanism posterior calibration tracking**.

The system can now:
- **Measure** confidence calibration (ECE metric)
- **Detect** overconfidence (ECE > 0.15)
- **Distinguish** accuracy from calibration
- **Prevent** false alarms (small-sample guardrails)

**This is honesty about uncertainty, not accuracy improvement.**

If the agent is confidently wrong, ECE will show it.

---

**Agent 3 Status**: ✅ CORE INSTRUMENTATION COMPLETE

Calibration is now measurable. Overconfidence is detectable.

**Integration pending**: Wire tracker into classification pipeline, add JSONL logging, add alerts.
