import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { DependencyMap } from '../components/DependencyMap';
import { mockWorkflowMenadione } from '../data/mockWorkflowMenadione';
import { Workflow } from '../types/workflow';
import { Viewport } from 'reactflow';

import { AxisDetailPanel } from '../components/AxisDetailPanel';
import { ThemeToggle } from '../components/ThemeToggle';

// Timeline configuration
const TIMELINE_CONFIG = {
    nowPixel: 100,
    fixedPixelsPerDay: 25,
};

const daysToXPosition = (daysFromNow: number): number => {
    const { nowPixel, fixedPixelsPerDay } = TIMELINE_CONFIG;
    const xPos = nowPixel + (daysFromNow * fixedPixelsPerDay);
    return Math.max(10, xPos);
};

const daysToWidth = (days: number): number => {
    const { fixedPixelsPerDay } = TIMELINE_CONFIG;
    const width = days * fixedPixelsPerDay;
    return Math.max(180, width);
};

// Cell Thalamus workflow - Dose and Timepoint Calibration
const cellModelsWorkflow: Workflow = {
    id: "CELL_THALAMUS_WORKFLOW",
    name: "Cell Thalamus",
    description: "Dose and Timepoint Calibration - identify stressor doses and timepoints that produce maximal, reproducible morphological separation without viability collapse",
    owner: "Roey",
    status: "in_progress",
    axes: [
        // Phase 0 — Single-Stressor Calibration (Menadione in A549)
        {
            id: "axis_phase0_menadione",
            kind: "stressor",
            name: "Phase 0: Menadione Calibration (A549)",
            status: "in_progress",
            owner: "Roey",
            definitionOfDone: "One dose and one timepoint nominated for menadione in A549 with maximal reproducible morphology shift before viability collapse.",
            inputsRequired: "A549 WCB, Menadione, Cell Painting reagents, CytoTox-Glo, γ-H2AX antibody",
            outputsPromised: "Nominated menadione dose and timepoint, replicate agreement report",
            blockers: undefined,
            tasks: [
                { id: "t_p0_dose_response", title: "Dose response (Vehicle + 5 doses)", status: "in_progress" },
                { id: "t_p0_timepoints", title: "24h and 48h imaging", status: "not_started" },
                { id: "t_p0_cell_painting", title: "Cell Painting morphology analysis", status: "not_started" },
                { id: "t_p0_cytotox", title: "CytoTox-Glo viability check", status: "not_started" },
                { id: "t_p0_gamma_h2ax", title: "γ-H2AX sanity check", status: "not_started" },
                { id: "t_p0_replicate", title: "Replicate stability (≥3 plates, ≥2 days)", status: "not_started" },
            ],
            startDaysFromNow: 0,
            durationDays: 28,
            confidenceRange: { left: 0, right: 175 },
        },
        // Phase 1 — Multi-Stressor Calibration in A549
        {
            id: "axis_phase1_multistressor",
            kind: "stressor",
            name: "Phase 1: Multi-Stressor Calibration (A549)",
            status: "not_started",
            owner: "Roey",
            definitionOfDone: "Usable operating doses and timepoints nominated for remaining 9 compounds in A549.",
            inputsRequired: "A549 WCB, 9 stressor compounds, Cell Painting reagents, CytoTox-Glo",
            outputsPromised: "Operating dose per stressor, failure mode documentation",
            blockers: undefined,
            dependencies: [
                { id: "d_phase0", label: "Phase 0: Menadione Calibration (A549)", status: "in_progress", linkedAxisId: "axis_phase0_menadione" },
            ],
            tasks: [
                { id: "t_p1_dose_curves", title: "Dose curves (Vehicle + 5 doses × 9 compounds)", status: "not_started" },
                { id: "t_p1_24h_imaging", title: "24h imaging all compounds", status: "not_started" },
                { id: "t_p1_48h_imaging", title: "48h imaging all compounds", status: "not_started" },
                { id: "t_p1_nomination", title: "Dose nomination per compound", status: "not_started" },
                { id: "t_p1_failure_doc", title: "Document failure modes", status: "not_started" },
            ],
            startDaysFromNow: 35,
            durationDays: 42,
        },
        // Phase 2 — Multi-Line Calibration (HepG2 + LX-2)
        {
            id: "axis_phase2_multiline",
            kind: "stressor",
            name: "Phase 2: Multi-Line Calibration (HepG2 + LX-2)",
            status: "not_started",
            owner: "Roey",
            definitionOfDone: "Cell-line-specific operating doses established for HepG2 and LX-2 across all stressors from Phase 1.",
            inputsRequired: "A549 WCB (reference), HepG2 WCB, LX-2 WCB, all stressors from Phase 1",
            outputsPromised: "Operating dose per stressor per cell line, cross-line comparison report",
            blockers: undefined,
            dependencies: [
                { id: "d_phase1", label: "Phase 1: Multi-Stressor Calibration (A549)", status: "not_started", linkedAxisId: "axis_phase1_multistressor" },
            ],
            tasks: [
                { id: "t_p2_hepg2_curves", title: "HepG2 dose curves (all stressors)", status: "not_started" },
                { id: "t_p2_lx2_curves", title: "LX-2 dose curves (all stressors)", status: "not_started" },
                { id: "t_p2_a549_reference", title: "A549 reference runs", status: "not_started" },
                { id: "t_p2_24h_48h", title: "24h and 48h imaging all lines", status: "not_started" },
                { id: "t_p2_nomination", title: "Dose nomination per stressor per line", status: "not_started" },
            ],
            startDaysFromNow: 84,
            durationDays: 56,
        },
        // Future: iPSC differentiations (deferred - post Phase 2)
        {
            id: "axis_future_ipsc",
            kind: "stressor",
            name: "Future: iPSC Cell Systems (Deferred)",
            status: "not_started",
            owner: "TBD",
            definitionOfDone: "Decision made on extending Cell Thalamus to iPSC-derived neurons and microglia based on Phase 2 results.",
            inputsRequired: "Phase 2 results, steering committee input",
            outputsPromised: "Go/no-go decision for iPSC extension",
            blockers: undefined,
            dependencies: [
                { id: "d_phase2", label: "Phase 2: Multi-Line Calibration (HepG2 + LX-2)", status: "not_started", linkedAxisId: "axis_phase2_multiline" },
            ],
            tasks: [
                { id: "t_future_review", title: "Review Phase 2 results", status: "not_started" },
                { id: "t_future_steering", title: "Steering committee decision", status: "not_started" },
                { id: "t_future_ingn2", title: "iNGN2 neurons (if approved)", status: "not_started" },
                { id: "t_future_imicroglia", title: "iMicroglia (if approved)", status: "not_started" },
            ],
            startDaysFromNow: 147,
            durationDays: 14,
        },
    ],
};

