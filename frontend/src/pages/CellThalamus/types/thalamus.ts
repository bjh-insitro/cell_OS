/**
 * TypeScript types for Cell Thalamus Dashboard
 */

export interface Design {
  design_id: string;
  phase: number;
  cell_lines: string[];
  compounds: string[];
  status: 'running' | 'completed' | 'failed';
  created_at?: string;
}

export interface Result {
  result_id: number;
  design_id: string;
  well_id: string;
  cell_line: string;
  compound: string;
  dose_uM: number;
  timepoint_h: number;
  plate_id: string;
  day: number;
  operator: string;
  is_sentinel: boolean;
  morph_er: number;
  morph_mito: number;
  morph_nucleus: number;
  morph_actin: number;
  morph_rna: number;
  atp_signal: number;
}

export interface MorphologyData {
  matrix: number[][];
  well_ids: string[];
  channels: string[];
}

export interface DoseResponseData {
  doses: number[];
  values: number[];
  compound: string;
  cell_line: string;
  metric: string;
}

export interface VarianceComponent {
  source: string;
  variance: number;
  fraction: number;
}

export interface SuccessCriteria {
  biological_dominance: boolean;
  technical_minimal: boolean;
  sentinel_stable: boolean;
}

export interface VarianceAnalysis {
  design_id: string;
  metric: string;
  total_variance: number;
  biological_fraction: number;
  technical_fraction: number;
  components: VarianceComponent[];
  criteria: SuccessCriteria;
  pass_rate: number;
}

export interface SentinelPoint {
  plate_id: string;
  day: number;
  operator: string;
  value: number;
  is_outlier: boolean;
}

export interface SentinelData {
  sentinel_type: string;
  metric: string;
  mean: number;
  std: number;
  ucl: number;
  lcl: number;
  points: SentinelPoint[];
}

export interface PlateData extends Result {
  row: string;
  col: number;
}

export interface RunSimulationRequest {
  cell_lines: string[];
  compounds?: string[];
  mode: 'demo' | 'quick' | 'full';
}

export interface SimulationStatus {
  status: 'running' | 'completed' | 'failed';
  design_id: string;
  phase: number;
  cell_lines: string[];
  compounds: string[];
  mode: string;
  error?: string;
}
