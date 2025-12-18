/**
 * Invariant: Sentinel Scaffold Exact Match
 *
 * For fixed scaffold designs, verify:
 * 1. Scaffold ID and hash match expected values
 * 2. All plates have identical sentinel positions and types
 * 3. Sentinel positions match scaffold specification exactly
 *
 * This makes "someone tweaks a position because vibes" unrepresentable
 * without bumping the scaffold version.
 */

import type { Well, Violation } from './types';
import crypto from 'crypto';

export interface ScaffoldInvariantConfig {
  expectedScaffoldId: string;
  expectedScaffoldHash: string;
  expectedScaffold: Array<{
    position: string;
    type: string;
  }>;
}

/**
 * Phase0_v2 scaffold configuration
 * Hash: 901ffeb4603019fe (frozen from phase0_sentinel_scaffold.py)
 */
export const PHASE0_V2_SCAFFOLD_CONFIG: ScaffoldInvariantConfig = {
  expectedScaffoldId: 'phase0_v2_scaffold_v1',
  expectedScaffoldHash: '901ffeb4603019fe',
  expectedScaffold: [
    { position: 'A02', type: 'vehicle' },
    { position: 'A05', type: 'ER_mid' },
    { position: 'A10', type: 'mito_mid' },
    { position: 'B02', type: 'vehicle' },
    { position: 'B06', type: 'ER_mid' },
    { position: 'B09', type: 'mito_mid' },
    { position: 'B12', type: 'vehicle' },
    { position: 'C03', type: 'ER_mid' },
    { position: 'C06', type: 'mito_mid' },
    { position: 'C09', type: 'vehicle' },
    { position: 'C12', type: 'ER_mid' },
    { position: 'D04', type: 'mito_mid' },
    { position: 'D07', type: 'vehicle' },
    { position: 'D10', type: 'ER_mid' },
    { position: 'E01', type: 'mito_mid' },
    { position: 'E04', type: 'vehicle' },
    { position: 'E07', type: 'oxidative' },
    { position: 'E10', type: 'oxidative' },
    { position: 'F02', type: 'vehicle' },
    { position: 'F05', type: 'oxidative' },
    { position: 'F08', type: 'proteostasis' },
    { position: 'F11', type: 'vehicle' },
    { position: 'G02', type: 'oxidative' },
    { position: 'G05', type: 'proteostasis' },
    { position: 'G08', type: 'proteostasis' },
    { position: 'G12', type: 'oxidative' },
    { position: 'H04', type: 'proteostasis' },
    { position: 'H09', type: 'proteostasis' },
  ],
};

import type { DesignMetadata } from './types';

