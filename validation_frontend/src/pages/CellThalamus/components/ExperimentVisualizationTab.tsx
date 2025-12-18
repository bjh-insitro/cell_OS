/**
 * Experiment Visualization Tab
 *
 * Interactive visualization of experimental results including:
 * - Animated plate layout
 * - Well-by-well results
 * - Dose-response coverage
 */

import React, { useState, useEffect } from 'react';
import { cellThalamusService } from '../../../services/CellThalamusService';
import PlateLayoutVisualization from '../../AutonomousLoop/components/PlateLayoutVisualization';
import ExperimentWorkflowAnimation from '../../AutonomousLoop/components/ExperimentWorkflowAnimation';

interface ExperimentVisualizationTabProps {
    selectedDesignId: string | null;
    onDesignChange: (designId: string) => void;
}

const ExperimentVisualizationTab: React.FC<ExperimentVisualizationTabProps> = ({
    selectedDesignId,
    onDesignChange
}) => {
    const [designs, setDesigns] = useState<any[]>([]);
    const [results, setResults] = useState<any[]>([]);
    const [plateData, setPlateData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedCompound, setSelectedCompound] = useState<string | null>(null);
    const [selectedCellLine, setSelectedCellLine] = useState<string | null>(null);
    const [selectedTimepoint, setSelectedTimepoint] = useState<number | null>(null);

    // Fetch designs
    useEffect(() => {
        const fetchDesigns = async () => {
            try {
                const data = await cellThalamusService.getDesigns();
                setDesigns(data);
                if (!selectedDesignId && data.length > 0) {
                    onDesignChange(data[0].design_id);
                }
            } catch (err) {
                console.error('Failed to fetch designs:', err);
                setError('Failed to load designs');
            }
        };
        fetchDesigns();
    }, []);

    // Fetch results when design changes
    useEffect(() => {
        if (!selectedDesignId) return;

        const fetchResults = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await cellThalamusService.getResults(selectedDesignId);
                setResults(data);

                // Auto-select first compound/cell line/timepoint
                if (data.length > 0) {
                    const compounds = [...new Set(data.map((r: any) => r.compound))];
                    const cellLines = [...new Set(data.map((r: any) => r.cell_line))];
                    const timepoints = [...new Set(data.map((r: any) => Math.round(r.timepoint_h)))];

                    setSelectedCompound(compounds[0]);
                    setSelectedCellLine(cellLines[0]);
                    setSelectedTimepoint(timepoints[0]);
                }
            } catch (err) {
                console.error('Failed to fetch results:', err);
                setError('Failed to load results');
            } finally {
                setLoading(false);
            }
        };

        fetchResults();
    }, [selectedDesignId]);

    // Filter plate data based on selections
    useEffect(() => {
        if (!results.length) {
            setPlateData([]);
            return;
        }

        const filtered = results.filter((r: any) => {
            if (selectedCompound && r.compound !== selectedCompound) return false;
            if (selectedCellLine && r.cell_line !== selectedCellLine) return false;
            if (selectedTimepoint && Math.round(r.timepoint_h) !== selectedTimepoint) return false;
            return true;
        });

        const plateDataFormatted = filtered.map((r: any) => ({
            wellId: r.well_id,
            compound: r.compound,
            cellLine: r.cell_line,
            doseUm: r.dose_uM,
            atpSignal: r.atp_signal
        }));

        setPlateData(plateDataFormatted);
    }, [results, selectedCompound, selectedCellLine, selectedTimepoint]);

    // Get unique values for filters
    const compounds = [...new Set(results.map((r: any) => r.compound))];
    const cellLines = [...new Set(results.map((r: any) => r.cell_line))];
    const timepoints = [...new Set(results.map((r: any) => Math.round(r.timepoint_h)))].sort((a, b) => a - b);

    // Calculate summary stats
    const dosesCount = new Set(results.map((r: any) => r.dose_uM)).size;
    const wellsCount = plateData.length;
    const avgViability = plateData.length > 0
        ? (plateData.reduce((sum, d) => sum + d.atpSignal, 0) / plateData.length * 100).toFixed(1)
        : 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-2xl font-bold mb-2">Experiment Visualization</h2>
                <p className="text-slate-400">
                    Interactive visualization of experimental plate layouts and results
                </p>
            </div>

            {/* Experimental Workflow Animation */}
            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                <h3 className="text-xl font-semibold mb-4">Experimental Protocol Workflow</h3>
                <ExperimentWorkflowAnimation
                    isDarkMode={true}
                    autoPlay={false}
                />
            </div>

            {/* Design Selector */}
            <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                <label className="block text-sm font-medium mb-2">Select Design:</label>
                <select
                    value={selectedDesignId || ''}
                    onChange={(e) => onDesignChange(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white"
                >
                    {designs.map((design) => (
                        <option key={design.design_id} value={design.design_id}>
                            {design.design_id.slice(0, 8)}... - Phase {design.phase} - {design.created_at}
                        </option>
                    ))}
                </select>
            </div>

            {error && (
                <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 text-red-300">
                    {error}
                </div>
            )}

            {loading && (
                <div className="text-center py-12 text-slate-400">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500 mb-4"></div>
                    <p>Loading experimental data...</p>
                </div>
            )}

            {!loading && results.length > 0 && (
                <>
                    {/* Filters */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <label className="block text-sm font-medium mb-2">Compound:</label>
                            <select
                                value={selectedCompound || ''}
                                onChange={(e) => setSelectedCompound(e.target.value)}
                                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white"
                            >
                                {compounds.map((compound) => (
                                    <option key={compound} value={compound}>
                                        {compound}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <label className="block text-sm font-medium mb-2">Cell Line:</label>
                            <select
                                value={selectedCellLine || ''}
                                onChange={(e) => setSelectedCellLine(e.target.value)}
                                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white"
                            >
                                {cellLines.map((cellLine) => (
                                    <option key={cellLine} value={cellLine}>
                                        {cellLine}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <label className="block text-sm font-medium mb-2">Timepoint:</label>
                            <select
                                value={selectedTimepoint || ''}
                                onChange={(e) => setSelectedTimepoint(Number(e.target.value))}
                                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white"
                            >
                                {timepoints.map((timepoint) => (
                                    <option key={timepoint} value={timepoint}>
                                        {timepoint}h
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Summary Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <div className="text-slate-400 text-sm">Total Wells</div>
                            <div className="text-2xl font-bold text-violet-400">{wellsCount}</div>
                        </div>
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <div className="text-slate-400 text-sm">Dose Points</div>
                            <div className="text-2xl font-bold text-violet-400">{dosesCount}</div>
                        </div>
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <div className="text-slate-400 text-sm">Avg Viability</div>
                            <div className="text-2xl font-bold text-violet-400">{avgViability}%</div>
                        </div>
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                            <div className="text-slate-400 text-sm">Current Selection</div>
                            <div className="text-sm font-medium text-violet-400">
                                {selectedCompound} × {selectedCellLine}
                            </div>
                        </div>
                    </div>

                    {/* Plate Layout Visualization */}
                    <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                        <div className="mb-4">
                            <h3 className="text-xl font-semibold mb-2">Plate Layout</h3>
                            <p className="text-slate-400 text-sm">
                                Showing {plateData.length} wells for {selectedCompound} on {selectedCellLine} cells at {selectedTimepoint}h
                            </p>
                        </div>

                        {plateData.length > 0 ? (
                            <PlateLayoutVisualization
                                data={plateData}
                                isDarkMode={true}
                                animated={true}
                            />
                        ) : (
                            <div className="text-center py-12 text-slate-500">
                                No data available for the selected filters
                            </div>
                        )}
                    </div>

                    {/* Dose Distribution */}
                    <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                        <h3 className="text-xl font-semibold mb-4">Dose Distribution</h3>
                        <div className="space-y-2">
                            {[...new Set(plateData.map(d => d.doseUm))].sort((a, b) => a - b).map(dose => {
                                const wellsAtDose = plateData.filter(d => d.doseUm === dose);
                                const avgViabilityAtDose = (wellsAtDose.reduce((sum, d) => sum + d.atpSignal, 0) / wellsAtDose.length * 100).toFixed(1);

                                return (
                                    <div key={dose} className="flex items-center gap-4">
                                        <div className="w-24 text-sm font-mono text-slate-400">
                                            {dose} µM
                                        </div>
                                        <div className="flex-1 bg-slate-900 rounded-full h-8 relative overflow-hidden">
                                            <div
                                                className="absolute inset-y-0 left-0 bg-gradient-to-r from-violet-500 to-violet-600 flex items-center justify-end pr-2"
                                                style={{ width: `${Math.min(100, parseFloat(avgViabilityAtDose))}%` }}
                                            >
                                                <span className="text-xs font-medium text-white">
                                                    {avgViabilityAtDose}%
                                                </span>
                                            </div>
                                        </div>
                                        <div className="w-16 text-sm text-slate-400">
                                            {wellsAtDose.length} wells
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </>
            )}

            {!loading && results.length === 0 && !error && (
                <div className="text-center py-12 text-slate-400">
                    <p>No experimental data available.</p>
                    <p className="mt-2 text-sm">Run a simulation first from the "Run Simulation" tab.</p>
                </div>
            )}
        </div>
    );
};

export default ExperimentVisualizationTab;
