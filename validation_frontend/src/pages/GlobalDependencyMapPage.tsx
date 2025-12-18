import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { DependencyMap } from '../components/DependencyMap';
import { mockWorkflow } from '../data/mockWorkflow';

import { AxisDetailPanel } from '../components/AxisDetailPanel';

import { ThemeToggle } from '../components/ThemeToggle';

const GlobalDependencyMapPage: React.FC = () => {
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

    const selectedAxis = selectedAxisId ? mockWorkflow.axes.find(a => a.id === selectedAxisId) : null;

    const kinds: { value: string; label: string; color: string }[] = [
        { value: 'cell_line', label: 'Biobanking', color: 'bg-violet-500' },
        { value: 'stressor', label: 'Cell Models', color: 'bg-pink-500' },
        { value: 'perturbation', label: 'Functional Genomics', color: 'bg-teal-500' },
        { value: 'measurement', label: 'PST', color: 'bg-orange-500' },
    ];

    return (
        <div className="h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors duration-300">
            <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-8">
                    <h1 className="text-xl font-bold text-slate-900 dark:text-white">Global Dependency Map</h1>

                    <div className="flex items-center space-x-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400 font-medium">Filter by:</span>
                        <div className="flex space-x-2">
                            {kinds.map(kind => (
                                <button
                                    key={kind.value}
                                    onClick={() => toggleKind(kind.value)}
                                    className={`
                                        px-3 py-1.5 rounded-full text-xs font-bold transition-all border
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
                    <ThemeToggle />
                    <Link
                        to="/dashboard"
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                    >
                        ← Back to Dashboard
                    </Link>
                </div>
            </div>
            <div className="flex-grow h-full w-full relative flex">
                <div className="flex-grow h-full">
                    <DependencyMap
                        workflow={mockWorkflow}
                        className="h-full w-full bg-slate-50 dark:bg-slate-900"
                        highlightedKinds={selectedKinds}
                        onNodeClick={handleNodeClick}
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

export default GlobalDependencyMapPage;
