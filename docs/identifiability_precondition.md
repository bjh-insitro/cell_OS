# Identifiability Precondition (Lock-In)

**Created:** 2025-12-29
**From:** Phase 2C.2 mito failure analysis

---

## Purpose

This document defines **hard requirements** that any stochastic commitment mechanism must satisfy before attempting a Phase 2C identifiability suite.

**Why this matters:** Phase 2C.2 showed that time-above-threshold is insufficient - mito showed "50% time >0.60" but H ≈ 0 due to oscillatory stress barely crossing threshold.

---

## Hard Requirements

### 1. Hazard Mass Check (Primary Gate)

**Before running identifiability suite:**

Compute per-well cumulative hazard over observation window:

```
H = ∫λ(t)dt
where λ(t) = min(cap, λ₀ · ((max(0, S(t) - S_commit)/(1 - S_commit))^p))
```

**Acceptance:**
- **Median(H) across wells must exceed 0.2**
- This ensures ~18% expected commitment probability: P(commit) = 1 - exp(-H) ≈ 1 - exp(-0.2) ≈ 0.18

**Rationale:**
- Need 10-50% commitment to fit parameters with reasonable uncertainty
- Lower bound (H ≥ 0.2) ensures you're not trying to identify from noise

---

### 2. Stress Coverage Check

**Requirement:** Stress covariate S(t) must meaningfully sample around threshold S_commit.

**Not sufficient:**
- ❌ "Crosses threshold at some point"
- ❌ "Peak stress > threshold"

**Required:**
- ✅ Sustained time at S ∈ [S_commit, S_commit + 0.3]
- ✅ At commitment-producing doses, mean time in "identifiable region" >20% of window

**Why:** The hazard function λ(S) is nonlinear. If stress only barely crosses threshold (S ≈ S_commit + 0.01), then u = (S - S_commit)/(1 - S_commit) ≈ 0.025, and with p=2, λ ≈ λ₀ · 6×10⁻⁴.

**Diagnostic:** Plot distribution of u(t) = (S(t) - S_commit)/(1 - S_commit) for S(t) > S_commit. Should see meaningful density at u ∈ [0.1, 0.5], not just u ∈ [0.001, 0.05].

---

### 3. Temporal Stability Check

**Requirement:** Stress should not oscillate wildly within wells.

**Acceptance:**
- Stress CV (within-well, over time) <0.7 at commitment-producing doses
- If CV >0.9, **stress dynamics are incompatible with instantaneous threshold gate**

**Why:** High temporal variance means stress briefly spikes above threshold but doesn't sustain. Even if time-above-threshold looks good (say 50%), most of that time is at S barely above S_commit where hazard is negligible.

**Phase 2C.2 finding:** All mito stressors (rotenone, CCCP, oligomycin) showed CV ~0.96 → structural incompatibility.

---

## Diagnostic Workflow (Use This Before Running Suite)

### Step 1: Hazard-Mass Scout

```python
# For each dose_uM:
for well in wells:
    H = 0.0
    for i in range(len(times) - 1):
        s = stress[i]
        dt = times[i+1] - times[i]

        if s <= threshold:
            hazard = 0.0
        else:
            u = (s - threshold) / (1.0 - threshold)
            hazard = min(cap, lambda0 * (u ** p))

        H += hazard * dt

    cumulative_hazards.append(H)

median_H = np.median(cumulative_hazards)
```

**Gate:** If `median_H < 0.2`, **STOP**. Do not run full identifiability suite.

---

### Step 2: Stress Coverage Analysis

```python
# For wells with H > 0:
for well in wells_with_hazard:
    u_values = []
    for s in stress_trajectory:
        if s > threshold:
            u = (s - threshold) / (1.0 - threshold)
            u_values.append(u)

    # Check coverage
    frac_in_identifiable_region = np.mean([0.1 <= u <= 0.5 for u in u_values])
```

**Gate:** If `frac_in_identifiable_region < 0.20`, stress barely crosses threshold. Parameters will be confounded.

---

### Step 3: Temporal Stability Check

