import React from "react";
import { Workflow } from "../types/workflow";
import { StatusPill } from "./StatusPill";

interface WorkflowHeaderProps {
    workflow: Workflow;
}

export const WorkflowHeader: React.FC<WorkflowHeaderProps> = ({ workflow }) => {
    const axisSummary = React.useMemo(() => {
        const counts = workflow.axes.reduce((acc, axis) => {
            acc[axis.status] = (acc[axis.status] || 0) + 1;
            return acc;
        }, {} as Record<string, number>);

        return Object.entries(counts)
            .map(([status, count]) => `${count} ${status.replace(/_/g, " ")}`)
            .join(", ");
    }, [workflow.axes]);

    return (
        <div className="mb-8">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">{workflow.name}</h1>
                    <p className="text-slate-600 dark:text-slate-400 text-lg max-w-3xl">{workflow.description}</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-3">
                        <span className="text-sm font-mono text-slate-400 dark:text-slate-500">{workflow.id}</span>
                        <StatusPill status={workflow.status} />
                    </div>

                </div>
            </div>

            <div className="flex flex-col gap-2 py-3 px-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm transition-colors duration-300">
                <div className="flex items-center gap-4">
                    <span className="font-semibold text-slate-700 dark:text-slate-200">{workflow.axes.length} Tasks</span>
                    <div className="h-4 w-px bg-slate-300 dark:bg-slate-600"></div>
                    <span className="text-sm text-slate-600 dark:text-slate-400 capitalize">{axisSummary}</span>
                </div>

                {/* Progress Bars by Home Function */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                    {(['cell_line', 'stressor', 'perturbation', 'measurement'] as const).map(kind => {
                        const axes = workflow.axes.filter(a => a.kind === kind);

                        // Sort axes: Ready -> In Progress -> Blocked -> Not Started
                        const sortedAxes = [...axes].sort((a, b) => {
                            const score = (status: string) => {
                                if (status === 'ready') return 0;
                                if (status === 'in_progress') return 1;
                                if (status === 'blocked') return 2;
                                return 3; // not_started, design
                            };
                            return score(a.status) - score(b.status);
                        });

                        const label = kind === 'cell_line' ? 'Biobanking'
                            : kind === 'stressor' ? 'Cell Models'
                                : kind === 'perturbation' ? 'Functional Genomics'
                                    : 'PST';



                        return (
                            <div key={kind} className="flex flex-col gap-1">
                                <div className="flex justify-between items-center text-xs text-slate-500 dark:text-slate-400">
                                    <span className="font-semibold uppercase tracking-wider">{label}</span>
                                    <span>{axes.length}</span>
                                </div>
                                <div className="flex h-2 w-full rounded-full overflow-hidden bg-slate-100 dark:bg-slate-700">
                                    {sortedAxes.map(axis => {
                                        let color = 'bg-slate-200 dark:bg-slate-600'; // Default (not_started, design)
                                        if (axis.status === 'ready') color = 'bg-green-500';
                                        else if (axis.status === 'in_progress') color = 'bg-blue-500';
                                        else if (axis.status === 'blocked') color = 'bg-red-500';

                                        return (
                                            <div
                                                key={axis.id}
                                                className={`h-full ${color} border-r border-white/50 dark:border-slate-800/50 last:border-0`}
                                                style={{ width: `${100 / axes.length}%` }}
                                                title={`${axis.name}: ${axis.status}`}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Legend */}
                <div className="flex items-center justify-end gap-4 mt-3 text-xs text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-green-500"></div>
                        <span>Complete</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                        <span>In Progress</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-red-500"></div>
                        <span>Blocked</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-slate-200 dark:bg-slate-600"></div>
                        <span>Pending</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
