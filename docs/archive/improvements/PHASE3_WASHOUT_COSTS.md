# Phase 3: Washout Costs - Physics Lock Complete ✅

**Completion Date:** 2025-12-19

## Summary

Phase 3 introduces **intervention costs** for washout operations, locking the physics before defining reward functions. This prevents accidentally designing backdoors into the world model.

**Core principle:** Costs are part of the world, not the policy.

## Implementation

### Feature Flag

```python
ENABLE_INTERVENTION_COSTS = True  # Default: on for Phase 3
```

Allows legacy tests to disable if needed, but Phase 3 tests require it on.

### Washout Costs (3 components)

#### 1. Time Cost
- **Value:** 0.25h operator time per washout
- **Effect:** Recorded in result metadata for policy cost tracking
- **Rationale:** Prevents infinite pulse micro-cycling

#### 2. Contamination Risk
- **Probability:** 0.1% (lower than feeding's 0.2%)
- **Effect:** If triggered, manifests as temporary intensity drop (measurement artifact)
- **Duration:** Handled via `last_washout_time` check during assays
- **Rationale:** Makes washout a risky choice, but not catastrophic

#### 3. Intensity Penalty (Deterministic)
- **Magnitude:** 5% signal intensity drop
- **Duration:** Linear recovery over 12h
- **Effect:** Applied to all morphology channels during measurement
- **Rationale:** Cells are disturbed by media change → measurement noise

**Formula:**
```python
if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
    recovery_fraction = time_since_washout / WASHOUT_INTENSITY_RECOVERY_H
    washout_penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
    viability_factor *= (1.0 - washout_penalty)
```

### What Washout Does NOT Do

**Explicit design constraints (enforced in code comments):**

❌ Does NOT directly affect latent states:
  - `er_stress` unchanged
  - `mito_dysfunction` unchanged
  - `transport_dysfunction` unchanged

❌ Does NOT reset viability

❌ Does NOT magically improve outcomes

✅ Washout ONLY:
  - Removes compounds
  - Adds intervention costs (time, contamination risk, intensity penalty)

**Recovery comes from natural decay dynamics** (`k_off` terms), not from washout itself.

## Code Changes

### Constants Added (lines 59-64)

```python
# Intervention costs (Phase 3: washout costs prevent free micro-cycling)
ENABLE_INTERVENTION_COSTS = True
WASHOUT_TIME_COST_H = 0.25  # Operator time per washout operation
WASHOUT_CONTAMINATION_RISK = 0.001  # 0.1% chance (lower than feeding)
WASHOUT_INTENSITY_PENALTY = 0.05  # 5% intensity drop for 12h (measurement artifact)
WASHOUT_INTENSITY_RECOVERY_H = 12.0  # Recovery time for intensity penalty
```

### VesselState Fields Added (lines 155-157)

```python
# Intervention tracking (Phase 3: costs for washout/feed)
self.last_washout_time = None  # Simulated time of last washout (for intensity penalty)
self.washout_count = 0  # Total washouts performed (for ops cost tracking)
```

### washout_compound() Updated (lines 1170-1257)

**Added:**
- Comprehensive docstring explaining costs and constraints
- Intervention cost application (time, contamination, intensity)
- Metadata return (time_cost_h, contamination_event, intensity_penalty_applied)
- Tracking fields update (last_washout_time, washout_count)

**Key implementation detail:**
```python
# IMPORTANT: Washout does NOT directly affect latent states (er_stress, mito_dysfunction,
# transport_dysfunction). Recovery comes from natural decay dynamics (k_off terms).
# Washout only removes compounds and adds intervention costs.
```

### cell_painting_assay() Updated (lines 1891-1900)

**Added intensity penalty application:**
```python
# Apply washout intensity penalty (Phase 3: intervention costs)
# Washout disturbs cells → transient measurement artifact (NOT biology)
if ENABLE_INTERVENTION_COSTS and vessel.last_washout_time is not None:
    time_since_washout = self.simulated_time - vessel.last_washout_time
    if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
        # Linear recovery over WASHOUT_INTENSITY_RECOVERY_H hours
        recovery_fraction = time_since_washout / WASHOUT_INTENSITY_RECOVERY_H
        washout_penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
        viability_factor *= (1.0 - washout_penalty)
```

## Test Results

### New Test: test_washout_costs.py

**Single sanity test (as specified):** `test_washout_has_cost_but_no_structural_effect`

**Timeline:**
- 0h: Apply paclitaxel (induce transport dysfunction)
- 6h: Measure baseline (transport engaged)
- 6h: Washout
- 6h+1min: Measure immediately after

**Results:**
```
Before washout (6h):
  Compounds: {'paclitaxel'}
  Transport dysfunction: 0.808
  Actin structural: 209.5
  Signal intensity: 0.802
  Viability: 0.716

Washout result:
  Status: success
  Removed compounds: ['paclitaxel']
  Time cost: 0.25h
  Contamination event: False
  Intensity penalty applied: True

Immediately after washout (6h + 1min):
  Compounds: none
  Transport dysfunction: 0.807 (Δ=-0.001)
  Actin structural: 178.1 (Δ=-31.4)
  Signal intensity: 0.762 (Δ=-0.040)
  Viability: 0.716 (Δ=+0.000)
```

**8 checks verified:**

✅ **Check 1:** Compounds cleared
✅ **Check 2:** Transport dysfunction unchanged (0.0011 drift, natural decay)
✅ **Check 3:** ER and mito unchanged
✅ **Check 4:** Structural morphology changes from compound removal (-15%, expected)
✅ **Check 5:** Signal intensity reduced (0.040, measurement artifact)
✅ **Check 6:** Viability unchanged (washout doesn't kill)
✅ **Check 7:** Ops cost metadata present
✅ **Check 8:** Washout count tracked

**Key insight from Check 4:**

Structural morphology decreased 15% because the compound's **direct stress axis effect** is removed immediately when washed out, while the **latent state** (transport dysfunction) persists. This is correct physics:

- **Before washout:** `baseline + compound_effect + latent_effect`
- **After washout:** `baseline + latent_effect` (compound effect removed)

The latent decays gradually via `k_off`, not instantaneously.

### Existing Tests: All Pass ✅

**Phase 2 tests (5/5):**
- ✅ Morphology-first behavior
- ✅ Faster timescale
- ✅ Orthogonality
- ✅ Trafficking marker
- ✅ Monotone invariant

**Phase 0 tests (3/3):**
- ✅ Control baseline stability
- ✅ ER vs mito signal directions
- ✅ Structural vs measured separation

**4-way identifiability:**
- ✅ 11.1× minimum separation maintained
- ✅ All latent signatures intact

## Physics Principles Enforced

### 1. Observer Independence
Washout does NOT affect latent states. Assays observe latents, they don't modify them.

### 2. Causality
- **Physics drives measurement:** Latent dynamics → morphology readouts
- **NOT the reverse:** Measurements don't modify latents

### 3. Intervention Costs Are Part of the World
- Costs are constraints on the environment
- NOT policy incentives
- Defined BEFORE rewards to prevent backdoors

### 4. Recovery Is Gradual
- Compound effects disappear immediately (acute removal)
- Latent effects decay naturally (chronic state)
- Recovery timescale: k_off determines dynamics

## Design Rationale

### Why Intensity Penalty Instead of Viability Hit?

**Chosen:** Intensity penalty (measurement artifact)
**Rejected:** Viability hit (biological damage)

**Rationale:**
- Keeps washout as a measurement concern, not a death mechanism
- Prevents contamination from being "just another death cause"
- Maintains clean separation between biology (latents) and measurement (artifacts)

### Why 0.1% Contamination Risk?

Lower than feeding (0.2%) because:
- Washout involves removing media (less contamination vector)
- Feeding adds new media (more contamination risk)
- Still enough to make it a real concern for policy

### Why 12h Recovery Time?

Matches biological timescales:
- ER/mito decay: k_off = 0.05/h → 20h to 37% (half-life ~14h)
- Transport decay: k_off = 0.08/h → 12.5h to 37% (half-life ~9h)
- Intensity recovery: 12h to full recovery (linear, not exponential)

Slightly faster than latent decay to avoid confounding.

## Next Steps

### Phase 3 Part 2: Reward Function (NOT YET IMPLEMENTED)

Now that costs are locked in the physics, we can safely define rewards:

```python
def compute_reward(vessel_12h, vessel_48h, interventions):
    """
    Multi-objective reward for microtubule mechanism validation.

    Goal: Engage transport mechanism early, minimize death late, minimize ops.
    """
    # 1. Mechanism engagement at 12h (binary gate)
    mechanism_hit = 1.0 if actin_achieved >= 0.40 else 0.0

    # 2. Viability preservation at 48h (quadratic penalty)
    death_penalty = ((1.0 - viability_48h) ** 2) * 10.0

    # 3. Operational cost (linear penalty)
    ops_cost = 0.1 * n_washouts + 0.05 * n_feeds

    return mechanism_hit - death_penalty - ops_cost
```

**DO NOT IMPLEMENT YET.** Wait for user confirmation that physics lock is correct.

### Phase 3 Part 3: Policy Pressure Tests

After reward definition:
1. `test_pulse_vs_continuous_tradeoff()` - Verify pulse beats continuous
2. `test_pulse_recovery_signature()` - Verify washout enables recovery
3. `test_identifiability_under_pulsing()` - Verify feeding doesn't break signatures

## Files Modified

1. **`src/cell_os/hardware/biological_virtual.py`**
   - Added constants (lines 59-64)
   - Added VesselState fields (lines 155-157)
   - Updated washout_compound() (lines 1170-1257)
   - Updated cell_painting_assay() (lines 1891-1900)

2. **`tests/unit/test_washout_costs.py`** (NEW)
   - Single sanity test verifying costs apply correctly
   - 8 comprehensive checks
   - Test passing

## Completion Status

✅ **Physics Lock Complete**

- Washout costs implemented (time, contamination, intensity)
- Costs are part of the world, not the policy
- No direct effects on latent states (observer independence)
- All existing tests pass
- One sanity test passing

**Ready for:** Reward function definition (Phase 3 Part 2)

**Blocked until:** User confirms physics lock is correct

**Quote from user:**
> "Lock the physics before you define incentives. If you do reward first, you'll accidentally bake loopholes into the world model. Costs are part of the world, not the policy."

**Status:** Physics locked. No loopholes. Ready for policy pressure.
