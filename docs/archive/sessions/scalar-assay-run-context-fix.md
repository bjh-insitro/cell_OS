# Scalar Assay Run Context Fix: 2025-01-20

## Semantic Gap: "Always Trust Scalars" Cheat Code

**Bug**: Biochemical assays (ATP/LDH/UPR/TRAFFICKING) were immune to RunContext drift, living in a "sterile vacuum" while imaging suffered lot/instrument effects.

**Why It Matters**: Agents learn "when morphology and LDH disagree, always trust LDH because LDH is magically context-free." This does NOT transfer to reality where both modalities have correlated lot effects.

**Real World**: Plate readers drift, reagent kits vary in quality, and these effects are **correlated** with imaging drift on "cursed days."

---

## The Fix

### 1) Extended RunContext to Include Scalar Assay Modifiers

**Added to run_context.py (lines 97-107, 170-189):**

```python
# Sample per-assay reagent lot shifts (like channel_biases but for biochem)
scalar_assays = ['ATP', 'LDH', 'UPR', 'TRAFFICKING']
scalar_reagent_lot_shift = {}
for assay in scalar_assays:
    assay_shift = (
        0.5 * correlation * cursed_latent +  # Some shared (bad day = bad reagents)
        0.5 * rng.normal(0, 1.0)  # Some independent (each kit is different lot)
    ) * 0.15 * context_strength
    scalar_reagent_lot_shift[assay] = float(assay_shift)
```

**Returns in `get_measurement_modifiers()`:**
- `scalar_assay_biases`: Dict[str, float] - per-assay kit lot multipliers (ATP/LDH/UPR/TRAFFICKING)
- `reader_gain`: float - plate reader instrument drift (**correlated** with `illumination_bias`)

### 2) Applied Modifiers in atp_viability_assay

**Modified biological_virtual.py (lines 2565-2632):**

```python
# Phase 5B: Apply run context measurement modifiers (instrument + kit lot effects)
# CRITICAL: reader_gain is correlated with illumination_bias (imaging),
# so cross-modality disagreement teaches caution (not "always trust scalars")
meas_mods = self.run_context.get_measurement_modifiers()
reader_gain = meas_mods['reader_gain']  # Plate reader instrument drift
scalar_assay_biases = meas_mods['scalar_assay_biases']  # Per-assay kit lot effects

total_tech_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor * reader_gain

# Apply to each scalar readout
ldh_signal *= total_tech_factor * scalar_assay_biases['LDH']
atp_signal *= total_tech_factor * scalar_assay_biases['ATP']
upr_marker *= total_tech_factor * scalar_assay_biases['UPR']
trafficking_marker *= total_tech_factor * scalar_assay_biases['TRAFFICKING']
```

---

## Key Design Decisions

### 1) Shared Latent for Cross-Modality Correlation

**Both** `illumination_bias` (imaging) and `reader_gain` (plate reader) derive from the **same** `instrument_shift` latent:

```python
illumination_bias = float(np.exp(instrument_shift))  # ±0.2 → 0.82× to 1.22×
reader_gain = float(np.exp(instrument_shift))        # ±0.2 → 0.82× to 1.22×
```

**Result**: Perfect correlation (ρ=1.0) between imaging and scalar instrument drift.

**Why**: On "cursed days," BOTH modalities are cursed together. This teaches agents:
- Cross-modality disagreement is sometimes **shared measurement artifact** (both wrong together)
- Cross-modality disagreement is sometimes **real biology** (one right, one wrong)
- Must learn to disambiguate through calibration, not blind trust

### 2) Independent Per-Assay Lot Effects

Each assay kit (ATP/LDH/UPR/TRAFFICKING) has **independent** reagent lot drift:
- Some correlation with `cursed_latent` (bad days → bad reagents generally)
- Some independence (ATP lot is different from LDH lot)

**Result**: Within same context, ATP and LDH can have different biases (e.g., ATP: 1.056×, LDH: 1.049×, UPR: 0.884×)

