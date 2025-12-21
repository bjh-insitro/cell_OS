# Confluence Confounding Validator: Density-Matched Design Enforcement

**Date**: 2025-12-20
**Status**: ✅ FULLY INTEGRATED - Design-time guardrail active in bridge layer

---

## Problem Statement

Now that confluence is a **real confounder** in the simulator (systematic measurement bias in both morphology and transcriptomics), the planner must be prevented from proposing designs that rely on confounded density comparisons.

**Without this constraint**, the agent could:
- Compare high-growth vs low-growth conditions at the same timepoint
- Attribute density-driven measurement shifts to compound mechanism
- Learn brittle hacks instead of proper experimental design

**Key insight**: Making the world harder is not enough. You must also **force the planner to respect that hardness**.

---

## Solution: Design-Time Policy Guard

Added a **validator method** that enforces density-matched design as a scientific constraint.

### Location

`src/cell_os/simulation/design_validation.py:ExperimentalDesignValidator`

### New Methods

1. **`_predict_contact_pressure()`** (lines 368-422)
   - Lightweight heuristic model (NOT full simulation)
   - Uses cell-line-specific defaults (seeding fraction, growth rate)
   - Applies conservative dose penalty to catch confounding
   - Same sigmoid as simulator: c0=0.75, width=0.08

2. **`validate_proposal_for_confluence_confounding()`** (lines 424-540)
   - Groups wells by readout context: `(cell_line, time_h, assay)`
   - Predicts pressure for each well at readout time
   - Compares across conditions within each group
   - Rejects if `delta_p > threshold` (default 0.15)

---

## Contract

### What Gets Validated

**Comparison groups**: Wells that share `(cell_line, time_h, assay)` are assumed to be compared against each other.

**Conditions**: Unique `(compound, dose_uM)` pairs within a comparison group.

**Confounding check**: If max(pressure) - min(pressure) > 0.15 across conditions, reject.

### Three Resolution Strategies

When a design is rejected, the error provides three paths to resolve:

1. **Add density sentinel arm** (escape hatch, implemented now)
   - Include a well with `compound="DENSITY_SENTINEL"` in the confounded group
   - Validator skips groups containing sentinels
   - Signals explicit acknowledgment of density confounding

2. **Per-arm seeding density** (future, requires schema upgrade)
   - Add `initial_cell_count` field to well spec
   - Allow agent to density-match arms by adjusting seeding

3. **Explicit covariate** (future, requires inference upgrade)
   - Mark `contact_pressure` as a covariate in design metadata
   - Posterior inference subtracts density effect from mechanism

---

## Pressure Prediction Model

### Cell Line Defaults

```python
defaults = {
    "A549":  {"seed_frac": 0.20, "growth_rate_h": 0.035},  # ~20h doubling
    "HepG2": {"seed_frac": 0.25, "growth_rate_h": 0.025},  # ~28h doubling
    "U2OS":  {"seed_frac": 0.18, "growth_rate_h": 0.030},  # ~23h doubling
    "293T":  {"seed_frac": 0.15, "growth_rate_h": 0.040},  # ~17h doubling
}
```

### Dose Effect (Conservative)

Assumes compounds slow growth unless marked as vehicle:

```python
dose_penalty = 0.0
if dose_uM > 0 and compound.lower() not in ("dmso", "vehicle", "control", "pbs"):
    dose_penalty = min(0.6, 0.08 * log10(dose_uM + 1.0))  # Bounded logarithmic

growth_rate_effective = growth_rate * (1.0 - dose_penalty)
```

### Pressure Calculation

```python
confluence = seed_frac * exp(growth_rate_effective * time_h)
confluence = min(1.2, max(0.0, confluence))  # Cap at 120%

# Same sigmoid as simulator
c0, width = 0.75, 0.08
x = (confluence - c0) / width
pressure = 1.0 / (1.0 + exp(-x))
```

---

## Test Results

All 5 tests pass (`tests/unit/test_confluence_confounding_validator.py`):

### Test 1: Reject Confounded Design ✅

**Setup**:
- Control: DMSO @ 0 µM, 48h
- Treatment: ToxicCompound @ 10000 µM, 48h
- Same cell line, same timepoint, same assay

**Result**:
```
Δp = 0.806 > 0.15
Highest pressure: DMSO @ 0 µM (p=0.983)
Lowest pressure: ToxicCompound @ 10000 µM (p=0.177)
```

**Verdict**: REJECTED with structured error details

### Test 2: Accept With Density Sentinel ✅

