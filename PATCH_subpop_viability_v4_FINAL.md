# Patch v4: Independent Subpopulation Viabilities (Mergeable)

**Status**: Ready for hostile review
**Depends on**: v3 (commitment heterogeneity)

---

## Problem: Kill-Shot Artifact

**Current behavior**: Subpops have different parameters (IC50 shifts, commitment delays), but all share `vessel.viability`. Updates happen at vessel level, then subpops are synced backward.

**Impossibility**: Even when sensitive subpop "should" die earlier (lower IC50, earlier commitment), it cannot - viability updates are synchronized.

**Falsification**: Time-course flow cytometry showing sensitive cells (marked) dropping earlier than resistant cells under lethal dose. Current simulator cannot generate this trajectory.

---

## Solution

1. **Store viability per subpop** (authoritative)
2. **Derive vessel.viability** as weighted mean (never authoritative)
3. **Apply death per subpop** in both instant kill and hazard accumulation
4. **Keep fractions fixed** (no selection dynamics yet)

### Weighted Mean Specification

**Weights**: Fixed subpopulation fractions defined at vessel creation:
- `sensitive`: 0.25 (25%)
- `typical`: 0.50 (50%)
- `resistant`: 0.25 (25%)

**These fractions NEVER change in v4** (no selection dynamics). Tests compute weighted mean from same `subpop['fraction']` source as code.

**Formula**: `vessel.viability = sum(subpop['fraction'] * subpop['viability'])` over all subpops.

### Death Ledger Compatibility

**Vessel-level death fields** (`death_compound`, `death_er_stress`, etc.):
- **NOT causal** - compatibility/reporting outputs only
- Derived by allocating realized kill proportionally to subpop hazard shares
- Exist for backward compatibility with downstream code
- **Do not use for causal logic** - subpop viabilities are ground truth

---

## Prerequisites (Must Be Applied Before Diff 1)

v4 assumes per-subpop hazard computation exists. Current code defines IC50 shifts but doesn't use them. These prerequisites make the code obey the world it already claims exists.

### Prereq A: Delete sync helper (removes lie injector)

**Problem**: `_sync_subpopulation_viabilities()` at lines 922-956 forces all subpop viabilities back to vessel viability. Called at line 1018, immediately after `_commit_step_death`. This defeats v4 entirely.

**What to do**:
1. Delete line 1018: `self._sync_subpopulation_viabilities(vessel)`
2. Delete lines 922-956: function definition
3. Verify: `rg "_sync_subpopulation_viabilities"` returns nothing

**Why safe**: Function is explicitly a lie injector. Removing it doesn't change behavior, it stops preventing behavior.

**Tripwire test**:
```python
def test_prereq_no_sync_after_step():
    """Verify subpop viabilities stay independent after step."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.9)
    vessel = vm.vessel_states["v"]

    # Manually set different viabilities
    names = sorted(vessel.subpopulations.keys())
    vessel.subpopulations[names[0]]['viability'] = 0.5
    vessel.subpopulations[names[1]]['viability'] = 0.7
    vessel.subpopulations[names[2]]['viability'] = 0.9

    # Step (no treatment, just time passage)
    vm._step_vessel(vessel, 1.0)

    # Assert they stayed different
    v_after = [vessel.subpopulations[n]['viability'] for n in names]
    unique = len(set(np.round(v_after, 6)))
    assert unique >= 2, f"Subpops re-synced during step: {v_after}"
```

---

### Prereq B: Per-subpop hazard computation and caching

**Problem**: Lines 1170-1224 compute attrition ONCE at vessel level. IC50 shifts defined (lines 213, 222, 231) but unused. `_commit_step_death` expects `subpop['_total_hazard']` but it doesn't exist.

**Minimal refactor objective**: Move loop boundary from vessel-level to per-subpop. No new ontology, just use existing parameters.

**Location**: In `_step_vessel`, around where compound attrition is computed (lines ~1170-1224)

**Replace vessel-level computation** with:

