# v4 Ready to Ship - Final Checklist

**Status**: ✅ Conditional GO accepted by user
**Date**: 2025-12-25

---

## What Changed from Initial Approach

**Initial approach**: "v4 is 4 diffs, go implement"

**After go/no-go audit**: Current code defines IC50 shifts but doesn't use them. Two blockers found:
1. `_sync_subpopulation_viabilities` called after death computation (defeats v4)
2. Attrition computed at vessel level (IC50 shifts unused)

**User directive**: "Make blockers prerequisites, not extra features. Keep 4 diffs discipline."

**Final structure**:
- **Prerequisites**: Make code honest about what it claims (delete sync, use IC50 shifts)
- **v4 Proper**: 4 surgical diffs as originally specified

---

## Documentation Delivered

### Core Specifications
- ✅ `PATCH_subpop_viability_v4_FINAL.md` - Updated with prerequisites section
- ✅ `MERGE_CHECKLIST_v4.md` - Updated with prereq verification
- ✅ `test_subpop_viability_v4_FINAL.py` - 6 hardened tests (4 core + 2 tripwires)

### Supporting Documentation
- ✅ `GO_NO_GO_v4_verification.md` - Pre-implementation audit (line-by-line verification)
- ✅ `test_v4_prereq_verification.py` - Standalone prereq tripwire tests
- ✅ `v4_IMPLEMENTATION_NOTES.md` - Implementation guidance and failure modes

---

## Prerequisites (Before v4 Diffs)

### Prereq A: Delete sync helper
**File**: `src/cell_os/hardware/biological_virtual.py`

**Actions**:
1. Delete line 1018: `self._sync_subpopulation_viabilities(vessel)`
2. Delete lines 922-956: function definition
3. Verify: `rg "_sync_subpopulation_viabilities"` returns nothing

**Why**: Function forces backward authority after every step, defeating v4 entirely.

**Tripwire**: `test_v4_prereq_verification.py::test_prereq_a_no_sync_after_step`

---

### Prereq B: Per-subpop hazard computation
**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: Lines ~1170-1224 (attrition computation in `_step_vessel`)

**Objective**: Replace vessel-level attrition with per-subpop loop. Use existing IC50 shifts.

**Key changes**:
- Loop over `sorted(vessel.subpopulations.keys())`
- Apply `subpop['ic50_shift']` to IC50
- Retrieve `commitment_delay_h` from v3 cache
- Compute attrition per subpop
- Store `subpop['_total_hazard']` and `subpop['_hazards']`

**Two guardrails**:
1. No silent fallback: raise if lethal dose missing `commitment_delay_h`
2. Clear cache each step: init `_hazards` and `_total_hazard` to empty/zero

**Full code**: See `PATCH_subpop_viability_v4_FINAL.md` Prerequisites section

**Tripwire**: `test_v4_prereq_verification.py::test_prereq_b_per_subpop_hazards_exist`

---

## v4 Proper (4 Diffs)

### Diff 1: Add recompute helper
- Add `_recompute_vessel_from_subpops(vessel)` method
- Computes `vessel.viability = sum(frac * subpop_viability)`
- Initialize `subpop['viability']` at vessel creation

### Diff 2: Fix `_apply_instant_kill`
- Replace lines 770-797
- Apply kill to each subpop independently
- Call `_recompute_vessel_from_subpops(vessel)` to derive vessel

### Diff 3: Fix `_commit_step_death`
- Replace lines ~798-880
- Apply survival per subpop using `subpop['_total_hazard']`
- Call `_recompute_vessel_from_subpops(vessel)` to derive vessel

### Diff 4: Add runtime invariants
- Add at end of `_apply_instant_kill`, `_commit_step_death`, `_step_vessel`
- Assert `vessel.viability == weighted_mean(subpop viabilities)` within 1e-9

---

## Tests (6 Total)

### Core Tests (from v4 spec)
1. `test_vessel_viability_is_weighted_mean` - Basic invariant
2. `test_instant_kill_creates_subpop_divergence` - Multiplicative independence
3. `test_sensitive_dies_earlier_than_resistant` - **KILL-SHOT** (flow cytometry)
4. `test_subpop_viability_trajectories_deterministic` - Determinism smoke

### Tripwire Tests (from user's final review)
5. `test_one_step_divergence` - Catches vessel-level survival disguised as per-subpop
6. `test_no_resync_invariant` - Catches cleanup steps that re-sync

---

## Verification Sequence

