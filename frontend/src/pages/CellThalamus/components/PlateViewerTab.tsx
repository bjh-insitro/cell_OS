/**
 * Tab 6: Plate Viewer
 *
 * 96-well plate heatmaps with spatial visualization
 */

import React, { useState, useMemo } from 'react';
import { useDesigns, usePlateData, useResults } from '../hooks/useCellThalamusData';

interface PlateViewerTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const PlateViewerTab: React.FC<PlateViewerTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: results } = useResults(selectedDesignId);

  const [selectedPlate, setSelectedPlate] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>('atp_signal');

  const { data: plateData, loading, error } = usePlateData(selectedDesignId, selectedPlate);

  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  // Extract unique plate IDs
  const plateIds = Array.from(new Set(results?.map((r) => r.plate_id) || [])).sort();

  const metrics = [
    { value: 'atp_signal', label: 'ATP Viability' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
  ];

  // Parse well ID to row/col
  const parseWellId = (wellId: string) => {
    const row = wellId.charCodeAt(0) - 65; // A=0, B=1, ...
    const col = parseInt(wellId.substring(1)) - 1;
    return { row, col };
  };

  // Create 96-well grid (8 rows × 12 cols)
  const heatmapGrid = useMemo(() => {
    if (!plateData) return null;

    const grid: (number | null)[][] = Array(8)
      .fill(null)
      .map(() => Array(12).fill(null));

    plateData.forEach((well) => {
      const { row, col } = parseWellId(well.well_id);
      const value = (well as any)[selectedMetric];
      if (row >= 0 && row < 8 && col >= 0 && col < 12) {
        grid[row][col] = value;
      }
    });

    return grid;
  }, [plateData, selectedMetric]);

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

  // Check if well is on edge
  const isEdgeWell = (row: number, col: number) => {
    return row === 0 || row === 7 || col === 0 || col === 11;
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

  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Plate Viewer</h2>
        <p className="text-slate-400">
          96-well plate heatmaps with spatial visualization and edge effect analysis
        </p>
      </div>

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
              {completedDesigns.map((design) => (
                <option key={design.design_id} value={design.design_id}>
                  {design.design_id.slice(0, 8)}...
                </option>
              ))}
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
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">
                {selectedPlate} - {metrics.find((m) => m.value === selectedMetric)?.label}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                96-well plate (8 rows × 12 columns)
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

          {/* 96-well grid */}
          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              {/* Column headers */}
              <div className="flex">
                <div className="w-10"></div>
                {Array.from({ length: 12 }, (_, i) => (
                  <div key={i} className="w-16 text-center text-xs text-slate-400 mb-1">
                    {i + 1}
                  </div>
                ))}
              </div>

              {/* Rows */}
              {heatmapGrid &&
                rows.map((rowLabel, rowIdx) => (
                  <div key={rowLabel} className="flex items-center mb-1">
                    {/* Row label */}
                    <div className="w-10 text-xs text-slate-400 text-right pr-2">
                      {rowLabel}
                    </div>

                    {/* Wells */}
                    {heatmapGrid[rowIdx].map((value, colIdx) => {
                      const wellId = `${rowLabel}${(colIdx + 1).toString().padStart(2, '0')}`;
                      const isEdge = isEdgeWell(rowIdx, colIdx);

                      return (
                        <div
                          key={colIdx}
                          className="w-16 h-14 mr-1 rounded border-2 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-violet-500 transition-all group relative"
                          style={{
                            backgroundColor: getColor(value, min, max),
                            borderColor: isEdge ? '#f59e0b' : '#475569',
                          }}
                          title={`${wellId}: ${value?.toFixed(2) || 'N/A'}`}
                        >
                          <span className="text-xs font-mono text-white opacity-60 group-hover:opacity-100">
                            {wellId}
                          </span>
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