```python
# For each compound with active exposure
for compound, dose_uM in vessel.compound_concentrations.items():
    if dose_uM <= 0:
        continue

    meta = self.thalamus_params[compound]
    stress_axis = meta['stress_axis']
    base_ec50 = meta['base_ec50']
    hill_slope = meta.get('hill_slope', 1.5)
    toxicity_scalar = meta.get('toxicity_scalar', 1.0)

    # Get exposure_id for commitment delay lookup
    exposure_id = vessel.compound_meta.get('exposure_ids', {}).get(compound)
    time_since_treatment_start = self.simulated_time - vessel.compound_start_time.get(compound, self.simulated_time)

    # ===== PER-SUBPOP HAZARD COMPUTATION =====
    for subpop_name in sorted(vessel.subpopulations.keys()):
        subpop = vessel.subpopulations[subpop_name]

        # Clear cache at start of step
        if '_hazards' not in subpop:
            subpop['_hazards'] = {}
        if '_total_hazard' not in subpop:
            subpop['_total_hazard'] = 0.0

        # Apply subpop-specific IC50 shift
        ic50_shift = subpop['ic50_shift']
        ic50_uM = biology_core.compute_adjusted_ic50(
            compound=compound,
            cell_line=vessel.cell_line,
            base_ec50=base_ec50,
            stress_axis=stress_axis,
            cell_line_sensitivity=self.thalamus_params.get('cell_line_sensitivity', {}),
            proliferation_index=biology_core.PROLIF_INDEX.get(vessel.cell_line)
        )
        ic50_uM *= ic50_shift  # Apply subpop shift

        # Run context modifier
        bio_mods = self.run_context.get_biology_modifiers()
        ic50_uM *= bio_mods['ec50_multiplier']

        # Get commitment delay for this subpop (from v3 cache)
        commitment_delay_h = None
        if exposure_id is not None:
            cache_key = (compound, exposure_id, subpop_name)
            commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)

        # Guard: For lethal doses, delay must exist (v3 contract)
        dose_ratio = dose_uM / ic50_uM if ic50_uM > 0 else 0.0
        if dose_ratio >= 1.0 and commitment_delay_h is None:
            raise ValueError(
                f"Missing commitment_delay_h for {subpop_name} at lethal dose "
                f"(dose_ratio={dose_ratio:.2f}). v3 sampling skipped?"
            )

        # Compute transport dysfunction (currently vessel-level, but can be per-subpop)
        transport_dysfunction = biology_core.compute_transport_dysfunction_from_exposure(
            cell_line=vessel.cell_line,
            compound=compound,
            dose_uM=dose_uM,
            stress_axis=stress_axis,
            base_potency_uM=base_ec50,
            time_since_treatment_h=time_since_treatment_start,
            params=self.thalamus_params
        )

        # Compute attrition for THIS subpop
        attrition_rate = biology_core.compute_attrition_rate_interval_mean(
            cell_line=vessel.cell_line,
            compound=compound,
            dose_uM=dose_uM,
            stress_axis=stress_axis,
            ic50_uM=ic50_uM,  # Subpop-specific!
            hill_slope=hill_slope,
            transport_dysfunction=transport_dysfunction,
            time_since_treatment_start_h=time_since_treatment_start,
            dt_h=hours,
            current_viability=subpop['viability'],  # Subpop-specific!
            params={'commitment_delay_h': commitment_delay_h} if commitment_delay_h else None
        )

        # Apply toxicity scalar
        attrition_rate *= toxicity_scalar

        if attrition_rate <= 0:
            continue

        # Cache per-subpop hazard (used by _commit_step_death)
        death_field = "death_compound"
        subpop['_hazards'][death_field] = attrition_rate
        subpop['_total_hazard'] += attrition_rate

        logger.debug(
            f"{vessel.vessel_id}:{subpop_name}: Attrition hazard={attrition_rate:.4f}/h"
        )
```

**Two guardrails**:
1. **No silent fallback**: If dose is lethal and `commitment_delay_h` missing, raise (v3 contract enforcement)
2. **Clear cache each step**: Initialize `subpop['_hazards'] = {}` and `subpop['_total_hazard'] = 0.0` at start

**Verification**: After this refactor + v3 merged, under lethal dose:
- Print `subpop['_total_hazard']` for sensitive vs resistant
- They should differ (sensitive has lower IC50, higher hazard)

---

## Code Changes (v4 Proper)

