# Phase 0 Founder: Fixed Sentinel Scaffolding - Complete

## Status: Production Ready

The Phase 0 founder design now passes all invariants with **0 errors, 0 warnings** using fixed sentinel scaffolding.

---

## Before/After Comparison

### Original Founder (phase0_design_v2_controls_stratified.json)
- **Allocation**: Timepoint-dependent sentinel schema (T12h/T24h: 28 sentinels, T48h: 30 sentinels)
- **Policy Collision**: T48h needed 30 sentinels but only 88 wells available → silent dropping of 2 experimental conditions
- **Murder Weapon**: `next(well_iter)` stops silently when exhausted
- **Validation Result**: **123 errors** (after config fix: 43 errors)
  - Sentinel count mismatches
  - Missing experimental conditions (MG132@30, paclitaxel@0.3 on T48h plates)
  - Batch confounding (timepoint-dependent allocation)

### Sequential Regenerated (first iteration)
- **Allocation**: Fixed sentinel schema (28 everywhere, no timepoint variance)
- **Placement**: Sequential (60 experimentals → 28 sentinels at end)
- **Capacity**: Hard validation before generation (no silent dropping possible)
- **Validation Result**: **0 errors, 1992 warnings**
  - Allocation correct by construction
  - Placement warnings (sentinels clustered at end, high gap variance, spatial clustering)

### Fixed Scaffold Regenerated (final)
- **Allocation**: Fixed sentinel schema (28 everywhere, batch-first)
- **Placement**: Fixed 28 positions on ALL plates (same positions, all timepoints/days/operators/cell lines)
- **Capacity**: Hard validation + position validation
- **Validation Result**: ✅ **0 errors, 0 warnings** (CLEAN PASS)
  - Allocation correct by construction
  - Placement correct by construction
  - Sentinels interspersed, evenly distributed, well-separated

---

## Fixed Sentinel Scaffold (28 positions)

Same positions and types on every plate:

```
  A02: vehicle       A05: ER_mid        A10: mito_mid
  B02: vehicle       B06: ER_mid        B09: mito_mid       B12: vehicle
  C03: ER_mid        C06: mito_mid      C09: vehicle        C12: ER_mid
  D04: mito_mid      D07: vehicle       D10: ER_mid
  E01: mito_mid      E04: vehicle       E07: oxidative      E10: oxidative
  F02: vehicle       F05: oxidative     F08: proteostasis   F11: vehicle
  G02: oxidative     G05: proteostasis  G08: proteostasis   G12: oxidative
  H04: proteostasis  H09: proteostasis
```

### Sentinel Type Distribution
- **vehicle**: 8 (min separation = 3 positions)
- **ER_mid**: 5 (min separation = 3 positions)
- **mito_mid**: 5 (min separation = 3 positions)
- **oxidative**: 5 (min separation = 1-2 positions)
- **proteostasis**: 5 (min separation = 1-2 positions)

### Design Properties
1. **Fixed for SPC**: Same positions enable drift detection (compare A02 vehicle on Plate_1 vs Plate_24)
2. **Spatial confounding impossible**: Fixed geometry across all batch factors
3. **Even distribution**: Sentinels interspersed throughout plate (not clustered)
4. **Type separation**: Greedy placement with anti-clustering (vehicle types well-separated)
5. **2D spatial balance**: Good distribution across physical plate regions

---

## Generator Architecture (design_generator_phase0.py)

### Phase A: Capacity Validation (Hard Constraints)
```python
plan = PlatePlan(
    plate_format=96,
    available_wells=88,
    sentinel_count=28,
    experimental_count=60,
    require_exact_fill=True,
)
violations = plan.validate()
if violations:
    raise ValueError("Design violates capacity constraints. Cannot proceed.")
```

**Result**: No generation until capacity proven valid (no silent dropping)

### Phase B: Allocation (Batch-First)
```python
# Build identical experimental conditions for each timepoint
for cell_line in cell_lines:
    conditions = get_conditions_for_cell_line(cell_line)
    for day in days:
        for operator in operators:
            for timepoint in timepoints_h:
                # IDENTICAL 60 experimental conditions
                experimental_tokens = build_experimental_tokens(conditions)

                # HARD CHECK: count must match available positions
                if len(experimental_tokens) != 60:
                    raise AssertionError("Experimental count mismatch")
```

**Result**: Batch orthogonality baked into allocation (confounding impossible)

### Phase C: Placement (Fixed Scaffold)
```python
# Get sentinel tokens from FIXED scaffold (with positions pre-assigned)
sentinel_tokens = get_sentinel_tokens()  # Always returns same 28 positions
sentinel_positions = {s['position'] for s in sentinel_tokens}

# Get experimental positions (available minus sentinel)
experimental_positions = [pos for pos in available_well_positions
                         if pos not in sentinel_positions]

# Place sentinels at fixed positions
for sentinel_token in sentinel_tokens:
    wells.append(create_well(sentinel_token))

# Place experimentals in remaining positions
for exp_token, exp_pos in zip(experimental_tokens, experimental_positions):
    wells.append(create_well(exp_token, exp_pos))
```

