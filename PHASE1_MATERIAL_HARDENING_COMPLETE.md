# Phase 1: Material Measurement Hardening - COMPLETE

## Status: ✅ All Critical Hardening Items Implemented

**Date:** 2025-12-26
**Test Results:** 24/24 contract tests passing (100.74s)

---

## Summary

Phase 1 implemented non-biological calibration material measurement (beads, dyes, buffer) with **brutal isolation guarantees** enforced through contract tests. All critical hardening items from hostile review #2 are complete.

---

## Critical Hardening Items (ALL COMPLETE)

### #1: Semantic Type IDs ✅
**Problem:** String-based seeding vulnerable to refactoring drift (rename "fluorescent_dye_solution" → seed changes)

**Solution:** Material type registry with integer IDs
```python
MATERIAL_TYPE_IDS = {
    'buffer_only': 1,
    'fluorescent_dye_solution': 2,
    'fluorescent_beads': 3
}

# Seed format: "material|{run_seed}|{type_id}|{row_idx}|{col_num}"
seed_string = f"material|{self.run_context.seed}|{material_type_id}|{well_row_idx}|{well_col_num}"
```

**Proof:** `test_material_type_rename_does_not_change_seed` - type_id=2 is stable even if label changes

---

### #2: Collision Resistance at Scale ✅
**Problem:** 384-well test insufficient for calibration scale (multiple runs, materials, plates)

**Solution:** Test 11,520 seeds (10 runs × 3 types × 384 wells)
```python
def test_seed_collision_at_scale():
    """10 runs × 3 materials × 384 wells = 11,520 unique seeds"""
    for run_seed in range(100, 110):
        for material_type_id in [1, 2, 3]:
            for row_idx in range(16):
                for col_num in range(1, 25):
                    # All seeds unique, zero collisions
```

**Result:** ✅ No collisions in 11,520 seeds

---

### #3: Stateless Detector RNG ✅
**Problem:** Shared material/detector RNG creates call-order dependence

**Solution:** Separate seed for detector noise
```python
# Material signal RNG (per-material randomness)
material_seed = stable_u64(f"material|{run_seed}|{type_id}|{row}|{col}")
rng_material = np.random.default_rng(material_seed)

# Detector RNG (stateless - same well always gives same detector noise)
detector_seed = stable_u64(f"detector|{run_seed}|{type_id}|{row}|{col}")
rng_detector = np.random.default_rng(detector_seed)
```

**Proof:** `test_detector_rng_order_independent` - measure A→B vs B→A, identical per-well results
```
✓ Detector RNG order-independent: A=50.8, B=53.7 (same both orders)
```

---

### #4: Kill **kwargs in apply_detector_stack ✅
**Problem:** **kwargs is a "garbage chute" - allows smuggling VM state through

**Solution:** Explicit parameter signature (no **kwargs)
```python
def apply_detector_stack(
    signal: Dict[str, float],
    detector_params: Dict[str, Any],
    rng_detector: np.random.Generator,
    exposure_multiplier: float = 1.0,  # Explicit
    well_position: str = "H12",         # Explicit
    plate_format: int = 384,            # Explicit
    enable_vignette: bool = True,       # Explicit
    enable_pipeline: bool = True        # Explicit
) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    NO VM COUPLING: Takes explicit detector params + dedicated RNG.
    NO KWARGS: All parameters explicit (prevents coupling creep).
    """
```

**Result:** Unknown parameters now cause immediate type errors (no silent coupling)

---

## Isolation Guarantees (PROVEN BY BRUTAL TESTS)

### Biology Isolation
```
✓ Material measurement in A1 did NOT mutate vessel B2 (byte-for-byte assertion)
✓ Material measurement works with ZERO vessels (no biology dependency)
✓ Material RNG isolated: cell signal unchanged (70.6 AU)
✓ Detector output independent of VM biology: clean=62.7±0.0, stressed=62.7±0.0
```

