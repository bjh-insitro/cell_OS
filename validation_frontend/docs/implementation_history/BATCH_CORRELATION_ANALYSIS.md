# Batch Correlation Risk Analysis

## Current Proportional Interspersion Algorithm

From `DesignCatalogTab.tsx` lines 593-609:

```typescript
// Interleave based on density - add experimental or sentinel based on which is "due"
let expIdx = 0;
let sentIdx = 0;

for (let i = 0; i < totalWells; i++) {
  // Calculate what proportion we've added so far
  const expProportion = expIdx / experimentalWells.length;
  const sentProportion = sentIdx / sentinelWells.length;

  // Add whichever type is "behind" its target proportion
  if (expIdx < experimentalWells.length &&
      (sentIdx >= sentinelWells.length || expProportion <= sentProportion)) {
    allWells.push(experimentalWells[expIdx++]);
  } else if (sentIdx < sentinelWells.length) {
    allWells.push(sentinelWells[sentIdx++]);
  }
}
```

## Risk: Can This Correlate Batch Factors with Plate Regions?

**YES - Silent killer identified.**

### The Problem

The algorithm intersperses based on **global proportion**, but:

1. **Experimental wells are ordered** by compound → dose → replicate
2. **Sentinels are ordered** by type (DMSO×8, tBHQ×5, etc.)
3. **This creates deterministic spatial patterns**

### Example: Phase0_v2 (60 experimental + 28 sentinel = 88 wells)

**Order of experimental wells**:
```
[Compound1_dose1_rep1, Compound1_dose1_rep2,
 Compound1_dose2_rep1, Compound1_dose2_rep2,
 ...
 Compound5_dose6_rep1, Compound5_dose6_rep2]  // 5 compounds × 6 doses × 2 reps = 60
```

**Order of sentinels**:
```
[DMSO, DMSO, DMSO, DMSO, DMSO, DMSO, DMSO, DMSO,  // 8
 tBHQ, tBHQ, tBHQ, tBHQ, tBHQ,                      // 5
 thapsigargin, thapsigargin, thapsigargin, thapsigargin, thapsigargin,  // 5
 oligomycin, oligomycin, oligomycin, oligomycin, oligomycin,  // 5
 MG132, MG132, MG132, MG132, MG132]                 // 5
```

**Proportional interspersion result**:
```
Positions 0-20:  Mostly Compound1 (early in experimental list)
Positions 20-40: Compound2-3 (middle)
Positions 40-60: Compound4 (later)
Positions 60-80: Compound5 (latest)
```

### Where Does Batch Confounding Happen?

**Phase0_v2 structure**: Separate plates per (day × operator × timepoint × cell_line)

**NO batch confounding within plates** because:
- Each plate is a single batch slice
- All compounds on same plate are in same batch
- Spatial position ≠ batch factor

**However, confounding CAN happen if**:
1. Different cell lines get different compound splits (5 each for v2)
2. Compound assignment is batch-dependent

## Current V2 Compound Splitting

From generator comments and PHASE0_V2_VALIDATION.md:
- 10 total compounds split into 2 groups of 5
- Each plate gets 5 compounds (not specified which 5)

**CRITICAL QUESTION**: Are the same 5 compounds always together, or does it vary?

If compounds [0-4] always on sub-plate A and [5-9] always on sub-plate B:
- ✅ No batch confounding (deterministic split)
- ✅ Easy to analyze

If compound assignment varies by day/operator/timepoint:
- ✗ **SEVERE batch confounding**
- ✗ Cannot separate compound effect from batch effect

## Fixed vs Statistical Sentinel Positions

### My Recommendation: **Fixed Positions for Phase 0 Founder**

**Why fixed**:
1. **Drift detection**: Compare plate N from campaign 1 vs campaign 2 at exact same sentinel positions
2. **Heatmap clarity**: Sentinels always in predictable spots makes visual QC instant
3. **Reduces degrees of freedom**: Placement can't accidentally absorb batch structure
4. **SPC is easier**: Fixed positions = cleaner control charts

