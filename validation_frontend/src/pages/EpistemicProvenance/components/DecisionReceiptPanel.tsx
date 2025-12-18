/**
 * DecisionReceiptPanel: Inspect decision details for a selected cycle.
 */

import React from 'react';
import type { DecisionEvent, EvidenceEvent } from '../../../types/provenance.types';

interface DecisionReceiptPanelProps {
    selectedCycle: number | null;
    decision: DecisionEvent | null;
    evidence: EvidenceEvent[];
    isDarkMode: boolean;
}

const DecisionReceiptPanel: React.FC<DecisionReceiptPanelProps> = ({
    selectedCycle,
    decision,
    evidence,
    isDarkMode,
}) => {
    if (!selectedCycle) {
        return (
            <div className={`p-6 h-full flex items-center justify-center ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'}`}>
                <p className="text-sm">Click a cycle to view decision details</p>
            </div>
        );
    }

    if (!decision) {
        return (
            <div className={`p-6 h-full ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                <h3 className="text-lg font-semibold mb-2">Cycle {selectedCycle}</h3>
                <p className="text-sm text-yellow-600">No decision record available for this cycle.</p>
            </div>
        );
    }

    const cand = decision.selected_candidate;

    // Find evidence events for this cycle
    const cycleEvidence = evidence.filter(ev => ev.cycle === selectedCycle);

    return (
        <div className={`p-6 h-full overflow-y-auto ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-50'}`}>
            <h3 className={`text-lg font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                Cycle {selectedCycle} Decision
            </h3>

            {/* Template */}
            <div className="mb-4">
                <div className="text-xs font-semibold text-zinc-500 uppercase mb-1">Template</div>
                <div className={`text-sm font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {decision.selected}
                </div>
            </div>

            {/* Reason */}
            <div className="mb-4">
                <div className="text-xs font-semibold text-zinc-500 uppercase mb-1">Reason</div>
                <div className={`text-sm ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    {decision.reason}
                </div>
            </div>

            {/* Regime Badge */}
            <div className="mb-4 flex items-center gap-2">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                    cand.regime === 'in_gate'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : cand.regime === 'pre_gate'
                        ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
                        : cand.regime === 'gate_revoked'
                        ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                }`}>
                    {cand.regime}
                </span>

                {cand.forced && (
                    <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                        FORCED
                    </span>
                )}

                <span className={`px-2 py-1 rounded text-xs font-medium ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-200 text-zinc-700'}`}>
                    {cand.trigger}
                </span>
            </div>

            {/* Gate State */}
            <div className="mb-4">
                <div className="text-xs font-semibold text-zinc-500 uppercase mb-1">Gate State</div>
                <div className={`text-sm space-y-1 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    <div>Noise: <span className="font-mono">{cand.gate_state.noise_sigma}</span></div>
                    {cand.gate_state.edge_effect && (
                        <div>Edge: <span className="font-mono">{cand.gate_state.edge_effect}</span></div>
                    )}
                </div>
            </div>

            {/* Calibration Plan */}
            {cand.calibration_plan && (
                <div className="mb-4">
                    <div className="text-xs font-semibold text-zinc-500 uppercase mb-1">Calibration Plan</div>
                    <div className={`text-sm font-mono space-y-1 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                        <div>df_current: {cand.calibration_plan.df_current}</div>
                        <div>df_needed: {cand.calibration_plan.df_needed}</div>
                        <div>wells_needed: {cand.calibration_plan.wells_needed}</div>
                        <div>rel_width: {cand.calibration_plan.rel_width?.toFixed(4) || 'null'}</div>
                    </div>
                </div>
            )}

            {/* Evidence Breadcrumb */}
            {cycleEvidence.length > 0 && (
                <div className="mt-6 pt-4 border-t" style={{ borderColor: isDarkMode ? '#475569' : '#e4e4e7' }}>
                    <div className="text-xs font-semibold text-zinc-500 uppercase mb-2">Evidence (This Cycle)</div>
                    <div className="space-y-2">
                        {cycleEvidence.map((ev, idx) => (
                            <div
                                key={idx}
                                className={`text-xs p-2 rounded ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-100 text-zinc-700'}`}
                            >
                                <div className="font-mono font-semibold">{ev.belief}</div>
                                {ev.note && <div className="mt-1 text-xs">{ev.note}</div>}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default DecisionReceiptPanel;
