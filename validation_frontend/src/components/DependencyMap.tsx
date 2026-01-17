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
    Viewport,
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
    skipStrategyLane?: boolean;
    hideTooltip?: boolean;
    hideKindInfo?: boolean;
    timelineScale?: number;
    onViewportChange?: (viewport: Viewport) => void;
}

const nodeWidth = 180;
const nodeHeight = 100;
const containerNodeWidth = 200;
const containerNodeHeight = 150;
const quarterWidth = 300; // Width for each quarter column

const getTimelineLayoutedElements = (nodes: Node[], edges: Edge[], containerWidth: number, containerHeight: number, skipStrategyLane: boolean = false, timelineScale: number = 1) => {
    // Calculate dynamic dimensions based on container size
    // 5 or 6 swim lanes depending on whether strategy is skipped
    const numLanes = skipStrategyLane ? 5 : 6;
    const numQuarters = 4 / timelineScale; // Scale factor stretches the timeline
    const leftMargin = 10; // Space for swim lane labels

    const laneHeight = containerHeight / numLanes;
    const usableWidth = containerWidth - leftMargin;
    const quarterColumnWidth = usableWidth / numQuarters;

    // Calculate the center Y position for each lane
    // Center cards directly in each lane (no offset needed)
    const getLaneCenterY = (laneIndex: number) => {
        return (laneIndex + 0.5) * laneHeight;
    };

    const swimLaneCenterY: { [key: string]: number } = skipStrategyLane ? {
        'strategy': -1000,                    // Strategy - hidden off-screen
        'perturbation': getLaneCenterY(0),    // Functional Genomics - teal (lane 1)
        'cell_line': getLaneCenterY(1),       // Biobanking - violet (lane 2)
        'stressor': getLaneCenterY(2),        // Cell Models - pink (lane 3)
        'measurement': getLaneCenterY(3),     // PST - orange (lane 4)
        'analysis': getLaneCenterY(4),        // Compute - grey (lane 5)
        'program': getLaneCenterY(0),         // Default
    } : {
        'strategy': getLaneCenterY(0),        // Strategy - black (lane 1)
        'perturbation': getLaneCenterY(1),    // Functional Genomics - teal (lane 2)
        'cell_line': getLaneCenterY(2),       // Biobanking - violet (lane 3)
        'stressor': getLaneCenterY(3),        // Cell Models - pink (lane 4)
        'measurement': getLaneCenterY(4),     // PST - orange (lane 5)
        'analysis': getLaneCenterY(5),        // Compute - grey (lane 6)
        'program': getLaneCenterY(0),         // Default
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

        // Calculate actual node height for centering (use consistent height for alignment)
        // Use a fixed height so all nodes in a lane align at the same Y position
        // This should match the minHeight set on the card component
        const visualNodeHeight = 95; // Consistent height for all nodes

        // Get the center of the lane and calculate top position to center this node
        const laneCenterY = swimLaneCenterY[kind] ?? 100;
        const nodeTopY = laneCenterY - visualNodeHeight / 2;

        // Stack nodes horizontally (side by side) with small vertical offset for visual separation
        const horizontalOffset = stackIndex * (nodeWidth + 10); // Node width + gap
        // No vertical offset - keep all nodes in the same lane at the same Y position
        const verticalOffset = 0;

        const customYOffset = node.data.yOffset ?? 0;
        const customXPosition = node.data.xPosition;

        // Use fixed positions - DO NOT scale based on container width
        // This ensures layout stays consistent across screen sizes
        // Users can pan/scroll to see content that doesn't fit

        // Use customWidth directly without scaling
        const originalCustomWidth = node.data.customWidth;
        if (originalCustomWidth) {
            node.data.scaledWidth = Math.max(nodeWidth, originalCustomWidth);
        }

        node.targetPosition = Position.Left;
        node.sourcePosition = Position.Right;
        node.position = {
            x: customXPosition !== undefined ? customXPosition : (leftMargin + quarter * quarterColumnWidth + horizontalOffset),
            y: nodeTopY + verticalOffset + customYOffset,
        };
    });

    return { nodes, edges };
};

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({
        rankdir: 'LR',
        nodesep: 140,   // Vertical spacing between nodes in same rank
        ranksep: 10,    // Horizontal spacing between ranks (columns)
        marginx: 5,     // Left/right margin
        marginy: 40,    // Top/bottom margin
    });

    nodes.forEach((node) => {
        const isContainer = node.type === 'container';
        // Account for taller nodes when they have blockers or custom width
        const hasBlockers = node.data.computedBlockers && node.data.computedBlockers.length > 0;
        const width = isContainer ? containerNodeWidth : (node.data.customWidth || nodeWidth);
        const height = isContainer ? containerNodeHeight : (hasBlockers ? nodeHeight + 40 : nodeHeight);
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

const CustomNode = ({ data }: { data: { id: string; label: string; subLabel: string; status: string; kind: string; owner: string; definitionOfDone: string; inputsRequired: string; outputsPromised: string; computedBlockers: string[]; dimmed?: boolean; hideStatusIcons?: boolean; hideTooltip?: boolean; hideKindInfo?: boolean; confidenceRange?: { left: number; right: number }; customWidth?: number; scaledWidth?: number; customStyle?: string; compact?: boolean; durationDays?: number; startDaysFromNow?: number } }) => {
    const getHeaderColor = (kind: string, status: string) => {
        if (kind === 'strategy') return 'bg-black';
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
    // Time-based status: current/past = in progress, future = planned
    const startDays = data.startDaysFromNow ?? 0;
    const durationDays = data.durationDays ?? 14;
    const isCurrent = startDays <= 0 || (startDays > 0 && startDays <= durationDays); // Started or within duration
    const isInProgress = !isDone && !isBlocked && isCurrent;
    const isPlanned = !isDone && !isBlocked && !isCurrent; // Future tasks
    const isPending = !isDone && !isBlocked; // For styling purposes - both IN PROGRESS and PLANNED get amber styling

    return (
        <div className={`group relative ${data.dimmed ? 'opacity-20 grayscale transition-all duration-300' : 'opacity-100 transition-all duration-300'} hover:z-[9999]`}>
            {/* Confidence interval range indicator */}
            {data.confidenceRange && (() => {
                const cardWidth = data.scaledWidth || data.customWidth || nodeWidth;
                const totalWidth = cardWidth + data.confidenceRange.left + data.confidenceRange.right;
                const cardStartPercent = (data.confidenceRange.left / totalWidth) * 100;
                const cardEndPercent = ((cardWidth + data.confidenceRange.left) / totalWidth) * 100;

                // Use red for blocked cards, yellow for others
                const uncertaintyColor = isBlocked ? '#fecaca' : '#fde68a'; // red-200 or amber-200
                const borderColor = isBlocked ? 'border-red-400 dark:border-red-500' : 'border-amber-400 dark:border-amber-500';

                // Build gradient based on which sides have uncertainty
                // Use wider transition zones (15-20%) for smoother blending without visible lines
                // Center color matches the card background (amber-50 for pending, red-50 for blocked)
                const centerColor = isBlocked ? '#fef2f2' : '#fffbeb'; // red-50 or amber-50
                let gradient;
                if (data.confidenceRange.left > 0 && data.confidenceRange.right > 0) {
                    // Both sides: color -> center -> color (smooth 15% transitions)
                    gradient = `linear-gradient(to right, ${uncertaintyColor} 0%, ${centerColor} ${cardStartPercent + 15}%, ${centerColor} ${cardEndPercent - 15}%, ${uncertaintyColor} 100%)`;
                } else if (data.confidenceRange.right > 0) {
                    // Right side only: center -> color (smooth 20% transition)
                    gradient = `linear-gradient(to right, ${centerColor} 0%, ${centerColor} ${cardEndPercent - 10}%, ${uncertaintyColor} 100%)`;
                } else {
                    // Left side only: color -> center (smooth 20% transition)
                    gradient = `linear-gradient(to right, ${uncertaintyColor} 0%, ${centerColor} ${cardStartPercent + 15}%, ${centerColor} 100%)`;
                }

                // Only show labels for axis_stressor (Obtain Optimised Dosage Regime)
                const showLabels = data.id === 'axis_stressor';

                return (
                    <>
                        {/* Labels above card showing Start Uncertainty, Task Length, and Completion Uncertainty */}
                        {showLabels && (
                            <div className="absolute pointer-events-none" style={{ bottom: '100%', left: `-${data.confidenceRange.left}px`, right: `-${data.confidenceRange.right}px`, marginBottom: '6px' }}>
                                <div className="flex items-end text-xs text-slate-600 dark:text-slate-300 font-semibold" style={{ height: '24px' }}>
                                    {/* Start Uncertainty label - only show if left uncertainty exists */}
                                    {data.confidenceRange.left > 0 && (
                                        <div className="flex items-center" style={{ width: `${data.confidenceRange.left}px` }}>
                                            <span className="text-slate-500 text-base">←</span>
                                            <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                            <span className="whitespace-nowrap px-1">Start Uncertainty</span>
                                            <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                            <span className="text-slate-500 text-base">→</span>
                                        </div>
                                    )}
                                    {/* Task Length label - spans the card width */}
                                    <div className="flex items-center" style={{ width: `${cardWidth}px` }}>
                                        <span className="text-slate-500 text-base">←</span>
                                        <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                        <span className="whitespace-nowrap px-1">Task Length</span>
                                        <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                        <span className="text-slate-500 text-base">→</span>
                                    </div>
                                    {/* Completion Uncertainty label - only show if right uncertainty exists */}
                                    {data.confidenceRange.right > 0 && (
                                        <div className="flex items-center" style={{ width: `${data.confidenceRange.right}px` }}>
                                            <span className="text-slate-500 text-base">←</span>
                                            <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                            <span className="whitespace-nowrap px-1">Completion Uncertainty</span>
                                            <div className="flex-1 border-t-2 border-slate-400 dark:border-slate-500 mx-1" />
                                            <span className="text-slate-500 text-base">→</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                        <div
                            className={`absolute top-0 bottom-0 rounded-lg border-2 border-dashed ${borderColor}`}
                            style={{
                                left: `-${data.confidenceRange.left}px`,
                                right: `-${data.confidenceRange.right}px`,
                                width: `calc(100% + ${data.confidenceRange.left + data.confidenceRange.right}px)`,
                                background: gradient,
                                zIndex: -1,
                                pointerEvents: 'none',
                            }}
                        />
                    </>
                );
            })()}
            <div className={`${
                data.customStyle === 'dark'
                    ? 'bg-slate-900 border-2 border-slate-700'
                    : isBlocked
                        ? data.confidenceRange
                            ? 'bg-transparent border-0 shadow-none'
                            : 'bg-red-50 dark:bg-red-900/30 border-2 border-red-500 dark:border-red-400 animate-pulse shadow-lg shadow-red-500/50'
                        : isPending
                            ? data.confidenceRange
                                ? 'bg-transparent border-0 shadow-none'
                                : 'bg-amber-50 dark:bg-amber-900/20 border-2 border-dashed border-amber-400 dark:border-amber-500'
                            : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'
            } rounded-lg shadow-md overflow-hidden`} style={{ width: `${data.scaledWidth || data.customWidth || nodeWidth}px`, height: '95px' }}>
                <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" style={{ left: data.confidenceRange ? -(data.confidenceRange.left + 6) : -6 }} />
                {/* Colored header bar - hidden when hideKindInfo is true */}
                {!data.hideKindInfo && (
                    <div className={`h-1.5 ${data.customStyle === 'dark' ? 'bg-white' : getHeaderColor(data.kind, data.status)}`} />
                )}
                <div className={`p-2 ${data.customStyle === 'dark' ? 'text-center' : ''}`}>
                    {/* Home function label - hidden when hideKindInfo is true */}
                    {!data.hideKindInfo && (
                        <div className={`text-[10px] font-semibold uppercase truncate mb-1 ${data.customStyle === 'dark' ? 'text-slate-300' : 'text-slate-500 dark:text-slate-400'}`}>{data.subLabel}</div>
                    )}
                    <div className={`flex ${data.customStyle === 'dark' ? 'justify-center' : 'justify-between'} items-start`}>
                        <div className={`font-bold leading-tight line-clamp-2 ${data.customStyle === 'dark' ? 'text-white text-sm' : 'text-sm text-slate-900 dark:text-white'}`}>{data.label}</div>
                        {!data.hideStatusIcons && isDone && <CheckIcon />}
                        {!data.hideStatusIcons && isPending && <PendingIcon />}
                        {!data.hideStatusIcons && isBlocked && <span className="text-red-500 text-base ml-1">⛔</span>}
                    </div>

                    {/* Status labels */}
                    {isBlocked && data.computedBlockers && data.computedBlockers.length > 0 && (
                        <div className="mt-1 pt-1 border-t border-red-300 dark:border-red-700">
                            <div className="text-xs font-bold text-red-600 dark:text-red-400">BLOCKED: {data.computedBlockers.length}</div>
                        </div>
                    )}
                    {isInProgress && !isBlocked && (
                        <div className="mt-1 pt-1 border-t border-amber-300 dark:border-amber-700">
                            <div className="text-xs font-bold text-amber-600 dark:text-amber-400">IN PROGRESS</div>
                        </div>
                    )}
                    {isDone && (
                        <div className="mt-1 pt-1 border-t border-green-300 dark:border-green-700">
                            <div className="text-xs font-bold text-green-600 dark:text-green-400">COMPLETE</div>
                        </div>
                    )}
                    {!isBlocked && !isInProgress && !isDone && (
                        <div className="mt-1 pt-1 border-t border-slate-200 dark:border-slate-600">
                            <div className="text-xs font-bold text-slate-500 dark:text-slate-400">PLANNED</div>
                        </div>
                    )}
                </div>
                <Handle type="source" position={Position.Right} className="!bg-slate-400 !w-2 !h-2" style={{ right: data.confidenceRange ? -(data.confidenceRange.right + 6) : -6 }} />
            </div>

            {/* Tooltip - Only show if not dimmed and not hidden */}
            {/* Position above for most cards, below for top lane (perturbation/Functional Genomics) */}
            {!data.dimmed && !data.hideTooltip && (
                <div className={`absolute left-1/2 transform -translate-x-1/2 w-64 bg-slate-800 dark:bg-slate-700 text-white text-xs rounded-lg p-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-[1000] shadow-lg ${
                    data.kind === 'perturbation' ? 'top-full mt-2' : 'bottom-full mb-2'
                }`}>
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

                    {/* Duration and uncertainty info */}
                    {data.durationDays && (
                        <div className="mb-2">
                            <span className="font-bold text-slate-300">Duration:</span> {data.durationDays} days ({Math.round(data.durationDays / 7 * 10) / 10} weeks)
                        </div>
                    )}
                    {data.confidenceRange && (data.confidenceRange.left > 0 || data.confidenceRange.right > 0) && (
                        <div className="mb-2">
                            <span className="font-bold text-slate-300">Uncertainty:</span>
                            {data.confidenceRange.left > 0 && (
                                <span className="ml-1">Start: {Math.round(data.confidenceRange.left / 25)} days</span>
                            )}
                            {data.confidenceRange.left > 0 && data.confidenceRange.right > 0 && <span>,</span>}
                            {data.confidenceRange.right > 0 && (
                                <span className="ml-1">End: {Math.round(data.confidenceRange.right / 25)} days</span>
                            )}
                        </div>
                    )}

                    <div className="mb-2">
                        <span className="font-bold text-slate-300">Inputs:</span> {data.inputsRequired}
                    </div>
                    <div>
                        <span className="font-bold text-slate-300">Outputs:</span> {data.outputsPromised}
                    </div>
                    {/* Arrow - points up for top lane (tooltip below), points down for others (tooltip above) */}
                    <div className={`absolute left-1/2 transform -translate-x-1/2 border-4 border-transparent ${
                        data.kind === 'perturbation'
                            ? 'bottom-full -mb-1 border-b-slate-800 dark:border-b-slate-700'
                            : 'top-full -mt-1 border-t-slate-800 dark:border-t-slate-700'
                    }`}></div>
                </div>
            )}
        </div>
    );
};

const ContainerNode = ({ data }: { data: { label: string; subItems: { title: string; status: string }[] } }) => {
    return (
        <div className="group relative">
            <div className="bg-slate-200 dark:bg-slate-700 rounded-xl p-4 shadow-md w-[280px] border border-slate-300 dark:border-slate-600">
                <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" style={{ left: -6 }} />
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
            // For timeline layout, don't auto-fit on resize - let user control the view
            // For non-timeline layouts, fit view normally
            if (!useTimelineLayout) {
                setTimeout(() => fitView({ padding: 0.1 }), 100);
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [fitView, useTimelineLayout]);

    return null;
};

// Viewport constraint handler for timeline layout - restricts vertical panning
const ViewportConstraint: React.FC<{ onViewportChange?: (viewport: Viewport) => void }> = ({ onViewportChange }) => {
    const { setViewport } = useReactFlow();
    const lockedY = useRef(0); // Lock y to initial position

    // This is called from the parent's onMove - immediately correct any y drift
    const constrainViewport = useCallback((viewport: Viewport) => {
        // If y has drifted from locked position, correct it immediately
        if (viewport.y !== lockedY.current) {
            setViewport({ ...viewport, y: lockedY.current }, { duration: 0 });
        }
        // Report the corrected viewport
        if (onViewportChange) {
            onViewportChange({ ...viewport, y: lockedY.current });
        }
    }, [setViewport, onViewportChange]);

    // Expose the constrain function via a ref that parent can access
    useEffect(() => {
        // Store the function on window for the parent to call
        (window as any).__constrainViewport = constrainViewport;
        return () => {
            delete (window as any).__constrainViewport;
        };
    }, [constrainViewport]);

    return null;
};

// Custom reset view button for timeline layout - resets to initial position
const HorizontalFitViewButton: React.FC = () => {
    const { setViewport } = useReactFlow();

    const handleClick = () => {
        // Reset to initial timeline view (start position, default zoom)
        setViewport({ x: 0, y: 0, zoom: 1 });
    };

    return (
        <button
            onClick={handleClick}
            className="react-flow__controls-button"
            title="reset view"
        >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            </svg>
        </button>
    );
};

export const DependencyMap: React.FC<DependencyMapProps> = ({ workflow, focusedAxisId, className, highlightedKinds, highlightedPrograms, onNodeClick, hideStatusIcons, useTimelineLayout, skipStrategyLane, hideTooltip, hideKindInfo, timelineScale = 1, onViewportChange }) => {
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
                        id: axis.id,
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
                        hideTooltip: hideTooltip,
                        hideKindInfo: hideKindInfo,
                        quarter: axis.quarter,
                        yOffset: (axis as any).yOffset,
                        xPosition: (axis as any).xPosition,
                        startDaysFromNow: (axis as any).startDaysFromNow,
                        durationDays: (axis as any).durationDays,
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
                            type: 'smoothstep',
                            animated: false,
                            zIndex: -1,
                            style: { stroke: edgeColor, strokeWidth: 2 },
                            markerEnd: {
                                type: MarkerType.ArrowClosed,
                                color: edgeColor,
                                width: 12,
                                height: 12,
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
            ? getTimelineLayoutedElements(filteredNodes, filteredEdges, containerSize.width, containerSize.height, skipStrategyLane, timelineScale)
            : getLayoutedElements(filteredNodes, filteredEdges);
    }, [workflow, focusedAxisId, highlightedKinds, highlightedPrograms, hideStatusIcons, hideTooltip, hideKindInfo, useTimelineLayout, containerSize, skipStrategyLane, timelineScale]);

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
                    fitViewOptions={{ padding: 0.02, minZoom: 0.6, maxZoom: 2 }}
                    defaultViewport={useTimelineLayout ? { x: 0, y: 0, zoom: 1 } : undefined}
                    minZoom={0.5}
                    panOnDrag={true}
                    panOnScroll={useTimelineLayout}
                    panOnScrollMode={useTimelineLayout ? "horizontal" : undefined}
                    zoomOnScroll={!useTimelineLayout}
                    preventScrolling={true}
                    onMove={(_event, viewport) => {
                        if (useTimelineLayout) {
                            // Call the constraint function to lock y position
                            const constrainFn = (window as any).__constrainViewport;
                            if (constrainFn) {
                                constrainFn(viewport);
                            }
                        } else if (onViewportChange) {
                            onViewportChange(viewport);
                        }
                    }}
                    attributionPosition="bottom-right"
                    elevateEdgesOnSelect={true}
                    edgesUpdatable={false}
                >
                    <ResizeHandler useTimelineLayout={useTimelineLayout} />
                    {useTimelineLayout && <ViewportConstraint onViewportChange={onViewportChange} />}
                    {!useTimelineLayout && <Background className="!bg-slate-50 dark:!bg-slate-900" color="#94a3b8" gap={16} />}
                    <Controls
                        className="dark:bg-slate-800 dark:border-slate-700 dark:text-white"
                        position="bottom-right"
                        showFitView={!useTimelineLayout}
                    >
                        {useTimelineLayout && <HorizontalFitViewButton />}
                    </Controls>
                </ReactFlow>
            </ReactFlowProvider>
        </div>
    );
};
