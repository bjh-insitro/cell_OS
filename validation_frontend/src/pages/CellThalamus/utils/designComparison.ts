/**
 * Utilities for comparing design parameters canonically
 */

import { parseNumberList, parseIntList, parseStringList } from './inputParsing';

export interface DesignParams {
  cellLines: string[];
  compounds: string[];
  doseMultipliers: number[];
  replicatesPerDose: number;
  days: number[];
  operators: string[];
  timepoints: number[];
  sentinels: {
    DMSO: number;
    tBHQ: number;
    thapsigargin: number;
    oligomycin: number;
    MG132: number;
  };
  plateFormat: 96 | 384;
  checkerboard: boolean;
  excludeCorners: boolean;
  excludeMidRowWells: boolean;
  excludeEdges: boolean;
}

/**
 * Parse raw form state into canonical design params
 */
export function parseDesignParams(formState: {
  selectedCellLines: string[];
  selectedCompounds: string[];
  doseMultipliers: string;
  replicatesPerDose: number;
  days: string;
  operators: string;
  timepoints: string;
  sentinelDMSO: number;
  sentinelTBHQ: number;
  sentinelThapsigargin: number;
  sentinelOligomycin: number;
  sentinelMG132: number;
  plateFormat: 96 | 384;
  checkerboard: boolean;
  excludeCorners: boolean;
  excludeMidRowWells: boolean;
  excludeEdges: boolean;
}): DesignParams {
  return {
    cellLines: [...formState.selectedCellLines].sort(),
    compounds: [...formState.selectedCompounds].sort(),
    doseMultipliers: parseNumberList(formState.doseMultipliers).sort((a, b) => a - b),
    replicatesPerDose: formState.replicatesPerDose,
    days: parseIntList(formState.days).sort((a, b) => a - b),
    operators: parseStringList(formState.operators).sort(),
    timepoints: parseNumberList(formState.timepoints).sort((a, b) => a - b),
    sentinels: {
      DMSO: formState.sentinelDMSO,
      tBHQ: formState.sentinelTBHQ,
      thapsigargin: formState.sentinelThapsigargin,
      oligomycin: formState.sentinelOligomycin,
      MG132: formState.sentinelMG132,
    },
    plateFormat: formState.plateFormat,
    checkerboard: formState.checkerboard,
    excludeCorners: formState.excludeCorners,
    excludeMidRowWells: formState.excludeMidRowWells,
    excludeEdges: formState.excludeEdges,
  };
}

/**
 * Quantize a number to N decimal places to avoid float precision issues
 * User types 0.1 or 0.10 → both become 0.1
 * User types 0.100000001 → becomes 0.1 (if decimals=1)
 */
function quantize(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

/**
 * Canonicalize design params for stable comparison
 * - Sorts object keys (stable JSON.stringify)
 * - Quantizes floats to avoid precision drift
 * - Returns a pure JSON-serializable value
 */
function canonicalizeForCompare(params: DesignParams): unknown {
  return {
    cellLines: params.cellLines, // already sorted
    checkerboard: params.checkerboard,
    compounds: params.compounds, // already sorted
    days: params.days, // already sorted
    doseMultipliers: params.doseMultipliers.map(d => quantize(d, 6)), // 6 decimals enough for dose multipliers
    excludeCorners: params.excludeCorners,
    excludeEdges: params.excludeEdges,
    excludeMidRowWells: params.excludeMidRowWells,
    operators: params.operators, // already sorted
    plateFormat: params.plateFormat,
    replicatesPerDose: params.replicatesPerDose,
    sentinels: {
      DMSO: params.sentinels.DMSO,
      MG132: params.sentinels.MG132,
      oligomycin: params.sentinels.oligomycin,
      tBHQ: params.sentinels.tBHQ,
      thapsigargin: params.sentinels.thapsigargin,
    }, // keys alphabetically sorted
    timepoints: params.timepoints.map(t => quantize(t, 3)), // 3 decimals enough for hours
  };
  // Keys are explicitly sorted alphabetically - stable regardless of construction order
}

/**
 * Deep equality check for design params
 * Uses canonical representation with stable key order and quantized floats
 */
export function designParamsEqual(a: DesignParams, b: DesignParams): boolean {
  const canonA = canonicalizeForCompare(a);
  const canonB = canonicalizeForCompare(b);
  return JSON.stringify(canonA) === JSON.stringify(canonB);
}

/**
 * Phase0 v2 canonical params for comparison
 */
export const PHASE0_V2_PARAMS: DesignParams = {
  cellLines: ['A549', 'HepG2'],
  compounds: [
    'CCCP',
    'H2O2',
    'MG132',
    'etoposide',
    'nocodazole',
    'oligomycin',
    'paclitaxel',
    'tBHQ',
    'thapsigargin',
    'tunicamycin',
  ].sort(),
  doseMultipliers: [0.1, 0.3, 1.0, 3.0, 10.0, 30.0],
  replicatesPerDose: 2,
  days: [1, 2],
  operators: ['Operator_A', 'Operator_B'],
  timepoints: [12.0, 24.0, 48.0],
  sentinels: {
    DMSO: 8,
    tBHQ: 5,
    thapsigargin: 5,
    oligomycin: 5,
    MG132: 5,
  },
  plateFormat: 96,
  checkerboard: false,
  excludeCorners: true,
  excludeMidRowWells: true,
  excludeEdges: false,
};
