/**
 * Design invariants for Phase 0 founder
 *
 * Invariants are executable checks that define what makes a design correct.
 * They produce violations (errors/warnings) when constraints are not met.
 */

export * from './types';
export * from './sentinelPlacement';
export * from './batchBalance';
export * from './sentinelScaffold';
export * from './plateCapacity';
export * from './conditionMultiset';

import type { Well, Violation, DesignCertificate, DesignMetadata } from './types';
import { inv_sentinelsPlacedCorrectly, PHASE0_V2_SENTINEL_CONFIG } from './sentinelPlacement';
import { inv_batchBalance, PHASE0_V2_BATCH_CONFIG } from './batchBalance';
import {
  inv_sentinelScaffoldExactMatch,
  PHASE0_V2_SCAFFOLD_CONFIG,
  computeWellDerivedScaffoldHashStrict,
} from './sentinelScaffold';
import { inv_empty_wells_exactly_exclusions, PHASE0_V2_CAPACITY_CONFIG } from './plateCapacity';
import {
  inv_condition_multiset_identical_across_timepoints,
  inv_experimental_position_stability,
  PHASE0_V2_CONDITION_MULTISET_CONFIG,
} from './conditionMultiset';

/**
 * Run all invariants for Phase 0 v2 (max identifiability)
 */
export function checkPhase0V2Design(wells: Well[], designMetadata?: DesignMetadata): DesignCertificate {
  const violations: Violation[] = [];

  // 1. Sentinel scaffold exact match (FIRST - if scaffold is wrong, rest is irrelevant)
  violations.push(...inv_sentinelScaffoldExactMatch(wells, PHASE0_V2_SCAFFOLD_CONFIG, designMetadata));

  // 2. Plate capacity (no ghosts, no duplicates)
  violations.push(...inv_empty_wells_exactly_exclusions(wells, PHASE0_V2_CAPACITY_CONFIG));

  // 3. Condition multiset identical across timepoints (murder weapon antidote)
  violations.push(
    ...inv_condition_multiset_identical_across_timepoints(wells, PHASE0_V2_CONDITION_MULTISET_CONFIG)
  );

  // 4. Experimental position stability
  violations.push(...inv_experimental_position_stability(wells, PHASE0_V2_CONDITION_MULTISET_CONFIG));

  // 5. Sentinel placement quality
  violations.push(...inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG));

  // 6. Batch balance
  violations.push(...inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG));

  // TODO: 7. IC50 dose calculation
  // TODO: 8. Cell line stratification

  const sentinelWells = wells.filter((w) => w.is_sentinel).length;
  const experimentalWells = wells.length - sentinelWells;
  const plates = new Set(wells.map((w) => w.plate_id));

  // Compute well-derived scaffold hash (strict version that should match Python spec hash)
  const wellDerivedHash = computeWellDerivedScaffoldHashStrict(wells, PHASE0_V2_SCAFFOLD_CONFIG);

  // Check if well-derived hash matches expected (CRITICAL for Phase 0 founder)
  const wellDerivedMatchesExpected = wellDerivedHash === PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffoldHash;

  if (wellDerivedHash && !wellDerivedMatchesExpected) {
    violations.push({
      type: 'scaffold_well_derived_hash_mismatch',
      severity: 'error',
      message: `Well-derived scaffold hash (${wellDerivedHash}) does not match expected scaffold hash (${PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffoldHash}). Wells may contain incorrect sentinel data.`,
      suggestion: 'This indicates the wells do not contain the exact expected scaffold. Check compound names, doses, or type assignments.',
      details: {
        expected: PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffoldHash,
        wellDerived: wellDerivedHash,
      },
    });
  }

  const certificate: DesignCertificate = {
    paramsHash: hashWells(wells),
    invariantsVersion: '1.0.0',
    plateFormat: 96, // TODO: detect from wells
    exclusions: {
      corners: true,
      midRow: true,
      edges: false,
    },
    timestamp: new Date().toISOString(),
    violations,
    stats: {
      totalWells: wells.length,
      sentinelWells,
      experimentalWells,
      nPlates: plates.size,
    },
    scaffoldMetadata: {
      expected: {
        scaffoldId: PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffoldId,
        scaffoldHash: PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffoldHash,
        scaffoldSize: PHASE0_V2_SCAFFOLD_CONFIG.expectedScaffold.length,
      },
      observed: {
        scaffoldId: designMetadata?.sentinel_schema?.scaffold_metadata?.scaffold_id,
        scaffoldHash: designMetadata?.sentinel_schema?.scaffold_metadata?.scaffold_hash,
        scaffoldSize: designMetadata?.sentinel_schema?.scaffold_metadata?.scaffold_size,
        wellDerivedHash: wellDerivedHash ?? undefined,
        wellDerivedMatchesExpected: wellDerivedHash ? wellDerivedMatchesExpected : undefined,
      },
    },
  };

  return certificate;
}

/**
 * Simple hash of wells for reproducibility checking
 */
function hashWells(wells: Well[]): string {
  // Simple deterministic hash based on well count and positions
  const sorted = [...wells].sort((a, b) =>
    a.plate_id.localeCompare(b.plate_id) || a.well_pos.localeCompare(b.well_pos)
  );
  const sig = `${wells.length}:${sorted.slice(0, 10).map(w => w.well_pos).join(',')}`;
  // Simple string hash (not crypto, just for tracking)
  let hash = 0;
  for (let i = 0; i < sig.length; i++) {
    hash = ((hash << 5) - hash) + sig.charCodeAt(i);
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16);
}
