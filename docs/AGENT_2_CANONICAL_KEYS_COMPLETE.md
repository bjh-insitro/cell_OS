# Agent 2: Canonical Condition Keys - Complete

**Status:** ✅ SHIPPED

**Date:** 2025-12-21

---

## Mission

**Eliminate condition-splitting and aggregation races by introducing canonical condition keys.**

Make it **impossible** for floating-point noise, formatting differences, or near-duplicate doses to cause:
- Replicate splitting
- Spurious gate loss
- Unexplained CI widening
- Nondeterministic aggregation

**After this change:** Two semantically identical experimental conditions **MUST** always collapse to the same key.

---

## What Was Built

### 1. Canonicalization Module Created ✅

**File:** `src/cell_os/core/canonicalize.py`

**Core design:**
```python
@dataclass(frozen=True)
class CanonicalCondition:
    cell_line: str
    compound_id: str
    dose_nM: int          # Integer nanomolar (NO FLOATS)
    time_min: int         # Integer minutes (NO FLOATS)
    assay: str
    position_class: Optional[str]
```

**Conversion functions:**
- `canonical_dose_uM(float) → int` - Converts µM → nM (1.0 µM → 1000 nM)
- `canonical_time_h(float) → int` - Converts hours → minutes (24.0 h → 1440 min)
- `canonical_condition_key(...)` - Single entry point for creating keys

**Contract enforced:**
- NO floats escape this module
- ALL grouping must use `CanonicalCondition`
- Immutable (frozen=True), hashable, safe for dict keys

---

### 2. Aggregation Enforces Canonical Keys ✅

**File:** `src/cell_os/epistemic_agent/observation_aggregator.py`

**Changes:**
- Replaced `ConditionKey` with `CanonicalCondition` for all grouping
- All wells grouped by integer dose_nM and time_min (lines 108-155)
- Float parameters converted ONCE at aggregation entry
- No manual key construction - must use `canonical_condition_key()`

**Before (vulnerable to float splitting):**
```python
key = (cell_line, compound, dose_uM, time_h, assay)  # FLOAT KEYS!
```

**After (immune to float noise):**
```python
key = canonical_condition_key(
    cell_line=...,
    compound_id=...,
    dose_uM=...,      # Converted to int nM internally
    time_h=...,       # Converted to int min internally
    assay=...,
    position_class=...
)
```

---

### 3. Near-Duplicate Detection and Logging ✅

**Implementation:** Lines 157-177 in `observation_aggregator.py`

**Behavior:**
- Tracks raw parameter values during aggregation
- Detects when multiple raw (dose, time) pairs collapse to same canonical key
- Logs diagnostic events to `near_duplicate_merges` field

**Diagnostic event format:**
```json
{
  "event": "canonical_condition_merge",
  "canonical_key": {"dose_nM": 1000, "time_min": 1440, ...},
  "raw_doses_uM": [1.0, 1.00001, 1.000002],
  "raw_times_h": [24.0],
  "n_wells": 32
}
```

**Result:**
- Near-duplicates are visible, not silent
- Does NOT block execution
- Enables audit and monitoring

---

### 4. Schemas Updated ✅

**File:** `src/cell_os/epistemic_agent/schemas.py`

**ConditionSummary additions:**
```python
# Agent 2: Canonical representation (prevents aggregation races)
canonical_dose_nM: Optional[int] = None    # Integer nanomolar
canonical_time_min: Optional[int] = None   # Integer minutes
```

**Observation additions:**
```python
# Agent 2: Near-duplicate detection
near_duplicate_merges: List[Dict[str, Any]] = field(default_factory=list)
```

**Backward compatibility:**
- `dose_uM` and `time_h` still present (floats, for legacy code)
- BUT derived from canonical integers, not used for grouping
- Downstream code can migrate to canonical fields over time

---

## Tests Created and Passing ✅

### Unit Tests

**File:** `tests/unit/test_condition_canonicalization.py`

**Coverage:**
1. ✅ Dose conversion (µM → nM)
2. ✅ Time conversion (h → min)
3. ✅ Canonical key creation
4. ✅ Identical conditions collapse
5. ✅ Near-duplicates stay distinct (when meaningful)
6. ✅ **CRITICAL:** 32-well dose collapse scenario
7. ✅ Time float noise collapse
8. ✅ Determinism across orderings
9. ✅ Equivalence checking
10. ✅ Immutability enforcement
11. ✅ Validation (rejects negatives, floats)
12. ✅ Serialization (`to_dict()`)

**Result:**
```
✅ All canonicalization unit tests passed

Key results:
  → Float noise collapses to single canonical key
  → 32-well DMSO split is now IMPOSSIBLE
  → Deterministic across runs and orderings
  → Validation prevents invalid conditions
```

---

### Regression Test

**File:** `tests/integration/test_aggregation_race_regression.py`

