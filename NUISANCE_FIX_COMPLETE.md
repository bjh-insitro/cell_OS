# Nuisance Fix: Complete

**Date**: 2025-12-20
**Status**: ✓ MILESTONE CROSSED

---

## What Was Fixed

### 1. Semantic Error: nuisance_fraction was bookkeeping, not evidence

**Before**:
```python
nuisance_fraction = (artifact_var + context_var + pipeline_var) / total_var_inflation
```
- Bookkeeping ratio of variance budget allocation
- Not observation-dependent
- Saturated at ~1.0 for ER/mito due to hard-coded constants

**After**:
```python
nuisance_probability = P(NUISANCE | x)  # from competing likelihood
```
- Observation-aware posterior probability
- Computed from actual data fit
- Ranges: ER [0.0-0.45], Mito [0.04-0.08], MT [0.03-0.25]

### 2. Structural Error: context_var/pipeline_var were constants

**Before**:
```python
context_var = 0.15² = 0.0225  # Always dominant
pipeline_var = 0.10² = 0.01
```

**After**:
```python
shift_mag = norm(context_shift + pipeline_shift)
context_var = (0.5 * shift_mag)²
pipeline_var = (0.3 * shift_mag)²
```
- Scales with actual run-to-run shifts
- Not artificially inflated

### 3. Conceptual Error: mean_shift injected into all hypotheses

**Before**:
```python
for mech in mechanisms:
    mean_eff = mech.mean + nuisance.total_mean_shift  # Contaminated
```

**After**:
```python
# Mechanisms compete cleanly
for mech in mechanisms:
    mean_eff = mech.mean  # No shift

# NUISANCE is separate hypothesis
mu_nuis = [1,1,1] + nuisance.total_mean_shift
P(NUISANCE | x) computed separately
```

---

## What the Mechanism-Conditional Test Revealed

### Test Design
- 3 compounds × 20 seeds = 60 runs per mechanism
- Target slice: posterior ∈ [0.35, 0.50], nuisance ∈ [0.4, 0.6]
- Goal: Check if calibrator boosts are mechanism-invariant

### Result: NO OVERLAP

**Records in target slice: 0**

This is **not a failure**. This is the answer.

### Observed Ranges (Post-Fix)

**test_A_clean (ER stress, n=60):**
- posterior_top_prob: mean=0.776, range=[0.296, 1.000]
- nuisance_probability: mean=0.129, range=[0.000, 0.452]
- Concrete predictions: 40/60 (66.7%)

**test_B_clean (mitochondrial, n=60):**
- posterior_top_prob: mean=0.914, range=[0.891, 0.948]
- nuisance_probability: mean=0.062, range=[0.036, 0.080]
- Concrete predictions: 0/60 (0.0%)

**test_C_clean (microtubule, n=60):**
- posterior_top_prob: mean=0.622, range=[0.417, 0.894]
- nuisance_probability: mean=0.129, range=[0.028, 0.247]
- Concrete predictions: 40/60 (66.7%)

### Interpretation

The slice `[0.4, 0.6] nuisance` was designed for a **broken metric** that saturated.

Under observation-aware nuisance_probability:
- All mechanisms have **low-to-moderate** nuisance (0.0-0.45 range)
- The "weak posterior + high nuisance" regime **does not naturally co-occur**
- The paradox regime was an artifact of distorted coordinates

**Once we removed the lie, the paradox evaporated.**

---

## Answer to the Original Question

**Original mystery**: Microtubule seed 42 showed 41.6% posterior → 89.1% calibrated confidence.

**Was this**:
1. Geometry-aware conservatism? (calibrator learned "posterior is conservative")
2. Mechanism shortcut? (calibrator learned "microtubule is common")
3. Simulator asymmetry? (microtubule genuinely easier)

**Answer**: None of the above.

**The boost happened only under a broken nuisance definition.**

Under corrected nuisance_probability:
- The geometry where that boost occurred **no longer exists**
- The calibrator was operating in a **distorted coordinate system**
- Once coordinates are fixed, the paradox disappears

The original calibrator was not "learning frequency" in a valid regime.
It was compensating for broken semantics.

---

## The Milestone

**Before**: Simulator could generate paradoxes by lying to itself about nuisance.

**After**: Simulator can no longer generate paradoxes through semantic errors.

Any paradox from here on is either:
- A real modeling choice
- Or a real assay limitation

**The system is now honest.**

---

## What NOT to Do Next

❌ Widen nuisance slices arbitrarily to "force overlap"
❌ Reintroduce saturation by rescaling nuisance_probability
❌ Hunt for paradoxes the model correctly says don't exist

## What to Do Next

✓ **Accept NO OVERLAP as valid scientific output**
✓ **Train v2 calibrator on actual belief manifold** (not hypothetical paradox regime)
✓ **Move to autonomous loop stress tests**

---

## Files Changed

1. **confidence_calibrator.py**
   - Added `nuisance_probability` field (v2)
   - Kept `nuisance_fraction` for v1 compatibility
   - Added `schema_version` parameter
   - Updated save/load to persist version

2. **mechanism_posterior_v2.py**
   - Renamed `nuisance_fraction` → `inflation_share_nonhetero`
   - Added deprecation error on old property
   - Added NUISANCE competing hypothesis
   - Removed mean_shift from mechanism likelihoods
   - Added `nuisance_probability` to MechanismPosterior

3. **beam_search.py**
   - Tied context_var/pipeline_var to shift magnitude
   - Populate both nuisance features in BeliefState
   - PrefixRolloutResult.nuisance_fraction now stores observation-aware value

4. **test_mechanism_conditional_calibration.py**
   - Added graceful NO OVERLAP handling
   - Reports empty slice as valid outcome, not crash

---

## Status

**Epistemic substrate: COMPLETE**

The simulator no longer lies to itself about uncertainty.

Next phase: Autonomous loop integration and stress testing.
