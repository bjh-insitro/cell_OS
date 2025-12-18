# Scaffold Versioning and Plate Geometry

## Status: Scaffold Frozen as Versioned Contract

The sentinel scaffold is now a **versioned specification** with cryptographic hash verification.

---

## 1. Scaffold as Versioned Contract ✅

### Added to `phase0_sentinel_scaffold.py`

```python
SCAFFOLD_ID = "phase0_v2_scaffold_v1"
SCAFFOLD_VERSION = "1.0.0"
SCAFFOLD_HASH = "901ffeb4603019fe"  # SHA256 first 16 chars

def compute_scaffold_hash():
    """Deterministic hash of scaffold specification (position, type, compound, dose)"""
    # Sorted canonical JSON -> SHA256 -> first 16 chars
```

### Embedded in Design Metadata

```json
{
  "sentinel_schema": {
    "scaffold_metadata": {
      "scaffold_id": "phase0_v2_scaffold_v1",
      "scaffold_version": "1.0.0",
      "scaffold_hash": "901ffeb4603019fe",
      "scaffold_size": 28,
      "scaffold_types": {
        "vehicle": 8,
        "ER_mid": 5,
        "mito_mid": 5,
        "oxidative": 5,
        "proteostasis": 5
      }
    }
  }
}
```

### Embedded in Certificate

```json
{
  "scaffoldMetadata": {
    "scaffoldId": "phase0_v2_scaffold_v1",
    "scaffoldHash": "901ffeb4603019fe",
    "scaffoldSize": 28
  }
}
```

### Invariant: `inv_sentinelScaffoldExactMatch` ✅

**Checks**:
1. **Scaffold hash matches** expected value (ERROR if mismatch)
2. **All plates identical** sentinel positions and types (ERROR if any plate differs)
3. **Position/type exact match** against frozen specification (ERROR if tweaked)

**Result**: "Someone tweaks a position because vibes" is now **unrepresentable** without bumping scaffold version.

**Run order**: Scaffold check runs FIRST, before placement quality checks. If scaffold is wrong, the design is wrong regardless of distribution metrics.

---

## 2. Spatial Distribution Verification ✅

### Problem: Are 0 warnings real or is the audit blind?

**Answer**: 0 warnings are **real**. The audit is not blind.

### Evidence: `scripts/spatial_diagnostic.py`

Runs independent spatial checks on the regenerated design:

#### Quadrant Distribution (2×2 grid)
```
✅ Q0 (Top-left):     7 sentinels (expected ~7.0, deviation 0.0)
✅ Q1 (Top-right):    7 sentinels (expected ~7.0, deviation 0.0)
✅ Q2 (Bottom-left):  7 sentinels (expected ~7.0, deviation 0.0)
✅ Q3 (Bottom-right): 7 sentinels (expected ~7.0, deviation 0.0)
```

**Perfect balance**: Exactly 7 sentinels per quadrant.

#### Edge Band Distribution
```
✅ Edge band: 9 sentinels (32.1%)
   Expected ~11.2 (±4 acceptable)
   Interior: 19 sentinels (67.9%)
```

**Good distribution**: Slightly fewer edge sentinels (avoiding corners/mid-row exclusions), but well within tolerance.

#### Row Distribution
```
✅ Row A: 3 sentinels  |  ✅ Row E: 4 sentinels
✅ Row B: 4 sentinels  |  ✅ Row F: 4 sentinels
✅ Row C: 4 sentinels  |  ✅ Row G: 4 sentinels
✅ Row D: 3 sentinels  |  ✅ Row H: 2 sentinels
```

**Even spread**: All rows have 2-4 sentinels (expected ~3.5 per row).

**Conclusion**: The scaffold has balanced geometry **by construction**. The 0 warnings are because placement is correct, not because checks are neutered.

---

## 3. Experimental Position Policy Decision

### The Question

Do we want:
- **Option A**: Experimental position stability (same `compound@dose` always at same well_pos)
- **Option B**: Deterministic shuffle (same multiset, different positions per plate)

### Phase 0 Decision: **Option A (Position Stability)**

**Rationale**:
1. **Drift detection consistency**: Compare same position across timepoints/days/operators
2. **Spatial confounding impossible**: All batch factors see all positions (orthogonality by design)
3. **Simplicity**: No shuffle seed to track, positions are deterministic from compound list
4. **SPC-friendly**: Fixed geometry for both sentinels AND experimentals

