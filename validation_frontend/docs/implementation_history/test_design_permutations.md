# Design Generator Permutation Testing

## Test Plan

### Parameters to Test:
1. **Cell lines**: 1, 2, 4 cell lines
2. **Compounds**: 0, 1, 5, 10 compounds
3. **Plate format**: 96-well, 384-well
4. **Checkerboard**: true, false
5. **Exclusions**: corners only, corners+midrow, corners+midrow+edges, none
6. **Doses**: 4 doses, 6 doses, 8 doses
7. **Replicates**: 1, 2, 3

### Critical Scenarios:

## Scenario 1: Default (phase0_v2 match)
- Cell lines: 2 (A549, HepG2)
- Compounds: 10 (all)
- Doses: 6 (0.1, 0.3, 1.0, 3.0, 10.0, 30.0)
- Replicates: 2
- Days: 2
- Operators: 2
- Timepoints: 3
- Plate: 96-well
- Checkerboard: false
- Exclude corners: true
- Exclude mid-row: true
- Exclude edges: false

**Expected**:
- Shows v2 design from file
- 88 wells/plate
- 24 plates
- 2,112 total wells
- fits=true

**Issues to check**:
- [ ] Does it load v2 design?
- [ ] Does calculator show correct stats?
- [ ] Are sentinels interspersed?
- [ ] Available wells = 88?

---

## Scenario 2: Uncheck mid-row wells (should break v2 match)
- Same as Scenario 1 but exclude_mid_row: false

**Expected**:
- Falls back to algorithmic generation
- 92 wells/plate available
- Still doesn't fit (needs 148, has 92)
- Shows overflow warning

**Issues to check**:
- [ ] Does it switch to algorithmic mode?
- [ ] Available wells = 92?
- [ ] Are A6, A7, H6, H7 visible in preview?
- [ ] Does overflow warning show?

---

## Scenario 3: Single cell line, few compounds (should fit)
- Cell lines: 1 (A549)
- Compounds: 3 (tBHQ, CCCP, tunicamycin)
- Doses: 4 (0, 0.1, 1.0, 10.0)
- Replicates: 3
- Days: 1
- Operators: 1
- Timepoints: 1
- Sentinels: 4 DMSO only
- Plate: 96-well
- Checkerboard: false
- Exclude corners: true
- Exclude mid-row: true

**Expected**:
- Experimental: 3 compounds × 4 doses × 3 reps = 36 wells
- Sentinels: 4 wells
- Total: 40 wells
- Available: 88 wells
- fits=true
- 1 plate

**Issues to check**:
- [ ] Does calculator show 40 total wells?
- [ ] Does it show 1 plate?
- [ ] Does preview show sparse plate with empty wells?
- [ ] Are sentinels interspersed correctly?

---

## Scenario 4: Checkerboard with 2 cell lines
- Cell lines: 2 (A549, HepG2)
- Compounds: 5 (tBHQ, CCCP, tunicamycin, thapsigargin, oligomycin)
- Doses: 4 (0, 0.1, 1.0, 10.0)
- Replicates: 2
- Days: 1
- Operators: 1
- Timepoints: 1
- Sentinels: 8 DMSO, 5 each for others = 28 per cell
- Plate: 96-well
- Checkerboard: TRUE
- Exclude corners: true
- Exclude mid-row: true

**Expected**:
- Experimental per cell: 5 × 4 × 2 = 40
- Experimental both cells: 40 × 2 = 80
- Sentinels per cell: 28
- Sentinels both cells: 28 × 2 = 56
- Total: 136 wells
- Available: 88 wells
- fits=FALSE (overflow)
- 1 plate (checkerboard)

**Issues to check**:
- [ ] Does calculator show 136 wells needed?
- [ ] Does it show fits=false?
- [ ] Are both cell lines on same plate in preview?
- [ ] Are they interleaved properly?

---

## Scenario 5: 384-well high throughput
- Cell lines: 2 (A549, HepG2)
- Compounds: 10 (all)
- Doses: 8 (0, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0)
- Replicates: 2
- Days: 1
- Operators: 1
- Timepoints: 1
- Sentinels: 8 DMSO, 4 each for others = 24 per cell
- Plate: 384-well
- Checkerboard: TRUE
- Exclude corners: true
- Exclude mid-row: false

