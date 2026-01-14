import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { DependencyMap } from '../components/DependencyMap';
import { mockWorkflowMenadione } from '../data/mockWorkflowMenadione';

import { AxisDetailPanel } from '../components/AxisDetailPanel';

import { ThemeToggle } from '../components/ThemeToggle';

const MenadioneMapPage: React.FC = () => {
    const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
    const [selectedAxisId, setSelectedAxisId] = useState<string | null>(null);

    const toggleKind = (kind: string) => {
        setSelectedKinds(prev =>
            prev.includes(kind)
                ? prev.filter(k => k !== kind)
                : [...prev, kind]
        );
    };

    const handleNodeClick = (_: React.MouseEvent, node: any) => {
        setSelectedAxisId(node.id);
    };

    const selectedAxis = selectedAxisId ? mockWorkflowMenadione.axes.find(a => a.id === selectedAxisId) : null;

    const kinds: { value: string; label: string; color: string }[] = [
        { value: 'cell_line', label: 'Biobanking', color: 'bg-violet-500' },
        { value: 'stressor', label: 'Cell Models', color: 'bg-pink-500' },
        { value: 'perturbation', label: 'Functional Genomics', color: 'bg-teal-500' },
        { value: 'measurement', label: 'PST', color: 'bg-orange-500' },
    ];

    return (
        <div className="fixed top-0 left-0 right-0 bottom-0 w-screen h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors duration-300">
            <div className="shrink-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-8">
                    <div>
                        <h1 className="text-xl font-bold text-slate-900 dark:text-white">{mockWorkflowMenadione.name}</h1>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{mockWorkflowMenadione.id}</p>
                    </div>

                    <div className="flex items-center space-x-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400 font-medium">Filter by:</span>
                        <div className="flex space-x-2">
                            {kinds.map(kind => (
                                <button
                                    key={kind.value}
                                    onClick={() => toggleKind(kind.value)}
                                    className={`
                                        px-2 py-1 rounded-full text-[10px] font-bold transition-all border
                                        ${selectedKinds.includes(kind.value)
                                            ? `${kind.color} text-white border-transparent shadow-md`
                                            : 'bg-white dark:bg-slate-700 text-slate-500 dark:text-slate-300 border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500'
                                        }
                                    `}
                                >
                                    {kind.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Strategy:</span>
                        <Link
                            to="/overall"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-emerald-100 hover:text-emerald-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-emerald-900 dark:hover:text-emerald-300 transition-colors"
                        >
                            Overall
                        </Link>
                    </div>
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Workflows:</span>
                        <Link
                            to="/map"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-blue-100 hover:text-blue-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-blue-900 dark:hover:text-blue-300 transition-colors"
                        >
                            Generic
                        </Link>
                        <Link
                            to="/menadione/map"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300"
                        >
                            Menadione A549
                        </Link>
                    </div>
                    <ThemeToggle />
                    <Link
                        to="/dashboard"
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                    >
                        ← Back to Dashboard
                    </Link>
                </div>
            </div>


            <div className="grow min-h-0 w-full relative flex">
                <div className="grow min-h-0 relative">
                    {/* Swim lane backgrounds and labels - 5 equal lanes at 20% each */}
                    <div className="absolute inset-0 pointer-events-none overflow-hidden flex flex-col">
                        {/* Functional Genomics lane - teal (lane 1) */}
                        <div className="flex-1 bg-teal-300/10 dark:bg-teal-900/10 border-b-2 border-teal-300 dark:border-teal-700 relative">
                            <div className="absolute left-2 top-2 bg-teal-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-20">
                                Functional Genomics
                            </div>
                        </div>
                        {/* Biobanking lane - violet (lane 2) */}
                        <div className="flex-1 bg-violet-300/10 dark:bg-violet-900/10 border-b-2 border-violet-300 dark:border-violet-700 relative">
                            <div className="absolute left-2 top-2 bg-violet-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-20">
                                Biobanking
                            </div>
                        </div>
                        {/* Cell Models lane - pink (lane 3) */}
                        <div className="flex-1 bg-pink-300/10 dark:bg-pink-900/10 border-b-2 border-pink-300 dark:border-pink-700 relative">
                            <div className="absolute left-2 top-2 bg-pink-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-20">
                                Cell Models
                            </div>
                        </div>
                        {/* PST lane - orange (lane 4) */}
                        <div className="flex-1 bg-orange-300/10 dark:bg-orange-900/10 border-b-2 border-orange-300 dark:border-orange-700 relative">
                            <div className="absolute left-2 top-2 bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-20">
                                PST
                            </div>
                        </div>
                        {/* Compute lane - grey (lane 5) */}
                        <div className="flex-1 bg-slate-400/10 dark:bg-slate-700/10 border-b-2 border-slate-400 dark:border-slate-600 relative">
                            <div className="absolute left-2 top-2 bg-slate-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-20">
                                Compute
                            </div>
                        </div>
                    </div>
                    <DependencyMap
                        workflow={mockWorkflowMenadione}
                        className="h-full w-full bg-transparent"
                        highlightedKinds={selectedKinds}
                        onNodeClick={handleNodeClick}
                        hideStatusIcons={false}
                        useTimelineLayout={true}
                    />
                </div>

                {/* Detail Panel Slide-over */}
                {selectedAxis && (
                    <div className="w-[400px] h-full border-l border-slate-200 dark:border-slate-700 shadow-xl z-20 absolute right-0 top-0 bg-white dark:bg-slate-800 transition-colors duration-300">
                        <AxisDetailPanel
                            axis={selectedAxis}
                            onClose={() => setSelectedAxisId(null)}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default MenadioneMapPage;
