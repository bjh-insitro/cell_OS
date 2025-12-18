/**
 * Hostile JSONL parser with strict validation and error surfacing.
 *
 * Design: Count and expose all failures. Never silently skip malformed data.
 */

import type { ParseResult } from '../types/provenance.types';

export function parseJSONL<T>(
    content: string,
    validator: (obj: any, lineNum: number) => T | null
): ParseResult<T> {
    const lines = content.split('\n').filter(line => line.trim().length > 0);
    const data: T[] = [];
    const errors: string[] = [];
    let malformed_count = 0;

    lines.forEach((line, idx) => {
        const lineNum = idx + 1;
        try {
            const obj = JSON.parse(line);
            const validated = validator(obj, lineNum);
            if (validated === null) {
                malformed_count++;
                errors.push(`Line ${lineNum}: Schema validation failed`);
            } else {
                data.push(validated);
            }
        } catch (e) {
            malformed_count++;
            errors.push(`Line ${lineNum}: JSON parse error - ${(e as Error).message}`);
        }
    });

    return {
        data,
        errors,
        malformed_count,
        total_lines: lines.length,
    };
}

export function validateEvidenceEvent(obj: any, lineNum: number): any | null {
    if (typeof obj !== 'object' || obj === null) return null;
    if (typeof obj.cycle !== 'number') return null;
    if (typeof obj.belief !== 'string') return null;
    // prev, new, evidence can be any type
    return obj;
}

export function validateDecisionEvent(obj: any, lineNum: number): any | null {
    if (typeof obj !== 'object' || obj === null) return null;
    if (typeof obj.cycle !== 'number') return null;
    if (typeof obj.selected !== 'string') return null;
    if (typeof obj.selected_score !== 'number') return null;
    if (typeof obj.reason !== 'string') return null;

    // Validate selected_candidate exists and has critical fields
    const cand = obj.selected_candidate;
    if (typeof cand !== 'object' || cand === null) return null;
    if (typeof cand.template !== 'string') return null;
    if (typeof cand.forced !== 'boolean') return null;
    if (typeof cand.trigger !== 'string') return null;
    if (typeof cand.regime !== 'string') return null;

    // gate_state must exist
    if (typeof cand.gate_state !== 'object' || cand.gate_state === null) return null;

    return obj;
}

export function validateDiagnosticEvent(obj: any, lineNum: number): any | null {
    if (typeof obj !== 'object' || obj === null) return null;
    if (typeof obj.cycle !== 'number') return null;
    if (typeof obj.pooled_df !== 'number') return null;
    if (typeof obj.pooled_sigma !== 'number') return null;
    if (typeof obj.noise_sigma_stable !== 'boolean') return null;
    return obj;
}
