/**
 * RunPicker: List and select available runs.
 *
 * Answers "which story?" not "which file?":
 * - Status badge (gate earned, aborted, etc.)
 * - Regime summary (pre_gate → in_gate)
 * - Why it ended this way (abort reason or gate info)
 * - Budget + cycles context
 */

import React from 'react';
import type { IntegrityStatus, RunSummary } from '../../../types/provenance.types';

interface RunPickerProps {
    runs: RunSummary[];
    selectedRun: string | null;
    onSelectRun: (runFilename: string) => void;
    integrityStatus: IntegrityStatus;
    isDarkMode: boolean;
}

const RunPicker: React.FC<RunPickerProps> = ({
    runs,
    selectedRun,
    onSelectRun,
    integrityStatus,
    isDarkMode,
}) => {
    const getStatusBadge = (status: RunSummary['status']) => {
        const badges = {
            gate_earned: { emoji: '🟩', text: 'Gate earned', color: 'text-green-600' },
            aborted: { emoji: '🟥', text: 'Aborted', color: 'text-red-600' },
            integrity_error: { emoji: '🟪', text: 'Integrity error', color: 'text-purple-600' },
            completed_no_gate: { emoji: '🟨', text: 'No gate', color: 'text-yellow-600' },
            legacy: { emoji: '🟦', text: 'Legacy', color: 'text-blue-600' },
        };

        const badge = badges[status];
        return (
            <span className={`font-semibold ${badge.color}`}>
                {badge.emoji} {badge.text}
            </span>
        );
    };

    const getIntegrityPill = (status: IntegrityStatus) => {
        const styles: Record<IntegrityStatus, string> = {
            ok: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
            ok_aborted: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
            integrity_error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
            missing_decisions_legacy: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
            no_data: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
        };

        const labels: Record<IntegrityStatus, string> = {
            ok: '✓ OK',
            ok_aborted: '⚠ Aborted',
            integrity_error: '✗ Integrity Error',
            missing_decisions_legacy: '⚠ Legacy (No Decisions)',
            no_data: '○ No Data',
        };

        return (
            <span className={`px-2 py-1 rounded text-xs font-medium ${styles[status]}`}>
                {labels[status]}
            </span>
        );
    };

    // Format run summary as compact label
    const formatRunLabel = (summary: RunSummary): string => {
        const parts = [
            `Run ${summary.timestamp}`,
            `${summary.status === 'gate_earned' ? '🟩' : summary.status === 'aborted' ? '🟥' : '🟦'}`,
            summary.regime_summary,
            `budget=${summary.budget}`,
            `cycles=${summary.cycles_completed}`,
        ];

        if (summary.gate_slack !== null) {
            parts.push(`slack=${summary.gate_slack.toFixed(3)}`);
        }

        if (summary.reason_line) {
            parts.push(`| ${summary.reason_line}`);
        }

        return parts.join(' · ');
    };

    return (
        <div className={`p-4 border-b ${isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-zinc-200'}`}>
            <div className="flex items-center justify-between mb-3">
                <h2 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    Select Run
                </h2>
                {selectedRun && getIntegrityPill(integrityStatus)}
            </div>

            <select
                value={selectedRun || ''}
                onChange={(e) => onSelectRun(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg border text-sm ${
                    isDarkMode
                        ? 'bg-slate-700 border-slate-600 text-white'
                        : 'bg-white border-zinc-300 text-zinc-900'
                }`}
            >
                <option value="">-- Select a run --</option>
                {runs.map((summary) => (
                    <option key={summary.filename} value={summary.filename}>
                        {formatRunLabel(summary)}
                    </option>
                ))}
            </select>

            {runs.length === 0 && (
                <div className={`mt-4 p-4 rounded-lg ${isDarkMode ? 'bg-slate-700' : 'bg-zinc-100'}`}>
                    <p className={`text-sm ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                        No runs found. Generate a run:
                    </p>
                    <code className={`block mt-2 text-xs p-2 rounded ${isDarkMode ? 'bg-slate-900 text-green-400' : 'bg-zinc-200 text-zinc-900'}`}>
                        python scripts/run_epistemic_agent.py --cycles 5 --budget 200 --seed 42
                    </code>
                </div>
            )}

            {/* Show selected run details if available */}
            {selectedRun && runs.length > 0 && (
                <div className={`mt-4 p-3 rounded-lg ${isDarkMode ? 'bg-slate-700' : 'bg-zinc-100'}`}>
                    {(() => {
                        const summary = runs.find(r => r.filename === selectedRun);
                        if (!summary) return null;

                        return (
                            <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                    {getStatusBadge(summary.status)}
                                    <span className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        {summary.timestamp}
                                    </span>
                                </div>
                                <div className={`text-sm ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                    {summary.regime_summary} · budget={summary.budget} · cycles={summary.cycles_completed}
                                </div>
                                {summary.reason_line && (
                                    <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        {summary.reason_line}
                                    </div>
                                )}
                                {summary.gate_slack !== null && (
                                    <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        Gate slack: {summary.gate_slack.toFixed(4)} · Time in gate: {summary.time_in_gate_percent?.toFixed(0)}%
                                    </div>
                                )}
                            </div>
                        );
                    })()}
                </div>
            )}
        </div>
    );
};

export default RunPicker;
