/**
 * TimelineTracks: Regime, Gate, and Noise tracks aligned by cycle.
 */

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { RunArtifacts, DecisionEvent, GateEvent, DiagnosticEvent } from '../../../types/provenance.types';

interface TimelineTracksProps {
    artifacts: RunArtifacts;
    selectedCycle: number | null;
    onSelectCycle: (cycle: number) => void;
    isDarkMode: boolean;
}

const TimelineTracks: React.FC<TimelineTracksProps> = ({
    artifacts,
    selectedCycle,
    onSelectCycle,
    isDarkMode,
}) => {
    const { decisions, gate_events, diagnostics } = artifacts;

    if (decisions.data.length === 0 && diagnostics.data.length === 0) {
        return (
            <div className={`p-8 text-center ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'}`}>
                No timeline data available.
            </div>
        );
    }

    const decisions_data = decisions.data as DecisionEvent[];
    const gate_events_data = gate_events as GateEvent[];
    const diagnostics_data = diagnostics.data as DiagnosticEvent[];

    // Build timeline data structure
    const maxCycle = Math.max(
        ...decisions_data.map(d => d.cycle),
        ...diagnostics_data.map(d => d.cycle),
        0
    );

    const timelineData = [];
    for (let cycle = 1; cycle <= maxCycle; cycle++) {
        const decision = decisions_data.find(d => d.cycle === cycle);
        const diagnostic = diagnostics_data.find(d => d.cycle === cycle);

        timelineData.push({
            cycle,
            decision,
            diagnostic,
        });
    }

    // Regime colors
    const regimeColors: Record<string, string> = {
        pre_gate: '#f59e0b',
        in_gate: '#10b981',
        gate_revoked: '#ef4444',
        integrity_error: '#8b5cf6',
        aborted: '#6b7280',
    };

    // Gate event markers
    const gateMarkers = gate_events_data.map(ev => ({
        cycle: ev.cycle,
        type: ev.event_type,
        gate: ev.gate_name,
    }));

    return (
        <div className="space-y-6 p-6">
            {/* Regime Track */}
            <div>
                <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    Decision Regime
                </h3>
                <div className="flex items-center gap-1 h-12">
                    {timelineData.map(({ cycle, decision }) => {
                        const regime = decision?.selected_candidate?.regime || 'unknown';
                        const forced = decision?.selected_candidate?.forced;
                        const isSelected = cycle === selectedCycle;

                        return (
                            <div
                                key={cycle}
                                onClick={() => onSelectCycle(cycle)}
                                className="flex-1 h-full cursor-pointer relative group"
                                style={{
                                    backgroundColor: regimeColors[regime] || '#9ca3af',
                                    opacity: isSelected ? 1 : 0.7,
                                    border: isSelected ? '2px solid white' : 'none',
                                }}
                                title={`Cycle ${cycle}: ${regime}${forced ? ' (forced)' : ''}`}
                            >
                                {forced && (
                                    <div className="absolute inset-0 flex items-center justify-center text-white text-xs font-bold">
                                        F
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
                <div className="flex justify-between mt-1 text-xs text-zinc-500">
                    <span>Cycle 1</span>
                    <span>Cycle {maxCycle}</span>
                </div>
            </div>

            {/* Gate Event Track */}
            <div>
                <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    Gate Events
                </h3>
                <div className="relative h-16 border-l border-r" style={{ borderColor: isDarkMode ? '#475569' : '#d4d4d8' }}>
                    {gateMarkers.map((marker, idx) => {
                        const position = ((marker.cycle - 1) / Math.max(1, maxCycle - 1)) * 100;
                        return (
                            <div
                                key={idx}
                                className="absolute top-0 bottom-0 w-1"
                                style={{
                                    left: `${position}%`,
                                    backgroundColor: marker.type === 'gate_event' ? '#10b981' : '#ef4444',
                                }}
                                title={`Cycle ${marker.cycle}: ${marker.type} (${marker.gate})`}
                            >
                                <div className={`absolute bottom-full mb-1 text-xs whitespace-nowrap ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                    {marker.type === 'gate_event' ? '✓' : '✗'}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Noise Track */}
            {diagnostics_data.length > 0 && (
                <div>
                    <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                        Noise Metrics
                    </h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={diagnostics_data}>
                            <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#475569' : '#e4e4e7'} />
                            <XAxis dataKey="cycle" stroke={isDarkMode ? '#94a3b8' : '#71717a'} />
                            <YAxis stroke={isDarkMode ? '#94a3b8' : '#71717a'} />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: isDarkMode ? '#1e293b' : '#ffffff',
                                    border: `1px solid ${isDarkMode ? '#475569' : '#d4d4d8'}`,
                                    color: isDarkMode ? '#f1f5f9' : '#18181b',
                                }}
                            />
                            <ReferenceLine y={0.25} stroke="#10b981" strokeDasharray="3 3" label="Enter (0.25)" />
                            <ReferenceLine y={0.40} stroke="#ef4444" strokeDasharray="3 3" label="Exit (0.40)" />
                            <Line type="monotone" dataKey="rel_width" stroke="#3b82f6" name="Rel Width" dot={false} />
                            <Line type="monotone" dataKey="pooled_sigma" stroke="#8b5cf6" name="Pooled Sigma" dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
};

export default TimelineTracks;
