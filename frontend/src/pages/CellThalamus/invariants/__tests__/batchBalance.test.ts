/**
 * Tests for inv_batchBalance
 *
 * Critical: Batch balance prevents confounding.
 * If conditions correlate with batch factors, you cannot separate biology from batch effects.
 */

import { describe, it, expect } from '@jest/globals';
import { inv_batchBalance, PHASE0_V2_BATCH_CONFIG } from '../batchBalance';
import type { Well } from '../types';

describe('inv_batchBalance', () => {
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

  describe('Check 1: Marginal Balance', () => {
    it('should pass when wells perfectly balanced across batch levels', () => {
      const wells: Well[] = [
        // Day 1: 4 wells
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 3 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 3 }),
        // Day 2: 4 wells
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 3 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 1 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 3 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );

      expect(marginalViolations).toHaveLength(0);
    });

    it('should error when batch levels have unequal well counts', () => {
      const wells: Well[] = [
        // Day 1: 6 wells (too many)
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 3 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 3 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 10 }),
        // Day 2: 2 wells (too few)
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 1 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );

      expect(marginalViolations.length).toBeGreaterThan(0);
      expect(marginalViolations[0].severity).toBe('error');
      expect(marginalViolations[0].message).toContain('day');
    });

    it('should check all batch factors independently', () => {
      const wells: Well[] = [
        // Balanced on day, but imbalanced on operator
        makeWell({ day: 1, operator: 'Operator_A', compound: 'tBHQ' }),
        makeWell({ day: 1, operator: 'Operator_A', compound: 'H2O2' }),
        makeWell({ day: 1, operator: 'Operator_A', compound: 'MG132' }),
        makeWell({ day: 1, operator: 'Operator_B', compound: 'tBHQ' }),
        makeWell({ day: 2, operator: 'Operator_A', compound: 'tBHQ' }),
        makeWell({ day: 2, operator: 'Operator_A', compound: 'H2O2' }),
        makeWell({ day: 2, operator: 'Operator_A', compound: 'MG132' }),
        makeWell({ day: 2, operator: 'Operator_B', compound: 'tBHQ' }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const operatorViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance' && v.message.includes('operator')
      );

      expect(operatorViolations.length).toBeGreaterThan(0);
    });
  });

  describe('Check 2: Condition Independence', () => {
    it('should pass when conditions uniformly distributed across batches', () => {
      const wells: Well[] = [
        // tBHQ@10uM appears in both days equally
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
        // H2O2@5uM appears in both days equally
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );

      expect(confoundingViolations).toHaveLength(0);
    });

    it('should warn when condition only appears in one batch level', () => {
      const wells: Well[] = [
        // tBHQ@10uM ONLY in day 1 (100% confounded)
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        // H2O2@5uM ONLY in day 2 (100% confounded)
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );

      expect(confoundingViolations.length).toBeGreaterThan(0);
      expect(confoundingViolations[0].severity).toBe('warning');
      expect(confoundingViolations[0].message).toContain('not uniformly distributed');
    });

    it('should detect partial confounding (skewed distribution)', () => {
      const wells: Well[] = [
        // tBHQ@10uM: 75% in day 1, 25% in day 2 (skewed)
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const confoundingViolations = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.message.includes('tBHQ@10uM')
      );

      expect(confoundingViolations.length).toBeGreaterThan(0);
    });

    it('should check all batch factors for each condition', () => {
      const wells: Well[] = [
        // Balanced on day, confounded on operator
        makeWell({
          day: 1,
          operator: 'Operator_A',
          compound: 'tBHQ',
          dose_uM: 10,
        }),
        makeWell({
          day: 2,
          operator: 'Operator_A',
          compound: 'tBHQ',
          dose_uM: 10,
        }),
        makeWell({
          day: 1,
          operator: 'Operator_A',
          compound: 'tBHQ',
          dose_uM: 10,
        }),
        makeWell({
          day: 2,
          operator: 'Operator_A',
          compound: 'tBHQ',
          dose_uM: 10,
        }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const operatorConfounding = violations.filter(
        (v) =>
          v.type === 'batch_condition_confounding' &&
          v.message.includes('operator')
      );

      expect(operatorConfounding.length).toBeGreaterThan(0);
    });
  });

  describe('Check 3: Chi-Square Test', () => {
    it('should pass when conditions independent of batch factors', () => {
      // Create perfectly balanced design: 2 conditions × 2 days × 2 replicates
      const wells: Well[] = [
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 1, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );

      expect(chiSquareViolations).toHaveLength(0);
    });

    it('should warn when significant dependence detected', () => {
      // Create strongly dependent design: each condition only in one day
      const wells: Well[] = [
        // All tBHQ in day 1
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 1 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 3 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 30 }),
        // All H2O2 in day 2
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 1 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 3 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'H2O2', dose_uM: 30 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const chiSquareViolations = violations.filter(
        (v) => v.type === 'batch_condition_dependence'
      );

      expect(chiSquareViolations.length).toBeGreaterThan(0);
      expect(chiSquareViolations[0].severity).toBe('warning');
      expect(chiSquareViolations[0].message).toContain('χ²=');
      expect(chiSquareViolations[0].details?.pValue).toBeDefined();
    });
  });

  describe('Edge Cases', () => {
    it('should skip sentinels (only check experimental wells)', () => {
      const wells: Well[] = [
        // Imbalanced sentinels should be ignored
        makeWell({ day: 1, is_sentinel: true, sentinel_type: 'DMSO' }),
        makeWell({ day: 1, is_sentinel: true, sentinel_type: 'DMSO' }),
        makeWell({ day: 1, is_sentinel: true, sentinel_type: 'DMSO' }),
        makeWell({ day: 2, is_sentinel: true, sentinel_type: 'DMSO' }),
        // Balanced experimental wells should pass
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );

      // Should not complain about imbalanced sentinels
      expect(marginalViolations).toHaveLength(0);
    });

    it('should handle zero experimental wells gracefully', () => {
      const wells: Well[] = [
        makeWell({ is_sentinel: true, sentinel_type: 'DMSO' }),
        makeWell({ is_sentinel: true, sentinel_type: 'tBHQ' }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      expect(violations).toHaveLength(0);
    });

    it('should handle undefined batch factor values', () => {
      const wells: Well[] = [
        makeWell({ day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: undefined, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ day: 2, compound: 'tBHQ', dose_uM: 10 }),
      ];

      // Should not crash, may warn about undefined level
      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);
      expect(violations).toBeDefined();
    });
  });

  describe('Multi-Plate Scenarios', () => {
    it('should check batch balance across all plates', () => {
      const wells: Well[] = [
        // Plate 1: all day 1
        makeWell({ plate_id: 'plate1', day: 1, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate1', day: 1, compound: 'H2O2', dose_uM: 5 }),
        // Plate 2: all day 2
        makeWell({ plate_id: 'plate2', day: 2, compound: 'tBHQ', dose_uM: 10 }),
        makeWell({ plate_id: 'plate2', day: 2, compound: 'H2O2', dose_uM: 5 }),
      ];

      const violations = inv_batchBalance(wells, PHASE0_V2_BATCH_CONFIG);

      // Should pass marginal balance (2 wells per day)
      const marginalViolations = violations.filter(
        (v) => v.type === 'batch_marginal_imbalance'
      );
      expect(marginalViolations).toHaveLength(0);

      // Should pass condition balance (each condition in both days)
      const confoundingViolations = violations.filter(
        (v) => v.type === 'batch_condition_confounding'
      );
      expect(confoundingViolations).toHaveLength(0);
    });
  });
});
