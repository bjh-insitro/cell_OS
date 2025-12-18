/**
 * Type definitions for epistemic agent provenance artifacts.
 *
 * v0.4.2: Pay-for-calibration regime with gate events and decision receipts.
 */

export interface RunMetadata {
    run_id: string;
    budget: number;
    max_cycles: number;
    seed: number;
    cycles_completed: number;
    abort_reason: string | null;
    paths: {
        log: string;
        json: string;
        evidence: string;
        decisions: string;
        diagnostics: string;
    };
    beliefs_final: Record<string, any>;
    integrity_warnings?: string[];
}

export interface EvidenceEvent {
    cycle: number;
    belief: string;
    prev: any;
    new: any;
    evidence: Record<string, any>;
    supporting_conditions?: string[];
    note?: string;
}

export interface DecisionEvent {
    cycle: number;
    candidates: Array<Record<string, any>>;
    selected: string;
    selected_score: number;
    selected_candidate: {
        template: string;
        forced: boolean;
        trigger: 'must_calibrate' | 'gate_lock' | 'scoring' | 'abort';
        regime: 'pre_gate' | 'in_gate' | 'gate_revoked' | 'integrity_error' | 'aborted';
        gate_state: {
            noise_sigma: 'earned' | 'lost' | 'unknown' | 'corrupted';
            edge_effect?: 'earned' | 'lost' | 'unknown';
        };
        calibration_plan?: {
            df_current: number;
            df_needed: number;
            wells_needed: number;
            rel_width: number | null;
        };
        [key: string]: any;
    };
    reason: string;
}

export interface DiagnosticEvent {
    cycle: number;
    condition_key: string;
    n_wells: number;
    std_cycle: number;
    mean_cycle: number;
    pooled_df: number;
    pooled_sigma: number;
    ci_low: number | null;
    ci_high: number | null;
    rel_width: number | null;
    drift_metric: number | null;
    noise_sigma_stable: boolean;
    enter_threshold: number;
    exit_threshold: number;
    df_min: number;
    drift_threshold: number;
}

export interface GateEvent {
    cycle: number;
    gate_name: string;
    event_type: 'gate_event' | 'gate_loss';
    evidence: Record<string, any>;
}

export interface ParseResult<T> {
    data: T[];
    errors: string[];
    malformed_count: number;
    total_lines: number;
}

export interface RunArtifacts {
    metadata: RunMetadata;
    evidence: ParseResult<EvidenceEvent>;
    decisions: ParseResult<DecisionEvent>;
    diagnostics: ParseResult<DiagnosticEvent>;
    gate_events: GateEvent[];
}

export interface GateKPIs {
    gate_earned: boolean;
    cycles_to_gate: number | null;
    rel_width_at_gate: number | null;
    df_at_gate: number | null;
    gate_slack: number | null;
    gate_loss_count: number;
    time_in_gate_cycles: number;
    time_out_gate_cycles: number;
    time_in_gate_percent: number;
}

export interface DecisionKPIs {
    forced_calibration_rate: number;
    first_in_gate_cycle: number | null;
    regime_distribution: Record<string, number>;
    abort_cycle: number | null;
    abort_template: string | null;
}

export type IntegrityStatus =
    | 'ok'
    | 'ok_aborted'
    | 'integrity_error'
    | 'missing_decisions_legacy'
    | 'no_data';

/**
 * Run summary for picker display - answers "which story?" not "which file?"
 */
export interface RunSummary {
    filename: string;
    timestamp: string; // Human-readable: "2025-12-18 13:08"
    status: 'gate_earned' | 'aborted' | 'integrity_error' | 'completed_no_gate' | 'legacy';
    regime_summary: string; // e.g., "pre_gate → in_gate" or "pre_gate (abort)"
    reason_line: string | null; // Abort reason (first line) or gate cycle info
    budget: number;
    cycles_completed: number;
    gate_slack: number | null; // Only for gate_earned runs
    time_in_gate_percent: number | null; // Only for gate_earned runs
}
