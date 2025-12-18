/**
 * Provenance artifact loader.
 *
 * Non-negotiable: No filename guessing. Always use run.paths.* from JSON.
 */

import type {
    RunMetadata,
    RunArtifacts,
    IntegrityStatus,
    GateEvent,
    EvidenceEvent,
    RunSummary,
} from '../types/provenance.types';
import {
    parseJSONL,
    validateEvidenceEvent,
    validateDecisionEvent,
    validateDiagnosticEvent,
} from './jsonlParser';

// Configurable base path: defaults to demo dataset, override with VITE_RESULTS_BASE
const RESULTS_BASE = import.meta.env.VITE_RESULTS_BASE ?? '/demo_results/epistemic_agent';

export async function listAvailableRuns(): Promise<string[]> {
    try {
        // Try manifest file first (for dev/demo environments)
        const manifestResponse = await fetch(`${RESULTS_BASE}/runs_manifest.json`);
        if (manifestResponse.ok) {
            const runFiles: string[] = await manifestResponse.json();
            return runFiles.sort().reverse();
        }

        // Fallback: Try directory listing (for production with directory listings enabled)
        const response = await fetch(`${RESULTS_BASE}/`);
        if (!response.ok) throw new Error('Failed to list runs');

        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const links = Array.from(doc.querySelectorAll('a'));

        const runFiles = links
            .map(a => a.getAttribute('href'))
            .filter(href => href && href.match(/^run_.*\.json$/))
            .map(href => href!);

        // Sort by timestamp (descending - most recent first)
        return runFiles.sort().reverse();
    } catch (e) {
        console.error('Failed to list runs:', e);
        return [];
    }
}

export async function loadRunMetadata(runJsonFilename: string): Promise<RunMetadata> {
    const response = await fetch(`${RESULTS_BASE}/${runJsonFilename}`);
    if (!response.ok) throw new Error(`Failed to load ${runJsonFilename}`);
    return await response.json();
}

export async function loadRunArtifacts(metadata: RunMetadata): Promise<RunArtifacts> {
    const basePath = RESULTS_BASE;

    // Load evidence
    let evidenceResult;
    try {
        const evidenceFile = metadata.paths.evidence;
        const evidenceResponse = await fetch(`${basePath}/${evidenceFile}`);
        if (!evidenceResponse.ok) throw new Error('Evidence file not found');
        const evidenceText = await evidenceResponse.text();
        evidenceResult = parseJSONL(evidenceText, validateEvidenceEvent);
    } catch (e) {
        evidenceResult = { data: [], errors: [(e as Error).message], malformed_count: 0, total_lines: 0 };
    }

    // Load decisions (backward compatible: may not exist in legacy runs)
    let decisionsResult;
    try {
        const decisionsFile = metadata.paths.decisions;
        const decisionsResponse = await fetch(`${basePath}/${decisionsFile}`);
        if (!decisionsResponse.ok) throw new Error('Decisions file not found');
        const decisionsText = await decisionsResponse.text();
        decisionsResult = parseJSONL(decisionsText, validateDecisionEvent);
    } catch (e) {
        decisionsResult = { data: [], errors: [(e as Error).message], malformed_count: 0, total_lines: 0 };
    }

    // Load diagnostics
    let diagnosticsResult;
    try {
        const diagnosticsFile = metadata.paths.diagnostics;
        const diagnosticsResponse = await fetch(`${basePath}/${diagnosticsFile}`);
        if (!diagnosticsResponse.ok) throw new Error('Diagnostics file not found');
        const diagnosticsText = await diagnosticsResponse.text();
        diagnosticsResult = parseJSONL(diagnosticsText, validateDiagnosticEvent);
    } catch (e) {
        diagnosticsResult = { data: [], errors: [(e as Error).message], malformed_count: 0, total_lines: 0 };
    }

    // Extract gate events from evidence (source of truth)
    const gateEvents = extractGateEvents(evidenceResult.data);

    return {
        metadata,
        evidence: evidenceResult,
        decisions: decisionsResult,
        diagnostics: diagnosticsResult,
        gate_events: gateEvents,
    };
}

function extractGateEvents(evidence: any[]): GateEvent[] {
    return evidence
        .filter(ev => {
            const belief = ev.belief || '';
            return belief.startsWith('gate_event:') || belief.startsWith('gate_loss:');
        })
        .map(ev => {
            const belief = ev.belief || '';
            const isLoss = belief.startsWith('gate_loss:');
            const gateName = belief.substring(isLoss ? 10 : 11); // Remove prefix

            return {
                cycle: ev.cycle,
                gate_name: gateName,
                event_type: isLoss ? 'gate_loss' as const : 'gate_event' as const,
                evidence: ev.evidence || {},
            };
        });
}

