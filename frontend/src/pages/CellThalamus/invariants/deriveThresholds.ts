/**
 * Derive invariant thresholds from actual Phase0_v2 design
 *
 * Don't guess thresholds - compute from the founder design's 95th percentile.
 * The founder should pass cleanly, otherwise you've encoded a policy your reference violates.
 */

import type { Well } from './types';
import { inv_sentinelsPlacedCorrectly, PHASE0_V2_SENTINEL_CONFIG } from './sentinelPlacement';

export interface DerivedThresholds {
  maxGapNonSentinel: {
    actual: number[];
    p95: number;
    suggested: number;
  };
  gapCV: {
    actual: number[];
    p95: number;
    suggested: number;
  };
  closePairsPerType: {
    actual: Record<string, number[]>;
    p95ByType: Record<string, number>;
    suggestedMax: number;
  };
  spatialBinDeviation: {
    actual: number[];
    p95: number;
    suggested: number;
  };
}

/**
 * Compute actual metrics from v2 design and suggest thresholds
 */
export function deriveThresholdsFromFounder(wells: Well[]): DerivedThresholds {
  const wellsByPlate = groupBy(wells, w => w.plate_id);

  const maxGaps: number[] = [];
  const cvs: number[] = [];
  const closePairsByType: Record<string, number[]> = {};
  const spatialDeviations: number[] = [];

  for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
    const ordered = orderWells(plateWells);
    const sentinels = ordered.filter(w => w.is_sentinel);

    // Max gap
    const maxGap = computeMaxNonSentinelRun(ordered);
    maxGaps.push(maxGap);

    // Gap CV
    const sentinelIdx = sentinels
      .map(s => ordered.findIndex(w => w === s))
      .filter(i => i >= 0)
      .sort((a, b) => a - b);
    const gaps = computeInterSentinelGaps(sentinelIdx, ordered.length);
    const cv = computeCV(gaps);
    if (Number.isFinite(cv)) cvs.push(cv);

    // Close pairs by type
    const closePairs = computeClosePairsByType(ordered);
    for (const [type, count] of Object.entries(closePairs)) {
      (closePairsByType[type] ??= []).push(count);
    }

    // Spatial deviation
    const spatialViolations = computeSpatialDeviations(plateWells);
    spatialDeviations.push(...spatialViolations);
  }

  // Compute 95th percentiles
  const maxGapP95 = percentile(maxGaps, 0.95);
  const cvP95 = percentile(cvs, 0.95);
  const closePairsP95ByType: Record<string, number> = {};
  for (const [type, counts] of Object.entries(closePairsByType)) {
    closePairsP95ByType[type] = percentile(counts, 0.95);
  }
  const spatialP95 = percentile(spatialDeviations, 0.95);

  return {
    maxGapNonSentinel: {
      actual: maxGaps,
      p95: maxGapP95,
      suggested: Math.ceil(maxGapP95 * 1.1), // Add 10% margin
    },
    gapCV: {
      actual: cvs,
      p95: cvP95,
      suggested: Math.ceil(cvP95 * 10) / 10, // Round to 1 decimal
    },
    closePairsPerType: {
      actual: closePairsByType,
      p95ByType: closePairsP95ByType,
      suggestedMax: Math.max(...Object.values(closePairsP95ByType)),
    },
    spatialBinDeviation: {
      actual: spatialDeviations,
      p95: spatialP95,
      suggested: Math.ceil(spatialP95),
    },
  };
}

/**
 * Generate report comparing current thresholds to derived ones
 */
export function generateThresholdReport(wells: Well[]): string {
  const derived = deriveThresholdsFromFounder(wells);

  const report: string[] = [
    '# Threshold Derivation Report',
    '',
    '## Max Gap (Non-Sentinel Run)',
    `Current threshold: ${PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel}`,
    `Actual max across plates: ${Math.max(...derived.maxGapNonSentinel.actual)}`,
    `Actual mean: ${mean(derived.maxGapNonSentinel.actual).toFixed(1)}`,
    `95th percentile: ${derived.maxGapNonSentinel.p95.toFixed(1)}`,
    `**Suggested threshold: ${derived.maxGapNonSentinel.suggested}**`,
    '',
    derived.maxGapNonSentinel.suggested > PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel
      ? `⚠️  Current threshold ${PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel} is too tight - founder design exceeds it.`
      : `✓ Current threshold ${PHASE0_V2_SENTINEL_CONFIG.maxGapNonSentinel} is appropriate.`,
    '',
    '## Gap Coefficient of Variation',
    `Current threshold: 0.9`,
    `Actual max across plates: ${Math.max(...derived.gapCV.actual).toFixed(2)}`,
    `Actual mean: ${mean(derived.gapCV.actual).toFixed(2)}`,
    `95th percentile: ${derived.gapCV.p95.toFixed(2)}`,
    `**Suggested threshold: ${derived.gapCV.suggested}**`,
    '',
    derived.gapCV.suggested > 0.9
      ? `⚠️  Current threshold 0.9 is too tight - founder design exceeds it.`
      : `✓ Current threshold 0.9 is appropriate.`,
    '',
    '## Close Pairs Per Type',
    `Current threshold: ${PHASE0_V2_SENTINEL_CONFIG.maxClosePairsPerType}`,
    '',
  ];

  for (const [type, counts] of Object.entries(derived.closePairsPerType.actual)) {
    const typeP95 = derived.closePairsPerType.p95ByType[type];
    report.push(`### ${type}:`);
    report.push(`  Actual max: ${Math.max(...counts)}`);
    report.push(`  Actual mean: ${mean(counts).toFixed(1)}`);
    report.push(`  95th percentile: ${typeP95.toFixed(1)}`);
    report.push('');
  }

  report.push(`**Suggested max: ${derived.closePairsPerType.suggestedMax}**`);
  report.push('');

  if (derived.closePairsPerType.suggestedMax > PHASE0_V2_SENTINEL_CONFIG.maxClosePairsPerType) {
    report.push(
      `⚠️  Current threshold ${PHASE0_V2_SENTINEL_CONFIG.maxClosePairsPerType} is too tight - founder design exceeds it.`
    );
  } else {
    report.push(`✓ Current threshold ${PHASE0_V2_SENTINEL_CONFIG.maxClosePairsPerType} is appropriate.`);
  }

  report.push('');
  report.push('## Spatial Bin Deviation');
  report.push(`Current tolerance: ${PHASE0_V2_SENTINEL_CONFIG.spatialBinTolerance}`);
  report.push(`Actual max deviation: ${Math.max(...derived.spatialBinDeviation.actual).toFixed(1)}`);
  report.push(`Actual mean: ${mean(derived.spatialBinDeviation.actual).toFixed(1)}`);
  report.push(`95th percentile: ${derived.spatialBinDeviation.p95.toFixed(1)}`);
  report.push(`**Suggested tolerance: ${derived.spatialBinDeviation.suggested}**`);
  report.push('');

  if (derived.spatialBinDeviation.suggested > PHASE0_V2_SENTINEL_CONFIG.spatialBinTolerance) {
    report.push(
      `⚠️  Current tolerance ${PHASE0_V2_SENTINEL_CONFIG.spatialBinTolerance} is too tight - founder design exceeds it.`
    );
  } else {
    report.push(`✓ Current tolerance ${PHASE0_V2_SENTINEL_CONFIG.spatialBinTolerance} is appropriate.`);
  }

  return report.join('\n');
}