**Result**: Fixed scaffold + deterministic experimental placement

---

## Invariant Validation Results

### Run Command
```bash
cd /Users/bjh/cell_OS/frontend
npx tsx validateFounderDesign.ts --regenerated
```

### Output
```
═══════════════════════════════════════════════════════════════
  PHASE 0 FOUNDER CALIBRATION REPORT
═══════════════════════════════════════════════════════════════

## Design Stats
  Total wells: 2112
  Sentinel wells: 672 (31.8%)
  Experimental wells: 1440 (68.2%)
  Plates: 24
  Plate format: 96-well

## Invariants Version: 1.0.0
## Timestamp: 2025-12-18T04:31:23.115Z

## Violations Summary
  Errors: 0
  Warnings: 0

✅ CLEAN PASS - Founder design satisfies all invariants

Interpretation:
  • Thresholds are aligned with reality
  • Founder is the zero point for comparison
  • Future designs should match or exceed this quality
═══════════════════════════════════════════════════════════════
```

### Verification
```bash
cd /Users/bjh/cell_OS
python3 scripts/verify_sentinel_scaffold.py
```

```
✅ VERIFIED: All 24 plates have identical sentinel positions and types

Sentinel scaffold (28 positions):
  A02: vehicle
  A05: ER_mid
  ...
  H09: proteostasis

Sentinel counts by type:
  ER_mid: 5
  mito_mid: 5
  oxidative: 5
  proteostasis: 5
  vehicle: 8
```

---

## What Changed

### 1. Sentinel Schema (Fixed for All Timepoints)
**Before**: Timepoint-dependent (T48h had 7 types, 30 sentinels)
**After**: Fixed schema (5 types, 28 sentinels everywhere)

```python
PHASE0_SENTINEL_SCHEMA = {
    'vehicle': {'compound': 'DMSO', 'dose_uM': 0.0, 'n': 8},
    'ER_mid': {'compound': 'thapsigargin', 'dose_uM': 0.5, 'n': 5},
    'mito_mid': {'compound': 'oligomycin', 'dose_uM': 1.0, 'n': 5},
    'proteostasis': {'compound': 'MG132', 'dose_uM': 1.0, 'n': 5},
    'oxidative': {'compound': 'tBHQ', 'dose_uM': 30.0, 'n': 5},
}
# Total: 28 sentinels
# NO timepoint-dependent variance for Phase 0
```

### 2. Capacity Validation (Hard Constraints)
**Before**: `next(well_iter)` silently stops when exhausted
**After**: `PlatePlan.validate()` errors before generating anything

```python
@dataclass
class PlatePlan:
    def validate(self) -> List[Violation]:
        """Hard capacity constraint - no silent failures"""
        total_needed = self.sentinel_count + self.experimental_count

        if total_needed > self.available_wells:
            violations.append(Violation(
                type='capacity_overflow',
                severity='error',
                message=f"Cannot fit {total_needed} wells into {self.available_wells}",
            ))

        if self.require_exact_fill and total_needed < self.available_wells:
            violations.append(Violation(
                type='capacity_underfill',
                severity='error',
                message=f"Only using {total_needed} of {self.available_wells}",
            ))

        return violations
```

### 3. Fixed Sentinel Scaffolding
**Before**: Sequential placement (experimentals first, sentinels at end)
**After**: Fixed 28 positions on all plates

Created `phase0_sentinel_scaffold.py`:
```python
SENTINEL_POSITIONS = [
    "A02", "A05", "A10",  # Row A (3)
    "B02", "B06", "B09", "B12",  # Row B (4)
    "C03", "C06", "C09", "C12",  # Row C (4)
    "D04", "D07", "D10",  # Row D (3)
    "E01", "E04", "E07", "E10",  # Row E (4)
    "F02", "F05", "F08", "F11",  # Row F (4)
    "G02", "G05", "G08", "G12",  # Row G (4)
    "H04", "H09",  # Row H (2)
]

SENTINEL_SCAFFOLD = [
    {"position": "A02", "type": "vehicle"},
    {"position": "A05", "type": "ER_mid"},
    # ... 28 total with greedy type placement
]
```

### 4. Batch-First Allocation
**Before**: Mixed token ordering (experimental + sentinel interleaved during generation)
**After**: Build complete experimental multiset per timepoint, then place

```python
# Build identical experimental conditions for this timepoint
experimental_tokens = []
for cond in conditions:  # Same 60 conditions for all plates at this timepoint
    experimental_tokens.append({
        'compound': cond['compound'],
        'dose_uM': cond['dose_uM'],
        'is_sentinel': False,
    })

# HARD CHECK: experimental count must match
if len(experimental_tokens) != 60:
    raise AssertionError("Experimental count mismatch")
```

---

## Files Created/Modified

