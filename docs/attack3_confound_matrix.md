# Attack 3: Confound Matrix - Identifiability Boundaries

## Purpose

Document which experimental confounds are **observationally equivalent** in cell_OS,
defining the epistemic contract between the simulator and the agent.

This tells the agent:
- What it **CAN** learn from observations alone
- What it **CANNOT** learn without external calibration/metadata
- When it must spend budget on calibration vs when it can infer causality

## Test Methodology

For each confound pair (A vs B):

1. **Generate dose-response data** with same seed for both conditions
   - 8-dose ladder (0-10× nominal EC50)
   - 3 replicates per dose
   - Stratified plate allocation
   - Multimodal readouts (viability + 5-channel morphology)

2. **Test distinguishability** using cross-validated permutation test
   - Features: Per-dose aggregates (prevents replicate leakage)
   - Classifier: Logistic regression with scaling inside CV
   - Null: 100 permutations of labels
   - Metric: AUC and p-value

3. **Verdict criteria**:
   - **Confounded**: AUC < 0.65 AND p > 0.1
     - Agent cannot distinguish → Requires external info
   - **Distinguishable**: AUC > 0.7 AND p < 0.05
     - Agent can learn correct action from observations
   - **Weakly distinct**: Between thresholds
     - Agent will struggle → Calibration recommended

## Confound Pairs Tested

### 1. EC50 Shift vs Dose Scale Error

**Manipulation:**
- A: EC50 × 2 (biology changes, dose accurate)
- B: Dose × 0.5 (biology constant, dose wrong)

**Mathematical equivalence:**
Both produce 2× rightward shift in Hill curve (same ratio C/EC50 at all doses).

**Result:** **CONFOUNDED**
- Single timepoint: Cannot distinguish
- Multiple timepoints: Cannot distinguish
- Temporal dynamics do NOT break equivalence

**Requires:** Calibration compounds with known sensitivity OR independent dose verification

**Biological interpretation:**
The simulator is scale-invariant under Hill model (as expected). This is honest -
real cells would also struggle without calibration compounds.

### 2. Dose Error vs Assay Gain Shift

**Manipulation:**
- A: Dose × 0.5 (less compound delivered)
- B: Assay gain × 2.0 (measurement sensitivity doubled)

**Why confounded:**
Both weaken observed morphology signal.

**Expected result:** **DISTINGUISHABLE** (viability unaffected by gain)
- Viability is a ratio measurement, not affected by intensity scaling
- Dose error affects viability, gain shift does not

**Breaks tie:** Viability signal (morphology/viability dissociation)

### 3. Viability Loss vs Background/Debris Increase

**Manipulation:**
- A: Viability × 0.7 (cells dying)
- B: Background + 30 (debris/dirty plates)

**Why potentially confounded:**
Both reduce signal quality.

**Expected result:** **DISTINGUISHABLE** (structure differs)
- Death: Multiplicative effect (scales with signal)
- Debris: Additive offset (constant across wells)
- Dose-response structure should differ

**Breaks tie:** Additive vs multiplicative structure across dose ladder

**If confounded:** Requires empty well background measurement

### 4. Stress-Specific Morphology vs Confluence Compression
**Status:** TODO

### 5. Batch "Cursed Day" vs Reagent Lot Effect
**Status:** TODO

### 6. Subpopulation Shift vs EC50 Shift
**Status:** TODO

## Identifiability Regression Test

For confounds verified as fundamentally indistinguishable (like EC50 vs Dose),
maintain a regression test that asserts:

```python
def test_identifiability_regression_ec50_vs_dose():
    """
    Regression: EC50 shift vs Dose error must remain confounded.

    Prevents accidentally introducing magic disambiguation.
    """
    measurements = generate_pair1_ec50_vs_dose(seed=42, timepoints=[12.0, 24.0, 48.0])
    auc, pval = test_distinguishability(measurements, timepoints=[12.0, 24.0, 48.0])

    # Assert confounded
    assert auc < 0.65, f"EC50 vs Dose became distinguishable (AUC={auc:.3f})"
    assert pval > 0.1, f"EC50 vs Dose became distinguishable (p={pval:.3f})"
```

This prevents:
- Accidentally adding absolute-concentration dependencies
- Introducing layer mismatches (dose affects one pathway, EC50 affects another)
- Creating false confidence in causal inference

## References

- Hill equation scale invariance: C/EC50 ratio determines effect
- Permutation test methodology: Phipson & Smyth (2010)
- Cross-validation for small N: Beleites et al. (2013)

## Change Log

- 2025-01-XX: Initial confound matrix framework
- 2025-01-XX: Pairs 1-3 implemented and tested
- 2025-01-XX: Pairs 4-6 TODO
