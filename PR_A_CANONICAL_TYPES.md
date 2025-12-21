# PR A: Canonical Experiment and Observation Types

**Date:** 2025-12-21
**Status:** ✅ COMPLETE
**Type:** Additive scaffolding (no behavior change)

---

## What Was Built

PR A introduces canonical types for the **Decision → Experiment → Observation** chain.

These types are **pure scaffolding**: they don't change any existing behavior, but they provide the foundation for PR B (compiler) and PR C (world accepts Experiment).

### Files Created

**1. `src/cell_os/core/experiment.py` (updated with new types)**
- `DesignSpec` - Template + params (what Decision references)
- `Experiment` - Wells with allocated locations (unit of execution)

**2. `src/cell_os/core/observation.py` (NEW - 68 lines)**
- `RawWellResult` - Raw measured output from one well
- `ConditionKey` - Canonical axes for aggregation
- `Observation` - Results from executing Experiment

**3. `src/cell_os/core/capabilities.py` (NEW - 104 lines)**
- `PlateGeometry` - Rows, cols, edge detection
- `Capabilities` - System capabilities (geometry + supported assays)
- `AllocationPolicy` - How to map abstract → concrete positions

### Semantic Teeth Tests Created

**4. `tests/unit/test_experiment_semantics.py` (NEW - 250 lines)**
- Experiment is immutable
- Experiment uses canonical types (no legacy strings)
- Experiment fingerprint is deterministic and order-independent
- DesignSpec params are JSON-serializable

**5. `tests/unit/test_observation_semantics.py` (NEW - 180 lines)**
- RawWellResult uses canonical types
- Observation is immutable
- Observation links to Experiment via fingerprint
- ConditionKey uses canonical observation axes

**6. `tests/unit/test_capabilities_semantics.py` (NEW - 190 lines)**
- PlateGeometry provides edge detection
- Capabilities is immutable and fingerprintable
- AllocationPolicy is immutable and fingerprintable

---

## Key Design Decisions

### 1. Experiment Fingerprinting

**What gets hashed:**
- Wells (sorted by location for order-independence)
- Design spec (template + params)
- Capabilities ID
- Allocation policy ID

**NOT included:**
- experiment_id (assigned after fingerprinting)
- metadata (not part of canonical identity)
- timestamps, paths, run_id (not reproducible)

**Result:** Same wells + design + capabilities → same fingerprint, even if wells in different order.

### 2. Wells Are Ordered But Fingerprint Is Not

**Wells stored as tuple:** Execution order matters (preserves provenance)

**Fingerprint sorts wells:** Identity doesn't depend on list construction order

**Pattern:**
```python
# Store in given order
experiment.wells = (well_a, well_b)

# Fingerprint sorts by (plate_id, well_id)
experiment.fingerprint()  # Same regardless of original order
```

### 3. Compiler Owns Allocation

**Design principle:** World is **dumb executor**, doesn't interpret or allocate.

**Compiler responsibilities:**
1. Expand DesignSpec → Wells
2. Allocate Well locations (abstract "edge" → concrete "A01")
3. Return complete Experiment with locations assigned

**World responsibilities:**
1. Execute Experiment (what it's given)
2. Measure results
3. Return RawWellResults

**Result:** Allocation is deterministic, reproducible, testable.

### 4. Observation Links to Experiment

**Observation.experiment_fingerprint:** Links back to Experiment that produced it

**Enables:**
- Audit: "Which experiment produced this observation?"
- Replay: "Run same experiment again"
- Deduplication: "Did I already run this?"

---

## What Doesn't Change

**No behavior change.** This is pure scaffolding.

- World still takes Proposal (for now)
- Agent still uses chooser.choose_next() → Decision
- Loop still works the same way
- Tests still pass

**What PR A enables:**
- PR B: Create compiler (DesignSpec → Experiment)
- PR C: World accepts Experiment, returns Observation
- PR D: Move aggregation out of world
- PR E: Agent loop uses full chain

---

## Verification

All semantic teeth tests pass:

```bash
$ python3 tests/unit/test_experiment_semantics.py
✓ All experiment semantic teeth tests passed
✓ Experiment is immutable (frozen=True)
✓ Experiment uses canonical types (no legacy strings)
✓ Experiment fingerprint is deterministic
✓ Wells are ordered but fingerprint is order-independent

$ python3 tests/unit/test_observation_semantics.py
✓ All observation semantic teeth tests passed
✓ RawWellResult uses canonical types (no legacy strings)
✓ Observation is immutable (frozen=True)
✓ Observation links to Experiment via fingerprint

$ python3 tests/unit/test_capabilities_semantics.py
✓ All capabilities semantic teeth tests passed
✓ PlateGeometry provides edge detection
✓ Capabilities is immutable (frozen=True)
✓ Capabilities fingerprint is deterministic
```

---

## What's Next

**PR B: Compiler**

Create `epistemic_agent/compiler.py`:
```python
def compile_design(
    design_spec: DesignSpec,
    capabilities: Capabilities,
    allocation_policy: AllocationPolicy,
) -> Experiment:
    """Expand design spec into experiment with allocated wells."""
```

**Compiler owns:**
- Template expansion (design_spec.template → Wells)
- Well allocation (abstract "edge" → concrete "A01")
- Validation (capabilities check)

**Result:** Agent can go from Decision → DesignSpec → Experiment without touching world.

---

## Summary

**Lines added:** ~620 (types + tests + docs)

**Time:** ~1 hour

**Leverage:** Enables Decision → Experiment → Observation chain with:
- Immutable provenance
- Deterministic fingerprints
- Canonical types throughout
- No behavior change (pure scaffolding)

**Semantic teeth:** 3 test files enforce canonical types, immutability, and fingerprinting.

**Next step:** PR B (compiler) can now be implemented with clear types and interfaces.

*"Teeth first. The types behave."*
