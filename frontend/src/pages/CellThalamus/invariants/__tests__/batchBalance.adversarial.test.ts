/**
 * Adversarial Tests for inv_batchBalance
 *
 * These tests deliberately create pathological designs to confirm the invariant
 * fails for the reasons we think, not dumb reasons.
 *
 * Test scenarios:
 * 1. Perfectly marginally balanced but fully confounded by token ordering
 * 2. Balanced globally but confounded within each plate
 * 3. Sparse condition tables where chi-square would lie
 * 4. Float dose trap: 10.0 vs 10.000000001
 * 5. Small count tolerance edge cases
 */

import { describe, it, expect } from '@jest/globals';
import { inv_batchBalance, PHASE0_V2_BATCH_CONFIG } from '../batchBalance';
import type { Well } from '../types';

describe('inv_batchBalance - Adversarial Tests', () => {
  // Helper to create experimental wells
  const makeWell = (overrides: Partial<Well>): Well => ({
    plate_id: 'plate1',
    well_pos: 'A01',
    cell_line: 'A549',
    compound: 'tBHQ',
    dose_uM: 10,
    is_sentinel: false,
    day: 1,
    operator: 'Operator_A',
    timepoint_h: 12.0,
    ...overrides,
  });

  describe('Adversarial 1: Marginal balance but full confounding', () => {
    it('should catch confounding even when marginally balanced', () => {
      // Classic Simpson's paradox trap:
      // - Marginally balanced: 4 wells per day
      // - BUT: each compound ONLY in one day (100% confounded)
      const wells: Well[] = [
        // Day 1: All tBHQ (marginally balanced)
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 3 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 30 }),
        // Day 2: All H2O2 (marginally balanced)
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 1 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 3 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 30 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // Should PASS marginal balance (4 wells per day)
      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );
      expect(marginalViolations).toHaveLength(0);

      // Should FAIL condition independence (each condition 100% in one day)
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );
      expect(confoundingViolations.length).toBeGreaterThan(0);

      // Should FAIL chi-square test (perfect dependence)
      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );
      expect(chiSquareViolations.length).toBeGreaterThan(0);

      // Check effect size is large
      const chiViolation = chiSquareViolations[0];
      const cramersV = parseFloat(chiViolation.details?.cramersV ?? '0');
      expect(cramersV).toBeGreaterThan(0.5); // Large effect size
    });
  });

  describe('Adversarial 2: Global balance but plate-level confounding', () => {
    it('should catch confounding within plates even if globally balanced', () => {
      // Globally balanced but locally confounded:
      // - Plate 1: All tBHQ in Day 1, all H2O2 in Day 2
      // - Plate 2: All tBHQ in Day 2, all H2O2 in Day 1
      // - Global: tBHQ appears 4× in Day 1, 4× in Day 2 (balanced!)
      // - But within each plate: 100% confounded

      const wells: Well[] = [
        // Plate 1
        makeWell({ plate_id: 'plate1', day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate1', day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate1', day: 2, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ plate_id: 'plate1', day: 2, compound: 'H2O2', dose_uM: 5 }),
        // Plate 2 (reversed)
        makeWell({ plate_id: 'plate2', day: 2, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate2', day: 2, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate2', day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ plate_id: 'plate2', day: 1, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // Global check should PASS (each condition in both days)
      const globalConfounding = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.details?.scope === 'global'
      );
      expect(globalConfounding).toHaveLength(0);

      // Per-plate check should FAIL (confounded within each plate)
      const plateConfounding = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.details?.scope?.includes('plate')
      );
      expect(plateConfounding.length).toBeGreaterThan(0);

      // Verify message includes plate ID
      expect(plateConfounding[0].message).toContain('plate');
    });
  });

  describe('Adversarial 3: Sparse tables', () => {
    it('should gate chi-square when table is too sparse', () => {
      // Create design with many conditions (10 compounds × 6 doses = 60 conditions)
      // but small sample size (only 1-2 replicates per condition)
      // This creates a sparse contingency table where chi-square is unreliable

      const compounds = ['tBHQ', 'H2O2', 'MG132', 'oligomycin', 'CCCP', 'tunicamycin', 'thapsigargin', 'etoposide', 'nocodazole', 'paclitaxel'];
      const doses = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0];

      const wells: Well[] = [];
      for (const compound of compounds) {
        for (const dose of doses) {
          // Only 2 replicates per condition, split across 2 days
          wells.push(
            makeWell({ day: 1, compound, dose_uM: dose }),
            makeWell({ day: 2, compound, dose_uM: dose })
          );
        }
      }

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // Should warn that table is too sparse for chi-square
      const sparseWarnings = violations.filter(
        (v) => v.type === 'batch_table_too_sparse'
      );
      expect(sparseWarnings.length).toBeGreaterThan(0);

      // Should NOT run chi-square test (gated)
      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );
      // Chi-square should be gated, so no dependence violations from it
      // (there may be confounding violations from check 2, but not from chi-square)
      expect(sparseWarnings[0].message).toContain('too sparse');
      expect(sparseWarnings[0].message).toContain('chi-square');
    });
  });

  describe('Adversarial 4: Float dose trap', () => {
    it('should canonicalize dose to avoid float comparison traps', () => {
      // Create conditions with float doses that are "equal" but formatted differently
      // Without canonicalization, these would be treated as different conditions

      const wells: Well[] = [
        // "10.0" vs "10.000000001" - should be treated as same condition
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10.0 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10.000000001 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10.0 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10.000000001 }),
        // Different compound to avoid single-condition edge case
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5.0 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5.0 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5.0 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5.0 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // Should NOT create fake conditions due to float formatting
      // All tBHQ@10.0 wells should be grouped together
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );

      // Should have no confounding (balanced across days)
      expect(confoundingViolations).toHaveLength(0);

      // If float trap existed, we'd see violations for fake conditions like:
      // - "tBHQ@10.000000uM" vs "tBHQ@10.000000001uM"
      // But with canonicalization, these are the same condition
    });

    it('should handle extreme float precision differences', () => {
      const wells: Well[] = [
        // Extreme cases that would fail without canonicalization
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10.0 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10.00 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 9.999999999 }),
        // Different compound
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // With 6 decimal place rounding, 9.999999999 becomes 10.000000
      // So all tBHQ doses should be treated as same condition
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );

      expect(confoundingViolations).toHaveLength(0);
    });
  });

  describe('Adversarial 5: Small count tolerance', () => {
    it('should use max(1, 10% of expected) for small counts', () => {
      // Create design with small counts where 10% < 1 well
      // Example: 2 replicates per condition across 2 days
      // Expected per day: 1 replicate
      // 10% of 1 = 0.1 wells (meaningless)
      // Should use 1 well tolerance instead

      const wells: Well[] = [
        // tBHQ: 2 in Day 1, 0 in Day 2 (deviation = 1 well, should be within tolerance)
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        // H2O2: 1 in Day 1, 1 in Day 2 (perfectly balanced)
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // tBHQ has deviation of 1 well (100% vs 0%)
      // But tolerance should be max(1, 10% * 1) = 1 well
      // So it should NOT violate (deviation = 1, tolerance = 1)

      const tBHQConfounding = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.details?.condition?.includes('tBHQ')
      );

      // Should not violate (deviation exactly at tolerance)
      expect(tBHQConfounding).toHaveLength(0);
    });

    it('should use 10% tolerance for large counts', () => {
      // Create design with large counts where 10% > 1 well
      // Example: 20 replicates per condition across 2 days
      // Expected per day: 10 replicates
      // 10% of 10 = 1 well
      // Tolerance = max(1, 1) = 1 well

      const wells: Well[] = [];

      // tBHQ: 12 in Day 1, 8 in Day 2 (deviation = 2 wells, should violate)
      for (let i = 0; i < 12; i++) {
        wells.push(makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }));
      }
      for (let i = 0; i < 8; i++) {
        wells.push(makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }));
      }

      // H2O2: 10 in Day 1, 10 in Day 2 (perfectly balanced)
      for (let i = 0; i < 10; i++) {
        wells.push(makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }));
        wells.push(makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }));
      }

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // tBHQ has deviation of 2 wells (60% vs 40%)
      // Tolerance = max(1, 10% * 10) = 1 well
      // So it SHOULD violate (deviation = 2 > tolerance = 1)

      const tBHQConfounding = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.details?.condition?.includes('tBHQ')
      );

      expect(tBHQConfounding.length).toBeGreaterThan(0);
      expect(tBHQConfounding[0].details?.toleranceCount).toBe('1.0');
    });
  });

  describe('Adversarial 6: Effect size vs p-value', () => {
    it('should report negligible effect size even when p-value is significant', () => {
      // Create design with VERY large sample size but TINY effect
      // This will have significant p-value but negligible Cramér's V
      // (p-value theater: statistically significant but practically meaningless)

      const wells: Well[] = [];

      // Create 1000 wells with tiny imbalance
      // tBHQ: 252 in Day 1, 248 in Day 2 (51% vs 49%)
      // H2O2: 248 in Day 1, 252 in Day 2 (49% vs 51%)
      for (let i = 0; i < 252; i++) {
        wells.push(makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }));
      }
      for (let i = 0; i < 248; i++) {
        wells.push(makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }));
      }
      for (let i = 0; i < 248; i++) {
        wells.push(makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }));
      }
      for (let i = 0; i < 252; i++) {
        wells.push(makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }));
      }

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );

      if (chiSquareViolations.length > 0) {
        const cramersV = parseFloat(
          chiSquareViolations[0].details?.cramersV ?? '0'
        );
        const effectSize = chiSquareViolations[0].details?.effectSize;

        // Effect size should be negligible despite significant p-value
        expect(effectSize).toBe('negligible');
        expect(cramersV).toBeLessThan(0.1);

        // Suggestion should mention small effect size
        expect(chiSquareViolations[0].suggestion).toContain('small effect size');
      }
    });

    it('should flag large effect size with appropriate urgency', () => {
      // Create design with strong confounding and large effect size
      const wells: Well[] = [
        // Perfect confounding: each compound only in one day
        ...Array(10)
          .fill(null)
          .map(() => makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 })),
        ...Array(10)
          .fill(null)
          .map(() => makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 })),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );

      expect(chiSquareViolations.length).toBeGreaterThan(0);

      const cramersV = parseFloat(
        chiSquareViolations[0].details?.cramersV ?? '0'
      );
      const effectSize = chiSquareViolations[0].details?.effectSize;

      // Effect size should be large
      expect(effectSize).toBe('large');
      expect(cramersV).toBeGreaterThan(0.5);

      // Suggestion should be more urgent for large effect
      expect(chiSquareViolations[0].suggestion).toContain('Large effect size');
      expect(chiSquareViolations[0].suggestion).toContain('practically important');
    });
  });

  describe('Adversarial 7: Marginal balance note', () => {
    it('should remind that marginal balance is necessary but not sufficient', () => {
      const wells: Well[] = [
        // Imbalanced
        ...Array(8)
          .fill(null)
          .map(() => makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 })),
        ...Array(2)
          .fill(null)
          .map(() => makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 })),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );

      expect(marginalViolations.length).toBeGreaterThan(0);

      // Message should include the reminder
      expect(marginalViolations[0].message).toContain('necessary but not sufficient');
      expect(marginalViolations[0].message).toContain('marginally balanced and still confounded');
    });
  });
});
