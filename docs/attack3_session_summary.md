# Attack 3 Session Summary: Confound Matrix Framework

## What We Built

A systematic framework for testing **observational equivalences** in cell_OS, defining the epistemic contract between simulator and agent.

## Key Deliverables

### 1. Fixed Three Critical Bugs in Confound Testing

**Bug 1: Test Harness Leakage**
- **Problem**: Training on full data, testing on same data → AUC = 1.0 by memorization
- **Symptom**: Null AUC ~0.99 (random labels fit perfectly)
- **Root cause**: No train/test split, global preprocessing before CV
- **Fix**: Cross-validated pipeline with scaling inside folds

**Bug 2: EC50 Manipulation Broken**
- **Problem**: Test modified non-existent `compound_sensitivity` key
- **Symptom**: EC50 shift had zero effect on biology
- **Root cause**: YAML uses `cell_line_ic50_modifiers`, code expects `cell_line_sensitivity`
- **Fix**: Create correct key structure: `cell_line_sensitivity[compound][cell_line] = multiplier`

**Bug 3: Spurious Seed Variance**
- **Problem**: Condition A used seed=42, Condition B used seed=43
- **Symptom**: Perfect AUC = 1.0 even with healthy null
- **Root cause**: Different run contexts allowed classifier to learn seed differences
- **Fix**: Use same base seed for both conditions (only manipulation differs)

**Impact**: These bugs would have generated **false certainty** - claiming the agent can distinguish confounds when it actually cannot. This destroys research programs.

### 2. Validated Scale Invariance

**Mathematical expectation**:
- EC50 × 2 and Dose × 0.5 should be observationally equivalent
- Hill equation: Effect = f(C/EC50, hill_slope)
- Identical C/EC50 ratios → Identical curves

**Empirical result after fixes**:
```
Single timepoint:  AUC = 0.125, p = 0.96 → Confounded ✓
Multiple timepoints: AUC = 0.025, p = 1.00 → Confounded ✓
Null distribution: ~0.5 ± 0.23 (healthy)
```

**Interpretation**:
- ✅ Simulator is scale-invariant (honest)
- ✅ Agent correctly cannot distinguish
- ✅ Requires calibration compounds or dose verification

This is the **right answer**. Not a bug, a feature.

### 3. Confound Matrix Framework

**File**: `tests/contracts/test_attack3_confound_matrix.py`

**Features**:
- Systematic test runner for multiple confound pairs
- Cross-validated permutation test (no leakage)
- Clear verdict criteria (confounded/distinguishable/weak)
- Documents what breaks ties and what metadata is required

**Pairs implemented**:
1. ✅ EC50 shift vs Dose error (Pair 1) - **Confounded**
2. ⏳ Dose error vs Assay gain (Pair 2) - Framework ready
3. ⏳ Death vs Debris (Pair 3) - Framework ready
4. 🔲 Stress morphology vs Confluence (Pair 4) - TODO
5. 🔲 Batch cursed day vs Reagent lot (Pair 5) - TODO
6. 🔲 Subpopulation shift vs EC50 (Pair 6) - TODO

### 4. Identifiability Regression Test

**File**: `tests/contracts/test_identifiability_regression.py`

**Purpose**: Prevent accidental "magic disambiguation"

**What it does**:
- Asserts EC50 vs Dose remains confounded (AUC < 0.65, p > 0.1)
- Fails loudly if simulator gains absolute-concentration dependencies
- Catches layer mismatches (dose affects one pathway, EC50 affects another)
- Protects against false confidence in causal inference

**Test result**: ✅ PASS (AUC = 0.025, p = 1.0)

### 5. Documentation

**File**: `docs/attack3_confound_matrix.md`

**Contents**:
- Test methodology
- Verdict criteria
- Confound pair descriptions
- Expected results and interpretations
- Required metadata for confounded pairs

## Lessons Learned

### 1. Null Distribution is Your Canary

A healthy null should be ~0.5 ± ~0.2:
- If null AUC > 0.9: You have data leakage
- If null std < 0.05: You're overfitting with high-dimensional noise

### 2. Same Seed for Both Conditions

Different seeds create spurious distinguishability from:
- Run context differences (incubator effects, EC50 multipliers)
- Plate allocation patterns (spatial confounds)
- Biological noise (lognormal multipliers)

Only the manipulation should differ, not the stochastic context.

### 3. Cross-Validation Must Be Leak-Proof

- Scale/normalize **inside** CV folds, not globally
- Aggregate replicates **before** splitting (avoid replicate leakage)
- Permute at correct level (dose-level, not well-level)
- Test on held-out data, never on training data

### 4. Confounded ≠ Failure

Observational equivalence is an **honest epistemic boundary**:
- Tells agent when it needs calibration
- Prevents false confidence
- Defines what external info is required

Real science admits what it cannot know.

## Next Steps

### Immediate (Finish Attack 3)

1. **Run Pairs 2-3** to test:
   - Dose vs Gain (should be distinguishable via viability)
   - Death vs Debris (should be distinguishable via additive/multiplicative structure)

2. **Implement Pairs 4-6**:
   - Stress morphology vs Confluence compression
   - Batch cursed day vs Reagent lot
   - Subpopulation shift vs EC50 shift

3. **Generate confound matrix table**:
   ```
   Confound Pair               1TP AUC  3TP AUC  Verdict         Required Metadata
   -------------------------------------------------------------------------------
   EC50 vs Dose                0.125    0.025    Confounded      Calibration cpds
   Dose vs Gain                 TBD      TBD     TBD             TBD
   Death vs Debris              TBD      TBD     TBD             TBD
   ...
   ```

### After Attack 3

4. **Attack 4**: Variance confounds
   - Biological variance vs technical variance
   - Replicate variance vs dose-response heterogeneity

5. **Integration with agent loop**:
   - Agent checks confound matrix before inferring causality
   - Auto-allocates budget to calibration when needed
   - Refuses to distinguish confounded pairs without external info

## Files Modified/Created

```
tests/contracts/
├── test_attack3_confound_matrix.py         (NEW - framework)
├── test_identifiability_regression.py      (NEW - regression test)
├── test_confound_ec50_vs_dose_error.py     (FIXED - all 3 bugs)
├── test_confound_diagnostic.py             (NEW - debugging tool)
└── test_confound_trace.py                  (NEW - internal state tracer)

docs/
├── attack3_confound_matrix.md              (NEW - documentation)
└── attack3_session_summary.md              (NEW - this file)
```

## Key Insight

**The simulator is honest about what it cannot distinguish.**

This is vastly more valuable than a simulator that produces false confidence by accidentally introducing magic disambiguation signals. We caught three such bugs early, before they ruined the research program.

The confound matrix will become the **epistemic contract** between simulator and agent:

> "Here is what you can infer from observations alone, and here is when you must spend budget on calibration."

That's how you build trustworthy autonomy.