export function inv_sentinelScaffoldExactMatch(
  wells: Well[],
  cfg: ScaffoldInvariantConfig,
  designMetadata?: DesignMetadata
): Violation[] {
  const violations: Violation[] = [];

  const policy = designMetadata?.sentinel_schema?.policy;
  const scaffoldMeta = designMetadata?.sentinel_schema?.scaffold_metadata;

  // PHASE 0 REQUIREMENT: Policy must exist (no mystery designs)
  if (!policy) {
    violations.push({
      type: 'sentinel_policy_missing',
      severity: 'error',
      message: 'Phase 0 design is missing sentinel_schema.policy. Mystery designs are not allowed.',
      suggestion: 'Regenerate design with explicit sentinel_schema.policy (e.g. "fixed_scaffold").',
    });
    // Continue checking to report all violations, not just the first
  }

  // PHASE 0 FOUNDER REQUIREMENT: Policy must be "fixed_scaffold"
  if (policy && policy !== 'fixed_scaffold') {
    violations.push({
      type: 'sentinel_policy_unsupported',
      severity: 'error',
      message: `Phase 0 founder requires sentinel_schema.policy = "fixed_scaffold", got "${policy}".`,
      suggestion: 'Phase 0 founder only supports fixed_scaffold policy. Use correct design generator.',
      details: { policy },
    });
  }

  // Detect if wells match THE expected scaffold exactly
  const looksScaffolded = detectScaffoldPattern(wells, cfg);

  // SHARP EDGE 1: If wells look scaffolded but metadata missing/incorrect, ERROR
  if (looksScaffolded) {
    if (policy !== 'fixed_scaffold') {
      violations.push({
        type: 'scaffold_undocumented',
        severity: 'error',
        message: `Wells appear to follow fixed scaffold pattern, but metadata policy is "${policy ?? 'missing'}". Expected "fixed_scaffold".`,
        suggestion: 'Regenerate design with scaffold versioning metadata (policy: "fixed_scaffold").',
        details: {
          detectedPattern: 'fixed_scaffold',
          metadataPolicy: policy ?? null,
        },
      });
    }

    if (!scaffoldMeta?.scaffold_hash) {
      violations.push({
        type: 'scaffold_metadata_missing_hash',
        severity: 'error',
        message: 'Wells follow fixed scaffold pattern but metadata missing scaffold_hash.',
        suggestion: 'Regenerate design with scaffold versioning metadata.',
      });
    } else if (scaffoldMeta.scaffold_hash !== cfg.expectedScaffoldHash) {
      violations.push({
        type: 'scaffold_metadata_hash_mismatch',
        severity: 'error',
        message: `Design metadata has scaffold_hash ${scaffoldMeta.scaffold_hash}, expected ${cfg.expectedScaffoldHash}.`,
        suggestion: 'Regenerate design with correct scaffold version or update invariant config.',
        details: {
          expected: cfg.expectedScaffoldHash,
          actual: scaffoldMeta.scaffold_hash,
        },
      });
    }

    if (!scaffoldMeta?.scaffold_id) {
      violations.push({
        type: 'scaffold_metadata_missing_id',
        severity: 'error',
        message: 'Wells follow fixed scaffold pattern but metadata missing scaffold_id.',
        suggestion: 'Regenerate design with scaffold versioning metadata.',
      });
    } else if (scaffoldMeta.scaffold_id !== cfg.expectedScaffoldId) {
      violations.push({
        type: 'scaffold_metadata_id_mismatch',
        severity: 'error',
        message: `Design metadata has scaffold_id ${scaffoldMeta.scaffold_id}, expected ${cfg.expectedScaffoldId}.`,
        suggestion: 'Regenerate design with correct scaffold version or update invariant config.',
        details: {
          expected: cfg.expectedScaffoldId,
          actual: scaffoldMeta.scaffold_id,
        },
      });
    }
  }

  const wellsByPlate = groupBy(wells, (w) => w.plate_id);
  const plateIds = Object.keys(wellsByPlate).sort();

  if (plateIds.length === 0) {
    return violations; // No plates to check
  }

  // Build expected scaffold map (position -> type)
  const expectedScaffoldMap = new Map<string, string>();
  for (const entry of cfg.expectedScaffold) {
    expectedScaffoldMap.set(normalizePosition(entry.position), normalizeSentinelType(entry.type));
  }

  // Get reference scaffold from first plate
  const referencePlateId = plateIds[0];
  const referenceSentinels = wellsByPlate[referencePlateId]
    .filter((w) => w.is_sentinel)
    .map((w) => ({
      position: normalizePosition(w.well_pos),
      type: normalizeSentinelType(w.sentinel_type),
    }))
    .sort((a, b) => a.position.localeCompare(b.position));

  // Check reference plate matches expected scaffold
  if (referenceSentinels.length !== cfg.expectedScaffold.length) {
    violations.push({
      type: 'scaffold_count_mismatch',
      severity: 'error',
      plateId: referencePlateId,
      message: `Scaffold count mismatch: expected ${cfg.expectedScaffold.length} sentinels, got ${referenceSentinels.length}.`,
      suggestion: 'Regenerate design with correct scaffold specification.',
      details: {
        expected: cfg.expectedScaffold.length,
        actual: referenceSentinels.length,
      },
    });
  }

  // Check each sentinel position and type
  for (const refSentinel of referenceSentinels) {
    const expectedType = expectedScaffoldMap.get(refSentinel.position);

    if (expectedType === undefined) {
      violations.push({
        type: 'scaffold_position_unexpected',
        severity: 'error',
        plateId: referencePlateId,
        message: `Sentinel at position ${refSentinel.position} not in expected scaffold.`,
        suggestion: 'Regenerate design with correct scaffold specification.',
        details: { position: refSentinel.position, type: refSentinel.type },
      });
    } else if (expectedType !== refSentinel.type) {
      violations.push({
        type: 'scaffold_type_mismatch',
        severity: 'error',
        plateId: referencePlateId,
        message: `Sentinel at ${refSentinel.position} has type ${refSentinel.type}, expected ${expectedType}.`,
        suggestion: 'Regenerate design with correct scaffold specification.',
        details: {
          position: refSentinel.position,
          expected: expectedType,
          actual: refSentinel.type,
        },
      });
    }
  }

  // Check for missing positions
  for (const [expectedPos, expectedType] of expectedScaffoldMap) {
    const found = referenceSentinels.find((s) => s.position === expectedPos);
    if (!found) {
      violations.push({
        type: 'scaffold_position_missing',
        severity: 'error',
        plateId: referencePlateId,
        message: `Expected sentinel at position ${expectedPos} (type ${expectedType}) not found.`,
        suggestion: 'Regenerate design with correct scaffold specification.',
        details: { position: expectedPos, type: expectedType },
      });
    }
  }

  // Check all other plates match reference plate (scaffold stability)
  for (const plateId of plateIds.slice(1)) {
    const plateSentinels = wellsByPlate[plateId]
      .filter((w) => w.is_sentinel)
      .map((w) => ({
        position: normalizePosition(w.well_pos),
        type: normalizeSentinelType(w.sentinel_type),
      }))
      .sort((a, b) => a.position.localeCompare(b.position));

    // Quick check: count match
    if (plateSentinels.length !== referenceSentinels.length) {
      violations.push({
        type: 'scaffold_stability_count',
        severity: 'error',
        plateId,
        message: `Plate ${plateId} has ${plateSentinels.length} sentinels, reference plate has ${referenceSentinels.length}.`,
        suggestion: 'All plates must have identical sentinel scaffold.',
        details: {
          reference: referencePlateId,
          expected: referenceSentinels.length,
          actual: plateSentinels.length,
        },
      });
      continue; // Skip position-by-position check if counts differ
    }

    // Position-by-position check
    for (let i = 0; i < referenceSentinels.length; i++) {
      const ref = referenceSentinels[i];
      const plate = plateSentinels[i];

      if (ref.position !== plate.position || ref.type !== plate.type) {
        violations.push({
          type: 'scaffold_stability_mismatch',
          severity: 'error',
          plateId,
          message: `Plate ${plateId} sentinel at index ${i} differs from reference plate.`,
          suggestion: 'All plates must have identical sentinel scaffold.',
          details: {
            reference: referencePlateId,
            expected: ref,
            actual: plate,
          },
        });
      }
    }
  }

  return violations;
}