**Expected**:
- Experimental per cell: 10 × 8 × 2 = 160
- Experimental both: 320
- Sentinels both: 48
- Total: 368 wells
- Available: 380 (384 - 4 corners)
- fits=TRUE

**Issues to check**:
- [ ] Does calculator show fits=true?
- [ ] Does preview show 384-well layout?
- [ ] Are wells properly distributed?

---

## Scenario 6: 4 cell lines (neurons + microglia)
- Cell lines: 4 (all)
- Compounds: 4 (tBHQ, CCCP, tunicamycin, nocodazole)
- Doses: 4 (0, 0.1, 1.0, 10.0)
- Replicates: 2
- Days: 1
- Operators: 1
- Timepoints: 2 (12.0, 48.0)
- Sentinels: 8 DMSO only
- Plate: 96-well
- Checkerboard: false
- Exclude corners: true
- Exclude mid-row: true

**Expected**:
- Experimental per cell: 4 × 4 × 2 = 32
- Sentinels per cell: 8
- Total per plate: 40 wells
- Available: 88 wells
- fits=TRUE
- Plates: 4 cells × 2 timepoints = 8 plates

**Issues to check**:
- [ ] Does calculator show 8 plates?
- [ ] Does preview show all 4 cell lines?
- [ ] Are iPSC_NGN2 and iPSC_Microglia handled correctly?

---

## Scenario 7: Edge exclusion (maximal restriction)
- Cell lines: 1 (A549)
- Compounds: 3 (tBHQ, CCCP, tunicamycin)
- Doses: 4 (0, 0.1, 1.0, 10.0)
- Replicates: 2
- Days: 1
- Operators: 1
- Timepoints: 1
- Sentinels: 4 DMSO only
- Plate: 96-well
- Checkerboard: false
- Exclude corners: true
- Exclude mid-row: true
- Exclude edges: TRUE

**Expected**:
- Experimental: 3 × 4 × 2 = 24
- Sentinels: 4
- Total: 28 wells
- Available: 48 - 4 (corners) - 4 (midrow) = 40 wells (need to check this calculation)
- fits=TRUE

**Issues to check**:
- [ ] Does calculator handle triple exclusion correctly?
- [ ] Available wells calculation correct?
- [ ] Preview shows only inner wells?

---

## Scenario 8: Zero compounds (edge case)
- Cell lines: 1
- Compounds: 0 (none selected)
- Everything else default

**Expected**:
- Should show error or empty preview
- Calculator should handle gracefully

**Issues to check**:
- [ ] Does it crash?
- [ ] Does generatePreviewWells return empty?
- [ ] Any error messages?

---

## Scenario 9: Invalid dose string
- Dose multipliers: "abc, def, ghi" (invalid)

**Expected**:
- Should filter out NaN values
- May result in 0 doses

**Issues to check**:
- [ ] Does it crash?
- [ ] Does it gracefully handle invalid input?

---

## Scenario 10: Extreme sentinels
- Sentinels: 50 DMSO, 50 each compound
- Cell lines: 1
- Compounds: 1
- Doses: 4
- Replicates: 1

**Expected**:
- Experimental: 1 × 4 × 1 = 4
- Sentinels: 50 × 5 = 250
- Total: 254 wells
- Available: 88
- fits=FALSE (massive overflow)

**Issues to check**:
- [ ] Does calculator show correct overflow?
- [ ] Does preview truncate gracefully?
- [ ] Are sentinels still interspersed (not all grouped at end)?

---

## Key Issues to Look For:

### Calculator Issues:
1. Available wells calculation with different exclusion combos
2. Plate count calculation for checkerboard vs separate
3. Overflow detection (fits=true/false)
4. matchesV2Defaults logic

### Preview Generation Issues:
1. Sentinel interspersion algorithm
2. Well position assignment (A01, A02, ... H12)
3. Checkerboard cell line interleaving
4. Handling overflow (truncation at available wells)
5. Empty well positions when design fits with room to spare

### Exclusion Logic Issues:
1. Corner exclusion (A1, A12, H1, H12)
2. Mid-row exclusion (A6, A7, H6, H7) - only for 96-well
3. Edge exclusion (all first/last row/col)
4. Combinations of exclusions
5. 384-well exclusion patterns

### Edge Cases:
1. 0 compounds
2. 0 sentinels
3. Invalid input strings
4. Extreme values (1000 replicates, etc.)
5. Single day/operator/timepoint

## Testing Approach:

I'll now check the actual code logic for each of these scenarios.
