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
        { compound: 'tBHP', cellLine: 'HEK293', timepoint: '24h', entropy: 0.89 },
        { compound: 'Doxorubicin', cellLine: 'HeLa', timepoint: '48h', entropy: 0.72 },
        { compound: 'Staurosporine', cellLine: 'HepG2', timepoint: '24h', entropy: 0.55 },
        { compound: 'Paclitaxel', cellLine: 'A549', timepoint: '72h', entropy: 0.41 },
        { compound: 'Cisplatin', cellLine: 'MCF7', timepoint: '48h', entropy: 0.38 },
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

    useEffect(() => {
        const fetchData = async () => {
            let fetchedRealData: any[] = [];
            try {
                const designs = await cellThalamusService.getDesigns();

                if (designs && designs.length > 0) {
                    const recentDesigns = designs.slice(0, 10);
                    let allResults: any[] = [];

                    for (const design of recentDesigns) {
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
        };

        fetchData();
    }, []);

    // Merge real data into tutorial data
    const activeData = {
        ...TUTORIAL_DATA,
        candidateRanking: combinedRanking.length > 0 ? combinedRanking : TUTORIAL_DATA.candidateRanking
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

            {/* Stage Content */}
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
                                <p className={`max-w-lg mx-auto text-lg ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                    This interactive walkthrough demonstrates how cell_OS autonomously designs experiments to reduce uncertainty.
                                </p>

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
                                                <span className="font-semibold block mb-0.5">Maximize Information Gain</span>
                                                Identify and resolve areas of highest epistemic uncertainty (ignorance) in the world model.
                                            </p>
                                        </div>

                                        <div className="flex items-start gap-3">
                                            <div className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-orange-400' : 'bg-orange-600'}`}></div>
                                            <p className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                                                <span className="font-semibold block mb-0.5">Minimize Resource Cost</span>
                                                Achieve knowledge gain using the fewest plates, reagents, and robot hours possible.
                                            </p>
                                        </div>

                                        <div className="flex items-start gap-3">
                                            <div className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDarkMode ? 'bg-blue-400' : 'bg-blue-600'}`}></div>
                                            <p className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                                                <span className="font-semibold block mb-0.5">Convergence Criteria</span>
                                                Loop stops when parameter uncertainty hits target (CV &lt; 15%) or marginal gain &lt; cost.
                                            </p>
                                        </div>
                                    </div>

                                    <div className={`mt-4 pt-3 border-t text-xs font-mono flex justify-between ${isDarkMode ? 'border-slate-700 text-slate-500' : 'border-zinc-100 text-zinc-400'}`}>
                                        <span>R = ΔEntropy / Cost</span>
                                        <span>Constraints applied</span>
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

                        {stageIndex === 1 && <WorldModelStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 2 && <QuestionStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 3 && <ProposalStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 4 && <ExecutionStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 5 && <MeasurementStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 6 && <ReconciliationStage isDarkMode={isDarkMode} data={activeData} />}
                        {stageIndex === 7 && <RewardStage isDarkMode={isDarkMode} data={activeData} />}

                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Navigation Controls */}
            {stageIndex > 0 && (
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