const CellModelsPage: React.FC = () => {
    const [selectedAxisId, setSelectedAxisId] = useState<string | null>(null);
    const [containerWidth, setContainerWidth] = useState(1600);
    const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });
    const containerRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        const updateWidth = () => {
            if (containerRef.current) {
                const { width } = containerRef.current.getBoundingClientRect();
                setContainerWidth(width);
            }
        };

        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, []);

    // Transform workflow data
    const transformedWorkflow = useMemo(() => {
        const transformedAxes = cellModelsWorkflow.axes.map(axis => {
            const axisWithDates = axis as typeof axis & {
                startDaysFromNow?: number;
                durationDays?: number;
            };

            if (axisWithDates.startDaysFromNow !== undefined) {
                const xPosition = daysToXPosition(axisWithDates.startDaysFromNow);
                const customWidth = axisWithDates.durationDays
                    ? daysToWidth(axisWithDates.durationDays)
                    : undefined;

                return {
                    ...axis,
                    xPosition,
                    customWidth,
                    quarter: undefined,
                };
            }

            return axis;
        });

        return {
            ...cellModelsWorkflow,
            axes: transformedAxes,
        };
    }, [containerWidth]);

    const handleNodeClick = (_: React.MouseEvent, node: any) => {
        setSelectedAxisId(node.id);
    };

    const selectedAxis = selectedAxisId ? transformedWorkflow.axes.find(a => a.id === selectedAxisId) : null;

    return (
        <div className="fixed top-0 left-0 right-0 bottom-0 w-screen h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors duration-300">
            <div className="shrink-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-8">
                    <div>
                        <h1 className="text-xl font-bold text-slate-900 dark:text-white">Cell Thalamus</h1>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Dose and Timepoint Calibration</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Views:</span>
                        <Link
                            to="/overall-new"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-emerald-100 hover:text-emerald-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-emerald-900 dark:hover:text-emerald-300 transition-colors"
                        >
                            Overall
                        </Link>
                        <Link
                            to="/cell-models"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300"
                        >
                            Cell Thalamus
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
                <div ref={containerRef} className="grow min-h-0 relative">
                    {/* Timeline lines */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '100px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-red-500" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                            <span>NOW</span>
                        </div>
                    </div>
                    {/* Q1 line */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '275px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Jan 23</span>
                            <span>Q1</span>
                        </div>
                    </div>
                    {/* Q2 line */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '2200px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Apr 10</span>
                            <span>Q2</span>
                        </div>
                    </div>

                    {/* Single lane background for Cell Thalamus */}
                    <div className="absolute inset-0 pointer-events-none overflow-hidden flex flex-col z-0">
                        <div className="flex-1 bg-pink-300/10 dark:bg-pink-900/10 border-b-2 border-pink-300 dark:border-pink-700 relative">
                            <div className="absolute left-2 top-2 bg-pink-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                Cell Thalamus
                            </div>
                        </div>
                    </div>

                    <DependencyMap
                        workflow={transformedWorkflow}
                        className="h-full w-full bg-transparent"
                        onNodeClick={handleNodeClick}
                        hideStatusIcons={false}
                        useTimelineLayout={true}
                        skipStrategyLane={true}
                        timelineScale={3.2}
                        onViewportChange={setViewport}
                    />
                </div>

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

export default CellModelsPage;
