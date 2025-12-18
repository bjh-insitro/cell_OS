/**
 * Simulation Progress Component
 *
 * Shows live progress of a running simulation with visual plate map
 */

import React from 'react';

interface SimulationProgressProps {
  progress: {
    completed: number;
    total: number;
    percentage: number;
    last_well: string | null;
    completed_wells?: string[];
  };
  mode: 'demo' | 'benchmark' | 'full';
}

const SimulationProgress: React.FC<SimulationProgressProps> = ({ progress, mode }) => {
  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
  const cols = 12;

  // Extract plate info from last completed well if available
  const currentPlateInfo = React.useMemo(() => {
    if (!progress.completed_wells || progress.completed_wells.length === 0) {
      return null;
    }

    // Get last completed well and try to determine plate from context
    // In full mode, wells cycle through multiple physical plates
    const totalPlates = mode === 'full' ? 24 : mode === 'benchmark' ? 1 : 1;
    const completedCount = progress.completed;
    const wellsPerPlate = 96;

    // Calculate which physical plate we're on (approximate)
    const currentPlateIndex = Math.floor(completedCount / wellsPerPlate);
    const currentPlateNumber = (currentPlateIndex % totalPlates) + 1;

    return {
      plateNumber: currentPlateNumber,
      totalPlates: totalPlates,
      wellsOnCurrentPlate: completedCount % wellsPerPlate
    };
  }, [progress.completed_wells, progress.completed, mode]);

  // Parse well ID (e.g., "A01" -> row: 0, col: 0)
  const parseWellId = (wellId: string | null): { row: number; col: number } | null => {
    if (!wellId || wellId.length < 2) return null;
    const row = rows.indexOf(wellId[0]);
    const col = parseInt(wellId.substring(1)) - 1;
    if (row === -1 || isNaN(col)) return null;
    return { row, col };
  };

  // Build a set of completed well IDs from the backend list
  const completedWellIds = React.useMemo(() => {
    const completed = new Set<string>();

    // Use the completed_wells list from backend if available
    if (progress.completed_wells && progress.completed_wells.length > 0) {
      progress.completed_wells.forEach((wellId) => completed.add(wellId));
    }

    return completed;
  }, [progress.completed_wells]);

  // Calculate which wells should be highlighted as complete
  const isWellComplete = (row: number, col: number): boolean => {
    const wellId = `${rows[row]}${(col + 1).toString().padStart(2, '0')}`;

    if (mode === 'demo') {
      // Demo mode: only 8 wells (A01-A08)
      if (row > 0) return false;
      if (col >= 8) return false;
      return completedWellIds.has(wellId);
    } else if (mode === 'benchmark' || mode === 'full') {
      // Use the completed wells list from backend
      return completedWellIds.has(wellId);
    }

    // Fallback
    return false;
  };

  // Determine well color
  const getWellStyle = (row: number, col: number) => {
    const complete = isWellComplete(row, col);
    const isEmpty = mode === 'demo' && (row > 0 || col >= 8);

    if (isEmpty) {
      return {
        backgroundColor: '#0f172a', // slate-900
        border: '1px solid #334155', // slate-700
      };
    }

    if (complete) {
      return {
        backgroundColor: '#22c55e', // green-500
        border: '2px solid #16a34a', // green-600
        boxShadow: '0 0 10px rgba(34, 197, 94, 0.5)',
      };
    }

    return {
      backgroundColor: '#1e293b', // slate-800
      border: '2px solid #475569', // slate-600
    };
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
      {/* Progress Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <div className="animate-spin h-5 w-5 border-3 border-violet-500 border-t-transparent rounded-full"></div>
            Simulation Running
          </h3>
          <p className="text-sm text-slate-400 mt-1">
            Processing wells in real-time
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-violet-400">{progress.percentage}%</div>
          <div className="text-sm text-slate-400">
            {progress.completed} / {progress.total} wells
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-6">
        <div className="w-full h-4 bg-slate-900 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-green-500 transition-all duration-300 ease-out"
            style={{ width: `${progress.percentage}%` }}
          ></div>
        </div>
      </div>

      {/* Live Plate Map */}
      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-violet-400">
            Live Plate Progress
            {progress.last_well && (
              <span className="text-green-400 ml-2">
                → Last: {progress.last_well}
              </span>
            )}
          </div>
          {mode === 'full' && currentPlateInfo && (
            <div className="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
              Processing across <span className="text-violet-400 font-semibold">{currentPlateInfo.totalPlates} plates</span>
              {' '}(~Plate {currentPlateInfo.plateNumber})
            </div>
          )}
        </div>

        <div className="inline-block">
          {/* Column headers */}
          <div className="flex mb-1">
            <div className="w-6"></div>
            {Array.from({ length: cols }, (_, i) => (
              <div key={i} className="w-8 mr-0.5 text-center text-[10px] text-slate-400">
                {i + 1}
              </div>
            ))}
          </div>

          {/* Rows */}
          {rows.map((rowLabel, rowIdx) => (
            <div key={rowIdx} className="flex items-center mb-1">
              {/* Row label */}
              <div className="w-6 text-[10px] text-slate-400 text-right pr-1">
                {rowLabel}
              </div>

              {/* Wells */}
              {Array.from({ length: cols }, (_, colIdx) => {
                const wellStyle = getWellStyle(rowIdx, colIdx);
                const isEmpty = mode === 'demo' && (rowIdx > 0 || colIdx >= 8);

                return (
                  <div
                    key={colIdx}
                    className="w-8 h-8 mr-0.5 rounded transition-all duration-200"
                    style={wellStyle}
                    title={
                      isEmpty
                        ? 'Empty'
                        : `${rowLabel}${(colIdx + 1).toString().padStart(2, '0')}`
                    }
                  ></div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-4 flex gap-6 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <div
              className="w-4 h-4 rounded"
              style={{
                backgroundColor: '#1e293b',
                border: '2px solid #475569',
              }}
            ></div>
            <span>Pending</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="w-4 h-4 rounded"
              style={{
                backgroundColor: '#22c55e',
                border: '2px solid #16a34a',
              }}
            ></div>
            <span>Completed</span>
          </div>
        </div>

        {/* Multi-Plate Progress Indicator for Full Mode */}
        {mode === 'full' && (
          <div className="mt-4 pt-4 border-t border-slate-700">
            <div className="text-xs font-semibold text-slate-400 mb-2">
              Progress Across All {currentPlateInfo?.totalPlates || 24} Physical Plates
            </div>
            <div className="grid grid-cols-12 gap-1">
              {Array.from({ length: 24 }, (_, i) => {
                const plateStart = i * 96;
                const plateEnd = (i + 1) * 96;
                const completedInPlate = Math.max(0, Math.min(96, progress.completed - plateStart));
                const percentage = Math.round((completedInPlate / 96) * 100);
                const isActive = progress.completed >= plateStart && progress.completed < plateEnd;

                return (
                  <div
                    key={i}
                    className={`h-12 rounded flex flex-col items-center justify-center text-[10px] transition-all ${
                      isActive ? 'ring-2 ring-violet-500' : ''
                    }`}
                    style={{
                      backgroundColor: percentage > 0 ? '#22c55e' : '#1e293b',
                      opacity: percentage === 0 ? 0.3 : 0.5 + (percentage / 100) * 0.5,
                      border: '1px solid #475569'
                    }}
                    title={`Plate ${i + 1}: ${percentage}% complete`}
                  >
                    <div className="text-slate-300 font-semibold">{i + 1}</div>
                    {percentage > 0 && (
                      <div className="text-green-300">{percentage}%</div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="text-[10px] text-slate-500 mt-2 text-center">
              Each box represents one physical 96-well plate • Green = completed wells on that plate
            </div>
          </div>
        )}
      </div>

      {/* Status Message */}
      <div className="mt-4 bg-blue-900/30 border border-blue-500/50 rounded-lg p-3">
        <div className="text-sm text-blue-300 flex items-center gap-2">
          <div className="animate-pulse">⚡</div>
          <span>
            {progress.percentage < 25
              ? 'Initializing experiment...'
              : progress.percentage < 50
              ? 'Processing samples...'
              : progress.percentage < 75
              ? 'Analyzing measurements...'
              : progress.percentage < 100
              ? 'Finalizing results...'
              : 'Complete!'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default SimulationProgress;
