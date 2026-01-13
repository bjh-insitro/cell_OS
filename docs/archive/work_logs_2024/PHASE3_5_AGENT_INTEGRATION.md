# Phase 3.5: Agent Integration (Read-Only) - COMPLETE ✅

**Date:** 2025-12-27
**Status:** Calibration wired into agent (read-only, derived fields, no mutations)
**Integration:** Applied to `world.py:318-352` (morphology_corrected selection + metadata passthrough)

---

## What Was Built

### 1. CalibrationProfile (Read-Only Accessor)
**File:** `src/cell_os/calibration/profile.py`

**API:**
```python
profile = CalibrationProfile("calibration_report.json")

# Vignette correction
corrected = profile.correct_morphology(morphology, well_id)
multiplier = profile.vignette_multiplier_for_well(well_id, channel)

# Saturation awareness
safe_max = profile.safe_max(channel)
confidence = profile.saturation_confidence(channel)

# Exposure policy
exposure_mult, warnings = profile.exposure_policy(sample_class="bright")

# Quantization awareness
resolution = profile.effective_resolution(channel)
is_sig = profile.is_significant_difference(delta, channel, threshold_lsb=2.0)

# Floor status
floor_ok = profile.floor_observable()
reason = profile.floor_reason()

# Metadata stamping
metadata = profile.calibration_metadata()
```

**No side effects:** Pure functions, no config mutation, deterministic.

---

### 2. Apply Calibration Script
**File:** `src/cell_os/analysis/apply_calibration.py`

**CLI:**
```bash
python -m src.cell_os.analysis.apply_calibration \
  --obs results/cal_beads_dyes_seed42/observations.jsonl \
  --calibration results/cal_beads_dyes_seed42/calibration/calibration_report.json \
  --out results/cal_beads_dyes_seed42/observations_calibrated.jsonl
```

**Output:**
```
✓ Done! 384 observations calibrated

Summary:
  Vignette applied: 384/384
  Saturation warnings: 35
```

---

### 3. Observation Schema (Option 1: Derived Fields)

**Before calibration:**
```json
{
  "well_id": "A1",
  "morphology": {
    "er": 100.0,
    "mito": 100.0,
    ...
  }
}
```

**After calibration:**
```json
{
  "well_id": "A1",
  "morphology": {
    "er": 100.0,  // UNCHANGED (raw)
    "mito": 100.0,
    ...
  },
  "morphology_corrected": {
    "er": 114.8,  // Corrected (vignette-boosted for corner well)
    "mito": 114.2,
    ...
  },
  "calibration": {
    "schema_version": "bead_plate_calibration_report_v1",
    "report_created_utc": "2025-12-27T17:53:56Z",
    "vignette_applied": true,
    "saturation_policy": "avoid",
    "quantization_aware": true,
    "floor_observable": false,
    "applied": true,
    "saturation_warnings": [
      "er: 355.0 AU near safe max 325.4 AU (confidence: medium)"
    ]
  }
}
```

**Key properties:**
- ✅ Raw `morphology` unchanged (read-only)
- ✅ `morphology_corrected` as new derived field
- ✅ `calibration` metadata stamped
- ✅ Saturation warnings included when relevant

---

## Integration Tests (All Passing)

**File:** `tests/integration/test_apply_calibration_vignette.py`

```bash
$ pytest tests/integration/test_apply_calibration_vignette.py -xvs
PASSED (4/4 tests)

✓ Center well: 100.0 → 100.0 (unchanged)
✓ Corner well: 100.0 → 114.8 (boosted by 1.15x)
  Expected boost: 1.15x (edge_mult=0.871)

✓ Calibration metadata stamped
✓ Saturation warning triggered for high-intensity wells
✓ Quantization awareness: resolution=0.0131 AU
  Small delta (0.0197): not significant
  Large delta (0.0394): significant
```

---

## Agent Insertion Point

### Where Agent Reads Morphology

**File:** `src/cell_os/epistemic_agent/world.py`
**Function:** `execute_design_v2()`
**Lines:** 319-327

**Current code:**
```python
# Extract readouts (morphology channels)
morph = sim_result['morphology']
readouts = {
    'morphology': {
        'er': morph['er'],
        'mito': morph['mito'],
        'nucleus': morph['nucleus'],
        'actin': morph['actin'],
        'rna': morph['rna'],
    }
}
```

### Recommended Integration (Minimal)

