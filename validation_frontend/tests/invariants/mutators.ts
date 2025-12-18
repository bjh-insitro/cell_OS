/**
 * Systematic mutation functions for testing invariant detection
 *
 * Each mutator applies a specific "evil edit" to a design, returning a new
 * design that should trigger at least one violation.
 *
 * These are NOT random fuzzing - they're deterministic failure mode coverage.
 */

import type { Well, DesignMetadata } from '../../src/pages/CellThalamus/invariants/types';

export interface DesignWithMetadata {
  wells: Well[];
  metadata?: DesignMetadata;
}

/**
 * Delete the sentinel_schema.policy field (mystery design)
 */
export function mut_missing_policy(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  if (newDesign.metadata?.sentinel_schema) {
    delete newDesign.metadata.sentinel_schema.policy;
  }
  return newDesign;
}

/**
 * Change policy to something other than "fixed_scaffold"
 */
export function mut_wrong_policy(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  if (newDesign.metadata?.sentinel_schema) {
    newDesign.metadata.sentinel_schema.policy = 'adaptive_scaffold';
  }
  return newDesign;
}

/**
 * Delete the scaffold_metadata.scaffold_hash field
 */
export function mut_missing_scaffold_hash(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  if (newDesign.metadata?.sentinel_schema?.scaffold_metadata) {
    delete newDesign.metadata.sentinel_schema.scaffold_metadata.scaffold_hash;
  }
  return newDesign;
}

/**
 * Tamper with scaffold_hash value
 */
export function mut_wrong_scaffold_hash(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  if (newDesign.metadata?.sentinel_schema?.scaffold_metadata) {
    newDesign.metadata.sentinel_schema.scaffold_metadata.scaffold_hash = 'deadbeefcafebabe';
  }
  return newDesign;
}

/**
 * Change compound name for one sentinel position across ALL plates (breaks well-derived hash)
 */
export function mut_tamper_one_sentinel_compound(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  // Find first sentinel position (e.g., A02)
  const firstSentinel = newDesign.wells.find((w) => w.is_sentinel);
  if (!firstSentinel) return newDesign;

  const position = firstSentinel.well_pos;
  // Tamper ALL sentinels at this position across all plates
  newDesign.wells.forEach((w) => {
    if (w.is_sentinel && w.well_pos === position) {
      w.compound = 'TAMPERED_COMPOUND';
    }
  });
  return newDesign;
}

/**
 * Change dose for one sentinel position across ALL plates (breaks well-derived hash)
 */
export function mut_tamper_one_sentinel_dose(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  // Find first sentinel position
  const firstSentinel = newDesign.wells.find((w) => w.is_sentinel);
  if (!firstSentinel) return newDesign;

  const position = firstSentinel.well_pos;
  // Tamper ALL sentinels at this position across all plates
  newDesign.wells.forEach((w) => {
    if (w.is_sentinel && w.well_pos === position) {
      w.dose_uM = 999.999;
    }
  });
  return newDesign;
}

/**
 * Change sentinel type for one position (breaks scaffold type match)
 */
export function mut_tamper_one_sentinel_type(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstSentinel = newDesign.wells.find((w) => w.is_sentinel && w.sentinel_type === 'vehicle');
  if (firstSentinel) {
    firstSentinel.sentinel_type = 'ER_mid';
  }
  return newDesign;
}

/**
 * Swap two sentinel positions within a single plate (breaks scaffold position match)
 */
export function mut_swap_two_sentinel_positions_within_plate(
  design: DesignWithMetadata
): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstPlate = newDesign.wells[0]?.plate_id;
  if (!firstPlate) return newDesign;

  const sentinels = newDesign.wells.filter((w) => w.is_sentinel && w.plate_id === firstPlate);
  if (sentinels.length >= 2) {
    const temp = sentinels[0].well_pos;
    sentinels[0].well_pos = sentinels[1].well_pos;
    sentinels[1].well_pos = temp;
  }
  return newDesign;
}

/**
 * Remove one sentinel from first plate (breaks scaffold stability)
 */
export function mut_remove_one_sentinel_from_first_plate(
  design: DesignWithMetadata
): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstPlate = newDesign.wells[0]?.plate_id;
  if (!firstPlate) return newDesign;

  const firstSentinelIdx = newDesign.wells.findIndex(
    (w) => w.is_sentinel && w.plate_id === firstPlate
  );
  if (firstSentinelIdx >= 0) {
    newDesign.wells.splice(firstSentinelIdx, 1);
  }
  return newDesign;
}

/**
 * Change one sentinel position on second plate only (breaks scaffold stability)
 */