**Setup**: Same as Test 1, but includes `compound="DENSITY_SENTINEL"` well

**Result**: ACCEPTED (escape hatch)

### Test 3: Threshold Boundary ✅

**Setup**:
- Control: DMSO @ 0 µM, 24h
- Treatment: ToxicCompound @ 100 µM, 24h
- Δp = ~0.05 < 0.15

**Result**: ACCEPTED (below threshold)

### Test 4: Single Condition No Validation ✅

**Setup**: All wells have same condition (no comparison)

**Result**: ACCEPTED (nothing to compare)

### Test 5: Independent Readout Groups ✅

**Setup**:
- Group 1: A549 @ 48h (confounded, Δp > 0.15)
- Group 2: HepG2 @ 24h (not confounded)

**Result**: REJECTED (Group 1 caught, Group 2 ignored)

---

## Error Structure

When a design is rejected, a `ValueError` is raised with a structured dict:

```python
{
    "message": "Design likely confounded by confluence...",
    "violation_code": "confluence_confounding",
    "design_id": "...",
    "threshold": 0.15,
    "delta_p": 0.806,
    "cell_line": "A549",
    "time_h": 48.0,
    "assay": "cell_painting",
    "highest_pressure": {
        "p": 0.983,
        "compound": "DMSO",
        "dose_uM": 0.0
    },
    "lowest_pressure": {
        "p": 0.177,
        "compound": "ToxicCompound",
        "dose_uM": 10000.0
    },
    "resolution_strategies": [
        "Add density sentinel arm: compound='DENSITY_SENTINEL'...",
        "Add schema support for per-arm seeding density...",
        "Mark contact_pressure as explicit covariate..."
    ]
}
```

**Bridge layer** can catch this and convert to `InvalidDesignError` with structured refusal receipt.

---

## Integration with Design Bridge

### ✅ Integration Complete

The validator is **fully integrated** into `epistemic_agent/design_bridge.py` (lines 233-269).

The bridge now:
1. Converts design wells to validator format (`timepoint_h` → `time_h`, `_assay` → `assay`)
2. Calls `validate_proposal_for_confluence_confounding()` after structural checks
3. Catches `ValueError` with structured dict
4. Converts to `InvalidDesignError` with proper violation_code and details
5. Preserves resolution strategies in error details

**Test coverage**: `tests/phase6a/test_bridge_confluence_validator.py` (3/3 tests passing)
- Rejects confounded design (Δp = 0.806 > 0.15)
- Accepts sentinel design (escape hatch)
- Accepts density-matched design (Δp < 0.15)

---

## Philosophical Note: This Is a Policy Guard, Not Truth

The pressure prediction model uses **conservative heuristics**, not full simulation:

- Nominal seeding fractions (not agent-specified)
- Crude dose penalties (not full mechanism models)
- No nutrient depletion, no death, no stochasticity

**This is intentional**. The goal is:

✅ **Catch obvious confounding patterns** (e.g., 48h vehicle vs 48h toxic compound)
✅ **Prevent brittle comparisons** (force density-matching or explicit acknowledgment)
✅ **Err on the side of rejection** (conservative: over-estimate pressure differences)

❌ **NOT to predict exact final pressures** (that requires full simulation)
❌ **NOT to be user-tunable per design** (that would allow gaming the validator)

If the agent wants precise control, it must:
1. Use density sentinel arms
2. Request schema upgrades for per-arm seeding
3. Explicitly model pressure as a covariate

---

## Next Steps

### ✅ Completed (Bridge Integration)

1. ✅ Called `validate_proposal_for_confluence_confounding()` in design_bridge.py:validate_design()
2. ✅ Converted `ValueError` to `InvalidDesignError` with structured details
3. ✅ Tested end-to-end: bridge rejects confounded designs, accepts sentinel/matched designs

### Near-Term (Schema Upgrades)

1. Add `initial_cell_count` field to WellSpec
2. Allow agent to specify per-arm seeding density
3. Update validator to use agent-specified seeding when present

### Long-Term (Posterior Modeling)

1. Add `covariates: List[str]` field to Proposal metadata
2. Teach posterior to subtract density effects when `"contact_pressure"` in covariates
3. Agent learns to explicitly model confounders instead of avoiding them

---

**Last Updated**: 2025-12-20
**Test Status**: ✅ 8/8 tests passing (5 validator + 3 bridge)
**Integration Status**: ✅ COMPLETE - Active in bridge layer (design_bridge.py:233-269)