**Implementation**: Current generator already uses Option A (deterministic position assignment from experimental condition list).

### Current Behavior (Verified)

```python
# Experimental positions are deterministic and stable
experimental_positions = [pos for pos in available_well_positions
                         if pos not in sentinel_positions]

# Conditions are deterministic (same order for all plates at a timepoint)
for cell_line in cell_lines:
    conditions = conditions_group_1 if cell_line == 'A549' else conditions_group_2
    # conditions is a fixed list, same for all plates with this cell_line

    for day, operator, timepoint:
        # Build experimental tokens in same order
        for cond in conditions:
            experimental_tokens.append(cond)

        # Assign to positions in row-major order
        for exp_token, exp_pos in zip(experimental_tokens, experimental_positions):
            # Deterministic mapping: token[i] -> position[i]
```

**Result**: For any given cell line, the same experimental condition goes to the same well position across all plates (all timepoints, days, operators).

**Examples**:
- `tBHQ @ 3.0 µM (replicate 1)` → always at position `A03` (first non-sentinel position) on all A549 plates
- `MG132 @ 1.0 µM (replicate 2)` → always at position `A04` on all HepG2 plates

### Invariant TODO: `inv_experimental_position_stability`

**Check**: For each cell line, verify that the same experimental condition appears at the same position across all plates.

**Severity**: ERROR (position instability breaks drift detection assumptions)

**Implementation sketch**:
```typescript
function inv_experimental_position_stability(wells: Well[]): Violation[] {
  const violations: Violation[] = [];

  // Group by cell line
  const wellsByCellLine = groupBy(wells, w => w.cell_line);

  for (const [cellLine, cellLineWells] of Object.entries(wellsByCellLine)) {
    // Get experimental positions from first plate
    const firstPlate = cellLineWells.filter(w => w.plate_id === getFirstPlate(cellLineWells));
    const referenceMapping = new Map<string, string>(); // position -> condition key

    for (const well of firstPlate.filter(w => !w.is_sentinel)) {
      const conditionKey = `${well.compound}@${well.dose_uM}`;
      referenceMapping.set(well.well_pos, conditionKey);
    }

    // Check all other plates match
    const plateIds = new Set(cellLineWells.map(w => w.plate_id));
    for (const plateId of plateIds) {
      const plateWells = cellLineWells.filter(w => w.plate_id === plateId && !w.is_sentinel);

      for (const well of plateWells) {
        const expectedCondition = referenceMapping.get(well.well_pos);
        const actualCondition = `${well.compound}@${well.dose_uM}`;

        if (expectedCondition !== actualCondition) {
          violations.push({
            type: 'experimental_position_instability',
            severity: 'error',
            plateId,
            message: `Position ${well.well_pos} has ${actualCondition}, expected ${expectedCondition} (cell line ${cellLine}).`,
          });
        }
      }
    }
  }

  return violations;
}
```

---

## 4. Plate Geometry Fingerprint

### Sentinel Fingerprint ✅ (Already Verified)

**Script**: `scripts/verify_sentinel_scaffold.py`

**Check**: All 24 plates have identical sentinel positions and types.

**Result**: ✅ VERIFIED

```
✅ VERIFIED: All 24 plates have identical sentinel positions and types

Sentinel scaffold (28 positions):
  A02: vehicle
  ...
  H09: proteostasis
```

### Experimental Fingerprint 🔄 (TODO)

**Script**: `scripts/verify_experimental_geometry.py` (to be created)

**Checks**:
1. **Position multiset stability**: For each cell line, verify same 60 positions used across all plates
2. **Condition stability**: For each cell line, verify same `compound@dose` at same position across all plates
3. **Multiset correctness**: For each timepoint, verify expected 60 experimental conditions present

**Expected result**: All A549 plates use positions [A03, A04, A08, A09, A11, B01, B03, B04, B05, ...] (60 positions, excluding sentinel positions).

**Severity**: ERROR if any plate deviates from stable geometry.

---

## 5. New Invariants to Add

### Priority 1: Capacity and Exclusions

#### `inv_empty_wells_exactly_exclusions`

**Check**: Error if any non-excluded well is empty OR any excluded well is filled.

**Severity**: ERROR

**Why**: Catches silent dropping (if wells are empty) or exclusion violations.

