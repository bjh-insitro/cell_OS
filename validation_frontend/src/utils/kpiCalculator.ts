/**
 * KPI calculator for gate and decision metrics.
 *
 * Source of truth: gate events from explicit gate_event/gate_loss, not state transitions.
 */

import type {
    RunArtifacts,
    GateKPIs,
    DecisionKPIs,
    GateEvent,
    DecisionEvent,
} from '../types/provenance.types';

export function calculateGateKPIs(artifacts: RunArtifacts): GateKPIs {
    const { gate_events, diagnostics, metadata } = artifacts;

    const noiseGateEvents = gate_events.filter(ev => ev.gate_name === 'noise_sigma');
    const noiseGateEarned = noiseGateEvents.find(ev => ev.event_type === 'gate_event');
    const noiseGateLosses = noiseGateEvents.filter(ev => ev.event_type === 'gate_loss');

    let gate_earned = false;
    let cycles_to_gate: number | null = null;
    let rel_width_at_gate: number | null = null;
    let df_at_gate: number | null = null;
    let gate_slack: number | null = null;

    if (noiseGateEarned) {
        gate_earned = true;
        cycles_to_gate = noiseGateEarned.cycle;

        // Find diagnostic at gate cycle
        const diagAtGate = diagnostics.data.find(d => d.cycle === noiseGateEarned.cycle);
        if (diagAtGate) {
            rel_width_at_gate = diagAtGate.rel_width;
            df_at_gate = diagAtGate.pooled_df;
            if (rel_width_at_gate !== null) {
                gate_slack = 0.25 - Math.abs(rel_width_at_gate);
            }
        }
    }

    const gate_loss_count = noiseGateLosses.length;

    // Calculate time in gate vs out of gate
    // Use decisions to track regime
    const decisions = artifacts.decisions.data;
    let time_in_gate_cycles = 0;
    let time_out_gate_cycles = 0;

    decisions.forEach((dec: DecisionEvent) => {
        if (dec.selected_candidate.regime === 'in_gate') {
            time_in_gate_cycles++;
        } else if (
            dec.selected_candidate.regime === 'pre_gate' ||
            dec.selected_candidate.regime === 'gate_revoked'
        ) {
            time_out_gate_cycles++;
        }
    });

    const total_cycles = time_in_gate_cycles + time_out_gate_cycles;
    const time_in_gate_percent = total_cycles > 0 ? (time_in_gate_cycles / total_cycles) * 100 : 0;

    return {
        gate_earned,
        cycles_to_gate,
        rel_width_at_gate,
        df_at_gate,
        gate_slack,
        gate_loss_count,
        time_in_gate_cycles,
        time_out_gate_cycles,
        time_in_gate_percent,
    };
}

export function calculateDecisionKPIs(artifacts: RunArtifacts): DecisionKPIs {
    const { decisions } = artifacts;

    if (decisions.data.length === 0) {
        return {
            forced_calibration_rate: 0,
            first_in_gate_cycle: null,
            regime_distribution: {},
            abort_cycle: null,
            abort_template: null,
        };
    }

    const decisionData = decisions.data as DecisionEvent[];

    // Forced calibration rate
    const forced_count = decisionData.filter(d => d.selected_candidate.forced).length;
    const forced_calibration_rate = forced_count / decisionData.length;

    // First in-gate cycle
    const firstInGate = decisionData.find(d => d.selected_candidate.regime === 'in_gate');
    const first_in_gate_cycle = firstInGate ? firstInGate.cycle : null;

    // Regime distribution
    const regime_distribution: Record<string, number> = {};
    decisionData.forEach(d => {
        const regime = d.selected_candidate.regime;
        regime_distribution[regime] = (regime_distribution[regime] || 0) + 1;
    });

    // Abort info
    const abortDecision = decisionData.find(d => d.selected.startsWith('abort'));
    const abort_cycle = abortDecision ? abortDecision.cycle : null;
    const abort_template = abortDecision ? abortDecision.selected : null;

    return {
        forced_calibration_rate,
        first_in_gate_cycle,
        regime_distribution,
        abort_cycle,
        abort_template,
    };
}
