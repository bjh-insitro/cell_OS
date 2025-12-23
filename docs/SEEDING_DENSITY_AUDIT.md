# Seeding Density Audit - COMPREHENSIVE

## Executive Summary

**STATUS**: 🚨 **INCOMPLETE FIX** - Only 1 of 4 production files fixed

The seeding density problem is **widespread across the codebase**:
- **279 total** `seed_vessel()` calls
- **156 calls** with hardcoded `1e6` (1 million cells)
- **4 production files** need immediate fixing
- **~150 test files** need updating

## Critical Production Files with Wrong Seeding Densities

### ✅ FIXED
1. **src/cell_os/plate_executor.py** (line 476)
   - **Before**: `int(1e6 * density_scale)`
   - **After**: Uses `get_seeding_density(plate_format, cell_line, density_level)`
   - **Status**: ✅ FIXED (2025-12-22)

### ❌ NEEDS FIXING
2. **src/cell_os/plate_executor_v2.py** (line 626)
   - **Current**: `compute_initial_cells(pw.cell_density)` with `base_count=1_000_000`
   - **Problem**: Still uses 1M cells as base
   - **Priority**: 🔴 HIGH - Used in production plate simulation

3. **src/cell_os/plate_executor_parallel.py** (line 64)
   - **Current**: `int(1e6 * density_scale)`
   - **Problem**: Hardcoded 1 million cells
   - **Priority**: 🔴 HIGH - Parallel plate executor

4. **src/cell_os/cell_thalamus/thalamus_agent.py** (line 119)
   - **Current**: `initial_count = 5e5` (500,000 cells)
   - **Problem**: Still 100-166x too high for 384-well plates!
   - **Priority**: 🔴 HIGH - Cell Thalamus simulation

5. **src/cell_os/cell_thalamus/parallel_runner.py** (line 45)
   - **Current**: Receives `initial_count` as parameter
   - **Problem**: Depends on thalamus_agent.py passing correct value
   - **Priority**: 🟡 MEDIUM - Will be fixed when thalamus_agent.py is fixed

## Pattern Analysis

### Pattern 1: Direct Hardcoding (Most Common)
```python
vm.seed_vessel(vessel_id, cell_line, 1e6)  # WRONG!
```
**Found in**: 156 files

### Pattern 2: Scaled Hardcoding
```python
density_scale = 0.7 if "LOW" else 1.3 if "HIGH" else 1.0
initial_cells = int(1e6 * density_scale)  # WRONG!
```
**Found in**: plate_executor_parallel.py

### Pattern 3: Helper Function with Wrong Base
```python
def compute_initial_cells(cell_density: str, base_count: int = 1_000_000):  # WRONG!
    return int(base_count * density_multipliers[cell_density])
```
**Found in**: plate_executor_v2.py

### Pattern 4: Reasonable for Context
```python
# T-flask simulation
vm.seed_vessel(flask_id, cell_line, 1e6, capacity=1e7)  # OK for T75 flask!
```
**Found in**: workflow_simulator.py (This is actually correct for T-flasks)

### Pattern 5: Abstract Units (Might be Intentional)
```python
# Episode-based beam search
vm.seed_vessel("episode", cell_line, 1e6, capacity=1e7)  # Abstract vessel?
```
**Found in**: episode.py, beam_search/runner.py
**Question**: Are these abstract units or do they represent real vessels?

## Vessel Type Classification

### Need Vessel-Specific Densities
| File | Vessel Type | Current | Should Be |
|------|-------------|---------|-----------|
| plate_executor.py | 384-well | ~~1e6~~ ✅ 3-5K | 3-5K ✅ FIXED |
| plate_executor_v2.py | 384-well | 1e6 | 3-5K |
| plate_executor_parallel.py | 384-well | 1e6 | 3-5K |
| cell_thalamus/thalamus_agent.py | Unknown | 5e5 | 3-5K (if 384-well) |
| tbhp_dose_finder.py | 96-well? | 10K | 10K ✅ OK |

