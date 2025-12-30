# Growth, Passage, and Viability Fixes

**Date**: 2025-12-20
**Status**: ✓ COMPLETE

---

## Three Semantic Corrections

### 1. Growth Double-Penalty Fix ✓

**Problem**: Growth was penalized by viability factor AFTER death already updated cell_count.

**Before**:
```python
# Death step: cell_count *= survival_total (viability penalty applied)
# Growth step:
viability_factor = max(0.0, vessel.viability)
effective_growth_rate = growth_rate * lag_factor * (1.0 - edge_penalty) * viability_factor * context_growth_modifier
# Double penalty! Dead cells counted twice.
```

**After**:
```python
# Death step: cell_count *= survival_total (viability penalty applied once)
# Growth step:
effective_growth_rate = growth_rate * lag_factor * (1.0 - edge_penalty) * context_growth_modifier
# NO viability_factor - death already updated cell_count
```

**Rationale**:
- `cell_count` represents "viable cells in the vessel right now"
- Death already paid the viability tax via `cell_count *= survival_total`
- Applying viability again in growth double-penalizes

**File**: `biological_virtual.py:1332-1337`

---

### 2. Passage Split-Ratio Cell-Minting Fix ✓

**Problem**: When `split_ratio < 1.0`, passage MINTED cells instead of erroring.

**Before**:
```python
cells_transferred = source.cell_count / split_ratio

if split_ratio >= 1.0:
    del self.vessel_states[source_vessel]
else:
    source.cell_count = cells_transferred  # BUG: SETS instead of subtracts
    # If split_ratio = 0.5, transfers 2× cells and leaves 2× cells in source!
```

**After**:
```python
# Guard against cell minting
if split_ratio < 1.0:
    raise ValueError(
        f"split_ratio must be >= 1.0 (got {split_ratio}). "
        f"split_ratio < 1.0 would transfer more cells than exist (cell minting). "
        f"Use split_ratio=1.0 to transfer all cells."
    )

cells_transferred = source.cell_count / split_ratio

# Update source (or remove if fully passaged)
if split_ratio == 1.0:
    # Full passage: delete source vessel
    del self.vessel_states[source_vessel]
elif split_ratio > 1.0:
    # Partial passage: subtract transferred cells from source
    source.cell_count -= cells_transferred
```

**Rationale**:
- `split_ratio` is a divisor: `cells_transferred = source.cell_count / split_ratio`
- `split_ratio < 1.0` would transfer MORE cells than exist (physically impossible)
- Hard error prevents silent cell minting

**File**: `biological_virtual.py:1867-1975`

---

### 3. Viability Invariant Enforcement ✓

**Problem**: Viability was both a state variable and a bookkeeping shadow, with no systematic enforcement of conservation.

**Solution**: End-of-step invariant enforcement (not setter trap).

**Added**:
```python
def _assert_conservation(self, vessel: VesselState, gate: str = "unknown"):
    """
    Assert conservation law: sum(death_*) <= 1 - viability + epsilon.

    This catches:
    - Viability drift without death accounting
    - Cell_count changes without proper survival application
    - Death field overcrediting

    Raises ConservationViolationError if violated beyond DEATH_EPS.
    """
    total_dead = 1.0 - float(np.clip(vessel.viability, 0.0, 1.0))
    credited = float(
        max(0.0, vessel.death_compound)
        + max(0.0, vessel.death_starvation)
        + max(0.0, vessel.death_mitotic_catastrophe)
        + max(0.0, vessel.death_er_stress)
        + max(0.0, vessel.death_mito_dysfunction)
        + max(0.0, vessel.death_confluence)
        + max(0.0, vessel.death_unknown)
    )

    if credited > total_dead + DEATH_EPS:
        raise ConservationViolationError(
            f"Ledger overflow in {gate}: credited={credited:.9f} > total_dead={total_dead:.9f}\n"
            f"  vessel_id={vessel.vessel_id}\n"
            f"  viability={vessel.viability:.6f}, total_dead={total_dead:.6f}\n"
            f"  compound={vessel.death_compound:.9f}, starvation={vessel.death_starvation:.9f}, "
            f"mitotic={vessel.death_mitotic_catastrophe:.9f}, er={vessel.death_er_stress:.9f}, "
            f"mito={vessel.death_mito_dysfunction:.9f}, confluence={vessel.death_confluence:.9f}, "
            f"unknown={vessel.death_unknown:.9f}\n"
            f"This is a simulator bug, not user error. Cannot be silently renormalized."
        )
```

**Called at strategic gates**:
- `_commit_step_death()` - after death application (line 796)
- `passage_cells()` - after stateful transfer (line 1967)
- Future: any operation that modifies viability/death_fields

**Rationale**:
- Cleaner than setter trap (doesn't break internal code)
- Catches violations at operation boundaries
- Clear error messages identify the gate where violation occurred
- Answers "do you want viability as independent state or derived?" with "independent, but enforced"

**File**: `biological_virtual.py:800-852` (method definition), called at 796 and 1967

---

## Why These Fixes Matter

### 1. Growth Double-Penalty
**Before fix**: Dead cells were penalized twice - once in death step (reducing cell_count) and again in growth (multiplying by viability_factor). This caused growth to be artificially suppressed.

**After fix**: Dead cells only penalized once. Growth operates on already-corrected cell_count.

### 2. Passage Cell-Minting
**Before fix**: `split_ratio = 0.5` would:
- Transfer `cell_count / 0.5 = 2 × cell_count` cells to target
- Leave `2 × cell_count` cells in source
- **Total: 4× cells created from nothing**

**After fix**: `split_ratio < 1.0` raises ValueError immediately. No silent minting.

### 3. Viability Invariant
**Before fix**: No systematic check that viability changes were reflected in death accounting. Future bugs could drift viability without updating death_fields.

**After fix**: Every critical operation enforces conservation. Bugs caught immediately with clear gate identification.

---

## The Uncomfortable Answer

**Question posed**: "Do you actually want viability as an independent state at all, or should it be derived?"

**Current answer**: Independent state with hard enforcement.

**Why**:
- Viability is set at multiple operation boundaries (death, passage, compound treatment)
- Deriving it from death_fields would require death_fields to be set first, creating ordering dependencies
- Enforcement catches drift without imposing derivation constraints
- If drift becomes a persistent issue, revisit derivation

**Alternative considered**: `viability = 1.0 - sum(death_fields)` (derived).

**Rejected because**:
- Current code structure sets viability first, then allocates to death_fields
- Reversing this would require major refactoring
- Enforcement is simpler and achieves the same correctness goal

---

## Status

All three fixes implemented and syntax-checked.

**Next**: Run autonomous loop stress tests to verify no regressions.
