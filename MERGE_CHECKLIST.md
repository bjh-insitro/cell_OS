# Merge Checklist: Commitment Heterogeneity Patch v3

## Status: READY TO MERGE (after verification)

All hostile review issues addressed. Tests are real tripwires, not motivational posters.

---

## Deliverables

- ✓ **AUDIT_DELIVERABLE.md** - Complete statistical analysis, confidence statement
- ✓ **test_12h_commitment_artifact.py** - Proof artifact exists (28,058× jump)
- ✓ **PATCH_commitment_heterogeneity_v3_FINAL.md** - Implementation specification
- ✓ **test_commitment_heterogeneity_v3_MERGEABLE.py** - Four hardened tests

---

## Code Changes

### Change 1: Add exposure ID counter
**File**: `src/cell_os/hardware/biological_virtual.py:450`
```python
self.next_exposure_id = 0
```

### Change 2: Sample commitment delays (with guards)
**File**: `src/cell_os/hardware/biological_virtual.py:2061`

Add IC50 validity guard BEFORE dose_ratio:
```python
if ic50_uM is None or not np.isfinite(ic50_uM) or ic50_uM <= 0:
    raise ValueError(f"Invalid IC50 {ic50_uM} for {compound}")
```

Then sample delays (full code in patch doc):
- Sorted iteration: `sorted(vessel.subpopulations.keys())`
- dose_ratio computed once
- Always sample if dose_uM > 0
- Bounds [1.5h, 48h]
- Integer exposure_id cache key

### Change 3: Retrieve commitment delay (sorted iteration)
**File**: `src/cell_os/hardware/biological_virtual.py:~1184`

Change loop:
```python
for subpop_name in sorted(vessel.subpopulations.keys()):
    subpop = vessel.subpopulations[subpop_name]
```

Retrieve delay:
```python
exposure_id = vessel.compound_meta.get('exposure_ids', {}).get(compound)
if exposure_id is not None:
    cache_key = (compound, exposure_id, subpop_name)
    commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)
else:
    commitment_delay_h = None

params = {'commitment_delay_h': commitment_delay_h} if commitment_delay_h else None
```

### Change 4: Reorder attrition with strong fallback contract
**File**: `src/cell_os/sim/biology_core.py:439-452`

Replace with (order matters):
```python
# 1. IC50 validity guard
if ic50_uM is None or not np.isfinite(ic50_uM) or ic50_uM <= 0:
    raise ValueError(f"Invalid IC50 {ic50_uM} for {compound}")

# 2. World A check FIRST
dose_ratio = dose_uM / ic50_uM
if dose_ratio < 1.0:
    return 0.0

# 3. Viability gate
if current_viability >= 0.5:
    return 0.0

# 4. Commitment delay gate
if params and params.get('commitment_delay_h') is not None:
    commitment_delay_h = params['commitment_delay_h']
else:
    # STRONG CONTRACT: Fallback only for pre-patch or sublethal
    # Missing delay for lethal dose indicates a bug
    if dose_ratio >= 1.0:
        raise ValueError(
            f"Missing commitment_delay_h for lethal dose "
            f"(dose_ratio={dose_ratio:.2f}). Sampling skipped incorrectly."
        )
    commitment_delay_h = 12.0

if time_since_treatment_h <= commitment_delay_h:
    return 0.0
```

---

## Tests (Run Before Merge)

### 1. Hardened Tests
```bash
cd /Users/bjh/cell_OS
PYTHONPATH=.:$PYTHONPATH python3 \
  tests/statistical_audit/test_commitment_heterogeneity_v3_MERGEABLE.py
```

Expected output:
```
✓ Maximum derivative ratio: <100× (smooth)
✓ All lethal doses have sampled delays
✓ Attrition activates at ≥2 distinct times
✓ Commitment heterogeneity with stable CV
✓ All tests passed - READY TO MERGE
```

### 2. Original Artifact Test (Should Change After Patch)
```bash
PYTHONPATH=.:$PYTHONPATH python3 \
  tests/statistical_audit/test_12h_commitment_artifact.py
```

Before patch: Jump magnitude 28,058×
After patch: Should fail or show <<1000× (artifact removed)

