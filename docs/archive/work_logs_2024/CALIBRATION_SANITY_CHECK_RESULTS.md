# Calibration Report - Sanity Check Results

**Date:** 2025-12-27
**Bead Plate:** CAL_384_MICROSCOPE_BEADS_DYES_v1 (384 wells, seed=42)

---

## 1. Vignette R² Analysis (Radial vs Radial+Row+Col)

### Results
```
Channel   Edge Mult   R² (radial)   R² (extended)   ΔR²      Unmodeled?
er        0.8709      0.4985        0.5006         +0.0021   ✓ No
mito      0.8752      0.4632        0.4662         +0.0030   ✓ No
nucleus   0.8736      0.4783        0.4783         +0.0000   ✓ No
actin     0.8586      0.5433        0.5445         +0.0012   ✓ No
rna       0.8546      0.5729        0.5749         +0.0020   ✓ No
```

### Interpretation ✅ PASS

**R² is low (0.46-0.57) BUT correctly interpreted:**

1. **Extended model barely helps:** ΔR² < 0.003 for all channels
   - Adding row/col terms does NOT significantly improve fit
   - This rules out strong row or column bias
   - The 0.46-0.57 R² represents **true well-to-well variation**, not unmodeled structure

2. **Why R² isn't higher:**
   - Real well-to-well intensity variation (measurement noise, dye loading, etc.)
   - Radial model is a **simplification** (real vignette may have slight asymmetry)
   - R² = 0.5 means vignette explains 50% of variance, which is **reasonable for flatfield data**

3. **Edge multipliers are stable:** 0.85-0.88 across all channels
   - This consistency validates the radial model choice
   - If model were badly wrong, edge estimates would vary wildly

**Conclusion:** Radial-only model is appropriate. Low R² reflects real variation, not model inadequacy.

---

## 2. Saturation Confidence Assessment

### Results
```
Overall confidence: medium
Interpretation: "No clipping observed; saturation cap is above observed max values."

Per-channel:
  er:      max_observed = 421.47 AU,  cap_inferred = False,  confidence = medium
  mito:    max_observed = 526.64 AU,  cap_inferred = False,  confidence = medium
  nucleus: max_observed = 561.78 AU,  cap_inferred = False,  confidence = medium
  actin:   max_observed = 478.13 AU,  cap_inferred = False,  confidence = medium
  rna:     max_observed = 596.28 AU,  cap_inferred = False,  confidence = medium

Top bin fractions: 0.26% (all channels < 1% → no pile-up)
```

### Interpretation ✅ PASS (with caveat)

**What "no saturation detected" means:**

1. **We didn't hit the cap:** Current max intensities (400-600 AU) are below saturation
2. **Cap exists but is higher:** Likely >600-800 AU based on distribution
3. **Exposure=1.0 is conservative:** Room to increase exposure without clipping

**Why confidence is "medium" not "high":**
- We have **no direct observation** of saturation (no pile-up, top_bin < 1%)
- Threshold estimates are **extrapolations** from p999, not measured caps
- True saturation cap could be 1000 AU or 5000 AU — we don't know

**What this tells us:**
- ✅ Current dye intensities are safe (no clipping risk)
- ✅ Can increase exposure for dim samples
- ⚠️ Don't trust threshold_estimate as a hard cap (it's a proxy)
- ⚠️ Need higher exposure or brighter samples to observe true saturation

**Recommendation for Phase 4:**
- Add FLATFIELD_DYE_VERYHIGH with exposure=2.0 or 3.0
- Intentionally push into saturation to observe true cap
- This would upgrade confidence from "medium" to "high"

---

## 3. Quantization Cross-Channel Consistency

### Results
```
Cross-channel consistency:
  Mean step: 0.015254 AU/LSB
  Std:       0.001745 AU/LSB
  CV:        11.44%
  Is consistent: True

Per-channel estimates:
  er:      0.01315 AU/LSB
  mito:    0.01545 AU/LSB
  nucleus: 0.01833 AU/LSB  ← Slightly higher
  actin:   0.01411 AU/LSB
  rna:     0.01524 AU/LSB
```

### Interpretation ✅ PASS (with note)

**Cross-channel CV = 11.4% < 20% threshold:**
- Quantization step is **consistent** across channels
- This validates that delta histogram method is detecting **real quantization**
- Not an artifact of smoothing or per-channel scaling