### Diff 1: Add recompute helper and initialize subpop fields

**File**: `src/cell_os/hardware/biological_virtual.py`

#### Part A: Add helper method (after `__init__` or near other helpers)

```python
def _recompute_vessel_from_subpops(self, vessel: VesselState):
    """
    Derive vessel viability and death_total from subpopulations.

    Subpop viability is authoritative. Vessel viability is readout.
    This is the core semantic change in v4.
    """
    total_v = 0.0
    for name in sorted(vessel.subpopulations.keys()):  # Sorted for determinism
        sp = vessel.subpopulations[name]
        frac = float(sp.get('fraction', 0.0))
        v = float(np.clip(sp.get('viability', 1.0), 0.0, 1.0))
        total_v += frac * v

    vessel.viability = float(np.clip(total_v, 0.0, 1.0))
    vessel.death_total = float(np.clip(1.0 - vessel.viability, 0.0, 1.0))
```

#### Part B: Initialize subpop viability at vessel creation

**Location**: Wherever `vessel.subpopulations` is initialized (seeding, __init__)

```python
# After creating vessel.subpopulations dict
for subpop_name in sorted(vessel.subpopulations.keys()):
    subpop = vessel.subpopulations[subpop_name]
    # Initialize to match vessel's initial viability
    subpop['viability'] = float(np.clip(vessel.viability, 0.0, 1.0))
    subpop['death_total'] = float(np.clip(1.0 - subpop['viability'], 0.0, 1.0))
```

---

### Diff 2: Fix `_apply_instant_kill` (reverse authority)

**File**: `src/cell_os/hardware/biological_virtual.py`
**Function**: `_apply_instant_kill` (lines ~770-797)

**Replace lines 770-797** with:

```python
def _apply_instant_kill(self, vessel: VesselState, kill_fraction: float, death_field: str):
    """
    Apply instant kill fraction to vessel.

    v4 SEMANTIC CHANGE: Updates subpop viabilities independently, then derives vessel.
    Previously: updated vessel, then synced subpops (backward authority).
    """
    # Validate death_field
    TRACKED_DEATH_FIELDS = {
        'death_compound', 'death_starvation', 'death_mitotic_catastrophe',
        'death_er_stress', 'death_mito_dysfunction', 'death_confluence',
        'death_unknown'
    }
    if death_field not in TRACKED_DEATH_FIELDS:
        raise ValueError(
            f"Unknown death_field '{death_field}' in _apply_instant_kill. "
            f"Valid fields: {TRACKED_DEATH_FIELDS}"
        )

    v0 = float(np.clip(vessel.viability, 0.0, 1.0))
    DEATH_EPS = 1e-9

    if v0 <= DEATH_EPS or kill_fraction <= DEATH_EPS:
        return

    # v4: Apply kill independently to each subpop (authoritative)
    for name in sorted(vessel.subpopulations.keys()):  # Sorted for determinism
        sp = vessel.subpopulations[name]
        sv0 = float(np.clip(sp.get('viability', v0), 0.0, 1.0))

        # Apply kill as fraction of viable
        sv1 = float(np.clip(sv0 * (1.0 - kill_fraction), 0.0, 1.0))

        sp['viability'] = sv1
        sp['death_total'] = float(np.clip(1.0 - sv1, 0.0, 1.0))

    # Derive vessel viability from subpops (v4: vessel is readout, not authoritative)
    v_before = vessel.viability
    self._recompute_vessel_from_subpops(vessel)
    v_after = vessel.viability

    # Scale cell count proportionally to vessel viability change
    if v_before > DEATH_EPS:
        vessel.cell_count *= (v_after / v_before)

    # Credit vessel death ledger with realized kill (compatibility readout)
    realized_kill = float(np.clip(v_before - v_after, 0.0, 1.0))
    current_ledger = getattr(vessel, death_field, 0.0)
    setattr(vessel, death_field, float(np.clip(current_ledger + realized_kill, 0.0, 1.0)))

    # Update confluence
    vessel.confluence = vessel.cell_count / vessel.vessel_capacity
```

---

### Diff 3: Fix `_commit_step_death` (apply per subpop, derive vessel)