export function mut_diverge_scaffold_on_second_plate(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const plates = Array.from(new Set(newDesign.wells.map((w) => w.plate_id))).sort();
  if (plates.length < 2) return newDesign;

  const secondPlate = plates[1];
  const firstSentinel = newDesign.wells.find((w) => w.is_sentinel && w.plate_id === secondPlate);
  if (firstSentinel) {
    firstSentinel.well_pos = 'Z99'; // Invalid position
  }
  return newDesign;
}

/**
 * Add duplicate well (same plate_id + well_pos)
 */
export function mut_add_duplicate_well(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstWell = newDesign.wells[0];
  if (firstWell) {
    newDesign.wells.push({ ...firstWell });
  }
  return newDesign;
}

/**
 * Add well in excluded corner position (e.g., A01)
 */
export function mut_add_well_in_excluded_corner(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstPlate = newDesign.wells[0]?.plate_id;
  if (!firstPlate) return newDesign;

  newDesign.wells.push({
    plate_id: firstPlate,
    well_pos: 'A01',
    cell_line: 'A549',
    compound: 'DMSO',
    dose_uM: 0,
    is_sentinel: false,
    day: 1,
    operator: 'Operator_A',
    timepoint_h: 12,
  });
  return newDesign;
}

/**
 * Remove one experimental condition from one timepoint (breaks multiset)
 */
export function mut_remove_experimental_condition_from_one_timepoint(
  design: DesignWithMetadata
): DesignWithMetadata {
  const newDesign = deepClone(design);
  const experimentals = newDesign.wells.filter((w) => !w.is_sentinel);
  if (experimentals.length > 0) {
    const idx = newDesign.wells.indexOf(experimentals[0]);
    if (idx >= 0) {
      newDesign.wells.splice(idx, 1);
    }
  }
  return newDesign;
}

/**
 * Change compound for one experimental well (breaks position stability)
 */
export function mut_change_compound_for_experimental_position(
  design: DesignWithMetadata
): DesignWithMetadata {
  const newDesign = deepClone(design);
  const experimental = newDesign.wells.find((w) => !w.is_sentinel);
  if (experimental) {
    experimental.compound = 'TAMPERED_EXPERIMENTAL';
  }
  return newDesign;
}

/**
 * Change dose for one experimental well at same position (breaks position stability)
 */
export function mut_change_dose_for_experimental_position(
  design: DesignWithMetadata
): DesignWithMetadata {
  const newDesign = deepClone(design);
  const experimental = newDesign.wells.find((w) => !w.is_sentinel);
  if (experimental) {
    experimental.dose_uM = 123.456;
  }
  return newDesign;
}

/**
 * Concentrate all sentinels in one corner (breaks placement quality)
 */
export function mut_cluster_sentinels_in_corner(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const firstPlate = newDesign.wells[0]?.plate_id;
  if (!firstPlate) return newDesign;

  const sentinels = newDesign.wells.filter((w) => w.is_sentinel && w.plate_id === firstPlate);
  const cornerPositions = ['A02', 'A03', 'A04', 'B02', 'B03', 'B04', 'C02', 'C03', 'C04'];

  sentinels.forEach((s, i) => {
    if (i < cornerPositions.length) {
      s.well_pos = cornerPositions[i];
    }
  });
  return newDesign;
}

/**
 * Make first half of plates all Operator_A (breaks batch balance across plates)
 */
export function mut_unbalance_batch_operator(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const plates = Array.from(new Set(newDesign.wells.map((w) => w.plate_id))).sort();
  if (plates.length < 2) return newDesign;

  const halfPoint = Math.floor(plates.length / 2);
  const firstHalfPlates = new Set(plates.slice(0, halfPoint));

  // Make first half all Operator_A (creates confounding with other factors)
  newDesign.wells.forEach((w) => {
    if (firstHalfPlates.has(w.plate_id)) {
      w.operator = 'Operator_A';
    }
  });
  return newDesign;
}

/**
 * Make first half of plates all A549 (breaks batch balance across plates)
 */
export function mut_unbalance_batch_cell_line(design: DesignWithMetadata): DesignWithMetadata {
  const newDesign = deepClone(design);
  const plates = Array.from(new Set(newDesign.wells.map((w) => w.plate_id))).sort();
  if (plates.length < 2) return newDesign;

  const halfPoint = Math.floor(plates.length / 2);
  const firstHalfPlates = new Set(plates.slice(0, halfPoint));

  // Make first half all A549 (creates confounding with other factors)
  newDesign.wells.forEach((w) => {
    if (firstHalfPlates.has(w.plate_id)) {
      w.cell_line = 'A549';
    }
  });
  return newDesign;
}

/* ---------------- helpers ---------------- */

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}
