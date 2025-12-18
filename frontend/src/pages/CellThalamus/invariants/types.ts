/**
 * Invariant checking types
 */

export type Severity = 'error' | 'warning';

export interface Violation {
  type: string;
  severity: Severity;
  message: string;
  suggestion?: string;
  plateId?: string;
  details?: Record<string, any>;
}

export interface Well {
  plate_id: string;
  well_pos: string;          // e.g. "A01"
  cell_line: string;
  compound: string;
  dose_uM: number;
  is_sentinel: boolean;
  sentinel_type?: string;    // e.g. "dmso", lowercase
  day?: number;
  operator?: string;
  timepoint_h?: number;
}

export interface DesignMetadata {
  sentinel_schema?: {
    policy?: string;
    scaffold_metadata?: {
      scaffold_id?: string;
      scaffold_version?: string;
      scaffold_hash?: string;
      scaffold_size?: number;
    };
  };
}

export interface DesignCertificate {
  seed?: number;
  paramsHash: string;
  invariantsVersion: string;
  plateFormat: 96 | 384;
  exclusions: {
    corners: boolean;
    midRow: boolean;
    edges: boolean;
  };
  timestamp: string;
  violations: Violation[];
  stats: {
    totalWells: number;
    sentinelWells: number;
    experimentalWells: number;
    nPlates: number;
  };
  scaffoldMetadata?: {
    expected: {
      scaffoldId: string;
      scaffoldHash: string;
      scaffoldSize: number;
    };
    observed?: {
      scaffoldId?: string;
      scaffoldHash?: string;
      scaffoldSize?: number;
      wellDerivedHash?: string; // computed from actual wells (strict, should match expected)
      wellDerivedMatchesExpected?: boolean; // true if wellDerivedHash === expectedScaffoldHash
    };
  };
}

export interface InvariantResult {
  passed: boolean;
  violations: Violation[];
  certificate: DesignCertificate;
}
