/**
 * Epistemic Provenance Demo Page
 *
 * Visualizes the "instrument regime" for epistemic agent runs:
 * - Pay-for-calibration constraints
 * - Gate events (earned/lost)
 * - Decision provenance with regime tracking
 * - Gate slack and stability metrics
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import RunPicker from './EpistemicProvenance/components/RunPicker';
import TimelineTracks from './EpistemicProvenance/components/TimelineTracks';
import DecisionReceiptPanel from './EpistemicProvenance/components/DecisionReceiptPanel';
import GateSlackPanel from './EpistemicProvenance/components/GateSlackPanel';
import type { RunArtifacts, IntegrityStatus, DecisionEvent, RunSummary } from '../types/provenance.types';
import {
    listAvailableRuns,
    loadRunMetadata,
    loadRunArtifacts,
    computeIntegrityStatus,
    computeRunSummary,
} from '../utils/provenanceLoader';
import { calculateGateKPIs, calculateDecisionKPIs } from '../utils/kpiCalculator';

// Semantic sort: gate_earned → aborted → completed_no_gate → legacy → integrity_error, newest first within each group
function sortRunsSemantically(summaries: RunSummary[]): RunSummary[] {
    const statusPriority: Record<string, number> = {
        gate_earned: 1,
        aborted: 2,
        completed_no_gate: 3,
        legacy: 4,
        integrity_error: 5,
    };

    return [...summaries].sort((a, b) => {
        const priorityDiff = statusPriority[a.status] - statusPriority[b.status];
        if (priorityDiff !== 0) return priorityDiff;
        // Within same status, newest first (reverse timestamp order)
        return b.timestamp.localeCompare(a.timestamp);
    });
}

const EpistemicProvenancePage: React.FC = () => {
    const navigate = useNavigate();
    const [isDarkMode, setIsDarkMode] = useState(false);

    const [runs, setRuns] = useState<RunSummary[]>([]);
    const [selectedRun, setSelectedRun] = useState<string | null>(null);
    const [artifacts, setArtifacts] = useState<RunArtifacts | null>(null);
    const [integrityStatus, setIntegrityStatus] = useState<IntegrityStatus>('no_data');
    const [loading, setLoading] = useState(false);
    const [loadingSummaries, setLoadingSummaries] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedCycle, setSelectedCycle] = useState<number | null>(null);

    // Load available runs on mount (with summaries)
    useEffect(() => {
        setLoadingSummaries(true);
        listAvailableRuns()
            .then(async (filenames) => {
                const summaries = await Promise.all(filenames.map(f => computeRunSummary(f)));
                const sorted = sortRunsSemantically(summaries);
                setRuns(sorted);
                setLoadingSummaries(false);
            })
            .catch((err) => {
                console.error('Failed to load run summaries:', err);
                setLoadingSummaries(false);
            });
    }, []);

    // Load artifacts when run is selected
    useEffect(() => {
        if (!selectedRun) {
            setArtifacts(null);
            setIntegrityStatus('no_data');
            return;
        }

        setLoading(true);
        setError(null);

        loadRunMetadata(selectedRun)
            .then((metadata) => loadRunArtifacts(metadata))
            .then((arts) => {
                setArtifacts(arts);
                setIntegrityStatus(computeIntegrityStatus(arts));
                setLoading(false);

                // Auto-select first cycle if available
                if (arts.decisions.data.length > 0) {
                    const firstDecision = arts.decisions.data[0] as DecisionEvent;
                    setSelectedCycle(firstDecision.cycle);
                }
            })
            .catch((err) => {
                setError((err as Error).message);
                setLoading(false);
            });
    }, [selectedRun]);

    const gateKPIs = artifacts ? calculateGateKPIs(artifacts) : null;
    const decisionKPIs = artifacts ? calculateDecisionKPIs(artifacts) : null;

    const selectedDecision =
        artifacts && selectedCycle
            ? (artifacts.decisions.data.find((d: any) => d.cycle === selectedCycle) as DecisionEvent) || null
            : null;

    return (
        <div
            className={`min-h-screen transition-colors duration-300 ${
                isDarkMode ? 'bg-gradient-to-b from-slate-900 to-slate-800' : 'bg-gradient-to-b from-zinc-50 to-white'
            }`}
        >
            {/* Header */}
            <div
                className={`backdrop-blur-sm border-b sticky top-0 z-50 transition-colors duration-300 ${
                    isDarkMode ? 'bg-slate-800/80 border-slate-700' : 'bg-white/80 border-zinc-200'
                }`}
            >
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <button
                                onClick={() => navigate('/')}
                                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${
                                    isDarkMode ? 'text-slate-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'
                                }`}
                            >
                                ← Back to Home
                            </button>
                            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                Epistemic Provenance Demo
                            </h1>
                            <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                Pay-for-calibration regime with gate events and decision receipts
                            </p>
                        </div>

                        {/* Dark Mode Toggle */}
                        <button
                            onClick={() => setIsDarkMode(!isDarkMode)}
                            className={`p-2 rounded-lg transition-all ${
                                isDarkMode
                                    ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                                    : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                            }`}
                            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                        >
                            {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="container mx-auto px-6 py-6">
                {/* Run Picker */}
                {loadingSummaries ? (
                    <div className={`p-4 border-b ${isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-zinc-200'}`}>
                        <p className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Loading runs...</p>
                    </div>
                ) : (
                    <RunPicker
                        runs={runs}
                        selectedRun={selectedRun}
                        onSelectRun={setSelectedRun}
                        integrityStatus={integrityStatus}
                        isDarkMode={isDarkMode}
                    />
                )}

                {/* Loading/Error States */}
                {loading && (
                    <div className="mt-8 text-center">
                        <p className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Loading run artifacts...</p>
                    </div>
                )}

                {error && (
                    <div className="mt-8 p-4 bg-red-100 text-red-800 rounded-lg">
                        <p className="font-semibold">Error loading run:</p>
                        <p className="text-sm">{error}</p>
                    </div>
                )}

                {/* Main Content */}
                {artifacts && !loading && (
                    <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Left: Timeline (spans 2 cols) */}
                        <div className={`lg:col-span-2 rounded-lg overflow-hidden ${isDarkMode ? 'bg-slate-800' : 'bg-white'} shadow-lg`}>
                            <TimelineTracks
                                artifacts={artifacts}
                                selectedCycle={selectedCycle}
                                onSelectCycle={setSelectedCycle}
                                isDarkMode={isDarkMode}
                            />
                        </div>

                        {/* Right: Decision Inspector */}
                        <div className={`rounded-lg overflow-hidden ${isDarkMode ? 'bg-slate-800' : 'bg-white'} shadow-lg`}>
                            <DecisionReceiptPanel
                                selectedCycle={selectedCycle}
                                decision={selectedDecision}
                                evidence={artifacts.evidence.data}
                                isDarkMode={isDarkMode}
                            />
                        </div>
                    </div>
                )}

                {/* Bottom: Gate Slack Panel */}
                {artifacts && gateKPIs && decisionKPIs && !loading && (
                    <div className={`mt-6 rounded-lg overflow-hidden ${isDarkMode ? 'bg-slate-800' : 'bg-white'} shadow-lg`}>
                        <GateSlackPanel gateKPIs={gateKPIs} decisionKPIs={decisionKPIs} isDarkMode={isDarkMode} />
                    </div>
                )}

                {/* Integrity Warnings */}
                {artifacts && artifacts.metadata.integrity_warnings && artifacts.metadata.integrity_warnings.length > 0 && (
                    <div className="mt-6 p-4 bg-yellow-100 text-yellow-900 rounded-lg">
                        <p className="font-semibold mb-2">Integrity Warnings:</p>
                        <ul className="list-disc list-inside text-sm space-y-1">
                            {artifacts.metadata.integrity_warnings.map((warning, idx) => (
                                <li key={idx}>{warning}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

export default EpistemicProvenancePage;