/* ============ Helpers ============ */

function groupBy<T>(items: T[], keyFn: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = keyFn(it);
    (out[k] ??= []).push(it);
  }
  return out;
}

function orderWells(wells: Well[]): Well[] {
  const withKey = wells.map(w => ({
    w,
    k: positionToIndex(w.well_pos),
  }));
  withKey.sort((a, b) => a.k - b.k);
  return withKey.map(x => x.w);
}

function positionToIndex(pos: string): number {
  const row = pos[0].toUpperCase();
  const col = Number(pos.slice(1));
  const nCols = 12; // Assume 96-well for v2
  const rowIdx = row.charCodeAt(0) - 'A'.charCodeAt(0);
  return rowIdx * nCols + (col - 1);
}

function computeMaxNonSentinelRun(ordered: Well[]): number {
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

function computeInterSentinelGaps(idxs: number[], n: number): number[] {
  if (idxs.length <= 1) return [n];
  const gaps: number[] = [];
  for (let i = 1; i < idxs.length; i++) {
    gaps.push(idxs[i] - idxs[i - 1]);
  }
  return gaps;
}

function computeCV(xs: number[]): number {
  if (xs.length === 0) return NaN;
  const m = mean(xs);
  if (m === 0) return NaN;
  const varr = xs.reduce((a, x) => a + (x - m) ** 2, 0) / xs.length;
  return Math.sqrt(varr) / m;
}

function computeClosePairsByType(ordered: Well[]): Record<string, number> {
  const dist = 3;
  const idxByType: Record<string, number[]> = {};
  ordered.forEach((w, i) => {
    if (!w.is_sentinel) return;
    const t = (w.sentinel_type ?? 'UNKNOWN').trim().toLowerCase();
    (idxByType[t] ??= []).push(i);
  });

  const out: Record<string, number> = {};
  for (const [t, idxs] of Object.entries(idxByType)) {
    let pairs = 0;
    for (let i = 0; i < idxs.length; i++) {
      for (let j = i + 1; j < idxs.length; j++) {
        if (idxs[j] - idxs[i] <= dist) pairs++;
        else break;
      }
    }
    out[t] = pairs;
  }
  return out;
}

function computeSpatialDeviations(wells: Well[]): number[] {
  const plateFormat = 96;
  const binRows = 2;
  const binCols = 3;

  const nRows = 8;
  const nCols = 12;
  const rowsPerBin = Math.ceil(nRows / binRows);
  const colsPerBin = Math.ceil(nCols / binCols);

  const binCounts: number[][] = Array.from({ length: binRows }, () => Array(binCols).fill(0));

  for (const w of wells) {
    if (!w.is_sentinel) continue;

    const idx = positionToIndex(w.well_pos);
    const row = Math.floor(idx / nCols);
    const col = idx % nCols;

    const binRow = Math.floor(row / rowsPerBin);
    const binCol = Math.floor(col / colsPerBin);

    if (binRow < binRows && binCol < binCols) {
      binCounts[binRow][binCol]++;
    }
  }

  const totalSentinels = wells.filter(w => w.is_sentinel).length;
  const expectedPerBin = totalSentinels / (binRows * binCols);

  const deviations: number[] = [];
  for (let r = 0; r < binRows; r++) {
    for (let c = 0; c < binCols; c++) {
      deviations.push(Math.abs(binCounts[r][c] - expectedPerBin));
    }
  }

  return deviations;
}

function percentile(xs: number[], p: number): number {
  if (xs.length === 0) return NaN;
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.ceil(sorted.length * p) - 1;
  return sorted[Math.max(0, idx)];
}

function mean(xs: number[]): number {
  if (xs.length === 0) return NaN;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