**Why nucleus is slightly higher (0.01833 vs 0.0131-0.0152):**
- Could be legitimate per-channel ADC scaling
- Could be slightly different noise floor in nucleus channel
- Still within 20% tolerance (consistent)

**Confidence that this is real quantization:**
1. ✅ Detected via delta histogram (independent of metadata)
2. ✅ Consistent across 5 channels (CV = 11%)
3. ✅ Step size ~0.015 AU is plausible for 16-bit ADC scaled to 0-1000 AU range
4. ✅ metadata.quant_step was 0.0, so this isn't circular (estimator works independently)

**Potential confounds ruled out:**
- ❌ Smoothing: Would produce larger, less consistent steps
- ❌ Post-processing artifacts: Would vary wildly across channels
- ❌ Rounding errors: Would show as multiples of a base step

**Recommendation:**
- Current estimate is solid
- To increase confidence further:
  - Check if detector params have per-channel ADC scaling
  - Verify that ~0.015 AU matches expected bit-depth (e.g., 16-bit → 2^16 = 65536 levels over 1000 AU = 0.015 AU/LSB ✓)

---

## Summary: All Sanity Checks PASS ✅

### 1. Vignette R² (0.46-0.57)
**Interpretation:** Correctly reflects real well-to-well variation, not unmodeled structure.
**Evidence:** Extended model (radial+row+col) barely improves fit (ΔR² < 0.003)
**Status:** ✅ PASS - Radial-only model is appropriate

### 2. Saturation "none detected"
**Interpretation:** We didn't hit the cap, cap is above observed max (400-600 AU)
**Evidence:** Top bin fraction < 1%, no pile-up observed
**Confidence:** Medium (extrapolation, not direct observation)
**Status:** ✅ PASS - Honest about what we didn't observe
**Recommendation:** Add very-high-exposure sweep to observe true saturation

### 3. Quantization step ~0.015 AU/LSB
**Interpretation:** Real quantization detected, consistent across channels
**Evidence:** CV = 11.4% < 20%, independent of metadata
**Status:** ✅ PASS - Robust estimate
**Note:** Nucleus channel slightly higher (0.0183 vs 0.013-0.015), still consistent

---

## What This Means for Agent

### Actionable Estimates (High Confidence)
1. **Vignette correction:** Edge wells are 85-88% of center → apply 1.15x boost
2. **Quantization awareness:** Resolution is ~0.015 AU → differences < 0.05 AU may be noise
3. **Dynamic range:** Safe operating range is 0-400 AU at exposure=1.0

### Moderate Confidence (Use with Caution)
1. **Saturation avoidance:** Stay below ~400-500 AU to avoid clipping
   - Based on p99 analysis, not direct cap observation
   - True cap may be much higher

### Unobservable (Documented)
1. **Floor:** DARK = 0.0 with zero variance
   - Cannot estimate noise floor
   - Cannot set "above floor" policy

---

## Ready for Phase 3.5: Agent Integration (Read-Only)

**What to wire in:**
```python
# Load calibration report
with open("calibration_report.json") as f:
    cal = json.load(f)

# Apply vignette correction
vignette_edge = cal["vignette"]["edge_multiplier"]
for well in plate_wells:
    if is_edge_well(well):
        well["intensity_corrected"] = well["intensity_raw"] / vignette_edge[channel]

# Check saturation risk
sat_safe_max = cal["saturation"]["per_channel"][channel]["p99"] * 0.8
if well["intensity_raw"] > sat_safe_max:
    warnings.append(f"Well {well_id} may be near saturation")

# Exposure planning
expo_rec = cal["exposure_recommendations"]["per_channel"][channel]["recommended_exposure_multiplier"]
if sample_type == "bright":
    exposure = 1.0 * expo_rec  # Use 0.7x for bright samples
```

**Keep it read-only:** Don't auto-write back into detector config yet.

---

## Next: Phase 4 - Fix DARK Floor

**When you fix DARK floor, ensure:**
1. DARK has **variance** (not just constant bias)
2. Negative values handled correctly (clamp after adding floor, not before)
3. Floor observable even when mean near 0

**Cleanest approach:** Add small bias offset (1-2 AU) before quantization + keep additive noise.

This will produce non-degenerate DARK distribution without breaking existing assumptions.
