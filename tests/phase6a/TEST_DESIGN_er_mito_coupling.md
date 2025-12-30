# Test Design: ER → Mito Susceptibility Coupling

## Goal
Validate that ER damage amplifies mito induction rate in a continuous, monotonic, identifiable way.

## Challenge
Mito compounds (CCCP, oligomycin) have steep dose-response curves. Naïve dosing leads to saturation.

## Experimental Design

### Test 1: Monotonic Susceptibility (Spearman ρ)

**Conditions:**
- 3 ER damage levels: D ≈ 0.0, 0.3, 0.6 (span sensitive region)
- 1 mito dose: MID-SLOPE only (sensitive regime)
- Assert: Spearman ρ > 0.6

**Controls (prove test isn't cheating):**
- Subthreshold mito dose: Should show NO coupling effect (floor)
- Near-saturation mito dose: Should show NO coupling effect (ceiling)

**Protocol:**
1. Prime ER damage with tunicamycin (0, 1, 3 µM × 24h)
2. Washout
3. Expose to CCCP (dose TBD, 12h)
4. Measure mito_dysfunction

**Dose Selection (empirical):**
- Run pilot: CCCP 0.5, 1.0, 2.0, 5.0 µM × 12h on clean cells
- Pick dose where mito_dysfunction ≈ 0.3-0.5 (mid-slope)
- This is the sensitive dose for the main test

**Assertion:**
```python
# Mid-slope only
rho, _ = spearmanr(er_damage, mito_dysfunction)
assert rho > 0.6

# Controls
# Subthreshold: all mito_dysfunction < 0.1
# Saturation: all mito_dysfunction > 0.9
```

---

### Test 2: Identifiable Distribution Shift (KS test)

**Conditions:**
- Condition A: CCCP alone (mid-slope dose)
- Condition B: Tunicamycin 2 µM (24h) → washout → CCCP (same dose)
- N=12 replicates each
- Assert: KS test p < 0.05

**Why this works:**
- ER damage persists after washout (latent vulnerability)
- Mito compound re-exposure triggers amplified response
- Distribution shift is detectable even with noise

**Assertion:**
```python
ks_stat, p = ks_2samp(mito_alone, er_then_mito)
assert p < 0.05  # Distributions differ significantly
assert mean(er_then_mito) / mean(mito_alone) > 1.2  # Effect size > 20%
```

---

## Implementation Order

1. Write pilot script (dose-finding)
2. Document selected dose in this file
3. Implement coupling in mito_dysfunction.py
4. Write Test 1 with correct dose
5. Write Test 2 with correct dose
6. Commit

---

## Parameters (Selected after pilot)

```python
# Coupling constants (to be calibrated with mid-slope dose)
ER_MITO_COUPLING_K = 3.0  # Amplification factor (conservative start)
ER_MITO_COUPLING_D0 = 0.3  # Sigmoid midpoint (activates at D≈0.3)
ER_MITO_COUPLING_SLOPE = 8.0  # Steepness

# Test doses (from pilot results)
CCCP_SUBTHRESHOLD = 0.5  # Floor: 0.285 median (below sensitivity)
CCCP_MIDSLOPE = 0.7  # Main test: 0.384 median (dead center)
CCCP_SATURATION = 2.0  # Ceiling: 0.887 median (near saturation)
```

---

## Success Criteria

- [ ] Pilot identifies mid-slope dose
- [ ] Test 1 shows monotonic coupling (ρ > 0.6)
- [ ] Test 1 controls confirm no effect at floor/ceiling
- [ ] Test 2 shows distribution shift (p < 0.05)
- [ ] Coupling can be disabled cleanly (ablation test)

## Pilot Results (Baseline CCCP Dose-Response)

Tested: [0.5, 0.6, 0.7, 0.8, 1.0] µM CCCP × 12h (N=6 per dose)

**Mid-slope dose identified:**
- **CCCP 0.6 µM** → median mito_dysfunction = 0.335
- IQR: [0.307, 0.371]

This dose will be used for the monotonicity test.

**Full results:**
- 0.5 µM: median=0.285, IQR=[0.260, 0.316]
- 0.6 µM: median=0.335, IQR=[0.307, 0.371]
- 0.7 µM: median=0.384, IQR=[0.352, 0.425]
- 0.8 µM: median=0.431, IQR=[0.396, 0.476]
- 1.0 µM: median=0.520, IQR=[0.479, 0.572]