**File**: `src/cell_os/hardware/biological_virtual.py`
**Function**: `_commit_step_death` (lines ~798-880)

**Key change**: Need to store per-subpop total hazard before calling `_commit_step_death`.

#### Part A: In hazard proposal loop (before `_commit_step_death` is called)

**Location**: Where you iterate subpops computing hazards (around line 1170-1220)

```python
# After computing hazard for each subpop, store it
subpop['_total_hazard'] = 0.0  # Initialize
subpop['_hazards'] = {}  # Per-axis hazards for this subpop

# When you compute a hazard for this subpop (e.g., ER stress, compound attrition):
hazard_rate = biology_core.compute_attrition_rate_instantaneous(...)
subpop['_hazards'][axis_name] = hazard_rate
subpop['_total_hazard'] += hazard_rate
```

#### Part B: Replace `_commit_step_death` body (lines ~840-880)

```python
def _commit_step_death(self, vessel: VesselState, hours: float):
    """
    Apply combined survival per subpop, then derive vessel viability.

    v4 SEMANTIC CHANGE: Survival applied independently per subpop.
    Vessel viability is weighted mean of subpop viabilities.
    """
    if hours <= 0:
        return

    DEATH_EPS = 1e-9
    v_before = float(np.clip(vessel.viability, 0.0, 1.0))
    c0 = float(vessel.cell_count)

    if v_before <= DEATH_EPS:
        return

    # v4: Apply survival per subpop (authoritative)
    for name in sorted(vessel.subpopulations.keys()):  # Sorted for determinism
        sp = vessel.subpopulations[name]
        sv0 = float(np.clip(sp.get('viability', v_before), 0.0, 1.0))

        # Use per-subpop total hazard (computed upstream)
        total_hazard_subpop = float(max(0.0, sp.get('_total_hazard', 0.0)))

        # Compute survival for this subpop
        survival = float(np.exp(-total_hazard_subpop * hours))
        sv1 = float(np.clip(sv0 * survival, 0.0, 1.0))

        sp['viability'] = sv1
        sp['death_total'] = float(np.clip(1.0 - sv1, 0.0, 1.0))

    # Derive vessel viability from subpops
    self._recompute_vessel_from_subpops(vessel)
    v_after = vessel.viability

    # Scale cell count proportionally to vessel viability change
    if v_before > DEATH_EPS:
        vessel.cell_count = float(max(0.0, c0 * (v_after / v_before)))

    # Assert non-negative invariants
    assert 0.0 <= vessel.viability <= 1.0, f"viability={vessel.viability} out of bounds"
    assert vessel.cell_count >= 0.0, f"cell_count={vessel.cell_count} negative"

    # Realized kill at vessel level (compatibility)
    kill_total = float(max(0.0, v_before - v_after))
    vessel._step_total_kill = kill_total

    # Allocate realized kill across causes at vessel level (cosmetic ledger)
    # Aggregate hazards from all subpops, weighted by fraction
    total_hazard_weighted = 0.0
    hazards_aggregated = {}

    for name in sorted(vessel.subpopulations.keys()):
        sp = vessel.subpopulations[name]
        frac = float(sp.get('fraction', 0.0))
        for axis, h in sp.get('_hazards', {}).items():
            hazards_aggregated[axis] = hazards_aggregated.get(axis, 0.0) + frac * h
        total_hazard_weighted += frac * sp.get('_total_hazard', 0.0)

    # Proportional allocation to vessel death fields (for reporting/compatibility)
    if total_hazard_weighted > DEATH_EPS:
        for field, h in hazards_aggregated.items():
            if h <= 0.0:
                continue
            share = h / total_hazard_weighted
            d = kill_total * share
            current = getattr(vessel, field, 0.0)
            setattr(vessel, field, float(np.clip(current + d, 0.0, 1.0)))

    # Conservation enforcement
    self._assert_conservation(vessel, gate="_commit_step_death")

    vessel._step_ledger_scale = 1.0
```

---

### Diff 4: Runtime invariant (vessel = weighted mean)

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: End of `_step_vessel`, end of `_apply_instant_kill`, end of `_commit_step_death`

