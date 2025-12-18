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
                            <p className={`mt-1 max-w-3xl text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                <strong>Pay-for-calibration regime:</strong> The system only acts when it can statistically justify its conclusions.
                                Gate events mark when noise calibration meets thresholds. Aborts are first-class decisions - refusing to act
                                when reliability can't be guaranteed.
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {['gate thresholds', 'regime tracking', 'forced decisions', 'abort provenance', 'gate slack', 'calibration plans'].map((concept) => (
                                    <span
                                        key={concept}
                                        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs shadow-sm ${
                                            isDarkMode
                                                ? 'border-slate-600 bg-slate-700 text-slate-300'
                                                : 'border-zinc-200 bg-white text-zinc-700'
                                        }`}
                                    >
                                        {concept}
                                    </span>
                                ))}
                            </div>
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
                {/* How It Works - Always visible first */}
                <div className={`mb-6 rounded-lg border ${isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-zinc-200'} shadow-lg overflow-hidden`}>
                    <div className={`p-6 border-b ${isDarkMode ? 'border-slate-700 bg-slate-800/50' : 'border-zinc-200 bg-zinc-50'}`}>
                        <h2 className={`text-2xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                            How the Epistemic Agent Decides
                        </h2>
                        <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                            Each cycle, the system evaluates what it can do given constraints, chooses an action, and updates its confidence.
                        </p>
                    </div>

                    {/* Walkthrough Example */}
                    <div className="p-6 space-y-6">
                        {/* Step 1: Starting State */}
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-indigo-900 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
                                Step 1: Check Current State
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Budget</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>384 wells</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Gate Status</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>❌ Not earned</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Noise (rel_width)</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>0.38</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Regime</div>
                                        <div className={`font-mono text-orange-600`}>pre_gate</div>
                                    </div>
                                </div>
                                <p className={`mt-3 text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                    <strong>Interpretation:</strong> Noise is too high (0.38 &gt; 0.25 threshold). System cannot make reliable biological conclusions yet.
                                </p>
                            </div>
                        </div>

                        {/* Step 2: Available Options */}
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'}`}>
                                Step 2: Evaluate Options
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <div className="space-y-3">
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-orange-500' : 'bg-orange-50 border-orange-500'}`}>
                                        <div className="flex items-center justify-between mb-2">
                                            <div className={`font-semibold text-sm ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>calibrate_noise_sigma</div>
                                            <div className={`text-xs px-2 py-1 rounded ${isDarkMode ? 'bg-orange-900 text-orange-300' : 'bg-orange-200 text-orange-800'}`}>Must do this first</div>
                                        </div>
                                        <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            Cost: 156 wells (12 doses × 13 replicates) • Will reduce rel_width to ~0.22
                                        </div>
                                    </div>
                                    <div className={`p-3 rounded border-l-4 opacity-50 ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-zinc-50 border-zinc-300'}`}>
                                        <div className="flex items-center justify-between mb-2">
                                            <div className={`font-semibold text-sm ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>measure_biomarker</div>
                                            <div className={`text-xs px-2 py-1 rounded ${isDarkMode ? 'bg-red-900 text-red-300' : 'bg-red-100 text-red-700'}`}>Blocked</div>
                                        </div>
                                        <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            Cannot run: Gate not earned. Would produce unreliable results.
                                        </div>
                                    </div>
                                    <div className={`p-3 rounded border-l-4 opacity-50 ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-zinc-50 border-zinc-300'}`}>
                                        <div className="flex items-center justify-between mb-2">
                                            <div className={`font-semibold text-sm ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>abort</div>
                                            <div className={`text-xs px-2 py-1 rounded ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-200 text-zinc-700'}`}>Available</div>
                                        </div>
                                        <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            Would trigger if: Budget insufficient for calibration (need 156, have less)
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Step 3: Decision */}
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                                Step 3: Choose Action
                            </div>
                            <div className={`p-4 rounded-lg border-2 ${isDarkMode ? 'bg-blue-900/20 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                <div className="flex items-start gap-4">
                                    <div className="text-3xl">✓</div>
                                    <div className="flex-1">
                                        <div className={`font-bold text-lg mb-1 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            Selected: calibrate_noise_sigma
                                        </div>
                                        <div className={`text-sm mb-2 ${isDarkMode ? 'text-blue-300' : 'text-blue-700'}`}>
                                            <strong>Reason:</strong> Pre-gate regime forces calibration. Budget allows (384 &gt; 156). Must earn gate before biological measurements.
                                        </div>
                                        <div className={`text-xs font-mono p-2 rounded ${isDarkMode ? 'bg-slate-900 text-slate-300' : 'bg-white text-zinc-700'}`}>
                                            trigger: must_calibrate | forced: true | regime: pre_gate
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Step 4: Outcome */}
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'}`}>
                                Step 4: Update State
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Budget</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>228 wells <span className="text-red-600">(-156)</span></div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Gate Status</div>
                                        <div className={`font-mono text-green-600`}>✓ Earned</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Noise (rel_width)</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>0.22 <span className="text-green-600">(-0.16)</span></div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Regime</div>
                                        <div className={`font-mono text-green-600`}>in_gate</div>
                                    </div>
                                </div>
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                                    <p className={`text-sm ${isDarkMode ? 'text-green-300' : 'text-green-800'}`}>
                                        <strong>Gate Event:</strong> noise_sigma earned (0.22 &lt; 0.25). System can now make reliable biological measurements. Gate slack = 0.03.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-4 border-t ${isDarkMode ? 'border-slate-700 bg-slate-800/50' : 'border-zinc-200 bg-zinc-50'}`}>
                        <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                            <strong>Key insight:</strong> The system doesn't just execute experiments—it decides <em>whether to act at all</em>.
                            If budget had been 100 wells instead of 384, it would have chosen <strong>abort</strong>, refusing to proceed with unreliable data.
                        </p>
                    </div>
                </div>

                {/* Concept Guide */}
                {!selectedRun && !loadingSummaries && runs.length > 0 && (
                    <div className={`mb-6 p-6 rounded-lg border-l-4 ${isDarkMode ? 'bg-indigo-900/20 border-indigo-500' : 'bg-indigo-50 border-indigo-600'}`}>
                        <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                            Understanding Run Stories
                        </h3>
                        <p className={`text-sm mb-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                            Each run is sorted by outcome quality. Look for:
                        </p>
                        <ul className={`text-sm space-y-2 ml-4 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                            <li><strong className="text-green-600">🟩 Gate earned:</strong> System calibrated noise to statistical threshold. Biological conclusions are valid.</li>
                            <li><strong className="text-red-600">🟥 Aborted:</strong> System refused to act because conclusions would be unreliable. <em>This is correct behavior.</em></li>
                            <li><strong className="text-amber-600">🟨 No gate:</strong> Run completed but never earned statistical confidence.</li>
                            <li><strong>Regime summary:</strong> Shows transitions (e.g., <code className={`px-1 ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>pre_gate → in_gate</code>)</li>
                        </ul>
                    </div>
                )}

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

                {/* Timeline Guide */}
                {artifacts && !loading && (
                    <div className={`mb-6 p-6 rounded-lg border-l-4 ${isDarkMode ? 'bg-green-900/20 border-green-500' : 'bg-green-50 border-green-600'}`}>
                        <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                            Reading the Timeline
                        </h3>
                        <div className={`text-sm space-y-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                            <p><strong>Decision Regime Track:</strong> Each bar is one cycle. Colors show regime (orange=pre-gate, green=in-gate, red=revoked). <strong>F</strong> marks forced decisions (system had no choice).</p>
                            <p><strong>Gate Events Track:</strong> Vertical bars mark explicit gate transitions. ✓ = earned, ✗ = lost.</p>
                            <p><strong>Noise Metrics Chart:</strong> Shows rel_width (blue) and pooled_sigma (purple) over time. Thresholds at 0.25 (enter) and 0.40 (exit).</p>
                            <p><strong>Decision Receipt:</strong> Click any cycle to see the full decision provenance: template chosen, why, calibration plan, gate state.</p>
                        </div>
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

                {/* Gate Metrics Guide */}
                {artifacts && gateKPIs && decisionKPIs && !loading && (
                    <div className={`mt-6 p-6 rounded-lg border-l-4 ${isDarkMode ? 'bg-amber-900/20 border-amber-500' : 'bg-amber-50 border-amber-600'}`}>
                        <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                            Understanding Gate Metrics
                        </h3>
                        <div className={`text-sm space-y-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                            <p><strong>Gate Slack:</strong> How much "room" the system had when earning the gate. High slack (&gt;0.10) = comfortable margin. Low slack (&lt;0.05) = barely made it.</p>
                            <p><strong>Gate Flapping:</strong> Number of times the gate was lost after earning. Zero losses = stable calibration.</p>
                            <p><strong>Forced Rate:</strong> Percentage of decisions where the system had no choice (constraints forced the action). High forced rate = tight constraints.</p>
                            <p><strong>Time in Gate:</strong> What fraction of the run was spent with valid statistical confidence. Higher is better.</p>
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
