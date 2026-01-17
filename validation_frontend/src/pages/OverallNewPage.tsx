import React, { useState, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { DependencyMap } from '../components/DependencyMap';
import { mockWorkflowMenadione } from '../data/mockWorkflowMenadione';
import { Workflow } from '../types/workflow';
import { Viewport } from 'reactflow';

import { AxisDetailPanel } from '../components/AxisDetailPanel';

import { ThemeToggle } from '../components/ThemeToggle';

// Timeline configuration - all dates and positions defined here
const TIMELINE_CONFIG = {
    // Reference dates
    nowDate: new Date(), // Today's date, updates automatically
    q1Date: new Date(2026, 0, 23), // Jan 23, 2026
    q2Date: new Date(2026, 3, 10), // Apr 10, 2026

    // Fixed pixel positions (from CSS)
    nowPixel: 100,      // NOW line at 100px from left
    rightMargin: 200,   // Q2 line at 200px from right edge

    // Fixed design width - DO NOT scale based on container width
    // This ensures layout stays consistent across screen sizes
    designWidth: 2600,

    // Fixed pixels per day for consistent timeline spacing
    fixedPixelsPerDay: 25,
};

// Calculate days between two dates
const daysBetween = (date1: Date, date2: Date): number => {
    const msPerDay = 24 * 60 * 60 * 1000;
    return Math.round((date2.getTime() - date1.getTime()) / msPerDay);
};

// Calculate timeline metrics
const getTimelineMetrics = (containerWidth: number) => {
    const { nowDate, q2Date, nowPixel, rightMargin, designWidth } = TIMELINE_CONFIG;

    // Usable timeline width (from NOW to Q2)
    const timelineWidth = containerWidth - nowPixel - rightMargin;

    // Total days from NOW to Q2
    const totalDays = daysBetween(nowDate, q2Date);

    // Pixels per day
    const pixelsPerDay = timelineWidth / totalDays;

    // Scale factor for converting to design coordinates
    const scaleFactor = containerWidth / designWidth;

    return {
        timelineWidth,
        totalDays,
        pixelsPerDay,
        scaleFactor,
        nowPixel,
    };
};

// Convert a date offset (days from NOW) to x position - FIXED, not scaled
const daysToXPosition = (daysFromNow: number, _containerWidth: number): number => {
    const { nowPixel, fixedPixelsPerDay } = TIMELINE_CONFIG;
    const xPos = nowPixel + (daysFromNow * fixedPixelsPerDay);
    // Ensure nodes are visible - clamp to minimum of 10px from left edge
    return Math.max(10, xPos);
};

// Convert duration in days to width - FIXED, not scaled
const daysToWidth = (days: number, _containerWidth: number): number => {
    const { fixedPixelsPerDay } = TIMELINE_CONFIG;
    const width = days * fixedPixelsPerDay;
    // Ensure minimum width of 180px
    return Math.max(180, width);
};

// Helper to log timeline calculations (for debugging)
const logTimelineInfo = (containerWidth: number) => {
    const metrics = getTimelineMetrics(containerWidth);
    console.log('Timeline Metrics:', {
        containerWidth,
        ...metrics,
        '1 week in pixels': metrics.pixelsPerDay * 7,
        '4 weeks in pixels': metrics.pixelsPerDay * 28,
    });
};

// Extended workflow with HepG2 transduction
const workflowWithHepG2: Workflow = {
    ...mockWorkflowMenadione,
    axes: [
        ...mockWorkflowMenadione.axes,
        {
            id: "axis_transduce_hepg2",
            kind: "cell_line",
            name: "Transduce HepG2s with WG Library",
            status: "not_started",
            owner: "Babacar",
            definitionOfDone: "HepG2 mutant pool created for screening.",
            visible: true,
            inputsRequired: "Cas9+ HepG2s, WG LV Library",
            outputsPromised: "Transduced HepG2 cell pool",
            blockers: undefined,
            dependencies: [
                { id: "d_wg_lib_hepg2", label: "Generate Lib LV particles", status: "not_started", linkedAxisId: "axis_generate_lv" },
            ],
            tasks: [{ id: "t_transduce_hepg2", title: "Large scale transduction", status: "not_started" }],
            // Date-based: starts after A549 transduction (44 + 28 + 7 = 79) + 16 days offset
            startDaysFromNow: 95,
            durationDays: 28, // 4 weeks duration
            confidenceRange: { left: 100, right: 200 },
        },
        // HepG2 Functional Genomics downstream
        {
            id: "axis_hepg2_fg_treat",
            kind: "perturbation",
            name: "Treat with Menadione (HepG2)",
            status: "not_started",
            owner: "TBD",
            definitionOfDone: "HepG2 cells treated with Menadione for sequencing.",
            inputsRequired: "Transduced HepG2 cells, Menadione",
            outputsPromised: "Treated HepG2 cells for sequencing",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_transduce", label: "Transduce HepG2s with WG Library", status: "not_started", linkedAxisId: "axis_transduce_hepg2" },
            ],
            tasks: [{ id: "t_hepg2_fg_treat", title: "Treat cells", status: "not_started" }],
            startDaysFromNow: 162,
            durationDays: 14,
        },
        {
            id: "axis_hepg2_prepare_seq_lib",
            kind: "perturbation",
            name: "Prepare Seq Lib (HepG2)",
            status: "not_started",
            owner: "TBD",
            definitionOfDone: "HepG2 sequencing library prepared.",
            inputsRequired: "Treated HepG2 cells",
            outputsPromised: "HepG2 sequencing library",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_fg_treat", label: "Treat with Menadione (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_fg_treat" },
            ],
            tasks: [{ id: "t_hepg2_prep_seq", title: "Prepare sequencing library", status: "not_started" }],
            startDaysFromNow: 179,
            durationDays: 7,
        },
        {
            id: "axis_hepg2_perturb",
            kind: "perturbation",
            name: "Acquire WG Perturb HepG2/Menadione Seq data",
            status: "not_started",
            owner: "TBD",
            definitionOfDone: "Complete genome-wide perturbation screen in HepG2 cells with Menadione stressor.",
            inputsRequired: "HepG2 cells, Menadione, WG Library, Transduced cells",
            outputsPromised: "Raw HepG2 perturbation screening data",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_seq_lib", label: "Prepare Seq Lib (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_prepare_seq_lib" },
            ],
            tasks: [{ id: "t_hepg2_perturb", title: "Perform perturbation screen", status: "not_started" }],
            startDaysFromNow: 189,
            durationDays: 14,
        },
        // HepG2 PST downstream
        {
            id: "axis_hepg2_treat",
            kind: "measurement",
            name: "Treat with Menadione (HepG2)",
            status: "not_started",
            owner: "Jana",
            definitionOfDone: "HepG2 cells treated with Menadione stressor.",
            inputsRequired: "Transduced HepG2 cells, Menadione",
            outputsPromised: "Treated HepG2 cell plates",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_transduce_pst", label: "Transduce HepG2s with WG Library", status: "not_started", linkedAxisId: "axis_transduce_hepg2" },
            ],
            tasks: [{ id: "t_hepg2_treat", title: "Perform treatment", status: "not_started" }],
            startDaysFromNow: 162,
            durationDays: 14,
        },
        {
            id: "axis_hepg2_prepare_plates",
            kind: "measurement",
            name: "Prepare plates for phenotyping (HepG2)",
            status: "not_started",
            owner: "Jana",
            definitionOfDone: "HepG2 plates prepared and ready for imaging.",
            inputsRequired: "Treated HepG2 plates",
            outputsPromised: "Prepared HepG2 plates",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_treat_prep", label: "Treat with Menadione (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_treat" },
            ],
            tasks: [{ id: "t_hepg2_prepare", title: "Prepare plates", status: "not_started" }],
            startDaysFromNow: 179,
            durationDays: 11,
        },
        {
            id: "axis_hepg2_paint_image",
            kind: "measurement",
            name: "Acquire Phenotyping images (HepG2)",
            status: "not_started",
            owner: "Jana",
            definitionOfDone: "HepG2 plates imaged.",
            inputsRequired: "Prepared HepG2 plates",
            outputsPromised: "Raw HepG2 images",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_prepare", label: "Prepare plates for phenotyping (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_prepare_plates" },
            ],
            tasks: [{ id: "t_hepg2_image", title: "Acquire images", status: "not_started" }],
            startDaysFromNow: 193,
            durationDays: 14,
        },
        {
            id: "axis_hepg2_iss",
            kind: "measurement",
            name: "Acquire ISS images (HepG2)",
            status: "not_started",
            owner: "Jana",
            definitionOfDone: "HepG2 ISS imaging complete.",
            inputsRequired: "Imaged HepG2 plates",
            outputsPromised: "HepG2 ISS images",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_image", label: "Acquire Phenotyping images (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_paint_image" },
            ],
            tasks: [{ id: "t_hepg2_iss", title: "Acquire ISS images", status: "not_started" }],
            startDaysFromNow: 210,
            durationDays: 14,
        },
        // HepG2 Compute downstream
        {
            id: "axis_hepg2_analysis",
            kind: "analysis",
            name: "POSH/Perturb Analysis (HepG2)",
            status: "not_started",
            owner: "TBD",
            definitionOfDone: "HepG2 data analysis complete.",
            inputsRequired: "HepG2 ISS images, Phenotyping images, Perturbation data",
            outputsPromised: "HepG2 analysis results, hit list",
            blockers: undefined,
            visible: true,
            dependencies: [
                { id: "d_hepg2_iss_analysis", label: "Acquire ISS images (HepG2)", status: "not_started", linkedAxisId: "axis_hepg2_iss" },
                { id: "d_hepg2_perturb_analysis", label: "Acquire WG Perturb HepG2/Menadione Seq data", status: "not_started", linkedAxisId: "axis_hepg2_perturb" },
            ],
            tasks: [{ id: "t_hepg2_analysis", title: "Run analysis pipeline", status: "not_started" }],
            startDaysFromNow: 231,
            durationDays: 28,
        },
    ],
};

