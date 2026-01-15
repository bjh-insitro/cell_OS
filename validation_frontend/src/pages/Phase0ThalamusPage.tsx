import React from 'react';
import { Link } from 'react-router-dom';
import { DependencyMap } from '../components/DependencyMap';
import { mockWorkflowPhase0Thalamus } from '../data/mockWorkflowPhase0Thalamus';
import { ThemeToggle } from '../components/ThemeToggle';

const Phase0ThalamusPage: React.FC = () => {
    return (
        <div className="fixed top-0 left-0 right-0 bottom-0 w-screen h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors duration-300">
            <div className="shrink-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-8">
                    <div>
                        <h1 className="text-xl font-bold text-slate-900 dark:text-white">{mockWorkflowPhase0Thalamus.name}</h1>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{mockWorkflowPhase0Thalamus.description}</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Workflows:</span>
                        <Link
                            to="/a549-focus"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-amber-100 hover:text-amber-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-amber-900 dark:hover:text-amber-300 transition-colors"
                        >
                            A549 Focus
                        </Link>
                        <Link
                            to="/phase0-thalamus"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
                        >
                            Phase 0 Thalamus
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

            <div className="grow min-h-0 w-full relative">
                <DependencyMap
                    workflow={mockWorkflowPhase0Thalamus}
                    className="h-full w-full"
                />
            </div>
        </div>
    );
};

export default Phase0ThalamusPage;
