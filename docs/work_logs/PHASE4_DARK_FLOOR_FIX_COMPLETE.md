# Phase 4: DARK Floor Fix - COMPLETE ✅

**Date:** 2025-12-27
**Status:** All validation complete, architecture proven

---

## What Was Done

### 1. Implementation ✅
- Added detector bias baseline (Step 0 in detector_stack.py:78-114)
- Enabled bias for optical_material mode only (biological_virtual.py:3123)
- Created calibration-specific technical noise params (calibration_thalamus_params.yaml)
- Wrote contract tests for DARK floor observability

### 2. Data Generation ✅
- Regenerated bead plate with darkfix (384 wells, seed=42)
- Output: `results/cal_beads_dyes_seed42_darkfix/`

### 3. Contract Tests ✅
All 4 tests pass:
- ✓ DARK non-degeneracy: 7-9 unique values per channel (>> 3 minimum)
- ✓ DARK stays dark: mean 0.23-0.31 AU (< 0.5% of dye_low)
- ✓ DARK has positive mean: bias applied (~20 LSB)
- ✓ DARK has positive std: noise applied (~3 LSB)

### 4. Calibration Report ✅
Generated: `results/cal_beads_dyes_seed42_darkfix/calibration/calibration_report.json`

Key result: **`floor.observable = true`** (was `false` in Phase 3)

---

## Phase 3 → Phase 4 Comparison

### FLOOR (The Key Upgrade)
| Metric | Phase 3 | Phase 4 | Change |
|--------|---------|---------|--------|
| Observable | **false** | **true** ✅ | Upgraded |
| ER mean | 0.0000 AU | 0.2645 AU | + bias |
| Unique values | 1 | 7-9 | Non-degenerate |

Phase 3 reason: _"DARK wells return literal 0.0 with zero variance"_

### VIGNETTE (Stable)
| Channel | Phase 3 Edge | Phase 4 Edge | Δ |
|---------|-------------|-------------|---|
| er | 0.8709 | 0.8714 | +0.06% |
| mito | 0.8752 | 0.8755 | +0.03% |
| nucleus | 0.8736 | 0.8740 | +0.05% |
| actin | 0.8586 | 0.8592 | +0.07% |
| rna | 0.8546 | 0.8552 | +0.07% |

**All < 0.1% change** - vignette unaffected by floor fix

### SATURATION (Stable)
| Channel | Phase 3 p99 | Phase 4 p99 | Δ |
|---------|------------|------------|---|
| er | 406.79 | 407.09 | +0.07% |
| mito | 502.91 | 503.10 | +0.04% |
| nucleus | 599.35 | 599.67 | +0.05% |
| actin | 457.92 | 458.15 | +0.05% |
| rna | 552.97 | 553.23 | +0.05% |

**All < 0.1% change** - saturation unaffected by floor fix

### QUANTIZATION
| Metric | Phase 3 | Phase 4 |
|--------|---------|---------|
| Mean step | 0.01525 AU | 0.01328 AU |
| CV | 11.44% | 8.60% |
| Consistent | True | True |

Both phases maintain cross-channel consistency (CV < 20%).
Per-channel estimates shifted ~7-17% (bias affects delta histogram),
but both are valid and internally consistent.

---

## Architecture Validation

**What we proved:**

1. **Observable flags are honest**
   - Floor was `false` when DARK = 0.0 ± 0.0
   - Floor became `true` when DARK = 0.26 ± 0.05
   - Calibration module correctly detects instrument upgrades

2. **No false positives**
   - Vignette stayed stable (< 0.1% change)
   - Saturation stayed stable (< 0.1% change)
   - Only floor changed (the thing we fixed)

3. **Containment preserved**
   - Bias gated to `optical_material` mode only
   - Cell biology unchanged
   - No breaking changes to existing code

4. **Closed epistemic loop working**
   - Fix instrument → regenerate data → calibration upgrades → agent gains capability
   - No manual intervention needed
   - Read-only, no side effects

---

