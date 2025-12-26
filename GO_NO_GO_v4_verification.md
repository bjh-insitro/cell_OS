# Go/No-Go Verification: Subpop Viability v4

**Status**: ✅ **CONDITIONAL GO ACCEPTED**
**Date**: 2025-12-25
**Updated**: After user review

---

## Executive Summary

**RESULT**: ✅ **GO** - v4 can ship after prerequisites applied.

**Key Decision**: Reframe blockers as "prerequisites" (not extra features). Prerequisites make code obey world it already claims exists.

**Critical Finding**: Per-subpop hazard computation does NOT exist in current codebase. IC50 shifts defined but unused. Prerequisites make them real.

**Structure**:
- **Prerequisites** (unglamorous honesty work): Delete sync, add per-subpop hazards
- **v4 Proper** (4 surgical diffs): Reverse authority direction

See: `PATCH_subpop_viability_v4_FINAL.md` and `MERGE_CHECKLIST_v4.md` for full specification.

---

## Checklist Results

### ✅ Check 1: Sync-to-Vessel Patterns

**Search Command**:
```bash
rg -n "subpop\['viability'\]\s*=\s*vessel\.viability" src/cell_os
```

**Found**: 3 instances (all in `biological_virtual.py`)

#### Line 793: `_apply_instant_kill`
```python
# Sync subpops to vessel (epistemic-only model)
# Don't try to "distribute" kill - just sync viabilities
for subpop in vessel.subpopulations.values():
    subpop['viability'] = vessel.viability
```

**Status**: ✅ This is EXACTLY the backward authority that Diff 2 will replace.

**Diff 2 removes lines 770-797** and replaces with forward authority:
```python
# NEW: Apply kill to each subpop independently
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    sv0 = sp['viability']
    sv1 = sv0 * (1.0 - kill_fraction)
    sp['viability'] = sv1

# Derive vessel from subpops (FORWARD!)
self._recompute_vessel_from_subpops(vessel)
```

**Verification**: ✅ Diff 2 will eliminate this pattern.

---

#### Lines 945, 956: Sync helper function `_sync_subpopulation_viabilities`

**Function definition**: Lines 922-956
**Function call**: Line 1018 in `_step_vessel` (right after `_commit_step_death`)

```python
def _sync_subpopulation_viabilities(self, vessel: VesselState):
    """
    Phase 5: Sync subpopulation viabilities to vessel viability (epistemic-only model).
    - For now, we sync them to avoid the semantic break of "post-hoc synthetic death"
    """
    # Simple sync: all subpops have same viability as vessel
    for subpop in vessel.subpopulations.values():
        subpop['viability'] = vessel.viability

    # Verify mixture equals vessel (should be exact by construction)
    mixture = vessel.viability_mixture
    if abs(mixture - vessel.viability) > 1e-9:
        logger.error(...)
        # Force sync
        for subpop in vessel.subpopulations.values():
            subpop['viability'] = vessel.viability
```

**Status**: 🔴 **CRITICAL** - This function is called AFTER `_commit_step_death` in every step.

**Impact**: Even if Diff 3 makes `_commit_step_death` use per-subpop hazards, this sync call will **immediately overwrite** all subpop viabilities with vessel viability.

**Result**: All subpop viabilities will be synchronized again, defeating v4 entirely.

**Action Required**:
1. **REMOVE** line 1018: `self._sync_subpopulation_viabilities(vessel)`
2. **DELETE** function definition (lines 922-956)
3. **CRITICAL**: This must be done BEFORE or WITH v4 diffs, not after

**Recommendation**: This is the #1 "passing locally while lying" risk. The function literally exists to enforce backward authority. DELETE IMMEDIATELY.

---

### 🔴 Check 2: Per-Subpop Hazard Storage

**Search Command**:
```bash
rg -n "_total_hazard" src/cell_os/hardware/biological_virtual.py
```

**Found**: 4 instances, ALL vessel-level:

