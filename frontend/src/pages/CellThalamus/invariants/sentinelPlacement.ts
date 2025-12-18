/**
 * Invariant: Sentinels Placed Correctly
 *
 * For max identifiability (Phase 0 founder), sentinels must be:
 * 1. Exact count per type per plate
 * 2. Evenly distributed (not grouped at end)
 * 3. Same type separated (not clumped)
 * 4. Low variance in spacing
 */

import type { Well, Violation, Severity } from './types';

export interface SentinelInvariantConfig {
  // Expected counts per type per plate
  expectedCountsByType: Record<string, number>;

  // Ordering definition
  plateFormat: 96 | 384;

  // Distribution constraints (1D traversal order)
  maxGapNonSentinel: number;           // max run of non-sentinel wells
  windowSize: number;                  // sliding window size
  windowMinSentinels: number;          // min sentinels in window
  windowMaxSentinels: number;          // max sentinels in window

  // Type separation: "too many close pairs" heuristic
  sameTypeCloseDistance: number;       // distance threshold for "close"
  maxClosePairsPerType: number;        // max allowed close pairs

  // Spatial distribution (2D physical space)
  spatialBinRows: number;              // e.g., 2 for 96-well = 4×6 bins
  spatialBinCols: number;              // e.g., 3 for 96-well = 4×6 bins
  spatialBinTolerance: number;         // max deviation from expected per bin

  // Optional: validate per-slice (e.g., per timepoint)
  sliceKeys?: Array<(w: Well) => string>;
}

/**
 * Phase0_v2 configuration for max identifiability
 * - 28 sentinels per plate (32% sentinel density)
 * - 88 wells per plate (96-well with 8 excluded)
 * - Tight distribution constraints
 */
export const PHASE0_V2_SENTINEL_CONFIG: SentinelInvariantConfig = {
  expectedCountsByType: {
    // Actual founder uses mechanism-based sentinels, not compound-based
    'vehicle': 8,        // was: 'dmso'
    'er_mid': 5,         // was: 'tbhq'
    'mito_mid': 5,       // was: 'thapsigargin'
    'oxidative': 5,      // was: 'oligomycin'
    'proteostasis': 5,   // was: 'mg132'
  },
  plateFormat: 96,
  // 1D traversal constraints
  maxGapNonSentinel: 8,           // tight: no more than 8 non-sentinel wells in a row
  windowSize: 12,                  // window of 12 wells (about 1 column)
  windowMinSentinels: 2,           // at least 2 sentinels per 12 wells
  windowMaxSentinels: 6,           // at most 6 sentinels per 12 wells
  sameTypeCloseDistance: 3,        // "close" = within 3 positions
  maxClosePairsPerType: 2,         // max 2 close pairs per sentinel type
  // 2D spatial constraints (96-well: 8 rows × 12 cols)
  spatialBinRows: 2,               // 2 bin rows = 4 physical rows per bin
  spatialBinCols: 3,               // 3 bin cols = 4 physical cols per bin
  spatialBinTolerance: 3,          // max ±3 sentinels from expected per bin
  // This creates 2×3 = 6 bins, each bin should have ~28/6 = 4-5 sentinels
};

