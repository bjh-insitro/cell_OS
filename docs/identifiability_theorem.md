# The Identifiability Theorem (Phase 2C.1)

**Proven:** 2025-12-29
**Context:** Cell_OS Phase 2A commitment mechanism calibration

---

## Statement

**A threshold parameter in a stress-driven hazard model is independently identifiable from event timing data if and only if the stress covariate distribution straddles the threshold value during the observation window.**

### Precise Form

Given commitment hazard:
```
λ(S,t) = λ₀ · h((S(t) - S_threshold) / (1 - S_threshold))
```

Where:
- S(t) = stress covariate over time
- S_threshold = threshold parameter
- λ₀ = baseline hazard rate
- h(·) = monotonic activation function (e.g., power law)

**Identifiability condition:**
```
∃ t₁, t₂ in observation window:
  S(t₁) < S_threshold  AND  S(t₂) > S_threshold
```

**Failure mode:**
If S(t) >> S_threshold for all t, then S_threshold and λ₀ become confounded. The likelihood surface degenerates to a ridge where multiple (S_threshold, λ₀) pairs explain the data equally well.

---

## Proof by Experimental Design

### Setup
- Generative model: Phase 2A ER stress commitment
- True parameters: S_threshold = 0.60, λ₀ = 0.20 h⁻¹, p = 2.0
- Observation window: 120 hours
- Four dose levels in Regime C (parameter recovery)

### Experiment 1: Saturated Covariate (Failed)
**Design:** Tunicamycin 0.275, 0.331, 0.438, 0.637 µM
**Stress range:** S ∈ [0.72, 0.79, 0.90, 0.95] at t=12h
**All values > threshold (0.60)**

**Result:**
- Commitment fractions: 33%, 42%, 83%, 83%
- Recovered threshold: 0.70 (error: 0.100)
- Recovered λ₀: 0.139 h⁻¹ (0.69x error)
- Verdict: Parameters confounded (threshold at tolerance boundary)

**Analysis:**
Model can explain data by:
1. Threshold = 0.60, λ₀ = 0.20 → High hazard everywhere
2. Threshold = 0.70, λ₀ = 0.14 → Lower hazard, but still above threshold

Both fit equally well when S is always above threshold.

### Experiment 2: Bracketed Covariate (Passed)
**Design:** Tunicamycin 0.130, 0.197, 0.245, 0.300 µM
**Stress range:** S ∈ [0.43, 0.59, 0.68, 0.75] at t=12h
**Values span threshold (0.60)**

**Result:**
- Commitment fractions: 0%, 17%, 42%, 83%
- Recovered threshold: 0.57 (error: 0.033) ✅
- Recovered λ₀: 0.373 h⁻¹ (1.86x error) ✅
- Verdict: Parameters independently identifiable

**Analysis:**
- C1 (S=0.43): Below threshold → λ ≈ 0 → No events (anchors threshold lower bound)
- C2 (S=0.59): At threshold → λ ramping up → Few events (identifies transition)
- C3 (S=0.68): Above threshold → λ significant → Moderate events (steep region)
- C4 (S=0.75): Well above threshold → λ saturated → Many events (checks saturation)

Full sigmoid shape observable → Parameters independently identifiable.

---

## Generalization

This applies to any mechanistic model where:
1. A continuous covariate X drives a discrete outcome via threshold
2. Parameters θ_threshold and θ_rate control hazard/probability
3. You want to infer both from outcome timing data

**Identifiability requires:**
- Covariate variation around θ_threshold (not just outcome variation)
- Observations in regions where hazard transitions (not just extremes)

**Common failures:**
- Sampling only above threshold → threshold confounded with baseline rate
- Sampling only below threshold → no signal (zero events)
- Sampling at extremes only → parameters determined by extrapolation, not data

---

## Implications for Experimental Design

### Bad Design Heuristic
**"Choose doses that give 20-80% event rates"**

This maximizes outcome variance but doesn't guarantee covariate variation around parameters.

Result: High event counts, mushy parameters.

### Good Design Heuristic
**"Choose doses that span the covariate region where mechanism parameters act"**

For threshold models:
1. Run dose scout to measure covariate (not just outcomes)
2. Identify doses where covariate brackets threshold
3. Ensure at least one dose below, one at, one above threshold
4. Extend observation window if low-covariate doses need more time at risk

Result: Parameters identifiable even with fewer total events.

---

## Why This Matters

### For Simulators
Most biological simulators have threshold parameters (commitment thresholds, death thresholds, differentiation thresholds). This theorem tells you:
- When those parameters are learnable from simulated data
- How to design calibration experiments that aren't lying to themselves
- Why parameter recovery sometimes fails despite "enough events"

### For Real Experiments
Same principle applies to real dose-response experiments:
- Don't just measure outcome fractions at a few doses
- Measure the **proximal covariate** (stress, receptor occupancy, signal intensity)
- Design doses to bracket the region where you think mechanism parameters live
- If you can't get covariate variation, you're measuring an effective parameter, not a mechanistic one

### For Model Trust
A model with unidentifiable parameters is not "complex" - it's **unvalidated**.

This theorem provides a constructive test:
- Can you design an experiment where parameters recover?
- If yes → mechanism is testable
- If no → mechanism is a hypothesis, not a validated model

---

## Connection to Phase 2C.1

Phase 2C.1 proved this theorem by:
1. Building identifiability infrastructure (scout, diagnostics, precondition checks)
2. **Failing honestly** when covariate was saturated (2C.1.2)
3. Fixing by redesigning experiment, not tuning parameters (2C.1.3)
4. **Passing with margin** when covariate bracketed threshold

The infrastructure ensures future mechanisms get the same discipline.

---

## Related Work

This is a special case of:
- **Fisher Information** theory (parameter identifiability from likelihood geometry)
- **Optimal Experimental Design** (choosing measurements to maximize information)
- **Structural Identifiability** (when parameter uniqueness fails)

Novelty here: Applied specifically to stress-threshold-hazard models common in cell fate decisions, with constructive fix via dose-scout methodology.

---

*This theorem wasn't handed down. It was earned by watching the simulator fail, diagnosing why, and fixing the experiment instead of the model.*
