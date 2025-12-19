# Phase 3: Policy Pressure - COMPLETE ✅

**Completion Date:** 2025-12-19

## Summary

Phase 3 creates **policy pressure** through real tradeoffs where "doing the locally good thing" causes later failure. The agent now faces multi-objective rewards with competing incentives, forcing temporal credit assignment instead of lookup-table solutions.

## Three-Part Implementation

### Part 1: Physics Lock (Washout Costs)

**Completed first** to prevent accidentally baking loopholes into the world model.

**Costs implemented:**
- **Time cost:** 0.25h operator time per washout
- **Contamination risk:** 0.1% chance of intensity artifact
- **Intensity penalty:** 5% deterministic signal drop, recovers over 12h

**Critical constraint:** Washout does NOT affect latent states. Recovery comes from natural decay dynamics (k_off), not from washout itself.

**Files:** `src/cell_os/hardware/biological_virtual.py`, `tests/unit/test_washout_costs.py`

### Part 2: Model B Documentation

**Discovered and documented** the morphology readout model:

```python
morph_struct[channel] = baseline × (1 + acute_effect) × (1 + chronic_effect)
```

**Two components:**
1. **Acute:** Direct compound stress axis effects (instant on/off)
2. **Chronic:** Latent dysfunction effects (slow k_off decay)

**Why this matters:** Washout removes acute component immediately, chronic component decays gradually. This prevents "washout = instant fix" policies.

**Files:** `docs/MORPHOLOGY_READOUT_MODEL.md`

### Part 3: Reward Function & Policy Tests

**Reward formula:**
```python
reward_total = mechanism_hit - death_penalty - ops_cost

where:
- mechanism_hit = 1.0 if (actin_struct_12h / baseline) >= 1.4 else 0.0
- death_penalty = 2.0 × (1 - viability_48h)²  # Quadratic
- ops_cost = 0.1 × (washout_count + feed_count)  # Count-based
```

**Design principles:**
- Uses morphology_struct (not measured) to avoid chasing artifacts
- Death penalty is quadratic: killing 50% is 4× worse than 25%
- Ops cost is linear: each intervention has unit cost

**Files:** `src/cell_os/hardware/reward.py`

## Test Results

### Test 1: Pulse vs Continuous Tradeoff ✅

**Policy comparison:**

| Policy     | Mechanism | Death | Ops Cost | Reward |
|------------|-----------|-------|----------|--------|
| Continuous | 1.9× ✓    | 55%   | 0.00     | **0.39** |
| Pulse      | 1.9× ✓    | 33%   | 0.10     | **0.68** |

**Key tradeoffs:**
- Mechanism engagement: MATCHED (both 1.9× baseline)
- Death: Pulse WINS (33% vs 55%, **+40% reduction**)
- Ops cost: Pulse LOSES (0.10 vs 0.00)
- **Total reward: Pulse WINS (0.68 vs 0.39, +0.29 advantage)**

**Policy pressure verified:** Death penalty >> ops cost makes pulse the dominant strategy.

**File:** `tests/unit/test_policy_pressure.py`

### Test 2: Pulse Recovery Signature (Model B Verification) ✅

**Timeline: 12h drug → washout → recover to 48h**

**Tight assertions verified:**

1. **Immediate removal of acute component:**
   - Actin drops 15% instantly (acute removed)
   - Transport dysfunction unchanged (latent persists)

2. **Chronic recovery via k_off:**
   - Transport dysfunction: 1.00 → 0.04 → 0.00 (monotonic decay)
   - Actin structural: returns to baseline by 48h

3. **Trafficking marker tracks latent:**
   - Stays elevated post-washout (latent high)
   - Decays toward baseline as latent decays

4. **Intensity penalty is transient:**
   - Drops immediately post-washout
   - Recovers by 24h (12h recovery time)

**Model B verified:** Acute + chronic components behave as designed throughout washout and recovery.

**File:** `tests/unit/test_pulse_recovery.py`

### Test 3: Identifiability Under Pulsing ✅

**Setup:** Feed all vessels at 6h (adds technical noise), classify at 12h

**Rule-based classifier:**
- ER stress: UPR high AND ER_struct up
- Mito dysfunction: ATP low AND Mito_struct down
- Transport dysfunction: Trafficking high AND Actin_struct up
- Control: None of the above

**Results:**

| Condition              | ER    | Mito  | Actin | UPR   | ATP   | Traffic | Predicted  |
|------------------------|-------|-------|-------|-------|-------|---------|------------|
| Control                | 1.00× | 1.00× | 1.00× | 1.00× | 0.97× | 0.96×   | Control ✓  |
| ER stress              | 1.88× | 1.11× | 1.00× | 2.21× | 0.97× | 0.96×   | ER stress ✓|
| Mito dysfunction       | 1.01× | 0.90× | 0.99× | 1.00× | 0.72× | 0.96×   | Mito ✓     |
| Transport dysfunction  | 1.04× | 1.07× | 1.58× | 1.01× | 0.97× | 1.79×   | Transport ✓|

**Classification accuracy: 100%** (all mechanisms correctly identified)

**Intervention does not destroy mechanism signatures.**

**File:** `tests/unit/test_identifiability_pulsing.py`