### New Files
1. `/scripts/phase0_sentinel_scaffold.py` - Fixed 28 positions with type assignments
2. `/scripts/verify_sentinel_scaffold.py` - Verification script
3. `/PHASE0_FOUNDER_FIXED_SCAFFOLD_COMPLETE.md` - This document

### Modified Files
1. `/scripts/design_generator_phase0.py` - Integrated fixed scaffold
2. `/data/designs/phase0_founder_v2_regenerated.json` - New design with scaffold
3. `/frontend/FOUNDER_VALIDATION_CERTIFICATE.json` - Clean pass certificate

---

## Design Statistics

### Plate Structure
- **Format**: 96-well
- **Excluded wells**: 8 (A01, A12, H01, H12, A06, A07, H06, H07)
- **Available wells**: 88
- **Sentinels per plate**: 28 (31.8%)
- **Experimental per plate**: 60 (68.2%)

### Batch Structure
- **Cell lines**: 2 (A549, HepG2)
- **Days**: 2
- **Operators**: 2
- **Timepoints**: 3 (12h, 24h, 48h)
- **Total plates**: 24 (2 × 2 × 2 × 3)

### Experimental Conditions
- **Compounds**: 10 (split into 2 groups of 5)
- **Doses per compound**: 6 (0.1×, 0.3×, 1×, 3×, 10×, 30× IC50)
- **Replicates per dose**: 2
- **Conditions per plate**: 60 (5 compounds × 6 doses × 2 reps)

### Sentinel Types
- **vehicle** (DMSO, 0 µM): 8 per plate
- **ER_mid** (thapsigargin, 0.5 µM): 5 per plate
- **mito_mid** (oligomycin, 1.0 µM): 5 per plate
- **oxidative** (tBHQ, 30.0 µM): 5 per plate
- **proteostasis** (MG132, 1.0 µM): 5 per plate

---

## Why This Matters

### 1. Drift Detection is Now Trivial
Compare **exact same well positions** over time:
- A02 (vehicle) on Day 1, Operator A, 12h vs Day 2, Operator B, 48h
- No need to "match similar sentinels" - they're literally the same position

### 2. Spatial Confounding is Impossible
Fixed geometry means:
- Edge effects affect ALL conditions equally (if present)
- Row/column effects affect ALL conditions equally (if present)
- No batch factor can correlate with position (positions are constant)

### 3. SPC Control Charts Work
Standard SPC assumes:
- Same process (✓ same compound/dose)
- Same measurement system (✓ same position)
- Only time varies (✓ fixed everything else)

Phase 0 now satisfies these assumptions by construction.

### 4. Warnings Mean Something
With sequential placement, 1992 warnings were "cosmetic" but real.
With fixed scaffold, **0 warnings** means the design is actually correct.

Don't accept warnings as normal - they indicate real geometry problems.

---

## Next Steps (Optional)

### 1. Upgrade Audit Semantics for Scaffolding
When using fixed scaffold, demote certain checks:
- **Window/gap checks**: Less relevant (scaffold has fixed geometry)
- **Type separation checks**: Less relevant (scaffold has fixed types)

Promote new checks:
- **Scaffold stability**: All plates use exact same positions
- **Scaffold integrity**: No experimental wells in scaffold positions

### 2. Fix Old Frontend Generator
Replace `next(iterator)` with explicit bounds checks:
```typescript
if (wellIndex >= availablePositions.length) {
  throw new Error(`Capacity overflow: need ${tokens.length} wells, only ${availablePositions.length} available`);
}
```

### 3. Implement inv_sentinelBatchBalance
Separate invariant for sentinel-only batch balance checks (looser thresholds, warnings not errors).

---

## Summary

**What we had**: Founder design with policy collision (T48h needed 30 sentinels but only 88 wells available), silent dropping of experimental conditions, 123 errors

**What we built**: Founder design with fixed sentinel scaffolding, hard capacity constraints, batch-first allocation, 0 errors, 0 warnings

**What we proved**: The invariant system works. It accused the founder, we fixed the generator, now the design passes cleanly.

**Status**: Phase 0 founder is production-ready. The audit crossed the important line - it's a design audit that knows when it's allowed to speak.

---

## Verification Commands

```bash
# Generate design
cd /Users/bjh/cell_OS
python3 scripts/design_generator_phase0.py

# Validate design
cd /Users/bjh/cell_OS/frontend
npx tsx validateFounderDesign.ts --regenerated

# Verify scaffold consistency
cd /Users/bjh/cell_OS
python3 scripts/verify_sentinel_scaffold.py
```

Expected output: ✅ 0 errors, 0 warnings, all 24 plates have identical sentinel positions and types.

---

**The uncomfortable question has been answered.**

`cell_line` now has `policy: 'separate'` and checks for constancy within plate (not independence). This is correct by design.

**The pivot has happened.**

We stopped polishing guardrails and fixed the actual design logic. The founder now passes cleanly.

**The warnings are not cosmetic.**

Sequential placement had 1992 warnings. Fixed scaffold has 0 warnings. Placement matters for drift detection.

**Status**: Ready to build on this foundation.
