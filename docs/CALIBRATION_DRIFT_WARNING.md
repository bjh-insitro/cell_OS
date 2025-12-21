# Warning: Calibration Constants Affected by Time Semantics Fix

**Date**: 2025-12-20
**Status**: ⚠️ KNOWN ISSUE - Constants may need retuning

---

## The Problem

The time semantics fix (using t0 instead of t1 for biology) corrected a systematic temporal bias. This is good for causality, but it means **any parameters that were tuned under the old (wrong) timebase are now miscalibrated**.

### Specific Parameters Affected

#### 1. Attrition Rates (High Impact)

**File**: `src/cell_os/sim/biology_core.py`

**Constants**:
```python
base_attrition_rates = {
    'er_stress': 0.40,      # Strong cumulative effect
    'proteasome': 0.35,     # Strong cumulative effect
    'oxidative': 0.20,      # Moderate
    'mitochondrial': 0.18,  # Moderate
    'dna_damage': 0.20,     # Moderate
}
```

**Why affected**: Attrition onset threshold uses `time_since_treatment`:
```python
if time_since_treatment_h <= 12.0:
    return 0.0  # No attrition before 12h
```

**Before fix**: `time_since_treatment` used t1 (end of interval)
- After advance_time(12h), `time_since_treatment = 12h + epsilon`
- Attrition could activate immediately

**After fix**: `time_since_treatment` uses t0 (start of interval)
- After advance_time(12h), `time_since_treatment = 12h exactly`
- Attrition activates at correct boundary

**Impact**: Effective attrition rates may be systematically lower (by ~1 step worth of accumulated error). If these rates were fit to data, they were implicitly compensating for the time bias.

---

#### 2. Lag Phase Duration (Medium Impact)

**File**: `src/cell_os/hardware/biological_virtual.py`

**Constant**:
```python
DEFAULT_DOUBLING_TIME_H = 24.0
lag_duration_h = 12.0  # From params
```

**Why affected**: Lag factor computation uses `time_since_seed`:
```python
time_since_seed = self.simulated_time - vessel.seed_time
lag_factor = time_since_seed / lag_duration
```

**Before fix**: Cells aged faster (t1 reference)
**After fix**: Cells age correctly (t0 reference)

**Impact**: Growth curves may shift ~1 step worth of lag. If doubling times were fit to data, they may appear ~5-10% slower now.

---

#### 3. Cross-Talk Coupling Delay (Medium Impact)

**File**: `src/cell_os/hardware/biological_virtual.py`

**Constant**:
```python
TRANSPORT_MITO_COUPLING_DELAY_H = 18.0  # Delay before coupling activates
```

**Why affected**: Uses `time_above_threshold`:
```python
if vessel.transport_high_since is None:
    vessel.transport_high_since = self.simulated_time
time_above_threshold = self.simulated_time - vessel.transport_high_since
```

**Before fix**: Coupling activated ~1 step early
**After fix**: Coupling activates at correct delay

**Impact**: Transport → mito coupling may appear delayed by ~1 step. If this was tuned to match data, the 18h threshold may need adjustment.

---

#### 4. Plating Artifact Decay (Low Impact)

**File**: `src/cell_os/hardware/biological_virtual.py` (plating context)

**Constant**:
```python
tau_recovery_h = 12.0  # Typical recovery time
```

**Why affected**: Decay uses `time_since_seed`:
```python
artifact_magnitude = post_dissoc_stress * exp(-time_since_seed / tau_recovery)
```

**Before fix**: Artifacts decayed faster (aged from t1)
**After fix**: Artifacts decay correctly (aged from t0)

**Impact**: Early timepoint variance may be slightly higher than before. If tau was fit to stabilize confidence margins, it may need slight adjustment.

---

## Verification Strategy

### 1. Depletion Linearity Test

**Test**: Does nutrient depletion scale linearly with interval length?

```python
# Run two simulations:
# Sim A: advance_time(24.0)
# Sim B: advance_time(12.0), advance_time(12.0)

# Assert: glucose drop in A ≈ glucose drop in B (within numerical noise)
```

**Expected**: If time semantics are correct, depletion should be path-independent.

**If fails**: There's still a hidden time leak somewhere.

---

### 2. Attrition Step-Size Independence

**Test**: Does attrition accumulate consistently across step sizes?

```python
# Run three simulations:
# Sim A: advance_time(48.0)
# Sim B: advance_time(24.0), advance_time(24.0)
# Sim C: 48 steps of advance_time(1.0)

# Assert: final viability similar across all three (within integration error)
```

**Expected**: If timebase is correct, viability should converge as dt → 0.

**If fails**: Integration scheme has step-size bias.

---

### 3. Washout Artifact Separation

**Test**: Does washout affect only measurement, not biology?

```python
# Run two simulations (same seed, same biology):
# Sim A: washout ON
# Sim B: washout OFF

# Assert:
# - morph_struct identical
# - viability_factor identical
# - only washout_multiplier differs
# - posterior attribution shifts nuisance, not mechanism
```

**Expected**: Biology should be identical, only measurement layer differs.

**If fails**: Washout leaked into biology somewhere.

---

## Migration Strategy

### Option A: Accept Miscalibration (Recommended for now)

**Status**: Use current constants, accept that they may be slightly off.

**Rationale**:
- Constants were not fit to real data (they're synthetic/exploratory)
- Correcting the timebase is more important than preserving legacy constants
- We can retune later when we have real calibration data

**Action**: Document this in code comments, move forward.

---

### Option B: Scale Constants for Backward Compatibility (Not Recommended)

**Status**: Adjust constants to preserve old behavior.

**Example**: If attrition onset was effectively 11h before (due to t1 bias), keep it at 12h but accept the temporal lie.

**Rationale**: Preserves behavior if someone depends on it.

**Problem**: This perpetuates the bug. Don't do this unless you have a strong reason.

---

### Option C: Refit Constants to Corrected Timebase (Future Work)

**Status**: Wait until we have real data, then refit systematically.

**Rationale**:
- Any constants fit to synthetic data under the old timebase are doubly wrong
- Better to fix the timebase now, refit constants later when we have ground truth

**Action**: Mark all rate constants as "preliminary, may need retuning."

---

## Recommendation

**Use Option A**: Accept that constants may be slightly miscalibrated. The timebase correction is more important than preserving legacy constants that were never fit to real data anyway.

**Document clearly**: Any rate constants (attrition, coupling delays, decay timescales) are "exploratory values, not calibrated to data."

**Next steps**: When real calibration data becomes available, refit systematically under the corrected timebase.

---

## Evidence: Glucose Depletion Shifted by ~40%

**Before fix**: 13.15 mM glucose drop @ 24h (cells aged from t1 perspective)
**After fix**: 8.15 mM drop @ 24h (cells aged from t0 perspective)
**Ratio**: 8.15 / 13.15 = **0.62** (38% reduction in effective rate)

This is roughly consistent with "aging from end of interval vs start" - if depletion was accumulated over [0, 24h] but timestamped at 24h, then used again at [24h, 48h], you'd double-count the last moment.

The fix removes this double-counting, so rates appear ~30-40% lower. If any rate constants were tuned to match data under the old (wrong) timebase, they would have been implicitly inflated to compensate.

---

**Last Updated**: 2025-12-20
**Status**: ⚠️ KNOWN - Use Option A (accept miscalibration, refit later)
