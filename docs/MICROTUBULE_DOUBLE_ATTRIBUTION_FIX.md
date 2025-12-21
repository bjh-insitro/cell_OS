# Critical Fix: Microtubule Double Attribution (Phase 3 Adversarial Testing)

**Date**: 2025-12-20
**Status**: ✅ FIXED - All tests passing (29/29 enforcement assertions)

---

## The Bug

User identified in adversarial testing mode: **Microtubule death was being double-attributed**.

For microtubule compounds (e.g., nocodazole) on dividing cells (e.g., A549):
- `death_compound` was credited from attrition (base rate 0.05)
- `death_mitotic_catastrophe` was credited from mitotic failure
- **Result**: Same death counted twice in different ledgers

This violates the conservation law principle that death causes should be mutually exclusive.

---

## User's Diagnosis

> "You have two parallel 'explanations' for microtubule death [...] If your `biology_core.compute_attrition_rate` already bakes in a microtubule axis lethality component, then you are double-charging microtubule death: once as mitotic, once as compound."

**Recommended fix (Option A)**:
> "For `stress_axis == 'microtubule'`, make `compute_attrition_rate` return a 'non-mitotic baseline' only, and leave division-linked death to mitotic catastrophe."

---

## The Fix (Three Parts)

### Fix 1: Attrition Returns 0.0 for Microtubule + Dividing Cells

**File**: `src/cell_os/sim/biology_core.py` (lines 363-393)

**Before**:
```python
base_attrition_rates = {
    'microtubule': 0.05,    # Weak (rapid commitment for cancer cells)
}

# All cell lines got microtubule attrition
if stress_axis == 'microtubule' and cell_line == 'iPSC_NGN2':
    base_mt_attrition = 0.25  # Higher for neurons
    # ... scaling logic
else:
    attrition_rate_base = base_attrition_rates.get(stress_axis, 0.10)
```

**After**:
```python
base_attrition_rates = {
    # 'microtubule' NOT in this dict - handled explicitly below
}

# Microtubule-specific logic
if stress_axis == 'microtubule':
    if cell_line == 'iPSC_NGN2':
        # Neurons: non-dividing, die from axonal transport collapse
        base_mt_attrition = 0.25  # Transport collapse death
        # ... scaling logic
    else:
        # Dividing cells (A549, HepG2, etc.): mitotic catastrophe ONLY
        return 0.0  # No attrition - prevents double-attribution
else:
    attrition_rate_base = base_attrition_rates.get(stress_axis, 0.10)
```

**Contract**: For dividing cells + microtubule drugs, attrition returns 0.0. Mitotic catastrophe is the ONLY source of microtubule death attribution.

---

### Fix 2: Mitotic Catastrophe Skips Non-Dividing Cells

**File**: `src/cell_os/hardware/biological_virtual.py` (lines 924-928)

**Added check**:
```python
# Skip non-dividing cells (neurons, post-mitotic cells)
prolif_index = biology_core.PROLIF_INDEX.get(vessel.cell_line, 1.0)
if prolif_index < 0.3:  # Threshold: below 0.3 = post-mitotic
    return
```

**Contract**: Neurons (iPSC_NGN2, prolif_index=0.1) never get mitotic catastrophe. They die from transport collapse (credited to `death_compound`).

---

### Fix 3: Instant Kill Attribution Based on Cell Division Status

**File**: `src/cell_os/hardware/biological_virtual.py` (lines 2053-2065)

**Before**:
```python
# All instant kills credited to death_compound
self._apply_instant_kill(vessel, instant_death_fraction_applied, "death_compound")
```

**After**:
```python
# CRITICAL: For microtubule drugs on dividing cells, instant effect is division-linked
# Credit to death_mitotic_catastrophe (not death_compound) to avoid double-attribution
if stress_axis == 'microtubule':
    prolif_index = biology_core.PROLIF_INDEX.get(vessel.cell_line, 1.0)
    if prolif_index >= 0.3:  # Dividing cells
        death_field = "death_mitotic_catastrophe"
    else:
        death_field = "death_compound"  # Non-dividing (neurons) - transport collapse
else:
    death_field = "death_compound"  # All other stress axes

self._apply_instant_kill(vessel, instant_death_fraction_applied, death_field)
```

**Rationale**: For microtubule drugs on dividing cells, the instant effect represents cells that were already in mitosis when the drug hit. This is mitotic failure, not generic compound toxicity.

---

## Attribution Logic Summary

### Dividing Cells (A549, HepG2) + Microtubule Drugs

**Death sources**:
- Instant kill → `death_mitotic_catastrophe` (cells in mitosis at treatment time)
- Time-dependent mitotic catastrophe → `death_mitotic_catastrophe` (ongoing division failures)
- Attrition → **0.0** (returns early to prevent double-attribution)

**Result**: ALL microtubule death goes to `death_mitotic_catastrophe`. No double-attribution.

---

### Non-Dividing Cells (iPSC_NGN2) + Microtubule Drugs