### Priority 2: Timepoint Multiset Consistency

#### `inv_condition_multiset_identical_across_timepoints`

**Check**: For each cell line, verify that all timepoints have identical experimental condition multisets (ignoring position).

**Severity**: ERROR

**Why**: This is the bug we killed. Make it permanently unrepresentable.

**Implementation**:
```typescript
function inv_condition_multiset_identical_across_timepoints(wells: Well[]): Violation[] {
  // Group by cell line
  // For each cell line:
  //   - Get experimental conditions at each timepoint
  //   - Build multiset (compound, dose, count)
  //   - Verify all timepoints have identical multisets
  //   - ERROR if any timepoint differs
}
```

### Priority 3: Position Stability

#### `inv_experimental_position_stability`

**Check**: For each cell line, verify same `compound@dose` at same position across all plates.

**Severity**: ERROR

**Why**: Position stability is required for drift detection.

---

## 6. Experimental Position Policy Documentation

### For Future Phase 1+

If you want to **change** the experimental position policy in a future phase:

#### Option B: Deterministic Shuffle (Per-Plate Randomization)

**When to use**: If you're worried about position confounding leaking into biology (e.g., edge effects systematically affecting one compound).

**Implementation**:
1. Add `shuffle_seed` to plate metadata (unique per plate, deterministic from plate_id)
2. Shuffle experimental positions using plate-specific seed
3. Store shuffle seed in design metadata
4. Add invariant: `inv_shuffle_seed_reproducible` (verify positions can be reconstructed from seed)

**Trade-off**: Loses position stability (can't compare "A03 on Plate_1 vs Plate_2"), but gains protection against systematic position effects.

**Phase 0 choice**: NOT using shuffle. Fixed positions for maximum drift detection power.

---

## Summary

### What We Built

1. ✅ **Scaffold versioning**: ID, version, hash embedded in design and certificate
2. ✅ **Scaffold invariant**: `inv_sentinelScaffoldExactMatch` errors on any deviation
3. ✅ **Spatial diagnostics**: Verified 0 warnings are real (quadrant/edge/row balance)
4. ✅ **Experimental position policy**: Decided on Option A (position stability)
5. 🔄 **Geometry fingerprint**: Sentinel verified, experimental TODO

### What to Add Next

1. `inv_empty_wells_exactly_exclusions` - No silent dropping
2. `inv_condition_multiset_identical_across_timepoints` - Prevent the bug we killed
3. `inv_experimental_position_stability` - Enforce position stability policy
4. `verify_experimental_geometry.py` - Complete geometry fingerprint

### Verification Commands

```bash
# 1. Generate design
python3 scripts/design_generator_phase0.py

# 2. Verify scaffold consistency
python3 scripts/verify_sentinel_scaffold.py

# 3. Verify spatial distribution
python3 scripts/spatial_diagnostic.py

# 4. Run invariant checks
cd frontend && npx tsx validateFounderDesign.ts --regenerated

# 5. Check certificate
cat FOUNDER_VALIDATION_CERTIFICATE.json | python3 -m json.tool
```

**Expected output**:
- ✅ All 24 plates identical scaffold
- ✅ Spatial distribution GOOD
- ✅ 0 errors, 0 warnings
- ✅ Certificate includes `scaffoldMetadata` with hash `901ffeb4603019fe`

---

## Certificate (Current)

```json
{
  "paramsHash": "2f4e2bf9",
  "invariantsVersion": "1.0.0",
  "plateFormat": 96,
  "timestamp": "2025-12-18T04:37:59.109Z",
  "violations": [],
  "stats": {
    "totalWells": 2112,
    "sentinelWells": 672,
    "experimentalWells": 1440,
    "nPlates": 24
  },
  "scaffoldMetadata": {
    "scaffoldId": "phase0_v2_scaffold_v1",
    "scaffoldHash": "901ffeb4603019fe",
    "scaffoldSize": 28
  }
}
```

**Passing for the right reasons**:
- Scaffold hash matches frozen spec
- All plates have identical sentinel positions (verified)
- Spatial distribution is balanced (verified independently)
- Batch factors are orthogonal (batch-first allocation)
- Cell line is separate (constant within plate)

**Status**: Scaffold is frozen. Tweaking a position now requires bumping scaffold version and updating hash in both Python and TypeScript specs.
