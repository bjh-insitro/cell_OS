import React, { useMemo, useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    Edge,
    Node,
    Position,
    useNodesState,
    useEdgesState,
    MarkerType,
    Handle,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { Workflow } from '../types/workflow';
import { getAxisLabel } from '../utils/axisLabels';

interface DependencyMapProps {
    workflow: Workflow;
    focusedAxisId?: string;
    className?: string;
    highlightedKinds?: string[];
    onNodeClick?: (event: React.MouseEvent, node: Node) => void;
}

const nodeWidth = 250;
const nodeHeight = 100;

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({ rankdir: 'LR' });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        node.targetPosition = Position.Left;
        node.sourcePosition = Position.Right;

        // We are shifting the dagre node position (anchor=center center) to the top left
        // so it matches the React Flow node anchor point (top left).
        node.position = {
            x: nodeWithPosition.x - nodeWidth / 2,
            y: nodeWithPosition.y - nodeHeight / 2,
        };
    });

    return { nodes, edges };
};

const CheckIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-green-600">
        <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
    </svg>
);

const CustomNode = ({ data }: { data: { label: string; subLabel: string; status: string; kind: string; owner: string; definitionOfDone: string; inputsRequired: string; outputsPromised: string; computedBlockers: string[]; dimmed?: boolean } }) => {
    const getHeaderColor = (kind: string, status: string) => {
        if (kind === 'cell_line') return 'bg-violet-500';
        if (kind === 'measurement') return 'bg-orange-500';
        if (kind === 'stressor') return 'bg-pink-500';
        if (kind === 'perturbation') return 'bg-teal-500';

        switch (status) {
            case 'ready': return 'bg-green-500';
            case 'in_progress': return 'bg-blue-500';
            case 'blocked': return 'bg-red-500';
            case 'design': return 'bg-amber-500';
            default: return 'bg-slate-400';
        }
    };

    const isDone = data.status === 'ready' || data.status === 'done';
    const isBlocked = data.status === 'blocked' || (data.computedBlockers && data.computedBlockers.length > 0);

    return (
        <div className={`group relative ${data.dimmed ? 'opacity-20 grayscale transition-all duration-300' : 'opacity-100 transition-all duration-300'} hover:z-[100]`}>
            <div className={`${
                isBlocked
                    ? 'bg-red-50 dark:bg-red-900/30 border-2 border-red-500 dark:border-red-400 animate-pulse shadow-lg shadow-red-500/50'
                    : isDone
                        ? 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'
                        : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'
            } rounded-lg shadow-md overflow-hidden w-[250px]`}>
                <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" />
                <div className={`h-2 ${getHeaderColor(data.kind, data.status)}`} />
                <div className="p-3">
                    <div className="flex justify-between items-start mb-1">
                        <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">{data.subLabel}</div>
                        {isDone && <CheckIcon />}
                        {isBlocked && <span className="text-red-500 text-lg">⛔</span>}
                    </div>
                    <div className="text-sm font-bold text-slate-900 dark:text-white">{data.label}</div>

                    {/* Inline blocker warning */}
                    {isBlocked && data.computedBlockers && data.computedBlockers.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-red-300 dark:border-red-700">
                            <div className="text-xs font-bold text-red-600 dark:text-red-400 mb-1">BLOCKED:</div>
                            <div className="text-xs text-red-700 dark:text-red-300">
                                {data.computedBlockers[0]}
                                {data.computedBlockers.length > 1 && (
                                    <span className="ml-1 text-red-500">+{data.computedBlockers.length - 1} more</span>
                                )}
                            </div>
                        </div>
                    )}
                </div>
                <Handle type="source" position={Position.Right} className="!bg-slate-400 !w-2 !h-2" />
            </div>

            {/* Tooltip - Only show if not dimmed */}
            {!data.dimmed && (
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-64 bg-slate-800 dark:bg-slate-700 text-white text-xs rounded-lg p-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50 shadow-lg">
                    <div className="mb-2">
                        <span className="font-bold text-slate-300">Owner:</span> {data.owner}
                    </div>
                    <div className="mb-2">
                        <span className="font-bold text-slate-300">DoD:</span> {data.definitionOfDone}
                    </div>

                    {data.computedBlockers && data.computedBlockers.length > 0 && (
                        <div className="mb-2 text-red-400">
                            <span className="font-bold">Blocked by:</span>
                            <ul className="list-disc list-inside ml-1">
                                {data.computedBlockers.map((blocker, idx) => (
                                    <li key={idx}>{blocker}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="mb-2">
                        <span className="font-bold text-slate-300">Inputs:</span> {data.inputsRequired}
                    </div>
                    <div>
                        <span className="font-bold text-slate-300">Outputs:</span> {data.outputsPromised}
                    </div>
                    {/* Arrow */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 -mb-1 border-4 border-transparent border-b-slate-800 dark:border-b-slate-700"></div>
                </div>
            )}
        </div>
    );
};

const nodeTypes = {
    custom: CustomNode,
};

export const DependencyMap: React.FC<DependencyMapProps> = ({ workflow, focusedAxisId, className, highlightedKinds, onNodeClick }) => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => {
        const nodes: Node[] = [];
        const edges: Edge[] = [];

        workflow.axes.forEach((axis) => {
            // Calculate blockers
            const computedBlockers: string[] = [];

            // 1. Explicit blockers
            if (axis.blockers) {
                computedBlockers.push(...axis.blockers);
            }

            // 2. Upstream dependencies not complete
            if (axis.dependencies) {
                axis.dependencies.forEach(dep => {
                    if (dep.linkedAxisId) {
                        const upstreamAxis = workflow.axes.find(a => a.id === dep.linkedAxisId);
                        if (upstreamAxis) {
                            const isComplete = upstreamAxis.status === 'ready';
                            if (!isComplete) {
                                computedBlockers.push(`Waiting for ${upstreamAxis.name}`);
                            }
                        }
                    }
                });
            }

            // Determine if dimmed
            const isDimmed = highlightedKinds && highlightedKinds.length > 0 && !highlightedKinds.includes(axis.kind);

            // Create node for the axis
            nodes.push({
                id: axis.id,
                type: 'custom',
                data: {
                    label: axis.name,
                    subLabel: getAxisLabel(axis.kind),
                    status: axis.status,
                    kind: axis.kind,
                    owner: axis.owner,
                    definitionOfDone: axis.definitionOfDone,
                    inputsRequired: axis.inputsRequired,
                    outputsPromised: axis.outputsPromised,
                    computedBlockers: computedBlockers,
                    dimmed: isDimmed
                },
                position: { x: 0, y: 0 },
            });

            // Create edges for dependencies
            if (axis.dependencies) {
                axis.dependencies.forEach((dep) => {
                    if (dep.linkedAxisId) {
                        const isReady = dep.status === 'ready';
                        const edgeColor = isReady ? '#16a34a' : '#94a3b8'; // green-600 or slate-400

                        edges.push({
                            id: `${dep.linkedAxisId}-${axis.id}`,
                            source: dep.linkedAxisId,
                            target: axis.id,
                            animated: false,
                            style: { stroke: edgeColor, strokeWidth: 2 },
                            markerEnd: {
                                type: MarkerType.ArrowClosed,
                                color: edgeColor,
                            },
                        });
                    }
                });
            }
        });

        // Filter if focusedAxisId is provided
        let filteredNodes = nodes;
        let filteredEdges = edges;

        if (focusedAxisId) {
            const focusedAxis = workflow.axes.find(a => a.id === focusedAxisId);

            if (focusedAxis) {
                // Filter nodes to only show those of the same kind (Home Function)
                filteredNodes = nodes.filter(node => node.data.kind === focusedAxis.kind);

                // Filter edges to only show connections between visible nodes
                const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
                filteredEdges = edges.filter(
                    edge => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
                );
            }
        }

        return getLayoutedElements(filteredNodes, filteredEdges);
    }, [workflow, focusedAxisId, highlightedKinds]);

    const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

    useEffect(() => {
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

    return (
        <div className={className || "h-[500px] bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden"}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
                attributionPosition="bottom-right"
            >
                <Background className="!bg-slate-50 dark:!bg-slate-900" color="#94a3b8" gap={16} />
                <Controls className="dark:bg-slate-800 dark:border-slate-700 dark:text-white" />
            </ReactFlow>
        </div>
    );
};
