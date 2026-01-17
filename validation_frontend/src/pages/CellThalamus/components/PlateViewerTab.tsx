/**
 * Tab 6: Plate Viewer
 *
 * 96-well and 384-well plate heatmaps with spatial visualization
 */

import React, { useState, useMemo } from 'react';
import { useDesigns, usePlateData, useResults } from '../hooks/useCellThalamusData';

type PlateFormat = '96' | '384';

interface PlateViewerTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const PLATE_CONFIG: Record<PlateFormat, { rows: number; cols: number; rowLabels: string[] }> = {
  '96': {
    rows: 8,
    cols: 12,
    rowLabels: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
  },
  '384': {
    rows: 16,
    cols: 24,
    rowLabels: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'],
  },
};

const PlateViewerTab: React.FC<PlateViewerTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: results, refetch: refetchResults } = useResults(selectedDesignId);

  const [selectedPlate, setSelectedPlate] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>('atp_signal');
  const [isLiveMode, setIsLiveMode] = useState<boolean>(false);

  const { data: plateData, loading, error, refetch: refetchPlateData } = usePlateData(selectedDesignId, selectedPlate);

  // Detect plate format from design metadata or plate data
  const plateFormat: PlateFormat = useMemo(() => {
    if (!selectedDesignId || !designs) return '96';
    const design = designs.find(d => d.design_id === selectedDesignId);
    if (design?.metadata?.plate_format === 384) return '384';
    // Fallback: check if any well position has row > H or col > 12
    if (plateData) {
      for (const well of plateData) {
        const row = well.well_id?.charCodeAt(0) - 65;
        const col = parseInt(well.well_id?.substring(1) || '0');
        if (row > 7 || col > 12) return '384';
      }
    }
    return '96';
  }, [selectedDesignId, designs, plateData]);

  const { rows: numRows, cols: numCols, rowLabels } = PLATE_CONFIG[plateFormat];

  const allDesigns = useMemo(() => designs || [], [designs]);
  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  // Check if selected design is currently running
  const isDesignRunning = useMemo(() => {
    if (!selectedDesignId || !designs) return false;
    const design = designs.find(d => d.design_id === selectedDesignId);
    return design?.status === 'running';
  }, [selectedDesignId, designs]);

  // Live polling: refetch data every 5 seconds when design is running
  React.useEffect(() => {
    if (isDesignRunning && selectedDesignId) {
      setIsLiveMode(true);
      refetchResults();
      if (selectedPlate) {
        refetchPlateData();
      }

      const intervalId = setInterval(() => {
        refetchResults();
        if (selectedPlate) {
          refetchPlateData();
        }
      }, 5000);

      return () => clearInterval(intervalId);
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, selectedPlate, refetchResults, refetchPlateData]);

  // Extract unique plate IDs
  const plateIds = Array.from(new Set(results?.map((r) => r.plate_id) || [])).sort();

  const metrics = [
    { value: 'atp_signal', label: 'ATP Viability' },
    { value: 'ldh_signal', label: 'LDH Signal' },
    { value: 'viability_fraction', label: 'Viability (Ground Truth)' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
    { value: 'gamma_h2ax_intensity', label: 'γ-H2AX Intensity' },
    { value: 'gamma_h2ax_fold_induction', label: 'γ-H2AX Fold Induction' },
    { value: 'gamma_h2ax_pct_positive', label: 'γ-H2AX % Positive' },
  ];

  // Parse well ID to row/col
  const parseWellId = (wellId: string) => {
    const row = wellId.charCodeAt(0) - 65; // A=0, B=1, ...
    const col = parseInt(wellId.substring(1)) - 1;
    return { row, col };
  };

  // Create grid dynamically based on plate format
  const heatmapGrid = useMemo(() => {
    if (!plateData) return null;

    const grid: (number | null)[][] = Array(numRows)
      .fill(null)
      .map(() => Array(numCols).fill(null));

    plateData.forEach((well) => {
      const { row, col } = parseWellId(well.well_id);
      const value = (well as any)[selectedMetric];
      if (row >= 0 && row < numRows && col >= 0 && col < numCols) {
        grid[row][col] = value;
      }
    });

    return grid;
  }, [plateData, selectedMetric, numRows, numCols]);

  // Color scale (blue = low, red = high)
  const getColor = (value: number | null, min: number, max: number) => {
    if (value === null) return '#334155'; // slate-700 for empty
    const normalized = (value - min) / (max - min);
    const r = Math.round(normalized * 255);
    const b = Math.round((1 - normalized) * 255);
    return `rgb(${r}, 100, ${b})`;
  };

  // Calculate min/max for color scale
  const { min, max } = useMemo(() => {
    if (!heatmapGrid) return { min: 0, max: 1 };
    const values = heatmapGrid.flat().filter((v) => v !== null) as number[];
    return {
      min: Math.min(...values),
      max: Math.max(...values),
    };
  }, [heatmapGrid]);

  // Check if well is on edge (dynamic based on plate format)
  const isEdgeWell = (row: number, col: number) => {
    return row === 0 || row === numRows - 1 || col === 0 || col === numCols - 1;
  };

  // Calculate edge effect statistics
  const edgeStats = useMemo(() => {
    if (!plateData) return null;

    const edgeWells = plateData.filter((well) => {
      const { row, col } = parseWellId(well.well_id);
      return isEdgeWell(row, col);
    });

    const centerWells = plateData.filter((well) => {
      const { row, col } = parseWellId(well.well_id);
      return !isEdgeWell(row, col);
    });

    const edgeValues = edgeWells.map((w) => (w as any)[selectedMetric]);
    const centerValues = centerWells.map((w) => (w as any)[selectedMetric]);

    const edgeMean = edgeValues.reduce((a, b) => a + b, 0) / edgeValues.length;
    const centerMean = centerValues.reduce((a, b) => a + b, 0) / centerValues.length;

    return {
      edgeMean,
      centerMean,
      difference: edgeMean - centerMean,
      percentDiff: ((edgeMean - centerMean) / centerMean) * 100,
    };
  }, [plateData, selectedMetric]);

  // Well sizing based on plate format
  const wellSize = plateFormat === '384' ? 'w-6 h-5' : 'w-16 h-14';
  const wellGap = plateFormat === '384' ? 'mr-0.5' : 'mr-1';
  const fontSize = plateFormat === '384' ? 'text-[8px]' : 'text-xs';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Plate Viewer</h2>
        <p className="text-slate-400">
          {plateFormat}-well plate heatmaps with spatial visualization and edge effect analysis
        </p>
      </div>

      {/* Live Mode Indicator */}
      {isLiveMode && results && results.length > 0 && (
        <div className="bg-gradient-to-r from-red-900/30 to-orange-900/30 border-2 border-red-500/50 rounded-xl p-4 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-ping absolute"></div>
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
              </div>
              <div>
                <div className="text-lg font-bold text-white">🔴 LIVE DATA</div>
                <div className="text-sm text-red-300">
                  Plate data updating every 5 seconds as wells complete
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-red-400">{results.length}</div>
              <div className="text-xs text-red-300 uppercase tracking-wider">Wells Completed</div>
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Design Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Design
            </label>
            <select
              value={selectedDesignId || ''}
              onChange={(e) => {
                onDesignChange(e.target.value || null);
                setSelectedPlate(null);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="">-- Select design --</option>
              {allDesigns.map((design, index) => {
                const date = design.created_at ? new Date(design.created_at).toLocaleString() : '';
                const statusLabel = design.status === 'running' ? ' 🔴 LIVE' : design.status === 'completed' ? ' ✓' : '';
                return (
                  <option key={design.design_id} value={design.design_id}>
                    {date} ({design.design_id.slice(0, 8)}) - {design.well_count || '?'} wells{statusLabel}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Plate Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Plate
            </label>
            <select
              value={selectedPlate || ''}
              onChange={(e) => setSelectedPlate(e.target.value || null)}
              disabled={!selectedDesignId}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            >
              <option value="">-- Select plate --</option>
              {plateIds.map((plateId) => (
                <option key={plateId} value={plateId}>
                  {plateId}
                </option>
              ))}
            </select>
          </div>

          {/* Metric Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Metric
            </label>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              disabled={!selectedDesignId}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            >
              {metrics.map((metric) => (
                <option key={metric.value} value={metric.value}>
                  {metric.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Edge Effect Stats */}
        {edgeStats && (
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Edge Mean</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {edgeStats.edgeMean.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Center Mean</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {edgeStats.centerMean.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Difference</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {edgeStats.difference.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">% Difference</div>
                <div
                  className={`text-lg font-bold mt-1 ${
                    Math.abs(edgeStats.percentDiff) > 10 ? 'text-red-400' : 'text-green-400'
                  }`}
                >
                  {edgeStats.percentDiff > 0 ? '+' : ''}
                  {edgeStats.percentDiff.toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Heatmap */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a design to view plate heatmaps
          </div>
        </div>
      ) : !selectedPlate ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a plate to view heatmap
          </div>
        </div>
      ) : loading ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-slate-400">Loading plate data...</div>
        </div>
      ) : error ? (
        <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6">
          <div className="text-red-300">Error: {error}</div>
        </div>
      ) : (
        <div className={`bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all ${
          isLiveMode
            ? 'border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
            : 'border-slate-700'
        }`}>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                {selectedPlate} - {metrics.find((m) => m.value === selectedMetric)?.label}
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                {plateFormat}-well plate ({numRows} rows × {numCols} columns)
              </p>
            </div>
            {/* Color scale legend */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400">Low</span>
              <div
                className="w-24 h-4 rounded"
                style={{
                  background: `linear-gradient(to right, rgb(0, 100, 255), rgb(255, 100, 0))`,
                }}
              ></div>
              <span className="text-slate-400">High</span>
            </div>
          </div>

          {/* Plate grid */}
          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              {/* Column headers */}
              <div className="flex">
                <div className={plateFormat === '384' ? 'w-6' : 'w-10'}></div>
                {Array.from({ length: numCols }, (_, i) => (
                  <div key={i} className={`${plateFormat === '384' ? 'w-6' : 'w-16'} ${wellGap} text-center ${fontSize} text-slate-400 mb-1`}>
                    {/* Show fewer labels for 384-well to reduce crowding */}
                    {plateFormat === '384' ? (i % 4 === 0 || i === 0 ? i + 1 : '') : i + 1}
                  </div>
                ))}
              </div>

              {/* Rows */}
              {heatmapGrid &&
                rowLabels.map((rowLabel, rowIdx) => (
                  <div key={rowLabel} className={`flex items-center ${plateFormat === '384' ? 'mb-0.5' : 'mb-1'}`}>
                    {/* Row label */}
                    <div className={`${plateFormat === '384' ? 'w-6' : 'w-10'} ${fontSize} text-slate-400 text-right pr-2`}>
                      {rowLabel}
                    </div>

                    {/* Wells */}
                    {heatmapGrid[rowIdx].map((value, colIdx) => {
                      const wellId = `${rowLabel}${(colIdx + 1).toString().padStart(2, '0')}`;
                      const isEdge = isEdgeWell(rowIdx, colIdx);

                      return (
                        <div
                          key={colIdx}
                          className={`${wellSize} ${wellGap} rounded border-2 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-violet-500 transition-all group relative`}
                          style={{
                            backgroundColor: getColor(value, min, max),
                            borderColor: isEdge ? '#f59e0b' : '#475569',
                          }}
                          title={`${wellId}: ${value?.toFixed(2) || 'N/A'}`}
                        >
                          {/* Only show well ID on larger wells */}
                          {plateFormat === '96' && (
                            <span className={`${fontSize} font-mono text-white opacity-60 group-hover:opacity-100`}>
                              {wellId}
                            </span>
                          )}
                          {/* Tooltip */}
                          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                            <div className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs whitespace-nowrap">
                              <div className="font-semibold">{wellId}</div>
                              <div className="text-slate-400">
                                {value?.toFixed(2) || 'N/A'}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
            </div>
          </div>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-4 text-xs items-center justify-center">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-orange-500 rounded"></div>
              <span className="text-slate-300">Edge Wells</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-slate-600 rounded"></div>
              <span className="text-slate-300">Center Wells</span>
            </div>
          </div>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Plate heatmaps reveal spatial patterns in measurements.
            <strong className="text-orange-400"> Edge wells</strong> (highlighted in orange) often show
            systematic differences from center wells due to temperature gradients or evaporation - this is
            the "edge effect". Hover over wells to see exact values. Goal: Edge effect {'<'}10%.
          </div>

          {/* Edge Effect Warning */}
          {edgeStats && Math.abs(edgeStats.percentDiff) > 10 && (
            <div className="mt-4 bg-yellow-900/20 border border-yellow-500/50 rounded-lg p-4">
              <div className="text-yellow-300 text-sm">
                ⚠️ <strong>Edge Effect Detected:</strong> Edge wells differ from center by{' '}
                {edgeStats.percentDiff.toFixed(1)}% (threshold: 10%). Consider plate-based normalization or
                avoid using edge wells for critical measurements.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PlateViewerTab;