```
266:        self._step_total_hazard: float = 0.0           # Vessel field init
820:            vessel._step_total_hazard = 0.0            # Reset in _commit_step_death
829:        vessel._step_total_hazard = total_hazard       # Vessel-level aggregation
990:        vessel._step_total_hazard = 0.0                # Reset in _step_vessel
```

**Status**: 🔴 **DOES NOT EXIST** - No per-subpop hazard storage.

**Current Attrition Computation** (lines 1170-1224):
- Computes attrition ONCE at vessel level
- Uses vessel-level IC50 (no ic50_shift applied)
- Proposes to vessel-level `_step_hazard_proposals` dict
- No loop over subpopulations

**Critical Code** (line 1202-1214):
```python
attrition_rate = biology_core.compute_attrition_rate_interval_mean(
    cell_line=vessel.cell_line,
    compound=compound,
    dose_uM=dose_uM,
    stress_axis=stress_axis,
    ic50_uM=ic50_uM,  # ← Vessel-level IC50, no subpop shift applied
    hill_slope=hill_slope,
    transport_dysfunction=transport_dysfunction,
    time_since_treatment_start_h=time_since_treatment_start,
    dt_h=hours,
    current_viability=vessel.viability,  # ← Vessel-level viability
    params=self.thalamus_params
)
```

**What's Missing**:
1. Loop over `sorted(vessel.subpopulations.keys())`
2. Apply `subpop['ic50_shift']` to compute subpop-specific IC50
3. Retrieve `commitment_delay_h` from `vessel.compound_meta['commitment_delays'][cache_key]`
4. Compute attrition per subpop with subpop-specific parameters
5. Store `subpop['_total_hazard']` and `subpop['_hazards']`

**Prerequisite Work Required**:

#### Option A: Refactor lines 1170-1224 (preferred)

**BEFORE Diff 3**, replace vessel-level attrition computation with per-subpop loop:

```python
# For each compound with active exposure
for compound, dose_uM in vessel.compound_concentrations.items():
    if dose_uM <= 0:
        continue

    meta = self.thalamus_params[compound]
    stress_axis = meta['stress_axis']
    base_ec50 = meta['base_ec50']
    hill_slope = meta.get('hill_slope', 1.5)

    # Get exposure_id for commitment delay lookup
    exposure_id = vessel.compound_meta.get('exposure_ids', {}).get(compound)

    # Time since treatment
    time_since_treatment_start = self.simulated_time - vessel.compound_start_time.get(compound, self.simulated_time)

    # ===== NEW: LOOP OVER SUBPOPULATIONS =====
    for subpop_name in sorted(vessel.subpopulations.keys()):
        subpop = vessel.subpopulations[subpop_name]

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

        # Get commitment delay for this subpop
        commitment_delay_h = None
        if exposure_id is not None:
            cache_key = (compound, exposure_id, subpop_name)
            commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)

        # Compute transport dysfunction (can use subpop-specific or vessel-level)
        transport_dysfunction = subpop.get('transport_dysfunction', 0.0)

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
        toxicity_scalar = meta.get('toxicity_scalar', 1.0)
        attrition_rate *= toxicity_scalar

        # Store per-subpop hazard
        if '_hazards' not in subpop:
            subpop['_hazards'] = {}
        if '_total_hazard' not in subpop:
            subpop['_total_hazard'] = 0.0

        subpop['_hazards'][death_field] = attrition_rate
        subpop['_total_hazard'] += attrition_rate
```

**Impact**:
- Changes attrition from vessel-level to subpop-level (SEMANTIC CHANGE)
- Requires v3 (commitment heterogeneity) to be merged first
- Makes IC50 shifts and commitment delays actually matter

---

#### Option B: Minimal shim (NOT RECOMMENDED)

Add storage without refactoring loop (vessel-level hazard duplicated to all subpops):

```python
# After current attrition computation (line 1224)
# Shim: Distribute vessel hazard equally to all subpops
for subpop in vessel.subpopulations.values():
    if '_hazards' not in subpop:
        subpop['_hazards'] = {}
    if '_total_hazard' not in subpop:
        subpop['_total_hazard'] = 0.0
    subpop['_hazards']["death_compound"] = attrition_rate
    subpop['_total_hazard'] += attrition_rate
```

