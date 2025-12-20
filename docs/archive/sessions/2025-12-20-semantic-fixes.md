# Semantic Fixes Status

**Date**: 2025-12-20
**Context**: Post-calibration semantic cleanup to enforce epistemic honesty

## Critical Fixes Requested

### ✓ Fix #1: death_unknown vs death_unattributed split

**Status**: COMPLETE (already in code)

**Location**: `biological_virtual.py` lines 179-180, 1306-1331

**What was fixed**:
- `death_unknown`: Credited bucket for KNOWN unknowns (contamination, handling mishaps)
- `death_unattributed`: Residual bookkeeping for UNKNOWN unknowns (numerical residue, missing model)
- `_update_death_mode()` uses `death_unknown` in tracked_known (line 1313)
- `_update_death_mode()` computes `death_unattributed` as residual (line 1331)

**Evidence**:
```python
# Line 179-180
self.death_unknown = 0.0  # KNOWN unknowns (explicitly credited)
self.death_unattributed = 0.0  # UNKNOWN unknowns (numerical residue)

# Line 1313
tracked_known = (
    vessel.death_compound
    + vessel.death_starvation
    + vessel.death_mitotic_catastrophe
    + vessel.death_er_stress
    + vessel.death_mito_dysfunction
    + vessel.death_confluence
    + vessel.death_unknown  # <-- Included in tracked
)

# Line 1331
vessel.death_unattributed = float(max(0.0, total_dead - tracked_known))
```

**Result**: No silent laundering of contamination deaths.

### ✓ Fix #2: Remove silent renormalization from _commit_step_death

**Status**: COMPLETE (already in code)

**Location**: `biological_virtual.py` lines 654-680

**What was fixed**:
- Removed renormalization block (used to scale ledgers if tracked > total_dead)
- Replaced with hard error: `ConservationViolationError` if violation detected (lines 667-678)
- `_step_ledger_scale` always 1.0 (line 680)

**Evidence**:
```python
# Lines 654-655 (comment)
# Conservation: tracked <= total_dead (+eps). HARD ERROR if violated.
# No silent renormalization - that's laundering.

# Lines 667-678 (hard fail)
if tracked > total_dead + 1e-9:
    raise ConservationViolationError(
        f"Ledger overflow in _commit_step_death: tracked={tracked:.9f} > total_dead={total_dead:.9f}\n"
        ...
        f"This is a simulator bug, not user error. Cannot be silently renormalized."
    )

# Line 680
vessel._step_ledger_scale = 1.0  # Always 1.0 (no renormalization)
```

**Result**: Conservation violations crash loudly with receipts, no silent fixes.

### ✓ Fix #3: Passaging clock resets and plating context

**Status**: COMPLETE (already in code)

**Location**: `biological_virtual.py` lines 1646-1658

**What was fixed**:
- Reset `seed_time`, `last_update_time`, `last_feed_time` to current time (lines 1647-1649)
- Resample `plating_context` with deterministic seed (lines 1652-1653)
- Credit passage stress to `death_unknown` (lines 1656-1658)

**Evidence**:
```python
# Lines 1646-1649
# Fix: Reset clocks for new vessel (passage is like seeding)
target.seed_time = self.simulated_time
target.last_update_time = self.simulated_time
target.last_feed_time = self.simulated_time

# Lines 1652-1653
# Fix: Resample plating context (dissociation creates plating stress)
plating_seed = stable_u32(f"plating_{self.run_context.seed}_{target_vessel}")
target.plating_context = sample_plating_context(plating_seed)

# Lines 1656-1658
# Credit passage stress to death_unknown
passage_death = source.viability * passage_stress
if passage_death > DEATH_EPS:
    target.death_unknown = passage_death
```

**Result**: Passaging properly resets temporal artifacts and creates new plating stress.

### ⚠ Fix #4: Subpopulation epistemic invariants

**Status**: PARTIALLY COMPLETE (semantics documented, guards needed)

**Location**: `biological_virtual.py` lines 682-716

**What exists**:
- `_sync_subpopulation_viabilities()` syncs all subpop viabilities to vessel (lines 702-716)
- Comment documents epistemic-only model (lines 686-700)
- Mixture verification check (lines 708-716)

**What's missing**:
- Rename `subpopulations` → `epistemic_particles` or `parameter_particles`
- Rename `fraction` → `weight`
- Add invariant check function (weights sum to 1, viabilities synced)

**Recommendation**: Add guardrails to prevent future cosplay:

```python
def _check_epistemic_particle_invariants(vessel):
    """Enforce epistemic-only semantics until Phase 6."""
    w = sum(p['fraction'] for p in vessel.subpopulations.values())
    if abs(w - 1.0) > 1e-9:
        raise ValueError(f"Particle weights must sum to 1 (got {w:.9f})")

    # In sync-only model, all particles must match vessel viability
    for name, p in vessel.subpopulations.items():
        if abs(p['viability'] - vessel.viability) > 1e-9:
            raise ValueError(
                f"Particle {name} viability ({p['viability']:.9f}) != "
                f"vessel viability ({vessel.viability:.9f}). "
                f"This violates sync-only model."
            )
```