export function inv_sentinelsPlacedCorrectly(
  wells: Well[],
  cfg: SentinelInvariantConfig
): Violation[] {
  const violations: Violation[] = [];

  const wellsByPlate = groupBy(wells, w => w.plate_id);

  for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
    const ordered = orderWells(plateWells, cfg.plateFormat);

    // You can validate either full plate or per-slice (or both)
    const slices = cfg.sliceKeys?.length
      ? slicePlate(ordered, cfg.sliceKeys)
      : { all: ordered };

    for (const [sliceId, sliceWells] of Object.entries(slices)) {
      const sliceTag = cfg.sliceKeys?.length ? ` (${sliceId})` : '';

      const sentinels = sliceWells.filter(w => w.is_sentinel);
      const sentinelIdx = sentinels
        .map(s => sliceWells.findIndex(w => w === s))
        .filter(i => i >= 0)
        .sort((a, b) => a - b);

      // 1) Count exactness per type
      // CRITICAL: Normalize sentinel type to lowercase with trim (one throat to choke)
      const actualCounts = countBy(sentinels, s => normalizeSentinelType(s.sentinel_type));
      for (const [type, expected] of Object.entries(cfg.expectedCountsByType)) {
        const actual = actualCounts[type] ?? 0;
        if (actual !== expected) {
          violations.push({
            type: 'sentinel_count_mismatch',
            severity: 'error',
            plateId,
            message: `Plate ${plateId}${sliceTag}: expected ${expected} ${type} sentinels, got ${actual}.`,
            suggestion: 'Fix Allocation: sentinel tokens per plate must be exact.',
            details: { type, expected, actual },
          });
        }
      }

      // If no sentinels, everything else is meaningless
      if (sentinelIdx.length === 0) {
        violations.push({
          type: 'no_sentinels',
          severity: 'error',
          plateId,
          message: `Plate ${plateId}${sliceTag}: no sentinels placed.`,
          suggestion: 'Max identifiability requires sentinel structure on every plate.',
        });
        continue;
      }

      // 2a) Max gap of non-sentinel wells (linear order)
      const maxGap = maxNonSentinelRun(sliceWells);
      if (maxGap > cfg.maxGapNonSentinel) {
        violations.push({
          type: 'sentinel_max_gap_exceeded',
          severity: 'warning',
          plateId,
          message: `Plate ${plateId}${sliceTag}: max run of non-sentinel wells is ${maxGap} (limit ${cfg.maxGapNonSentinel}).`,
          suggestion: 'Improve placement: intersperse sentinels more evenly.',
          details: { maxGap, limit: cfg.maxGapNonSentinel },
        });
      }

      // 2b) Sliding window density
      const windowViol = slidingWindowSentinelCheck(
        sliceWells,
        cfg.windowSize,
        cfg.windowMinSentinels,
        cfg.windowMaxSentinels
      );
      for (const v of windowViol) {
        violations.push({
          type: 'sentinel_window_density',
          severity: 'warning',
          plateId,
          message: `Plate ${plateId}${sliceTag}: ${v}`,
          suggestion: 'Improve placement: enforce local sentinel density constraints.',
        });
      }

      // 3) Same-type close pairs heuristic
      const closePairsByType = countSameTypeClosePairs(
        sliceWells,
        cfg.sameTypeCloseDistance
      );
      for (const [type, nPairs] of Object.entries(closePairsByType)) {
        if (nPairs > cfg.maxClosePairsPerType) {
          violations.push({
            type: 'sentinel_type_clumping',
            severity: 'warning',
            plateId,
            message: `Plate ${plateId}${sliceTag}: sentinel type ${type} has ${nPairs} close pairs within distance ${cfg.sameTypeCloseDistance} (limit ${cfg.maxClosePairsPerType}).`,
            suggestion: 'Improve placement: spread identical sentinel types out.',
            details: { type, nPairs, limit: cfg.maxClosePairsPerType, distance: cfg.sameTypeCloseDistance },
          });
        }
      }

      // 4) Dispersion metric (optional but useful)
      const gaps = interSentinelGaps(sentinelIdx, sliceWells.length);
      const cv = coefficientOfVariation(gaps);
      if (Number.isFinite(cv) && cv > 0.9) {
        violations.push({
          type: 'sentinel_gap_high_variance',
          severity: 'warning',
          plateId,
          message: `Plate ${plateId}${sliceTag}: sentinel gap CV is ${cv.toFixed(2)} (high dispersion).`,
          suggestion: 'Improve placement: reduce uneven spacing between sentinels.',
          details: { cv, threshold: 0.9 },
        });
      }

      // 5) Spatial distribution (2D physical space, not traversal order)
      const spatialViolations = checkSpatialDistribution(
        sliceWells,
        cfg.plateFormat,
        cfg.spatialBinRows,
        cfg.spatialBinCols,
        cfg.spatialBinTolerance
      );
      for (const v of spatialViolations) {
        violations.push({
          type: 'sentinel_spatial_clustering',
          severity: 'warning',
          plateId,
          message: `Plate ${plateId}${sliceTag}: ${v}`,
          suggestion: 'Improve placement: distribute sentinels evenly across physical plate regions.',
        });
      }
    }
  }

  return violations;
}

/* ---------------- helpers ---------------- */

/**
 * Normalize sentinel type to canonical form
 * ONE THROAT TO CHOKE: all sentinel type comparisons go through here
 */
function normalizeSentinelType(type: string | undefined): string {
  return (type ?? 'UNKNOWN').trim().toLowerCase();
}

function groupBy<T>(items: T[], keyFn: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = keyFn(it);
    (out[k] ??= []).push(it);
  }
  return out;
}