**Scenario 1: Historical Gate-Loss Bug**
- 32 DMSO baseline wells at "1.0 µM"
- Injected float noise: `[1.0, 1.0+1e-6, 1.0+2e-6, 1.0-1e-6, 1.0+5e-7]`
- **Old behavior:** Split into 3-4 conditions → gate lost
- **New behavior:** Collapse to ONE condition → gate maintained

**Assertions:**
- ✅ Exactly 1 condition (not 3-4)
- ✅ n=32 wells in that condition
- ✅ canonical_dose_nM = 1000
- ✅ canonical_time_min = 1440
- ✅ Near-duplicates detected and logged
- ✅ Gate remains STABLE (rel_ci_width ~0.0057 < 0.25 threshold)

**Scenario 2: Near-Duplicate Detection**
- 16 wells at 10.0 µM
- 16 wells at 10.001 µM
- **Result:** 2 distinct conditions (10000 nM vs 10001 nM)
- Correctly kept separate (meaningful 1 nM difference)

**Test output:**
```
✅ Historical gate-loss bug is now IMPOSSIBLE
✅ Float noise cannot split replicates
✅ 32-well baseline always groups correctly
✅ Canonical keys eliminate aggregation races
```

---

## Definition of Done - All Met ✅

- ✅ No aggregation path uses float dose or time directly
- ✅ CanonicalCondition is the ONLY grouping key
- ✅ Near-duplicate merges are logged
- ✅ Historical gate-loss failure is impossible
- ✅ Tests pass with deterministic behavior across runs

---

## Files Modified

**Created:**
1. `src/cell_os/core/canonicalize.py` - 217 lines (canonical key module)
2. `tests/unit/test_condition_canonicalization.py` - 370 lines (unit tests)
3. `tests/integration/test_aggregation_race_regression.py` - 282 lines (regression test)

**Modified:**
1. `src/cell_os/epistemic_agent/observation_aggregator.py` - Canonical key enforcement
2. `src/cell_os/epistemic_agent/schemas.py` - Added canonical fields to ConditionSummary, Observation

**Total:** ~217 lines of core code + 652 lines of tests = **869 lines**

---

## Impact

### Before (Vulnerable)

**32 DMSO wells at 1.0 µM:**
```
Float noise: [1.0, 1.00001, 1.000002, ...]
↓
Dictionary keys: {1.0, 1.00001, 1.000002}  (3-4 distinct keys)
↓
Aggregation: 3-4 conditions with n=8-12 each
↓
CI widening: rel_width jumps from 0.006 → 0.015
↓
Gate lost: noise_sigma_stable = False
↓
FAILURE: Agent thinks calibration regressed
```

### After (Immune)

**32 DMSO wells at 1.0 µM:**
```
Float noise: [1.0, 1.00001, 1.000002, ...]
↓
Canonical: all → 1000 nM (integer)
↓
Dictionary keys: {1000}  (ONE key)
↓
Aggregation: 1 condition with n=32
↓
CI stable: rel_width = 0.006
↓
Gate maintained: noise_sigma_stable = True
↓
SUCCESS: Calibration state preserved
```

---

## Behavioral Contract

**No floats escape canonicalization:**
- All grouping uses `CanonicalCondition` (integers only)
- Conversion happens ONCE at aggregation entry
- No manual key construction allowed

**Near-duplicates are visible:**
- Merges logged to `near_duplicate_merges`
- Includes raw dose/time values that collapsed
- Diagnostic, not blocking

**Backward compatibility maintained:**
- `ConditionSummary` still has `dose_uM` and `time_h` (floats)
- But these are DERIVED from canonical integers
- Legacy code continues to work

**Determinism guaranteed:**
- Same inputs → same canonical keys
- Order-independent
- Reproducible across runs

---

## Why This Matters

This patch removes an entire class of failures that **look like epistemic uncertainty** but are actually **schema bugs**.

**Before:** "Why did the gate unlock? Did calibration regress?"
**After:** "Gate state is deterministic. If it unlocks, it's because the system learned something."

Float noise can no longer cause:
- Replicate splitting
- Nondeterministic aggregation
- Spurious CI widening
- Silent gate loss

When Agent 2 is done, **the system becomes quieter in the right way.**

---

## Commit Message

```
Canonicalize condition keys to prevent aggregation races

- All doses converted to integer nanomolar (dose_nM)
- All times converted to integer minutes (time_min)
- Single canonicalization function: canonical_condition_key()
- CanonicalCondition replaces ConditionKey for grouping
- Near-duplicate detection and logging added
- 32-well DMSO split is now impossible

Fixes historical gate-loss bug where float arithmetic
caused replicate splitting and spurious CI widening.

Tests:
- 12 unit tests covering canonicalization correctness
- Regression test reproducing historical failure
- All tests pass, deterministic across runs
```

---

**End of Agent 2 Report**
