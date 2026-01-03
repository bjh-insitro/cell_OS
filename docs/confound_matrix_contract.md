# Confound Matrix Contract

## Status: Locked (2025-12-29)

This document defines the **identifiability boundaries** of the cell_OS simulator. These are not bugs to fix - they are honest epistemic constraints that force agents to do real experimental design instead of magical inference.

## Summary Table

| Pair | Verdict | Multi-TP AUC | p-value | Required Intervention |
|------|---------|--------------|---------|----------------------|
| **Pair 1: EC50 shift vs Dose error** | **Confounded** | 0.025 | 1.0 | Calibration compounds OR dose verification |
| **Pair 2: Dose error vs Assay gain** | **Distinguishable** | 1.0 | 0.0 | None (cross-modal features sufficient) |
| **Pair 3: Death vs Debris** | **Confounded** | 0.0 | 1.0 | Empty-well controls OR background QC |

## Pair 1: EC50 Shift vs Dose Scale Error

**Construction:**
- Condition A: EC50 × 2, Dose × 1.0
- Condition B: EC50 × 1.0, Dose × 0.5

**Effect parity:** Both produce 2× rightward Hill shift (C/EC50 ratio matched)

**Why confounded:**
- Hill equation depends only on `dose / EC50` ratio
- Multiplying EC50 is observationally equivalent to dividing dose
- This is **scale symmetry** - a fundamental property of the Hill model

**What this means:**
- Agent cannot distinguish these from observations alone
- Must run calibration compounds (known potency) OR independent dose verification
- If this ever becomes distinguishable, assume implementation tell (seed leakage, batch asymmetry) until proven otherwise

**Regression test:** `test_pair1_remains_confounded()` in `test_confound_regression.py`

## Pair 2: Dose Error vs Assay Gain Shift

**Construction:**
- Condition A: Dose × 0.67 (biology changes)
- Condition B: Gain × 1.5 (readout scales)

**Effect parity:** Morphology intensity matched at 24h

**Why distinguishable:**
- Dose error: Both viability AND morphology change (biology)
- Gain shift: Only morphology changes (readout artifact)
- Cross-modal features (viability/morphology ratios) detect discordance

**What this means:**
- Multi-modal design is sufficient to separate instrument artifacts from biology
- Agent can infer gain drift from viability-morphology disagreement
- If this becomes confounded, measurement model collapsed to single scalar

**Regression test:** `test_pair2_remains_distinguishable()` in `test_confound_regression.py`

## Pair 3: Death vs Debris (Dual Parity)

**Construction:**
- Condition A (Death): viability × 0.80, morphology + 0.0
- Condition B (Debris): viability × 0.80, morphology + 0.0 (calibrated to match)

**Effect parity:** DUAL - both E[viability] AND E[morphology] matched at 24h

**Why confounded:**
- First-order information (means) identical by construction
- Second-order information (variance) underpowered with 3 replicates:
  - Death (multiplicative): var ∝ mean²
  - Debris (additive): var independent of mean
  - But with 3 replicates, std estimates have ~50% CV themselves
- Missing orthogonal observables:
  - No empty-well controls (background estimate)
  - No segmentation QC (foreground fraction, focus score)
  - No tail metrics beyond simple variance

**What this means:**
- Agent **cannot** distinguish "biological loss" from "additive junk" under dual parity
- This is NOT a bug - it's the honest answer given the observation model
- Agent **must** run empty-well controls or add background QC readouts
- **Deliberate trapdoor:** forces experimental design, not magical inference

**What NOT to do:**
- ❌ Feature engineer (add skewness, quantiles) to mine the same 3 replicates
- ❌ "Improve realism" in a way that leaks condition deterministically
- ✅ Add **orthogonal observable** (empty wells, segmentation metrics, background channel)

**Regression test:** `test_pair3_remains_confounded()` in `test_confound_regression.py`

## Locked Evaluation Protocol

```python
PROTOCOL = {
    'base_seed': 42,
    'dose_factors': [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
    'replicates_per_dose': 3,
    'plate_format': 96,
    'timepoints_single': [24.0],
    'timepoints_multi': [12.0, 24.0, 48.0],
    'cv_folds': 5,
    'cv_seed': 42,
    'permutations': 100,
    'perm_seed': 888,
}
```

## Exit Criteria

### Confounded (Pair 1, Pair 3):
- Multi-TP AUC < 0.65
- p-value > 0.1
- Cannot be separated from observations alone

### Distinguishable (Pair 2):
- Multi-TP AUC > 0.7
- p-value < 0.05
- Can be separated with current feature set

## Regression Tests

**File:** `tests/contracts/test_confound_regression.py`

**Run:** `python3 tests/contracts/test_confound_regression.py`

**Purpose:**
- Fail if Pair 1 becomes distinguishable (scale invariance broken)
- Fail if Pair 2 becomes confounded (cross-modal detection lost)
- Fail if Pair 3 becomes distinguishable without new observables (accidental tell)

## Policy Implications

1. **For Pair 1 (EC50 vs Dose):**
   - Agent must spend budget on calibration plate OR dose verification
   - Cannot "learn" to correct from data alone without cheating

2. **For Pair 2 (Dose vs Gain):**
   - Multi-modal design is sufficient
   - Agent can infer gain drift from cross-modal discordance

3. **For Pair 3 (Death vs Debris):**
   - Agent must schedule empty-well controls
   - Make "empty-well control" an explicit action with cost
   - Inference depends on having run the control, not mining features

## Future Extensions

### Pairs 4-6 (Planned):
- **Pair 4:** ER stress vs Mito dysfunction (mechanism disambiguation)
- **Pair 5:** Batch effect vs Biology (instrument vs compound)
- **Pair 6:** Plating density vs Confluence (initial condition vs dynamics)

### Adding New Pairs:
1. Define manipulations with **effect parity** (matched on key observable)
2. Run with locked protocol
3. Classify as Confounded / Distinguishable / Suggestive
4. If Confounded: document required intervention
5. Add regression test to prevent accidental disambiguation

## References

- **Test implementation:** `tests/contracts/test_attack3_confound_matrix_v2.py`
- **Regression tests:** `tests/contracts/test_confound_regression.py`
- **Results:** `/tmp/confound_matrix_results.json`

## Version History

- **2025-12-29:** Initial lock (Phase 2 complete, Pairs 1-3 tested)
- **Pair 1 AUC:** 0.025 (p=1.0) - Confounded ✓
- **Pair 2 AUC:** 1.0 (p=0.0) - Distinguishable ✓
- **Pair 3 AUC:** 0.0 (p=1.0) - Confounded ✓
