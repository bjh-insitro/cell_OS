/**
 * Tests for inv_sentinelsPlacedCorrectly
 *
 * These tests document expected behavior for Phase 0 founder designs
 * and catch regressions in sentinel placement logic.
 */

import { inv_sentinelsPlacedCorrectly, PHASE0_V2_SENTINEL_CONFIG } from '../sentinelPlacement';
import type { Well } from '../types';

describe('inv_sentinelsPlacedCorrectly', () => {
  describe('Phase 0 v2 configuration', () => {
    it('should have correct expected counts for v2', () => {
      expect(PHASE0_V2_SENTINEL_CONFIG.expectedCountsByType).toEqual({
        'dmso': 8,
        'tbhq': 5,
        'thapsigargin': 5,
        'oligomycin': 5,
        'mg132': 5,
      });
    });

    it('should total 28 sentinels per plate', () => {
      const total = Object.values(PHASE0_V2_SENTINEL_CONFIG.expectedCountsByType)
        .reduce((a, b) => a + b, 0);
      expect(total).toBe(28);
    });

    it('should have tight distribution constraints for max identifiability', () => {
      expect(PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel).toBe(8);
      expect(PHASE0_V2_SENTINEL_CONFIG.windowSize).toBe(12);
      expect(PHASE0_V2_SENTINEL_CONFIG.windowMinSentinels).toBe(2);
      expect(PHASE0_V2_SENTINEL_CONFIG.windowMaxSentinels).toBe(6);
    });
  });

  describe('Count exactness (error level)', () => {
    it('should error if sentinel counts do not match exactly', () => {
      const wells: Well[] = [
        ...createSentinels('plate1', 'dmso', 7),  // Wrong: should be 8
        ...createSentinels('plate1', 'tbhq', 5),
        ...createSentinels('plate1', 'thapsigargin', 5),
        ...createSentinels('plate1', 'oligomycin', 5),
        ...createSentinels('plate1', 'mg132', 5),
        ...createExperimental('plate1', 60),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const countErrors = violations.filter(v => v.type === 'sentinel_count_mismatch');
      expect(countErrors.length).toBeGreaterThan(0);
      expect(countErrors[0].severity).toBe('error');
      expect(countErrors[0].message).toContain('expected 8 dmso sentinels, got 7');
    });

    it('should pass if all sentinel counts are exact', () => {
      const wells: Well[] = [
        ...createSentinels('plate1', 'dmso', 8),
        ...createSentinels('plate1', 'tbhq', 5),
        ...createSentinels('plate1', 'thapsigargin', 5),
        ...createSentinels('plate1', 'oligomycin', 5),
        ...createSentinels('plate1', 'mg132', 5),
        ...createExperimental('plate1', 60),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const countErrors = violations.filter(v => v.type === 'sentinel_count_mismatch');
      expect(countErrors.length).toBe(0);
    });

    it('should error if no sentinels present', () => {
      const wells: Well[] = createExperimental('plate1', 88);

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const noSentinelErrors = violations.filter(v => v.type === 'no_sentinels');
      expect(noSentinelErrors.length).toBe(1);
      expect(noSentinelErrors[0].severity).toBe('error');
    });
  });

  describe('Max gap constraint (warning level)', () => {
    it('should warn if non-sentinel run exceeds maxGapNonSentinel', () => {
      // Create wells with all sentinels grouped at start (bad)
      const wells: Well[] = [
        ...createSentinelsAtPositions('plate1', 'dmso', [0, 1, 2, 3, 4, 5, 6, 7]),
        ...createSentinelsAtPositions('plate1', 'tbhq', [8, 9, 10, 11, 12]),
        ...createSentinelsAtPositions('plate1', 'thapsigargin', [13, 14, 15, 16, 17]),
        ...createSentinelsAtPositions('plate1', 'oligomycin', [18, 19, 20, 21, 22]),
        ...createSentinelsAtPositions('plate1', 'mg132', [23, 24, 25, 26, 27]),
        ...createExperimentalAtPositions('plate1', Array.from({length: 60}, (_, i) => i + 28)),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const gapWarnings = violations.filter(v => v.type === 'sentinel_max_gap_exceeded');
      expect(gapWarnings.length).toBeGreaterThan(0);
      expect(gapWarnings[0].severity).toBe('warning');
      expect(gapWarnings[0].details?.maxGap).toBeGreaterThan(PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel);
    });

    it('should pass if sentinels are evenly interspersed', () => {
      // Intersperse sentinels evenly (every ~3 wells)
      const wells = createInterspersedDesign('plate1', 28, 60, 3);

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const gapWarnings = violations.filter(v => v.type === 'sentinel_max_gap_exceeded');
      expect(gapWarnings.length).toBe(0);
    });
  });

  describe('Windowing constraint (warning level)', () => {
    it('should warn if any window violates min/max sentinel density', () => {
      // Create design with uneven distribution
      const wells: Well[] = [
        // First window: too many sentinels (12 sentinels in window of 12)
        ...createSentinelsAtPositions('plate1', 'dmso', [0, 1, 2, 3, 4, 5, 6, 7]),
        ...createSentinelsAtPositions('plate1', 'tbhq', [8, 9, 10, 11]),
        // Rest: too few sentinels
        ...createSentinelsAtPositions('plate1', 'tbhq', [12]),
        ...createSentinelsAtPositions('plate1', 'thapsigargin', [40, 41, 42, 43, 44]),
        ...createSentinelsAtPositions('plate1', 'oligomycin', [45, 46, 47, 48, 49]),
        ...createSentinelsAtPositions('plate1', 'mg132', [50, 51, 52, 53, 54]),
        ...createExperimentalAtPositions('plate1', Array.from({length: 33}, (_, i) => i + 13).filter(i => i < 40 || i >= 55)),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const windowWarnings = violations.filter(v => v.type === 'sentinel_window_density');
      expect(windowWarnings.length).toBeGreaterThan(0);
      expect(windowWarnings[0].severity).toBe('warning');
    });
  });

  describe('Same-type clumping (warning level)', () => {
    it('should warn if same sentinel type appears too close too often', () => {
      // Put all DMSO sentinels consecutively (bad)
      const wells: Well[] = [
        ...createSentinelsAtPositions('plate1', 'dmso', [0, 1, 2, 3, 4, 5, 6, 7]),  // All consecutive
        ...createInterspersedSentinels('plate1', 'tbhq', 5, 10, 8),
        ...createInterspersedSentinels('plate1', 'thapsigargin', 5, 10, 23),
        ...createInterspersedSentinels('plate1', 'oligomycin', 5, 10, 38),
        ...createInterspersedSentinels('plate1', 'mg132', 5, 10, 53),
        ...createExperimentalAtPositions('plate1', Array.from({length: 60}, (_, i) => i + 8).filter(i => ![8,18,23,33,38,48,53,63,68,78].includes(i))),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const clumpWarnings = violations.filter(v => v.type === 'sentinel_type_clumping');
      expect(clumpWarnings.length).toBeGreaterThan(0);
      expect(clumpWarnings[0].severity).toBe('warning');
      expect(clumpWarnings[0].details?.type).toBe('dmso');
    });
  });

  describe('Gap variance (warning level)', () => {
    it('should warn if sentinel spacing has high coefficient of variation', () => {
      // Create very uneven spacing
      const wells: Well[] = [
        // Cluster of sentinels
        ...createSentinelsAtPositions('plate1', 'dmso', [0, 1, 2, 3, 4, 5, 6, 7]),
        ...createSentinelsAtPositions('plate1', 'tbhq', [8, 9, 10, 11, 12]),
        // Big gap
        ...createExperimentalAtPositions('plate1', Array.from({length: 30}, (_, i) => i + 13)),
        // Another cluster
        ...createSentinelsAtPositions('plate1', 'thapsigargin', [43, 44, 45, 46, 47]),
        ...createSentinelsAtPositions('plate1', 'oligomycin', [48, 49, 50, 51, 52]),
        ...createSentinelsAtPositions('plate1', 'mg132', [53, 54, 55, 56, 57]),
        ...createExperimentalAtPositions('plate1', Array.from({length: 30}, (_, i) => i + 58)),
      ];

      const violations = inv_sentinelsPlacedCorrectly(wells, PHASE0_V2_SENTINEL_CONFIG);

      const cvWarnings = violations.filter(v => v.type === 'sentinel_gap_high_variance');
      expect(cvWarnings.length).toBeGreaterThan(0);
      expect(cvWarnings[0].severity).toBe('warning');
      expect(cvWarnings[0].details?.cv).toBeGreaterThan(0.9);
    });
  });

  describe('Multi-plate designs', () => {
    it('should validate each plate independently', () => {
      const plate1Good = createInterspersedDesign('plate1', 28, 60, 3);
      const plate2Bad: Well[] = [
        // Missing sentinels
        ...createSentinels('plate2', 'dmso', 4),  // Wrong: should be 8
        ...createExperimental('plate2', 84),
      ];

      const violations = inv_sentinelsPlacedCorrectly(
        [...plate1Good, ...plate2Bad],
        PHASE0_V2_SENTINEL_CONFIG
      );

      // Plate 1 should pass count check
      const plate1Errors = violations.filter(v => v.plateId === 'plate1' && v.type === 'sentinel_count_mismatch');
      expect(plate1Errors.length).toBe(0);

      // Plate 2 should fail count check
      const plate2Errors = violations.filter(v => v.plateId === 'plate2' && v.type === 'sentinel_count_mismatch');
      expect(plate2Errors.length).toBeGreaterThan(0);
    });
  });
});

/* ============ Test helpers ============ */

function createSentinels(plateId: string, type: string, count: number): Well[] {
  return Array.from({ length: count }, (_, i) => ({
    plate_id: plateId,
    well_pos: indexToPosition(i, 96),
    cell_line: 'A549',
    compound: type.toUpperCase(),
    dose_uM: 0,
    is_sentinel: true,
    sentinel_type: type,
  }));
}

function createSentinelsAtPositions(plateId: string, type: string, positions: number[]): Well[] {
  return positions.map(pos => ({
    plate_id: plateId,
    well_pos: indexToPosition(pos, 96),
    cell_line: 'A549',
    compound: type.toUpperCase(),
    dose_uM: 0,
    is_sentinel: true,
    sentinel_type: type,
  }));
}

function createInterspersedSentinels(plateId: string, type: string, count: number, spacing: number, offset: number): Well[] {
  return Array.from({ length: count }, (_, i) => ({
    plate_id: plateId,
    well_pos: indexToPosition(offset + i * spacing, 96),
    cell_line: 'A549',
    compound: type.toUpperCase(),
    dose_uM: 0,
    is_sentinel: true,
    sentinel_type: type,
  }));
}

function createExperimental(plateId: string, count: number): Well[] {
  return Array.from({ length: count }, (_, i) => ({
    plate_id: plateId,
    well_pos: indexToPosition(i + 28, 96),  // Start after sentinels
    cell_line: 'A549',
    compound: 'Compound_X',
    dose_uM: 1.0,
    is_sentinel: false,
  }));
}

function createExperimentalAtPositions(plateId: string, positions: number[]): Well[] {
  return positions.map(pos => ({
    plate_id: plateId,
    well_pos: indexToPosition(pos, 96),
    cell_line: 'A549',
    compound: 'Compound_X',
    dose_uM: 1.0,
    is_sentinel: false,
  }));
}

function createInterspersedDesign(plateId: string, nSentinels: number, nExperimental: number, spacing: number): Well[] {
  const wells: Well[] = [];
  const totalWells = nSentinels + nExperimental;
  const sentinelTypes = ['dmso', 'tbhq', 'thapsigargin', 'oligomycin', 'mg132'];
  const sentinelCounts = [8, 5, 5, 5, 5];

  let sentinelTypeIdx = 0;
  let sentinelCountInType = 0;
  let sentinelsSoFar = 0;
  let experimentalSoFar = 0;

  for (let i = 0; i < totalWells; i++) {
    // Intersperse: place sentinel every `spacing` wells
    const shouldPlaceSentinel = sentinelsSoFar < nSentinels && (i % spacing === 0 || experimentalSoFar >= nExperimental);

    if (shouldPlaceSentinel) {
      // Find next sentinel type that still has count remaining
      while (sentinelTypeIdx < sentinelTypes.length && sentinelCountInType >= sentinelCounts[sentinelTypeIdx]) {
        sentinelTypeIdx++;
        sentinelCountInType = 0;
      }

      if (sentinelTypeIdx < sentinelTypes.length) {
        wells.push({
          plate_id: plateId,
          well_pos: indexToPosition(i, 96),
          cell_line: 'A549',
          compound: sentinelTypes[sentinelTypeIdx].toUpperCase(),
          dose_uM: 0,
          is_sentinel: true,
          sentinel_type: sentinelTypes[sentinelTypeIdx],
        });
        sentinelCountInType++;
        sentinelsSoFar++;
      }
    } else {
      wells.push({
        plate_id: plateId,
        well_pos: indexToPosition(i, 96),
        cell_line: 'A549',
        compound: 'Compound_X',
        dose_uM: 1.0,
        is_sentinel: false,
      });
      experimentalSoFar++;
    }
  }

  return wells;
}

function indexToPosition(idx: number, plateFormat: 96 | 384): string {
  const nCols = plateFormat === 96 ? 12 : 24;
  const row = String.fromCharCode(65 + Math.floor(idx / nCols));
  const col = (idx % nCols) + 1;
  return `${row}${String(col).padStart(2, '0')}`;
}