**Option A: Use corrected morphology if available**
```python
# Extract readouts (morphology channels)
morph_raw = sim_result['morphology']

# Use corrected morphology if calibration was applied
if 'morphology_corrected' in sim_result:
    morph = sim_result['morphology_corrected']
    # Log that calibration was used
    self.logger.info(f"Using vignette-corrected morphology for well {sim_result['well_id']}")
else:
    morph = morph_raw

readouts = {
    'morphology': {
        'er': morph['er'],
        'mito': morph['mito'],
        'nucleus': morph['nucleus'],
        'actin': morph['actin'],
        'rna': morph['rna'],
    }
}

# Optionally: Pass calibration metadata through
if 'calibration' in sim_result:
    qc['calibration_applied'] = sim_result['calibration']
```

**Option B: Always apply calibration if profile exists**
```python
# Load calibration profile once at agent initialization
# In __init__:
self.calibration_profile = None
if Path("calibration_report.json").exists():
    from src.cell_os.calibration.profile import CalibrationProfile
    self.calibration_profile = CalibrationProfile("calibration_report.json")
    self.logger.info("Loaded calibration profile (vignette correction enabled)")

# In execute_design_v2:
morph_raw = sim_result['morphology']

if self.calibration_profile is not None:
    well_id = sim_result.get('well_id')
    morph = self.calibration_profile.correct_morphology(morph_raw, well_id)
    # Add metadata
    qc['calibration_applied'] = True
else:
    morph = morph_raw

readouts = {
    'morphology': {
        'er': morph['er'],
        'mito': morph['mito'],
        'nucleus': morph['nucleus'],
        'actin': morph['actin'],
        'rna': morph['rna'],
    }
}
```

**My recommendation:** Option A (use corrected if available)
- More flexible (can run with or without calibration)
- Supports pre-calibrated observations (from apply_calibration script)
- Agent doesn't need to know about calibration internals

---

## Exposure Policy Integration

### Where to Add

**File:** `src/cell_os/epistemic_agent/agent/policy_rules.py`
**Function:** Wherever exposure is currently set (or add new policy rule)

**Example:**
```python
# Load calibration profile
from src.cell_os.calibration.profile import CalibrationProfile

profile = CalibrationProfile("calibration_report.json")

# Get exposure recommendation based on sample class
sample_class = "bright" if expected_intensity > 300 else "normal"
exposure_mult, warnings = profile.exposure_policy(sample_class)

# Log warnings
for warning in warnings:
    self.logger.warning(f"Calibration: {warning}")

# Use recommended exposure
well_spec.exposure_multiplier = exposure_mult
```

**Rule-based policy (no optimization yet):**
- Bright samples (high expected intensity): use 0.7x (avoid saturation)
- Normal samples: use 1.0x
- Dim samples (low expected intensity): use 1.3x (if safe)

---

## Quantization Anti-Overfitting

### Where to Add

**File:** Anywhere agent scores improvements or differences

**Example: Acquisition function**
```python
from src.cell_os.calibration.profile import CalibrationProfile

profile = CalibrationProfile("calibration_report.json")

# When computing improvement
delta_er = new_value - baseline_value

# Check if difference is significant (above noise floor)
if not profile.is_significant_difference(delta_er, "er", threshold_lsb=2.0):
    # Treat as tie - don't claim improvement
    improvement_score = 0.0
else:
    improvement_score = delta_er
```

**Use case:** Prevents agent from hallucinating progress on sub-LSB differences.

---

## What This Enables (Without Breaking Anything)

### 1. Vignette Correction ✅
- Edge wells boosted by ~15% (1/0.85)
- Center wells unchanged
- Spatially uniform morphology comparisons

### 2. Saturation Awareness ✅
- Warnings when wells approach safe max
- Exposure policy avoids clipping
- Agent knows dynamic range limits

### 3. Quantization Awareness ✅
- Resolution ~0.013 AU/LSB
- Differences < 0.026 AU treated as noise
- Anti-overfitting guard

### 4. Floor Status ✅
- Agent knows floor is unobservable
- Warnings that "signal above floor" policy unavailable
- Documented limitation

---

## What NOT to Do (Anti-Patterns)

❌ **Don't overwrite `morphology` in-place**
- Keep raw values accessible
- Use derived fields for corrected data

❌ **Don't auto-write calibration back into detector config**
- Calibration is read-only input
- No silent mutations