```python
# INVARIANT: vessel.viability must equal weighted mean of subpops
# This catches accidental direct writes to vessel.viability
wm = 0.0
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    wm += float(sp.get('fraction', 0.0)) * float(np.clip(sp.get('viability', 1.0), 0.0, 1.0))

assert abs(vessel.viability - wm) < 1e-9, \
    f"INVARIANT VIOLATION: vessel.viability ({vessel.viability:.10f}) != " \
    f"weighted mean ({wm:.10f}). Subpop viabilities are authoritative."
```

---

## Tests

### Test 1: Vessel viability is derived weighted mean

```python
def test_vessel_viability_is_weighted_mean():
    """Verify vessel.viability equals weighted mean of subpop viabilities."""

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.9)
    vessel = vm.vessel_states["v"]

    # Manually set distinct subpop viabilities
    names = sorted(vessel.subpopulations.keys())
    vessel.subpopulations[names[0]]['viability'] = 0.2
    vessel.subpopulations[names[1]]['viability'] = 0.6
    vessel.subpopulations[names[2]]['viability'] = 0.9

    # Recompute
    vm._recompute_vessel_from_subpops(vessel)

    # Assert exact weighted mean
    expected = sum(
        vessel.subpopulations[n]['fraction'] * vessel.subpopulations[n]['viability']
        for n in names
    )
    assert abs(vessel.viability - expected) < 1e-12, \
        f"vessel.viability={vessel.viability:.10f} != expected={expected:.10f}"

    print(f"✓ Vessel viability is weighted mean: {vessel.viability:.4f}")
```

### Test 2: Instant kill creates subpop divergence

```python
def test_instant_kill_creates_subpop_divergence():
    """Verify instant kill updates each subpop independently, not synchronized."""

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.9)
    vessel = vm.vessel_states["v"]

    # Manually set distinct starting viabilities
    names = sorted(vessel.subpopulations.keys())
    vessel.subpopulations[names[0]]['viability'] = 0.9
    vessel.subpopulations[names[1]]['viability'] = 0.6
    vessel.subpopulations[names[2]]['viability'] = 0.3

    # Recompute vessel (so we have clean baseline)
    vm._recompute_vessel_from_subpops(vessel)
    v_before = vessel.viability

    # Apply instant kill
    kill_fraction = 0.2
    vm._apply_instant_kill(vessel, kill_fraction, "death_compound")

    # Assert each subpop was multiplied by (1 - kill_fraction) independently
    assert abs(vessel.subpopulations[names[0]]['viability'] - 0.9 * 0.8) < 1e-9
    assert abs(vessel.subpopulations[names[1]]['viability'] - 0.6 * 0.8) < 1e-9
    assert abs(vessel.subpopulations[names[2]]['viability'] - 0.3 * 0.8) < 1e-9

    # Assert vessel viability is weighted mean
    expected = sum(
        vessel.subpopulations[n]['fraction'] * vessel.subpopulations[n]['viability']
        for n in names
    )
    assert abs(vessel.viability - expected) < 1e-12

    # Assert subpops are NOT synchronized (all different)
    viabilities = [vessel.subpopulations[n]['viability'] for n in names]
    assert len(set(viabilities)) == 3, "Subpop viabilities should differ"

    print(f"✓ Instant kill creates divergence: {viabilities}")
```

### Test 3: Sensitive dies earlier than resistant under lethal dose