### RNG Isolation
```
✓ All 384 wells have unique seeds (no collisions)
✓ Material types have unique seeds in same well
✓ No collisions in 11,520 seeds (10 runs × 3 types × 384 wells)
✓ Detector RNG order-independent: A=50.8, B=53.7 (same both orders)
```

### Semantic Stability
```
✓ Material type ID provides semantic identity (rename-stable)
✓ Vignette deterministic: H12 → 0.9995
✓ Signal generation deterministic (same seed → same output)
```

### Variance Model Validation
```
✓ Buffer is true zero (no variance)
✓ Dye variance N-independent: CV=2.8%
✓ Bead variance scales 1/sqrt(N): CV_10=3.0%, CV_100=1.0%, ratio=3.12
✓ Vignette achromatic: ratio=0.8504 (identical for all channels)
```

### Mapping Table Coverage
```
✓ All bead plate assignments are mapped in ASSIGNMENT_TO_MATERIAL
✓ Mapping table covers 7/7 known materials
✓ Unmapped assignments fail loudly with helpful error
✓ Assignment names are case-insensitive
```

---

## Test Coverage (24 tests, 100.74s)

### test_material_seed_isolation.py (7 tests)
- ✅ Seeds unique across 384 wells
- ✅ Seeds vary across material types
- ✅ Detector output independent of VM biology
- ✅ No collisions at scale (11,520 seeds)
- ✅ Type rename does not change seed
- ✅ Detector RNG order independent

### test_material_vessel_isolation.py (3 tests)
- ✅ Cannot mutate vessel state
- ✅ Works without any vessels
- ✅ Material RNG does not shift biological RNG

### test_optical_materials_fast.py (7 tests)
- ✅ Vignette deterministic
- ✅ Vignette monotonic radial
- ✅ Buffer is true zero
- ✅ Dye variance N-independent
- ✅ Bead variance scales 1/sqrt(N)
- ✅ Vignette achromatic
- ✅ Signal generation deterministic

### test_material_assignment_mapping.py (8 tests)
- ✅ Bead plate assignments all mapped
- ✅ Unmapped assignments fail loudly
- ✅ Mapping table complete
- ✅ DARK assignment correct
- ✅ Dye assignment correct
- ✅ Beads assignment correct
- ✅ Case-insensitive normalization
- ✅ get_all_valid_assignments works

---

## Key Architecture Decisions

### 1. Ephemeral MaterialState (not VM registry)
MaterialState is passed as argument, never stored in VM. Prevents bloat and enforces purity.

### 2. Semantic Type IDs (integer registry)
Type IDs (1=buffer, 2=dye, 3=beads) ensure rename stability. Labels can change, IDs cannot.

### 3. Separate Material/Detector RNG
- `material_seed`: Per-material signal randomness
- `detector_seed`: Stateless detector noise (order-independent)

### 4. No **kwargs (explicit parameters)
All parameters explicit in apply_detector_stack. Unknown parameters cause type errors.

### 5. Pure Function Signal Generation
All optical signal formation in `optical_materials.py`, all detector physics in `detector_stack.py`.

### 6. Single Mapping Table
All plate assignments mapped in `material_assignments.py`. Unmapped assignments fail loudly.

---

## Deferred Items (Phase 2/3)

### Mapping Table Normalization Policy (#5)
**Decision needed:** Strict fail-only OR allow aliases with canonicalization?

Current: Case-insensitive normalization (DARK = dark = Dark)

Potential extension: Aliasing (BUFFER_ONLY → DARK, deprecated but accepted)

**Recommendation:** Keep strict for Phase 2, add aliases only if user feedback demands

---

### Vignette/Pipeline Conceptual Clarity (#6)
**Current state:** Both enabled by default, correct order (analog → digital)

**Potential improvement:** Rename/document boundary more clearly:
- Vignette = analog optical effect (illumination falloff)
- Pipeline transform = digital post-processing (background subtraction, etc.)