**Priority**: Medium (semantics correct, but easy to regress without guards)

### ⚠ Fix #5: Plate factor seeding with run_context

**Status**: INCOMPLETE (needs fix)

**Location**: `biological_virtual.py` lines 2293, 2298, 2303 (and duplicates at 2474, 2479, 2484)

**Problem**:
```python
# Current (WRONG - plate effects constant across runs)
rng_plate = np.random.default_rng(stable_u32(f"plate_{plate_id}"))
rng_day = np.random.default_rng(stable_u32(f"day_{day}"))
rng_operator = np.random.default_rng(stable_u32(f"operator_{operator}"))
```

**Fix needed**:
```python
# Include run_context.seed and batch_id so "cursed day" varies per run
rng_plate = np.random.default_rng(stable_u32(f"plate_{self.run_context.seed}_{batch_id}_{plate_id}"))
rng_day = np.random.default_rng(stable_u32(f"day_{self.run_context.seed}_{batch_id}_{day}"))
rng_operator = np.random.default_rng(stable_u32(f"op_{self.run_context.seed}_{batch_id}_{operator}"))
```

**Impact**: Currently, plate/day/operator effects are deterministic ACROSS runs. "Cursed day" should vary by run_context, not be global constant.

**Priority**: HIGH (affects calibration - context effects not actually per-context)

### ⚠ Fix #6: Edge well detection for 384-well plates

**Status**: INCOMPLETE (TODO)

**Location**: `biological_virtual.py` _is_edge_well() function

**Problem**: Defaults to 96-well, never gets 384-well info from call site

**Fix needed**: Pass plate_format through assay call or infer from well_position format

**Priority**: LOW (only matters when simulating 384-well plates)

## Regression Tests Needed

### Test A: Contamination death survives _update_death_mode

```python
def test_death_unknown_no_laundering():
    """Contamination death should not be overwritten."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6)
    vessel = vm.vessel_states["test"]

    # Set initial viability
    vessel.viability = 0.98

    # Apply contamination (credited to death_unknown)
    vm._apply_instant_kill(vessel, 0.02, "death_unknown")
    assert vessel.death_unknown == pytest.approx(0.02, abs=1e-6)

    # Update death mode (should NOT overwrite death_unknown)
    vm._update_death_mode(vessel)

    # death_unknown should still be 0.02, not zeroed
    assert vessel.death_unknown == pytest.approx(0.02, abs=1e-6)

    # death_unattributed should be near zero (all death attributed)
    assert vessel.death_unattributed < 1e-6
```

### Test B: No renormalization ever occurs

```python
def test_no_silent_renormalization():
    """Conservation violations should crash, not renormalize."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6)
    vessel = vm.vessel_states["test"]

    # Run short sim with multiple hazards
    vm.treat_with_compound("test", "nocodazole", dose_uM=0.5)
    vm.advance_time(12.0)

    # _step_ledger_scale should always be 1.0 (no renormalization)
    assert vessel._step_ledger_scale == 1.0

    # If we manually create overflow, should crash
    vessel.death_compound = 0.60
    vessel.death_er_stress = 0.50
    vessel.viability = 0.50  # total_dead = 0.50, tracked = 1.10

    with pytest.raises(ConservationViolationError):
        vm._update_death_mode(vessel)
```

### Test C: Passaging resets clocks

```python
def test_passaging_resets_clocks():
    """Passaging should reset seed_time and resample plating context."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("source", "A549", 1e6)

    # Advance time
    vm.advance_time(24.0)

    # Passage
    vm.passage_cells("source", "target", split_ratio=4.0)
    target = vm.vessel_states["target"]

    # seed_time should be current time, not 0
    assert target.seed_time == vm.simulated_time
    assert target.last_update_time == vm.simulated_time
    assert target.last_feed_time == vm.simulated_time

    # plating_context should be resampled (not None)
    assert target.plating_context is not None
    assert 'post_dissociation_stress' in target.plating_context
```

## Summary

**Critical fixes complete**: 3/6 (death accounting, conservation, passaging)

**Needs immediate attention**:
1. Fix #5: Plate factor seeding with run_context (HIGH priority - affects calibration)
2. Fix #4: Add epistemic particle guards (MEDIUM priority - prevents regression)
3. Regression tests: Implement Tests A, B, C

**Can defer**:
- Fix #6: 384-well edge detection (LOW priority - only matters for 384-well sims)

## Next Actions

1. **Fix plate factor seeding** (lines 2293, 2298, 2303, 2474, 2479, 2484)
   - Include `self.run_context.seed` and `batch_id` in deterministic seeds
   - Ensures "cursed day" varies per run

2. **Add epistemic particle guards**
   - Create `_check_epistemic_particle_invariants()` function
   - Call after `_sync_subpopulation_viabilities()`
   - Prevents future cosplay (adding per-subpop hazards without Phase 6 machinery)

3. **Implement regression tests**
   - Test A: death_unknown not laundered
   - Test B: no silent renormalization
   - Test C: passaging resets clocks

Once these are done, the simulator will have **no quiet lies** and the calibration layer can trust the inference layer's honesty.