export function computeIntegrityStatus(artifacts: RunArtifacts): IntegrityStatus {
    const { metadata, decisions } = artifacts;

    // No data case
    if (metadata.cycles_completed === 0 && !metadata.abort_reason) {
        return 'no_data';
    }

    // Aborted before any cycles
    if (metadata.abort_reason && metadata.cycles_completed === 0) {
        return 'ok_aborted';
    }

    // Has history but missing decisions -> legacy run
    if (metadata.cycles_completed > 0 && decisions.data.length === 0) {
        return 'missing_decisions_legacy';
    }

    // Explicit integrity warnings
    if (metadata.integrity_warnings && metadata.integrity_warnings.length > 0) {
        return 'integrity_error';
    }

    // Aborted with data
    if (metadata.abort_reason) {
        return 'ok_aborted';
    }

    return 'ok';
}

/**
 * Compute rich run summary for picker display.
 * Answers "which story?" - success/abort/integrity, regime, why it ended this way.
 */
export async function computeRunSummary(filename: string): Promise<RunSummary> {
    const metadata = await loadRunMetadata(filename);

    // Parse timestamp from run_id (e.g., "run_20251218_130825" -> "2025-12-18 13:08")
    const timestampMatch = metadata.run_id.match(/run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    const timestamp = timestampMatch
        ? `${timestampMatch[1]}-${timestampMatch[2]}-${timestampMatch[3]} ${timestampMatch[4]}:${timestampMatch[5]}`
        : metadata.run_id;

    // Load minimal artifacts to determine status
    const artifacts = await loadRunArtifacts(metadata);
    const { decisions, gate_events } = artifacts;

    // Determine status
    let status: RunSummary['status'];
    let regime_summary = '';
    let reason_line: string | null = null;
    let gate_slack: number | null = null;
    let time_in_gate_percent: number | null = null;

    // Check for integrity errors first
    if (metadata.integrity_warnings && metadata.integrity_warnings.length > 0) {
        status = 'integrity_error';
        regime_summary = 'integrity_error';
        reason_line = metadata.integrity_warnings[0];
    }
    // Check for legacy (no decisions)
    else if (metadata.cycles_completed > 0 && decisions.data.length === 0) {
        status = 'legacy';
        regime_summary = 'legacy (no decisions)';
        reason_line = 'Pre-v0.4.2 run without decision provenance';
    }
    // Check for abort
    else if (metadata.abort_reason) {
        status = 'aborted';
        const firstDecision = decisions.data[0] as any;
        const abortRegime = firstDecision?.selected_candidate?.regime || 'pre_gate';
        regime_summary = `${abortRegime} (abort)`;
        // Extract first line of abort reason
        reason_line = metadata.abort_reason.split('\n')[0].replace('ABORT EXPERIMENT: ', '');
    }
    // Check for gate earned
    else {
        const noiseGateEarned = gate_events.find(
            ev => ev.gate_name === 'noise_sigma' && ev.event_type === 'gate_event'
        );

        if (noiseGateEarned) {
            status = 'gate_earned';

            // Compute regime transitions
            const regimes = decisions.data.map((d: any) => d.selected_candidate?.regime).filter(Boolean);
            const uniqueRegimes = Array.from(new Set(regimes));
            regime_summary = uniqueRegimes.join(' → ');

            // Compute gate slack
            const diagAtGate = artifacts.diagnostics.data.find(d => d.cycle === noiseGateEarned.cycle);
            if (diagAtGate && diagAtGate.rel_width !== null) {
                gate_slack = 0.25 - Math.abs(diagAtGate.rel_width);
            }

            // Compute time in gate
            const inGateCycles = decisions.data.filter((d: any) => d.selected_candidate?.regime === 'in_gate').length;
            time_in_gate_percent = (inGateCycles / metadata.cycles_completed) * 100;

            reason_line = `Gate earned at cycle ${noiseGateEarned.cycle}`;
        } else {
            status = 'completed_no_gate';
            regime_summary = 'pre_gate (no gate earned)';
            reason_line = null;
        }
    }

    return {
        filename,
        timestamp,
        status,
        regime_summary,
        reason_line,
        budget: metadata.budget,
        cycles_completed: metadata.cycles_completed,
        gate_slack,
        time_in_gate_percent,
    };
}
