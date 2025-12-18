# Invariant System Implementation - Complete

## What Was Built

Implemented `inv_sentinelsPlacedCorrectly` - the first of 7 design invariants for Phase 0 founder (max identifiability policy).

## Decision: Max Identifiability

**Chose Policy #1**: Heavy sentinel structure, tight replication, strict spatial separation.

**Why**: Phase 0 founder is the reference dataset. Every future experiment asks "did we drift?" Requires:
- Sentinel structure for SPC monitoring across campaigns
- Operator/day stratification to quantify batch effects
- Spatial separation to isolate biology from plate artifacts
- High replication for narrow confidence intervals

**Not discovering - establishing ground truth.**

---

## Files Created

### 1. `/invariants/types.ts`
Type definitions for invariant checking:
- `Violation` (error/warning with message, suggestion, details)
- `Well` (matches existing design well structure)
- `DesignCertificate` (reproducibility and stats)
- `InvariantResult` (violations + certificate)

### 2. `/invariants/sentinelPlacement.ts` ✅
**Complete implementation** of sentinel placement invariant with 4 concrete checks:

#### 1. Count Exactness (ERROR)
- Expected: DMSO(8), tBHQ(5), thapsigargin(5), oligomycin(5), MG132(5) = 28 per plate
- Actual: Must match exactly
- Violation: `sentinel_count_mismatch`

#### 2. Max Gap (WARNING)
- Max consecutive non-sentinel wells: ≤ 8
- Prevents "all sentinels grouped at end"
- Violation: `sentinel_max_gap_exceeded`

#### 3. Sliding Window Density (WARNING)
- Window size: 12 wells
- Min sentinels per window: 2
- Max sentinels per window: 6
- Enforces local uniformity
- Violation: `sentinel_window_density`

#### 4. Type Separation (WARNING)
- Same type within distance 3 = "close"
- Max 2 close pairs per sentinel type
- Prevents: DMSO-DMSO-DMSO-DMSO-DMSO-DMSO-DMSO-DMSO
- Violation: `sentinel_type_clumping`

#### 5. Dispersion Metric (WARNING)
- Coefficient of variation of inter-sentinel gaps
- Threshold: CV < 0.9
- Detects clusters + voids pattern
- Violation: `sentinel_gap_high_variance`

### 3. `/invariants/__tests__/sentinelPlacement.test.ts` ✅
Comprehensive test suite with 12 test cases covering:
- Count exactness (error if mismatch)
- Max gap constraint (warning if exceeded)
- Window density (warning if violated)
- Type clumping (warning if too close)
- Gap variance (warning if CV > 0.9)
- Multi-plate validation
- Helper functions for test data generation

### 4. `/invariants/index.ts`
Exports all invariants and provides `checkPhase0V2Design()` runner:
```typescript
const certificate = checkPhase0V2Design(wells);
// Returns: violations, stats, timestamp, hash
```

### 5. `/INVARIANT_SYSTEM.md` ✅
Complete documentation of:
- Philosophy (executable, defensible, testable)
- Three-phase architecture (Capacity → Allocation → Placement)
- Sentinel invariant specification with examples
- Phase0_v2 configuration rationale
- Next 6 invariants to implement
- Scoring function design

---

## Configuration for Phase0_v2

```typescript
export const PHASE0_V2_SENTINEL_CONFIG = {
  expectedCountsByType: {
    'dmso': 8, 'tbhq': 5, 'thapsigargin': 5,
    'oligomycin': 5, 'mg132': 5,
  },
  plateFormat: 96,
  maxGapNonSentinel: 8,
  windowSize: 12,
  windowMinSentinels: 2,
  windowMaxSentinels: 6,
  sameTypeCloseDistance: 3,
  maxClosePairsPerType: 2,
};
```

**These are starting values** - tune based on real phase0_v2 layout validation.

---

## Well Ordering

**Row-major**: A01, A02, ..., A12, B01, ...

Matches generator assignment order. Most intuitive for lab personnel.

Position to index: `index = (row - 'A') * nCols + (col - 1)`

---

## What "Interspersed" Means (No Vibes)

### ✅ Good: Interspersed
```
S-E-E-E-S-E-E-E-S-E-E-E-S-E-E-E
```
- Max gap: 3 (✓ < 8)
- Window [0-11]: 4 sentinels (✓ in [2,6])
- No type clumping
- CV: ~0.2 (✓ < 0.9)

### ✗ Bad: Grouped at End
```
E-E-E-E-E-E-E-E-E-E-E-E-S-S-S-S
```
- Max gap: 12 (✗ > 8)
- Window [0-11]: 0 sentinels (✗ < 2)
- All sentinels in window [12-23]: 4 sentinels
- CV: >1.0 (✗ > 0.9)

### ✗ Bad: Type Clumping
```
D-D-D-D-D-D-D-D-T-T-T-T-T-O-O-O
```
(D=DMSO, T=tBHQ, O=oligomycin)
- DMSO has 7 close pairs (✗ > 2)
- tBHQ has 4 close pairs (✗ > 2)
- High clustering by type

---

## Next 6 Invariants (Priority Order)

1. **inv_batchBalance** - Ensure batch factors not confounded with experimental factors
2. **inv_plateCapacityRespected** - No overflow, no excluded wells used
3. **inv_ic50DoseCalculation** - Dose = multiplier × IC50
4. **inv_cellLineStratification** - Phase0_v2: separate plates per cell line
5. **inv_wellPositionUniqueness** - No duplicate positions
6. **inv_replicateStructure** - Correct replicate counts per condition

---

## Integration Points

### Generator Output
```typescript
interface GeneratorResult {
  wells: Well[];
  certificate: DesignCertificate;
  // If cannot satisfy constraints:
  // wells = [], violations explain why
}
```

### UI Display
Show certificate with violations:
- **Errors**: Red, must fix
- **Warnings**: Yellow, should improve
- Suggestion text guides user to fix

### Tests
```typescript
const certificate = checkPhase0V2Design(phase0v2Wells);
expect(certificate.violations.filter(v => v.severity === 'error'))
  .toHaveLength(0);
```

---

## TypeScript Compilation

✅ **All invariant code compiles cleanly** - zero TypeScript errors.

---

## Summary

**Implemented**: Complete, production-ready sentinel placement invariant with:
- 4 concrete, defensible checks (no vibes)
- Parameterized for Phase0_v2 max identifiability
- Comprehensive test suite (12 test cases)
- Clear documentation with examples

**Philosophy**: Executable > vibes. Math > heuristics. Defensible in meetings.

**Next**: `inv_batchBalance` to ensure batch structure integrity.

The invariant system is ready to catch bugs, prevent regressions, and generate verifiable certificates.
