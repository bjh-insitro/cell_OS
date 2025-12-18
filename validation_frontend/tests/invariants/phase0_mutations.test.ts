/**
 * Systematic mutation tests for Phase 0 invariants
 *
 * Strategy: Apply deterministic "evil edits" to golden fixture and verify
 * that invariants catch them. High failure mode coverage, not exhaustive.
 */

import { describe, test, expect, beforeAll } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { checkPhase0V2Design } from '../../src/pages/CellThalamus/invariants/index';
import type { DesignWithMetadata } from './mutators';
import * as mutators from './mutators';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let goldenDesign: DesignWithMetadata;

beforeAll(() => {
  // Load golden fixture (known-good Phase0_v2 design)
  const designPath = path.join(__dirname, '../../../data/designs/phase0_founder_v2_regenerated.json');
  const designData = JSON.parse(fs.readFileSync(designPath, 'utf-8'));
  goldenDesign = {
    wells: designData.wells,
    metadata: designData.metadata,
  };

  // Sanity check: golden should have zero violations
  const certificate = checkPhase0V2Design(goldenDesign.wells, goldenDesign.metadata);
  expect(certificate.violations.length).toBe(0);
});

describe('Phase 0 Invariant Mutations', () => {
  /**
   * Table-driven mutation tests
   *
   * Each row: [mutation function, expected violation types]
   */
  const mutationTests: Array<{
    name: string;
    mutator: (design: DesignWithMetadata) => DesignWithMetadata;
    expectOneOf: string[]; // At least one of these violation types should be present
  }> = [
    {
      name: 'missing policy',
      mutator: mutators.mut_missing_policy,
      expectOneOf: ['sentinel_policy_missing'],
    },
    {
      name: 'wrong policy',
      mutator: mutators.mut_wrong_policy,
      expectOneOf: ['sentinel_policy_unsupported'],
    },
    {
      name: 'missing scaffold hash',
      mutator: mutators.mut_missing_scaffold_hash,
      expectOneOf: ['scaffold_metadata_missing_hash'],
    },
    {
      name: 'wrong scaffold hash',
      mutator: mutators.mut_wrong_scaffold_hash,
      expectOneOf: ['scaffold_metadata_hash_mismatch'],
    },
    {
      name: 'tamper sentinel compound',
      mutator: mutators.mut_tamper_one_sentinel_compound,
      expectOneOf: [
        'scaffold_well_derived_hash_mismatch',
        'scaffold_undocumented',
        'scaffold_metadata_missing_hash',
      ],
    },
    {
      name: 'tamper sentinel dose',
      mutator: mutators.mut_tamper_one_sentinel_dose,
      expectOneOf: [
        'scaffold_well_derived_hash_mismatch',
        'scaffold_undocumented',
        'scaffold_metadata_missing_hash',
      ],
    },
    {
      name: 'tamper sentinel type',
      mutator: mutators.mut_tamper_one_sentinel_type,
      expectOneOf: ['scaffold_type_mismatch', 'scaffold_well_derived_hash_mismatch'],
    },
    {
      name: 'swap sentinel positions',
      mutator: mutators.mut_swap_two_sentinel_positions_within_plate,
      expectOneOf: [
        'scaffold_type_mismatch',
        'scaffold_stability_mismatch',
        'scaffold_position_unexpected',
        'scaffold_position_missing',
      ],
    },
    {
      name: 'remove sentinel from first plate',
      mutator: mutators.mut_remove_one_sentinel_from_first_plate,
      expectOneOf: ['scaffold_count_mismatch', 'scaffold_position_missing'],
    },
    {
      name: 'diverge scaffold on second plate',
      mutator: mutators.mut_diverge_scaffold_on_second_plate,
      expectOneOf: ['scaffold_stability_mismatch', 'scaffold_stability_count'],
    },
    {
      name: 'add duplicate well',
      mutator: mutators.mut_add_duplicate_well,
      expectOneOf: [
        'duplicate_position',
        'scaffold_count_mismatch',
        'scaffold_stability_count',
      ],
    },
    {
      name: 'add well in excluded corner',
      mutator: mutators.mut_add_well_in_excluded_corner,
      expectOneOf: ['excluded_well_used', 'condition_multiset_mismatch'],
    },
    {
      name: 'remove experimental condition from one timepoint',
      mutator: mutators.mut_remove_experimental_condition_from_one_timepoint,
      expectOneOf: ['expected_well_missing', 'condition_multiset_mismatch'],
    },
    {
      name: 'change compound for experimental position',
      mutator: mutators.mut_change_compound_for_experimental_position,
      expectOneOf: ['experimental_position_instability', 'condition_multiset_mismatch'],
    },
    {
      name: 'change dose for experimental position',
      mutator: mutators.mut_change_dose_for_experimental_position,
      expectOneOf: ['experimental_position_instability', 'condition_multiset_mismatch'],
    },
    {
      name: 'cluster sentinels in corner',
      mutator: mutators.mut_cluster_sentinels_in_corner,
      expectOneOf: [
        'sentinel_placement_quality',
        'sentinel_spatial_distribution',
        'scaffold_position_unexpected',
        'scaffold_position_missing',
      ],
    },
    {
      name: 'unbalance batch operator',
      mutator: mutators.mut_unbalance_batch_operator,
      expectOneOf: [
        'batch_marginal_imbalance',
        'batch_condition_confounding',
        'batch_separate_factor_violation',
      ],
    },
    {
      name: 'unbalance batch cell line',
      mutator: mutators.mut_unbalance_batch_cell_line,
      expectOneOf: [
        'batch_marginal_imbalance',
        'batch_condition_confounding',
        'batch_separate_factor_violation',
        'condition_multiset_mismatch',
        'experimental_position_instability',
      ],
    },
  ];

  mutationTests.forEach(({ name, mutator, expectOneOf }) => {
    test(`mutation: ${name}`, () => {
      const mutated = mutator(goldenDesign);
      const certificate = checkPhase0V2Design(mutated.wells, mutated.metadata);

      // Should have at least one violation
      expect(certificate.violations.length).toBeGreaterThan(0);

      // Should have at least one of the expected violation types
      const violationTypes = certificate.violations.map((v) => v.type);
      const hasExpectedType = expectOneOf.some((expectedType) => violationTypes.includes(expectedType));

      if (!hasExpectedType) {
        console.error(`Expected one of: ${expectOneOf.join(', ')}`);
        console.error(`Got: ${violationTypes.join(', ')}`);
      }

      expect(hasExpectedType).toBe(true);
    });
  });
});

