# Phase 2 Meta-Tests: Boring Correctness That Actually Scales

## What Was Built

Two layers of **structural enforcement** that prevent regression to epistemic dishonesty:

### 1. AST Meta-Test: No Hardcoded Death Lists (`test_no_hardcoded_death_lists.py`)

**Problem Pattern**:
```python
# Someone adds a new death channel
TRACKED_DEATH_FIELDS = frozenset({..., "death_new_mechanism"})

# But forgets to update this hardcoded list in conservation check
credited = (
    vessel.death_compound
    + vessel.death_starvation
    # ... death_new_mechanism MISSING
)
```

**Solution**: AST scan that **hard-fails** if any literal list/set/tuple contains `"death_"` strings.

**Result**: Adding a new death channel requires ONE edit (to `TRACKED_DEATH_FIELDS`). All conservation checks, clamping loops, and error messages automatically include it.

**Test Coverage**:
- ✅ `biological_virtual.py`: No hardcoded lists (uses loops over `TRACKED_DEATH_FIELDS`)
- ✅ `constants.py`: Only `TRACKED_DEATH_FIELDS` definition allowed

### 2. Authority Contract: Single Source of Truth (`test_tracked_fields_authority.py`)

**Operational Rules Enforced**:
1. **Proposable fields** = `TRACKED_DEATH_FIELDS` (can be passed to `_propose_hazard`)
2. **Residual field** = `death_unattributed` (computed, never proposed)
3. **Stub field** = `death_transport_dysfunction` (schema-only, not active)
4. **Metadata fields** = `death_committed*` (booleans/timestamps, not fractions)

**Test Coverage**:
- ✅ `death_unattributed` excluded from `TRACKED_DEATH_FIELDS`
- ✅ `death_transport_dysfunction` excluded (Phase 2 stub)
- ✅ `_propose_hazard` rejects both (operational enforcement)
- ✅ VesselState has all tracked fields initialized
- ✅ VesselState death fields match `TRACKED_DEATH_FIELDS` (no drift)
- ✅ All tracked fields are proposable (no typos)

---

## What Was Fixed

### Conservation Check Landmine Defused

**Before**: Three hardcoded lists in `_assert_conservation()` and `_update_death_mode()`, missing:
- `death_committed_er`
- `death_committed_mito`
- `death_contamination`

**After**: All loops use `TRACKED_DEATH_FIELDS` (single source of truth).

**Impact**: When Phase 2A.1 commitment channels activate, conservation checks work correctly. No "dashboard lying but conservation correct" bugs possible.

### Missing Field Added

Added `death_contamination` to `TRACKED_DEATH_FIELDS` (Phase 2D.1 operational events). This was already in VesselState but missing from the canonical list.

---

## Test Results

### ✅ 23/23 Critical Tests Passing

**Contract Tests** (10):
- 8 no-subpop-structure tests (Phase 2 refactor)
- 2 AST meta-tests (hardcoded list scan)

**Authority Tests** (8):
- Exclusion rules (unattributed, transport stub)
- Proposal validation
- Field matching (VesselState ↔ TRACKED_DEATH_FIELDS)

**Phase 6a Physics Tests** (5):
- 2 hazard scaling tests (single vs double)
- 3 conservation tests (bounded, monotone, allocation)

**Integration**:
- ✅ 24h staurosporine simulation (full conservation, no ledger drift)

---

## Why This Matters

### The Old Pattern (Guaranteed to Rot)

```python
# constants.py
TRACKED_DEATH_FIELDS = {..., "death_new_mechanism"}

# biological_virtual.py (3 places)
def _assert_conservation():
    credited = death_compound + death_starvation + ...  # FORGOT death_new_mechanism

def _update_death_mode():
    tracked_known = death_compound + death_starvation + ...  # FORGOT death_new_mechanism
    for field in ["death_compound", "death_starvation", ...]:  # FORGOT death_new_mechanism
```

**Result**: Silent conservation violations when new channels activate.

### The New Pattern (Impossible to Forget)

