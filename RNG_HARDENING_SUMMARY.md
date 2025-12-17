# RNG Hardening & Accounting Finalization

## The Problem

After implementing observer-independent physics and death accounting, three subtle bugs remained that would cause "works on my machine" failures:

1. **Python's `hash()` is salted per-process** → "deterministic" batch RNG becomes nondeterministic across runs
2. **Seed selection used global RNG** → Initialization coupled to whatever touched `np.random` before
3. **Seeding stress mishandled** → 2% initial death treated as accounting error instead of unknown cause

Plus ongoing risk of **accidental global RNG usage** breaking observer independence.

## The Fixes

### 1. ✅ Stable Hashing for Deterministic Seeding

**Problem**: `hash(f"plate_{plate_id}") % 2**32` varies across Python processes due to hash randomization.

**Fix**: Implemented `stable_u32()` using `hashlib.blake2s`:

```python
def stable_u32(s: str) -> int:
    """
    Stable deterministic hash for RNG seeding.

    Unlike Python's hash(), this is NOT salted per process, so it gives
    consistent seeds across runs and machines. Critical for reproducibility.
    """
    return int.from_bytes(hashlib.blake2s(s.encode(), digest_size=4).digest(), "little")
```

**Usage**:
```python
# Before (nondeterministic across processes)
rng_plate = np.random.default_rng(hash(f"plate_{plate_id}") % 2**32)

# After (fully deterministic)
rng_plate = np.random.default_rng(stable_u32(f"plate_{plate_id}"))
```

**Applied to**:
- Plate/day/operator batch effects (cell_painting_assay, atp_viability_assay)
- Well failure deterministic seeding

**Why it matters**: Tests pass locally but fail in CI on different machines. This is the "curse" bug.

---

### 2. ✅ Explicit Seed Selection (Default seed=0)

**Problem**: `seed=None` meant "pick random seed from global RNG", coupling initialization to prior RNG state.

**Fix**: Changed default to `seed=0` for fully reproducible behavior:

```python
def __init__(self, ..., seed: int = 0):
    """
    Args:
        seed: RNG seed for reproducibility (default: 0 for fully reproducible behavior).
              Use different seeds for independent runs, but ALWAYS pass explicitly.
    """
    self.rng_growth = np.random.default_rng(seed + 1)
    self.rng_treatment = np.random.default_rng(seed + 2)
    self.rng_assay = np.random.default_rng(seed + 3)
```

**Seed Contract**:
- `seed=0` → Reproducible physics + reproducible measurements (fully deterministic)
- Future extension: Support separate `seed_physics` and `seed_assay` for "deterministic physics, stochastic measurements"
- Never hack around this by conditionally consuming RNG (breaks stream isolation)

**Why it matters**: Forces users to think about randomness. Eliminates "tests pass in one order but fail in another" bugs.

---

### 3. ✅ Complete Death Accounting with `death_unknown`

