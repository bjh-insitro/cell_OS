import React from "react";
import { WorkflowAxis } from "../types/workflow";
import { getAxisLabel } from "../utils/axisLabels";
import { StatusPill } from "./StatusPill";

interface AxisCardProps {
    axis: WorkflowAxis;
    isSelected: boolean;
    onClick: (axisId: string) => void;
}

export const AxisCard: React.FC<AxisCardProps> = ({ axis, isSelected, onClick }) => {
    const isBiobanking = axis.kind === 'cell_line';
    const isPST = axis.kind === 'measurement';
    const isCellModels = axis.kind === 'stressor';
    const isFunctionalGenomics = axis.kind === 'perturbation';

    let borderColor = 'border-blue-500';
    let labelColor = 'text-blue-600';
    let ringColor = 'ring-blue-100';
    let bgColor = 'bg-blue-50 dark:bg-blue-900/20';

    if (isBiobanking) {
        borderColor = 'border-violet-500';
        labelColor = 'text-violet-600';
        ringColor = 'ring-violet-100';
        bgColor = 'bg-violet-50 dark:bg-violet-900/20';
    } else if (isPST) {
        borderColor = 'border-orange-500';
        labelColor = 'text-orange-600';
        ringColor = 'ring-orange-100';
        bgColor = 'bg-orange-50 dark:bg-orange-900/20';
    } else if (isCellModels) {
        borderColor = 'border-pink-500';
        labelColor = 'text-pink-600';
        ringColor = 'ring-pink-100';
        bgColor = 'bg-pink-50 dark:bg-pink-900/20';
    } else if (isFunctionalGenomics) {
        borderColor = 'border-teal-500';
        labelColor = 'text-teal-600';
        ringColor = 'ring-teal-100';
        bgColor = 'bg-teal-50 dark:bg-teal-900/20';
    }

    // Task Logic
    const tasks = axis.tasks || [];
    const uncompletedTask = tasks.find(t => t.status !== 'done');
    const lastCompletedTask = [...tasks].reverse().find(t => t.status === 'done');
    const displayTask = uncompletedTask || lastCompletedTask;

    const isBlocked = axis.status === 'blocked';
    const taskTextColor = isBlocked ? 'text-red-600 dark:text-red-400 font-medium' : 'text-slate-600 dark:text-slate-400';

    return (
        <div
            onClick={() => onClick(axis.id)}
            className={`
        relative p-4 rounded-xl border-2 cursor-pointer transition-all duration-200
        ${borderColor}
        ${isSelected
                    ? `bg-white dark:bg-slate-800 ring-4 ${ringColor} shadow-lg`
                    : `bg-white dark:bg-slate-800 hover:shadow-md`
                }
      `}
        >
            <div className="flex justify-between items-start mb-3">
                <span className={`text-xs font-bold uppercase tracking-wider ${labelColor} px-2 py-0.5 rounded-full ${bgColor}`}>
                    {getAxisLabel(axis.kind)}
                </span>
                <StatusPill status={axis.status} />
            </div>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 line-clamp-2 min-h-[3.5rem]">
                {axis.name}
            </h3>

            <div className="pt-3 border-t border-slate-100 dark:border-slate-700">
                {axis.dependencies && axis.dependencies.some(d => d.status !== 'ready') ? (
                    <>
                        <div className="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold mb-2">
                            Parallel Tasks
                        </div>
                        <div className="space-y-1.5">
                            {axis.dependencies.filter(d => d.status !== 'ready').map(dep => (
                                <div key={dep.id} className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600 dark:text-slate-400 truncate pr-2" title={dep.label}>
                                        {dep.label}
                                    </span>
                                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${dep.status === 'blocked'
                                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                        : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                                        }`}>
                                        {dep.status === 'blocked' ? 'Blocked' : 'Pending'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                ) : (
                    <>
                        <div className="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold mb-1">
                            {uncompletedTask ? 'Current Task' : 'Last Completed'}
                        </div>
                        <div className={`text-sm ${taskTextColor} line-clamp-2`}>
                            {displayTask ? displayTask.title : 'No tasks available'}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
