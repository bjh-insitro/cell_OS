# Phase 2C.1.3: Stress-Bracketed Identifiability Suite - PASS

**Status:** ✅ Complete - All Acceptance Criteria Met
**Date:** 2025-12-29
**Final Version:** 2C.1.3 (stress-bracketed design with extended horizon)

---

## Executive Summary

**✅ PASS** - Threshold recovered with 70% margin (0.033 vs 0.10 tolerance)

The stress-bracketed design successfully proves Phase 2A commitment parameters are identifiable:
- ✅ Threshold: 0.033 error (within 0.10 tolerance)
- ✅ Baseline hazard λ₀: 1.86x error (within 3x tolerance)
- ✅ Sharpness p: 0.50 error (within 1.0 tolerance)
- ✅ Held-out prediction: 0.017 error (within 0.15 tolerance)

**Key Innovation:** Doses selected to **bracket threshold in stress space** (S ∈ [0.43, 0.59, 0.68, 0.75]), not just by commitment fraction, breaking the confounding between threshold and λ₀.

---

## Design Changes (2C.1.2 → 2C.1.3)

### Problem Identified in 2C.1.2

Threshold recovery failed at boundary (0.100 vs 0.10 tolerance) because:
- ER stress saturated into 0.72-0.95 range (all above threshold=0.60)
- Model couldn't distinguish "threshold at 0.60 with λ₀=0.20" from "threshold at 0.70 with λ₀=0.14"
- Classic parameter confounding: threshold and λ₀ traded off in the fit

### Solution in 2C.1.3

**1. Extended Observation Window**
- **48h → 120h** (7 timepoints instead of 5)
- Allows low-dose regimes to generate commitments over longer time at risk
- Preserves λ₀ meaning (biology, not "cranked hazards")

**2. Lowered Doses**
- Previous: 0.275, 0.331, 0.438, 0.637 µM → S ∈ [0.72, 0.79, 0.90, 0.95]
- **New: 0.130, 0.197, 0.245, 0.300 µM → S ∈ [0.43, 0.59, 0.68, 0.75]**
- Stress now **brackets threshold=0.60** (samples below, at, and above)

**3. Stress-Bracketed Selection**
- Doses chosen by **stress level at observation timepoint**, not commitment fraction
- Design constraint: include at least one dose with S < threshold, one with S ≈ threshold, one with S > threshold
- This is "design for identifiability," not "design for event variance"

---

## Final Design (2C.1.3)

### Timepoints
```
0h, 12h, 24h, 48h, 72h, 96h, 120h
```

### Regime A (Low Stress - RE Baseline)
- **DMSO control** (0.0 µM)
- Result: 0% commitment ✅
- ICC: 0.0458 (negligible persistent variance)

### Regime B (Mid Stress - Held-Out Prediction)
- **0.227 µM tunicamycin**
- Stress: S=0.67 at t=12h
- Result: 4.2% commitment (2/48 events)
- Prediction error: 0.017 ✅

### Regime C (Stress-Bracketed - Parameter Recovery)

| Dose | Stress (t=12h) | Position | Committed | Fraction |
|------|----------------|----------|-----------|----------|
| **C1: 0.130 µM** | 0.427 | Below threshold | 0/12 | 0% |
| **C2: 0.197 µM** | 0.588 | At threshold edge | 2/12 | 17% |
| **C3: 0.245 µM** | 0.683 | Above threshold | 5/12 | 42% |
| **C4: 0.300 µM** | 0.750 | Saturated | 10/12 | 83% |

**Total events in C:** 17/48 (35%)

---

## Recovery Results

| Parameter | Truth | Recovered | Error | Tolerance | Status |
|-----------|-------|-----------|-------|-----------|--------|
| **Threshold** | 0.60 | 0.57 | **0.033** | ≤0.10 | ✅ **70% margin** |
| λ₀ (per h) | 0.200 | 0.373 | 1.86x | ≤3x | ✅ |
| Sharpness p | 2.0 | 2.5 | 0.50 | ≤1.0 | ✅ |
| Prediction | — | — | 0.017 | ≤0.15 | ✅ |

**Fit Quality:**
- Log-likelihood: -24.29
- Events: 17/48 wells in Regime C
- Precondition: SUFFICIENT_EVENTS ✅

---

## Why It Worked

### Stress Distribution Comparison

**2C.1.2 (Failed):**
```
Stress range: [0.72, 0.79, 0.90, 0.95]
Position: All above threshold=0.60
Result: Threshold and λ₀ confounded
```

**2C.1.3 (Passed):**
```
Stress range: [0.43, 0.59, 0.68, 0.75]
Position: Brackets threshold=0.60
Result: Threshold independently identifiable
```

### The Math

The commitment hazard is:
```
λ(S) = λ₀ · ((S - S_threshold) / (1 - S_threshold))^p
```

