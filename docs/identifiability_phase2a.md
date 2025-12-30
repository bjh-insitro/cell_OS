# Phase 2C.1: Identifiability Suite for Phase 2A

## Overview

The identifiability suite proves that Phase 1 (smooth persistent random effects) and Phase 2A (stochastic death commitment) are **identifiable** from simulated observations. This means:

1. We can **recover** the generative parameters (growth CV, commitment threshold, hazard rate, etc.) from observations alone.
2. We can use recovered parameters to **predict** held-out experiments with acceptable accuracy.
3. The two variance sources (smooth REs + discrete events) are **independent** and don't confound each other.

This is critical: if Phase 2A is not identifiable, it's just an expressive "story engine" that can fit anything but predicts nothing. Identifiability makes the simulator accountable to its own generative claims.

---

## What This Suite Proves (and Doesn't Prove)

### ✅ What It Proves

1. **Parameter Recovery**: From high-stress data (Plate C), we can recover:
   - Commitment threshold (S_commit)
   - Baseline hazard rate (λ0)
   - Hazard sharpness (p)

2. **Generalization**: Recovered parameters predict a held-out regime (Plate B) with acceptable error.

3. **Independence**: Phase 1 and Phase 2A are separable:
   - Disabling Phase 2A eliminates events (no false positives)
   - Disabling Phase 1 collapses ICC (smooth variance disappears)
   - Commitment parameters are stable across Phase 1 CV settings (no strong coupling)

### ❌ What It Doesn't Prove

- **Biological realism**: The suite tests identifiability, not whether the model matches real biology.
- **Optimal design**: It doesn't find the best experimental design for parameter estimation.
- **Full joint inference**: It uses staged estimation (Phase 1 → Phase 2A → prediction), not full Bayesian joint inference.

---

## Three-Regime Design

The suite uses three experimental regimes:

### Regime A: Low-Stress (RE-only)

- **Purpose**: Estimate Phase 1 smooth RE variance (ICC) with near-zero commitment contamination.
- **Condition**: DMSO control (no stress).
- **Expected**: Smooth divergence across wells, no commitment events.
- **Output**: ICC (intraclass correlation coefficient) quantifying well-level persistent variance.

### Regime B: Mid-Stress (Mixed, Held-Out)

- **Purpose**: Validate joint model on unseen data.
- **Condition**: Moderate dose (tunicamycin 1.0 µM) that hovers near commitment threshold.
- **Expected**: Mix of smooth REs and discrete commitment events (~20% of wells commit).
- **Output**: Held-out prediction error (model vs empirical commitment fraction).

### Regime C: High-Stress (Event-Rich)

- **Purpose**: Recover commitment parameters with statistical power.
- **Condition**: High doses (tunicamycin 2.5, 5.0, 10.0 µM) with multiple stress levels.
- **Expected**: Many commitment events (~60% of wells commit).
- **Output**: Recovered commitment parameters (threshold, λ0, p) via survival analysis.

---

## Pipeline

### 1. Run Suite

```bash
python scripts/run_identifiability_suite.py \
    --config configs/calibration/identifiability_2c1.yaml \
    --out artifacts/identifiability/dev_run
```

**Outputs:**
- `observations.csv`: Time-series data (cell_count, viability, stress metrics)
- `events.csv`: Commitment events (committed, commitment_time_h, mechanism)
- `truth.json`: Ground truth parameters
- `metadata.json`: Run info

### 2. Fit Inference Models

```bash
python scripts/fit_identifiability_suite.py \
    --in artifacts/identifiability/dev_run \
    --out artifacts/identifiability/dev_run
```

**Outputs:**
- `inference_results.json`: Recovered parameters and prediction metrics

### 3. Render Report

```bash
python scripts/render_identifiability_report.py \
    --run artifacts/identifiability/dev_run
```

**Outputs:**
- `report.md`: Human-readable report with pass/fail verdict

---

## Acceptance Criteria

### Parameter Recovery (Plate C)

| Parameter | Tolerance | Rationale |
|-----------|-----------|-----------|
| Threshold | ±0.10 absolute error | Stress levels measurable to ~0.1 precision |
| Sharpness p | ±1.0 absolute error | Power law exponent has wide prior |
| Baseline λ0 | Within factor 3 (log scale) | Hazard rates are log-distributed |

### Held-Out Prediction (Plate B)

| Metric | Tolerance | Rationale |
|--------|-----------|-----------|
| Commitment fraction | ±0.15 absolute error | ~10-20% of wells in mid-stress regime |