❌ **Don't add optimization objectives yet**
- Keep it rule-based (exposure policy)
- No auto-learning from calibration data

❌ **Don't recompute `morphology_struct` unless you know what you're doing**
- If struct is derived from raw morphology in simulator, leave it alone
- If struct is placeholder (zeros), doesn't matter yet

---

## Testing the Integration

### Smoke Test
```bash
# 1. Generate calibrated observations
python -m src.cell_os.analysis.apply_calibration \
  --obs my_observations.jsonl \
  --calibration calibration_report.json \
  --out observations_calibrated.jsonl

# 2. Run agent on calibrated observations
# (modify agent to use morphology_corrected if present)

# 3. Check logs for:
#    - "Using vignette-corrected morphology"
#    - Calibration warnings
#    - No errors about missing fields
```

### Validation Checks
```python
# After agent run, check:
# 1. Agent used corrected morphology
assert "calibration_applied" in agent_results

# 2. No regressions (beliefs still converge)
assert agent.beliefs.ldh_sigma_stable is True

# 3. Vignette correction improved edge well signal
edge_wells = [w for w in observations if w["well_id"] in ["A1", "P24"]]
assert all(w["morphology_corrected"]["er"] > w["morphology"]["er"] for w in edge_wells)
```

---

## Next Steps (Phase 4)

**After confirming read-only integration works:**

1. **Fix DARK floor behavior** (simulator-side)
   - Add detector bias offset (1-2 AU)
   - Enable floor variance observation
   - Re-run calibration → floor becomes observable

2. **Exposure sweep experiment** (optional)
   - Execute bead plate with multiple exposure_multiplier values (0.5, 1.0, 2.0)
   - Validate linearity
   - Observe true saturation threshold (upgrade confidence to "high")

3. **Markdown report generator** (trivial)
   - Read calibration_report.json
   - Generate human-readable summary with tables
   - Include interpretation and recommendations

4. **Agent policy refinement** (after validation)
   - Use quantization-aware scoring in acquisition function
   - Expose calibration metadata in agent UI
   - Consider vignette-aware experimental designs (avoid edge wells for critical measurements)

---

## Summary

✅ **Phase 3.5 Complete:**
- CalibrationProfile class (read-only, pure functions)
- apply_calibration script (derived fields, no mutations)
- Integration tests (7/7 passing)
  - 4 calibration application tests (test_apply_calibration_vignette.py)
  - 3 agent integration tests (test_agent_calibration_integration.py)
- **Agent integration applied** (world.py:318-352)

**Agent Integration Applied (Option A):**
```python
# src/cell_os/epistemic_agent/world.py:318-352
# Extract readouts (morphology channels)
morph_raw = sim_result['morphology']

# Use corrected morphology if calibration was applied
if 'morphology_corrected' in sim_result:
    morph = sim_result['morphology_corrected']
    self.logger.info(f"Using vignette-corrected morphology for well {sim_result.get('well_id', 'unknown')}")
else:
    morph = morph_raw

readouts = {
    'morphology': {
        'er': morph['er'],
        'mito': morph['mito'],
        'nucleus': morph['nucleus'],
        'actin': morph['actin'],
        'rna': morph['rna'],
    }
}

# Pass calibration metadata through if present
if 'calibration' in sim_result:
    qc['calibration_applied'] = sim_result['calibration']
```

**No breaking changes:**
- Raw morphology unchanged
- Agent works with or without calibration
- All corrections are opt-in via derived fields
- Backward compatible with uncalibrated observations

**Agent now has:**
- 15% vignette correction at edges (when using calibrated observations)
- Saturation-safe max values per channel (CalibrationProfile)
- Quantization noise floor (0.013 AU resolution)
- Honest floor status (unobservable, documented)

**Test Results:**
```bash
$ pytest tests/integration/test_agent_calibration_integration.py -xvs
PASSED (3/3 tests)

✓ Agent accepts calibrated observations
✓ Agent logic selects morphology_corrected when available
✓ Calibration metadata flows through

$ pytest tests/integration/test_apply_calibration_vignette.py -xvs
PASSED (4/4 tests)

✓ Vignette correction: center unchanged, edge boosted 1.15x
✓ Metadata stamped correctly
✓ Saturation warnings triggered
✓ Quantization awareness validated
```

This is **read-only integration done right**: no silent mutations, no auto-learning chaos, just clean derived data.
