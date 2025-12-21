# Temporal Causality Enforcement

**Status**: Complete
**Date**: 2025-12-21

## Mission

Make temporal causality non-negotiable: no observation may occur before its causal treatment.

## The Contract

### 1. Temporal Semantics (Explicit, Not Implicit)

**`observation_time_h`**
- Represents hours since universal time origin (t=0)
- This is WHEN the assay readout is captured (point measurement)
- Must be >= 0 (no negative time)
- Example: `observation_time_h=24.0` means "measure at 24 hours after experiment start"

**`treatment_start_time_h`**
- Hours since universal time origin (t=0) when treatment is applied
- This is the causal anchor - effects cannot precede this moment
- Defaults to 0.0 (treatment at experiment start)
- Must be >= 0 (no time travel)
- Example: `treatment_start_time_h=0.0` means "add compound at experiment start"

**Causality Invariant**
```
observation_time_h >= treatment_start_time_h
```

This ensures observations cannot report on treatments that haven't happened yet.

### 2. Example Scenarios

**Standard 24h experiment:**
```python
Well(
    cell_line="A549",
    treatment=Treatment(compound="staurosporine", dose_uM=0.1),
    observation_time_h=24.0,  # Observe at 24h
    treatment_start_time_h=0.0,  # Treat at t=0 (default)
)
# Valid: 24.0 >= 0.0 ✓
```

**Delayed treatment:**
```python
Well(
    cell_line="A549",
    treatment=Treatment(compound="tunicamycin", dose_uM=1.0),
    observation_time_h=48.0,  # Observe at 48h
    treatment_start_time_h=24.0,  # Treat at 24h
)
# Valid: 48.0 >= 24.0 ✓
# Duration: 24 hours after treatment
```

**INVALID - Observation before treatment:**
```python
Well(
    cell_line="A549",
    treatment=Treatment(compound="compound", dose_uM=1.0),
    observation_time_h=10.0,
    treatment_start_time_h=24.0,  # Treatment AFTER observation
)
# REJECTED: TemporalCausalityError
# 10.0 < 24.0 ✗ (causality violation)
```

## Implementation

### 1. Core Module: `temporal_causality.py`

Location: `src/cell_os/core/temporal_causality.py`

**New Exception Type:**
```python
class TemporalCausalityError(Exception):
    """Raised when temporal causality is violated."""
```

**Validation Functions:**
- `validate_well_temporal_causality(well)` - Validates Well construction
- `validate_raw_well_result_temporal_causality(result)` - Validates observation results

### 2. Schema Changes

**`Well` (src/cell_os/core/experiment.py):**
- Added field: `treatment_start_time_h: float = 0.0`
- Added `__post_init__` validation (calls `validate_well_temporal_causality`)
- Updated docstring with explicit temporal semantics
- Updated `fingerprint_inputs()` and `to_dict()` to include new field

**`RawWellResult` (src/cell_os/core/observation.py):**
- Added `__post_init__` validation (calls `validate_raw_well_result_temporal_causality`)
- Updated docstring with temporal invariants

### 3. Enforcement Points

Validation happens at **three layers**:

1. **Well construction** - Fail fast on invalid specs
2. **RawWellResult creation** - Guard observation generation
3. **Legacy adapters** - Cannot bypass validation (goes through Well.__post_init__)

All violations raise `TemporalCausalityError` with diagnostic context:
- Which field(s) are invalid
- Actual time values
- Treatment compound (for debugging context)

**No warnings. No silent corrections. Fail hard.**

### 4. Legacy Adapter Compatibility

Legacy adapters (`well_spec_to_well`, `well_assignment_to_well`) automatically:
- Map old `time_h` → new `observation_time_h`
- Use default `treatment_start_time_h=0.0`
- **Cannot bypass validation** (Well.__post_init__ always runs)

## Test Coverage

### 1. Rejection Tests (`test_temporal_causality_enforcement.py`)

Tests that INVALID cases are rejected:
- ✓ Negative observation time (`observation_time_h=-1.0`)
- ✓ Negative treatment start time (`treatment_start_time_h=-5.0`)
- ✓ Observation before treatment (causality paradox)
- ✓ Tiny violations (no epsilon tolerance)
- ✓ Legacy adapters cannot bypass validation
- ✓ RawWellResult rejects invalid times

### 2. Acceptance Tests (`test_temporal_causality_enforcement.py`)

Tests that VALID cases are accepted:
- ✓ Zero observation time (boundary case)
- ✓ Observation equals treatment start (boundary case)
- ✓ Observation after treatment (normal case)
- ✓ Default treatment_start_time_h=0.0

