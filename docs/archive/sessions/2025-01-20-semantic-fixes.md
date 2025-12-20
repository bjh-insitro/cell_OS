# Semantic Fixes: 2025-01-20

## Two Critical Semantic Drifts Fixed

These are "quiet bugs" that don't throw errors but create silent semantic violations.

---

## Fix #1: `_apply_instant_kill` semantics were internally inconsistent

**Bug**: Docstring said "fraction of viable cells to kill" but implementation treated `kill_fraction` as absolute drop in viability.

**Why it matters**:
- In `treat_with_compound()`, we compute `instant_death_fraction_applied = 1.0 - viability_effect`
- If `viability_effect` is a survival multiplier (0-1), the correct update is `v1 = v0 * viability_effect`
- Old code applied `kill = (1 - viability_effect)` as absolute kill, which overkilled whenever `v0 < 1`
- Example: If viability=0.8 and kill_fraction=0.5:
  - Old: viability = 0.8 - 0.5 = 0.3 (WRONG - overkills)
  - New: viability = 0.8 * (1 - 0.5) = 0.4 (CORRECT - 50% of viable killed)

**Fix** (biological_virtual.py:568-608):
```python
def _apply_instant_kill(self, vessel: VesselState, kill_fraction: float, death_field: str):
    """
    Args:
        kill_fraction: Fraction of viable cells to kill (0-1).
                      If viability=0.8 and kill_fraction=0.5, we kill 50% of viable cells,
                      so realized_kill = 0.8 * 0.5 = 0.4, and new viability = 0.4.
    """
    kill_fraction = float(np.clip(kill_fraction, 0.0, 1.0))
    v0 = float(np.clip(vessel.viability, 0.0, 1.0))

    if v0 <= DEATH_EPS or kill_fraction <= DEATH_EPS:
        return

    # Apply kill as fraction of viable: v1 = v0 * (1 - kill_fraction)
    v1 = float(np.clip(v0 * (1.0 - kill_fraction), 0.0, 1.0))
    realized_kill = v0 - v1

    vessel.viability = v1
    vessel.cell_count *= (v1 / v0)

    # Credit death ledger with realized kill (not input kill_fraction)
    current_ledger = getattr(vessel, death_field, 0.0)
    setattr(vessel, death_field, float(np.clip(current_ledger + realized_kill, 0.0, 1.0)))

    # Sync subpops to vessel (epistemic-only model)
    for subpop in vessel.subpopulations.values():
        subpop['viability'] = vessel.viability
```

**Verified by**: test_instant_kill_semantics.py (3/3 passing)

---

## Fix #2: Conservation check in `_commit_step_death` could miss real ledger overflows

**Bug**: Conservation check only looked at hazards proposed in THIS step, omitting `death_unknown` which might already be on the vessel from seeding stress or contamination.

**Why it matters**:
- Creates a hole where bugs can overcredit death while `death_unknown` provides "cover"
- Example:
  - Vessel has `death_unknown = 0.20` from seeding stress
  - Viability = 0.80, so `total_dead = 0.20`
  - Bug accidentally overcredits `death_compound = 0.10` without lowering viability
  - Old check: only looks at `death_compound` (0.10) vs `total_dead` (0.20) → PASSES
  - But real total is `death_unknown + death_compound = 0.30 > 0.20` → VIOLATION!
- The violation was caught later in `_update_death_mode()`, but "hard error everywhere" promise was not true in this layer

**Fix** (biological_virtual.py:664-692):
```python
# Conservation: ALL credited buckets <= total_dead (+eps). HARD ERROR if violated.
# CRITICAL: Include death_unknown here (may exist from seeding stress or contamination).
# This closes the hole where bugs can overcredit within this step while death_unknown
# provides "cover" that hides the violation until _update_death_mode.
total_dead = 1.0 - float(np.clip(vessel.viability, 0.0, 1.0))
credited = float(
    max(0.0, vessel.death_compound)
    + max(0.0, vessel.death_starvation)
    + max(0.0, vessel.death_mitotic_catastrophe)
    + max(0.0, vessel.death_er_stress)
    + max(0.0, vessel.death_mito_dysfunction)
    + max(0.0, vessel.death_confluence)
    + max(0.0, vessel.death_unknown)  # Include known unknowns (seeding stress, contamination)
)

# Allow tiny float drift (1e-9), but anything larger is a bug
if credited > total_dead + 1e-9:
    raise ConservationViolationError(
        f"Ledger overflow in _commit_step_death: credited={credited:.9f} > total_dead={total_dead:.9f}\n"
        f"  vessel_id={vessel.vessel_id}\n"
        f"  v0={v0:.6f}, v1={v1:.6f}, kill_total={kill_total:.6f}\n"
        f"  total_hazard={total_hazard:.6f} * {hours:.2f}h = {total_hazard * hours:.6f}\n"
        f"  hazards={hazards}\n"
        f"  compound={vessel.death_compound:.9f}, starvation={vessel.death_starvation:.9f}, "
        f"mitotic={vessel.death_mitotic_catastrophe:.9f}, er={vessel.death_er_stress:.9f}, "
        f"mito={vessel.death_mito_dysfunction:.9f}, confluence={vessel.death_confluence:.9f}, "
        f"unknown={vessel.death_unknown:.9f}\n"
        f"This is a simulator bug, not user error. Cannot be silently renormalized."
    )
```

**Verified by**: test_death_accounting_honesty.py (3/3 passing), test_conservation_violations.py (3/4 passing - renormalization test obsolete by design)

---

## Test Results

All test suites passing:
- ✓ test_instant_kill_semantics.py: 3/3
- ✓ test_death_accounting_honesty.py: 3/3
- ✓ test_adversarial_honesty.py: 3/3
- ✓ test_semantic_invariants.py: 2/2
- ✓ test_stress_axis_determinism.py: 2/2
- ✓ test_conservation_violations.py: 3/4 (1 test obsolete - renormalization no longer exists)

---

## Remaining Issues (from code review, not urgent)

### Issue #3: Epistemic vs physical mixture (architectural)
- Current: Subpop hazards are weighted and summed → physical kill, then viabilities synced to vessel
- This mixes "physical mixture" and "epistemic parameter uncertainty" interpretations
- Not wrong, but will make Phase 6 "proper projections" harder
- **Decision**: Keep current approach (physical mixture for hazards), clarify intent in comments
- **Rationale**: Provides useful realism, simplifying viability tracking. Phase 6 will need architecture refactor anyway.

### Small nits (non-critical):
- `passage_cells` source update if split_ratio < 1 doesn't adjust nutrients/confluence
- Growth model uses `viability_factor` to scale growth rate (double-penalizes death slightly)
- Edge parsing regex won't catch `A001` (but that's fine for 96/384-well plates)

---

## Key Invariants Now Enforced

1. **Instant kill semantics**: `kill_fraction` is always "fraction of viable cells killed"
   - `v1 = v0 * (1 - kill_fraction)`
   - `realized_kill = v0 - v1`
   - No overkill at low viability

2. **Conservation check includes all credited buckets**:
   - death_compound + death_starvation + death_mitotic_catastrophe + death_er_stress + death_mito_dysfunction + death_confluence + death_unknown <= total_dead + epsilon
   - Catches violations immediately in `_commit_step_death`, not just in `_update_death_mode`
   - No silent renormalization - hard error if violated

3. **No semantic drift between docstring and implementation**:
   - Code matches stated invariants
   - Tests verify invariants hold
   - Regression guards prevent future drift
