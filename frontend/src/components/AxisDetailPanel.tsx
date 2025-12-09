
import React, { useEffect, useState } from "react";
import { WorkflowAxis } from "../types/workflow";
import { getAxisLabel } from "../utils/axisLabels";
import { StatusPill } from "./StatusPill";
import { BenchlingService, BenchlingEntity } from "../services/BenchlingService";

interface AxisDetailPanelProps {
    axis: WorkflowAxis;
    onClose: () => void;
}

export const AxisDetailPanel: React.FC<AxisDetailPanelProps> = ({ axis, onClose }) => {
    const [benchlingData, setBenchlingData] = useState<BenchlingEntity | null>(null);
    const [inventoryCount, setInventoryCount] = useState<number | null>(null);
    const [loadingBenchling, setLoadingBenchling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (axis.benchlingEntityId) {
            setLoadingBenchling(true);
            setBenchlingData(null);
            setInventoryCount(null);
            setError(null);

            const fetchData = async () => {
                try {
                    let entity: BenchlingEntity | null = null;

                    // Check if it's a Registry ID (e.g. starts with CLI or LI) or Mock ID
                    if (axis.benchlingEntityId!.startsWith('CLI') || axis.benchlingEntityId!.startsWith('LI')) {
                        entity = await BenchlingService.searchEntity(axis.benchlingEntityId!);
                    } else {
                        // Assume it's an API ID or Mock ID
                        entity = await BenchlingService.getEntity(axis.benchlingEntityId!);
                    }

                    if (!entity) {
                        setError(`Could not find entity ${axis.benchlingEntityId}`);
                    } else {
                        setBenchlingData(entity);

                        if (entity.id && !entity.id.startsWith('ben_')) {
                            const count = await BenchlingService.getContainerCount(entity.id);
                            setInventoryCount(count);
                        }
                    }
                } catch (e: any) {
                    console.error(e);
                    setError(e.message || "Unknown error occurred");
                } finally {
                    setLoadingBenchling(false);
                }
            };

            fetchData();
        } else {
            setBenchlingData(null);
            setError(null);
        }
    }, [axis.benchlingEntityId]);

    return (
        <div className="h-full flex flex-col bg-white dark:bg-slate-800 shadow-xl border-l border-slate-200 dark:border-slate-700 overflow-y-auto transition-colors duration-300">
            <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                            {getAxisLabel(axis.kind)} Details
                        </span>
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{axis.name}</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{axis.id}</p>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="space-y-6">
                    <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-100 dark:border-slate-700">
                        <div className="text-sm text-slate-600 dark:text-slate-300">
                            Owner: <span className="font-medium text-slate-700 dark:text-slate-200">{axis.owner}</span>
                        </div>
                        <StatusPill status={axis.status} />
                    </div>

                    {/* Benchling Integration Section */}
                    {axis.benchlingEntityId && (
                        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded-lg p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <div className="w-5 h-5 bg-blue-500 rounded flex items-center justify-center text-white font-bold text-xs">B</div>
                                <h3 className="text-sm font-bold text-blue-900 dark:text-blue-300">Benchling Registry</h3>
                            </div>

                            {loadingBenchling ? (
                                <div className="text-sm text-blue-600 dark:text-blue-400 animate-pulse">Loading entity data...</div>
                            ) : error ? (
                                <div className="text-sm text-red-500">
                                    <p className="font-bold">Error loading data:</p>
                                    <p>{error}</p>
                                </div>
                            ) : benchlingData ? (
                                <div className="space-y-2">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="text-sm font-bold text-slate-900 dark:text-white">{benchlingData.name}</div>
                                            <div className="text-xs font-mono text-slate-500 dark:text-slate-400">{benchlingData.registryId}</div>
                                        </div>
                                        <a
                                            href={benchlingData.webURL}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded transition-colors"
                                        >
                                            Open
                                        </a>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-blue-100 dark:border-blue-800">
                                        {Object.entries(benchlingData.fields).map(([key, value]) => (
                                            <div key={key}>
                                                <div className="text-[10px] uppercase text-blue-400 font-semibold">{key}</div>
                                                <div className="text-xs text-slate-700 dark:text-slate-300">{value}</div>
                                            </div>
                                        ))}
                                        {/* Inventory Count Display */}
                                        {inventoryCount !== null && (
                                            <div className="col-span-2 mt-2 bg-white dark:bg-slate-800 rounded p-2 border border-blue-100 dark:border-blue-800 flex justify-between items-center">
                                                <span className="text-xs font-bold text-blue-900 dark:text-blue-300">Inventory</span>
                                                <span className={`text-sm font-bold ${inventoryCount > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                                                    {inventoryCount} {inventoryCount === 100 ? '100+' : ''} vials
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    )}

                    <div>
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">Definition of Done</h3>
                        <p className="text-sm text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900 p-3 rounded border border-slate-100 dark:border-slate-700">
                            {axis.definitionOfDone}
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">Inputs</h3>
                            <p className="text-sm text-slate-600 dark:text-slate-300">{axis.inputsRequired}</p>
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">Outputs</h3>
                            <p className="text-sm text-slate-600 dark:text-slate-300">{axis.outputsPromised}</p>
                        </div>
                    </div>

                    {axis.blockers && (
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/50 rounded-lg p-4">
                            <h3 className="text-sm font-bold text-red-800 dark:text-red-300 mb-1">Blockers</h3>
                            <p className="text-sm text-red-600 dark:text-red-400">{axis.blockers}</p>
                        </div>
                    )}

                    <div>
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3">Tasks</h3>
                        <div className="space-y-2">
                            {axis.tasks.map(task => (
                                <div key={task.id} className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-2 h-2 rounded-full ${task.status === 'done' ? 'bg-green-500' :
                                            task.status === 'in_progress' ? 'bg-blue-500' :
                                                task.status === 'blocked' ? 'bg-red-500' : 'bg-slate-300 dark:bg-slate-600'
                                            }`} />
                                        <span className={`text-sm ${task.status === 'done' ? 'text-slate-400 dark:text-slate-500 line-through' : 'text-slate-700 dark:text-slate-200'}`}>
                                            {task.title}
                                        </span>
                                    </div>
                                    <span className="text-xs text-slate-400 dark:text-slate-500 capitalize">{task.status.replace('_', ' ')}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
