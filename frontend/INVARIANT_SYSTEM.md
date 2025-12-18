# Design Invariant System

## Philosophy

**Design logic is religion, not heuristics.**

Invariants are executable specifications of what makes a design correct. They:
- Return violations (errors/warnings), not booleans
- Are defensible in meetings ("max gap of 8 wells" not "evenly distributed")
- Prevent regressions (run in tests)
- Generate certificates (reproducibility)

## Architecture: Three Phases

### Phase A: Capacity
Compute effective capacity after exclusions and reservations.
**Output**: `{ available, reserved, free, canFit, violations }`

### Phase B: Allocation
Decide counts per factor (compound × dose × replicate × cell line).
**Output**: `{ tokens, tokensByPlate, violations }`

### Phase C: Placement
Assign tokens to well positions with explicit optimization goals.
**Output**: `{ wells, certificate, violations }`

---

## Implemented: inv_sentinelsPlacedCorrectly ✅

**Policy**: Max Identifiability (Phase 0 Founder)

### What "interspersed" means (executable):

#### 1. Count Exactness (ERROR level)
Each sentinel type must have **exact** expected count per plate.

**Phase0_v2**:
- DMSO: 8
- tBHQ: 5
- thapsigargin: 5
- oligomycin: 5
- MG132: 5
- **Total: 28 sentinels per plate** (32% density)

**Violation**: `sentinel_count_mismatch`

---

#### 2. Distribution Constraints (WARNING level)

**2a. Max Gap**
The longest run of consecutive non-sentinel wells must be ≤ threshold.

**Phase0_v2**: `maxGapNonSentinel = 8`

This prevents "all sentinels grouped at end" patterns.

**Violation**: `sentinel_max_gap_exceeded`

**Example**:
```
✓ Good: S-E-E-E-S-E-E-E-S-E-E-E-S  (max gap = 3)
✗ Bad:  S-S-S-S-E-E-E-E-E-E-E-E-E  (max gap = 9)
```

---

**2b. Sliding Window Density**
In any window of size W, sentinel count must be in [min, max].

**Phase0_v2**:
- `windowSize = 12` (about 1 column)
- `windowMinSentinels = 2`
- `windowMaxSentinels = 6`

This enforces local uniformity - prevents clustering or voids.

**Violation**: `sentinel_window_density`

**Example** (window size 12):
```
✓ Good: [S-E-E-E-S-E-E-E-S-E-E-E] = 3 sentinels
✗ Bad:  [S-S-S-S-S-S-E-E-E-E-E-E] = 6 sentinels (max)
✗ Bad:  [E-E-E-E-E-E-E-E-E-E-E-S] = 1 sentinel (below min)
```

---

#### 3. Type Separation (WARNING level)

Same sentinel type should not appear "too close" too often.

**Phase0_v2**:
- `sameTypeCloseDistance = 3` (within 3 positions is "close")
- `maxClosePairsPerType = 2` (max 2 close pairs)

This prevents: `DMSO-DMSO-DMSO-DMSO-DMSO-DMSO-DMSO-DMSO` (all consecutive)

**Violation**: `sentinel_type_clumping`

**Example** (DMSO with distance=3):
```
✓ Good: DMSO at [0, 5, 10, 15, 20, 25, 30, 35]  (no close pairs)
✗ Bad:  DMSO at [0, 1, 2, 3, 4, 5, 6, 7]        (7 close pairs)
```

---

#### 4. Dispersion Metric (WARNING level)

Coefficient of variation (CV) of inter-sentinel gaps should be low.

**Phase0_v2**: `CV threshold = 0.9`

High CV means uneven spacing (clusters + voids).

**Violation**: `sentinel_gap_high_variance`

**Math**:
```
gaps = [dist between sentinel i and i+1]
mean_gap = mean(gaps)
std_gap = std(gaps)
CV = std_gap / mean_gap

CV < 0.9 → uniform spacing
CV > 0.9 → high dispersion (warning)
```

---

## Configuration for Phase0_v2

```typescript
export const PHASE0_V2_SENTINEL_CONFIG: SentinelInvariantConfig = {
  expectedCountsByType: {
    'dmso': 8,
    'tbhq': 5,
    'thapsigargin': 5,
    'oligomycin': 5,
    'mg132': 5,
  },
  plateFormat: 96,
  maxGapNonSentinel: 8,           // tight: no more than 8 non-sentinel in a row
  windowSize: 12,                  // window of 12 wells (~1 column)
  windowMinSentinels: 2,           // at least 2 sentinels per 12 wells
  windowMaxSentinels: 6,           // at most 6 sentinels per 12 wells
  sameTypeCloseDistance: 3,        // "close" = within 3 positions
  maxClosePairsPerType: 2,         // max 2 close pairs per type
};
```

