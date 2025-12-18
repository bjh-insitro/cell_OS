/**
 * Invariant: Condition Multiset Identical Across Timepoints
 *
 * Direct antidote to the murder weapon (timepoint-dependent sentinel schema).
 *
 * For each stratum (cell_line, day, operator):
 * - Build multiset of experimental conditions at each timepoint
 * - Verify exact equality (including multiplicity)
 * - ERROR if any timepoint differs
 *
 * This prevents silent dropping and policy collisions.
 */

import type { Well, Violation } from './types';

export interface ConditionMultisetConfig {
  // Dose canonicalization tolerance (to handle float precision)
  doseTolerance: number;
}

export const PHASE0_V2_CONDITION_MULTISET_CONFIG: ConditionMultisetConfig = {
  doseTolerance: 0.001, // 1 nanomolar tolerance for float comparison
};

export function inv_condition_multiset_identical_across_timepoints(
  wells: Well[],
  cfg: ConditionMultisetConfig
): Violation[] {
  const violations: Violation[] = [];

  // Group by stratum: (cell_line, day, operator)
  const experimentalWells = wells.filter((w) => !w.is_sentinel);

  const stratumKey = (w: Well) =>
    `${w.cell_line ?? 'UNKNOWN'}|${w.day ?? 'UNKNOWN'}|${w.operator ?? 'UNKNOWN'}`;

  const wellsByStratum = groupBy(experimentalWells, stratumKey);

  for (const [stratum, stratumWells] of Object.entries(wellsByStratum)) {
    const [cellLine, day, operator] = stratum.split('|');

    // Group by timepoint within this stratum
    const wellsByTimepoint = groupBy(stratumWells, (w) => String(w.timepoint_h ?? 'UNKNOWN'));

    // Build multisets for each timepoint
    const multisetsByTimepoint = new Map<string, Map<string, number>>();

    for (const [timepoint, timepointWells] of Object.entries(wellsByTimepoint)) {
      const multiset = new Map<string, number>();

      for (const well of timepointWells) {
        const conditionKey = canonicalConditionKey(well.compound, well.dose_uM, cfg.doseTolerance);
        multiset.set(conditionKey, (multiset.get(conditionKey) ?? 0) + 1);
      }

      multisetsByTimepoint.set(timepoint, multiset);
    }

    // Compare all timepoints to the first timepoint (reference)
    const timepoints = Array.from(multisetsByTimepoint.keys()).sort();
    if (timepoints.length <= 1) {
      continue; // Only one timepoint in this stratum, nothing to compare
    }

    const referenceTimepoint = timepoints[0];
    const referenceMultiset = multisetsByTimepoint.get(referenceTimepoint)!;

    for (const timepoint of timepoints.slice(1)) {
      const timepointMultiset = multisetsByTimepoint.get(timepoint)!;

      // Check if multisets are equal
      const mismatch = compareMultisets(referenceMultiset, timepointMultiset);

      if (mismatch) {
        violations.push({
          type: 'condition_multiset_mismatch',
          severity: 'error',
          message: `Stratum (cell_line=${cellLine}, day=${day}, operator=${operator}): timepoint ${timepoint} has different experimental conditions than reference timepoint ${referenceTimepoint}.`,
          suggestion: 'Regenerate design with identical condition multisets per timepoint. Check for timepoint-dependent allocation bugs.',
          details: {
            stratum: { cellLine, day, operator },
            referenceTimepoint,
            timepoint,
            mismatch,
          },
        });
      }
    }
  }

  return violations;
}

/**
 * Experimental Position Stability
 *
 * For each cell line, verify that each position always has the same (compound, dose)
 * across ALL plates (regardless of batch factors).
 *
 * NOTE: We check inverse direction ONLY (position -> condition), NOT forward direction
 * (condition -> position), because replicates mean the same compound@dose legitimately
 * appears at multiple positions.
 *
 * Example: tBHQ@3.0 has 2 replicates, so it appears at A03 and A04. Both are correct.
 * What matters is:
 * - A03 always has tBHQ@3.0 (replicate 1) across all plates
 * - A04 always has tBHQ@3.0 (replicate 2) across all plates
 */
export function inv_experimental_position_stability(
  wells: Well[],
  cfg: ConditionMultisetConfig
): Violation[] {
  const violations: Violation[] = [];

  const experimentalWells = wells.filter((w) => !w.is_sentinel);

  // Group by cell line
  const wellsByCellLine = groupBy(experimentalWells, (w) => w.cell_line ?? 'UNKNOWN');

  for (const [cellLine, cellLineWells] of Object.entries(wellsByCellLine)) {
    // Build position -> condition map (inverse stability only)
    const positionToCondition = new Map<string, string>();

    for (const well of cellLineWells) {
      const conditionKey = canonicalConditionKey(well.compound, well.dose_uM, cfg.doseTolerance);
      const position = normalizePosition(well.well_pos);

      // Check inverse stability: position -> condition
      const existingCondition = positionToCondition.get(position);
      if (existingCondition === undefined) {
        positionToCondition.set(position, conditionKey);
      } else if (existingCondition !== conditionKey) {
        violations.push({
          type: 'experimental_position_instability',
          severity: 'error',
          plateId: well.plate_id,
          message: `Cell line ${cellLine}: position ${position} has both ${existingCondition} and ${conditionKey}.`,
          suggestion: 'Regenerate design with deterministic position assignment.',
          details: {
            cellLine,
            position,
            conditions: [existingCondition, conditionKey],
          },
        });
      }
    }
  }

  return violations;
}

/* ---------------- helpers ---------------- */

function canonicalConditionKey(compound: string, dose: number, tolerance: number): string {
  // Round dose to tolerance precision to avoid float comparison issues
  const roundedDose = Math.round(dose / tolerance) * tolerance;
  return `${compound}@${roundedDose.toFixed(3)}`;
}

function normalizePosition(pos: string): string {
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

function compareMultisets(
  a: Map<string, number>,
  b: Map<string, number>
): { missing: string[]; extra: string[]; countMismatch: Array<{ key: string; expected: number; actual: number }> } | null {
  const missing: string[] = [];
  const extra: string[] = [];
  const countMismatch: Array<{ key: string; expected: number; actual: number }> = [];

  // Check keys in a but not in b (or count mismatch)
  for (const [key, countA] of a) {
    const countB = b.get(key);
    if (countB === undefined) {
      missing.push(key);
    } else if (countA !== countB) {
      countMismatch.push({ key, expected: countA, actual: countB });
    }
  }

  // Check keys in b but not in a
  for (const [key] of b) {
    if (!a.has(key)) {
      extra.push(key);
    }
  }

  if (missing.length === 0 && extra.length === 0 && countMismatch.length === 0) {
    return null; // Multisets are equal
  }

  return { missing, extra, countMismatch };
}
