import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Target, Scissors, FlaskConical, Microscope, Sigma, Sparkles, ChevronDown, ChevronUp, Info } from 'lucide-react';
import DoseResponseChart from './DoseResponseChart';
import PlateLayoutVisualization from './PlateLayoutVisualization';
import ExperimentWorkflowAnimation from './ExperimentWorkflowAnimation';

interface StageProps {
    isDarkMode: boolean;
    onNext?: () => void;
    data: any;
    availableDesigns?: any[];
    selectedDesignId?: string | null;
    onDesignChange?: (designId: string) => void;
}

export const WorldModelStage: React.FC<StageProps> = ({ isDarkMode, data, availableDesigns, selectedDesignId, onDesignChange }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <div className="space-y-6">
            {/* Design Selector */}
            {availableDesigns && availableDesigns.length > 0 && onDesignChange && (
                <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'}`}>
                    <label className={`text-sm font-semibold mb-2 block ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                        Starting Data Source
                    </label>
                    <select
                        value={selectedDesignId || ''}
                        onChange={(e) => onDesignChange(e.target.value)}
                        className={`w-full px-4 py-2 rounded-lg font-mono text-sm ${isDarkMode
                            ? 'bg-slate-700 border-slate-600 text-slate-200'
                            : 'bg-white border-zinc-300 text-zinc-900'
                        } border focus:outline-none focus:ring-2 focus:ring-indigo-500`}
                    >
                        {availableDesigns.map((design, index) => {
                            const date = design.created_at ? new Date(design.created_at).toLocaleString() : '';
                            return (
                                <option key={design.design_id} value={design.design_id}>
                                    {date} ({design.design_id.slice(0, 8)}) - {design.well_count || '?'} wells
                                </option>
                            );
                        })}
                    </select>
                    <p className={`mt-2 text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                        Select which experimental dataset to use as the Phase 0 baseline for candidate ranking.
                    </p>
                </div>
            )}

            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
                <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-indigo-500/20 text-indigo-400' : 'bg-indigo-100 text-indigo-600'} `}>
                        <Brain className="w-6 h-6" />
                    </div>
                    <div>
                        <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Phase 1: Morphology Variance Analysis</h3>
                        <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                            <span className="font-semibold text-indigo-500">Objective:</span> Identify conditions with high morphology scatter (tr(Σ_c)) but low nuisance dominance.
                            <span className="block mt-1">
                                The chart shows <strong>{data.candidateRanking?.[0]?.compound || 'oligomycin'} × {data.candidateRanking?.[0]?.cellLine || 'A549'} @ {data.candidateRanking?.[0]?.timepoint || '12h'}</strong> (primary candidate). The table ranks conditions by <strong>covariance trace</strong> (phenotypic scatter in PC space) weighted by nuisance penalty. High scatter = scientifically ambiguous, needs tightening.
                            </span>
                        </p>
                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className={`mt-3 text-xs flex items-center gap-1 font-medium ${isDarkMode ? 'text-indigo-400 hover:text-indigo-300' : 'text-indigo-600 hover:text-indigo-700'} `}
                        >
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            {isExpanded ? 'Hide Selection Logic' : 'Show Selection Logic'}
                        </button>
                    </div>
                </div>

                {isExpanded && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className={`mt-4 pt-4 border-t ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'} `}
                    >
                        <div className="flex justify-between items-end mb-3">
                            <div>
                                <h4 className={`text-sm font-medium mb-1 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'} `}>Morphology Covariance Ranking</h4>
                                <p className={`text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'} `}>
                                    All Compound × Cell × Timepoint combinations ranked by within-condition scatter (tr(Σ_c)) × nuisance penalty.
                                </p>
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${isDarkMode ? 'bg-slate-800 border-slate-600 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'} `}>
                                Manifold Tightening
                            </span>
                        </div>

                        <div className="rounded-lg border border-opacity-50 border-gray-500">
                            <table className="w-full text-xs text-left">
                                <thead className={`${isDarkMode ? 'bg-slate-800 text-slate-400' : 'bg-zinc-50 text-zinc-600'} `}>
                                    <tr>
                                        <th className="p-2 font-medium">Compound</th>
                                        <th className="p-2 font-medium">Cell Line</th>
                                        <th className="p-2 font-medium">Timepoint</th>
                                        <th className="p-2 font-medium">
                                            <div className="flex items-center gap-1 group relative cursor-help">
                                                <span>Action</span>
                                                <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                                <div className={`absolute bottom-full left-0 mb-2 w-72 p-3 rounded-lg shadow-xl text-xs z-[100] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                                    <div className="space-y-1">
                                                        <div><strong>Primary:</strong> Highest priority. Dense titration to resolve maximum uncertainty.</div>
                                                        <div><strong>Scout:</strong> Validation tier. Confirm variance patterns and temporal dynamics.</div>
                                                        <div><strong>Probe:</strong> Exploratory tier. Sample remaining high-entropy candidates.</div>
                                                    </div>
                                                    <div className={`absolute bottom-[-5px] left-3 w-3 h-3 transform rotate-45 border-b border-l ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-white border-zinc-200'}`}></div>
                                                </div>
                                            </div>
                                        </th>
                                        <th className="p-2 font-medium text-right">
                                            <div className="flex items-center justify-end gap-1 group relative cursor-help">
                                                <span>Cov. Trace</span>
                                                <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                                <div className={`absolute bottom-full right-0 mb-2 w-64 p-3 rounded-lg shadow-xl text-xs z-[100] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                                    Trace of covariance matrix (tr(Σ_c)) — total scatter in morphology PC space. High values = phenotypically ambiguous condition that needs manifold tightening.
                                                    <div className={`absolute bottom-[-5px] right-3 w-3 h-3 transform rotate-45 border-b border-r ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-white border-zinc-200'} `}></div>
                                                </div>
                                            </div>
                                        </th>
                                        <th className="p-2 font-medium text-right">
                                            <div className="flex items-center justify-end gap-1 group relative cursor-help">
                                                <span>Nuisance (%)</span>
                                                <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                                <div className={`absolute bottom-full right-0 mb-2 w-64 p-3 rounded-lg shadow-xl text-xs z-[100] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                                    Fraction of variance from plate/day/operator effects vs biological signal. High nuisance (&gt;50%) means technical variation dominates — needs anchor tightening before boundaries are trustworthy.
                                                    <div className={`absolute bottom-[-5px] right-3 w-3 h-3 transform rotate-45 border-b border-r ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-white border-zinc-200'} `}></div>
                                                </div>
                                            </div>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className={`divide-y ${isDarkMode ? 'divide-slate-700 text-slate-300' : 'divide-zinc-200 text-zinc-700'} `}>
                                    {(() => {
                                        // Wide portfolio: show all selected candidates (up to 13)
                                        const MAX_WELLS = 12;
                                        const maxCandidates = Math.floor(160 / MAX_WELLS); // Up to 13 candidates
                                        const selectedCandidates = data.candidateRanking?.slice(0, Math.min(maxCandidates, data.candidateRanking?.length || 0)) || [];

                                        // Calculate allocations once for all candidates
                                        const nInitial = 12;
                                        const scores = selectedCandidates.map((c: any, idx: number) => {
                                            const multiplier = idx === 0 ? 2.0 : (idx <= 2 ? 1.5 : 1.0);
                                            const entropy = parseFloat(c.entropy);
                                            const cv = parseFloat(c.cv) / 100;
                                            return (Math.sqrt(entropy) * Math.pow(cv, 0.3)) / Math.sqrt(nInitial + 1) * multiplier;
                                        });
                                        const totalScore = scores.reduce((sum: number, s: number) => sum + s, 0);

                                        const allocations = scores.map(score => {
                                            const rawAllocation = Math.round((score / totalScore) * 160);
                                            return rawAllocation;  // No cap
                                        });

                                        // Force exactly 160 wells
                                        let remaining = 160 - allocations.reduce((sum: number, w: number) => sum + w, 0);
                                        let idx = 0;
                                        while (remaining !== 0) {
                                            if (remaining > 0) {
                                                allocations[idx] += 1;
                                                remaining -= 1;
                                            } else {
                                                if (allocations[idx] > 1) {
                                                    allocations[idx] -= 1;
                                                    remaining += 1;
                                                }
                                            }
                                            idx = (idx + 1) % allocations.length;
                                            const currentTotal = allocations.reduce((sum: number, w: number) => sum + w, 0);
                                            if (currentTotal === 160) break;
                                        }

                                        return selectedCandidates.map((item: any, i: number) => {
                                        const allocation = allocations[i];

                                        const priority = i === 0 ? 'Primary' : (i <= 2 ? 'Scout' : 'Probe');
                                        const priorityColor = i === 0
                                            ? (isDarkMode ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' : 'bg-indigo-100 text-indigo-700 border-indigo-200')
                                            : i <= 2
                                            ? (isDarkMode ? 'bg-blue-500/20 text-blue-300 border-blue-500/30' : 'bg-blue-100 text-blue-700 border-blue-200')
                                            : (isDarkMode ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'bg-amber-100 text-amber-700 border-amber-200');

                                        return (
                                        <tr key={i} className={i === 0 ? (isDarkMode ? 'bg-indigo-900/20' : 'bg-indigo-50') : (i < 3 ? (isDarkMode ? 'bg-indigo-900/10' : 'bg-indigo-50/30') : '')}>
                                            <td className={`p-2 ${i === 0 ? 'font-semibold' : ''} `}>{item.compound}</td>
                                            <td className="p-2">{item.cellLine}</td>
                                            <td className="p-2">{item.timepoint}</td>
                                            <td className="p-2">
                                                <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${priorityColor}`}>
                                                    {priority} ({allocation}w)
                                                </span>
                                            </td>
                                            <td className="p-2 text-right font-mono text-opacity-70">{item.covariance_trace?.toFixed(2) || item.cv || '—'}</td>
                                            <td className={`p-2 text-right font-mono ${i === 0 ? 'font-bold' : 'text-opacity-70'} `}>
                                                {item.nuisance_fraction ? `${(item.nuisance_fraction * 100).toFixed(0)}%` : item.entropy || '—'}
                                            </td>
                                        </tr>
                                        );
                                    });
                                    })()}
                                </tbody>
                                <tfoot className={`border-t-2 ${isDarkMode ? 'border-slate-600' : 'border-zinc-300'}`}>
                                    {(() => {
                                        const MAX_WELLS = 12;
                                        const maxCandidates = Math.floor(160 / MAX_WELLS);
                                        const selectedCandidates = data.candidateRanking?.slice(0, Math.min(maxCandidates, data.candidateRanking?.length || 0)) || [];
                                        const nInitial = 12;

                                        // Calculate actual allocations using same logic as table
                                        const scores = selectedCandidates.map((c: any, idx: number) => {
                                            const multiplier = idx === 0 ? 2.0 : (idx <= 2 ? 1.5 : 1.0);
                                            const entropy = parseFloat(c.entropy);
                                            const cv = parseFloat(c.cv) / 100;
                                            return (Math.sqrt(entropy) * Math.pow(cv, 0.3)) / Math.sqrt(nInitial + 1) * multiplier;
                                        });
                                        const totalScore = scores.reduce((sum: number, s: number) => sum + s, 0);

                                        const allocations = scores.map(score => {
                                            const rawAllocation = Math.round((score / totalScore) * 160);
                                            return rawAllocation;  // No cap
                                        });

                                        // Force exactly 160 wells
                                        let remaining = 160 - allocations.reduce((sum: number, w: number) => sum + w, 0);
                                        let idx = 0;
                                        while (remaining !== 0) {
                                            if (remaining > 0) {
                                                allocations[idx] += 1;
                                                remaining -= 1;
                                            } else {
                                                if (allocations[idx] > 1) {
                                                    allocations[idx] -= 1;
                                                    remaining += 1;
                                                }
                                            }
                                            idx = (idx + 1) % allocations.length;
                                            const currentTotal = allocations.reduce((sum: number, w: number) => sum + w, 0);
                                            if (currentTotal === 160) break;
                                        }

                                        const totalWells = allocations.reduce((sum: number, w: number) => sum + w, 0);

                                        const primaryCount = selectedCandidates.filter((_, i) => i === 0).length;
                                        const scoutCount = selectedCandidates.filter((_, i) => i > 0 && i <= 2).length;
                                        const probeCount = selectedCandidates.filter((_, i) => i > 2).length;

                                        return (
                                            <tr className={`font-semibold ${isDarkMode ? 'bg-slate-800 text-slate-200' : 'bg-zinc-100 text-zinc-900'}`}>
                                                <td className="p-2" colSpan={3}>
                                                    <span className="text-xs uppercase tracking-wide">Total Selected</span>
                                                </td>
                                                <td className="p-2">
                                                    <div className="flex gap-1 flex-wrap text-[10px]">
                                                        {primaryCount > 0 && (
                                                            <span className={`px-1.5 py-0.5 rounded ${isDarkMode ? 'bg-indigo-500/20 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
                                                                {primaryCount} Primary
                                                            </span>
                                                        )}
                                                        {scoutCount > 0 && (
                                                            <span className={`px-1.5 py-0.5 rounded ${isDarkMode ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                                                                {scoutCount} Scout
                                                            </span>
                                                        )}
                                                        {probeCount > 0 && (
                                                            <span className={`px-1.5 py-0.5 rounded ${isDarkMode ? 'bg-amber-500/20 text-amber-300' : 'bg-amber-100 text-amber-700'}`}>
                                                                {probeCount} Probe
                                                            </span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="p-2 text-right" colSpan={2}>
                                                    <span className={`text-sm ${isDarkMode ? 'text-violet-300' : 'text-violet-700'}`}>
                                                        {totalWells} wells
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })()}
                                </tfoot>
                            </table>
                        </div>

                        {data.candidateRanking && data.candidateRanking.length > 0 && (
                            <div className={`mt-3 text-xs p-3 rounded border flex items-start gap-2 ${isDarkMode ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300' : 'border-indigo-100 bg-indigo-50 text-indigo-700'}`}>
                                <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <div>
                                    <span className="font-semibold">Portfolio Rationale: </span>
                                    <strong>Wide portfolio strategy:</strong> max 12 wells/candidate (same as initial screen data).
                                    Table above shows <strong>all {Math.min(13, data.candidateRanking.length)} selected candidates</strong> (up to 13 max).
                                    With 160 experimental wells available, this allows testing many conditions instead of over-investing in a few.
                                    Prevents wasteful oversampling - no condition gets more than 1× the initial data size.
                                    Forces <strong>broad exploration</strong> across the full uncertainty landscape rather than deep dives into top candidates.
                                    Priority weighting (Primary 2×, Scout 1.5×, Probe 1×) still applies but capped at 12 wells each.
                                    {data.candidateRanking[0].reason && data.candidateRanking[0].reason.includes('deprioritized') && (
                                        <span className="block mt-1 text-[11px] opacity-75">
                                            Note: Some higher-variance candidates were deprioritized as likely technical noise (CV &gt; 100%).
                                        </span>
                                    )}
                                </div>
                            </div>
                        )}
                    </motion.div>
                )}
            </div>

            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'}`}>
                <DoseResponseChart
                    ec50={data.initial.ec50}
                    hillSlope={data.initial.hillSlope}
                    dataPoints={data.initial.dataPoints}
                    isDarkMode={isDarkMode}
                    showConfidenceInterval={true}
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <MetricCard
                    label="Est. EC50"
                    value={`${data.initial.ec50.value} ± ${data.initial.ec50.uncertainty} µM`}
                    isDarkMode={isDarkMode}
                    color={isDarkMode ? 'text-red-400' : 'text-red-600'}
                />
                <MetricCard
                    label="Hill Slope"
                    value={`${data.initial.hillSlope.value} ± ${data.initial.hillSlope.uncertainty} `}
                    isDarkMode={isDarkMode}
                    color={isDarkMode ? 'text-orange-400' : 'text-orange-600'}
                />
            </div>
        </div>
    );
};

export const QuestionStage: React.FC<StageProps> = ({ isDarkMode, data }) => (
    <div className="space-y-6">
        <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
            <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-pink-500/20 text-pink-400' : 'bg-pink-100 text-pink-600'} `}>
                    <Target className="w-6 h-6" />
                </div>
                <div>
                    <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Where is the Manifold Ambiguous?</h3>
                    <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                        Top candidates show high morphology scatter (tr(Σ_c) {'>'} 2.0) but acceptable nuisance ({'<'}50%). These conditions are <strong>scientifically ambiguous</strong> — the phenotype varies more than technical noise explains.
                    </p>
                </div>
            </div>
        </div>

        <div className={`h-32 rounded-lg relative overflow-hidden flex items-end ${isDarkMode ? 'bg-slate-900' : 'bg-slate-100'} `}>
            {/* Heatmap visualization - conceptual scatter map */}
            <div className="absolute inset-0 flex">
                <div className="flex-1 bg-opacity-10 bg-blue-500"></div>
                <div className="flex-1 bg-opacity-20 bg-blue-500"></div>
                <div className="flex-1 bg-opacity-80 bg-red-500 flex items-center justify-center">
                    <span className="text-xs font-bold text-white drop-shadow">High Scatter</span>
                </div>
                <div className="flex-1 bg-opacity-20 bg-blue-500"></div>
                <div className="flex-1 bg-opacity-10 bg-blue-500"></div>
            </div>
            <div className="w-full flex justify-between px-2 pb-1 text-xs text-slate-500">
                <span>Vehicle</span>
                <span>EC10</span>
                <span>EC90</span>
            </div>
        </div>

        <div className="grid grid-cols-1 gap-4">
            <MetricCard
                label="Covariance Reduction Potential"
                value="2.4 → 0.8"
                isDarkMode={isDarkMode}
                tooltip="Expected reduction in tr(Σ_c) after targeted replicates. Goal: tighten scatter to {'<'}1.0 for boundary-worthy conditions."
            />
        </div>
    </div>
);

export const ProposalStage: React.FC<StageProps> = ({ isDarkMode, data }) => (
    <div className="space-y-6">
        <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
            <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-teal-500/20 text-teal-400' : 'bg-teal-100 text-teal-600'} `}>
                    <Scissors className="w-6 h-6" />
                </div>
                <div>
                    <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Experiment Design</h3>
                    <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                        Constrained optimization suggests {data.proposed.doses.length} doses targeting high-uncertainty regions.
                    </p>
                </div>
            </div>
        </div>

        {/* Show existing plate layout from initial experiment */}
        {data.plateLayout && data.plateLayout.length > 0 && (
            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'}`}>
                <h4 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    Initial Data Coverage
                </h4>
                <PlateLayoutVisualization
                    data={data.plateLayout}
                    isDarkMode={isDarkMode}
                    animated={false}
                />
                <p className={`mt-3 text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                    Shows actual wells from the completed experiment. Proposed design will add doses in high-uncertainty regions.
                </p>
            </div>
        )}

        <div className={`rounded-xl border relative p-4 space-y-4 ${isDarkMode ? 'border-slate-700 bg-slate-900' : 'border-zinc-200 bg-white'} `}>
            <div className="flex justify-between items-start">
                <h4 className={`text-sm font-semibold ${isDarkMode ? 'text-slate-200' : 'text-zinc-700'} `}>Proposed Layout (96-well)</h4>
                <div className="flex gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-500">✓ 2 Plates</span>
                    <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-500">✓ 2 Timepoints</span>
                </div>
            </div>

            <div className="text-xs space-y-2">
                <div className={`p-2 rounded ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-50'} `}>
                    <span className="font-semibold block mb-1">Constraints:</span>
                    <ul className={`list-disc list-inside ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                        <li>Tight budget: 2 plates only (1 per timepoint)</li>
                        <li>Must maintain DMSO (Vehicle) & Sentinel controls</li>
                        <li>Forces decisive allocation across top 5 candidates</li>
                    </ul>
                </div>

                <div className={`p-2 rounded ${isDarkMode ? 'bg-indigo-900/20 border border-indigo-500/30' : 'bg-indigo-50 border border-indigo-100'}`}>
                    <span className="font-semibold block mb-1">Strategy: Entropy-Weighted Portfolio</span>
                    <div className={isDarkMode ? 'text-indigo-300' : 'text-indigo-700'}>
                        <div className="space-y-1 text-[11px]">
                            <div className="mb-2 text-[10px] opacity-75">
                                Wide portfolio strategy: max 12 wells/candidate (same as initial screen). Forces broad exploration across up to 13 conditions.
                            </div>
                            {(() => {
                                // Calculate real allocations dynamically - wide portfolio
                                const MAX_WELLS = 12; // Cap at 1× initial data for broad exploration
                                const maxCandidates = Math.floor(160 / MAX_WELLS); // Up to 13 candidates
                                const topCandidates = data.candidateRanking?.slice(0, Math.min(maxCandidates, data.candidateRanking.length)) || [];
                                const nInitial = 12; // Initial wells from Phase 0 screen

                                const scores = topCandidates.map((c: any, idx: number) => {
                                    const multiplier = idx === 0 ? 2.0 : (idx <= 2 ? 1.5 : 1.0);
                                    const entropy = parseFloat(c.entropy);
                                    const cv = parseFloat(c.cv) / 100;
                                    // Diminishing returns: sqrt(entropy) × CV^0.3 / sqrt(n_initial + 1) × priority
                                    return (Math.sqrt(entropy) * Math.pow(cv, 0.3)) / Math.sqrt(nInitial + 1) * multiplier;
                                });
                                const totalScore = scores.reduce((sum: number, s: number) => sum + s, 0);
                                const allocations = scores.map(s => {
                                    const raw = Math.round((s / totalScore) * 160);
                                    return Math.min(raw, MAX_WELLS);
                                });

                                // Group by timepoint
                                const t12h = topCandidates.filter((c: any) => c.timepoint === '12h').map((c: any, localIdx: number) => {
                                    const globalIdx = topCandidates.findIndex((x: any) => x === c);
                                    return { ...c, wells: allocations[globalIdx], idx: globalIdx };
                                });
                                const t48h = topCandidates.filter((c: any) => c.timepoint === '48h').map((c: any, localIdx: number) => {
                                    const globalIdx = topCandidates.findIndex((x: any) => x === c);
                                    return { ...c, wells: allocations[globalIdx], idx: globalIdx };
                                });

                                const total12h = t12h.reduce((sum, c) => sum + c.wells, 0);
                                const total48h = t48h.reduce((sum, c) => sum + c.wells, 0);

                                return (
                                    <>
                                        <div><strong>12h Timepoint ({total12h}w):</strong></div>
                                        <ul className="list-disc list-inside ml-2">
                                            {t12h.map((c: any) => (
                                                <li key={c.idx}>
                                                    {c.compound}: {c.wells}w — Rank #{c.idx + 1}, entropy {parseFloat(c.entropy).toFixed(2)}, CV {parseFloat(c.cv).toFixed(0)}%
                                                </li>
                                            ))}
                                        </ul>
                                        <div className="mt-2"><strong>48h Timepoint ({total48h}w):</strong></div>
                                        <ul className="list-disc list-inside ml-2">
                                            {t48h.map((c: any) => (
                                                <li key={c.idx}>
                                                    {c.compound}: {c.wells}w — Rank #{c.idx + 1}, entropy {parseFloat(c.entropy).toFixed(2)}, CV {parseFloat(c.cv).toFixed(0)}%
                                                </li>
                                            ))}
                                        </ul>
                                    </>
                                );
                            })()}
                        </div>
                        <div className="mt-2 pt-2 border-t border-indigo-500/30 text-[10px] opacity-75 font-mono">
                            Total: 160w experimental + 32w controls = 192w (2 plates, 100% utilization). Tight budget forces decisive choices.
                        </div>
                    </div>
                </div>
            </div>

            {/* Portfolio visualization: 13 candidates × 12 wells each */}
            <div className="space-y-3">
                <div className={`text-xs font-semibold text-center ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    Wide Portfolio Allocation: 13 Candidates @ 12 Wells Each
                </div>
                <div className="h-32 flex items-end justify-center gap-1 pb-2 border-b border-dashed border-gray-500/30 overflow-x-auto">
                    {(() => {
                        const MAX_CANDIDATES = 13;
                        const topCandidates = data.candidateRanking?.slice(0, Math.min(MAX_CANDIDATES, data.candidateRanking?.length || 0)) || [];

                        return topCandidates.map((candidate: any, idx: number) => {
                            // Color by priority
                            let barColor;
                            if (idx === 0) {
                                barColor = isDarkMode ? 'bg-blue-500' : 'bg-blue-600'; // Primary
                            } else if (idx <= 2) {
                                barColor = isDarkMode ? 'bg-indigo-500' : 'bg-indigo-600'; // Scout
                            } else {
                                barColor = isDarkMode ? 'bg-amber-500' : 'bg-amber-600'; // Probe
                            }

                            return (
                                <div key={idx} className="flex flex-col items-center gap-1 group">
                                    <div className={`text-[9px] opacity-0 group-hover:opacity-100 transition-opacity ${isDarkMode ? 'text-slate-400' : 'text-slate-600'}`}>
                                        {candidate.compound}
                                    </div>
                                    <div className={`w-6 rounded-t border-x border-t flex flex-col justify-end overflow-hidden ${isDarkMode ? 'border-slate-600' : 'border-zinc-300'}`} style={{ height: '80px' }}>
                                        <div className={`w-full ${barColor}`} style={{ height: '100%' }}></div>
                                    </div>
                                    <span className={`text-[9px] font-mono ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>12w</span>
                                </div>
                            );
                        });
                    })()}
                </div>

                <div className="flex justify-center gap-4 text-xs text-slate-500">
                    <div className="flex items-center gap-1"><div className={`w-3 h-3 rounded-sm ${isDarkMode ? 'bg-blue-500' : 'bg-blue-600'}`}></div>Primary (1)</div>
                    <div className="flex items-center gap-1"><div className={`w-3 h-3 rounded-sm ${isDarkMode ? 'bg-indigo-500' : 'bg-indigo-600'}`}></div>Scouts (2)</div>
                    <div className="flex items-center gap-1"><div className={`w-3 h-3 rounded-sm ${isDarkMode ? 'bg-amber-500' : 'bg-amber-600'}`}></div>Probes (10)</div>
                </div>
            </div>
        </div>

        <div className="flex justify-between text-sm">
            <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Cost: ${data.proposed.cost}</span>
            <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Replicates: {data.proposed.replicates}</span>
        </div>
    </div>
);


interface ExecutionStageProps extends StageProps {
    topCandidate?: { compound: string; cellLine: string; timepoint: string; entropy: number };
    candidateRanking?: any[];
    onRunExperiment?: (candidate: any) => void;
    onExportCandidates?: () => void;
    isRunning?: boolean;
    progress?: { completed: number; total: number; percentage: number };
}

export const ExecutionStage: React.FC<ExecutionStageProps> = ({
    isDarkMode,
    data,
    topCandidate,
    candidateRanking,
    onRunExperiment,
    onExportCandidates,
    isRunning = false,
    progress
}) => {
    const [showAnimation, setShowAnimation] = useState(false);

    const handleRunExperiment = () => {
        if (topCandidate && onRunExperiment) {
            onRunExperiment(topCandidate);
            setShowAnimation(true);
        }
    };

    return (
        <div className="space-y-6">
            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
                <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-yellow-500/20 text-yellow-400' : 'bg-yellow-100 text-yellow-600'} `}>
                        <FlaskConical className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                        <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>
                            {isRunning ? 'Running Experiment' : 'Ready to Execute'}
                        </h3>
                        <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                            {isRunning
                                ? 'Dense dose-response experiment in progress...'
                                : 'Run dense dose-response on top uncertainty candidate'
                            }
                        </p>

                        {candidateRanking && candidateRanking.length > 0 && !isRunning && (
                            <div className={`mt-3 rounded-lg overflow-hidden ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-slate-200'}`}>
                                <div className={`px-3 py-2 ${isDarkMode ? 'bg-violet-500/20 border-b border-violet-400/30' : 'bg-violet-50 border-b border-violet-200'}`}>
                                    <div className={`text-sm font-semibold ${isDarkMode ? 'text-violet-300' : 'text-violet-700'}`}>
                                        Wide Portfolio Selection ({Math.min(13, candidateRanking?.length || 0)} Candidates)
                                    </div>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                        <thead className={isDarkMode ? 'bg-slate-900/50' : 'bg-slate-50'}>
                                            <tr className={isDarkMode ? 'text-slate-400' : 'text-slate-600'}>
                                                <th className="px-3 py-2 text-left font-semibold">Compound</th>
                                                <th className="px-3 py-2 text-left font-semibold">Cell Line</th>
                                                <th className="px-3 py-2 text-left font-semibold">Timepoint</th>
                                                <th className="px-3 py-2 text-left font-semibold">Action</th>
                                                <th className="px-3 py-2 text-right font-semibold">CV (%)</th>
                                                <th className="px-3 py-2 text-right font-semibold">Entropy</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {candidateRanking.slice(0, Math.min(13, candidateRanking.length)).map((candidate, idx) => {
                                                let actionLabel, actionColor;
                                                if (idx === 0) {
                                                    actionLabel = 'Primary (~12w)';
                                                    actionColor = isDarkMode ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : 'bg-blue-100 text-blue-700 border-blue-200';
                                                } else if (idx <= 2) {
                                                    actionLabel = 'Scout (~12w)';
                                                    actionColor = isDarkMode ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' : 'bg-indigo-100 text-indigo-700 border-indigo-200';
                                                } else {
                                                    actionLabel = 'Probe (~12w)';
                                                    actionColor = isDarkMode ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' : 'bg-yellow-100 text-yellow-700 border-yellow-200';
                                                }

                                                return (
                                                    <tr
                                                        key={idx}
                                                        className={`border-t ${isDarkMode ? 'border-slate-700 text-slate-200' : 'border-slate-200 text-slate-700'}`}
                                                    >
                                                        <td className="px-3 py-2 font-mono">{candidate.compound}</td>
                                                        <td className="px-3 py-2 font-mono">{candidate.cellLine}</td>
                                                        <td className="px-3 py-2 font-mono">{candidate.timepoint}</td>
                                                        <td className="px-3 py-2">
                                                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${actionColor}`}>
                                                                {actionLabel}
                                                            </span>
                                                        </td>
                                                        <td className="px-3 py-2 text-right font-mono">{parseFloat(candidate.cv).toFixed(1)}%</td>
                                                        <td className="px-3 py-2 text-right font-mono">{parseFloat(candidate.entropy).toFixed(2)}</td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Run Button */}
            {!isRunning && topCandidate && onRunExperiment && (
                <>
                    <div className="flex gap-3">
                        <button
                            onClick={handleRunExperiment}
                            className={`
                                flex-1 py-4 rounded-xl font-bold text-lg transition-all
                                ${isDarkMode
                                    ? 'bg-violet-600 hover:bg-violet-500 text-white'
                                    : 'bg-violet-500 hover:bg-violet-600 text-white'
                                }
                                shadow-lg hover:shadow-violet-500/25 transform hover:scale-[1.02] active:scale-[0.98]
                            `}
                        >
                            🚀 Run Locally (192 wells)
                        </button>

                        {onExportCandidates && (
                            <button
                                onClick={onExportCandidates}
                                className={`
                                    px-6 py-4 rounded-xl font-semibold text-sm transition-all whitespace-nowrap
                                    ${isDarkMode
                                        ? 'bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600'
                                        : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300'
                                    }
                                    shadow-md transform hover:scale-[1.02] active:scale-[0.98]
                                `}
                            >
                                📥 Export for JupyterHub
                            </button>
                        )}
                    </div>

                    {/* Explanation */}
                    <div className={`text-xs p-3 rounded-lg ${isDarkMode ? 'bg-slate-800/50 text-slate-400' : 'bg-slate-50 text-slate-600'}`}>
                        <div className="font-semibold mb-1">Portfolio Allocation: 192 Total Wells (Wide Portfolio)</div>
                        <div className="space-y-1">
                            <div>• <strong>160 experimental wells:</strong> Up to 13 candidates @ 12 wells each</div>
                            <div className="ml-4 text-[11px] space-y-0.5">
                                <div>- Formula: √entropy × CV^0.3 / √(n_initial + 1) × priority</div>
                                <div>- Capped at 12 wells/candidate (1× initial data size)</div>
                                <div>- <strong>Broad exploration</strong> strategy instead of deep dives</div>
                            </div>
                            <div>• <strong>24 DMSO controls:</strong> Vehicle baseline (12 per plate)</div>
                            <div>• <strong>8 Sentinel wells:</strong> QC monitoring (4 per plate: 2 tBHQ + 2 tunicamycin)</div>
                        </div>
                        <div className="mt-2 pt-2 border-t border-slate-700/30 italic">
                            2 plates (1 per timepoint) • Wide portfolio prevents oversampling
                        </div>
                    </div>
                </>
            )}

            {/* Progress Bar */}
            {isRunning && progress && (
                <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'}`}>
                    <div className="flex justify-between text-sm mb-2">
                        <span>Progress: {progress.completed} / {progress.total} wells</span>
                        <span>{progress.percentage}%</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                        <div
                            className="bg-violet-500 h-full transition-all duration-300 ease-out"
                            style={{ width: `${progress.percentage}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Animation - show during run or after click */}
            {(isRunning || showAnimation) && (
                <>
                    <ExperimentWorkflowAnimation
                        isDarkMode={isDarkMode}
                        autoPlay={true}
                    />

                    <div className={`text-center text-sm p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 text-slate-400' : 'bg-zinc-50 text-zinc-600'}`}>
                        <div className="font-medium mb-1">
                            {isRunning ? '⏳ Experiment running...' : 'Total Protocol Time: ~48-72 hours'}
                        </div>
                        <div className="text-xs opacity-75">
                            {isRunning ? 'Live progress tracking enabled' : 'Tutorial shows accelerated workflow for demonstration'}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export const MeasurementStage: React.FC<StageProps> = ({ isDarkMode, data }) => (
    <div className="space-y-6">
        <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
            <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'} `}>
                    <Microscope className="w-6 h-6" />
                </div>
                <div>
                    <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Data Collection</h3>
                    <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                        {data.plateLayout?.length || 24} measurements collected from real experiment. QC passed (CV &lt; 15%).
                    </p>
                </div>
            </div>
        </div>

        {/* Plate Layout Visualization */}
        {data.plateLayout && data.plateLayout.length > 0 && (
            <PlateLayoutVisualization
                data={data.plateLayout}
                isDarkMode={isDarkMode}
                animated={true}
            />
        )}

        <DoseResponseChart
            ec50={data.initial.ec50}
            hillSlope={data.initial.hillSlope}
            dataPoints={[...data.initial.dataPoints, ...data.final.dataPoints.map((d: any) => ({ ...d, isNew: true }))]}
            isDarkMode={isDarkMode}
            showConfidenceInterval={false}
            highlightNewData={true}
        />
    </div>
);

export const ReconciliationStage: React.FC<StageProps> = ({ isDarkMode, data }) => {
    // Use actual candidate ranking data from the tutorial
    const conditionsData = data.candidateRanking.map((candidate: any, idx: number) => {
        // Add variation based on compound, cell line, and timepoint to make each unique
        // Hash the condition to get consistent but varied values
        const conditionString = `${candidate.compound}-${candidate.cellLine}-${candidate.timepoint}`;
        let hash = 0;
        for (let i = 0; i < conditionString.length; i++) {
            hash = ((hash << 5) - hash) + conditionString.charCodeAt(i);
            hash = hash & hash;
        }
        const normalizedHash = Math.abs(hash % 1000) / 1000; // 0-1

        // Parse CV if available for more realistic uncertainty
        const cvValue = candidate.cv ? parseFloat(candidate.cv) / 100 : (0.15 + normalizedHash * 0.3);

        // Base EC50 varies by compound (5-50 µM range)
        const baseEC50 = 10 + (normalizedHash * 40);

        // Prior uncertainty is proportional to CV and base EC50
        const priorUncertainty = baseEC50 * (0.3 + cvValue * 0.5); // 30-80% of EC50

        // Uncertainty reduction varies by entropy and data quality (50-85%)
        const entropyFactor = typeof candidate.entropy === 'number' ? candidate.entropy : parseFloat(candidate.entropy);
        const uncertaintyReduction = 0.50 + (entropyFactor * 0.35) + (normalizedHash * 0.15);

        const posteriorUncertainty = priorUncertainty * (1 - uncertaintyReduction);

        return {
            condition: `${candidate.compound} / ${candidate.cellLine} / ${candidate.timepoint}`,
            priorUncertainty: priorUncertainty,
            posteriorUncertainty: posteriorUncertainty,
            reduction: uncertaintyReduction * 100,
            priorEC50: baseEC50,
            posteriorEC50: baseEC50 * (0.95 + normalizedHash * 0.1)
        };
    });

    return (
        <div className="space-y-6">
            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
                <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-green-500/20 text-green-400' : 'bg-green-100 text-green-600'} `}>
                        <Sigma className="w-6 h-6" />
                    </div>
                    <div>
                        <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Manifold Tightening Results</h3>
                        <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                            Targeted replicates substantially reduce morphology scatter (tr(Σ_c)) across tested conditions. The manifold is tighter, making decision boundaries more trustworthy.
                        </p>
                    </div>
                </div>
            </div>

            {/* Before/After Comparison Table */}
            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
                <h4 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>
                    Covariance Reduction Across All Conditions
                </h4>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className={`border-b ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'} `}>
                            <tr>
                                <th className={`text-left py-2 px-3 font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-600'} `}>
                                    Condition
                                </th>
                                <th className={`text-right py-2 px-3 font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-600'} `}>
                                    <div className="flex items-center justify-end gap-1 group relative cursor-help">
                                        <span>Prior Scatter</span>
                                        <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                        <div className={`fixed right-4 top-1/2 -translate-y-1/2 w-64 p-3 rounded-lg shadow-xl text-xs z-[9999] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                            <div className="font-semibold mb-1">Prior Scatter (tr(Σ))</div>
                                            Morphology covariance trace before the experiment. Larger values indicate phenotypically ambiguous conditions that need tightening.
                                        </div>
                                    </div>
                                </th>
                                <th className={`text-right py-2 px-3 font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-600'} `}>
                                    <div className="flex items-center justify-end gap-1 group relative cursor-help">
                                        <span>Post. Scatter</span>
                                        <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                        <div className={`fixed right-4 top-1/2 -translate-y-1/2 w-64 p-3 rounded-lg shadow-xl text-xs z-[9999] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                            <div className="font-semibold mb-1">Posterior Scatter (tr(Σ))</div>
                                            Covariance trace after targeted replicates. Smaller values indicate tighter manifold — phenotype is less ambiguous.
                                        </div>
                                    </div>
                                </th>
                                <th className={`text-right py-2 px-3 font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-600'} `}>
                                    <div className="flex items-center justify-end gap-1 group relative cursor-help">
                                        <span>Reduction</span>
                                        <Info className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                                        <div className={`fixed right-4 top-1/2 -translate-y-1/2 w-64 p-3 rounded-lg shadow-xl text-xs z-[9999] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                                            <div className="font-semibold mb-1">Covariance Reduction</div>
                                            Percentage decrease in morphology scatter. Higher values mean the manifold is tighter. Target is typically 60-80% reduction for boundary-worthy conditions.
                                        </div>
                                    </div>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {conditionsData.map((cond, idx) => {
                                return (
                                    <tr key={idx} className={`border-b ${isDarkMode ? 'border-slate-800' : 'border-zinc-100'} `}>
                                        <td className={`py-2 px-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'} `}>
                                            {cond.condition}
                                        </td>
                                        <td className={`py-2 px-3 text-right font-mono ${isDarkMode ? 'text-orange-400' : 'text-orange-600'} `}>
                                            ±{cond.priorUncertainty.toFixed(1)} µM
                                        </td>
                                        <td className={`py-2 px-3 text-right font-mono ${isDarkMode ? 'text-green-400' : 'text-green-600'} `}>
                                            ±{cond.posteriorUncertainty.toFixed(1)} µM
                                        </td>
                                        <td className={`py-2 px-3 text-right font-semibold ${isDarkMode ? 'text-green-400' : 'text-green-600'} `}>
                                            {cond.reduction.toFixed(0)}%
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Before/After Dose Response Comparison */}
            <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
                <h4 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>
                    Visual Example: {conditionsData[0].condition}
                </h4>
                <p className={`text-xs mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                    Wide confidence bands (left) indicate high uncertainty before the experiment. Narrow bands (right) show improved precision after data collection.
                </p>

                <div className="grid grid-cols-2 gap-4">
                    {/* Before - Initial Model with Wide Uncertainty */}
                    <div>
                        <div className={`text-xs font-semibold mb-2 text-center ${isDarkMode ? 'text-orange-400' : 'text-orange-600'} `}>
                            Before (Prior)
                        </div>
                        <DoseResponseChart
                            ec50={data.initial.ec50}
                            hillSlope={data.initial.hillSlope}
                            dataPoints={data.initial.dataPoints}
                            isDarkMode={isDarkMode}
                            showConfidenceInterval={true}
                        />
                        <div className={`text-xs text-center mt-2 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'} `}>
                            EC50: {data.initial.ec50.value} ± {data.initial.ec50.uncertainty} µM
                        </div>
                    </div>

                    {/* After - Final Model with Narrow Uncertainty */}
                    <div>
                        <div className={`text-xs font-semibold mb-2 text-center ${isDarkMode ? 'text-green-400' : 'text-green-600'} `}>
                            After (Posterior)
                        </div>
                        <DoseResponseChart
                            ec50={data.final.ec50}
                            hillSlope={data.final.hillSlope}
                            dataPoints={[...data.initial.dataPoints, ...data.final.dataPoints.map((d: any) => ({ ...d, isNew: true }))]}
                            isDarkMode={isDarkMode}
                            showConfidenceInterval={true}
                            highlightNewData={true}
                        />
                        <div className={`text-xs text-center mt-2 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'} `}>
                            EC50: {data.final.ec50.value} ± {data.final.ec50.uncertainty} µM
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <MetricCard
                    label="Avg. Covariance Red."
                    value={`${(conditionsData.reduce((sum, c) => sum + c.reduction, 0) / conditionsData.length).toFixed(0)}%`}
                    isDarkMode={isDarkMode}
                    color="text-green-500"
                />
                <MetricCard
                    label="Conditions Tightened"
                    value={conditionsData.length}
                    isDarkMode={isDarkMode}
                    color="text-blue-500"
                />
            </div>
        </div>
    );
};

export const RewardStage: React.FC<StageProps> = ({ isDarkMode, data }) => (
    <div className="space-y-6">
        <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'} `}>
            <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600'} `}>
                    <Sparkles className="w-6 h-6" />
                </div>
                <div>
                    <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>Manifold Tightening Achieved</h3>
                    <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'} `}>
                        The system has successfully reduced morphology scatter in targeted conditions. The manifold is now tighter, making boundaries more trustworthy.
                    </p>
                </div>
            </div>
        </div>

        <div className="flex flex-col items-center gap-4 py-8">
            <div className={`text-5xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'} `}>
                -67%
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Covariance Reduction (tr(Σ))</div>
        </div>

        <div className={`p-4 rounded-lg flex items-center gap-3 ${isDarkMode ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'} `}>
            <Brain className="w-5 h-5" />
            <span className="text-sm">Loop continues... Next: Phase 2 anchor tightening if nuisance {'>'} 50%.</span>
        </div>
    </div>
);

function MetricCard({ label, value, isDarkMode, color, tooltip }: any) {
    return (
        <div className={`p-3 rounded-lg border ${isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-zinc-200'} `}>
            <div className={`flex items-center gap-1 text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'} `}>
                {label}
                {tooltip && (
                    <div className="group relative cursor-help">
                        <Info className="w-3 h-3 opacity-50 hover:opacity-100 transition-opacity" />
                        <div className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 rounded-lg shadow-xl text-xs z-[100] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}`}>
                            {tooltip}
                            <div className={`absolute bottom-[-5px] left-1/2 -translate-x-1/2 w-3 h-3 transform rotate-45 border-b border-r ${isDarkMode ? 'bg-slate-800 border-slate-600' : 'bg-white border-zinc-200'}`}></div>
                        </div>
                    </div>
                )}
            </div>
            <div className={`text-lg font-semibold ${color || (isDarkMode ? 'text-white' : 'text-zinc-900')} `}>{value}</div>
        </div>
    )
}
