# Canonical Conditions: The Rules

**Last updated:** 2025-12-21
**Module:** `src/cell_os/core/canonicalize.py`

---

## Purpose

Prevent aggregation races where float noise splits replicates into separate conditions.

**Before canonical keys:**
- 32 DMSO wells at "1.0 µM"
- Float arithmetic creates [1.0, 1.00001, 1.000002, ...]
- Wells split into 3-4 conditions → gate loss

**After canonical keys:**
- All collapse to 1000 nM (integer)
- Single condition, n=32
- Gate maintained

---

## Identity Rules

### Condition identity uses **integers only**

- **Dose:** Integer nanomolar (`dose_nM: int`)
- **Time:** Integer minutes (`time_min: int`)
- **Never:** Floats in condition keys

### Resolution constants

```python
DOSE_RESOLUTION_NM = 1   # 1 nanomolar = 0.001 µM
TIME_RESOLUTION_MIN = 1  # 1 minute
```

Defined in: `src/cell_os/core/canonicalize.py`

---

## Rounding Semantics

Uses **Python's `round()`** (banker's rounding / round-half-to-even):

- 0.5 → 0 (rounds to even)
- 1.5 → 2 (rounds to even)
- 2.5 → 2 (rounds to even)

**Deterministic across:**
- Platforms
- Python versions
- Run orders

**If you need round-half-up instead:** Use `Decimal.quantize()`

---

## Conversion Examples

### Dose (µM → nM)

```python
canonical_dose_uM(1.000)    → 1000 nM
canonical_dose_uM(1.001)    → 1001 nM  (distinct)
canonical_dose_uM(1.0005)   → 1000 nM  (banker's rounding)
canonical_dose_uM(1.0015)   → 1002 nM  (banker's rounding)
canonical_dose_uM(0.0)      → 0 nM
```

### Time (hours → minutes)

```python
canonical_time_h(24.0)     → 1440 min
canonical_time_h(24.01)    → 1441 min  (distinct)
canonical_time_h(12.0)     → 720 min
canonical_time_h(0.00833)  → 0 min  (30 seconds, rounds down)
```

---

## What Counts as a Merge

Two raw conditions collapse to **same canonical key** when:

- `|dose1_nM - dose2_nM| < DOSE_RESOLUTION_NM`
- `|time1_min - time2_min| < TIME_RESOLUTION_MIN`
- Same compound, cell line, assay, position

**Example merge:**
- Well 1: dose=1.00000 µM → 1000 nM
- Well 2: dose=1.00001 µM → 1000 nM
- **Result:** Both collapse to same condition

**Not a merge:**
- Well 1: dose=1.000 µM → 1000 nM
- Well 2: dose=1.001 µM → 1001 nM
- **Result:** Two distinct conditions (1 nM difference is meaningful)

---

## Diagnostics

### When merges occur

Logged to `Observation.near_duplicate_merges`:

```json
{
  "event": "canonical_condition_merge",
  "canonical_key": {"dose_nM": 1000, "time_min": 1440, ...},
  "raw_doses_uM": [1.0, 1.00001, 1.000002],
  "raw_times_h": [24.0],
  "n_wells": 32
}
```

**Not an error.** This is visibility into rounding effects.

### Validation errors

Rejected inputs (raises `ValueError`):

- Negative dose or time
- NaN, Inf
- Non-finite values

---

## Changing Resolution Safely

**If you need coarser resolution:**

1. Update constants:
   ```python
   DOSE_RESOLUTION_NM = 10   # 10 nM = 0.01 µM
   TIME_RESOLUTION_MIN = 5   # 5 minutes
   ```

2. Update tests in `tests/unit/test_condition_canonicalization.py`

3. Run full test suite (aggregation races must remain impossible)

4. Document why change was needed

**Warning:** Changing resolution invalidates historical fingerprints.

---

## Usage

### Creating canonical keys

```python
from cell_os.core.canonicalize import canonical_condition_key

key = canonical_condition_key(
    cell_line="A549",
    compound="bortezomib",
    dose_uM=1.0,        # Float input
    observation_time_h=24.0,
    assay="cell_painting",
    position_class="center"
)
# Returns: CanonicalCondition(dose_nM=1000, time_min=1440, ...)
```

### Grouping wells

```python
from collections import defaultdict

conditions = defaultdict(list)
for well in raw_wells:
    key = canonical_condition_key(...)
    conditions[key].append(well)  # Safe: key is hashable, immutable
```

---

## What This Prevents

❌ **Eliminated:**
- Replicate splitting from float noise
- Nondeterministic aggregation
- Spurious gate loss from CI widening
- "Phantom" calibration regressions

✅ **Guaranteed:**
- Same input → same canonical key
- Deterministic across runs
- Float-immune identity
- Visible merges (diagnostic, not silent)

---

## Tests

**Location:** `tests/unit/test_condition_canonicalization.py`

**Coverage:**
- Float noise collapse (32-well DMSO scenario)
- Banker's rounding behavior
- Validation (negative, NaN, inf rejected)
- Determinism across orderings
- Resolution constants in use

**All tests must pass before deploying.**

---

## Summary

**Rule 1:** Condition identity = integers (dose_nM, time_min)
**Rule 2:** Resolution = 1 nM, 1 minute
**Rule 3:** Rounding = banker's (round-half-to-even)
**Rule 4:** Merges are logged, not hidden
**Rule 5:** Invalid inputs fail loudly

**Result:** Aggregation races structurally impossible.