describe('Golden Design Regression', () => {
  test('golden design should have zero violations', () => {
    const certificate = checkPhase0V2Design(goldenDesign.wells, goldenDesign.metadata);

    if (certificate.violations.length > 0) {
      console.error('Golden design has violations:');
      certificate.violations.forEach((v) => {
        console.error(`  - ${v.type}: ${v.message}`);
      });
    }

    expect(certificate.violations).toEqual([]);
  });

  test('golden design should have correct stats', () => {
    const certificate = checkPhase0V2Design(goldenDesign.wells, goldenDesign.metadata);

    expect(certificate.stats.nPlates).toBe(24);
    expect(certificate.stats.totalWells).toBe(2112); // 24 plates * 88 wells
    expect(certificate.stats.sentinelWells).toBe(672); // 24 plates * 28 sentinels
    expect(certificate.stats.experimentalWells).toBe(1440); // 24 plates * 60 experimental
  });

  test('golden design should have matching scaffold hash', () => {
    const certificate = checkPhase0V2Design(goldenDesign.wells, goldenDesign.metadata);

    expect(certificate.scaffoldMetadata?.expected.scaffoldHash).toBe('901ffeb4603019fe');
    expect(certificate.scaffoldMetadata?.observed?.scaffoldHash).toBe('901ffeb4603019fe');
    expect(certificate.scaffoldMetadata?.observed?.wellDerivedHash).toBe('901ffeb4603019fe');
    expect(certificate.scaffoldMetadata?.observed?.wellDerivedMatchesExpected).toBe(true);
  });
});