/* ---------------- helpers ---------------- */

/**
 * Detect if wells follow THE expected fixed scaffold pattern
 * (not just "a" stable pattern, but THIS specific scaffold)
 *
 * Returns true only if every plate's sentinel set exactly matches cfg.expectedScaffold
 * by (position, type).
 */
function detectScaffoldPattern(wells: Well[], cfg: ScaffoldInvariantConfig): boolean {
  const wellsByPlate = groupBy(wells, (w) => w.plate_id);
  const plateIds = Object.keys(wellsByPlate);

  if (plateIds.length === 0) return false;

  // Build expected map: position -> type
  const expectedByPos = new Map<string, string>();
  for (const e of cfg.expectedScaffold) {
    const pos = normalizePosition(e.position);
    const typ = normalizeSentinelType(e.type);
    expectedByPos.set(pos, typ);
  }

  const expectedPositions = Array.from(expectedByPos.keys()).sort();
  const expectedSize = expectedPositions.length;

  // Helper: get plate sentinel map: position -> type
  const plateSentinelMap = (plateId: string) => {
    const sent = wellsByPlate[plateId]
      .filter((w) => w.is_sentinel)
      .map((w) => ({
        position: normalizePosition(w.well_pos),
        type: normalizeSentinelType(w.sentinel_type),
      }));

    // If a position appears twice in sentinels, this plate is broken
    const byPos = new Map<string, string>();
    for (const s of sent) {
      if (byPos.has(s.position)) {
        // Duplicate sentinel position in same plate means not a valid scaffold pattern
        return null;
      }
      byPos.set(s.position, s.type);
    }
    return byPos;
  };

  for (const plateId of plateIds) {
    const byPos = plateSentinelMap(plateId);
    if (!byPos) return false;

    // Must have exact size
    if (byPos.size !== expectedSize) return false;

    // Must have exact same positions
    const positions = Array.from(byPos.keys()).sort();
    if (positions.length !== expectedPositions.length) return false;
    for (let i = 0; i < expectedPositions.length; i++) {
      if (positions[i] !== expectedPositions[i]) return false;
    }

    // Must match expected type per position
    for (const pos of expectedPositions) {
      const expectedType = expectedByPos.get(pos);
      const actualType = byPos.get(pos);
      if (!expectedType || !actualType) return false;
      if (actualType !== expectedType) return false;
    }
  }

  return true;
}

export type ScaffoldHashItem = {
  position: string;
  type: string;
  compound: string;
  dose_uM: number;
};