**Death sources**:
- Instant kill → `death_compound` (acute transport collapse)
- Attrition → `death_compound` (time-dependent transport collapse, scaled by dysfunction)
- Mitotic catastrophe → **0.0** (skipped, neurons don't divide)

**Result**: ALL microtubule death goes to `death_compound`. No mitotic attribution for non-dividing cells.

---

### Other Stress Axes (All Cell Lines)

**Death sources**:
- Instant kill → `death_compound`
- Attrition → `death_compound` (or mechanism-specific: `death_er_stress`, `death_mito_dysfunction`)
- Mitotic catastrophe → **0.0** (only applies to microtubule axis)

**Result**: No change from before. Attribution works as expected.

---

## New Enforcement Test

**File**: `tests/phase6a/test_microtubule_no_double_attribution.py` (3 tests)

### Test 1: Dividing Cells - Only Mitotic Attribution

**Setup**:
- Seed A549 (cancer line, dividing)
- Treat with 0.5µM nocodazole (microtubule disruptor)
- Advance 48h

**Assertion**:
- `death_mitotic_catastrophe > 0.02` (significant mitotic death)
- `death_compound < 0.01` (near-zero compound attribution)

**Result**: ✅ PASS
- Before fix: `death_compound=0.5809`, `death_mitotic=0.2316` (double-attribution)
- After fix: `death_compound=0.0000`, `death_mitotic=0.8125` (exclusive)

---

### Test 2: Non-Dividing Cells - Only Transport Collapse Attribution

**Setup**:
- Seed iPSC_NGN2 (neurons, non-dividing)
- Treat with 1.0µM nocodazole
- Advance 48h

**Assertion**:
- `death_mitotic_catastrophe < 0.01` (near-zero, neurons don't divide)
- `death_compound` may be >0 (transport collapse)

**Result**: ✅ PASS
- Before fix: `death_mitotic=0.2100` (incorrect - neurons don't divide)
- After fix: `death_mitotic=0.0000`, `death_compound=0.2955` (correct)

---

### Test 3: Non-Microtubule Compounds - Normal Attribution

**Setup**:
- Seed A549
- Treat with 3.0µM tunicamycin (ER stress, NOT microtubule)
- Advance 48h

**Assertion**:
- `death_mitotic_catastrophe < 0.01` (not a microtubule drug)
- `death_compound > 0.01` OR `death_er_stress > 0.01`

**Result**: ✅ PASS (no regressions)

---

## Test Coverage Summary

| Test Suite | Assertions | Status |
|-----------|-----------|--------|
| **Phase 3 (New)** | | |
| Microtubule No Double Attribution | 3/3 | ✅ PASS |
| **Phase 2 (Critical Fixes)** | | |
| Treatment Causality | 3/3 | ✅ PASS |
| Nutrient Single Authority | 3/3 | ✅ PASS |
| **Phase 1 (Surgical Fixes)** | | |
| 48-Hour Story Spine Invariants | 6/6 | ✅ PASS |
| Interval Semantics | 3/3 | ✅ PASS |
| Instant Kill Guardrail | 3/3 | ✅ PASS |
| Evap Drift Affects Attrition | 2/2 | ✅ PASS |
| Scheduler Order Invariance | 3/3 | ✅ PASS |
| Scheduler No Concentration Mutation | 3/3 | ✅ PASS |
| **Total** | **29/29** | ✅ **ALL PASSING** |

---

## What This Proves

### 1. Exclusive Attribution for Microtubule Drugs

For dividing cells + microtubule drugs:
- Instant effect → `death_mitotic_catastrophe`
- Time-dependent mitotic failure → `death_mitotic_catastrophe`
- Attrition → 0.0 (skipped)

**Result**: One ledger, one explanation. No double-counting.

---

### 2. Cell Type Determines Mechanism

- **Dividing cells** (A549, HepG2): Mitotic catastrophe (division failure)
- **Non-dividing cells** (neurons): Transport collapse (axonal dysfunction)

Proliferation index (`biology_core.PROLIF_INDEX`) is the discriminator:
- `>= 0.3`: Dividing (mitotic catastrophe applies)
- `< 0.3`: Post-mitotic (mitotic catastrophe skipped)

---

### 3. Other Stress Axes Unaffected

ER stress, mitochondrial, oxidative stress, etc. continue to credit `death_compound` (or mechanism-specific fields) as before. No regressions.

---

## User's Validation Criteria

User asked: *"Do you want this simulator to be a **world** or a **belief generator**?"*

This fix reinforces the "world" interpretation:
- Death causes are **mutually exclusive** (competing risks, not additive)
- Attribution follows **biological mechanism** (division-linked vs transport-collapse)
- No "hedging" with multiple explanations for the same death

---

## Contracts Enforced

### 1. Exclusive Attribution
- For any compound + cell line pair, death is credited to EXACTLY ONE mechanism
- No double-counting of the same death event

### 2. Mechanism Follows Biology
- Dividing cells + microtubule drugs = mitotic catastrophe
- Non-dividing cells + microtubule drugs = transport collapse
- Other axes = compound toxicity (or mechanism-specific)

### 3. Proliferation Index is Authoritative
- Single source of truth for "does this cell line divide?"
- Threshold: `prolif_index < 0.3` = post-mitotic

---

## Files Modified

### Core Simulation Logic
**`src/cell_os/sim/biology_core.py`** (lines 363-393):
- Removed 'microtubule' from `base_attrition_rates` dict
- Added explicit check: if dividing cell + microtubule → return 0.0
- Neurons (iPSC_NGN2) still get transport-collapse attrition

### Simulator
**`src/cell_os/hardware/biological_virtual.py`**:
- Lines 924-928: Added proliferation index check in `_apply_mitotic_catastrophe` (skip non-dividing)
- Lines 2053-2065: Route instant kill to correct death field based on stress axis + proliferation

### New Test
**`tests/phase6a/test_microtubule_no_double_attribution.py`**:
- 3 tests verifying exclusive attribution
- Covers dividing cells, non-dividing cells, and non-microtubule axes

---

## User's Direct Challenge

> "Now for the part where I try to break it."

**Status**: User found the break. We fixed it. Attribution is now exclusive and biologically correct.

---

**Last Updated**: 2025-12-20
**Test Status**: ✅ 29/29 PASSING (Phase 1 + Phase 2 + Phase 3)
**Critical Fixes**: ✅ ALL COMPLETE

The simulator now refuses to double-attribute microtubule death.