const OverallNewPage: React.FC = () => {
    const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
    const [selectedAxisId, setSelectedAxisId] = useState<string | null>(null);
    const [containerWidth, setContainerWidth] = useState(1600); // Default, will be measured
    const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Measure the actual container width
    React.useEffect(() => {
        const updateWidth = () => {
            if (containerRef.current) {
                const { width } = containerRef.current.getBoundingClientRect();
                setContainerWidth(width);
                // Debug: log timeline info
                logTimelineInfo(width);
            }
        };

        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, []);

    // Transform workflow data: convert date-based fields to xPosition and customWidth
    const transformedWorkflow = useMemo(() => {
        const transformedAxes = workflowWithHepG2.axes.map(axis => {
            const axisWithDates = axis as typeof axis & {
                startDaysFromNow?: number;
                durationDays?: number;
            };

            // If this axis has date-based positioning, calculate xPosition and customWidth
            if (axisWithDates.startDaysFromNow !== undefined) {
                const xPosition = daysToXPosition(axisWithDates.startDaysFromNow, containerWidth);
                const customWidth = axisWithDates.durationDays
                    ? daysToWidth(axisWithDates.durationDays, containerWidth)
                    : undefined;

                return {
                    ...axis,
                    xPosition,
                    customWidth,
                    // Clear quarter if using date-based positioning
                    quarter: undefined,
                };
            }

            return axis;
        });

        return {
            ...workflowWithHepG2,
            axes: transformedAxes,
        };
    }, [containerWidth]);

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

    const selectedAxis = selectedAxisId ? transformedWorkflow.axes.find(a => a.id === selectedAxisId) : null;

    const kinds: { value: string; label: string; color: string }[] = [
        { value: 'cell_line', label: 'Biobanking', color: 'bg-violet-500' },
        { value: 'stressor', label: 'Cell Models', color: 'bg-pink-500' },
        { value: 'perturbation', label: 'Functional Genomics', color: 'bg-teal-500' },
        { value: 'measurement', label: 'PST', color: 'bg-orange-500' },
        { value: 'analysis', label: 'Compute', color: 'bg-slate-500' },
    ];

    return (
        <div className="fixed top-0 left-0 right-0 bottom-0 w-screen h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors duration-300">
            <div className="shrink-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-8">
                    <div>
                        <h1 className="text-xl font-bold text-slate-900 dark:text-white">{workflowWithHepG2.name}</h1>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{workflowWithHepG2.id}</p>
                    </div>

                    <div className="flex items-center space-x-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400 font-medium">Filter by:</span>
                        <div className="flex space-x-2">
                            {kinds.map(kind => (
                                <button
                                    key={kind.value}
                                    onClick={() => toggleKind(kind.value)}
                                    className={`
                                        px-2 py-1 rounded-full text-[10px] font-bold transition-all border-transparent shadow-md
                                        ${kind.color} text-white
                                        ${selectedKinds.includes(kind.value)
                                            ? 'opacity-100'
                                            : 'opacity-30 hover:opacity-50'
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
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Strategy:</span>
                        <Link
                            to="/overall"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-emerald-100 hover:text-emerald-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-emerald-900 dark:hover:text-emerald-300 transition-colors"
                        >
                            Overall
                        </Link>
                    </div>
                    <div className="flex items-center gap-2 mr-4">
                        <span className="text-sm text-slate-500 dark:text-slate-400">Workflows:</span>
                        <Link
                            to="/map"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-blue-100 hover:text-blue-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-blue-900 dark:hover:text-blue-300 transition-colors"
                        >
                            Generic
                        </Link>
                        <Link
                            to="/menadione/map"
                            className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300"
                        >
                            Menadione A549
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
                    {/* Timeline lines - NOW at 100px, Q2 at 200px from right - scroll with viewport */}
                    {/* NOW line - dynamic date (100px from left) */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '100px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-red-500" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                            <span>NOW</span>
                        </div>
                    </div>
                    {/* Q1 line - Jan 23 (day 7 at 25px/day = 275px) */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '275px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Jan 23</span>
                            <span>Q1</span>
                        </div>
                    </div>
                    {/* Q2 line - Apr 10 (day 84 at 25px/day = 2200px) */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '2200px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Apr 10</span>
                            <span>Q2</span>
                        </div>
                    </div>
                    {/* Q3 line - Jul 10 (day 175 at 25px/day = 4475px) */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '4475px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Jul 10</span>
                            <span>Q3</span>
                        </div>
                    </div>
                    {/* Q4 line - Oct 9 (day 266 at 25px/day = 6750px) */}
                    <div className="absolute top-0 bottom-0 pointer-events-none z-0" style={{ left: '6750px', transform: `translateX(${viewport.x}px)` }}>
                        <div className="h-full w-0.5 bg-slate-300 dark:bg-slate-600" />
                        <div className="absolute -translate-x-1/2 left-1/2 bg-slate-500 text-white text-[10px] font-bold px-2 py-0.5 rounded flex flex-col items-center text-center" style={{ bottom: '4px' }}>
                            <span>Oct 9</span>
                            <span>Q4</span>
                        </div>
                    </div>
                    {/* Swim lane backgrounds and labels - 5 equal lanes at 20% each */}
                    <div className="absolute inset-0 pointer-events-none overflow-hidden flex flex-col z-0">
                        {/* Functional Genomics lane - teal (lane 1) */}
                        <div className="flex-1 bg-teal-300/10 dark:bg-teal-900/10 border-b-2 border-teal-300 dark:border-teal-700 relative">
                            <div className="absolute left-2 top-2 bg-teal-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                Functional Genomics
                            </div>
                        </div>
                        {/* Biobanking lane - violet (lane 2) */}
                        <div className="flex-1 bg-violet-300/10 dark:bg-violet-900/10 border-b-2 border-violet-300 dark:border-violet-700 relative">
                            <div className="absolute left-2 top-2 bg-violet-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                Biobanking
                            </div>
                        </div>
                        {/* Cell Models lane - pink (lane 3) */}
                        <div className="flex-1 bg-pink-300/10 dark:bg-pink-900/10 border-b-2 border-pink-300 dark:border-pink-700 relative">
                            <div className="absolute left-2 top-2 bg-pink-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                Cell Models
                            </div>
                        </div>
                        {/* PST lane - orange (lane 4) */}
                        <div className="flex-1 bg-orange-300/10 dark:bg-orange-900/10 border-b-2 border-orange-300 dark:border-orange-700 relative">
                            <div className="absolute left-2 top-2 bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                PST
                            </div>
                        </div>
                        {/* Compute lane - grey (lane 5) */}
                        <div className="flex-1 bg-slate-400/10 dark:bg-slate-700/10 border-b-2 border-slate-400 dark:border-slate-600 relative">
                            <div className="absolute left-2 top-2 bg-slate-500 text-white text-xs font-bold px-2 py-1 rounded shadow z-10">
                                Compute
                            </div>
                        </div>
                    </div>
                    <DependencyMap
                        workflow={transformedWorkflow}
                        className="h-full w-full bg-transparent"
                        highlightedKinds={selectedKinds}
                        onNodeClick={handleNodeClick}
                        hideStatusIcons={false}
                        useTimelineLayout={true}
                        skipStrategyLane={true}
                        timelineScale={3.2}
                        onViewportChange={setViewport}
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

export default OverallNewPage;