### Might Be Correct (Need Verification)
| File | Context | Current | Notes |
|------|---------|---------|-------|
| workflow_simulator.py | T-flask | 1e6 | OK for T75 flask (~75 cm²) |
| episode.py | Abstract | 1e6 | Might be intentional abstract units |
| beam_search/runner.py | Abstract | 1e6 | Same as episode.py |

### Test Files (Can Wait)
- ~150 test files with hardcoded 1e6
- **Priority**: 🟢 LOW - Tests should use fixture/config values
- **Action**: Create test fixture with correct densities

## The ROOT CAUSE

The `seed_vessel()` method signature does NOT include vessel type:

```python
def seed_vessel(
    self,
    vessel_id: str,
    cell_line: str,
    initial_count: float,  # <-- Caller must know the right number!
    capacity: float = 1e7,
    initial_viability: float = None
)
```

**Problem**: The METHOD doesn't know if it's seeding a:
- 384-well plate (3-5K cells)
- 96-well plate (10-20K cells)
- 6-well plate (300-800K cells)
- T75 flask (1M cells)

**Current Solution**: Callers use `get_seeding_density(plate_format, cell_line, density_level)`

**Long-term Solution Options**:
1. Add `vessel_type` parameter to `seed_vessel()`
2. Create vessel-specific methods: `seed_plate_well()`, `seed_flask()`, etc.
3. Maintain external configuration (current approach)

## Database Status

**Question**: Is there a database table for seeding densities?

**Answer**: ❌ NO

Checked `data/cell_lines.db`:
- Tables: cell_lines, cell_line_characteristics, protocol_parameters, etc.
- **No seeding density configuration found**
- `protocol_parameters` contains passage/thaw/feed protocols, but NOT seeding densities

**Recommendation**: The `seeding_densities.py` config file IS the correct place for this.

## Fix Priority

### 🔴 URGENT (Must fix immediately)
1. plate_executor_v2.py
2. plate_executor_parallel.py
3. cell_thalamus/thalamus_agent.py
4. cell_thalamus/parallel_runner.py (depends on #3)

### 🟡 REVIEW (Verify these are intentional)
1. episode.py - Are these abstract units?
2. beam_search/runner.py - Same question
3. workflow_simulator.py - Verify T-flask context is correct

### 🟢 LOW PRIORITY (Can defer)
1. ~150 test files - Should use test fixtures
2. epistemic_policies.py - Test/demo code

## Recommended Action Plan

### Phase 1: Fix Critical Production Code (TODAY)
- [ ] Fix plate_executor_v2.py
- [ ] Fix plate_executor_parallel.py
- [ ] Fix cell_thalamus/thalamus_agent.py
- [ ] Verify cell_thalamus/parallel_runner.py

### Phase 2: Clarify Abstract Units (THIS WEEK)
- [ ] Review episode.py - Document if 1e6 is intentional abstract unit
- [ ] Review beam_search - Same
- [ ] Document vessel type semantics in seed_vessel() docstring

### Phase 3: Test Suite Cleanup (NEXT SPRINT)
- [ ] Create test fixture with correct densities
- [ ] Update ~150 test files to use fixture
- [ ] Add test to catch future hardcoded densities

### Phase 4: Long-term Architecture (FUTURE)
- [ ] Consider adding `vessel_type` to seed_vessel() signature
- [ ] OR create typed vessel classes with built-in capacity/seeding
- [ ] OR add vessel type to RunContext/metadata

## Verification Script

Run to check all files:
```bash
python scripts/verify_seeding_densities.py

# Find all remaining hardcoded 1e6 in production code
grep -rn "seed_vessel.*1e6" src/cell_os --include="*.py" | grep -v test
```

## Impact Assessment

### If Left Unfixed
- ❌ Plate simulations produce unrealistic results
- ❌ Cells massively overconfluent from t=0
- ❌ Morphology signals don't match real experiments
- ❌ Validation studies will fail when compared to real data

### After Full Fix
- ✅ Realistic confluence dynamics (60-90% at 48h)
- ✅ Match real high-content screening protocols
- ✅ Correct cell-line-specific growth patterns
- ✅ Accurate morphology and viability simulations
