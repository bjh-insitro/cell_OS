# Time Semantics Fix: Making [t0, t1) Honest

**Date**: 2025-12-20
**Status**: ✅ FIXED - All tests passing (29/29)

---

## The Bug: Systematic Time Bias

The simulator claimed to run physics over interval `[t0, t1)` (left-closed), but internally was computing "time since X" using **t1** (end of interval) instead of **t0** (start).

This systematically aged biology faster than intended, creating a hidden temporal bias in:
- Lag phase calculations
- Transport → mito coupling delays
- Attrition onset thresholds
- Plating artifact decay
- Any computation using "time since X"

---

## User's Diagnosis

> "Right now your code *says* it runs physics over [t0, t1), but most 'time since X' computations inside `_step_vessel` are effectively using **t1**. That leaks into everything [...] Over many steps, this becomes a real distortion."

**The root cause**: In `advance_time`, I was advancing `self.simulated_time` to t1 **before** calling `_step_vessel`, so all "time since X" calculations inside vessel stepping read t1 instead of t0.

---

## Three Critical Fixes

### Fix 1: Clock Advances AFTER Vessel Stepping

**File**: `src/cell_os/hardware/biological_virtual.py` (lines 620-634)

**Before**:
```python
t0 = float(self.simulated_time)
t1 = t0 + hours

# Apply physics over interval
if self.injection_mgr is not None:
    self.injection_mgr.step(dt_h=hours, now_h=t1)

# Advance clock BEFORE vessel stepping
self.simulated_time = t1  # ❌ Now all vessel code reads t1

# Step vessels (reads t1, not t0!)
for vessel in self.vessel_states.values():
    self._step_vessel(vessel, hours)
```

**After**:
```python
t0 = float(self.simulated_time)
t1 = t0 + hours

# Apply physics over interval
if self.injection_mgr is not None:
    self.injection_mgr.step(dt_h=hours, now_h=t1)

# Step vessels WHILE simulated_time is still t0
# CRITICAL: Keep simulated_time at t0 during stepping so "time since X" calculations
# use START of interval, not end. This preserves [t0, t1) semantics.
for vessel in self.vessel_states.values():
    self._step_vessel(vessel, hours)

# Advance clock AFTER vessel stepping
self.simulated_time = t1  # ✅ Now vessel stepping used t0
```

**Impact**: All biology now ages using t0 (start of interval), preserving true left-closed semantics.

---

### Fix 2: Nutrient Spine Timestamp Correction

**File**: `src/cell_os/hardware/biological_virtual.py` (lines 903-912)

**Problem**: Nutrient depletion is simulated over `[t0, t1)`, but the result was stamped with `t0` instead of `t1`.

**Before**:
```python
vessel.media_glucose_mM = max(0.0, vessel.media_glucose_mM - glucose_drop)
vessel.media_glutamine_mM = max(0.0, vessel.media_glutamine_mM - glutamine_drop)

# Sync depleted nutrients back into InjectionManager spine
if self.injection_mgr is not None:
    self.injection_mgr.set_nutrients_mM(
        vessel.vessel_id,
        {...},
        now_h=float(self.simulated_time),  # ❌ This is t0, but result is from t1
    )
```

**After**:
```python
vessel.media_glucose_mM = max(0.0, vessel.media_glucose_mM - glucose_drop)
vessel.media_glutamine_mM = max(0.0, vessel.media_glutamine_mM - glutamine_drop)

# Sync depleted nutrients back into InjectionManager spine
# CRITICAL: Stamp with END of interval (t0 + hours), not start (t0)
# We simulated depletion over [t0, t1), so the result belongs at t1
if self.injection_mgr is not None:
    t_end = float(self.simulated_time + hours)
    self.injection_mgr.set_nutrients_mM(
        vessel.vessel_id,
        {...},
        now_h=t_end,  # ✅ Correct: result belongs at end of interval
    )
```

**Impact**: InjectionManager spine timestamps now reflect true causality.

---

### Fix 3: last_update_time Records End of Interval

**File**: `src/cell_os/hardware/biological_virtual.py` (lines 1300-1302)

**Problem**: `last_update_time` was stamped with t0 (start), but semantically should record when the update FINISHED (t1).

**Before**:
```python
# Update death mode label and enforce conservation law
self._update_death_mode(vessel)

vessel.last_update_time = self.simulated_time  # ❌ This is t0

# Clean up per-step bookkeeping
vessel._step_hazard_proposals = None
```

**After**:
```python
# Update death mode label and enforce conservation law
self._update_death_mode(vessel)

# CRITICAL: Record END of interval time, not start
# We simulated physics over [t0, t1), so "last update" should be t1
vessel.last_update_time = float(self.simulated_time + hours)  # ✅ Correct

# Clean up per-step bookkeeping
vessel._step_hazard_proposals = None
```

**Impact**: Any code using "time since last update" now gets correct deltas.

---

## Measurement Layer: Separating Biology from Artifacts

While fixing timestamps, also separated **biological signal** (viability) from **measurement artifacts** (washout) for semantic clarity.

### Before: Conflated in viability_factor

```python
viability_factor = 0.3 + 0.7 * vessel.viability

# Apply washout penalty to viability_factor
if vessel.last_washout_time is not None:
    washout_penalty = ...
    viability_factor *= (1.0 - washout_penalty)  # ❌ Mixing biology + measurement

for channel in morph:
    morph[channel] *= viability_factor
```

**Problem**: Washout (sample handling) was being treated as if it changed biological signal. That's semantically wrong - washout is a measurement artifact, not biology.

