# Aspiration Uncertainty Architecture - Complete Implementation

## Status: ✓ ALL STEPS DONE

**Date**: 2025-12-23
**Scope**: End-to-end implementation of aspiration position artifacts with full uncertainty quantification

---

## Overview

This document summarizes the complete 4-step implementation of aspiration uncertainty:
1. **Encode gamma as prior** (epistemic uncertainty)
2. **Push ridge into variance ledger** (ridge computation)
3. **Add calibration protocol hook** (Bayesian update)
4. **Variance ledger architecture** (make uncertainty felt)

Each step built on the previous, transforming aspiration artifacts from a deterministic model into a full uncertainty-aware system with calibration hooks and transparent variance accounting.

---

## Step #1: Encode Gamma as Prior ✓

**Goal**: Treat gamma (gradient shape exponent) as sampled random variable, not fitted parameter.

**Problem**: Parameter identifiability ridge - gamma and base_detach trade off, cannot fit both uniquely from Cell Painting measurements.

**Solution**: Sample gamma once per run from lognormal prior:
- Prior: `Lognormal(mean=1.0, CV=0.35)`, clipped to [0.3, 3.0]
- Sampled deterministically given seed + instrument_id
- Represents "this instrument instance" with unknown calibration

**Key files**:
- `src/cell_os/hardware/aspiration_effects.py`: Added `sample_gamma_from_prior()`
- `tests/unit/test_aspiration_gamma_prior.py`: 7 tests, all passing
- `docs/ASPIRATION_GAMMA_AS_PRIOR.md`: Full documentation

**Key insight**: Don't pretend to fit what we can't - encode the uncertainty explicitly.

---

## Step #2: Push Ridge into Variance Ledger ✓

**Goal**: Compute uncertainty in CP quality metrics induced by gamma prior.

**Problem**: If gamma has ±35% CV, how much does that uncertainty propagate to segmentation_yield and noise_mult?

**Solution**: Two-point bracket method:
1. Evaluate metrics at 5th percentile of gamma prior (gamma_low ≈ 0.58)
2. Evaluate metrics at 95th percentile of gamma prior (gamma_high ≈ 1.73)
3. Compute half-range as uncertainty estimate
4. Convert to CV: `half_range / nominal`

**Key files**:
- `src/cell_os/hardware/aspiration_effects.py`: Added `compute_gamma_ridge_uncertainty()`
- `src/cell_os/hardware/assays/cell_painting.py`: Wired into `_compute_cp_quality_metrics()`
- `tests/unit/test_aspiration_ridge_uncertainty.py`: 5 tests, all passing
- `docs/ASPIRATION_RIDGE_IN_VARIANCE_LEDGER.md`: Full documentation

**Key insight**: Ridge is EPISTEMIC uncertainty (calibration), not aleatoric (randomness).

---

## Step #3: Add Calibration Protocol Hook ✓

**Goal**: Allow system to learn from microscopy evidence and narrow gamma prior.

**Problem**: How do we update gamma prior when we run a calibration plate with microscopy?

**Solution**: Lightweight Bayesian update:
1. Define forward model: `f(gamma) = predicted_curvature`
2. Grid over gamma (200 points)
3. Evaluate posterior: `posterior(g) ∝ prior(g) * likelihood(g | evidence)`
4. Fit lognormal to posterior moments
5. Return updated prior with full provenance

**Evidence format**: Single scalar (curvature = (mid - right) / (left - right) at cols 6, 12, 19)

**Key files**:
- `src/cell_os/hardware/aspiration_effects.py`: Added `GammaPrior` dataclass, `update_gamma_prior_from_microscopy()`
- `tests/unit/test_aspiration_calibration_hook.py`: 5 tests, all passing
- `docs/ASPIRATION_CALIBRATION_HOOK_COMPLETE.md`: Full documentation

**Key insight**: Calibration updates narrow uncertainty AND maintain full audit trail (provenance).

---

## Step #4: Variance Ledger Architecture ✓

**Goal**: Make uncertainty "felt" through explain_difference() - not just warnings, but quantitative variance decomposition.

**Problem**: How do we communicate uncertainty in a way that's actionable (not vibes)?