### RE Identifiability (Plate A)

| Check | Criterion | Rationale |
|-------|-----------|-----------|
| ICC monotonicity | ICC(CV=0.10) ≥ ICC(CV=0) + 0.15 | REs must create observable variance |

### Ablations

| Test | Criterion | Rationale |
|------|-----------|-----------|
| Phase 2A OFF | Event fraction ≤ 0.02 | No false positives |
| Phase 1 OFF | ICC(OFF) < 0.3 × ICC(ON) | Smooth variance disappears |
| Coupling smoke | Params stable across CV settings | No strong confounding |

---

## Inference Methods

### 1. Mixed Model (Plate A → ICC)

**Method**: Simple variance decomposition
- Between-well variance: `var(mean_per_well)`
- Within-well variance: `var(residuals_per_well)`
- ICC = `var_between / (var_between + var_within)`

**Why not full mixed model?** Could use `statsmodels.MixedLM` but variance decomposition is simpler, deterministic, and sufficient for ICC estimation.

### 2. Survival Fit (Plate C → λ0, threshold, p)

**Method**: Maximum likelihood with discrete-time hazard model
- Hazard: `λ(t) = min(cap, λ0 * ((max(0, S(t) - threshold) / (1 - threshold))^p))`
- Grid search over:
  - Threshold: [0.3, 0.9] (10 points)
  - p: [1.0, 4.0] (7 points)
  - λ0: [0.001, 1.0] log-scale (8 points)
- Log-likelihood: Sum over wells of `log(P(event at t))` or `log(P(survive to end))`

**Why grid search?** Avoids gradient issues with survival models, deterministic, and fast enough for ~500 evaluations.

### 3. Held-Out Prediction (Plate B)

**Method**: Forward simulation with recovered params
- For each well, compute `P(survive to end)` using stress trajectory S(t)
- Predicted fraction = `Σ(1 - P(survive)) / n_wells`
- Compare to empirical fraction

---

## Diagnostics for Failure Modes

If tests fail, the report suggests likely causes:

### Threshold Recovery Failed

- **Symptom**: Recovered threshold >> 0.10 error from truth
- **Likely cause**: Stress proxy not informative, or hazard cap dominates
- **Fix**: Check that stress metric (er_stress, mito_dysfunction) varies meaningfully in Plate C

### Sharpness Recovery Failed

- **Symptom**: Recovered p >> 1.0 error from truth
- **Likely cause**: Regime C doses too similar (need more stress variation)
- **Fix**: Increase dose range in high_stress_event_rich regime

### Baseline Hazard Recovery Failed

- **Symptom**: Recovered λ0 outside factor 3 of truth
- **Likely cause**: Coupling between REs and stress dynamics
- **Fix**: Run coupling smoke test; check if Phase 1 REs shift stress trajectories

### Prediction Failed

- **Symptom**: Predicted fraction >> 0.15 error from empirical
- **Likely cause**: Model doesn't generalize (overfitting Plate C)
- **Fix**: Increase replicates in Plate B; check if Plate B stress regime is truly "between" A and C

---

## Running in CI (Small Mode)

The config uses **48 wells per regime** for fast tests (~2-3 minutes total). For production:

```yaml
global:
  total_wells_per_regime: 96  # Or 144 for more power
```

This increases statistical power but runtime scales linearly.

---

## Extending to Phase 2B (Catastrophes)

If you add a third variance source (e.g., rare catastrophic events), you'll need:

1. **Regime D**: Catastrophe-enriched regime (long duration, high operational risk)
2. **Inference**: Separate catastrophe rate from commitment hazard (different time scales)
3. **Acceptance**: Prove all three sources are identifiable and independent

**Don't add Phase 2B until Phase 2A identifiability is proven.** Otherwise you're adding a third variance class before separating the first two.

---

## References

- Phase 1 implementation: `src/cell_os/hardware/stochastic_biology.py`
- Phase 2A implementation: `src/cell_os/hardware/stress_mechanisms/er_stress.py`, `mito_dysfunction.py`
- Commitment contracts: `tests/contracts/test_er_commitment_contracts.py`, `test_mito_commitment_contracts.py`

---

## Questions?

If the suite fails and you're unsure why, check:
1. `report.md` for specific failure diagnostics
2. `inference_results.json` for raw numbers
3. `observations.csv` and `events.csv` for data quality issues

If you suspect a simulator bug (not just parameter tuning), file an issue with:
- Config used
- Seed
- Full report.md output
- Specific acceptance criterion that failed