```python
# For wells with H > 0:
for well in wells_with_hazard:
    stress_mean = np.mean(stress_trajectory)
    stress_std = np.std(stress_trajectory)
    cv = stress_std / stress_mean

    temporal_cvs.append(cv)

median_cv = np.median(temporal_cvs)
```

**Gate:** If `median_cv > 0.7`, stress oscillates rather than sustains. Instantaneous threshold gate is incompatible.

**Solution:** Change commitment model to use cumulative exposure integrator (Phase 2E), not calibration.

---

## What Preconditions Prevent

### Anti-Pattern 1: Scout Illusion

**Bad metric:** "50% time above threshold"

**Why bad:** Time-above-threshold doesn't account for nonlinear hazard. Most "time above" could be at S ≈ S_commit + ε where λ(S) ≈ 0.

**Good metric:** Median cumulative hazard H ≥ 0.2.

---

### Anti-Pattern 2: Tuning Harder

**Failure mode:** "Let's increase λ₀ to 2.0/h and extend window to 240h!"

**Why bad:** If H ≈ 0 at λ₀ = 0.80/h over 180h, the problem is **stress coverage**, not hazard magnitude. Raising λ₀ → ∞ won't help if u(t) ≈ 0.

**Precondition blocks:** Forces you to check H first. If it's low, you see stress dynamics are incompatible.

---

### Anti-Pattern 3: False Negatives from Zero Events

**Problem:** Suite runs, gets 0 events, reports INSUFFICIENT_EVENTS, user thinks "need more reps."

**Why bad:** If H ≈ 0, more reps won't help. You're sampling from P(commit) ≈ 0.

**Precondition prevents:** Check H before running. If H < 0.2, you know it's structural, not statistical.

---

## Example: Phase 2C.2 Mito

**What happened:**
- Scouts showed "50% time above threshold (0.60)"
- Looked promising → ran full suite
- Got 0 events in both 120h and 180h windows
- Cumulative hazard diagnostic revealed H ≈ 0

**What precondition would have caught:**
- Hazard-mass scout would compute H ≈ 0.05 at best doses
- Median H < 0.2 → **STOP, don't run full suite**
- Temporal CV ~0.96 → stress incompatible with instantaneous gate
- Conclusion: Need model revision (integrator), not calibration

**Time saved:** Would have diagnosed incompatibility in 1 scout run, not after full aggressive test.

---

## When Preconditions Fail: Decision Tree

```
Precondition check → median H < 0.2?
├─ YES → Is median_cv > 0.7?
│  ├─ YES → Stress dynamics incompatible with instantaneous gate
│  │         → Option 1: Change commitment model to integrator (Phase 2E)
│  │         → Option 2: Smooth stress metric (Phase 0/1 revision)
│  │         → Option 3: Accept mechanism as unidentifiable
│  └─ NO  → Is stress coverage poor (u barely crosses 0)?
│     ├─ YES → Doses too low or threshold too high
│     │        → Scout higher doses or lower threshold
│     └─ NO  → λ₀ too low or window too short
│                → Increase baseline hazard or extend window
└─ NO  → Preconditions satisfied → Run full identifiability suite
```

---

## Enforcement

**For any future Phase 2X identifiability suite:**

1. **Implement hazard-mass scout** (see `scout_cccp_time_above_threshold.py` as template)
2. **Run precondition check** before full suite
3. **Log H distribution, stress coverage, temporal CV** in scout report
4. **If preconditions fail:** Document as structural limitation, not "needs more tuning"

**This prevents:**
- Wasted compute on incompatible stress dynamics
- False hope from "time above threshold" scouts
- Iterative tuning when the problem is structural

---

## References

- **Phase 2C.2 Conclusion:** [identifiability_phase2c2_conclusion.md](identifiability_phase2c2_conclusion.md)
- **Scout scripts:** `scripts/scout_*_time_above_threshold.py`
- **Cumulative hazard diagnostic:** `src/cell_os/calibration/identifiability_inference.py:fit_commitment_params()`

---

*This precondition is a hard lock from Phase 2C.2 learnings. Do not bypass without documenting why.*