**Why NOT recommended**:
- All subpops get SAME hazard (ignores IC50 shifts)
- v4 diffs will "work" but subpops won't actually diverge
- Tests will FAIL (sensitive doesn't die earlier than resistant)
- Defeats entire purpose of v4

**Verdict**: ❌ Don't use Option B. It's a lie.

---

### ⚠️ Check 3: Vessel Viability Mutation Points

**Search Command**:
```bash
rg -n "vessel\.viability\s*=" src/cell_os/hardware/biological_virtual.py
```

**Found**: 5 direct mutations

#### Line 780: `_apply_instant_kill`
```python
vessel.viability = v1
```

**Status**: ✅ Will be replaced by Diff 2 with `self._recompute_vessel_from_subpops(vessel)`

---

#### Lines 836, 847: `_commit_step_death`
```python
vessel.viability = v0  # Line 836 (no-op case)
vessel.viability = v1  # Line 847 (survival application)
```

**Status**: ✅ Will be replaced by Diff 3 with `self._recompute_vessel_from_subpops(vessel)`

---

#### Line 1282: Clip operation in `_step_vessel`
```python
vessel.viability = float(np.clip(vessel.viability, 0.0, 1.0))
```

**Context**: Final sanity clamp after all operations.

**Status**: ⚠️ NEEDS INVARIANT after this line:
```python
vessel.viability = float(np.clip(vessel.viability, 0.0, 1.0))

# INVARIANT: vessel = weighted mean
wm = sum(sp['fraction'] * sp['viability']
         for sp in sorted(vessel.subpopulations.values()))
assert abs(vessel.viability - wm) < 1e-9, \
    f"INVARIANT: vessel.viability ({vessel.viability:.10f}) != weighted mean ({wm:.10f})"
```

---

#### Line 1653: Temperature modifier (run context)
```python
vessel.viability = float(vessel.viability * hardware_bias['temperature_factor'])
```

**Context**: Hardware simulation artifact (temperature effects).

**Status**: ⚠️ **SEMANTIC QUESTION**: Should temperature affect:
- **A) Vessel only** (current) - then subpops need re-sync (backward authority creep)
- **B) Each subpop independently** (v4 semantic) - then derive vessel

**Recommendation**:
```python
# Apply temperature to each subpop, then derive vessel
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    sp['viability'] = float(sp['viability'] * hardware_bias['temperature_factor'])

self._recompute_vessel_from_subpops(vessel)

# Invariant check
wm = sum(sp['fraction'] * sp['viability']
         for sp in vessel.subpopulations.values())
assert abs(vessel.viability - wm) < 1e-9
```

**Priority**: MEDIUM (only if temperature simulation is actually used)

---

## Summary of Required Work

### Before v4 Implementation:

1. **DELETE** `_sync_subpopulation_viabilities` function (lines 922-956) AND its call (line 1018)
   - Line 1018 in `_step_vessel` calls this function RIGHT AFTER `_commit_step_death`
   - This call will overwrite all per-subpop viabilities, defeating v4 entirely
   - **CRITICAL**: This is the #1 "passing locally while lying" risk

2. **REFACTOR** attrition computation (lines ~1170-1224)
   - Add loop over `sorted(vessel.subpopulations.keys())`
   - Apply `ic50_shift` per subpop
   - Retrieve `commitment_delay_h` per subpop
   - Store `subpop['_total_hazard']` and `subpop['_hazards']`
   - This is **PREREQUISITE** for Diff 3

3. **VERIFY** v3 (commitment heterogeneity) is merged
   - Commitment delay sampling must exist
   - `vessel.compound_meta['commitment_delays']` must be populated
   - Otherwise subpop-level attrition has no heterogeneity

### During v4 Implementation:

