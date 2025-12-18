/**
 * Invariant: Empty Wells Exactly Exclusions
 *
 * Boring and brutal checks:
 * 1. No excluded wells are used
 * 2. All non-excluded wells are present
 * 3. No position appears twice
 *
 * This is the "no ghosts, no duplicates" invariant.
 */

import type { Well, Violation } from './types';

export interface PlateCapacityConfig {
  plateFormat: 96 | 384;
  excludedWells: Set<string>;
}

export const PHASE0_V2_CAPACITY_CONFIG: PlateCapacityConfig = {
  plateFormat: 96,
  excludedWells: new Set(['A01', 'A06', 'A07', 'A12', 'H01', 'H06', 'H07', 'H12']),
};

export function inv_empty_wells_exactly_exclusions(
  wells: Well[],
  cfg: PlateCapacityConfig
): Violation[] {
  const violations: Violation[] = [];

  // Compute all positions for this plate format
  const nRows = cfg.plateFormat === 96 ? 8 : 16;
  const nCols = cfg.plateFormat === 96 ? 12 : 24;
  const rows = Array.from({ length: nRows }, (_, i) => String.fromCharCode(65 + i));

  const allPositions = new Set<string>();
  for (const row of rows) {
    for (let col = 1; col <= nCols; col++) {
      allPositions.add(`${row}${col.toString().padStart(2, '0')}`);
    }
  }

  // Expected used positions: all positions minus exclusions
  const expectedUsedPositions = new Set<string>();
  for (const pos of allPositions) {
    if (!cfg.excludedWells.has(pos)) {
      expectedUsedPositions.add(pos);
    }
  }

  // Group wells by plate
  const wellsByPlate = groupBy(wells, (w) => w.plate_id);

  for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
    // Check 1: No excluded wells are used
    for (const well of plateWells) {
      const normalizedPos = normalizePosition(well.well_pos);
      if (cfg.excludedWells.has(normalizedPos)) {
        violations.push({
          type: 'excluded_well_used',
          severity: 'error',
          plateId,
          message: `Plate ${plateId} uses excluded well ${normalizedPos}.`,
          suggestion: 'Regenerate design with correct exclusions.',
          details: { position: normalizedPos },
        });
      }
    }

    // Check 2: All non-excluded wells are present
    const observedPositions = new Set(plateWells.map((w) => normalizePosition(w.well_pos)));

    for (const expectedPos of expectedUsedPositions) {
      if (!observedPositions.has(expectedPos)) {
        violations.push({
          type: 'expected_well_missing',
          severity: 'error',
          plateId,
          message: `Plate ${plateId} missing expected well ${expectedPos}.`,
          suggestion: 'Check for silent dropping or allocation bugs.',
          details: { position: expectedPos },
        });
      }
    }

    // Check 3: No position appears twice
    const positionCounts = new Map<string, number>();
    for (const well of plateWells) {
      const normalizedPos = normalizePosition(well.well_pos);
      positionCounts.set(normalizedPos, (positionCounts.get(normalizedPos) ?? 0) + 1);
    }

    for (const [pos, count] of positionCounts) {
      if (count > 1) {
        violations.push({
          type: 'duplicate_position',
          severity: 'error',
          plateId,
          message: `Plate ${plateId} has position ${pos} duplicated ${count} times.`,
          suggestion: 'Check for allocation bug or data corruption.',
          details: { position: pos, count },
        });
      }
    }
  }

  return violations;
}

/* ---------------- helpers ---------------- */

function normalizePosition(pos: string): string {
  // Normalize "A2" -> "A02", "A02" -> "A02"
  if (!pos || pos.length < 2) return pos;
  const row = pos[0].toUpperCase();
  const col = pos.slice(1);
  return `${row}${col.padStart(2, '0')}`;
}

function groupBy<T>(items: T[], keyFn: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = keyFn(it);
    (out[k] ??= []).push(it);
  }
  return out;
}
