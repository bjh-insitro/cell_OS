# Heavy-Tail Measurement Noise: FINAL SHIP SUMMARY

## What Was Added

**Feature:** Rare heavy-tail measurement outliers for Cell Painting assays (Student-t on log-scale, clipped).

**Purpose:** Models lab artifacts (focus drift, contamination, bubbles) beyond lognormal noise.

---

## Test Results (All Pass)

| Test | Status | Time | What It Proves |
|------|--------|------|----------------|
| Golden contract (full epistemic loop) | ✅ 3/3 PASS | 0.71s | Schema, invariants, causal contracts preserved |
| Biology regression (deterministic equality) | ✅ PASS | 3.2s | Biology unchanged to machine precision (frequency=0.0) |
| Fast contract tests (heavy-tail behavior) | ✅ 5/5 PASS | 4.5s | Clipping, exceedance, RNG invariance |

---

## Key Fixes Made

### 1. RNG Guard: Exact Match (Not Substring)

**BEFORE:**
```python
if pattern in caller_func:  # Substring match
```

**AFTER:**
```python
if caller_func == pattern:  # EXACT MATCH
```

**Why:** Prevents accidental whitelisting of `heavy_tail_shock_debug()` or wrapper functions.

### 2. SHIP_PROOF.md: Reproduction Commands Added

Now includes:
- Exact pytest commands
- Seeds used (42, 123, 456)
- Config diff (heavy_tail_frequency=0.0)
- Base commit hash
- Expected outputs

---

## What Changed vs What Didn't

| Component | Changed? | Evidence |
|-----------|----------|----------|
| Biology trajectories | ❌ NO | Identical to 1e-12 precision |
| Measurement determinism (freq=0.0) | ❌ NO | Same seed → same output |
| Contract compliance | ❌ NO | Golden test passes |
| RNG guard | ✅ YES | Exact match (safer), one string added |
| well_biology bug | ✅ FIXED | Moved to seeding (no biology impact) |

---

## Configuration

**Default (Dormant):**
```yaml
technical_noise:
  heavy_tail_frequency: 0.0      # DORMANT (preserves golden files)
  heavy_tail_nu: 4.0             # Student-t degrees of freedom
  heavy_tail_log_scale: 0.35     # Shock magnitude
  heavy_tail_min_multiplier: 0.2 # Hard floor (5× attenuation max)
  heavy_tail_max_multiplier: 5.0 # Hard ceiling (5× amplification max)
```

**Enable for realism:**
```python
vm.thalamus_params['technical_noise']['heavy_tail_frequency'] = 0.01  # 1%
```

---

## Design Properties

1. **Clipping is part of the statistical contract** (documented in code)
   - Raw Student-t exp(t) can be infinite; clipping makes it bounded
   - Do NOT interpret capped outliers as biological signal

2. **Outliers are correlated across channels** (documented in code)
   - One shock per measurement affects all channels together
   - Creates "this well looks globally weird" signatures

3. **Measurement-only** (cannot affect biology)
   - Uses only `rng_assay`, not `rng_growth`
   - Observer independence preserved

4. **Deterministic given seed** (reproducible)
   - Draw-count invariant (always draws u and t)
   - Same seed → same outliers

---

## Verification Commands

```bash
# 1. Golden contract test (full epistemic loop)
python3 -m pytest tests/integration/test_golden_seed42_contract_regression.py -xvs
# Expected: 3/3 pass, ~0.7s

# 2. Biology regression (deterministic equality)
python3 test_regression_biology_unchanged.py
# Expected: All biology fields match to <1e-12

# 3. Fast contract tests (heavy-tail behavior)
python3 tests/contracts/test_heavy_tail_fast.py
# Expected: 5/5 pass, <5s
```

---

## What You Just Accomplished

Added realism without contaminating causality:

✅ Tails are **measurement-only**
✅ Deterministic when dormant
✅ Correlated across channels (interpretable)
✅ Clipped (no infinite-moment insanity)
✅ Contract golden didn't move
✅ RNG guard is exact match (safe)

**You made the simulator more evil without making it dishonest.**

---

## Next Realism Target (Not This PR)

**Regime shifts** (structured non-stationarity):
- Day where entire plate has systematic issue (not smooth drift)
- Temporary staining reagent hiccup (affects all wells on that plate)
- Operator-mode failure (increases variance for block of wells)

This is temporal correlation of variance, not just heavy-tail events.

---

## MERGE ✅

All tests pass. Physics unchanged. RNG guard is safe. Documentation complete.

**Ship it.**
