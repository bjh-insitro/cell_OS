/**
 * Type definitions for experimental design data
 */

export type PlateMode = 'full' | 'v2_split';

export interface Well {
  plate_id: string;
  well_pos: string;
  cell_line: string;
  compound: string;
  dose_uM: number;
  timepoint_h?: number;
  operator?: string;
  day?: number;
  is_sentinel: boolean;
  sentinel_type?: string;
  row?: string;
  col?: number;
  well_id?: string;
}

export interface DesignMetadata {
  generated_at_utc?: string;
  generator?: string;
  cell_lines: string[];
  compounds?: string[];
  n_doses: number;
  dose_multipliers: number[];
  replicates_per_dose: number;
  days: number[];
  operators: string[];
  timepoints_h: number[];
  plate_format: 96 | 384;
  checkerboard: boolean;
  exclude_corners: boolean;
  exclude_edges: boolean;
  n_plates: number;
  wells_per_plate: number;
  total_wells: number;
  n_compounds?: number;
  n_cell_lines?: number;
}

export interface DesignData {
  design_id: string;
  design_type: string;
  description: string;
  metadata: DesignMetadata;
  wells: Well[];
}

export interface WellStats {
  experimentalWells: number;
  sentinelWells: number;
  totalWells: number;
  nPlates: number;
  wellsPerPlate: number;
  availableWells: number;
  fits: boolean;
}