### 3. End-to-End Tests (`test_temporal_causality_e2e.py`)

Tests that valid experiments still work:
- ✓ Normal 24h experiment (treatment at t=0, observe at t=24h)
- ✓ Delayed treatment (treatment at t=24h, observe at t=48h)
- ✓ Immediate observation (treatment and observation both at t=0)
- ✓ Multi-well experiments with different timepoints
- ✓ Default treatment start time

### 4. Error Message Quality

All errors include:
- ✓ Observation time value
- ✓ Treatment start time value (for causality violations)
- ✓ Treatment compound (for context)

## Results

### All Tests Pass

```
Temporal Causality Enforcement Tests: 19/19 passed
End-to-End Tests: 5/5 passed
Existing Time Semantics Tests: All passed
Existing Experiment Semantics Tests: All passed
```

### Success Criterion Met

After this work, it is **impossible** for the system to produce an observation that implies an effect before its cause.

If a future developer tries to create:
- An observation with negative time
- An observation before its treatment

The system will **stop them with TemporalCausalityError**.

## What Changed

### Files Created
1. `src/cell_os/core/temporal_causality.py` - Core validation logic
2. `tests/unit/test_temporal_causality_enforcement.py` - Rejection/acceptance tests
3. `tests/unit/test_temporal_causality_e2e.py` - End-to-end validation tests
4. `docs/TEMPORAL_CAUSALITY_ENFORCEMENT.md` - This document

### Files Modified
1. `src/cell_os/core/experiment.py`
   - Added `treatment_start_time_h` field to `Well`
   - Added `__post_init__` validation to `Well`
   - Updated docstrings with explicit temporal semantics
   - Updated serialization methods

2. `src/cell_os/core/observation.py`
   - Added `__post_init__` validation to `RawWellResult`
   - Updated docstrings with temporal invariants

3. `tests/unit/test_time_semantics.py`
   - Updated test to check for new time semantics

## Non-Goals (What We Did NOT Do)

- Did NOT redesign the simulator
- Did NOT improve biological realism
- Did NOT add new assays
- Did NOT add observation windows (future work)
- Did NOT weaken validation to warnings

This agent existed to **remove ambiguity**, not add flexibility.

## Future Work (Out of Scope)

If observation windows are needed in the future:
1. Add `observation_window_h: Optional[float]` to `Well`
2. Validate: `observation_time_h - observation_window_h >= treatment_start_time_h`
3. Document semantics: is observation_time_h the start, middle, or end of window?

## Architectural Notes

### Why `treatment_start_time_h` Defaults to 0.0

Most experiments add treatment at experiment start (t=0). Making this the default:
- Minimizes boilerplate in common case
- Maintains backward compatibility with existing code
- Still enforces causality (observation_time_h must still be >= 0.0)

### Why No "Warnings Mode"

Silent correctness bugs are worse than loud failures. By failing hard:
- Developers fix bugs immediately (no accumulation of technical debt)
- No silent data corruption
- Clear error messages point to exact problem
- Tests can verify that violations are actually caught

### Why Validation in `__post_init__`

Frozen dataclasses can't mutate after construction, but they CAN validate in `__post_init__`. This:
- Ensures validation always runs (can't forget to call validate())
- Fails at construction time (fail fast principle)
- Works with all code paths (including legacy adapters)
- Clear error location (stack trace points to Well() call)

## Verification

To verify the invariant is enforced, try:

```python
from cell_os.core.experiment import Well, Treatment
from cell_os.core.assay import AssayType
from cell_os.core.temporal_causality import TemporalCausalityError

# This should raise TemporalCausalityError:
try:
    Well(
        cell_line="A549",
        treatment=Treatment(compound="test", dose_uM=1.0),
        observation_time_h=10.0,
        treatment_start_time_h=20.0,  # Paradox!
        assay=AssayType.CELL_PAINTING,
    )
    print("BUG: Should have raised TemporalCausalityError!")
except TemporalCausalityError as e:
    print(f"✓ Correctly rejected: {e}")
```

Expected output:
```
✓ Correctly rejected: Observation cannot occur before treatment.
Got observation_time_h=10.000h < treatment_start_time_h=20.000h
for well with treatment=test
```

## Summary

Temporal causality is now a **hard invariant**:
- Encoded in types (treatment_start_time_h field)
- Validated at runtime (Well.__post_init__)
- Documented explicitly (docstrings + this doc)
- Test-enforced (19 rejection tests + 5 e2e tests)

No observation can occur before its cause. The system will stop you.

That's the bar. ✓