**Status:** Documented in code comments, no refactor needed for Phase 2

---

### Optical Signal Formation Boundary Defense (#7)
**Current state:** Signal formation in `optical_materials.py`, detector in `detector_stack.py`

**Potential hardening:** Import scanning test that proves detector_stack.py never imports biology modules

**Status:** Not critical for Phase 2 (architecture already correct, imports clean)

---

### Executor Order Independence (#8)
**Scope:** Phase 2 (plate executor integration)

Test that executor produces identical results regardless of well execution order.

**Deferred:** Requires executor implementation first

---

## Phase 2 Readiness

**Phase 1 deliverables: COMPLETE**
- ✅ MaterialState dataclass
- ✅ Pure signal generation (optical_materials.py)
- ✅ Detector stack extraction (detector_stack.py)
- ✅ VM integration (measure_material method)
- ✅ Mapping table (material_assignments.py)
- ✅ 24 contract tests (brutal isolation proofs)

**Phase 2 requirements:**
1. Extend ParsedWell with `well_mode` field ("material" vs "biological")
2. Add material dispatch in `execute_well()` (if well_mode == "material": measure_material)
3. Parse bead plate JSON schema (explicit_assignments, repeatability_tiles)
4. Execute full bead plate end-to-end
5. Generate calibration report (detector characterization)

**Blocker check:** None. All Phase 1 dependencies satisfied.

---

## Hostile Review Responses

### "Your RNG isolation is good, but seed construction is a footgun"
**Fixed:** Semantic type IDs (integers, not strings). Rename-stable.

### "You still might be smuggling biology through apply_detector_stack(signal, self, **kwargs)"
**Fixed:** Killed **kwargs. All parameters explicit. VM never passed.

### "The biggest remaining leak is semantic, not technical: time"
**Acknowledged:** Measurement timing uses `self.simulated_time` (t1 after advance_time). Washout/plating artifacts reference this. This is CORRECT (measurements read post-interval state).

### "If you do only one more hardening pass before Phase 2: Kill **kwargs"
**Done:** apply_detector_stack has explicit signature, no **kwargs.

---

## Files Changed (Phase 1)

### Core Implementation
- `src/cell_os/hardware/_impl.py` - Added stable_u64 (64-bit collision resistance)
- `src/cell_os/hardware/material_state.py` - MaterialState dataclass + nominal intensities
- `src/cell_os/hardware/optical_materials.py` - Pure signal generation functions
- `src/cell_os/hardware/detector_stack.py` - Extracted detector pipeline (no **kwargs)
- `src/cell_os/hardware/material_assignments.py` - Single mapping table
- `src/cell_os/hardware/biological_virtual.py` - measure_material method (semantic type IDs, separate detector RNG)

### Contract Tests
- `tests/contracts/test_optical_materials_fast.py` - Pure function contracts (7 tests, 0.03s)
- `tests/contracts/test_material_seed_isolation.py` - RNG isolation proofs (7 tests)
- `tests/contracts/test_material_vessel_isolation.py` - Biology isolation proofs (3 tests)
- `tests/contracts/test_material_assignment_mapping.py` - Mapping table validation (8 tests)

---

## Next Steps

**User decision point:** Approve Phase 1 completion and proceed to Phase 2 (executor integration)?

**OR**

Additional hostile review pass on remaining items (#5-7)?

**Recommendation:** Proceed to Phase 2. Remaining items are refinements, not blockers.

---

## Conclusion

Phase 1 material measurement is **production-ready** with brutal isolation guarantees:
- ✅ No biology coupling (proven by byte-level vessel assertion)
- ✅ No RNG coupling (proven by sequence isolation + order independence)
- ✅ No string drift (semantic type IDs)
- ✅ No collision risk (11,520 seeds tested)
- ✅ No silent failures (unmapped assignments fail loudly)

**Architecture philosophy:** "Make coupling impossible, not just addressed."

Every hostile review feedback transformed into architectural constraint that prevents future drift.
