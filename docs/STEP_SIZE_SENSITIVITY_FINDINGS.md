# Step-Size Sensitivity Findings

**Date**: 2025-12-20
**Status**: 🔍 DISCOVERY - Time semantics fix exposed integration bugs

---

## Background: Why This Surfaced Now

The time semantics fix ([docs/TIME_SEMANTICS_FIX.md](TIME_SEMANTICS_FIX.md)) corrected the temporal contract:
- Biology now integrates over [t0, t1) using state AS-OF t0
- Before fix: biology used t1, which masked discretization artifacts
- After fix: integration bugs can no longer hide

**This is a feature, not a bug.** The model is now causally correct, and the discretization errors are exposed.

---

## Tests Run: Adversarial Step-Size Consistency

Created `tests/phase6a/test_step_size_consistency.py` with four adversarial tests:

1. **Depletion linearity (low density)**: 1×24h vs 2×12h vs 4×6h - ❌ FAIL
2. **Depletion with growth+death**: 1×24h vs 2×12h with compound attrition - ❌ FAIL
3. **Attrition convergence (variable hazard)**: dt = 24h, 12h, 6h, 3h - ❌ FAIL (non-monotonic jitter)
4. **RNG step-size independence**: 1×24h vs 24×1h measurement variance - ✅ PASS

