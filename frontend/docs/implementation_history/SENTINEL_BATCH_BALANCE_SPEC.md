# Sentinel Batch Balance Invariant - Specification

## Purpose

Phase 0 uses sentinels as the drift thermometer for SPC monitoring. If sentinels are unbalanced across batch factors, SPC charts get biased.

**Separate from experimental batch balance**: This checks sentinel structure, not experimental conditions.

## The Problem

If sentinels cluster in specific batch slices:
- Day 1 has mostly DMSO sentinels
- Day 2 has mostly tBHQ sentinels

Result: Cannot tell if drift signal is real or artifact of sentinel type distribution.

## Checks

Similar to `inv_batchBalance`, but sentinel-only:

### 1. Sentinel Marginal Balance

Each batch factor level should have equal sentinel counts (looser tolerance than experimental).

```typescript
// Per sentinel type, check balance across batch factors
for (const sentinelType of ['DMSO', 'tBHQ', 'thapsigargin', 'oligomycin', 'MG132']) {
  for (const factor of ['day', 'operator', 'timepoint']) {
    // Count sentinels of this type per batch level
    // Warn if deviation > tolerance
  }
}
```

**Tolerance**: ±2 sentinels per type per level (looser than experimental ±1)

**Why looser**: Sentinels are QC structure, not primary scientific signal. Small imbalances acceptable.

### 2. Sentinel Type Distribution

Each batch factor level should have similar sentinel type proportions.

```typescript
// Check that each day/operator/timepoint has similar sentinel type mix
// Example: Day 1 should have ~8 DMSO, ~5 tBHQ, etc.
//          Day 2 should have ~8 DMSO, ~5 tBHQ, etc.
```

**Tolerance**: ±20% deviation from expected type proportions

### 3. No Sentinel Type × Batch Confounding

No sentinel type should be 100% in one batch level.

```typescript
// FAIL if: All DMSO in Day 1, All tBHQ in Day 2
// PASS if: DMSO distributed across both days
```

## Configuration

```typescript
export interface SentinelBatchConfig {
  batchFactors: Array<{
    name: string;
    extractor: (w: Well) => string | number | undefined;
  }>;

  expectedCountsByType: Record<string, number>;

  marginalBalanceTolerance: number;  // ±2 sentinels per type per level

  typeDistributionTolerance: number; // ±20% deviation from expected proportions
}
```

## Violation Types

### `sentinel_batch_marginal_imbalance` (WARNING)

Sentinel type not balanced across batch levels.

```typescript
{
  type: 'sentinel_batch_marginal_imbalance',
  severity: 'warning',
  message: `Sentinel type 'DMSO' not balanced across 'day': Day 1 has 6, Day 2 has 2 (expected 4 each, tolerance ±2).`,
}
```

### `sentinel_batch_type_confounding` (WARNING)

Sentinel type confounded with batch factor.

```typescript
{
  type: 'sentinel_batch_type_confounding',
  severity: 'warning',
  message: `Sentinel type 'DMSO' confounded with 'day': 100% in Day 1, 0% in Day 2.`,
}
```

## Why Separate Invariant

**Not part of `inv_batchBalance`** because:
1. Different tolerance thresholds (looser for sentinels)
2. Different severity (WARNING not ERROR)
3. Different purpose (SPC monitoring vs scientific inference)
4. Sentinels explicitly excluded from experimental batch balance

## Implementation

```typescript
// In /invariants/sentinelBatchBalance.ts
export function inv_sentinelBatchBalance(
  wells: Well[],
  cfg: SentinelBatchConfig
): Violation[] {
  const violations: Violation[] = [];

  // Filter to sentinel wells only
  const sentinelWells = wells.filter((w) => w.is_sentinel);

  // Check 1: Marginal balance per sentinel type
  // Check 2: Type distribution per batch level
  // Check 3: No 100% confounding

  return violations;
}
```

## Usage

```typescript
export function checkPhase0V2Design(wells: Well[]): DesignCertificate {
  violations.push(...inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG));
  violations.push(...inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG));
  violations.push(...inv_sentinelBatchBalance(wells, PHASE0_V2_SENTINEL_BATCH_CONFIG)); // NEW

  return certificate;
}
```

## Priority

**Medium priority** (after core invariants).

Not as critical as experimental batch balance, but important for SPC reliability.

## Next Steps

1. Implement after `inv_batchBalance` validated on actual v2 design
2. Test on actual sentinel distribution from v2
3. Tune tolerance thresholds based on real layouts

## Status

📋 **Specification complete**
⏳ **Implementation pending**
