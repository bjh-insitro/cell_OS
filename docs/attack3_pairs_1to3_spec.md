# Attack 3: Confound Matrix Pairs 1-3 Specification

## Locked Evaluation Protocol

All pairs use identical protocol parameters to ensure AUC comparability:

```python
PROTOCOL = {
    'base_seed': 42,                    # Same seed for both conditions
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

## Pair 1: EC50 Shift vs Dose Scale Error

### Manipulations
- **Condition A**: EC50 × 2.0, Dose × 1.0
- **Condition B**: EC50 × 1.0, Dose × 0.5

### Effect Parity
Matched on **C/EC50 ratio** - both produce 2× rightward Hill shift

### Features
- Base: Viability + 5 morphology channels
- No cross-modal or variance features needed

### Expected Verdict
**CONFOUNDED** - Scale invariance under Hill model

### Interpretation
- Mathematical equivalence: Effect = f(C/EC50)
- Agent cannot distinguish without calibration compounds
- This is honest - real cells would also struggle

### Required Metadata (if confounded)
Calibration compounds with known sensitivity OR independent dose verification

---

## Pair 2: Dose Error vs Assay Gain Shift

### Manipulations
- **Condition A**: Dose × 0.67, Gain × 1.0
- **Condition B**: Dose × 1.0, Gain × 1.5

### Effect Parity
Matched on **apparent morphology intensity** at 24h

### Key Test
Can agent detect **viability-morphology discordance**?
- Dose error: Biology changes → viability and morphology move together
- Gain shift: Readout scales → morphology changes, viability doesn't

### Features
- Base: Viability + 5 morphology channels
- **Cross-modal**: Morphology/viability ratios (CRITICAL for distinguishing)
- No variance features needed

### Expected Verdict
**DISTINGUISHABLE** via cross-modal features

### Breaks Tie (if distinguishable)
Viability is a ratio measurement (unaffected by gain), morphology is intensity (affected by gain)

### Required Metadata (if confounded)
Dose verification OR plate reference controls

---

## Pair 3: Viability Loss vs Background/Debris Increase

### Manipulations
- **Condition A**: Viability × 0.8, Background + 0
- **Condition B**: Viability × 1.0, Background + 25

### Effect Parity
Matched on **mean morphology reduction** at 24h

### Key Test
Can agent detect **additive vs multiplicative structure**?
- Death: Multiplicative → scales with signal, changes distribution shape
- Debris: Additive offset → constant across wells, different shape

### Features
- Base: Viability + 5 morphology channels
- **Variance**: Within-dose replicate variance (CRITICAL for shape differences)
- No cross-modal features needed

### Expected Verdict
**DISTINGUISHABLE** via variance features

### Breaks Tie (if distinguishable)
Additive (debris) produces different dose-response structure than multiplicative (death)

### Required Metadata (if confounded)
Empty well background measurement

---

## Output Format

For each pair, report:

1. **AUC and p-value** (single timepoint and multi-timepoint)
2. **Verdict** (Confounded / Distinguishable / Weakly distinct)
3. **Effect parity metric** (what was matched)
4. **Best modality** (which features distinguish, if any)
5. **Breaks tie** (mechanism, if distinguishable)
6. **Required metadata** (what external info needed, if confounded)

Example:

```
Pair 1: EC50 shift vs Dose error
  1TP: AUC=0.125, p=0.96 → Confounded
  3TP: AUC=0.025, p=1.00 → Confounded
  Effect parity: C/EC50 ratio (2× shift)
  Verdict: Confounded
  Requires: Calibration compounds OR dose verification
```

## Interpretation Guidelines

### If Pair 1 is NOT confounded:
- **BUG ALERT**: Scale invariance broken
- Check for absolute-concentration dependencies
- Check for layer mismatches (dose affects one pathway, EC50 affects another)

### If Pair 2 is confounded:
- Viability signal insufficient to break tie
- May need stronger cross-modal structure or external calibrator

### If Pair 3 is confounded:
- Additive vs multiplicative structure too subtle
- May need empty well controls or stronger variance signal

## Next Steps After Pairs 1-3

1. Verify results against expectations
2. If unexpected, investigate before proceeding
3. Implement Pairs 4-6 with same locked protocol
4. Generate final confound matrix table