**Key result**: RNG test passed (measurement noise doesn't accumulate per-step), but physics tests exposed three mechanisms with dt-dependent discontinuities.

---

## Finding 1: Attrition Hard Threshold (Smoking Gun)

**Location**: `src/cell_os/sim/biology_core.py:345`

```python
# No attrition before 12h (cells need time to commit to death)
if time_since_treatment_h <= 12.0:
    return 0.0
```

**Location**: `src/cell_os/hardware/biological_virtual.py:1425`

```python
time_since_treatment = self.simulated_time - vessel.compound_start_time.get(compound, self.simulated_time)
```

### The Bug

Attrition is computed using a **hard step function** evaluated at interval **start** (t0):
- If `time_since_treatment ≤ 12h` at t0 → **NO attrition** over entire [t0, t1) interval
- If `time_since_treatment > 12h` at t0 → **FULL attrition** over entire [t0, t1) interval

This treats a discrete threshold as if it's constant over the interval.

### Example: Step-Boundary Artifacts

Consider compound treated at t=0, simulating to t=24h:

**Case A: 1×24h**
- Interval: [0, 24h)
- `time_since_treatment` at t0 = 0h
- Threshold check: 0 ≤ 12 → FALSE (boundary case)
- Result: Attrition applies over full 24h

**Case B: 2×12h**
- First interval: [0, 12h)
  - `time_since_treatment` at t0 = 0h
  - Threshold check: 0 ≤ 12 → TRUE
  - Result: NO attrition over [0, 12h)
- Second interval: [12h, 24h)
  - `time_since_treatment` at t0 = 12h
  - Threshold check: 12 ≤ 12 → TRUE (boundary case)
  - Result: NO attrition over [12h, 24h)

**Case C: Shifted interval [11h, 13h]**
- `time_since_treatment` at t0 = 11h
- Threshold check: 11 ≤ 12 → TRUE
- Result: NO attrition, even though interval crosses 12h boundary

**Case D: Shifted interval [13h, 15h]**
- `time_since_treatment` at t0 = 13h
- Threshold check: 13 ≤ 12 → FALSE
- Result: FULL attrition, even though only 2h past threshold

### Consequence

Non-monotonic convergence: viability jitter as dt changes how intervals straddle the 12h boundary.

**Test result**: Attrition convergence test showed successive differences that don't decrease monotonically.

---

## Finding 2: Lag Ramp Sampled at t0

**Location**: `src/cell_os/hardware/biological_virtual.py:1352`

```python
time_since_seed = (self.simulated_time + hours) - vessel.seed_time

lag_factor = 1.0
if time_since_seed < lag_duration:
    lag_factor = max(0.0, time_since_seed / lag_duration)
```

### The Bug

Lag factor is computed at **end of interval** (t0 + hours), then applied as if constant over [t0, t1).

For a linear ramp from 0 to 1 over 12h:
- 1×24h: samples at t=24h → lag_factor = min(24/12, 1) = 1.0
- 2×12h first: samples at t=12h → lag_factor = 12/12 = 1.0
- 4×6h first: samples at t=6h → lag_factor = 6/12 = 0.5

**Consequence**: Early intervals get wrong average growth rate. Should integrate ramp over interval, not sample at endpoint.

**Test result**: Depletion linearity showed 19-38% relative error (expected O(dt) for Euler).

---

## Finding 3: Confluence Saturation (Nonlinear Clamp)

**Location**: `src/cell_os/hardware/biological_virtual.py:1381-1383`

```python
confluence = vessel.cell_count / vessel.vessel_capacity
growth_factor = 1.0 - (confluence / max_confluence) ** 2
growth_factor = max(0, growth_factor)
```

### The Issue

Confluence saturation is applied as a **per-step clamp** based on current count:
- Count after growth differs between 1×24h vs 2×12h
- Nonlinear term evaluated at different points creates dt dependence

**Consequence**: Growth saturates differently for different step sizes, even at low density.

**Note**: This is a smaller effect than attrition gate and lag ramp, but compounds with them.

---

## Why This Matters

### Before Time Semantics Fix

When biology read t1 (end of interval):
- `time_since_treatment = t1 - t_start`
- For interval [11h, 13h]: evaluated at 13h → past threshold → attrition applies
- Effectively shifted evaluation point, masking boundary artifacts

### After Time Semantics Fix

Biology now correctly uses t0:
- `time_since_treatment = t0 - t_start`
- For interval [11h, 13h]: evaluated at 11h → before threshold → NO attrition
- Causally correct, but exposes that gate logic is NOT integrated over interval

**The time semantics fix didn't break anything. It removed a masking error.**

---

## Fix Plan

### Immediate: Interval-Integrated Attrition Gate

**What to change**: `src/cell_os/sim/biology_core.py:345`

**Current logic**:
```python
if time_since_treatment_h <= 12.0:
    return 0.0
```

**Proposed logic**: Compute fraction of interval [t0, t1) that lies past threshold

Let:
- `t0 = time_since_treatment_h` (start of interval, from caller)
- `t1 = t0 + dt` (end of interval)
- `T = 12.0` (threshold)

Effective attrition multiplier:
- If `t1 ≤ T`: 0 (entire interval before threshold)
- If `t0 ≥ T`: 1 (entire interval after threshold)
- Else: `(t1 - T) / (t1 - t0)` (fraction of interval past threshold)

**Impact**: Attrition converges smoothly as dt → 0, no step-boundary jitter.

---

### Immediate: Interval-Mean Lag Ramp

**What to change**: `src/cell_os/hardware/biological_virtual.py:1352-1356`

**Current logic**: Sample ramp at interval endpoint
**Proposed logic**: Compute average ramp value over [t0, t1)

If lag ramps linearly from 0 to 1 over L hours starting at t_seed:
- Integrate ramp over [t0, t1)
- Result: mean value, not endpoint sample

**Impact**: Growth rate averages correctly over interval, no early-interval bias.

---

### Later: Smooth Confluence Saturation

**What to change**: `src/cell_os/hardware/biological_virtual.py:1381-1383`

**Current logic**: Per-step clamp based on instantaneous confluence
**Proposed logic**: Logistic saturation term integrated over interval

This is a larger change (requires rethinking saturation model). Can be deferred until attrition and lag fixes are validated.

---

## Acceptance Criteria

After fixes, adversarial tests should show:

1. **Attrition convergence**: Successive differences decrease monotonically as dt halves
2. **Depletion linearity**: 2×12h ≈ 1×24h within O(dt) tolerance (5-10% for Euler)
3. **No RNG accumulation**: Already passing, must remain passing
4. **Growth+death composition**: Viability and count differences < 5% for 2×12h vs 1×24h

---

## Meta-Point: This Was Always There

These discretization bugs existed before the time semantics fix. They were masked by:
- Evaluating gates at t1 instead of t0 (shifted reference point)
- Systematic temporal bias making errors less obvious
- No adversarial step-size testing

**The time semantics fix is a win.** Annoying win, but still a win. The model is now:
1. Causally correct (biology uses t0, spines stamped at t1)
2. Honest about discretization errors (can't hide anymore)
3. Ready for proper interval integration

---

## Update: Interval Integration Fixes Implemented

**Date**: 2025-12-20 (afternoon)
**Status**: 🔧 FIXES APPLIED - Attrition and lag phase now use interval integration

### What Was Fixed

**1. Attrition Gate (Implemented)**
- Added `interval_fraction_after()` helper in biology_core
- Added `compute_attrition_rate_interval_mean()` wrapper
- Caller updated to pass `time_since_treatment_start_h` and `dt_h`

**Result**: Attrition convergence **dramatically improved**:
- 2×24h vs 4×12h: 0.000010 difference (nearly identical!)
- Was: non-monotonic jitter
- Now: smooth convergence for step sizes that cross 12h boundary

**2. Lag Phase Ramp (Implemented)**
- Added `mean_lag_factor_over_interval()` helper in biology_core
- Integrates linear ramp exactly (analytical solution)
- Growth function updated to use interval-mean lag factor

**Result**: Lag phase is now **perfectly path-independent**:
- 1×24h = 0.7500
- 2×12h weighted average = 0.7500 (exact match)

### What Remains

**Confluence Saturation (Deferred)**

Nonlinear saturation term creates Euler integration artifacts:
```python
confluence = vessel.cell_count / vessel.vessel_capacity
growth_factor = 1.0 - (confluence / max_confluence) ** 2
```

This is evaluated at different points for different step sizes, creating compounding differences.

**Test results after fixes**:
- Depletion linearity: 21-30% error (down from 63-73%)
- Growth+death: 29% cell count difference (down from 51%)
- Attrition convergence: **massive improvement**, but small dt still shows jitter

**Recommended next step**: Smooth saturation model (logistic-like) integrated over interval. This is a larger architectural change and can be deferred.

---

### Confluence as Biological Confounder (Not Yet Modeled)

**Status:** ❌ Not modeled
**Category:** Biological realism gap (measurement confounding, not integration error)

Confluence is currently implemented only as a **growth saturation term** and a reported diagnostic. It does **not** act as a biological driver of cell state or a systematic modifier of measurements.

Specifically, confluence does *not* currently influence:

* Cell Painting morphology (ER, mitochondria, actin, nucleus, RNA channels)
* Transcriptomic profiles (scRNA-seq)
* Latent stress states (ER stress, mitochondrial dysfunction, transport stress)
* Nutrient competition or contact-mediated signaling
* Compound potency, sensitivity, or attrition rates

This is a known realism gap. In real cell systems, increasing confluence introduces **predictable, non-mechanistic biases** through contact inhibition, altered cell cycle dynamics, metabolic competition, and mechanosensitive signaling (e.g. YAP/TAZ). These effects systematically shift both morphology and gene expression even in the absence of any experimental perturbation.

As a result, the current simulator implicitly assumes:

* Measurement invariance with respect to seeding density
* No density-driven confounding of biological axes
* No pressure-mediated lag or memory effects

This is acceptable for numerical stability work but incomplete for epistemic control. In real experiments, confluence is one of the dominant hidden variables that causes false mechanism attribution when not explicitly modeled.

Importantly, this gap is **orthogonal to step-size sensitivity**:

* Step-size artifacts arise from evaluating nonlinear terms at inconsistent temporal points
* Confluence confounding arises because measurement manifolds shift with density over time

Conflating the two would mask future failures.

For this reason, confluence–biology coupling is deferred until after integration semantics are fully stabilized (attrition gate, lag ramp, saturation smoothing). Introducing additional stateful feedback before those fixes would reintroduce dt-dependent artifacts.

---

### Acceptance Criteria for Future Implementation

When confluence is modeled as a biological confounder, the following must hold:

1. **Stateful Pressure, Not Instantaneous Thresholds**

   * Confluence effects must be mediated through a lagged, bounded latent variable (e.g. contact pressure)
   * No hard thresholds or instantaneous switches

2. **Integrated Over Time, Not Sampled at Boundaries**

   * All confluence-driven effects must integrate over the interval
   * No `effect = f(confluence_at_t0) * dt` patterns

3. **Measurement Manifold Shift, Not Mechanism Override**

   * Confluence should bias morphology and transcriptomics systematically
   * It must not masquerade as ER stress, mitochondrial toxicity, etc.
   * Posterior should express increased uncertainty, not confident misclassification

4. **Density Confounding Test**

   * Same compound and dose, different initial seeding densities:

     * Without confluence-aware nuisance modeling → posterior confusion
     * With modeling → reduced false mechanism attribution

5. **Step-Size Invariance**

   * For matched initial and final confluence, results must converge across dt
   * Differences must fall within stochastic noise bounds

6. **Isolation From Numerical Fixes**

   * Adding confluence coupling must not regress existing step-size sensitivity tests
   * Attrition convergence and growth consistency tests must continue to pass

---

**Last Updated**: 2025-12-20
**Status**: ✅ Attrition gate fixed, ✅ Lag ramp fixed, ⏳ Confluence saturation deferred (numerical), ❌ Confluence–biology coupling not modeled (realism gap)
**Test Status**: 1/4 passing (RNG), 3/4 improved but still show nonlinear artifacts