```bash
# STEP 0: Verify v3 merged
git log --oneline | grep "commitment heterogeneity"

# STEP 1: Apply Prereq A (delete sync)
# Delete line 1018 and lines 922-956
rg "_sync_subpopulation_viabilities" src/cell_os/hardware/biological_virtual.py
# Should return nothing

# STEP 2: Apply Prereq B (per-subpop hazards)
# Replace lines ~1170-1224 with per-subpop loop
# See PATCH_subpop_viability_v4_FINAL.md for exact code

# STEP 3: Verify prerequisites
PYTHONPATH=.:$PYTHONPATH python3 tests/statistical_audit/test_v4_prereq_verification.py
# Expected: All prerequisites verified

# STEP 4: Apply v4 Diffs 1-4
# See PATCH_subpop_viability_v4_FINAL.md for exact code

# STEP 5: Run v4 tests
PYTHONPATH=.:$PYTHONPATH python3 tests/statistical_audit/test_subpop_viability_v4_FINAL.py
# Expected: All v4 tests passed - READY TO SHIP

# STEP 6: Manual verification
python3 -c "
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('v', 'A549', initial_count=1e6, initial_viability=0.3)
vm.treat_with_compound('v', 'tunicamycin', 5.0)
vessel = vm.vessel_states['v']

# Step once
vm._step_vessel(vessel, 1.0)

# Print per-subpop state
names = sorted(vessel.subpopulations.keys())
for name in names:
    sp = vessel.subpopulations[name]
    print(f'{name}: hazard={sp[\"_total_hazard\"]:.6f}/h, viability={sp[\"viability\"]:.4f}')

# Check vessel is weighted mean
wm = sum(vessel.subpopulations[n]['fraction'] * vessel.subpopulations[n]['viability'] for n in names)
print(f'Vessel viability: {vessel.viability:.4f}, Weighted mean: {wm:.4f}')
"

# Expected output:
# - Hazards differ (sensitive highest, resistant lowest)
# - Viabilities diverging (sensitive dropping faster)
# - Vessel viability equals weighted mean (within 1e-9)
```

---

## Success Criteria

After all work:

1. ✅ Prereq verification test passes
2. ✅ All 6 v4 tests pass (4 core + 2 tripwires)
3. ✅ Manual verification shows:
   - Different hazards per subpop (sensitive highest)
   - Different viabilities per subpop (sensitive lowest)
   - Vessel viability = weighted mean
4. ✅ Runtime invariants don't fire
5. ✅ No sync function in codebase

---

## What This Enables

**Falsification target**: Flow cytometry time course with marked sensitive population

**Before v4**: Simulator cannot generate staggered drops (all synchronized)

**After v4**: Simulator generates realistic divergence (sensitive dies earlier)

**Next artifact** (v5 target): Fractions stay fixed despite differential death (no selection)

---

## Estimated Timeline

- Prereq A (delete sync): 5 min
- Prereq B (per-subpop hazards): 30-45 min
- Verify prerequisites: 10 min
- Apply v4 Diffs 1-4: 15 min
- Run and debug tests: 15-30 min
- **Total**: 1-2 hours

---

## Commit Message

```bash
git add src/cell_os/hardware/biological_virtual.py
git add tests/statistical_audit/test_subpop_viability_v4_FINAL.py
git add tests/statistical_audit/test_v4_prereq_verification.py
git commit -m "feat: independent subpopulation viabilities (v4)

Prerequisites:
- Delete _sync_subpopulation_viabilities (lie injector)
- Refactor attrition to per-subpop hazard computation
- IC50 shifts now actually used (not just defined)

Core changes:
- Make subpop viability authoritative (not vessel)
- Vessel viability derived as weighted mean
- Instant kill and hazard death update subpops independently
- Enables sensitive subpops to die earlier than resistant

Enables falsification: flow cytometry time courses showing
differential survival curves per subpopulation.

Depends on v3 (commitment heterogeneity).
Prepares for v5 (selection dynamics)."
```

---

## Key Design Principle

**Minimal honesty**: Don't add features. Make existing parameters matter.

IC50 shifts were defined but unused. Prerequisites make them real. v4 makes their effects observable.

---

## Files Ready for Implementation

All documentation complete and ready:

- Core specs updated with prerequisites
- Prereq tripwire tests written
- v4 tests include 2 extra tripwires from user review
- Implementation notes document failure modes
- Go/no-go audit provides line-by-line verification

**Status**: Ready to implement. Prerequisites first, then v4 diffs.
