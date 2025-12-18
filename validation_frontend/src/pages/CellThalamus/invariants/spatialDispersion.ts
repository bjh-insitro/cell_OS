/**
 * Invariant: Spatial Dispersion (Anti-Clumping)
 *
 * Ensures experimental wells are spatially scattered, not clustered.
 * This prevents spatial confounding from gradients (temperature, evaporation, edge effects).
 *
 * Sequential fill creates tight clusters (e.g., all tunicamycin in first 12 positions).
 * Randomized positions should scatter compounds across the plate.
 *
 * Check: For each compound on each plate, compute bounding box area (rows × cols).
 * Fail if area is too small (indicates clustering).
 */

import type { Well, Violation } from './types';

export interface SpatialDispersionConfig {
  minBoundingBoxArea: number; // Minimum area for compounds to span
  minRowSpan: number; // Minimum rows a compound should span
  minColSpan: number; // Minimum cols a compound should span
}

/**
 * Phase 0 v2 spatial dispersion thresholds
 *
 * Design: 12 wells per compound (6 doses × 2 replicates) on 8×12 plate (60 experimental wells)
 *
 * Expected values:
 * - Sequential fill: rows≈2, cols≈6, area≈12 (tightly packed)
 * - Random scatter: rows≈5-7, cols≈8-11, area≈50-80 (spread out)
 *
 * Thresholds (conservative to avoid false positives from natural clustering):
 * - minBoundingBoxArea: 40 (well above sequential baseline of 12)
 * - minRowSpan: 4 (sequential would be ≈2)
 * - minColSpan: 6 (sequential would be ≈6, but we want spread)
 */
export const PHASE0_V2_SPATIAL_CONFIG: SpatialDispersionConfig = {
  minBoundingBoxArea: 40,
  minRowSpan: 4,
  minColSpan: 6,
};

function getRowCol(wellPos: string): [number, number] {
  const row = wellPos.charCodeAt(0) - 65; // A=0, B=1, etc.
  const col = parseInt(wellPos.slice(1)) - 1; // 1=0, 2=1, etc.
  return [row, col];
}

export function inv_spatialDispersion(
  wells: Well[],
  cfg: SpatialDispersionConfig
): Violation[] {
  const violations: Violation[] = [];

  // Group wells by plate and compound (exclude sentinels)
  const wellsByPlateCompound = new Map<string, Well[]>();
  for (const well of wells) {
    if (well.is_sentinel) continue;

    const key = `${well.plate_id}|${well.compound}`;
    if (!wellsByPlateCompound.has(key)) {
      wellsByPlateCompound.set(key, []);
    }
    wellsByPlateCompound.get(key)!.push(well);
  }

  // Check spatial dispersion for each compound on each plate
  for (const [key, compoundWells] of wellsByPlateCompound.entries()) {
    const [plateId, compound] = key.split('|');

    if (compoundWells.length === 0) continue;

    // Get positions
    const positions = compoundWells.map((w) => getRowCol(w.well_pos));
    const rows = positions.map(([r, c]) => r);
    const cols = positions.map(([r, c]) => c);

    const minRow = Math.min(...rows);
    const maxRow = Math.max(...rows);
    const minCol = Math.min(...cols);
    const maxCol = Math.max(...cols);

    const rowSpan = maxRow - minRow + 1;
    const colSpan = maxCol - minCol + 1;
    const boundingBoxArea = rowSpan * colSpan;

    // Check bounding box area
    if (boundingBoxArea < cfg.minBoundingBoxArea) {
      violations.push({
        type: 'spatial_clustering',
        severity: 'error',
        plateId,
        message: `Compound ${compound} is spatially clustered (bbox area=${boundingBoxArea}, expected ≥${cfg.minBoundingBoxArea}).`,
        suggestion: 'Regenerate design with randomized position assignment (not sequential fill).',
        details: {
          compound,
          wellCount: compoundWells.length,
          rowSpan,
          colSpan,
          boundingBoxArea,
          minBoundingBoxArea: cfg.minBoundingBoxArea,
          note: 'Sequential fill creates tight clusters. Random scatter should span most of plate.',
        },
      });
    }

    // Check row span (compounds should spread vertically)
    if (rowSpan < cfg.minRowSpan) {
      violations.push({
        type: 'spatial_clustering_rows',
        severity: 'warning',
        plateId,
        message: `Compound ${compound} confined to ${rowSpan} rows (expected ≥${cfg.minRowSpan} for good vertical spread).`,
        suggestion: 'Review position assignment strategy. May indicate sequential or row-wise fill.',
        details: {
          compound,
          wellCount: compoundWells.length,
          rowSpan,
          minRowSpan: cfg.minRowSpan,
        },
      });
    }

    // Check col span (compounds should spread horizontally)
    if (colSpan < cfg.minColSpan) {
      violations.push({
        type: 'spatial_clustering_cols',
        severity: 'warning',
        plateId,
        message: `Compound ${compound} confined to ${colSpan} cols (expected ≥${cfg.minColSpan} for good horizontal spread).`,
        suggestion: 'Review position assignment strategy. May indicate column-wise fill.',
        details: {
          compound,
          wellCount: compoundWells.length,
          colSpan,
          minColSpan: cfg.minColSpan,
        },
      });
    }
  }

  return violations;
}