### 3. Determinism Smoke Test (New RNG draws)
```python
# Add to test file or run manually
def test_commitment_delays_deterministic():
    """Verify sampled delays are identical across runs with same seed."""

    delays_run1 = {}
    delays_run2 = {}

    for run in [1, 2]:
        vm = BiologicalVirtualMachine(seed=42)  # SAME seed
        vessel_id = "P1_A01"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)

        vessel = vm.vessel_states[vessel_id]
        exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']

        delays = {}
        for subpop_name in sorted(vessel.subpopulations.keys()):
            key = ('tunicamycin', exposure_id, subpop_name)
            delays[subpop_name] = vessel.compound_meta['commitment_delays'][key]

        if run == 1:
            delays_run1 = delays
        else:
            delays_run2 = delays

    # Assert exact equality (same seed → same draws)
    for subpop in ['sensitive', 'typical', 'resistant']:
        assert delays_run1[subpop] == delays_run2[subpop], \
            f"Determinism broken: {subpop} delays differ across runs"

    print(f"✓ Delays identical across runs (seed=42): {delays_run1}")

    # Verify they change with different seed
    vm3 = BiologicalVirtualMachine(seed=99)
    vessel_id = "P1_A01"
    vm3.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm3.treat_with_compound(vessel_id, "tunicamycin", 5.0)

    vessel = vm3.vessel_states[vessel_id]
    exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
    delays_run3 = {
        s: vessel.compound_meta['commitment_delays'][('tunicamycin', exposure_id, s)]
        for s in sorted(vessel.subpopulations.keys())
    }

    # At least one should differ
    assert any(delays_run1[s] != delays_run3[s] for s in delays_run1.keys()), \
        "Delays didn't change with different seed"

    print(f"✓ Delays differ with seed=99: {delays_run3}")
```

**Why this matters**: New RNG draws in `rng_treatment`. If ordering changes elsewhere, determinism breaks silently.

### 4. No Hidden Fallback Invariant (Runtime Guard)
Add to `biology_core.py:compute_attrition_rate_instantaneous` after World A check:

```python
# After World A check (dose_ratio < 1.0 returns 0.0)
# Before viability check

# INVARIANT: For lethal doses, commitment_delay_h must be provided
# Missing delay indicates sampling was skipped (bug in treat_with_compound)
if dose_ratio >= 1.0:
    if params is None or params.get('commitment_delay_h') is None:
        raise ValueError(
            f"INVARIANT VIOLATION: Missing commitment_delay_h for lethal dose.\n"
            f"  compound: {compound}\n"
            f"  dose_uM: {dose_uM:.2f}\n"
            f"  ic50_uM: {ic50_uM:.2f}\n"
            f"  dose_ratio: {dose_ratio:.2f}\n"
            f"This indicates sampling was skipped in treat_with_compound.\n"
            f"Check exposure_id and cache key generation."
        )
```

**Why this matters**: Turns future regression (sampling skipped) into loud failure, not silent fallback to 12h. No longer a "fallback," it's a **compatibility mode + invariant**.

---

## What This Fixes

1. ✓ Population synchronization removed (no sharp kink at 12h)
2. ✓ Dose-dependent commitment (high dose commits faster)
3. ✓ Per-subpopulation heterogeneity
4. ✓ No new ontology (uses existing 3-bucket model)
5. ✓ Determinism preserved (sorted iteration + determinism smoke test)
6. ✓ IC50 mismatch eliminated (always sample)
7. ✓ Fail loudly on junk (IC50 guards)
8. ✓ **Invariant enforcement** (not "fallback"): Missing delays for lethal doses → raise

---

## What This Doesn't Fix (Next Patch)

**Subpopulation viabilities synchronized** (line 922-956):
- All subpops share vessel.viability
- No differential death rates
- No selection pressure
- No Darwinian dynamics

After commitment heterogeneity, this becomes the next visible lie:
different commitment delays but identical death trajectories = uncanny valley.

Next structural upgrade:
1. Independent viability per subpop
2. Selection changes fractions over time
3. True clonal dynamics

---

## Sign-Off

**Ready to merge** after:
1. All four code changes applied
2. Tests pass (output matches expected)
3. Original artifact test shows change

**Merge command**:
```bash
git add src/cell_os/hardware/biological_virtual.py
git add src/cell_os/sim/biology_core.py
git add tests/statistical_audit/
git commit -m "fix: remove 12h commitment threshold, add per-subpop heterogeneity

- Replaces hard 12h gate with dose-dependent lognormal sampling
- Adds per-subpopulation commitment delays [1.5h, 48h]
- Uses integer exposure IDs (no float drift)
- Sorted iteration for determinism
- IC50 validity guards (fail loudly on junk)
- Four hardened regression tests

Closes #XXX (12h synchronization artifact)"
```