**Solution**: Structured variance ledger with three kinds:
- **MODELED**: Deterministic effects that happened in this run
- **ALEATORIC**: Irreducible randomness (well-to-well noise)
- **EPISTEMIC**: Calibration uncertainty (reducible with more data)

**Architecture**:
```python
@dataclass
class VarianceContribution:
    term: str                     # e.g., VAR_CALIBRATION_ASPIRATION_RIDGE
    metric: str                   # e.g., segmentation_yield
    kind: VarianceKind            # modeled, aleatoric, epistemic
    effect_type: EffectType       # delta, multiplier, cv, var
    value: float                  # magnitude
    scope: str                    # per_well, per_plate, per_run, per_instrument
    context: dict                 # metadata

class VarianceLedger:
    def record(contribution): ...
    def query(well_id, metric): ...
    def summarize(well_id, metric): ...

def explain_difference(ledger, well_a, well_b, metric) -> dict:
    """
    Decompose difference into:
    - delta_modeled: Deterministic prediction
    - uncertainty_aleatoric_cv: Randomness
    - uncertainty_epistemic_cv: Calibration uncertainty
    - top_terms: Ranked contributors
    """
```

**Key files**:
- `src/cell_os/uncertainty/variance_ledger.py`: Full implementation (264 lines)
- `src/cell_os/hardware/assays/cell_painting.py`: Wired ledger recording into `_compute_cp_quality_metrics()`
- `scripts/demo_variance_ledger.py`: Working demo with example output
- `tests/unit/test_variance_ledger.py`: 6 tests, all passing
- `docs/VARIANCE_LEDGER_COMPLETE.md`: Full documentation

**Key insight**: Instrument report format (quantitative) beats vibes summary (qualitative).

---

## Example: Complete Workflow

### 1. Sample gamma (Step #1)
```python
from cell_os.hardware.aspiration_effects import sample_gamma_from_prior, GammaPrior

prior = GammaPrior()  # Default: Lognormal(mean=1.0, CV=0.35)
gamma = sample_gamma_from_prior(seed=42, prior=prior)
# → gamma = 1.027 (deterministic given seed)
```

### 2. Compute ridge uncertainty (Step #2)
```python
from cell_os.hardware.aspiration_effects import compute_gamma_ridge_uncertainty

ridge = compute_gamma_ridge_uncertainty(
    edge_tear_score=0.0108,
    bulk_shear_score=0.0014,
    debris_load=0.15,
    gamma_prior_cv=0.35
)
# → {'segmentation_yield_cv': 0.1211, 'noise_multiplier_cv': 0.0002, ...}
```

### 3. Update prior from microscopy (Step #3)
```python
from cell_os.hardware.aspiration_effects import update_gamma_prior_from_microscopy

# Measure curvature from microscopy calibration plate
curvature = (damage_mid - damage_right) / (damage_left - damage_right)

updated_prior, report = update_gamma_prior_from_microscopy(
    prior=prior,
    evidence_curvature=curvature,
    evidence_uncertainty=0.10,
    plate_id="CAL_2024-12-23_001"
)

print(report['provenance'])
# → "Prior updated: mean 1.00→1.15, CV 0.35→0.25 (sigma reduced 27.5%)
#    based on microscopy CAL_2024-12-23_001"
```

### 4. Query variance ledger (Step #4)
```python
from cell_os.uncertainty.variance_ledger import VarianceLedger, explain_difference

# Create ledger and run simulation
vm.variance_ledger = VarianceLedger()
# (Simulation runs, ledger automatically populated by Cell Painting measure())

# Explain difference between wells
explanation = explain_difference(vm.variance_ledger, "A1", "A24", "noise_mult")

print(explanation['summary'])
# → Difference in noise_mult: A1 vs A24
#
#   Modeled difference: +0.0008
#   Uncertainty: aleatoric ±0.0000 (CV 0.0%), epistemic ±0.0003 (CV 0.0%)
#
#   Primary drivers:
#     - VAR_INSTRUMENT_ASPIRATION_POSITION: +0.0008 (100% of modeled delta)
#
#   Uncertainty breakdown:
#     - Aleatoric (randomness): 0.0% of total uncertainty
#     - Epistemic (calibration): 100.0% of total uncertainty
```

