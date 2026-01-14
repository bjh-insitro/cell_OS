import React, { useState } from "react";
import { Link } from 'react-router-dom';
import { mockWorkflowMenadione } from "../data/mockWorkflowMenadione";
import { WorkflowHeader } from "../components/WorkflowHeader";
import { AxisGrid } from "../components/AxisGrid";
import { AxisDetailPanel } from "../components/AxisDetailPanel";
import { DependencyMap } from "../components/DependencyMap";
import { ThemeToggle } from "../components/ThemeToggle";

export const MenadioneStatusPage: React.FC = () => {
    const [selectedAxisId, setSelectedAxisId] = useState<string | undefined>(undefined);

    const selectedAxis = React.useMemo(() => {
        return mockWorkflowMenadione.axes.find((axis) => axis.id === selectedAxisId);
    }, [selectedAxisId]);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors duration-300">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Workflows:</span>
                        <Link
                            to="/map"
                            className="px-3 py-1 text-xs font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-blue-100 hover:text-blue-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-blue-900 dark:hover:text-blue-300 transition-colors"
                        >
                            Generic
                        </Link>
                        <Link
                            to="/menadione/map"
                            className="px-3 py-1 text-xs font-medium rounded-full bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300"
                        >
                            Menadione A549
                        </Link>
                    </div>
                    <ThemeToggle />
                </div>

                <WorkflowHeader workflow={mockWorkflowMenadione} />

                {!selectedAxis && (
                    <div className="mb-12">
                        <AxisGrid
                            axes={mockWorkflowMenadione.axes.filter(a => a.visible !== false)}
                            onAxisSelect={setSelectedAxisId}
                            selectedAxisId={selectedAxisId}
                        />
                    </div>
                )}

                <div className="mt-8">
                    {selectedAxis ? (
                        <div className="animate-fade-in">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                                    {selectedAxis.name} Details
                                </h2>
                                <button
                                    onClick={() => setSelectedAxisId(undefined)}
                                    className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 underline"
                                >
                                    Back to Global Map
                                </button>
                            </div>

                            <div className="mb-8">
                                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-200 uppercase tracking-wider mb-4">Local Dependency Map</h3>
                                <DependencyMap workflow={mockWorkflowMenadione} focusedAxisId={selectedAxis.id} />
                            </div>

                            <AxisDetailPanel axis={selectedAxis} onClose={() => setSelectedAxisId(undefined)} />
                        </div>
                    ) : (
                        <div className="animate-fade-in">
                            <div className="relative bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm h-[400px] group transition-colors duration-300">
                                {/* Map Preview Background */}
                                <div className="absolute inset-0 opacity-40 grayscale group-hover:grayscale-0 group-hover:opacity-60 transition-all duration-500 pointer-events-none">
                                    <DependencyMap
                                        workflow={mockWorkflowMenadione}
                                        className="h-full w-full bg-slate-50 dark:bg-slate-900"
                                    />
                                </div>

                                {/* Overlay Content */}
                                <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/30 dark:bg-slate-900/40 backdrop-blur-[1px] p-8 text-center z-10">
                                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2 drop-shadow-sm">Global Dependency Map</h2>
                                    <p className="text-slate-800 dark:text-slate-200 font-medium mb-8 max-w-md drop-shadow-sm">View the complete project lineage and dependencies in a full-screen interactive map.</p>
                                    <Link
                                        to="/menadione/map"
                                        className="inline-flex items-center justify-center px-8 py-4 border border-transparent text-lg font-medium rounded-full text-white bg-blue-600 hover:bg-blue-700 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
                                    >
                                        View Full Screen Map →
                                    </Link>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MenadioneStatusPage;
