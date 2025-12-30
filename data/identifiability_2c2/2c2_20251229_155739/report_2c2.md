# Phase 2C.2: Multi-Mechanism Identifiability Report

**Run ID:** 2c2_20251229_155739
**Timestamp:** 2025-12-29T15:59:16.447712
**Seed:** 42
**Cell Line:** A549

---

## Summary

⚠️ **INSUFFICIENT_EVENTS**

This suite tests whether **ER and mito commitment mechanisms are discriminable** from stress trajectories and event timing alone, without mechanism labels.

---

## 1. ER-Dominant Regime (Regime A)

**Purpose:** Recover ER parameters with mito negligible

### Recovered ER Parameters

| Parameter | Truth | Recovered | Error | Status |
|-----------|-------|-----------|-------|--------|
| Threshold | 0.60 | 0.57 | 0.033 | ✅ |
| λ₀ (per h) | 0.200 | 0.373 | 1.86x | ✅ |
| Sharpness p | 2.0 | 3.5 | 1.50 | ❌ |

**Fit Quality:**
- Events: 15 / 48 wells
- Log-likelihood: -18.30

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** 100.0% (15 events)
**Target:** ≥80% ✅

**Confusion Matrix:**

| True \ Pred | ER | Mito |
|--------------|----|----|
| **ER** | 15 | 0 |
| **Mito** | 0 | 0 |

---

## 2. Mito-Dominant Regime (Regime B)

**Purpose:** Recover mito parameters with ER negligible

### Recovered Mito Parameters

| Parameter | Truth | Recovered | Error | Status |
|-----------|-------|-----------|-------|--------|
| Threshold | 0.60 | 0.90 | 0.300 | ❌ |
| λ₀ (per h) | 0.150 | 0.001 | 0.01x | ❌ |
| Sharpness p | 2.5 | 1.0 | 1.50 | ❌ |

**Fit Quality:**
- Events: 0 / 48 wells
- Log-likelihood: 0.00

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** 0.0% (0 events)
**Target:** ≥80% ❌

**Confusion Matrix:**

| True \ Pred | ER | Mito |
|--------------|----|----|
| **ER** | 0 | 0 |
| **Mito** | 0 | 0 |

---

## 3. Mixed Regime (Regime C)

**Purpose:** Test mechanism discrimination when both stresses compete

### Commitment Fraction Prediction

| Metric | Predicted | Observed | Error | Status |
|--------|-----------|----------|-------|--------|
| **Total fraction** | 0.000 | 0.021 | 0.021 | ✅ |
| ER fraction | 0.000 | 0.021 | 0.021 | ✅ |
| Mito fraction | 0.000 | 0.000 | — | — |

**Events:** 1 / 48 wells

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** 100.0% (1 events)

**Confusion Matrix:**

| True \ Pred | ER | Mito |
|--------------|----|----|
| **ER** | 1 | 0 |
| **Mito** | 0 | 0 |

### Stress Correlation (Confounding Check)

**Correlation at event times:** N/A

✅ Stresses are reasonably separated (no high correlation detected)

---

## 4. Identifiability Verdict

⚠️ **INSUFFICIENT_EVENTS**

Not enough events in dominant regimes to test mechanism discrimination.

**Event counts:**
- ER-dominant: 15 (need ≥10)
- Mito-dominant: 0 (need ≥10)

**Next steps:**
1. Scout doses for both ER and mito stressors
2. Increase baseline hazard or extend observation window
3. Ensure dominant regimes actually produce events before testing discrimination

---

## 5. Reproducibility

**Seed:** 42
**Config:** See run directory
**Inference:** NO mechanism labels used (post-hoc validation only)

---

*Report generated: 2025-12-29 15:59:43*