## What This Unlocks

### 1. SNR Estimation
- Floor mean: 0.23-0.31 AU per channel
- Floor sigma: 0.041-0.063 AU (from contract tests)
- Can now compute signal-to-noise ratios

### 2. Dim Sample Policies
Agent can now reason about:
- "Is this signal 3× above noise floor?"
- "Should I increase exposure or is it pointless?"
- Minimum detectable signal thresholds

### 3. Exposure Planning
- Know the noise floor → can set SNR targets
- E.g., "expose until signal > 10× floor"
- Avoid under-exposure (SNR too low) or over-exposure (saturation)

### 4. Complete Detector Characterization
All 4 calibration estimators now working:
- ✓ Floor: observable (was unobservable)
- ✓ Vignette: observable, correctable
- ✓ Saturation: observable (cap location)
- ✓ Quantization: observable, consistent

---

## Implementation Details

### Detector Bias Formula
```
bias = dark_bias_lsbs * quant_step_param
     = 20.0 * 0.012 AU
     = 0.24 AU
```

With 16-bit ADC and ceiling=800 AU:
- quant_step = 800 / 65535 ≈ 0.012 AU/LSB
- bias = 20 LSB ≈ 0.24 AU

Fallback: 0.3 AU if quantization disabled

### Additive Floor Noise
```yaml
additive_floor_sigma_*: 0.045 AU  # ~3 LSB
```

Ensures observable variance:
- Gaussian noise centered on bias (0.24 AU)
- Spread of ~0.045 AU (3 LSB)
- Results in 7-9 unique quantized values per channel

### Detector Stack Order
```
0. Bias (NEW in Phase 4, gated to optical_material)
1. Exposure multiplier
2. Additive floor noise
3. Vignette
4. Saturation (soft-knee)
5. Quantization (ADC)
```

---

## Files Changed

### Core Implementation
- `src/cell_os/hardware/detector_stack.py` (lines 78-114)
- `src/cell_os/hardware/biological_virtual.py` (line 3123)
- `data/calibration_thalamus_params.yaml` (new file)

### Tests
- `tests/contracts/test_dark_floor_observable.py` (new, 4 tests)

### Data
- `results/cal_beads_dyes_seed42_darkfix/observations.jsonl` (384 wells)
- `results/cal_beads_dyes_seed42_darkfix/calibration/calibration_report.json`

### Documentation
- `PHASE4_DARK_FLOOR_FIX.md` (this file, updated)

---

## Next Steps (Optional)

**Not yet requested, but ready when needed:**

1. **Update agent exposure policies**
   - Use floor.mean and floor.sigma for SNR-based exposure planning
   - Set minimum signal thresholds (e.g., 10× floor)
   - Validate on dim samples

2. **Exposure sweep validation**
   - Execute bead plate with exposures [0.5, 1.0, 2.0, 4.0]
   - Observe linearity and true saturation cap
   - Upgrade saturation confidence from "medium" to "high"

3. **Update biological simulation**
   - Consider adding bias to cell measurements (if desired)
   - Currently gated to optical_material only
   - Would make cell imaging more realistic

4. **Markdown report generator**
   - Human-readable calibration summary
   - Interpretation and recommendations
   - Confidence intervals and warnings

---

## Summary

**Phase 4 is complete.** We fixed the microscope simulator to make DARK wells measurable (bias + noise → observable variance), which:

1. **Upgraded floor from unobservable → observable**
2. **Maintained stability** of vignette, saturation, quantization
3. **Validated architecture** (observable flags respond correctly)
4. **Unlocked SNR reasoning** for agent exposure policies
5. **Preserved containment** (no biology contamination)

This is **instrument honesty at zero**. The simulator now behaves like a real detector: even in darkness, you measure bias + noise, not magic perfect zeros.

**Architecture proven:** Fix instrument → calibration upgrades → agent gains capability.
No manual rewrites, no silent mutations, no breaking changes.
Just honest instruments and responsive calibration.

✅ Phase 4 complete.