When all observations have S >> S_threshold:
- The term `(S - S_threshold) / (1 - S_threshold)` is always large
- λ₀ and S_threshold become confounded (can slide threshold up and λ₀ down, or vice versa)
- You're fitting a ridge, not identifying parameters independently

When observations span S < S_threshold and S > S_threshold:
- Some wells have λ(S) ≈ 0 (below threshold)
- Some wells have λ(S) ramping up (near threshold)
- Some wells have λ(S) saturated (above threshold)
- The full sigmoid shape is observable, breaking the confounding

---

## Artifacts

**Final suite output:** `/tmp/identifiability_suite_2c1_3/20251229_150613/`
- `observations.csv` (5040 rows: 144 wells × 7 timepoints × 5 metrics)
- `events.csv` (144 rows: commitment status per well)
- `inference_results.json` (recovered parameters, all criteria met)
- `report.md` (full report with per-dose diagnostics)

**Scout outputs:** `/tmp/identifiability_scout_2c1_3/`
- `scout_20251229_145957/` (wide scan: 0.03-0.30 µM, 12 doses)
- `scout_20251229_150239/` (fine scan: 0.18-0.36 µM, 10 doses)

**Config:** `configs/calibration/identifiability_2c1_3.yaml`

---

## Lessons Learned

### 1. Identifiability Requires Covariate Variation Around the Parameter

**Bad design:** Sample where all S > threshold → threshold confounded with λ₀

**Good design:** Sample S < threshold, S ≈ threshold, S > threshold → threshold independently identifiable

This applies broadly: if you want to identify a threshold/inflection/changepoint parameter, your covariate **must span the region where that parameter matters**, not just sample one side of it.

### 2. Commitment Fraction Alone Is Insufficient Design Criterion

**2C.1.2 had good commitment variation** (33%, 42%, 83%, 83%) but still failed threshold recovery because the **stress covariate** was saturated.

**2C.1.3 has less commitment variation** (0%, 17%, 42%, 83%) but **passes** because stress brackets the threshold.

**Design principle:** Select experimental conditions by **covariate distribution relative to the parameter of interest**, not just by outcome variance.

### 3. The Suite Correctly Diagnosed the Problem Before Fixing It

Phase 2C.1.2 didn't "fail to work" - it **worked correctly by revealing the design limitation**:
- Threshold error at boundary (0.100 vs 0.10)
- Per-dose diagnostics showed stress saturation (0.72-0.95)
- Report explicitly stated: "stress proxy may not be informative enough"

This is the value of an identifiability suite: **it tells you when you're asking too much of your data**, preventing overconfident parameter estimates from confounded fits.

### 4. Extend Time, Don't Just Crank Hazards

When low doses don't produce events, you have two levers:
- **Increase λ₀** (faster commitment) → changes biological meaning
- **Extend observation window** (more time at risk) → preserves biological meaning

We chose the latter. This keeps the recovered λ₀=0.373 as a biologically meaningful parameter, not an "accelerated clock for inference."

---

## Phase 2C.1 Overall Status

| Milestone | Version | Status | Key Finding |
|-----------|---------|--------|-------------|
| **Infrastructure** | 2C.1.0 | ✅ Complete | Dose scout, precondition checks, per-dose diagnostics work end-to-end |
| **Initial validation** | 2C.1.1 | ✅ Complete | Pipeline correctly shows zero events when below cliff |
| **Stratified design** | 2C.1.2 | ⚠️ Complete with limitation | Threshold unidentifiable due to stress saturation (diagnostic FAIL) |
| **Stress-bracketed** | 2C.1.3 | ✅ **PASS** | Threshold recovered by sampling stress around threshold region |

**Final Verdict:** Phase 2A commitment mechanism is **identifiable from observations** when the design properly samples the covariate space around generative parameters.

---

## Next Steps (Post-2C.1)

1. **Apply to real experiments:** Use stress-bracketed design principles when calibrating threshold for actual ER stress assays

2. **Generalize to other mechanisms:**
   - Mito commitment (threshold on mito dysfunction)
   - Multi-stress commitment (intersection of ER + Mito)
   - Dose-time confounding in sequential treatments

3. **Joint identifiability (Phase 2C.2):**
   - Can we recover **both** Phase 1 RE parameters **and** Phase 2A commitment parameters jointly?
   - Does RE variance confound with commitment variance?

4. **Practical calibration workflow:**
   - Integrate dose scout into standard experiment planning
   - Add stress-bracketing constraints to design generator
   - Build automated "identifiability health check" for configs

---

*This milestone proves that systematic identifiability testing reveals design limitations honestly, then guides you to fixes that work. The failed 2C.1.2 was just as valuable as the passing 2C.1.3 - both taught us something real about the model.*
