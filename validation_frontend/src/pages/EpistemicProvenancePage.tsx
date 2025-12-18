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
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine, ResponsiveContainer, Cell } from 'recharts';
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
    const [walkthroughStep, setWalkthroughStep] = useState<number>(1);

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
                        <p className={`text-sm mb-3 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                            Unlike traditional automated labs that blindly execute experiments, the epistemic agent treats <strong>measurement reliability</strong> as a constraint.
                            It won't make biological claims until it has statistical justification. This is called <strong>"pay-for-calibration"</strong> - you must earn the right to act.
                        </p>
                        <div className={`p-3 rounded ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                            <p className={`text-xs ${isDarkMode ? 'text-blue-300' : 'text-blue-800'}`}>
                                <strong>Core principle:</strong> The system tracks its own measurement noise. If noise is too high (rel_width &gt; 0.25),
                                it cannot distinguish real biological effects from experimental variability. In this state, it <em>must</em> calibrate before
                                making claims. If it can't afford calibration, it aborts rather than producing unreliable data.
                            </p>
                        </div>
                    </div>

                    {/* Walkthrough Example */}
                    <div className="p-6 space-y-6">
                        {/* Step Progress Indicator */}
                        <div className="flex items-center justify-center gap-2 mb-6">
                            {[1, 2, 3, 4].map((step) => (
                                <button
                                    key={step}
                                    onClick={() => setWalkthroughStep(step)}
                                    className={`flex items-center justify-center w-10 h-10 rounded-full text-sm font-semibold transition-all ${
                                        walkthroughStep === step
                                            ? isDarkMode
                                                ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                                                : 'bg-blue-600 text-white ring-2 ring-blue-400'
                                            : walkthroughStep > step
                                            ? isDarkMode
                                                ? 'bg-green-700 text-white'
                                                : 'bg-green-500 text-white'
                                            : isDarkMode
                                            ? 'bg-slate-700 text-slate-400'
                                            : 'bg-zinc-200 text-zinc-500'
                                    }`}
                                >
                                    {walkthroughStep > step ? '✓' : step}
                                </button>
                            ))}
                        </div>

                        {/* Step 1: Starting State (First Boot) */}
                        {walkthroughStep === 1 && (
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-indigo-900 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
                                Step 1: Initial State (Cycle 0)
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <p className={`text-sm mb-4 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                    The agent starts with no experimental history. It has never run a plate, so it has no noise estimate yet:
                                </p>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Budget</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>384 wells</div>
                                        <div className={`text-xs mt-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-600'}`}>Physical constraint</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Gate Status</div>
                                        <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>❌ Not earned</div>
                                        <div className={`text-xs mt-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-600'}`}>No data yet</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Noise (rel_width)</div>
                                        <div className={`font-mono text-slate-500`}>Unknown</div>
                                        <div className={`text-xs mt-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-600'}`}>No measurements</div>
                                    </div>
                                    <div>
                                        <div className={`text-xs font-semibold uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Regime</div>
                                        <div className={`font-mono text-orange-600`}>pre_gate</div>
                                        <div className={`text-xs mt-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-600'}`}>Must calibrate first</div>
                                    </div>
                                </div>
                                <div className={`p-3 rounded mb-4 ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                                    <p className={`text-xs mb-2 ${isDarkMode ? 'text-blue-300' : 'text-blue-800'}`}>
                                        <strong>What this means:</strong>
                                    </p>
                                    <ul className={`text-xs space-y-1 ml-4 list-disc ${isDarkMode ? 'text-blue-300' : 'text-blue-800'}`}>
                                        <li><strong>No noise estimate:</strong> The system hasn't run any experiments, so it doesn't know its measurement noise yet.</li>
                                        <li><strong>Gate not earned:</strong> Without noise calibration, the system cannot make reliable biological claims.</li>
                                        <li><strong>pre_gate regime:</strong> All biological experiments are blocked. The first action must be calibration.</li>
                                        <li><strong>Budget = 384 wells:</strong> Determines what experiments are affordable. Must choose wisely.</li>
                                    </ul>
                                </div>

                                {/* Visualization: No data yet */}
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>
                                    <div className={`text-xs font-semibold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                        Noise Level (No Data Yet)
                                    </div>
                                    <ResponsiveContainer width="100%" height={120}>
                                        <BarChart data={[{ name: 'Current', value: null }]} layout="vertical" margin={{ top: 5, right: 30, left: 60, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#374151' : '#e5e7eb'} />
                                            <XAxis type="number" domain={[0, 0.5]} stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 11 }} />
                                            <YAxis type="category" dataKey="name" stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 11 }} />
                                            <ReferenceLine x={0.25} stroke="#10b981" strokeWidth={2} strokeDasharray="3 3" label={{ value: 'Enter Gate (0.25)', position: 'top', fontSize: 10, fill: '#10b981' }} />
                                            <ReferenceLine x={0.40} stroke="#ef4444" strokeWidth={2} strokeDasharray="3 3" label={{ value: 'Exit Gate (0.40)', position: 'top', fontSize: 10, fill: '#ef4444' }} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                    <p className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        No noise measurement yet. The system must run calibration experiments to learn its measurement noise and earn the gate (rel_width &lt; 0.25).
                                    </p>
                                </div>
                            </div>
                        </div>
                        )}

                        {/* Step 2: Choose Experimental Parameters */}
                        {walkthroughStep === 2 && (
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'}`}>
                                Step 2: Choose Experimental Parameters
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <p className={`text-sm mb-4 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                    For the first calibration experiment, the agent must choose all experimental parameters. Here's what's available and what it selects:
                                </p>

                                {/* Parameter Selection Grid */}
                                <div className="space-y-4">
                                    {/* Cell Line Selection */}
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                        <div className={`font-semibold text-sm mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            1. Cell Line
                                        </div>
                                        <div className={`text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Available:</strong> HEK293, A549, HepG2, MCF7
                                        </div>
                                        <div className={`text-xs px-2 py-1 rounded inline-block ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-200 text-green-800'}`}>
                                            ✓ Selected: <strong>HEK293</strong>
                                        </div>
                                        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Why:</strong> HEK293 cells are robust, fast-growing, and have well-characterized morphology for calibration.
                                        </div>
                                    </div>

                                    {/* Compound Selection */}
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                        <div className={`font-semibold text-sm mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            2. Compound/Control
                                        </div>
                                        <div className={`text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Available:</strong> DMSO (vehicle control), Doxorubicin, Paclitaxel, Staurosporine
                                        </div>
                                        <div className={`text-xs px-2 py-1 rounded inline-block ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-200 text-green-800'}`}>
                                            ✓ Selected: <strong>Staurosporine (dose-response)</strong>
                                        </div>
                                        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Why:</strong> Staurosporine is a well-characterized compound with predictable dose-response. Using 12 dose levels creates a calibration curve that spans the measurement range.
                                        </div>
                                    </div>

                                    {/* Plate Size */}
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                        <div className={`font-semibold text-sm mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            3. Plate Format
                                        </div>
                                        <div className={`text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Available:</strong> 96-well, 384-well, 1536-well
                                        </div>
                                        <div className={`text-xs px-2 py-1 rounded inline-block ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-200 text-green-800'}`}>
                                            ✓ Selected: <strong>384-well</strong>
                                        </div>
                                        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Why:</strong> 384-well plates balance well density (can fit 12 doses × 13 replicates = 156 wells) with measurement reliability.
                                        </div>
                                    </div>

                                    {/* Plate Layout */}
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                        <div className={`font-semibold text-sm mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            4. Plate Layout
                                        </div>
                                        <div className={`text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Available:</strong> Single dose (high replicates), Dose-response curve, Sparse sampling
                                        </div>
                                        <div className={`text-xs px-2 py-1 rounded inline-block ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-200 text-green-800'}`}>
                                            ✓ Selected: <strong>Dose-response curve (12 doses × 13 replicates)</strong>
                                        </div>
                                        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Why:</strong> 13 replicates per dose level gives df=140 degrees of freedom (13-1 per dose × 12 doses). This high df is necessary to achieve rel_width &lt; 0.25.
                                        </div>
                                    </div>

                                    {/* Readout Method */}
                                    <div className={`p-3 rounded border-l-4 ${isDarkMode ? 'bg-slate-800 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                        <div className={`font-semibold text-sm mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            5. Measurement Readout
                                        </div>
                                        <div className={`text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Available:</strong> Morphology (image-based), Fluorescence intensity, Luminescence
                                        </div>
                                        <div className={`text-xs px-2 py-1 rounded inline-block ${isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-200 text-green-800'}`}>
                                            ✓ Selected: <strong>Morphology (noisy_morphology signal)</strong>
                                        </div>
                                        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                            <strong>Why:</strong> Morphology is the primary observable. The system measures cell shape, size, and texture features - these have inherent measurement noise that must be calibrated.
                                        </div>
                                    </div>
                                </div>

                                <div className={`mt-4 p-3 rounded ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                                    <p className={`text-xs ${isDarkMode ? 'text-purple-300' : 'text-purple-800'}`}>
                                        <strong>Decision summary:</strong> The agent selected parameters to maximize statistical power for calibration:
                                        12 dose levels × 13 replicates = 156 wells, giving df=140. This high replicate count is necessary to narrow the confidence
                                        interval on noise measurements to rel_width &lt; 0.25.
                                    </p>
                                </div>

                                {/* Visualization: Budget Allocation */}
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>
                                    <div className={`text-xs font-semibold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                        Budget vs Calibration Cost
                                    </div>
                                    <ResponsiveContainer width="100%" height={150}>
                                        <BarChart data={[
                                            { name: 'Available Budget', value: 384, fill: '#3b82f6' },
                                            { name: 'Calibration Cost', value: 156, fill: '#f97316' },
                                            { name: 'Remaining After', value: 228, fill: '#10b981' }
                                        ]} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#374151' : '#e5e7eb'} />
                                            <XAxis dataKey="name" stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={60} />
                                            <YAxis stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 11 }} label={{ value: 'Wells', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                                            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                                {[
                                                    { name: 'Available Budget', value: 384, fill: '#3b82f6' },
                                                    { name: 'Calibration Cost', value: 156, fill: '#f97316' },
                                                    { name: 'Remaining After', value: 228, fill: '#10b981' }
                                                ].map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.fill} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                    <p className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        Budget (384) &gt; Cost (156) = <strong className="text-green-600">Can afford</strong>. If budget were 100 wells, calibration would be impossible → forced abort.
                                    </p>
                                </div>
                            </div>
                        </div>
                        )}

                        {/* Step 3: Run Experiment & Measure */}
                        {walkthroughStep === 3 && (
                        <div>
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3 ${isDarkMode ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                                Step 3: Run Experiment & Measure
                            </div>
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                                <p className={`text-sm mb-4 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                    The system executes the calibration experiment with the chosen parameters:
                                </p>

                                {/* Experiment Execution */}
                                <div className={`p-4 rounded-lg border-2 mb-4 ${isDarkMode ? 'bg-blue-900/20 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                                    <div className="flex items-start gap-4">
                                        <div className="text-3xl">🔬</div>
                                        <div className="flex-1">
                                            <div className={`font-bold text-lg mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                                Executing: calibrate_noise_sigma
                                            </div>
                                            <div className={`text-sm space-y-1 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                                <div>• Plate 384 wells with HEK293 cells</div>
                                                <div>• Apply Staurosporine at 12 dose levels (13 replicates each)</div>
                                                <div>• Incubate 24 hours</div>
                                                <div>• Image all wells (morphology readout)</div>
                                                <div>• Extract morphology features (cell area, shape, texture)</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Measurement Results */}
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>
                                    <div className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                        Measurement Results
                                    </div>
                                    <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                                        <div>
                                            <div className={`text-xs uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Wells Measured</div>
                                            <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>156 / 156 ✓</div>
                                        </div>
                                        <div>
                                            <div className={`text-xs uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Degrees of Freedom</div>
                                            <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>140 (12 × 12)</div>
                                        </div>
                                        <div>
                                            <div className={`text-xs uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Pooled σ</div>
                                            <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>0.18</div>
                                        </div>
                                        <div>
                                            <div className={`text-xs uppercase mb-1 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>Mean Signal</div>
                                            <div className={`font-mono ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>0.82</div>
                                        </div>
                                    </div>
                                    <div className={`p-2 rounded text-xs ${isDarkMode ? 'bg-slate-900 text-slate-400' : 'bg-zinc-100 text-zinc-600'}`}>
                                        <strong>Computed rel_width:</strong> (2 × 0.18) / 0.82 = <strong className="text-green-600">0.22</strong> &lt; 0.25 threshold
                                    </div>
                                </div>
                            </div>
                        </div>
                        )}

                        {/* Step 4: Analyze Results */}
                        {walkthroughStep === 4 && (
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
                                <div className={`p-3 rounded mb-4 ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                                    <p className={`text-sm ${isDarkMode ? 'text-green-300' : 'text-green-800'}`}>
                                        <strong>Gate Event:</strong> noise_sigma earned (0.22 &lt; 0.25). System can now make reliable biological measurements. Gate slack = 0.03.
                                    </p>
                                </div>

                                {/* Visualization: Before/After Comparison */}
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>
                                    <div className={`text-xs font-semibold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                        Before vs After Calibration
                                    </div>
                                    <ResponsiveContainer width="100%" height={180}>
                                        <BarChart data={[
                                            { metric: 'Noise (rel_width)', Before: 0.38, After: 0.22 },
                                            { metric: 'Budget (wells)', Before: 384, After: 228 },
                                        ]} margin={{ top: 5, right: 20, left: 70, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#374151' : '#e5e7eb'} />
                                            <XAxis dataKey="metric" stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 10 }} />
                                            <YAxis stroke={isDarkMode ? '#94a3b8' : '#71717a'} tick={{ fontSize: 11 }} />
                                            <Bar dataKey="Before" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                            <Bar dataKey="After" fill="#10b981" radius={[4, 4, 0, 0]} />
                                            <ReferenceLine y={0.25} stroke="#10b981" strokeWidth={1} strokeDasharray="3 3" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                    <div className="flex items-center gap-4 mt-2 text-xs">
                                        <div className="flex items-center gap-1">
                                            <div className="w-3 h-3 rounded bg-red-500"></div>
                                            <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Before (pre-gate)</span>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <div className="w-3 h-3 rounded bg-green-500"></div>
                                            <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>After (in-gate)</span>
                                        </div>
                                    </div>
                                    <p className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        Noise dropped below enter threshold (0.25) → gate earned. Budget consumed 156 wells, 228 remaining for biological experiments.
                                    </p>
                                </div>
                            </div>
                        </div>
                        )}

                        {/* Navigation Buttons */}
                        <div className="flex items-center justify-between pt-6 border-t" style={{ borderColor: isDarkMode ? '#334155' : '#e5e7eb' }}>
                            <button
                                onClick={() => setWalkthroughStep(Math.max(1, walkthroughStep - 1))}
                                disabled={walkthroughStep === 1}
                                className={`px-6 py-2 rounded-lg font-semibold text-sm transition-all ${
                                    walkthroughStep === 1
                                        ? 'opacity-50 cursor-not-allowed bg-zinc-300 text-zinc-500'
                                        : isDarkMode
                                        ? 'bg-slate-700 hover:bg-slate-600 text-white'
                                        : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                                }`}
                            >
                                ← Previous
                            </button>
                            <div className={`text-sm font-semibold ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                Step {walkthroughStep} of 4
                            </div>
                            <button
                                onClick={() => setWalkthroughStep(Math.min(4, walkthroughStep + 1))}
                                disabled={walkthroughStep === 4}
                                className={`px-6 py-2 rounded-lg font-semibold text-sm transition-all ${
                                    walkthroughStep === 4
                                        ? 'opacity-50 cursor-not-allowed bg-zinc-300 text-zinc-500'
                                        : isDarkMode
                                        ? 'bg-blue-600 hover:bg-blue-500 text-white'
                                        : 'bg-blue-600 hover:bg-blue-500 text-white'
                                }`}
                            >
                                Next →
                            </button>
                        </div>
                    </div>

                    <div className={`p-4 border-t ${isDarkMode ? 'border-slate-700 bg-slate-800/50' : 'border-zinc-200 bg-zinc-50'}`}>
                        <div className="space-y-3">
                            <div>
                                <p className={`text-sm font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                    Key Insights
                                </p>
                                <ul className={`text-xs space-y-2 ml-4 list-disc ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                    <li><strong>The system decides whether to act:</strong> If budget had been 100 wells instead of 384, it would have chosen <strong>abort</strong>, explicitly refusing to proceed with unreliable data.</li>
                                    <li><strong>Constraints encode values:</strong> The gate threshold (rel_width &lt; 0.25) isn't arbitrary—it's the point where confidence intervals become narrow enough for biological interpretation.</li>
                                    <li><strong>Regimes are epistemic states:</strong> pre_gate = "I cannot make reliable claims", in_gate = "I can make reliable claims", gate_revoked = "I lost calibration and must recalibrate".</li>
                                    <li><strong>Forced decisions aren't failures:</strong> When a decision is marked "forced", it means the system had only one valid option given constraints. This is transparency, not an error.</li>
                                    <li><strong>Aborts are accountability:</strong> Traditional systems fail silently or produce bad data. This system explicitly refuses to act when it cannot justify reliability.</li>
                                </ul>
                            </div>
                            <div className={`p-3 rounded ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                                <p className={`text-xs ${isDarkMode ? 'text-purple-300' : 'text-purple-800'}`}>
                                    <strong>What happens next?</strong> After earning the gate, the agent enters <strong>in_gate regime</strong>. Now biological templates unlock.
                                    It can measure biomarkers, run dose-response curves, test conditions—as long as it maintains rel_width &lt; 0.40 (exit threshold).
                                    If noise drifts above 0.40, the gate is <strong>revoked</strong> and it must recalibrate before continuing.
                                </p>
                            </div>
                        </div>
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
