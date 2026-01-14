import React, { useMemo, useEffect, useState, useRef, useCallback } from 'react';
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
    ReactFlowProvider,
    useReactFlow,
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
    highlightedPrograms?: string[];
    onNodeClick?: (event: React.MouseEvent, node: Node) => void;
    hideStatusIcons?: boolean;
    useTimelineLayout?: boolean;
}

const nodeWidth = 145;
const nodeHeight = 58;
const containerNodeWidth = 280;
const containerNodeHeight = 200;
const quarterWidth = 300; // Width for each quarter column

const getTimelineLayoutedElements = (nodes: Node[], edges: Edge[], containerWidth: number, containerHeight: number) => {
    // Calculate dynamic dimensions based on container size
    // 5 swim lanes, 4 quarters
    const numLanes = 5;
    const numQuarters = 4;
    const leftMargin = 100; // Space for swim lane labels

    const laneHeight = containerHeight / numLanes;
    const usableWidth = containerWidth - leftMargin;
    const quarterColumnWidth = usableWidth / numQuarters;
    const nodeOffset = (laneHeight - nodeHeight) / 2; // Center node vertically in lane

    const swimLaneY: { [key: string]: number } = {
        'perturbation': nodeOffset,                    // Functional Genomics - teal (lane 1)
        'cell_line': laneHeight + nodeOffset,          // Biobanking - violet (lane 2)
        'stressor': laneHeight * 2 + nodeOffset,       // Cell Models - pink (lane 3)
        'measurement': laneHeight * 3 + nodeOffset,    // PST - orange (lane 4)
        'analysis': laneHeight * 4 + nodeOffset,       // Compute - grey (lane 5)
        'program': nodeOffset,                         // Default
    };

    // Track how many nodes are in each swim lane at each quarter to handle stacking
    const laneQuarterCount: { [key: string]: number } = {};

    nodes.forEach(node => {
        const quarter = node.data.quarter ?? 0;
        const kind = node.data.kind || 'program';
        // Round quarter to nearest 0.5 to group nearby nodes
        const quarterBucket = Math.round(quarter * 2) / 2;
        const laneKey = `${kind}-${quarterBucket}`;

        if (!laneQuarterCount[laneKey]) laneQuarterCount[laneKey] = 0;
        const stackIndex = laneQuarterCount[laneKey];
        laneQuarterCount[laneKey]++;

        const baseY = swimLaneY[kind] ?? 100;

        // Stack nodes horizontally (side by side) with small vertical offset for visual separation
        const horizontalOffset = stackIndex * (nodeWidth + 10); // Node width + gap
        const verticalOffset = stackIndex * 12; // Small diagonal offset

        const customYOffset = node.data.yOffset ?? 0;
        const customXPosition = node.data.xPosition;

        // Scale custom xPosition and customWidth proportionally to container width
        // Original design was for ~2600px width, scale to fit
        const designWidth = 2600;
        const scaleFactor = containerWidth / designWidth;
        const scaledXPosition = customXPosition !== undefined
            ? customXPosition * scaleFactor
            : undefined;

        // Scale customWidth if present
        const originalCustomWidth = node.data.customWidth;
        if (originalCustomWidth) {
            node.data.scaledWidth = Math.max(nodeWidth, originalCustomWidth * scaleFactor);
        }

        node.targetPosition = Position.Left;
        node.sourcePosition = Position.Right;
        node.position = {
            x: scaledXPosition !== undefined ? scaledXPosition : (leftMargin + quarter * quarterColumnWidth + horizontalOffset),
            y: baseY + verticalOffset + customYOffset,
        };
    });

    return { nodes, edges };
};

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({
        rankdir: 'LR',
        nodesep: 40,    // Vertical spacing between nodes in same rank
        ranksep: 80,    // Horizontal spacing between ranks (columns)
        align: 'UL',    // Align nodes to upper-left for more compact layout
    });

    nodes.forEach((node) => {
        const isContainer = node.type === 'container';
        const width = isContainer ? containerNodeWidth : nodeWidth;
        const height = isContainer ? containerNodeHeight : nodeHeight;
        dagreGraph.setNode(node.id, { width, height });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        const isContainer = node.type === 'container';
        const width = isContainer ? containerNodeWidth : nodeWidth;
        const height = isContainer ? containerNodeHeight : nodeHeight;

        node.targetPosition = Position.Left;
        node.sourcePosition = Position.Right;

        // We are shifting the dagre node position (anchor=center center) to the top left
        // so it matches the React Flow node anchor point (top left).
        node.position = {
            x: nodeWithPosition.x - width / 2,
            y: nodeWithPosition.y - height / 2,
        };
    });

    return { nodes, edges };
};

const CheckIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-green-600 flex-shrink-0">
        <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
    </svg>
);

const PendingIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 text-amber-500 flex-shrink-0">
        <circle cx="12" cy="12" r="9" strokeDasharray="4 2" />
    </svg>
);

const CustomNode = ({ data }: { data: { label: string; subLabel: string; status: string; kind: string; owner: string; definitionOfDone: string; inputsRequired: string; outputsPromised: string; computedBlockers: string[]; dimmed?: boolean; hideStatusIcons?: boolean; confidenceRange?: { left: number; right: number }; customWidth?: number; scaledWidth?: number; customStyle?: string; compact?: boolean } }) => {
    const getHeaderColor = (kind: string, status: string) => {
        if (kind === 'cell_line') return 'bg-violet-500';
        if (kind === 'measurement') return 'bg-orange-500';
        if (kind === 'stressor') return 'bg-pink-500';
        if (kind === 'perturbation') return 'bg-teal-500';
        if (kind === 'analysis') return 'bg-slate-500';
        if (kind === 'program') return 'bg-transparent';

        switch (status) {
            case 'ready': return 'bg-green-500';
            case 'in_progress': return 'bg-blue-500';
            case 'blocked': return 'bg-red-500';
            case 'design': return 'bg-amber-500';
            default: return 'bg-slate-400';
        }
    };

    const isDone = data.status === 'ready' || data.status === 'done';
    const isBlocked = !data.hideStatusIcons && (data.status === 'blocked' || (data.computedBlockers && data.computedBlockers.length > 0));
    const isPending = !isDone && !isBlocked;

    return (
        <div className={`group relative ${data.dimmed ? 'opacity-20 grayscale transition-all duration-300' : 'opacity-100 transition-all duration-300'} hover:z-[100]`}>
            {/* Confidence interval range indicator */}
            {data.confidenceRange && (
                <div
                    className="absolute top-0 bottom-0 bg-slate-200 dark:bg-slate-600 rounded-lg -z-10"
                    style={{
                        left: `-${data.confidenceRange.left}px`,
                        right: `-${data.confidenceRange.right}px`,
                        width: `calc(100% + ${data.confidenceRange.left + data.confidenceRange.right}px)`,
                    }}
                />
            )}
            <div className={`${
                data.customStyle === 'dark'
                    ? 'bg-slate-900 border-2 border-slate-700'
                    : isBlocked
                        ? 'bg-red-50 dark:bg-red-900/30 border-2 border-red-500 dark:border-red-400 animate-pulse shadow-lg shadow-red-500/50'
                        : isPending
                            ? 'bg-amber-50 dark:bg-amber-900/20 border-2 border-dashed border-amber-400 dark:border-amber-500'
                            : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'
            } rounded-lg shadow-md overflow-hidden`} style={{ width: `${data.scaledWidth || data.customWidth || 145}px` }}>
                <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" />
                <div className={`h-1.5 ${data.customStyle === 'dark' ? 'bg-white' : getHeaderColor(data.kind, data.status)}`} />
                <div className={`p-2 ${data.customStyle === 'dark' ? 'text-center' : ''}`}>
                    <div className={`flex ${data.customStyle === 'dark' ? 'justify-center' : 'justify-between'} items-start mb-0.5`}>
                        <div className={`text-[10px] font-semibold uppercase truncate ${data.customStyle === 'dark' ? 'text-slate-300' : 'text-slate-500 dark:text-slate-400'}`}>{data.subLabel}</div>
                        {!data.hideStatusIcons && isDone && <CheckIcon />}
                        {!data.hideStatusIcons && isPending && <PendingIcon />}
                        {!data.hideStatusIcons && isBlocked && <span className="text-red-500 text-sm">⛔</span>}
                    </div>
                    <div className={`font-bold leading-tight line-clamp-2 ${data.customStyle === 'dark' ? 'text-white text-[14px]' : 'text-[11px] text-slate-900 dark:text-white'}`}>{data.label}</div>

                    {/* Inline blocker warning */}
                    {isBlocked && data.computedBlockers && data.computedBlockers.length > 0 && (
                        <div className="mt-1 pt-1 border-t border-red-300 dark:border-red-700">
                            <div className="text-[9px] font-bold text-red-600 dark:text-red-400">BLOCKED: {data.computedBlockers.length}</div>
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

const ContainerNode = ({ data }: { data: { label: string; subItems: { title: string; status: string }[] } }) => {
    return (
        <div className="group relative">
            <div className="bg-slate-200 dark:bg-slate-700 rounded-xl p-4 shadow-md w-[280px] border border-slate-300 dark:border-slate-600">
                <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" />
                <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-3">{data.label}</div>
                <div className="space-y-2">
                    {data.subItems.map((item, idx) => {
                        const isDone = item.status === 'done' || item.status === 'ready';
                        const isPending = !isDone;
                        return (
                            <div
                                key={idx}
                                className={`rounded-lg overflow-hidden shadow-sm ${
                                    isPending
                                        ? 'bg-amber-50 dark:bg-amber-900/20 border-2 border-dashed border-amber-400 dark:border-amber-500'
                                        : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600'
                                }`}
                            >
                                <div className="h-2 bg-pink-500" />
                                <div className="p-3">
                                    <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-1">Cell Models</div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white">{item.title}</span>
                                    {isDone && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-green-600 flex-shrink-0 ml-2">
                                            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                                        </svg>
                                    )}
                                    {isPending && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 text-amber-500 flex-shrink-0 ml-2">
                                            <circle cx="12" cy="12" r="9" strokeDasharray="4 2" />
                                        </svg>
                                    )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
                <Handle type="source" position={Position.Right} className="!bg-slate-400 !w-2 !h-2" />
            </div>
        </div>
    );
};

const nodeTypes = {
    custom: CustomNode,
    container: ContainerNode,
};

const ResizeHandler: React.FC<{ useTimelineLayout?: boolean }> = ({ useTimelineLayout }) => {
    const { fitView } = useReactFlow();

    useEffect(() => {
        const handleResize = () => {
            if (!useTimelineLayout) {
                setTimeout(() => fitView({ padding: 0.1 }), 50);
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [fitView, useTimelineLayout]);

    return null;
};

export const DependencyMap: React.FC<DependencyMapProps> = ({ workflow, focusedAxisId, className, highlightedKinds, highlightedPrograms, onNodeClick, hideStatusIcons, useTimelineLayout }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerSize, setContainerSize] = useState({ width: 1600, height: 800 });

    // Track container size for timeline layout
    useEffect(() => {
        if (!useTimelineLayout || !containerRef.current) return;

        const updateSize = () => {
            if (containerRef.current) {
                const { width, height } = containerRef.current.getBoundingClientRect();
                setContainerSize({ width, height });
            }
        };

        updateSize();
        const resizeObserver = new ResizeObserver(updateSize);
        resizeObserver.observe(containerRef.current);

        return () => resizeObserver.disconnect();
    }, [useTimelineLayout]);

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

            // Determine if dimmed based on kind filter
            const isDimmedByKind = highlightedKinds && highlightedKinds.length > 0 && !highlightedKinds.includes(axis.kind);
            // Determine if dimmed based on program filter - dim if filter active and axis program doesn't match
            const isDimmedByProgram = highlightedPrograms && highlightedPrograms.length > 0 &&
                (!axis.program || !highlightedPrograms.includes(axis.program));
            const isDimmed = isDimmedByKind || isDimmedByProgram;

            // Create node for the axis
            if (axis.kind === 'container' && axis.subItems) {
                nodes.push({
                    id: axis.id,
                    type: 'container',
                    data: {
                        label: axis.name,
                        subItems: axis.subItems,
                    },
                    position: { x: 0, y: 0 },
                });
            } else {
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
                        dimmed: isDimmed,
                        hideStatusIcons: hideStatusIcons,
                        quarter: axis.quarter,
                        yOffset: (axis as any).yOffset,
                        xPosition: (axis as any).xPosition,
                        confidenceRange: (axis as any).confidenceRange,
                        customWidth: (axis as any).customWidth,
                        customStyle: (axis as any).customStyle
                    },
                    position: { x: 0, y: 0 },
                });
            }

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

        return useTimelineLayout
            ? getTimelineLayoutedElements(filteredNodes, filteredEdges, containerSize.width, containerSize.height)
            : getLayoutedElements(filteredNodes, filteredEdges);
    }, [workflow, focusedAxisId, highlightedKinds, highlightedPrograms, hideStatusIcons, useTimelineLayout, containerSize]);

    const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

    useEffect(() => {
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

    return (
        <div ref={containerRef} className={className || "h-[500px] bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden"}>
            <ReactFlowProvider>
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    nodeTypes={nodeTypes}
                    fitView={!useTimelineLayout}
                    fitViewOptions={{ padding: 0.1 }}
                    defaultViewport={useTimelineLayout ? { x: 0, y: 0, zoom: 1 } : undefined}
                    minZoom={0.3}
                    attributionPosition="bottom-right"
                >
                    <ResizeHandler useTimelineLayout={useTimelineLayout} />
                    {!useTimelineLayout && <Background className="!bg-slate-50 dark:!bg-slate-900" color="#94a3b8" gap={16} />}
                    <Controls className="dark:bg-slate-800 dark:border-slate-700 dark:text-white" position="bottom-right" />
                </ReactFlow>
            </ReactFlowProvider>
        </div>
    );
};