function countBy<T>(items: T[], keyFn: (t: T) => string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const it of items) {
    const k = keyFn(it);
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

function orderWells(wells: Well[], plateFormat: 96 | 384): Well[] {
  // Row-major ordering: A01, A02, ..., A12, B01, ...
  // This matches the generator's well assignment order
  const withKey = wells.map(w => ({
    w,
    k: positionToIndex(w.well_pos, plateFormat),
  }));
  withKey.sort((a, b) => a.k - b.k);
  return withKey.map(x => x.w);
}

function positionToIndex(pos: string, plateFormat: 96 | 384): number {
  // pos like "A01" or "A1" (handle both)
  const row = pos[0].toUpperCase();
  const col = Number(pos.slice(1));
  const nCols = plateFormat === 96 ? 12 : 24;
  const rowIdx = row.charCodeAt(0) - 'A'.charCodeAt(0);
  return rowIdx * nCols + (col - 1);
}

function slicePlate(
  ordered: Well[],
  sliceKeys: Array<(w: Well) => string>
): Record<string, Well[]> {
  // combines multiple keys into one slice id
  const out: Record<string, Well[]> = {};
  for (const w of ordered) {
    const sid = sliceKeys.map(fn => fn(w)).join('|');
    (out[sid] ??= []).push(w);
  }
  return out;
}

function maxNonSentinelRun(ordered: Well[]): number {
  let maxRun = 0;
  let run = 0;
  for (const w of ordered) {
    if (w.is_sentinel) {
      maxRun = Math.max(maxRun, run);
      run = 0;
    } else {
      run += 1;
    }
  }
  return Math.max(maxRun, run);
}

function slidingWindowSentinelCheck(
  ordered: Well[],
  windowSize: number,
  minS: number,
  maxS: number
): string[] {
  const msgs: string[] = [];
  if (windowSize <= 0 || windowSize > ordered.length) return msgs;

  let sCount = 0;
  for (let i = 0; i < windowSize; i++) {
    if (ordered[i].is_sentinel) sCount++;
  }

  const check = (start: number, count: number) => {
    if (count < minS) {
      msgs.push(`Window [${start}..${start + windowSize - 1}] has ${count} sentinels (min ${minS}).`);
    }
    if (count > maxS) {
      msgs.push(`Window [${start}..${start + windowSize - 1}] has ${count} sentinels (max ${maxS}).`);
    }
  };

  check(0, sCount);

  for (let start = 1; start + windowSize <= ordered.length; start++) {
    const prev = ordered[start - 1];
    const next = ordered[start + windowSize - 1];
    if (prev.is_sentinel) sCount--;
    if (next.is_sentinel) sCount++;
    check(start, sCount);
  }

  return msgs;
}

function countSameTypeClosePairs(ordered: Well[], dist: number): Record<string, number> {
  const idxByType: Record<string, number[]> = {};
  ordered.forEach((w, i) => {
    if (!w.is_sentinel) return;
    const t = normalizeSentinelType(w.sentinel_type);
    (idxByType[t] ??= []).push(i);
  });

  const out: Record<string, number> = {};
  for (const [t, idxs] of Object.entries(idxByType)) {
    let pairs = 0;
    for (let i = 0; i < idxs.length; i++) {
      for (let j = i + 1; j < idxs.length; j++) {
        if (idxs[j] - idxs[i] <= dist) pairs++;
        else break; // idxs sorted by construction
      }
    }
    out[t] = pairs;
  }
  return out;
}

function interSentinelGaps(idxs: number[], n: number): number[] {
  if (idxs.length <= 1) return [n];
  const gaps: number[] = [];
  for (let i = 1; i < idxs.length; i++) {
    gaps.push(idxs[i] - idxs[i - 1]);
  }
  // Note: not including wraparound (cyclic) gap for simplicity
  return gaps;
}

function coefficientOfVariation(xs: number[]): number {
  if (xs.length === 0) return NaN;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  if (mean === 0) return NaN;
  const varr = xs.reduce((a, x) => a + (x - mean) ** 2, 0) / xs.length;
  return Math.sqrt(varr) / mean;
}

/**
 * Check 2D spatial distribution of sentinels across plate
 * Bins plate into grid and ensures sentinels distributed evenly
 */
function checkSpatialDistribution(
  wells: Well[],
  plateFormat: 96 | 384,
  binRows: number,
  binCols: number,
  tolerance: number
): string[] {
  const msgs: string[] = [];

  const nRows = plateFormat === 96 ? 8 : 16;
  const nCols = plateFormat === 96 ? 12 : 24;

  const rowsPerBin = Math.ceil(nRows / binRows);
  const colsPerBin = Math.ceil(nCols / binCols);

  // Count sentinels per bin
  const binCounts: number[][] = Array.from({ length: binRows }, () =>
    Array(binCols).fill(0)
  );

  for (const w of wells) {
    if (!w.is_sentinel) continue;

    const idx = positionToIndex(w.well_pos, plateFormat);
    const row = Math.floor(idx / nCols);
    const col = idx % nCols;

    const binRow = Math.floor(row / rowsPerBin);
    const binCol = Math.floor(col / colsPerBin);

    if (binRow < binRows && binCol < binCols) {
      binCounts[binRow][binCol]++;
    }
  }

  // Expected sentinels per bin
  const totalSentinels = wells.filter(w => w.is_sentinel).length;
  const totalBins = binRows * binCols;
  const expectedPerBin = totalSentinels / totalBins;

  // Check each bin against tolerance
  for (let r = 0; r < binRows; r++) {
    for (let c = 0; c < binCols; c++) {
      const count = binCounts[r][c];
      const deviation = Math.abs(count - expectedPerBin);

      if (deviation > tolerance) {
        msgs.push(
          `Bin [${r},${c}] has ${count} sentinels (expected ~${expectedPerBin.toFixed(1)}, deviation ${deviation.toFixed(1)} > tolerance ${tolerance}).`
        );
      }
    }
  }

  return msgs;
}