---

## Test Results

**test_scalar_assay_run_context.py: 4/4 passing**

1. ✓ **Scalar assays respond to reader_gain**: Ratio = 0.762 (different contexts produce different readouts)
2. ✓ **Per-assay kit lot effects independent**: ATP/LDH/UPR have distinct biases within same context
3. ✓ **reader_gain correlated with imaging**: Correlation ρ=1.000 (perfect, as designed)
4. ✓ **No double-application**: Neutral context produces reasonable baseline values

---

## What This Changes for RL

### Before Fix
- Imaging: subject to lot/instrument drift
- Scalars: magically immune
- Agent learns: "Always trust scalars, ignore morphology when they disagree"
- **Transfer fails**: Real scalars also drift

### After Fix
- Imaging: subject to lot/instrument drift (illumination_bias + channel_biases)
- Scalars: subject to lot/instrument drift (reader_gain + scalar_assay_biases)
- **Correlated**: Both suffer together on cursed days (shared instrument_shift)
- Agent learns: "Cross-modality disagreement is ambiguous, must calibrate"
- **Transfer succeeds**: Agent has experienced correlated failure modes

---

## Semantic Consistency Preserved

### Observer Independence: ✓
- All modifiers applied at measurement time (assay call), not during physics step
- `reader_gain` and `scalar_assay_biases` use deterministic seeding from run_context
- No RNG consumption during observation (measurements don't perturb physics)

### Conservation Laws: ✓
- Modifiers are multiplicative on readouts, not on viability/death ledgers
- Death accounting unaffected
- No new conservation holes introduced

### Competing Risks: ✓
- Hazard proposals unchanged
- Scalar readouts are diagnostic, not mechanistic
- No feedback into physics layer

---

## Remaining Question (Documented in PHASE_6_REALISM_ROADMAP.md)

**atp_viability_assay still does NOT apply `pipeline_transform()`** (batch-dependent feature extraction).

**Current decision**: Correct. `pipeline_transform()` is imaging-specific (segmentation/feature extraction drift). Plate readers have their own drift (`reader_gain`), but don't need "feature extraction" transform since readouts are direct scalar values.

**Alternative**: If you model "curve fitting" or "background subtraction" as batch-dependent, you could add a scalar-specific pipeline transform. But current approach is cleaner.

---

## Files Modified

1. **run_context.py**:
   - Added `scalar_reagent_lot_shift` field to RunContext dataclass (line 39)
   - Extended `RunContext.sample()` to generate per-assay lot shifts (lines 97-107)
   - Extended `get_measurement_modifiers()` to return `reader_gain` and `scalar_assay_biases` (lines 150-189)

2. **biological_virtual.py**:
   - Modified `atp_viability_assay()` to apply run context modifiers (lines 2565-2632)
   - Applied `reader_gain * scalar_assay_biases[assay]` to LDH, ATP, UPR, TRAFFICKING signals

3. **test_scalar_assay_run_context.py** (new):
   - Regression tests ensuring modifiers work correctly
   - Tests correlation structure (reader_gain ↔ illumination_bias)
   - Tests no double-application

---

## Migration Notes

**Backwards compatibility**: ✓

Existing code that doesn't pass `run_context` will get default context (seed=0) which has `reader_gain=1.0` and `scalar_assay_biases={assay: 1.0}`, so behavior unchanged.

**Naming clean**: ✓

- `illumination_bias`: imaging-specific (lamp aging, focus drift)
- `reader_gain`: plate reader-specific (scalar instrument drift)
- Both derived from `instrument_shift`, but names stay semantically clean

---

## Next Steps

See **PHASE_6_REALISM_ROADMAP.md** for next realism priorities:
1. Volume + evaporation + concentration drift ⭐⭐⭐
2. Plate-level correlated fields ⭐⭐⭐
3. Waste + pH as second stress axis ⭐⭐
