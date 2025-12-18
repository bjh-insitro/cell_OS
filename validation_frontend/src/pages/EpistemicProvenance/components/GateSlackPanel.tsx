/**
 * GateSlackPanel: Display gate metrics summary.
 */

import React from 'react';
import type { GateKPIs, DecisionKPIs } from '../../../types/provenance.types';

interface GateSlackPanelProps {
    gateKPIs: GateKPIs;
    decisionKPIs: DecisionKPIs;
    isDarkMode: boolean;
}

const GateSlackPanel: React.FC<GateSlackPanelProps> = ({
    gateKPIs,
    decisionKPIs,
    isDarkMode,
}) => {
    const MetricCard: React.FC<{ label: string; value: string | number; sublabel?: string; color?: string }> = ({
        label,
        value,
        sublabel,
        color = isDarkMode ? 'text-slate-300' : 'text-zinc-700',
    }) => (
        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-700' : 'bg-zinc-100'}`}>
            <div className="text-xs font-semibold text-zinc-500 uppercase mb-1">{label}</div>
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            {sublabel && <div className="text-xs text-zinc-500 mt-1">{sublabel}</div>}
        </div>
    );

    return (
        <div className={`p-6 border-t ${isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-zinc-200'}`}>
            <h3 className={`text-lg font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                Gate & Decision Metrics
            </h3>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Gate Earned */}
                <MetricCard
                    label="Gate Status"
                    value={gateKPIs.gate_earned ? '✓ Earned' : '✗ Not Earned'}
                    color={gateKPIs.gate_earned ? 'text-green-600' : 'text-red-600'}
                />

                {/* Cycles to Gate */}
                <MetricCard
                    label="Cycles to Gate"
                    value={gateKPIs.cycles_to_gate !== null ? gateKPIs.cycles_to_gate : 'N/A'}
                    sublabel={gateKPIs.cycles_to_gate ? `Earned at cycle ${gateKPIs.cycles_to_gate}` : undefined}
                />

                {/* Gate Slack */}
                <MetricCard
                    label="Gate Slack"
                    value={
                        gateKPIs.gate_slack !== null
                            ? (gateKPIs.gate_slack >= 0 ? '+' : '') + gateKPIs.gate_slack.toFixed(4)
                            : 'N/A'
                    }
                    sublabel={
                        gateKPIs.gate_slack !== null
                            ? gateKPIs.gate_slack > 0.10
                                ? 'Comfortable'
                                : gateKPIs.gate_slack > 0
                                ? 'Tight'
                                : 'At threshold'
                            : undefined
                    }
                    color={
                        gateKPIs.gate_slack !== null
                            ? gateKPIs.gate_slack > 0.10
                                ? 'text-green-600'
                                : gateKPIs.gate_slack > 0
                                ? 'text-yellow-600'
                                : 'text-red-600'
                            : isDarkMode
                            ? 'text-slate-300'
                            : 'text-zinc-700'
                    }
                />

                {/* Gate Flapping */}
                <MetricCard
                    label="Gate Flapping"
                    value={`${gateKPIs.gate_loss_count} loss${gateKPIs.gate_loss_count !== 1 ? 'es' : ''}`}
                    color={gateKPIs.gate_loss_count === 0 ? 'text-green-600' : 'text-yellow-600'}
                />

                {/* Time in Gate */}
                <MetricCard
                    label="Time in Gate"
                    value={`${gateKPIs.time_in_gate_percent.toFixed(0)}%`}
                    sublabel={`${gateKPIs.time_in_gate_cycles} of ${gateKPIs.time_in_gate_cycles + gateKPIs.time_out_gate_cycles} cycles`}
                />

                {/* Forced Calibration Rate */}
                <MetricCard
                    label="Forced Rate"
                    value={`${(decisionKPIs.forced_calibration_rate * 100).toFixed(0)}%`}
                    sublabel="Decisions forced by constraints"
                />

                {/* DF at Gate */}
                {gateKPIs.df_at_gate !== null && (
                    <MetricCard label="DF at Gate" value={gateKPIs.df_at_gate} sublabel="Degrees of freedom" />
                )}

                {/* Rel Width at Gate */}
                {gateKPIs.rel_width_at_gate !== null && (
                    <MetricCard
                        label="Rel Width at Gate"
                        value={Math.abs(gateKPIs.rel_width_at_gate).toFixed(4)}
                        sublabel="At gate earn event"
                    />
                )}
            </div>

            {/* Regime Distribution */}
            {Object.keys(decisionKPIs.regime_distribution).length > 0 && (
                <div className="mt-6">
                    <div className="text-sm font-semibold text-zinc-500 uppercase mb-2">Regime Distribution</div>
                    <div className="flex gap-2 flex-wrap">
                        {Object.entries(decisionKPIs.regime_distribution).map(([regime, count]) => (
                            <div
                                key={regime}
                                className={`px-3 py-1 rounded text-sm ${
                                    isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-200 text-zinc-700'
                                }`}
                            >
                                <span className="font-mono">{regime}</span>: {count}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default GateSlackPanel;