### Why these numbers?

- **28 sentinels per 88 wells** = 32% sentinel density
- **Max gap 8**: Average experimental run is ~2.1 wells between sentinels, so 8 is ~4× average (tight but achievable)
- **Window 12, min 2**: 2/12 = 16.7% minimum local density (below average but allows some clustering)
- **Window 12, max 6**: 6/12 = 50% maximum local density (prevents overclustering)
- **Close distance 3**: Adjacent or 1-2 wells apart is "close"
- **Max 2 close pairs**: With 5-8 sentinels per type, allows some adjacency but prevents all-consecutive

These are **starting values** - tune based on real layouts.

---

## Well Ordering

Wells are linearized in **row-major order**:
```
A01, A02, A03, ..., A12,
B01, B02, B03, ..., B12,
...
H01, H02, H03, ..., H12
```

This matches the generator's well assignment order and is the most intuitive for lab personnel.

**Position to index**: `index = (row - 'A') * nCols + (col - 1)`

---

## Test Coverage

### Unit Tests (`__tests__/sentinelPlacement.test.ts`)

1. **Count exactness**: Error if counts don't match exactly
2. **Max gap**: Warning if non-sentinel run > threshold
3. **Windowing**: Warning if any window violates density
4. **Type clumping**: Warning if same type too close too often
5. **Gap variance**: Warning if CV > threshold
6. **Multi-plate**: Each plate validated independently

### Regression Tests (TODO)

Run against actual phase0_v2 design from catalog:
```typescript
const phase0v2Wells = await fetchDesign('phase0_founder_v2_controls_stratified');
const certificate = checkPhase0V2Design(phase0v2Wells);

// Should have ZERO errors (all warnings acceptable)
expect(certificate.violations.filter(v => v.severity === 'error')).toHaveLength(0);
```

---

## Implemented: inv_batchBalance ✅

**Policy**: Max Identifiability (Phase 0 Founder)

**The one that actually matters.**

This invariant prevents accidentally building confounding into the founder dataset. If conditions correlate with batch factors, you cannot separate compound effects from batch effects.

### Three Levels of Defense

#### 1. Marginal Balance (ERROR level)

Each batch factor level must have equal well counts (±1 tolerance).

**Phase0_v2 batch factors**:
- day: 1, 2 (2 biological replicates)
- operator: Operator_A, Operator_B (2 technical operators)
- timepoint: 12.0h, 24.0h, 48.0h (3 kinetic samples)
- cell_line: A549, HepG2 (2 cell lines)

**Violation**: `batch_marginal_imbalance`

**Example**:
```
✓ Good: Day 1: 60 wells, Day 2: 60 wells (balanced)
✗ Bad:  Day 1: 80 wells, Day 2: 40 wells (imbalanced)
```

**Why ERROR**: Marginal imbalance always indicates allocation bug.

---

#### 2. Condition Independence (WARNING level)

Each condition must be uniformly distributed across batch levels (≤10% deviation).

**Condition definition**: compound + dose (ignore replicates)

**Violation**: `batch_condition_confounding`

**Example**:
```
✓ Good: tBHQ@10uM appears 2× in Day 1, 2× in Day 2 (uniform 50/50)
✗ Bad:  tBHQ@10uM appears 4× in Day 1, 0× in Day 2 (100% confounded)
         → Cannot separate tBHQ effect from day effect!
```

**Why WARNING**: May be acceptable for pilots, but Phase 0 founder demands perfection.

---

#### 3. Chi-Square Test (WARNING level)

Contingency table (condition × batch) must be independent (p ≥ 0.05).

**Violation**: `batch_condition_dependence`

**Example**:
```
Contingency table:
           Day1  Day2
tBHQ@10uM    4     0
H2O2@5uM     0     4

χ² = 8.0, df = 1, p = 0.0047 < 0.05
→ WARNING: Significant dependence detected
```

**Why**: Mathy but explainable. Chi-square test is standard in experimental design literature.

---

### Configuration for Phase0_v2

