# Confidence Calibration Architecture

**Purpose**: Separate belief quality from task success. Learn when the posterior can be trusted.

## Three-Layer Architecture

### Layer 1: Inference (Bayesian Posterior)

**What it does**: Evaluates P(mechanism | features) via likelihood
**What it knows**: Mechanism signatures (μ_m, Σ_m), nuisance model (mean shifts, variance inflation)
**What it outputs**: Posterior probabilities over mechanisms

```python
posterior = compute_mechanism_posterior_v2(
    actin_fold=1.8,
    mito_fold=1.1,
    er_fold=1.0,
    nuisance=nuisance_model
)
# posterior.top_probability = 0.80  (MICROTUBULE)
```

**Critical**: This layer does NOT know:
- How often its predictions are correct
- Whether high nuisance invalidates its assumptions
- Context-dependent failure modes

### Layer 2: Reality (Calibration)

**What it does**: Maps belief state → P(correct)
**What it knows**: Empirical correctness rates from real experiments
**What it outputs**: Calibrated confidence

```python
belief_state = BeliefState(
    top_probability=0.80,
    margin=0.65,
    entropy=0.52,
    nuisance_fraction=0.53  # HIGH
)

calibrated_conf = calibrator.predict_confidence(belief_state)
# calibrated_conf = 0.52  (penalized for high nuisance)
```

**Allows inversions**:
- 80% posterior + 53% nuisance → 52% calibrated confidence
- 60% posterior + 10% nuisance → 70% calibrated confidence

This is NOT a bug. It's epistemic maturity.

### Layer 3: Decision (Governance)

**What it does**: Uses calibrated confidence to decide actions
**What it knows**: Cost/benefit of waiting, rescue options, commit thresholds
**What it outputs**: Actions (COMMIT, WAIT, RESCUE)

```python
if calibrated_conf > 0.85:
    action = "COMMIT"
elif calibrated_conf > 0.65 and cheapest_rescue_cost < threshold:
    action = "RESCUE"
else:
    action = "WAIT"
```

## Why Separation Matters

### Without Calibration (Layers Conflated)

```python
# BAD: Penalize inside posterior
if nuisance_fraction > 0.5:
    posterior.top_probability *= 0.7  # Ad-hoc penalty
```

**Problems**:
- Self-contradictory (posterior no longer Bayesian)
- Can't learn from data
- Penalty arbitrary (why 0.7?)

### With Calibration (Layers Separated)

```python
# GOOD: Posterior stays clean
posterior = compute_mechanism_posterior_v2(...)  # Pure inference

# Reality layer learns penalty empirically
calibrated_conf = calibrator.predict_confidence(belief_state)
```

**Benefits**:
- Posterior remains interpretable
- Calibration learned from correctness rates
- Can improve calibrator without touching inference

## Stratified Training

**Critical**: Do NOT train on IID samples only.

### Three Strata

1. **Low nuisance** (n=50)
   - Clean context (strength=0.5)
   - Early timepoint (10h, artifacts minimal)
   - Reference dose
   - Expected: High accuracy, high confidence justified

2. **Medium nuisance** (n=50)
   - Typical context (strength=1.0)
   - Mid timepoint (14h)
   - Varied dose
   - Expected: Moderate accuracy, moderate confidence

3. **High nuisance** (n=50)
   - Cursed context (strength=2.5, strong biases)
   - Late timepoint (18h, high heterogeneity from death)
   - Weak dose (ambiguous signal)
   - Expected: Lower accuracy, calibrator learns to be conservative

### Why Stratification Matters

Without stratification:
- Model calibrated for average case
- Overconfident in high-nuisance edge cases
- Fails exactly when you need it

With stratification:
- Explicit representation of hard cases
- Calibrator learns: "high nuisance → lower trust"
- Conservative where it matters

## Acceptance Criteria

Calibrator is "good enough" when:

1. **Overall calibration**: ECE < 0.1 (Expected Calibration Error)
   - Reliability curves near diagonal
   - Mean confidence ≈ mean accuracy

2. **High-nuisance bins conservative**: Not overconfident
   - Mean confidence ≤ mean accuracy + 0.05
   - If wrong, at least uncertain

3. **Low-nuisance bins maintain confidence**: Not paranoid
   - High accuracy reflected in high confidence
   - Don't throw away good signal

## Evaluation Metrics

### Expected Calibration Error (ECE)

Bins predictions by confidence, compares mean confidence to mean accuracy:

```
ECE = Σ (n_bin / n_total) * |mean_conf_bin - mean_acc_bin|
```

Target: ECE < 0.1

### Brier Score

Mean squared error of probability predictions:

```
Brier = mean((y_pred - y_true)²)
```

Lower is better. Range [0, 1].

### Stratified Metrics

Report ECE, Brier, accuracy, mean confidence **per stratum**:

```
LOW NUISANCE:
  Accuracy: 0.920
  Mean confidence: 0.900
  ECE: 0.025
  ✓ Well-calibrated

HIGH NUISANCE:
  Accuracy: 0.620
  Mean confidence: 0.580
  ECE: 0.048
  ✓ Conservative (conf < acc + 0.05)
```

## Integration with Posterior

### Before (Raw Posterior)

```python
posterior = compute_mechanism_posterior_v2(...)
confidence = posterior.top_probability  # 0.80

# Problem: Doesn't account for nuisance
```

### After (Calibrated)

```python
posterior = compute_mechanism_posterior_v2(...)

belief_state = BeliefState(
    top_probability=posterior.top_probability,
    margin=posterior.margin,
    entropy=posterior.entropy,
    nuisance_fraction=nuisance.nuisance_fraction,
    timepoint_h=14.0,
    viability=0.85
)

calibrated_conf = calibrator.predict_confidence(belief_state)

# Use calibrated_conf for decisions
posterior.calibrated_confidence = calibrated_conf
```

## Freezing and Versioning

Once trained, **freeze the calibrator**:

```python
calibrator.freeze()
calibrator.save('confidence_calibrator_v1.pkl')
```

**Treat like labware**:
- Do not retrain casually
- If retraining needed, version (v2, v3, ...)
- Document why (e.g., "added new mechanisms", "expanded to new cell lines")

## Expected Beam Search Behavior Changes

With calibrated confidence, expect:

1. **Fewer early commits in high-nuisance runs**
   - Raw: 80% posterior → COMMIT
   - Calibrated: 80% posterior + 53% nuisance → 52% confidence → WAIT

2. **No collapse in easy cases**
   - Raw: 95% posterior → COMMIT
   - Calibrated: 95% posterior + 10% nuisance → 92% confidence → COMMIT

3. **Rescue plans chosen for right reasons**
   - Dominant uncertainty source identified
   - Cheapest rescue targets that source

## When You Know It's Working

System is "teachable" when:

- Planner hesitates in exactly the cases you would hesitate
- High confidence reflects actual correctness
- No suspicious certainty (high conf + high nuisance)

The system isn't just correct. It **knows when it doesn't know**.

That's the difference between a classifier and a scientist.
