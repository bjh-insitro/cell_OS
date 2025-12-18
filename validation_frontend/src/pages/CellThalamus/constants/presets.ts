/**
 * Centralized preset definitions for design generator
 */

export const PRESET_IDS = {
  PHASE0_V2: 'phase0_founder_v2_controls_stratified',
} as const;

export type PresetId = typeof PRESET_IDS[keyof typeof PRESET_IDS];

/**
 * Form state for a preset
 */
export interface PresetFormState {
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
}

/**
 * Phase0 v2 preset form state
 */
export const PHASE0_V2_FORM_STATE: PresetFormState = {
  selectedCellLines: ['A549', 'HepG2'],
  selectedCompounds: [
    'tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
    'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel'
  ],
  doseMultipliers: '0.1, 0.3, 1.0, 3.0, 10.0, 30.0',
  replicatesPerDose: 2,
  days: '1, 2',
  operators: 'Operator_A, Operator_B',
  timepoints: '12.0, 24.0, 48.0',
  sentinelDMSO: 8,
  sentinelTBHQ: 5,
  sentinelThapsigargin: 5,
  sentinelOligomycin: 5,
  sentinelMG132: 5,
  plateFormat: 96,
  checkerboard: false,
  excludeCorners: true,
  excludeMidRowWells: true,
  excludeEdges: false,
};

/**
 * Registry of all available presets
 */
export const PRESET_REGISTRY: Record<PresetId, PresetFormState> = {
  [PRESET_IDS.PHASE0_V2]: PHASE0_V2_FORM_STATE,
};