```typescript
export const PHASE0_V2_BATCH_CONFIG: BatchInvariantConfig = {
  batchFactors: [
    { name: 'day', extractor: (w) => w.day },
    { name: 'operator', extractor: (w) => w.operator },
    { name: 'timepoint', extractor: (w) => w.timepoint_h },
    { name: 'cell_line', extractor: (w) => w.cell_line },
  ],
  conditionKey: (w) => `${w.compound}@${w.dose_uM}uM`,
  marginalBalanceTolerance: 1,           // ±1 well
  conditionDistributionTolerance: 0.1,   // ≤10% deviation
  runChiSquareTest: true,
  chiSquareAlpha: 0.05,
};
```

### Test Coverage

**Unit Tests** (`__tests__/batchBalance.test.ts`):
1. **Marginal balance**: Pass when balanced, error when imbalanced, check all factors
2. **Condition independence**: Pass when uniform, warn when confounded, detect partial skew
3. **Chi-square test**: Pass when independent, warn when dependent
4. **Edge cases**: Skip sentinels, handle zero wells, handle undefined values, multi-plate

---

## Next Invariants to Implement

### 3. inv_plateCapacityRespected

**Checks**:
- `wells.length ≤ availableWells` for every plate
- No well uses excluded position

**Violation types**:
- `plate_overflow`: Too many wells on plate
- `excluded_well_used`: Well in excluded position

---

### 4. inv_ic50DoseCalculation

**Checks**:
- `dose_uM === dose_multiplier × compound_IC50` (within tolerance)
- Dose multipliers sorted and unique

**Violation types**:
- `dose_calculation_error`: Dose doesn't match IC50 formula
- `dose_order_violation`: Doses not sorted

---

### 5. inv_cellLineStratification

**Checks**:
- Phase0_v2 policy: separate plates per cell line (no mixing)
- Each plate has exactly one cell line

**Violation types**:
- `cell_line_mixing`: Multiple cell lines on same plate
- `cell_line_missing`: Expected cell line not present

---

### 6. inv_wellPositionUniqueness

**Checks**:
- No duplicate (plate_id, well_pos) pairs
- All positions valid for plate format

**Violation types**:
- `duplicate_well_position`: Same position used twice
- `invalid_well_position`: Position doesn't exist on plate

---

### 7. inv_replicateStructure

**Checks**:
- Each (compound × dose × cell_line × batch) has expected replicate count
- Replicates are spatial/temporal replicates (not same well)

**Violation types**:
- `replicate_count_mismatch`: Wrong number of replicates
- `replicate_collision`: Replicates on same plate at same time

---

## Certificate Output

When generator runs, it produces:

```typescript
interface DesignCertificate {
  seed?: number;
  paramsHash: string;
  invariantsVersion: string;
  plateFormat: 96 | 384;
  exclusions: { corners, midRow, edges };
  timestamp: string;
  violations: Violation[];
  stats: {
    totalWells: number;
    sentinelWells: number;
    experimentalWells: number;
    nPlates: number;
  };
}
```

**If generator cannot satisfy constraints**: `wells = []`, violations explain why.

**UI renders certificate**: Shows violations, allows user to fix params.

---

## Scoring Function for Placement (TODO)

Once all invariants pass, placement can be optimized via score:

```typescript
function scorePlacement(wells: Well[], policy: 'max_identifiability'): number {
  return (
    10 * sentinelUniformityScore(wells) +      // HIGH - even distribution
    8  * batchBalanceScore(wells) +            // HIGH - no confounding
    6  * spatialSeparationScore(wells) +       // MEDIUM - avoid clustering
    4  * edgeAvoidanceScore(wells) +           // MEDIUM - corners excluded
    1  * throughputScore(wells)                // LOW - not the goal
  );
}
```

**For max identifiability**: Sentinel uniformity and batch balance dominate.

---

## Summary

**Implemented**:
1. ✅ `inv_sentinelsPlacedCorrectly` - 5 checks (count, max gap, window density, type separation, gap CV, spatial binning)
2. ✅ `inv_batchBalance` - 3 checks (marginal balance, condition independence, chi-square test)

**Config**: Parameterized for Phase0_v2 with tight constraints:
- Sentinels: 32% density, max gap 8, windowing, CV threshold, 2D spatial binning
- Batch balance: ±1 well tolerance, ≤10% condition distribution deviation, α=0.05 for chi-square

**Tests**: Comprehensive unit tests for all failure modes + happy paths.

**Next**:
- Run on actual phase0_v2 design to validate
- Implement remaining invariants (capacity, IC50, cell line, uniqueness, replicates)

The invariant system is **executable**, **testable**, and **defensible**. No vibes, just math.
