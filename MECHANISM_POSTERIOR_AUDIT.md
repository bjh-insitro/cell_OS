# Mechanism Posterior Audit - Current Behavior

**Date:** 2025-12-21
**File:** `src/cell_os/hardware/mechanism_posterior_v2.py`

---

## Input Space

**Channels:**
- `actin_fold` (float)
- `mito_fold` (float)
- `er_fold` (float)

**Normalization:**
- Fold-changes relative to baseline (ratio, not difference)
- Example: 1.0 = no change, 1.5 = 50% increase, 0.6 = 40% decrease

**Aggregation Level:**
- Per-condition averages (not raw wells)
- Already aggregated before mechanism classification

---

## Compression Step

**NOT cosine similarity** - uses proper Bayesian likelihood:

```python
# For each mechanism:
mean_eff = signature.to_mean_vector()  # [actin, mito, ER]
cov_eff = signature.to_cov_matrix() + heterogeneity
mvn = multivariate_normal(mean=mean_eff, cov=cov_eff)
likelihood[mech] = mvn.pdf(observed)

# Bayes rule:
posterior[mech] = likelihood[mech] * prior[mech] / Z
```

**Distance metric (implicit):**
- Mahalanobis distance through MVN likelihood
- NOT Euclidean - accounts for covariance structure
- Mechanism with tighter covariance gets higher likelihood for nearby observations

---

## What Is Returned

**Primary:** `MechanismPosterior` object containing:
- `probabilities: Dict[Mechanism, float]` - Bayesian posterior
- `observed_features: np.ndarray` - input [actin, mito, ER]
- `likelihood_scores: Dict[Mechanism, float]` - raw likelihoods
- `nuisance_probability: float` - P(NUISANCE | x)
- `calibrated_confidence: Optional[float]` - learned P(correct)

**Properties:**
- `top_mechanism` - argmax posterior
- `top_probability` - max posterior prob
- `margin` - gap between top-1 and top-2
- `entropy` - Shannon entropy of posterior

---

## Where Confidence Is Implicitly Assumed

### Problem 1: No confidence cap in ambiguous regions

**Current behavior:**
```python
posterior_probs = {m: unnormalized[m] / Z for m in mechanisms}
```

If two mechanisms have similar likelihood, Bayes rule still produces:
- Top-1: ~0.55
- Top-2: ~0.40
- Others: ~0.05

But nothing prevents:
- Top-1: 0.85
- Top-2: 0.10
- Others: 0.05

Even when `likelihood[top1] / likelihood[top2] ≈ 1.1` (barely distinguishable)

### Problem 2: No entropy floor

Posterior can be arbitrarily sharp (entropy → 0) even when:
- Multiple mechanisms fit data equally well
- Observation is equidistant from multiple centroids
- Covariances overlap substantially

### Problem 3: margin is computed but not enforced

```python
@property
def margin(self) -> float:
    sorted_probs = sorted(self.probabilities.values(), reverse=True)
    return sorted_probs[0] - sorted_probs[1]
```

This measures ambiguity but doesn't constrain it.

---

## Failure Mode Examples

### Case 1: Mechanisms with overlapping signatures

**Scenario:**
- MICROTUBULE: actin=1.6, mito=1.0, ER=1.0
- ER_STRESS: actin=1.0, mito=1.0, ER=1.5
- Observation: actin=1.3, mito=1.0, ER=1.2

**Current behavior:**
- MICROTUBULE: 0.60 (higher likelihood due to actin match)
- ER_STRESS: 0.35 (ER elevation pulls toward this)
- MITOCHONDRIAL: 0.05

**Problem:**
- Observation is **actually ambiguous** (between two mechanisms)
- But system reports 60% confidence
- No explicit `uncertainty` field

### Case 2: Observation in overlap region

**Scenario:**
- Two mechanisms with similar means but different variances
- Observation near both means
- One mechanism has slightly tighter covariance → gets higher likelihood

**Current behavior:**
- Tighter mechanism: 0.82
- Looser mechanism: 0.15
- Others: 0.03

**Problem:**
- High confidence (0.82) is due to covariance difference, not clear separation
- If variances were equal, would be ~0.50/0.50
- System doesn't flag this as ambiguous

---

## Identified Gaps

1. **No ambiguity metric** - margin exists but isn't used to constrain confidence
2. **No confidence cap** - high confidence possible even when gap is small
3. **No uncertainty field** - ambiguity is not explicitly represented
4. **No diagnostics** - classification events not logged to `diagnostics.jsonl`
5. **No overconfidence warning** - high confidence + low margin = warning opportunity

---

## Next Steps (Implementation)

1. Add **gap metric** - distance between top-2 likelihoods
2. Add **confidence cap** when gap < threshold
3. Add **uncertainty field** to posterior
4. Emit **classification diagnostics** to `diagnostics.jsonl`
5. Add **tests** for clear vs ambiguous cases

---

**Audit complete.** Ready to implement ambiguity awareness.
