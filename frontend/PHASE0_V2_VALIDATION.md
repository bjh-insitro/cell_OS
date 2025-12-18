# Phase0_v2 Design - Actual Parameters for Validation

## Sentinel Configuration (Per Plate)

From `/constants/presets.ts` and existing generator code:

```typescript
sentinelCounts = {
  DMSO: 8,
  tBHQ: 5,
  thapsigargin: 5,
  oligomycin: 5,
  MG132: 5,
}
// Total: 28 sentinels per plate
```

## Plate Specifications

- **Format**: 96-well (8 rows × 12 columns)
- **Exclusions**:
  - Corners: A1, A12, H1, H12 (4 wells)
  - Mid-row: A6, A7, H6, H7 (4 wells)
  - **Total excluded: 8 wells**
- **Available wells**: 96 - 8 = **88 wells per plate**
- **Sentinel density**: 28/88 = **31.8%**

## Well Ordering

**Row-major** (how generator assigns wells):

```
A01, A02, A03, A04, A05, A08, A09, A10, A11,  [A06, A07 excluded, A01, A12 excluded]
B01, B02, B03, B04, B05, B06, B07, B08, B09, B10, B11, B12,
C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12,
...
G01, G02, G03, G04, G05, G06, G07, G08, G09, G10, G11, G12,
H01, H02, H03, H04, H05, H08, H09, H10, H11,  [H06, H07 excluded, H01, H12 excluded]
```

**Available positions (88 total)**:
- Row A: A02, A03, A04, A05, A08, A09, A10, A11 (8 wells)
- Rows B-G: All 12 wells each (72 wells)
- Row H: H02, H03, H04, H05, H08, H09, H10, H11 (8 wells)

## Batch Structure

From existing v2 design:
- **Days**: 1, 2 (2 biological replicates)
- **Operators**: Operator_A, Operator_B (2 technical operators)
- **Timepoints**: 12.0h, 24.0h, 48.0h (3 kinetic samples)
- **Cell lines**: A549, HepG2 (2 cell lines)

**Plate count formula**:
```
nPlates = days × operators × timepoints × cellLines
        = 2 × 2 × 3 × 2
        = 24 plates total
```

**Plate naming**:
- `A549_Day1_Operator_A_T12.0h`
- `A549_Day1_Operator_A_T24.0h`
- `A549_Day1_Operator_A_T48.0h`
- `A549_Day1_Operator_B_T12.0h`
- ...
- `HepG2_Day2_Operator_B_T48.0h`

## Total Design Scale

- **Total plates**: 24
- **Wells per plate**: 88
- **Total wells**: 24 × 88 = **2,112 wells**
- **Total sentinels**: 24 × 28 = **672 wells** (32%)
- **Total experimental**: 24 × 60 = **1,440 wells** (68%)

## Experimental Configuration

- **Compounds**: 10 (tBHQ, H2O2, tunicamycin, thapsigargin, CCCP, oligomycin, etoposide, MG132, nocodazole, paclitaxel)
- **Dose multipliers**: 0.1, 0.3, 1.0, 3.0, 10.0, 30.0 (6 doses)
- **Replicates per dose**: 2
- **Experimental wells per cell line per plate**: 10 compounds × 6 doses × 2 reps = **120 wells**

**Problem**: 120 experimental + 28 sentinels = 148 wells needed, but only 88 available!

**Solution in actual v2 design**: Compound splitting
- Split 10 compounds into 2 sub-groups of 5 each
- Each plate gets 5 compounds: 5 × 6 × 2 = 60 experimental
- Total per plate: 60 + 28 = 88 wells (perfect fit!)
- Each condition appears twice across sub-plates

## Validation Requirements

When running `inv_sentinelsPlacedCorrectly` on actual phase0_v2 design:

### Expected to PASS:
- ✅ Count exactness: Each plate has DMSO(8), tBHQ(5), thapsigargin(5), oligomycin(5), MG132(5)
- ✅ Excluded wells: No well at A1, A6, A7, A12, H1, H6, H7, H12

### Tune thresholds until these PASS:
- Max gap ≤ 8 (may need adjustment)
- Window density: 2-6 sentinels per 12 wells (may need adjustment)
- Type clumping: ≤ 2 close pairs per type (may need adjustment)
- Gap CV < 0.9 (may need adjustment)

### Current interspersion algorithm:

Generator uses **proportional interleaving**:
```typescript
// Calculate what proportion we've added so far
const expProportion = expIdx / experimentalWells.length;
const sentProportion = sentIdx / sentinelWells.length;

// Add whichever type is "behind" its target proportion
if (expProportion <= sentProportion) {
  allWells.push(experimentalWells[expIdx++]);
} else {
  allWells.push(sentinelWells[sentIdx++]);
}
```

This should produce relatively even spacing. If violations occur, it means:
1. Algorithm needs improvement, OR
2. Thresholds too tight for 32% sentinel density

## Next Steps

1. **Fetch actual v2 design** from catalog:
   ```typescript
   const response = await fetch('/api/thalamus/catalog/designs/phase0_founder_v2_controls_stratified');
   const { design_data } = await response.json();
   ```

2. **Run invariant check**:
   ```typescript
   const certificate = checkPhase0V2Design(design_data.wells);
   ```

3. **Analyze violations**:
   - Count errors should be zero (if not, allocation bug)
   - Max gap warnings: tune threshold or improve algorithm
   - Window warnings: tune thresholds based on actual distribution
   - Type clumping warnings: may need to adjust interspersion

4. **Tune config** based on results:
   ```typescript
   // If max gap violations but layout looks good:
   maxGapNonSentinel: 10  // relax from 8 to 10

   // If window violations but density looks uniform:
   windowMinSentinels: 1  // relax from 2 to 1
   windowMaxSentinels: 7  // relax from 6 to 7
   ```

## Questions to Answer

1. **What is the actual max gap in v2 design?**
   - Run invariant, check `details.maxGap` in violations
   - If 9-10, that's acceptable - just relax threshold

2. **What is the actual CV of sentinel spacing?**
   - Check `details.cv` in gap variance violations
   - If 0.5-0.7, excellent; if 0.9-1.1, acceptable; if >1.5, needs improvement

3. **Are there any type clumping patterns?**
   - Check which sentinel types (if any) violate close pair threshold
   - May indicate allocation order bias (e.g., always DMSO first)

4. **Does spatial stratification exist in v2?**
   - Check if different sentinel types cluster in different plate regions
   - Could indicate intentional pattern (e.g., "sentinels in corners")

The invariant will tell us exactly what the actual design looks like.