## Ops Cost Fix

**Problem discovered:** Initially double-counting washout (event + time).

**Original formula:**
```python
ops_cost = 0.1 × (washout_count + feed_count + operator_hours/0.25)
# With washout_count=1, operator_hours=0.25 → ops_cost = 0.1 × 2 = 0.2
```

**Fixed formula:**
```python
ops_cost = 0.1 × (washout_count + feed_count)
# With washout_count=1 → ops_cost = 0.1 × 1 = 0.1
```

**Rationale:** Count-based is cleanest. Time cost is already implicit in the count (each operation takes time). Removed `operator_hours` parameter to avoid confusion.

## What This Achieves

The agent now faces **real policy pressure**:

1. **No free interventions:** Washout has costs (time, contamination risk, intensity penalty)
2. **Quadratic death penalty:** Killing 50% of cells is 4× worse than 25%
3. **Temporal credit assignment:** Must learn acute vs chronic recovery timescales
4. **Multi-objective tradeoffs:** Can't just "maximize viability" or "hit mechanism at any cost"

### Example Failure Mode (Prevented)

**"Washout spam"** (washing out every hour to reset everything) is now impossible because:
- Each washout costs 0.1 reward
- Washout doesn't instantly reset latents (chronic decay takes 24-48h)
- Intensity penalty makes frequent washouts accumulate measurement artifacts

### Example Success Mode (Encouraged)

**"Pulse dosing"** (hit mechanism early, wash, recover) beats continuous because:
- Both hit mechanism target (reward = +1.0)
- Pulse reduces death by 40% (quadratic penalty savings >> ops cost)
- Death penalty (0.55² × 2 = 0.61 vs 0.33² × 2 = 0.22) far outweighs ops cost (0.10)

## Agent-Ready Sandbox

The simulator now has:

✅ **Three orthogonal latent states** (ER stress, mito dysfunction, transport dysfunction)
✅ **Two sensors per latent** (morphology + scalar)
✅ **Observer independence** (assays don't modify latents)
✅ **Model B verified** (acute + chronic components throughout interventions)
✅ **Intervention costs** (no free operations)
✅ **Policy pressure** (real tradeoffs, temporal credit assignment)
✅ **Identifiability preserved** (interventions don't break signatures)

**Quote from user:**
> "Then we can talk about the next layer: letting the agent choose pulse duration and dose, and seeing if it discovers a Pareto frontier rather than a single hacky policy."

## Files Modified

### Core Implementation
1. **`src/cell_os/hardware/biological_virtual.py`**
   - Added washout costs (lines 59-64)
   - Updated washout_compound() with costs (lines 1170-1257)
   - Added intensity penalty application (lines 1891-1900)

2. **`src/cell_os/hardware/reward.py`** (NEW)
   - EpisodeReceipt dataclass for diagnostic logging
   - compute_microtubule_mechanism_reward() function
   - Count-based ops cost (no double-counting)

### Documentation
3. **`docs/MORPHOLOGY_READOUT_MODEL.md`** (NEW)
   - Model B formula and consequences
   - Acute vs chronic component separation
   - Why this matters for policy learning

4. **`docs/PHASE3_WASHOUT_COSTS.md`**
   - Physics lock completion report
   - Cost components and rationale

5. **`docs/PHASE3_COMPLETE.md`** (THIS FILE)
   - Full Phase 3 summary

### Tests
6. **`tests/unit/test_washout_costs.py`** (NEW)
   - Physics lock sanity test (washout has cost but no structural effect)

7. **`tests/unit/test_policy_pressure.py`** (NEW)
   - Pulse vs continuous tradeoff test

8. **`tests/unit/test_pulse_recovery.py`** (NEW)
   - Model B verification test (4 tight assertions)

9. **`tests/unit/test_identifiability_pulsing.py`** (NEW)
   - Identifiability under interventions test

## Test Suite Status

**Phase 0 (Identifiability):** 3/3 passing
**Phase 2 (Transport Dysfunction):** 5/5 passing
**Phase 3 (Policy Pressure):** 4/4 passing (washout costs + 3 policy tests)
**Total:** 12/12 tests passing

## Next Steps (User Suggestion)

> "Letting the agent choose pulse duration and dose, and seeing if it discovers a Pareto frontier rather than a single hacky policy."

**Possible extensions:**
1. **Continuous control:** Agent chooses dose (0-10 µM) and pulse duration (6-24h)
2. **Pareto frontier:** Explore mechanism_hit vs death_penalty tradeoff surface
3. **Multi-compound policies:** Combine ER/mito/transport stressors
4. **Adaptive policies:** Agent adjusts based on observed latent states

**Not implemented yet. Waiting for user direction.**

## Completion Criteria

✅ Physics locked (washout costs prevent free operations)
✅ Model B documented (acute + chronic components)
✅ Reward function implemented (mechanism + death + ops)
✅ Three policy tests passing (tradeoff + recovery + identifiability)
✅ Ops cost fixed (no double-counting)
✅ All existing tests still pass

**Status: Phase 3 COMPLETE. Agent-ready sandbox with policy pressure.**

The simulator now forces agents into tradeoffs where "doing the locally good thing" causes later failure. No more lookup tables. Time to learn temporal credit assignment.
