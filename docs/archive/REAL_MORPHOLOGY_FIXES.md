# Real Morphology Feedback: Implementation & Issues

## What Was Fixed

### 1. Replaced Dose Proxy with Real Morphology Disruption

**Before (wrong):**
```python
morph_penalty_approx = dose_uM / (dose_uM + ic50_base * 0.3)  # Dose proxy
attrition_scale = 1.0 + 2.0 * morph_penalty_approx
```

**After (correct):**
```python
# Compute REAL morphology disruption from actual values
actin_disruption = max(0.0, 1.0 - morph['actin'] / base['actin'])
mito_disruption = max(0.0, 1.0 - morph['mito'] / base['mito'])
transport_dysfunction_score = (actin_disruption + mito_disruption) / 2.0

# Use real disruption for attrition
dys = transport_dysfunction_score
attrition_scale = 1.0 + 2.0 * (dys ** 2.0)  # Nonlinear ceiling
```

✅ **No more dose proxy** - attrition directly responds to actual morphology

---

### 2. Added Nonlinear Ceiling (dys^2)

**Purpose:** Prevent mild disruption from causing inevitable death

**Scaling:**
- 20% disruption → scale = 1 + 2×(0.2)² = 1.08× (mild, allows recovery)
- 40% disruption → scale = 1 + 2×(0.4)² = 1.32× (moderate)
- 60% disruption → scale = 1 + 2×(0.6)² = 1.72× (severe, accelerates death)

✅ **Quadratic scaling** creates ceiling for mild disruption

---

### 3. Fixed Hidden EC50 Coupling

**Before:** Attrition used `ic50_base * 0.3` (tied to viability IC50)
**After:** Attrition uses `transport_dysfunction_score` (morphology-derived)

✅ **No more hidden coupling** between viability and attrition timelines

---

### 4. Fixed Comprehensive Table

**Changes:**
- Seed random state once (not per-well) → reveals real variance
- Create agent once per dose row (not per-well) → proper statefulness
- Added explicit LDH → viability conversion comments

✅ **More honest variance**, less artificial determinism

---

## Current Issue: Morphology Accumulation Bug

### Observation

At fixed low dose (0.3 µM nocodazole), morphology disruption **increases over time**:

| Time | Actin Loss | Pattern |
|------|------------|---------|
| 12h  | 31.9%      | Moderate |
| 24h  | 31.0%      | Moderate |
| 48h  | 29.6%      | Moderate |
| 72h  | 34.9%      | Moderate |
| 96h  | 41.7%      | **Severe** |

**Expected:** Morphology should be stable (~31%) at fixed dose
**Actual:** Morphology worsens over time (31% → 42%)

---

### Root Cause

**Feedback loop:**
1. Morphology disrupts (31%)
2. Attrition kills some cells → viability drops
3. Dead cells have reduced morphology signal (viability_factor = 0.3 + 0.7×viability)
4. Lower morphology → higher transport_dysfunction_score
5. Higher dysfunction → higher attrition
6. Back to step 2 (cycle repeats)

**Code:**
```python
# In morphology calculation:
viability_factor = 0.3 + 0.7 * vessel.viability  # Dead cells retain 30% signal
for channel in morph:
    morph[channel] *= viability_factor  # THIS CREATES THE FEEDBACK LOOP
```

When viability drops from 98% → 70%, viability_factor drops from 0.99 → 0.79, reducing morphology signal by 20%, which increases dysfunction score, which increases attrition...

---

### Solution Options

**Option 1: Clamp dysfunction score to initial value**
```python
# Store initial dysfunction at first calculation
if not hasattr(well, 'initial_dysfunction'):
    well.initial_dysfunction = transport_dysfunction_score

# Use initial value for attrition (don't let it grow)
dys = well.initial_dysfunction
```

**Pros:** Breaks feedback loop cleanly
**Cons:** Requires state threading

---

**Option 2: Separate "structural dysfunction" from "signal loss"**
```python
# Compute structural dysfunction BEFORE applying viability factor
transport_dysfunction_score = compute_disruption(morph_before_viability, base)

# Apply viability factor AFTER computing dysfunction
morph *= viability_factor
```

**Pros:** Conceptually correct (dead cells have broken structure even if signal is low)
**Cons:** Requires refactoring morphology calculation order

---

**Option 3: Make dysfunction score time-independent**
```python
# Compute dysfunction from dose and morphology EC50 (not actual morphology)
# This is still better than dose-only proxy because it uses morphology EC50
dys_from_dose = dose_uM / (dose_uM + morph_ec50)
```

**Pros:** Simple, no state needed
**Cons:** Back to using dose as proxy (defeats the purpose)

---

## Recommendation

**Use Option 2:** Compute dysfunction before applying viability factor.

**Rationale:**
- Conceptually correct: Transport dysfunction is structural (cytoskeleton broken)
- Viability factor represents "dead cells have low signal" not "dead cells have intact cytoskeleton"
- Breaks feedback loop without requiring state threading

**Implementation:**
```python
# 1. Calculate morphology with penalties
morph = apply_stress_axis_effects(...)
morph = apply_microtubule_penalties(...)

# 2. Compute dysfunction BEFORE viability factor
transport_dysfunction_score = compute_disruption(morph, base)

# 3. THEN apply viability factor (for signal loss, not structure)
morph *= viability_factor
```

---

## Test Results Summary

### High Dose (10 µM): ✓ Death arc works
```
12h:  98.7% viability, 28% disruption
72h:  71.8% viability, 33% disruption
96h:  0% viability, 41% disruption
```

### Low Dose (0.3 µM): ✗ Still dies at 96h
```
24h: 98.2% viability, 31% disruption
96h: 0% viability, 42% disruption (accumulates!)
```

**Problem:** Even low doses cause death because disruption accumulates.

---

## Next Actions

1. **Fix morphology accumulation bug** (Option 2: compute dysfunction before viability factor)
2. **Re-test low doses** to verify ceiling mechanism works
3. **Add recovery dynamics** (optional): If disruption <25%, slowly reduce attrition over time
4. **Move parameters to YAML:** Extract morphology EC50 fractions, attrition scales

---

## Files Modified

**Logic:**
- `standalone_cell_thalamus.py` (lines 785-795, 937-953): Real morphology feedback + quadratic ceiling

**Tests:**
- `test_low_dose_recovery.py`: Low dose survival test (reveals accumulation bug)
- `debug_morphology_accumulation.py`: Debug script showing 31% → 42% growth

**Tables:**
- `generate_comprehensive_table.py`: Fixed seeding, agent creation, added LDH comments

---

## Status

✅ **Completed:**
- Real morphology disruption (no dose proxy)
- Nonlinear attrition ceiling (dys^2)
- Fixed hidden EC50 coupling
- Fixed comprehensive table seeding/statefulness

⚠️ **Bug Found:**
- Morphology accumulation over time (feedback loop via viability factor)
- Causes low doses to kill inevitably

🔧 **Next Fix:**
- Compute dysfunction before viability factor (breaks feedback loop)
