import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, ChevronLeft, RotateCcw, Play, Target } from 'lucide-react';
import { cellThalamusService } from '../../../services/CellThalamusService';
import {
    WorldModelStage,
    QuestionStage,
    ProposalStage,
    ExecutionStage,
    MeasurementStage,
    ReconciliationStage,
    RewardStage
} from './TutorialStages';

const TUTORIAL_DATA = {
    initial: {
        ec50: { value: 25, uncertainty: 10 },
        hillSlope: { value: 1.2, uncertainty: 0.5 },
        dataPoints: [
            // Some scattered initial points
            { dose: 0.1, response: 98, error: 2 },
            { dose: 1, response: 95, error: 3 },
            { dose: 10, response: 85, error: 5 },
            { dose: 50, response: 15, error: 4 },
            { dose: 100, response: 5, error: 2 },
        ]
    },
    proposed: {
        doses: [10, 15, 20, 25, 30, 40],
        replicates: 4,
        cost: 450
    },
    final: {
        ec50: { value: 22.3, uncertainty: 3.1 },
        hillSlope: { value: 1.4, uncertainty: 0.2 },
        dataPoints: [
            // New points in the uncertainty region
            { dose: 10, response: 88, error: 3 },
            { dose: 15, response: 75, error: 4 },
            { dose: 20, response: 60, error: 4 },
            { dose: 25, response: 45, error: 5 },
            { dose: 30, response: 30, error: 3 },
            { dose: 40, response: 10, error: 2 },
        ]
    },
    metrics: {
        informationGain: 2.4,
        uncertaintyReduction: 0.67
    },
    candidateRanking: [
        { compound: 'tBHQ', cellLine: 'A549', timepoint: '24h', entropy: 0.89 },
        { compound: 'H2O2', cellLine: 'HeLa', timepoint: '48h', entropy: 0.72 },
        { compound: 'tunicamycin', cellLine: 'HepG2', timepoint: '24h', entropy: 0.55 },
        { compound: 'CCCP', cellLine: 'U2OS', timepoint: '24h', entropy: 0.41 },
        { compound: 'oligomycin', cellLine: 'A549', timepoint: '48h', entropy: 0.38 },
    ]
};

const STAGES = [
    { id: 'intro', title: 'Start' },
    { id: 'world', title: 'World Model' },
    { id: 'question', title: 'Question' },
    { id: 'proposal', title: 'Proposal' },
    { id: 'execute', title: 'Execution' },
    { id: 'measure', title: 'Measure' },
    { id: 'update', title: 'Update' },
    { id: 'reward', title: 'Reward' },
];