---

## Key Design Principles

### 1. Honest Uncertainty
- Don't pretend to know what we don't (gamma is a prior, not fitted)
- Don't hide uncertainty in "model parameters" (make it explicit in ledger)
- Don't claim calibration without evidence (default prior is uninformative)

### 2. Separation of Concerns
- **Physics**: What happens (aspiration creates detachment)
- **Calibration**: What we don't know (gamma has ±35% CV)
- **Accounting**: How uncertainty propagates (variance ledger)

### 3. Actionable Output
- **Modeled effects**: Deterministic predictions (what we simulated)
- **Aleatoric uncertainty**: Randomness (increase sample size to reduce)
- **Epistemic uncertainty**: Calibration (run microscopy to reduce)

### 4. Provenance Tracking
- Every calibration update has full audit trail (who, what, when, why)
- Every variance contribution has context (well_id, sampled_gamma, etc.)
- Every metric has traceable sources (which terms contributed)

---

## Tests Summary

**Total tests written**: 23
**All tests passing**: ✓

### Step #1 Tests (7 tests)
- `test_aspiration_gamma_prior.py`
- Key test: `test_ridge_persists_with_gamma_sampled` (protects identifiability)

### Step #2 Tests (5 tests)
- `test_aspiration_ridge_uncertainty.py`
- Key test: `test_ridge_zero_when_no_prior_uncertainty` (validates boundary)

### Step #3 Tests (5 tests)
- `test_aspiration_calibration_hook.py`
- Key test: `test_uninformative_evidence_leaves_prior_unchanged` (protects against runaway updates)

### Step #4 Tests (6 tests)
- `test_variance_ledger.py`
- Key test: `test_explain_difference_combines_aleatoric_and_epistemic_in_quadrature` (validates math)

---

## Files Created/Modified

### Core Physics
- `src/cell_os/hardware/aspiration_effects.py` (MODIFIED, 947 lines)
  - Added `GammaPrior` dataclass
  - Added `sample_gamma_from_prior()`
  - Added `update_gamma_prior_from_microscopy()`
  - Added `compute_gamma_ridge_uncertainty()`
  - Added `get_edge_damage_contribution_to_cp_quality()`

### Uncertainty Infrastructure
- `src/cell_os/uncertainty/variance_ledger.py` (NEW, 264 lines)
  - `VarianceKind`, `EffectType`, `VarianceContribution`
  - `VarianceLedger` (record, query, summarize)
  - `explain_difference()` (decomposition + instrument report)

### Integration
- `src/cell_os/hardware/assays/cell_painting.py` (MODIFIED)
  - Added variance ledger imports
  - Modified `_compute_cp_quality_metrics()` to accept ledger
  - Added ledger recording for edge damage + ridge

### Tests
- `tests/unit/test_aspiration_gamma_prior.py` (NEW, 233 lines)
- `tests/unit/test_aspiration_ridge_uncertainty.py` (NEW, 168 lines)
- `tests/unit/test_aspiration_calibration_hook.py` (NEW, 286 lines)
- `tests/unit/test_variance_ledger.py` (NEW, 287 lines)

### Demos
- `scripts/demo_variance_ledger.py` (NEW, 164 lines)

### Documentation
- `docs/ASPIRATION_PARAMETER_IDENTIFIABILITY.md` (NEW)
- `docs/ASPIRATION_GAMMA_AS_PRIOR.md` (NEW)
- `docs/ASPIRATION_RIDGE_IN_VARIANCE_LEDGER.md` (NEW)
- `docs/ASPIRATION_CALIBRATION_HOOK_COMPLETE.md` (NEW)
- `docs/VARIANCE_LEDGER_COMPLETE.md` (NEW)
- `docs/ASPIRATION_UNCERTAINTY_COMPLETE.md` (NEW, this document)

---

## What This Enables

### Before (deterministic model):
```python
# Aspiration creates L-R gradient
# gamma = 1.0 (fixed)
# No uncertainty quantification
# No calibration path
# No variance decomposition
```