**Problem**: Untracked death (seeding stress, delta errors) was either:
- Auto-corrected by dumping into `death_compound` (invents causality)
- Ignored (accounting doesn't partition)

**Fix**: Added explicit `death_unknown` bucket:

```python
class VesselState:
    def __init__(self, ...):
        self.death_compound = 0.0      # Compound-caused death
        self.death_confluence = 0.0    # Overconfluence death
        self.death_unknown = 0.0       # Unknown causes (seeding stress, etc.)
```

**Invariant enforced**:
```python
death_compound + death_confluence + death_unknown == 1 - viability
```

**Behavior**:
- **Before treatment**: `death_unknown = 0.02` (seeding stress), `death_mode = "unknown"`
- **After treatment**: `death_compound = 0.473`, `death_unknown = 0.02` (persists), `death_mode = "compound"`
- **Accounting**: Complete partition, no invented causality

**Warning logic**:
```python
# Only warn if unknown death EXCEEDS seeding baseline (suggests delta error)
seeding_stress_baseline = 0.025  # 2.5% tolerance
if vessel.death_unknown > seeding_stress_baseline and vessel.compounds:
    logger.warning("Unknown death exceeds seeding baseline. Suggests delta tracking error.")
```

**Labeling threshold**:
```python
# Lower threshold for unknown-only death (detect seeding stress early)
unknown_threshold = 0.01 if vessel.death_compound == 0 and vessel.death_confluence == 0 else 0.05
```

---

### 4. ✅ RNG Hygiene Enforcement

**Problem**: Easy to accidentally use `np.random.normal()` instead of `self.rng_*.normal()`, breaking observer independence.

**Fix**: Created `test_no_global_rng.py` to fail CI if global RNG usage detected:

```python
# Forbidden:
np.random.normal(1.0, cv)
np.random.uniform(0, 1)
np.random.seed(42)

# Allowed:
np.random.default_rng(seed)
self.rng_growth.normal(1.0, cv)
```

**Pattern**: Grep for `np.random.(?!default_rng)` in biological_virtual.py.

**Current status**: ✅ PASS (no global RNG usage)

---

## Validation Tests

### Test 1: Observer Independence (Perfect Seeding)
**Protocol**: Seed with `initial_viability=1.0`, treat with 2.0 µM nocodazole, compare Path A (no painting) vs Path B (painting every 12h).

**Results**:
```
Viability:      51.7% == 51.7%   ✓ Exact match
Death compound: 48.3% == 48.3%   ✓ Exact match
Death mode:     compound == compound ✓
```

**Validates**:
- ✅ RNG stream splitting works
- ✅ CV=0 guards prevent RNG consumption
- ✅ Stable hashing ensures deterministic batch effects

---

### Test 2: Double Dosing (Perfect Seeding)
**Protocol**: Dose at t=4h and t=52h, measure at t=96h.

**Results**:
```
Viability:      22.6% == 22.6%   ✓ Exact match
Death compound: 77.4% == 77.4%   ✓ Exact match
Untracked:      0.000%           ✓ Perfect accounting
```

**Validates**:
- ✅ Multiple treatments don't cause drift
- ✅ Instant death tracking works
- ✅ Accounting partition holds

---

### Test 3: Seeding Stress (Realistic Seeding)
**Protocol**: Seed with default `viability=0.98`, treat at t=4h, measure at t=96h.

**Results**:
```
Before treatment:
  death_unknown: 2.0%            ✓ Seeding stress tracked
  death_mode: "unknown"          ✓ Correctly labeled

After treatment:
  death_compound: 47.3%          ✓ Compound death added
  death_unknown: 2.0%            ✓ Seeding stress persists (not rewritten)
  death_mode: "compound"         ✓ Dominated by compound

Complete partition: 49.3% == 49.3%  ✓ Perfect accounting
```

**Validates**:
- ✅ Unknown death tracked honestly
- ✅ Compound death adds on top (doesn't rewrite history)
- ✅ Complete partition maintained
- ✅ No false warnings about seeding stress

---

## Architecture Summary

### RNG Streams (Observer Independence)
```
BiologicalVirtualMachine(seed=0)
  ↓
rng_growth (seed+1)      → Growth, cell count, viability measurements
rng_treatment (seed+2)   → Treatment biological variability
rng_assay (seed+3)       → Assay noise, morphology measurements
  ↓
Calling cell_painting_assay() ONLY touches rng_assay
  → Cannot perturb rng_growth or rng_treatment
  → Cell fate independent of observation frequency
```

### Death Accounting (Complete Partition)
```
treat_with_compound()
  ↓
Instant death tracked: death_compound += (prev - new)
  ↓
advance_time() → _apply_compound_attrition()
  ↓
Attrition death tracked: death_compound += attrition_delta
  ↓
_update_death_mode()
  ↓
Compute: death_unknown = total_dead - (compound + confluence)
  ↓
Result: death_compound + death_confluence + death_unknown == 1 - viability
```

### Stable Hashing (Cross-Machine Reproducibility)
```
Plate/Day/Operator batch effects
  ↓
stable_u32(f"plate_{plate_id}")  → Same seed on all machines
  ↓
rng_plate = np.random.default_rng(seed)
  ↓
plate_factor = rng_plate.normal(1.0, cv) if cv > 0 else 1.0
  ↓
Deterministic across Python processes, OS, architectures
```

---

## Files Modified

1. **`src/cell_os/hardware/biological_virtual.py`**:
   - Added `stable_u32()` function
   - Added `death_unknown` to `VesselState`
   - Changed seed default to `0` (explicit reproducibility)
   - Updated `_update_death_mode()` for complete partition
   - Replaced all `hash()` with `stable_u32()`
   - Updated result dicts to include `death_unknown`

2. **Test files**:
   - `test_observer_independence.py` - Uses `seed=seed`, `initial_viability=1.0`
   - `test_double_dosing_accounting.py` - Uses `seed=seed`, `initial_viability=1.0`
   - `test_seeding_stress_accounting.py` - NEW, validates unknown death tracking
   - `test_no_global_rng.py` - NEW, enforces RNG hygiene (lint check)
   - `test_stream_isolation.py` - NEW, proves assays don't perturb physics streams

---

## What This Prevents

### ❌ Before Hardening:

1. **Hash salt nondeterminism**:
   - Tests pass on dev machine
   - Tests fail in CI (different hash salt)
   - "Works on my machine" curse

2. **Global RNG coupling**:
   - Tests pass in isolation
   - Tests fail when run in suite (prior state differs)
   - Order-dependent failures

3. **Seeding stress lies**:
   - 2% initial death labeled as "compound" (wrong!)
   - OR ignored entirely (accounting doesn't partition)
   - Can't distinguish seeding issues from treatment effects

4. **Accidental regressions**:
   - Someone adds `np.random.normal()` innocently
   - Observer independence breaks silently
   - Discovered months later

### ✅ After Hardening:

1. **Cross-machine determinism**: Same seed → same results (always)
2. **Observer independence**: Observation frequency can't change physics
3. **Honest accounting**: Unknown death tracked, not invented
4. **Regression prevention**: Lint check fails if global RNG usage added

---

## Stream Isolation Invariant

Calling assays must not perturb physics RNG streams.

We guarantee this by:

1. **Dedicated RNG objects per subsystem** (rng_growth, rng_treatment, rng_assay)

2. **A regression test that snapshots bit_generator.state for each stream before and after an assay call, and asserts only rng_assay changes.**

This catches subtle future regressions like "I used rng_growth for a well-factor because it was convenient."

## Maintenance Guardrails

### 1. Run RNG Hygiene Check in CI
```bash
python3 test_no_global_rng.py || exit 1
```

Prevents global `np.random.*` usage that breaks observer independence.

### 2. Run Stream Isolation Test in CI
```bash
python3 test_stream_isolation.py || exit 1
```

Proves that `cell_painting_assay()` only advances `rng_assay`, not physics streams.
Catches regressions like "I borrowed rng_growth for convenience."

### 3. Require Explicit Seeds in Tests
All tests must pass `seed=<int>`, never rely on default randomness.

### 4. Document Unknown Death Sources
When adding new death mechanisms, decide:
- Is this tracked? → Update `death_compound` or `death_confluence`
- Is this unknown? → Let `death_unknown` absorb it (don't invent cause)

### 5. Validate Complete Partition
After any accounting change, assert:
```python
assert abs((death_compound + death_confluence + death_unknown) - (1 - viability)) < 1e-6
```

---

## Bottom Line

**Before**: Observer-dependent, machine-dependent, invented causality
**After**: Deterministic, reproducible, honest accounting

The simulation is now **immunized** against:
- Cross-machine nondeterminism (stable hashing)
- Observation coupling (split RNG streams)
- Accounting lies (complete partition with unknown bucket)
- Accidental regressions (RNG hygiene enforcement)

**No more "works on my machine" or "observation changes fate" bugs.**