const TutorialMode: React.FC<{ isDarkMode: boolean, onExit: () => void }> = ({ isDarkMode, onExit }) => {
    const [stageIndex, setStageIndex] = useState(0);
    const [combinedRanking, setCombinedRanking] = useState<any[]>([]);
    const [dataError, setDataError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [realDoseResponseData, setRealDoseResponseData] = useState<any>(null);
    const [plateLayoutData, setPlateLayoutData] = useState<any[]>([]);
    const [availableDesigns, setAvailableDesigns] = useState<any[]>([]);
    const [selectedDesignId, setSelectedDesignId] = useState<string | null>(null);

    // Experiment execution state
    const [isRunningExperiment, setIsRunningExperiment] = useState(false);
    const [experimentProgress, setExperimentProgress] = useState<any>(null);
    const [experimentDesignId, setExperimentDesignId] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setDataError(null);
            let fetchedRealData: any[] = [];
            let topCandidateDoseResponse: any = null;
            let allResults: any[] = [];  // Declare at function scope

            try {
                const designs = await cellThalamusService.getDesigns();

                if (!designs || designs.length === 0) {
                    throw new Error('No experimental designs found in database. Please run a simulation first.');
                }

                // Store available designs for selector
                setAvailableDesigns(designs);

                // Auto-select first design if none selected
                if (!selectedDesignId && designs.length > 0) {
                    setSelectedDesignId(designs[0].design_id);
                }

                if (designs && designs.length > 0) {
                    // Filter to selected design or use recent designs as fallback
                    const designsToProcess = selectedDesignId
                        ? designs.filter(d => d.design_id === selectedDesignId)
                        : designs.slice(0, 10);

                    for (const design of designsToProcess) {
                        try {
                            const results = await cellThalamusService.getResults(design.design_id);
                            if (results) allResults = [...allResults, ...results];
                        } catch (e) {
                            // console.warn('Skip design', design.design_id);
                        }
                    }

                    if (allResults.length > 0) {
                        const groups: Record<string, any[]> = {};
                        allResults.forEach(r => {
                            const timepoint = Math.round(r.timepoint_h || 24);
                            const key = `${r.compound}|${r.cell_line}|${timepoint}`;
                            if (!groups[key]) groups[key] = [];
                            groups[key].push(r);
                        });

                        fetchedRealData = Object.keys(groups).map(key => {
                            const [compound, cellLine, timepoint] = key.split('|');
                            const points = groups[key];

                            const values = points.map(p => p.atp_signal);
                            if (values.length === 0) return null;

                            const mean = values.reduce((a, b) => a + b, 0) / values.length;
                            const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;

                            // Normalized entropy score
                            const entropyMock = Math.min(0.99, (Math.sqrt(variance) / (mean || 1)) * 2).toFixed(2);
                            const cv = ((Math.sqrt(variance) / (mean || 1)) * 100).toFixed(1);

                            return {
                                compound,
                                cellLine,
                                timepoint: `${timepoint}h`,
                                entropy: entropyMock,
                                cv: `${cv}%`,
                                reason: 'High experimental variance detected',
                                source: 'Real Data'
                            };
                        }).filter(item => item !== null);
                    }
                }
            } catch (err) {
                console.error("Failed to load real data", err);
                const errorMessage = err instanceof Error ? err.message : 'Failed to connect to Cell Thalamus API. Please ensure the backend server is running.';
                setDataError(errorMessage);
            } finally {
                setIsLoading(false);
            }

            // MERGE Logic: 
            // 1. Take all Real Data
            // 2. Fill remaining slots with Reference Data (simulated) up to 10 items
            // 3. Sort by Entropy

            const realSignatures = new Set(fetchedRealData.map(d => `${d.compound}-${d.cellLine}`));
            const uniqueReferenceData = TUTORIAL_DATA.candidateRanking.filter(
                d => !realSignatures.has(`${d.compound}-${d.cellLine}`)
            ).map(d => ({
                ...d,
                source: 'Reference Model',
                cv: d.cv || '12.5%',
                reason: d.reason || 'Model prediction: Transition zone'
            }));

            const merged = [...fetchedRealData, ...uniqueReferenceData];

            // Smart Sort:
            // 1. Entropy (primary, DESC)
            // 2. Technical Quality (secondary): Penalize CV > 100% (likely noise)
            // 3. Information Content (tertiary): Higher CV is better (if < 100%)
            merged.sort((a, b) => {
                const entA = parseFloat(a.entropy as string);
                const entB = parseFloat(b.entropy as string);
                if (entA !== entB) return entB - entA;

                const cvA = parseFloat(a.cv as string);
                const cvB = parseFloat(b.cv as string);

                // Deprioritize super high variance (>100%) as likely technical error
                const aIsNoisy = cvA > 100;
                const bIsNoisy = cvB > 100;

                if (aIsNoisy && !bIsNoisy) return 1;
                if (!aIsNoisy && bIsNoisy) return -1;

                // Otherwise prefer higher variance (more to learn)
                return cvB - cvA;
            });

            // Add dynamic reasoning
            if (merged.length > 0) {
                const top = merged[0];
                const cleanCV = parseFloat(top.cv);

                if (top.reason === 'High experimental variance detected' || !top.reason) {
                    if (top.entropy >= 0.99) {
                        top.reason = `it has maximal entropy (${top.entropy}) with reliable variance (${cleanCV}%)`;
                    } else {
                        top.reason = `it maximizes expected information gain`;
                    }
                }

                // Annotate the "loser" if it had higher variance but was noisy
                const noisyLoser = merged.find(m => parseFloat(m.entropy) === parseFloat(top.entropy) && parseFloat(m.cv) > 100);
                if (noisyLoser && parseFloat(top.cv) < 100) {
                    top.reason += `. (Note: ${noisyLoser.compound} had higher variance but was deprioritized as likely technical noise)`;
                }
            }

            setCombinedRanking(merged.slice(0, 10));

            // Extract dose-response data for top candidate
            if (merged.length > 0 && allResults.length > 0) {
                const topCandidate = merged[0];
                console.log('Top candidate:', topCandidate);
                console.log('All results count:', allResults.length);

                const doseResponseData = allResults.filter(r =>
                    r.compound === topCandidate.compound &&
                    r.cell_line === topCandidate.cellLine &&
                    Math.round(r.timepoint_h) === parseInt(topCandidate.timepoint)
                );

                console.log('Dose response data points:', doseResponseData.length);
                console.log('Dose response data:', doseResponseData);

                if (doseResponseData.length > 0) {
                    // Convert to chart format
                    const dataPoints = doseResponseData.map(r => ({
                        dose: r.dose_uM,
                        response: r.atp_signal * 100, // Convert to percentage
                        error: 5 // Placeholder, could calculate from replicates
                    }));

                    // Sort by dose and filter out invalid points
                    const sortedByDose = [...dataPoints]
                        .filter(d => d.dose > 0 && d.response >= 0 && d.response <= 120) // Only valid data
                        .sort((a, b) => a.dose - b.dose);

                    // Get max dose from data
                    const maxDose = Math.max(...sortedByDose.map(d => d.dose));
                    const maxResponse = Math.max(...sortedByDose.map(d => d.response));
                    const minResponse = Math.min(...sortedByDose.map(d => d.response));

                    // Use only real data points, no interpolation
                    let enhancedDataPoints = sortedByDose;

                    // Only use real data if we have at least 2 valid points
                    if (enhancedDataPoints.length >= 2) {
                        // EC50 estimation: geometric mean of doses
                        const doses = enhancedDataPoints.map(d => d.dose);
                        const estimatedEC50 = Math.sqrt(Math.min(...doses) * Math.max(...doses));

                        const doseResponsePayload = {
                            initial: {
                                ec50: { value: estimatedEC50, uncertainty: estimatedEC50 * 0.5 },
                                hillSlope: { value: 1.2, uncertainty: 0.5 },
                                dataPoints: enhancedDataPoints
                            },
                            topCandidate: topCandidate
                        };

                        console.log('Setting dose response data:', doseResponsePayload);
                        setRealDoseResponseData(doseResponsePayload);
                    } else {
                        console.log('Insufficient valid data points, skipping real data visualization');
                    }

                    // Extract plate layout data for visualization
                    const plateData = doseResponseData.map((r: any) => ({
                        wellId: r.well_id,
                        compound: r.compound,
                        cellLine: r.cell_line,
                        doseUm: r.dose_uM,
                        atpSignal: r.atp_signal
                    }));
                    setPlateLayoutData(plateData);
                } else {
                    console.log('No dose response data found for top candidate');
                }
            } else {
                console.log('No merged candidates or no results');
            }
        };

        fetchData();
    }, [selectedDesignId]);

    // Generate candidates list (shared logic for run and export)
    const generateCandidates = () => {
        // Calculate entropy-weighted allocations - wide portfolio strategy
        // Cap at 12 wells/candidate (same as initial data) to force broad exploration
        const TOTAL_EXPERIMENTAL_WELLS = 160; // 2 plates × 96 wells - 32 controls = 160 experimental
        const MAX_WELLS_PER_CANDIDATE = 12; // No more than 1× expansion from initial screen

        // Select enough candidates to fill budget (up to 13 candidates with 12w each)
        const maxCandidates = Math.floor(TOTAL_EXPERIMENTAL_WELLS / MAX_WELLS_PER_CANDIDATE);
        const selectedCandidates = combinedRanking.slice(0, Math.min(maxCandidates, combinedRanking.length));

        // Calculate scores: entropy × √CV × priority_multiplier
        const candidatesWithScores = selectedCandidates.map((c, idx) => {
            let priorityMultiplier;
            let priority;
            if (idx === 0) {
                priority = 'Primary';
                priorityMultiplier = 2.0;
            } else if (idx <= 2) {
                priority = 'Scout';
                priorityMultiplier = 1.5;
            } else {
                priority = 'Probe';
                priorityMultiplier = 1.0;
            }

            const entropy = parseFloat(c.entropy) || 0.99;
            const cv = parseFloat(c.cv) || 50;

            // Diminishing returns formula: sqrt(entropy) × CV^0.3 / sqrt(n_initial + 1) × priority
            // Assumes ~12 initial wells per condition from Phase 0 screen
            const nInitial = 12;
            const score = (Math.sqrt(entropy) * Math.pow(cv / 100, 0.3)) / Math.sqrt(nInitial + 1) * priorityMultiplier;

            return { ...c, score, priority };
        });

        const totalScore = candidatesWithScores.reduce((sum, c) => sum + c.score, 0);

        // Allocate wells proportionally, capped at 12 wells each
        const candidates = candidatesWithScores.map(c => {
            const rawAllocation = Math.round((c.score / totalScore) * TOTAL_EXPERIMENTAL_WELLS);
            return {
                compound: c.compound,
                cell_line: c.cellLine,
                timepoint_h: parseFloat(c.timepoint) || 12.0,
                wells: rawAllocation,  // Don't cap yet
                priority: c.priority
            };
        });

        // Force exactly 160 wells allocation
        let allocatedTotal = candidates.reduce((sum, c) => sum + c.wells, 0);
        let remaining = TOTAL_EXPERIMENTAL_WELLS - allocatedTotal;

        // Distribute remaining wells (or remove excess) round-robin
        let idx = 0;
        while (remaining !== 0) {
            if (remaining > 0) {
                candidates[idx].wells += 1;
                remaining -= 1;
            } else {
                if (candidates[idx].wells > 1) {  // Don't go below 1 well
                    candidates[idx].wells -= 1;
                    remaining += 1;
                }
            }
            idx = (idx + 1) % candidates.length;

            // Safety: prevent infinite loop
            const currentTotal = candidates.reduce((sum, c) => sum + c.wells, 0);
            if (currentTotal === TOTAL_EXPERIMENTAL_WELLS) break;
        }

        return candidates;
    };

    // Export candidates as JSON for JupyterHub
    const handleExportCandidates = () => {
        const candidates = generateCandidates();

        const jsonStr = JSON.stringify(candidates, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = `autonomous_loop_candidates_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    // Handle running autonomous loop experiment
    const handleRunExperiment = async (candidate: any) => {
        try {
            setIsRunningExperiment(true);

            const candidates = generateCandidates();
            const totalWells = 160 + 32; // experimental + controls (2 plates)
            setExperimentProgress({ completed: 0, total: totalWells, percentage: 0 });

            const response = await fetch('http://localhost:8000/api/thalamus/autonomous-loop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidates })
            });

            if (!response.ok) throw new Error('Failed to start experiment');

            const data = await response.json();
            setExperimentDesignId(data.design_id);

            // Start polling for progress
            const pollInterval = setInterval(async () => {
                try {
                    const statusResponse = await fetch(`http://localhost:8000/api/thalamus/designs/${data.design_id}/status`);
                    if (!statusResponse.ok) throw new Error('Failed to fetch status');

                    const status = await statusResponse.json();

                    if (status.progress) {
                        setExperimentProgress(status.progress);
                    }

                    if (status.status === 'completed') {
                        clearInterval(pollInterval);
                        setIsRunningExperiment(false);
                        // Auto-advance to next stage
                        setTimeout(() => nextStage(), 2000);
                    } else if (status.status === 'failed') {
                        clearInterval(pollInterval);
                        setIsRunningExperiment(false);
                        alert('Experiment failed: ' + (status.error || 'Unknown error'));
                    }
                } catch (err) {
                    console.error('Error polling status:', err);
                }
            }, 1000); // Poll every second

        } catch (error) {
            console.error('Error starting experiment:', error);
            setIsRunningExperiment(false);
            alert('Failed to start experiment');
        }
    };

    // Merge real data into tutorial data
    const activeData = {
        ...TUTORIAL_DATA,
        candidateRanking: combinedRanking.length > 0 ? combinedRanking : TUTORIAL_DATA.candidateRanking,
        plateLayout: plateLayoutData,
        // Override with real dose-response data if available
        ...(realDoseResponseData ? {
            initial: realDoseResponseData.initial,
            proposed: {
                ...TUTORIAL_DATA.proposed,
                // Suggest doses around the EC50
                doses: realDoseResponseData.initial.ec50.value > 0 ? [
                    Math.round(realDoseResponseData.initial.ec50.value * 0.3 * 10) / 10,
                    Math.round(realDoseResponseData.initial.ec50.value * 0.5 * 10) / 10,
                    Math.round(realDoseResponseData.initial.ec50.value * 0.7 * 10) / 10,
                    Math.round(realDoseResponseData.initial.ec50.value * 1.0 * 10) / 10,
                    Math.round(realDoseResponseData.initial.ec50.value * 1.5 * 10) / 10,
                    Math.round(realDoseResponseData.initial.ec50.value * 2.0 * 10) / 10,
                ] : TUTORIAL_DATA.proposed.doses
            },
            final: {
                // Simulated "improved" estimates after experiment
                ec50: {
                    value: realDoseResponseData.initial.ec50.value * 0.95,
                    uncertainty: realDoseResponseData.initial.ec50.uncertainty * 0.3
                },
                hillSlope: {
                    value: realDoseResponseData.initial.hillSlope.value,
                    uncertainty: realDoseResponseData.initial.hillSlope.uncertainty * 0.4
                },
                dataPoints: [] // Keep empty for tutorial flow
            }
        } : {})
    };

    const nextStage = () => setStageIndex(Math.min(STAGES.length - 1, stageIndex + 1));
    const prevStage = () => setStageIndex(Math.max(0, stageIndex - 1));
    const restart = () => setStageIndex(0);

    return (
        <div className="max-w-4xl mx-auto py-8 px-4">

            {/* Header / Progress */}
            <div className="mb-8">
                <div className="flex items-center justify-between mb-4">
                    <h2 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                        Autonomous Loop Tutorial
                    </h2>
                    <div className="flex gap-2">
                        <button onClick={onExit} className={`text-sm px-3 py-1 rounded hover:bg-opacity-10 ${isDarkMode ? 'text-slate-400 hover:bg-white' : 'text-zinc-500 hover:bg-black'}`}>
                            Exit Tutorial
                        </button>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="flex gap-1 h-1.5 w-full bg-slate-200/20 rounded overflow-hidden">
                    {STAGES.map((_, i) => (
                        <div
                            key={i}
                            className={`flex-1 transition-colors ${i <= stageIndex
                                ? (isDarkMode ? 'bg-indigo-500' : 'bg-indigo-600')
                                : (isDarkMode ? 'bg-slate-700' : 'bg-slate-200')}`}
                        />
                    ))}
                </div>
                <div className="flex justify-between mt-2 text-xs text-slate-500">
                    <span>Intro</span>
                    <span>{STAGES[stageIndex].title}</span>
                    <span>Reward</span>
                </div>
            </div>

            {/* Loading State */}
            {isLoading && (
                <div className={`text-center py-12 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-4"></div>
                    <p>Loading experimental data...</p>
                </div>
            )}

            {/* Error State */}
            {!isLoading && dataError && (
                <div className={`p-6 rounded-xl border ${isDarkMode ? 'bg-red-900/20 border-red-700 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
                    <h3 className="text-lg font-semibold mb-2">Unable to Load Data</h3>
                    <p className="mb-4">{dataError}</p>
                    <div className="text-sm space-y-2">
                        <p className="font-semibold">To fix this:</p>
                        <ol className="list-decimal list-inside space-y-1 ml-2">
                            <li>Ensure the Cell Thalamus API backend is running on port 8000</li>
                            <li>Run a simulation from the "Run Simulation" tab first</li>
                            <li>Refresh this page</li>
                        </ol>
                    </div>
                </div>
            )}

            {/* Stage Content */}
            {!isLoading && !dataError && (
            <div className="min-h-[400px]">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={stageIndex}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.2 }}
                    >
                        {stageIndex === 0 && (
                            <div className="text-center py-12 space-y-6">
                                <div className="inline-flex p-4 rounded-full bg-indigo-500/20 text-indigo-500 mb-4">
                                    <Play className="w-8 h-8 ml-1" />
                                </div>
                                <h1 className={`text-4xl font-extrabold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                    Welcome to the Loop
                                </h1>
                                <div className={`max-w-2xl mx-auto text-left space-y-3`}>
                                    <p className={`text-lg ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                        <span className="font-semibold">Stop optimizing viability curves. Start tightening the morphology manifold.</span>
                                    </p>
                                    <p className={`text-base ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        The autonomous loop isn't trying to find the perfect EC50. It's making the phenotype space <strong>trustworthy enough to define boundaries, constraints, and reward functions</strong>.
                                    </p>
                                    <ul className={`text-base space-y-2 pl-6 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        <li className="flex items-start gap-2">
                                            <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`}></span>
                                            <span><strong>Phase 1:</strong> Identify conditions with high morphology scatter (tr(Σ)) but low nuisance — these are <em>scientifically ambiguous</em></span>
                                        </li>
                                        <li className="flex items-start gap-2">
                                            <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`}></span>
                                            <span><strong>Phase 2:</strong> Tighten boundaries between stress archetypes (death, ER, mito, oxidative) with sentinel-anchored normalization</span>
                                        </li>
                                        <li className="flex items-start gap-2">
                                            <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`}></span>
                                            <span><strong>Stop condition:</strong> When between-plate sentinel drift &lt; 0.5× within-scatter and geometry preservation &gt; 0.9, boundaries are allowed to exist</span>
                                        </li>
                                    </ul>
                                </div>

                                {/* Mission Objective Card */}
                                <div className={`max-w-md mx-auto text-left p-6 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} shadow-lg`}>
                                    <div className="flex items-center gap-2 mb-4">
                                        <div className={`p-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                                            <Target className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>The Agent's Objective</h3>
                                            <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">Reward Function</p>
                                        </div>
                                    </div>

                                    <div className="space-y-4 text-sm">
                                        <div className="flex items-start gap-3">
                                            <div className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-green-400' : 'bg-green-600'}`}></div>
                                            <p className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                                                <span className="font-semibold block mb-0.5">Maximize Covariance Reduction</span>
                                                Target conditions with high within-condition scatter (tr(Σ_c)) to tighten the manifold where decisions matter.
                                            </p>
                                        </div>

                                        <div className="flex items-start gap-3">
                                            <div className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-orange-400' : 'bg-orange-600'}`}></div>
                                            <p className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                                                <span className="font-semibold block mb-0.5">Minimize Nuisance Dominance</span>
                                                Penalize conditions where plate/day/operator effects swamp biological signal. Priority = scatter × (1 - λ·nuisance_fraction).
                                            </p>
                                        </div>

                                        <div className="flex items-start gap-3">
                                            <div className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-blue-400' : 'bg-blue-600'}`}></div>
                                            <p className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                                                <span className="font-semibold block mb-0.5">Integration Test: Anchor Stability</span>
                                                Loop proceeds to Phase 2 (boundaries) only when sentinel drift &lt; 0.5× within-scatter and geometry preservation &gt; 0.9.
                                            </p>
                                        </div>
                                    </div>

                                    <div className={`mt-4 pt-3 border-t text-xs font-mono flex justify-between ${isDarkMode ? 'border-slate-700 text-slate-500' : 'border-zinc-100 text-zinc-400'}`}>
                                        <span>R = tr(Σ) × (1 - λ·P_nuis) / Cost</span>
                                        <span>Nuisance-aware</span>
                                    </div>
                                </div>

                                <div className="pt-4">
                                    <button
                                        onClick={nextStage}
                                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-8 py-3 rounded-full font-medium transition-colors shadow-lg shadow-indigo-500/25"
                                    >
                                        Start Walkthrough
                                    </button>
                                </div>
                            </div>
                        )}

                        {stageIndex === 1 && (
                            <WorldModelStage
                                isDarkMode={isDarkMode}
                                data={activeData}
                                availableDesigns={availableDesigns}
                                selectedDesignId={selectedDesignId}
                                onDesignChange={setSelectedDesignId}
                            />
                        )}
                        {stageIndex === 2 && <QuestionStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 3 && <ProposalStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 4 && (
                            <ExecutionStage
                                isDarkMode={isDarkMode}
                                data={activeData}
                                topCandidate={combinedRanking[0]}
                                candidateRanking={combinedRanking}
                                onRunExperiment={handleRunExperiment}
                                onExportCandidates={handleExportCandidates}
                                isRunning={isRunningExperiment}
                                progress={experimentProgress}
                            />
                        )}
                        {stageIndex === 5 && <MeasurementStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 6 && <ReconciliationStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 7 && <RewardStage isDarkMode={isDarkMode} data={activeData} />}

                    </motion.div>
                </AnimatePresence>
            </div>
            )}

            {/* Navigation Controls */}
            {!isLoading && !dataError && stageIndex > 0 && (
                <div className={`mt-8 pt-6 border-t flex justify-between items-center ${isDarkMode ? 'border-slate-800' : 'border-zinc-200'}`}>
                    <button
                        onClick={prevStage}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${isDarkMode
                            ? 'text-slate-300 hover:bg-slate-800'
                            : 'text-zinc-600 hover:bg-zinc-100'}`}
                    >
                        <ChevronLeft className="w-4 h-4" /> Previous
                    </button>

                    {stageIndex < STAGES.length - 1 ? (
                        <button
                            onClick={nextStage}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors shadow-lg shadow-indigo-500/20"
                        >
                            Next <ChevronRight className="w-4 h-4" />
                        </button>
                    ) : (
                        <button
                            onClick={restart}
                            className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors ${isDarkMode
                                ? 'bg-slate-700 hover:bg-slate-600 text-white'
                                : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'}`}
                        >
                            <RotateCcw className="w-4 h-4" /> Restart Loop
                        </button>
                    )}
                </div>
            )}

        </div>
    );
};

export default TutorialMode;