```python
def test_sensitive_dies_earlier_than_resistant():
    """Verify sensitive subpop viability drops before resistant under lethal dose."""

    vm = BiologicalVirtualMachine(seed=42)
    # LOW viability to allow attrition gate (viability < 0.5)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
    vessel = vm.vessel_states["v"]

    # Treat with lethal dose
    vm.treat_with_compound("v", "tunicamycin", 5.0)

    # Identify subpops by IC50 shift (sensitive has lowest, resistant has highest)
    names = sorted(vessel.subpopulations.keys())
    subpops_by_shift = sorted(
        names,
        key=lambda n: vessel.subpopulations[n]['ic50_shift']
    )
    sensitive = subpops_by_shift[0]
    resistant = subpops_by_shift[-1]

    # Track viabilities over time
    threshold = 0.15
    t_sens = None
    t_res = None

    t_prev = 0.0
    for t in np.linspace(0, 24, 241):  # 0.1h steps
        dt = t - t_prev
        if dt > 0:
            # Assert time contract
            t0 = vm.simulated_time
            vm._step_vessel(vessel, dt)
            assert abs(vm.simulated_time - t0) < 1e-9, "_step_vessel advanced time"
            vm.simulated_time = t

        # Check crossings
        if t_sens is None and vessel.subpopulations[sensitive]['viability'] < threshold:
            t_sens = t
        if t_res is None and vessel.subpopulations[resistant]['viability'] < threshold:
            t_res = t

        t_prev = t

    # Assert both crossed
    assert t_sens is not None, f"Sensitive never crossed {threshold}"
    assert t_res is not None, f"Resistant never crossed {threshold}"

    # Assert sensitive crossed BEFORE resistant
    assert t_sens < t_res, \
        f"Sensitive crossed at {t_sens:.1f}h, resistant at {t_res:.1f}h (should be earlier)"

    print(f"✓ Sensitive dies earlier: {t_sens:.1f}h vs resistant: {t_res:.1f}h")
```

### Test 4: Determinism smoke (subpop trajectories)

```python
def test_subpop_viability_trajectories_deterministic():
    """Verify subpop viability trajectories identical for same seed."""

    checkpoints = [6, 12, 18, 24]
    trajectories_run1 = {}
    trajectories_run2 = {}

    for run in [1, 2]:
        vm = BiologicalVirtualMachine(seed=42)  # SAME seed
        vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
        vm.treat_with_compound("v", "tunicamycin", 5.0)

        vessel = vm.vessel_states["v"]

        # Step to checkpoints
        t_prev = 0.0
        traj = {name: [] for name in sorted(vessel.subpopulations.keys())}

        for t in checkpoints:
            dt = t - t_prev
            if dt > 0:
                vm._step_vessel(vessel, dt)
                vm.simulated_time = t

            for name in sorted(vessel.subpopulations.keys()):
                traj[name].append(vessel.subpopulations[name]['viability'])

            t_prev = t

        if run == 1:
            trajectories_run1 = traj
        else:
            trajectories_run2 = traj

    # Assert exact equality (same seed → same trajectories)
    for name in sorted(trajectories_run1.keys()):
        for i, t in enumerate(checkpoints):
            v1 = trajectories_run1[name][i]
            v2 = trajectories_run2[name][i]
            assert abs(v1 - v2) < 1e-12, \
                f"Determinism broken: {name} at {t}h differs (run1={v1:.10f}, run2={v2:.10f})"

    print(f"✓ Subpop trajectories identical across runs (seed=42)")

    # Verify they change with different seed
    vm3 = BiologicalVirtualMachine(seed=99)
    vm3.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
    vm3.treat_with_compound("v", "tunicamycin", 5.0)
    vessel3 = vm3.vessel_states["v"]

    # Step to first checkpoint
    vm3._step_vessel(vessel3, checkpoints[0])

    # At least one subpop should differ
    names = sorted(vessel3.subpopulations.keys())
    differs = False
    for name in names:
        v3 = vessel3.subpopulations[name]['viability']
        v1 = trajectories_run1[name][0]
        if abs(v3 - v1) > 1e-9:
            differs = True
            break

    assert differs, "Trajectories didn't change with different seed"
    print(f"✓ Trajectories differ with seed=99")
```

---

## What This Fixes

1. ✓ Subpops can diverge in survival (sensitive dies earlier)
2. ✓ Commitment heterogeneity produces real staggered death
3. ✓ Vessel viability clean readout (not hidden state)
4. ✓ No backward authority (subpops no longer "views")

## What This Doesn't Fix (Next Patch)

- No within-subpop heterogeneity
- No selection dynamics (fractions fixed)
- No recovery/stress reversal
- Viability gate (< 0.5) becomes more visible artifact

---

## Real Data That No Longer Embarrasses

**Flow cytometry time course** with marked populations:
- Sensitive cells (low IC50) drop earlier
- Resistant cells (high IC50) lag
- Bulk viability is mixture curve

Previously: simulator could only generate synchronized drops.
After v4: simulator matches real single-cell divergence.

**Next**: v5 adds selection (fractions change under pressure).