/**
 * Format a number like Python's json.dumps does for floats.
 * - Integers get .0 appended (0 -> "0.0", 1 -> "1.0")
 * - Floats keep their decimal representation
 * - NaN/Infinity should never reach here (rejected upstream)
 */
function formatNumberPythonStyle(n: number): string {
  if (!Number.isFinite(n)) {
    throw new Error(`Invalid number for scaffold hash: ${n}`);
  }
  return Number.isInteger(n) ? `${n}.0` : String(n);
}

/**
 * Python-compatible canonical JSON: alphabetically sorted object keys, no whitespace.
 * Matches Python's json.dumps(sort_keys=True, separators=(',', ':'))
 *
 * Explicit serialization instead of relying on JSON.stringify quirks.
 *
 * Exported for testing to verify byte-for-byte match with Python.
 */
export function canonicalJsonPythonCompatible(items: ScaffoldHashItem[]): string {
  // Sort items by position
  const sortedItems = [...items].sort((a, b) => a.position.localeCompare(b.position));

  // Manually serialize each item with keys in alphabetical order: compound, dose_uM, position, type
  const serializedItems = sortedItems.map((item) => {
    // Escape strings for JSON (handle quotes, backslashes, control chars)
    const escapeString = (s: string) => JSON.stringify(s);

    return [
      '{',
      `"compound":${escapeString(item.compound)},`,
      `"dose_uM":${formatNumberPythonStyle(item.dose_uM)},`,
      `"position":${escapeString(item.position)},`,
      `"type":${escapeString(item.type)}`,
      '}',
    ].join('');
  });

  return `[${serializedItems.join(',')}]`;
}

function sha256_16hex(canonical: string): string {
  return crypto.createHash('sha256').update(canonical, 'utf8').digest('hex').slice(0, 16);
}

/**
 * Compute well-derived scaffold hash from actual sentinel wells (strict version).
 *
 * MUST match Python scaffold hash exactly when wells contain correct scaffold.
 *
 * Only considers expected scaffold positions. If wells contain the expected scaffold,
 * the hash will equal cfg.expectedScaffoldHash (byte-for-byte canonical match with Python).
 *
 * Returns:
 * - hash string if computable and consistent
 * - null if pattern doesn't match, or internal inconsistency detected
 */
export function computeWellDerivedScaffoldHashStrict(
  wells: Well[],
  cfg: ScaffoldInvariantConfig
): string | null {
  // First ensure the scaffold pattern is EXACTLY the expected scaffold
  if (!detectScaffoldPattern(wells, cfg)) return null;

  const sentinels = wells.filter((w) => w.is_sentinel);
  if (sentinels.length === 0) return null;

  // Build expected position set
  const expectedByPos = new Map<string, string>();
  for (const e of cfg.expectedScaffold) {
    expectedByPos.set(normalizePosition(e.position), normalizeSentinelType(e.type));
  }

  // For each expected position, find sentinel well and lock its compound/dose
  const byPos = new Map<string, ScaffoldHashItem>();

  for (const s of sentinels) {
    const pos = normalizePosition(s.well_pos);
    if (!expectedByPos.has(pos)) continue; // ignore non-expected sentinels

    // CRITICAL: Do NOT normalize sentinel_type case for hashing - must match Python spec exactly
    const item: ScaffoldHashItem = {
      position: pos,
      type: (s.sentinel_type ?? 'UNKNOWN').trim(), // trim but preserve case
      compound: s.compound,
      dose_uM: s.dose_uM,
    };

    const existing = byPos.get(pos);
    if (!existing) {
      byPos.set(pos, item);
      continue;
    }

    // Duplicate position is OK only if identical
    if (
      existing.type !== item.type ||
      existing.compound !== item.compound ||
      existing.dose_uM !== item.dose_uM
    ) {
      return null; // internal inconsistency
    }
  }

  // Must have exactly all expected positions represented
  if (byPos.size !== expectedByPos.size) return null;

  // Ensure types match expected for every position (normalize for comparison only)
  for (const [pos, expectedType] of expectedByPos.entries()) {
    const obs = byPos.get(pos);
    if (!obs) return null;
    if (normalizeSentinelType(obs.type) !== expectedType) return null;
  }

  const canonical = canonicalJsonPythonCompatible(Array.from(byPos.values()));
  return sha256_16hex(canonical);
}

function normalizePosition(pos: string): string {
  // Normalize "A2" -> "A02", "A02" -> "A02"
  if (!pos || pos.length < 2) return pos;
  const row = pos[0].toUpperCase();
  const col = pos.slice(1);
  return `${row}${col.padStart(2, '0')}`;
}

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