**Implementation**:
```typescript
// Define fixed sentinel positions for 96-well (8 excluded)
const FIXED_SENTINEL_POSITIONS = [
  'A02', 'A05', 'A09', 'A11',  // Row A (4)
  'B03', 'B07', 'B10',          // Row B (3)
  'C02', 'C06', 'C09', 'C12',  // Row C (4)
  'D04', 'D08', 'D11',          // Row D (3)
  'E03', 'E07', 'E10',          // Row E (3)
  'F02', 'F06', 'F09', 'F12',  // Row F (4)
  'G04', 'G08', 'G11',          // Row G (3)
  'H03', 'H05', 'H09', 'H11',  // Row H (4)
];  // 28 total, spatially distributed

// Then assign which sentinel type goes where (deterministic by seed)
const sentinelAssignment = shuffleWithSeed(
  [
    ...Array(8).fill('DMSO'),
    ...Array(5).fill('tBHQ'),
    ...Array(5).fill('thapsigargin'),
    ...Array(5).fill('oligomycin'),
    ...Array(5).fill('MG132'),
  ],
  seed
);

for (let i = 0; i < FIXED_SENTINEL_POSITIONS.length; i++) {
  wells.push({
    well_pos: FIXED_SENTINEL_POSITIONS[i],
    is_sentinel: true,
    sentinel_type: sentinelAssignment[i],
    ...
  });
}
```

**Benefits**:
- Sentinels always in same physical positions across all plates/campaigns
- Only TYPE assignment varies (but still deterministic by seed)
- Easy to validate: "sentinels must be at these 28 positions"
- Spatial binning check becomes trivial (bins are pre-determined)

### Statistical Distribution (current approach)

**Benefits**:
- Flexible for weird exclusion patterns
- Works with any plate format

**Costs**:
- Can accidentally correlate with batch structure
- Harder to compare across campaigns
- More degrees of freedom = more ways to hide confounding
- Harder to explain in meetings

## Recommendation for Phase0_v2

### Short-term (current implementation):
1. Add `inv_batchBalance` to catch any confounding
2. Run both invariants on actual v2 design
3. If violations found, investigate compound split assignment

### Medium-term (next iteration):
1. Implement fixed sentinel positions
2. Keep proportional interspersion for experimentals only
3. This gives best of both: fixed structure + flexible experimental layout

### Long-term (ideal):
1. Fixed sentinel scaffolding
2. Fixed experimental blocks per compound (but shuffled order within blocks)
3. Seed determines shuffles, not positions
4. Result: maximally reproducible, minimally confounded

## Next: inv_batchBalance Implementation

**What to check**:

1. **Marginal balance per batch factor**:
```typescript
for (const batchFactor of ['day', 'operator', 'timepoint']) {
  const countsPerLevel = countWellsByBatchLevel(wells, batchFactor);
  const expected = totalWells / nLevels;
  for (const [level, actual] of countsPerLevel) {
    if (Math.abs(actual - expected) > 1) {
      violations.push({
        type: 'batch_marginal_imbalance',
        severity: 'error',
        message: `Batch factor ${batchFactor} level ${level} has ${actual} wells (expected ${expected}).`,
      });
    }
  }
}
```

2. **Condition × batch independence**:
```typescript
for (const condition of uniqueConditions) {
  const batchDist = getBatchDistribution(wells, condition);
  const maxDeviation = Math.max(...batchDist.map(p => Math.abs(p - 1/nBatches)));

  if (maxDeviation > 0.1) {  // >10% deviation from uniform
    violations.push({
      type: 'batch_condition_confounding',
      severity: 'warning',
      message: `Condition ${condition} not uniformly distributed across batches.`,
      details: { maxDeviation, distribution: batchDist },
    });
  }
}
```

3. **Chi-square test for independence** (optional, "mathy but explainable"):
```typescript
const contingencyTable = buildContingencyTable(wells, 'compound+dose', 'batch');
const chiSquare = computeChiSquare(contingencyTable);
const pValue = chiSquarePValue(chiSquare, dof);

if (pValue < 0.05) {
  violations.push({
    type: 'batch_condition_dependence',
    severity: 'warning',
    message: `Conditions not independent of batch factors (χ²=${chiSquare.toFixed(2)}, p=${pValue.toFixed(4)}).`,
  });
}
```

This will catch the silent killer before it kills the founder dataset.