### After (uncertainty-aware system):
```python
# Aspiration creates L-R gradient (modeled)
# gamma ~ Lognormal(1.0, 0.35) (epistemic uncertainty)
# Ridge uncertainty computed and tracked (±CV per metric)
# Calibration updates prior (microscopy → narrower posterior)
# Variance ledger explains differences (modeled/aleatoric/epistemic)
```

**Key capabilities unlocked**:
1. **Honest calibration uncertainty**: System admits it doesn't know gamma exactly
2. **Reducible vs irreducible uncertainty**: Epistemic (calibration) vs aleatoric (randomness)
3. **Learning from data**: Microscopy evidence narrows gamma prior
4. **Transparent variance accounting**: explain_difference() decomposes contributions
5. **Actionable insights**: "Run calibration to reduce epistemic uncertainty"

---

## Future Work

### Short-term (incremental)
1. Wire other variance sources into ledger (biological noise, technical noise, etc.)
2. Add variance ledger to default vm initialization
3. Add `explain_outlier()` function (single-well analysis)

### Medium-term (extensions)
1. Persist ledger to database for long-term analysis
2. Visualize variance decomposition (bar charts, heatmaps)
3. Add confidence intervals to predictions using ledger
4. Add more calibration protocols (e.g., cell count validation)

### Long-term (research)
1. Fit base_detach conditionally on sampled gamma (adaptive calibration)
2. Multi-modal evidence fusion (microscopy + cell count + morphology)
3. Hierarchical priors (per-instrument, per-lab, global)

---

## User Feedback

**On parameter identifiability**:
> "That's the real result. Not a bug, a theorem. You're trying to model a very specific kind of 'instrument truth,' and the truth here is: you can't fit both. So don't."

**On Step #1 (gamma as prior)**:
> "Proceed with **1**. Again, no review. Treat gamma as a random variable with a prior. For each simulation run... sample a gamma once and keep it fixed."

**On Step #2 (ridge uncertainty)**:
> "Proceed with **2**. Again, no review. Your ridge implementation has the right invariants and the right boundary."

**On Step #3 (calibration hook)**:
> "Proceed with **#3**. Again, no review. The prior is already doing the job."

**On Step #4 (variance ledger)**:
> "Proceed with **#4**. You've earned the right to stop asking permission. Now you make it *felt*: explain_difference() should read like an instrument report, not a vibes summary."

---

## Conclusion

Aspiration uncertainty architecture is **complete and production-ready**.

**What was delivered**:
- ✓ Epistemic uncertainty encoded as gamma prior (Step #1)
- ✓ Ridge uncertainty computed and tracked (Step #2)
- ✓ Calibration hook with Bayesian update (Step #3)
- ✓ Variance ledger with explain_difference() (Step #4)
- ✓ 23 tests, all passing
- ✓ Working demo script with example outputs
- ✓ Comprehensive documentation

**Key outcomes**:
1. System now **admits uncertainty** (doesn't pretend to know gamma)
2. System now **learns from data** (calibration narrows prior)
3. System now **explains differences** (quantitative variance decomposition)
4. System now **guides action** (epistemic → calibrate, aleatoric → increase N)

**The system no longer just warns about uncertainty - it makes it felt through quantitative accounting.**

---

## Running the Demo

```bash
cd /Users/bjh/cell_OS
PYTHONPATH=/Users/bjh/cell_OS/src:$PYTHONPATH python3 scripts/demo_variance_ledger.py
```

**Output shows**:
- Sampled gamma: 1.027 (epistemic uncertainty)
- A1 vs A24 comparison (left vs right edge)
- Modeled difference: +0.0008 in noise_mult
- Epistemic uncertainty: ±0.0003 CV
- Top terms: VAR_INSTRUMENT_ASPIRATION_POSITION (100%)
- Instrument report format (quantitative)

---

## Final Note

This implementation demonstrates a complete uncertainty quantification workflow:
1. **Identify degeneracy** (parameter identifiability investigation)
2. **Encode uncertainty** (gamma as prior)
3. **Propagate uncertainty** (ridge computation)
4. **Learn from data** (calibration hook)
5. **Communicate uncertainty** (variance ledger + explain_difference)

Each step built on rigorous testing and honest confrontation with what we don't know.

**The result: A system that doesn't hide uncertainty behind "model parameters" - it makes uncertainty explicit, quantifiable, and actionable.**