4. **APPLY** Diff 1: Add `_recompute_vessel_from_subpops` helper
5. **APPLY** Diff 2: Fix `_apply_instant_kill` (reverse authority)
6. **APPLY** Diff 3: Fix `_commit_step_death` (use per-subpop hazards)
7. **APPLY** Diff 4: Add runtime invariants at 3 locations:
   - End of `_apply_instant_kill`
   - End of `_commit_step_death`
   - End of `_step_vessel` (line ~1282)

8. **OPTIONAL** Fix temperature modifier (line 1653) if used

### After v4 Implementation:

9. **RUN** all 6 v4 tests (including 2 tripwires)
10. **VERIFY** test 3 passes (sensitive dies earlier than resistant)
    - If fails: per-subpop hazards not actually diverging
11. **VERIFY** invariants don't fire
    - If fire: some code path still writes vessel.viability directly

---

## Risk Assessment

### HIGH RISK: Per-subpop hazard storage
- **Current code does NOT compute attrition per subpop**
- Refactoring required BEFORE Diff 3
- If skipped: v4 diffs will "work" but tests will fail
- **Mitigation**: Do refactor first, test with print statements

### MEDIUM RISK: Hidden sync patterns
- `_sync_subpop_viabilities_to_vessel` function exists
- May be called from unexpected places
- **Mitigation**: Delete function entirely, see what breaks

### LOW RISK: Temperature modifier
- Only matters if hardware simulation is active
- Easy to fix if needed
- **Mitigation**: Add invariant check, see if it fires

---

## Go/No-Go Decision

### ✅ GO if:
1. v3 (commitment heterogeneity) merged first
2. Attrition refactored to per-subpop BEFORE Diff 3
3. `_sync_subpop_viabilities_to_vessel` deleted
4. All 4 diffs applied with invariants
5. All 6 tests pass

### 🔴 NO-GO if:
1. Per-subpop hazard storage NOT added (test 3 will fail)
2. Sync helper function NOT deleted (regression risk)
3. v3 NOT merged (no commitment heterogeneity → subpops synchronized)

---

## Recommended Implementation Order

```bash
# STEP 0: Verify v3 merged
git log --oneline | grep "commitment heterogeneity"

# STEP 1: Delete sync helper (CRITICAL - must be first)
# Remove line 1018: self._sync_subpopulation_viabilities(vessel)
# Delete lines 922-956: _sync_subpopulation_viabilities function definition
# This is the #1 "passing locally while lying" risk

# STEP 2: Refactor attrition to per-subpop (PREREQUISITE)
# Replace lines 1170-1224 with per-subpop loop
# Add subpop['_total_hazard'] and subpop['_hazards'] storage

# STEP 3: Test refactor in isolation
# Run existing tests, verify no regressions
# Print subpop hazards, verify they differ

# STEP 4: Apply v4 Diff 1 (add helper)
# STEP 5: Apply v4 Diff 2 (fix _apply_instant_kill)
# STEP 6: Apply v4 Diff 3 (fix _commit_step_death)
# STEP 7: Apply v4 Diff 4 (add invariants)

# STEP 8: Run v4 tests
PYTHONPATH=.:$PYTHONPATH python3 \
  tests/statistical_audit/test_subpop_viability_v4_FINAL.py

# STEP 9: If test 3 fails (sensitive doesn't die earlier)
# → Debug per-subpop hazard computation
# → Print subpop viabilities over time
# → Check IC50 shifts are actually applied

# STEP 10: Verify invariants don't fire
# If they fire: some code path still mutates vessel.viability directly
```

---

## Final Verdict

**GO with CONDITIONS**: v4 is ready to ship AFTER prerequisite work (per-subpop hazard storage) is completed. The patch itself is sound, but the current codebase is missing infrastructure that v4 assumes exists.

**Estimated effort**:
- Delete sync helper: 5 min
- Refactor attrition to per-subpop: 30-45 min
- Apply 4 v4 diffs: 15 min
- Run and debug tests: 15-30 min
- **Total**: ~1-2 hours

**Key insight**: v4 is not just "reversing authority direction" - it's also **making IC50 shifts and commitment delays actually matter**. Current code defines these parameters but doesn't use them in death computation. v4 makes them real.