```python
# constants.py
TRACKED_DEATH_FIELDS = frozenset({..., "death_new_mechanism"})

# biological_virtual.py (automatic)
def _assert_conservation():
    credited = sum(getattr(vessel, f, 0.0) for f in TRACKED_DEATH_FIELDS)

def _update_death_mode():
    tracked_known = sum(getattr(vessel, f, 0.0) for f in TRACKED_DEATH_FIELDS)
    for field in TRACKED_DEATH_FIELDS:
        setattr(vessel, field, ...)
```

**Result**: Add to `TRACKED_DEATH_FIELDS` once, everything updates. Meta-test fails if anyone adds a hardcoded list.

---

## Development Contract

### To Add a New Death Channel:

1. **Add to `TRACKED_DEATH_FIELDS`** in `constants.py`
2. **Initialize in `VesselState.__init__`** (set to 0.0)
3. **Propose hazard** in appropriate mechanism (e.g., `_apply_compound_attrition`)
4. **Done**. Conservation, clamping, error messages all work.

### To Add a Stub Field (Not Active Yet):

1. **Initialize in `VesselState.__init__`** (schema placeholder)
2. **DO NOT add to `TRACKED_DEATH_FIELDS`** (stub)
3. **Add comment** explaining why it's excluded
4. **Authority test will pass** (stub fields allowed if documented)

### To Add Metadata (Not a Death Fraction):

1. **Use `death_*` prefix** if semantically related to death
2. **Exclude from `TRACKED_DEATH_FIELDS`** (metadata)
3. **Add to excluded set** in `test_tracked_fields_matches_vessel_state_death_fields`

---

## Meta-Learning

**Pattern**: When a specific bad pattern keeps recurring, **make it syntactically impossible to write**.

**Example**: Hardcoded death field lists → AST scan that fails on any literal containing `"death_"`.

**Result**: CI **refuses to merge** if someone tries the old pattern (Python compiles fine, but the meta-test fails). They're forced to use the correct pattern (loop over `TRACKED_DEATH_FIELDS`).

This is "boring correctness that actually scales" - not clever, not elegant, just **annoying enough that nobody does the bad pattern by accident**.

---

## Files Modified

### Core Implementation
- `src/cell_os/hardware/constants.py` - Added `death_contamination` to `TRACKED_DEATH_FIELDS`
- `src/cell_os/hardware/biological_virtual.py` - Fixed `_assert_conservation()` and `_update_death_mode()` to use `TRACKED_DEATH_FIELDS`

### Test Infrastructure
- `tests/contracts/test_no_hardcoded_death_lists.py` - AST meta-test (NEW)
- `tests/contracts/test_tracked_fields_authority.py` - Authority contracts (NEW)
- `tests/phase6a/test_hazard_scaling_once.py` - Hazard scaling integrity (NEW)
- `tests/phase6a/test_conservation_strict.py` - Strict conservation (NEW)

### Supporting Files
- `test_phase2_sanity.py` - 24h integration sanity check
- `tests/contracts/test_no_subpop_structure.py` - Phase 2 refactor contracts (already existed)

---

## Next Steps (Optional)

1. **Mechanism Attribution Audit** - Run tests without access to ground truth labels
2. **Anti-Leak Tests for Other Assays** - Cell Painting, LDH, scRNA
3. **Continuous Heterogeneity Distribution Tests** - Validate empirical CV matches configured CV
4. **Explicit Persister Pathology Module** - Optional discrete substates as pathology (not default)

But these are **optional enhancements**. The core honesty infrastructure is done.

The simulator now:
- ✅ Has no privileged structure (continuous heterogeneity only)
- ✅ Enforces conservation exactly once (no silent renormalization)
- ✅ Applies hazard scaling exactly once (single-scale vs double-scale sentinel)
- ✅ Cannot have hardcoded death lists (AST meta-test)
- ✅ Has single source of truth for proposable fields (`TRACKED_DEATH_FIELDS`)

**It runs, the contracts are green, and the meta-tests prevent rot.**

That's the deliverable.
