/**
 * RunPicker: List and select available runs.
 */

import React from 'react';
import type { IntegrityStatus } from '../../../types/provenance.types';

interface RunPickerProps {
    runs: string[];
    selectedRun: string | null;
    onSelectRun: (runFile: string) => void;
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
                className={`w-full px-3 py-2 rounded-lg border text-sm font-mono ${
                    isDarkMode
                        ? 'bg-slate-700 border-slate-600 text-white'
                        : 'bg-white border-zinc-300 text-zinc-900'
                }`}
            >
                <option value="">-- Select a run --</option>
                {runs.map((runFile) => (
                    <option key={runFile} value={runFile}>
                        {runFile}
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
        </div>
    );
};

export default RunPicker;