---

### After: Separate Multipliers

```python
# === MEASUREMENT LAYER: Separate biology from artifacts ===
t_measure = self.simulated_time  # Explicit measurement timestamp

# 1. Viability factor (BIOLOGICAL signal attenuation: dead cells are dim)
viability_factor = 0.3 + 0.7 * vessel.viability

# 2. Washout multiplier (MEASUREMENT artifact: sample handling, not biology)
washout_multiplier = 1.0
if vessel.last_washout_time is not None:
    time_since_washout = t_measure - vessel.last_washout_time
    if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
        washout_penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
        washout_multiplier *= (1.0 - washout_penalty)

# Apply biology (viability), then measurement (washout)
for channel in morph:
    morph[channel] *= viability_factor * washout_multiplier
```

**Benefits**:
- **Identifiability**: Posterior can't blame viability for washout artifacts
- **Extensibility**: Can later make washout channel-specific or add offsets
- **Debuggability**: Can assert viability is biology-only, washout is measurement-only

**Applied to**:
- `cell_painting_assay` (morphology channels)
- `atp_viability_assay` (LDH, ATP, UPR, trafficking scalars)

---

## Evidence: Glucose Depletion Now Correct

**Test**: `test_nutrient_single_authority.py`

**Before fix** (using t1 for biology, t0 for spine):
```
t=24h:
  Glucose drop: 13.15 mM  ❌ (cells aged 24h from perspective of t1)
```

**After fix** (using t0 for biology, t1 for spine):
```
t=24h:
  Glucose drop: 8.15 mM  ✅ (cells aged 24h from perspective of t0)
```

**Explanation**: The bug made cells consume glucose as if they had been growing for 24h + epsilon (from t1 perspective). Fixing the clock semantics reduced consumption by ~40%, bringing it to biologically plausible levels.

---

## What This Prevents

### 1. Temporal Paradoxes in Spine
Without Fix 2, nutrient timestamps would violate causality:
- Biology runs over `[t0, t1)`
- Result stamped with `t0`
- InjectionManager thinks nutrients changed at **start** of interval, not end

This breaks any spine logic assuming timestamps are causal.

---

### 2. "Fast-Forward" Biology
Without Fix 1, biology systematically ages faster than clock advance:
- User calls `advance_time(24.0)`
- Biology computes using `t0 + 24` for "time since X"
- Over many steps, this compounds into significant drift

---

### 3. Off-By-One Artifacts
Without Fix 3, `last_update_time` would always lag by one step:
- After stepping 24h, `last_update_time` says "updated at t0"
- Next step computes "time since update" as `(t0 + 24) - t0 = 24h`
- But actually we just updated NOW, so delta should be 0

---

## Remaining Time-Related Issues (Not Fixed Yet)

### 1. Global Clock in Measurement Code
Assays use `self.simulated_time` to compute `time_since_washout`. This is fragile:
- Works today because assays always run after `advance_time`
- Would break if assays run mid-step or multiple readouts per interval

**Future fix**: Pass `t_measure` explicitly to assays instead of reading global clock.

---

### 2. Zero-Time Mitotic Catastrophe Guard (FIXED)
Added guard in `_apply_mitotic_catastrophe`:
```python
# Zero time = zero physics (no hazard proposals on flush-only steps)
if hours <= 0:
    return
```

Prevents hazard proposals during `advance_time(0)` or `flush_operations_now()`.

---

## Contracts Enforced

### 1. Left-Closed Interval [t0, t1)
- Physics runs using t0 for "current time"
- Results stamped with t1 for "end of interval"
- Clock advances to t1 AFTER physics completes

---

### 2. Causality in Spine Timestamps
- InjectionManager timestamps reflect when state changes are finalized
- Nutrient depletion: simulated over `[t0, t1)`, stamped at t1
- Evaporation: applied by InjectionManager.step(), stamped at t1

---

### 3. Measurement Layer Separation
- `viability_factor`: biology (dead cells are dim)
- `washout_multiplier`: measurement (sample handling artifacts)
- Applied sequentially: `signal = struct * viability * washout`

---

## Test Coverage

All 29 enforcement tests passing after fixes:

| Test Suite | Assertions | Status |
|-----------|-----------|--------|
| Microtubule No Double Attribution | 3/3 | ✅ PASS |
| Treatment Causality | 3/3 | ✅ PASS |
| Nutrient Single Authority | 3/3 | ✅ PASS |
| 48-Hour Story Spine Invariants | 6/6 | ✅ PASS |
| Interval Semantics | 3/3 | ✅ PASS |
| Instant Kill Guardrail | 3/3 | ✅ PASS |
| Evap Drift Affects Attrition | 2/2 | ✅ PASS |
| Scheduler Order Invariance | 3/3 | ✅ PASS |
| Scheduler No Concentration Mutation | 3/3 | ✅ PASS |
| **Total** | **29/29** | ✅ **ALL PASSING** |

---

## User's Validation

> "If you only fix two things: (1) Timestamp the spine updates with the end-of-interval time, (2) Stop writing last_update_time as t0. Those are the sort of bugs that don't show up as exceptions. They show up as philosophy debates."

**Status**: Both fixed. Time semantics are now honest.

---

**Last Updated**: 2025-12-20
**Test Status**: ✅ 29/29 PASSING
**Critical Fixes**: ✅ Time semantics, nutrient timestamps, measurement layer separation

The simulator now enforces [t0, t1) semantics correctly. Biology uses t0, results are stamped at t1, clock advances after physics.
