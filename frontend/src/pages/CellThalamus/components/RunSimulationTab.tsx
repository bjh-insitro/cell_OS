/**
 * Tab 1: Run Simulation
 *
 * Configure and execute Cell Thalamus Phase 0 simulations
 */

import React, { useState, useEffect } from 'react';
import { useSimulation } from '../hooks/useSimulation';
import { useDesigns } from '../hooks/useCellThalamusData';
import PlateMapPreview from './PlateMapPreview';
import SimulationProgress from './SimulationProgress';

interface RunSimulationTabProps {
  onSimulationComplete: (designId: string) => void;
}

const RunSimulationTab: React.FC<RunSimulationTabProps> = ({ onSimulationComplete }) => {
  const [mode, setMode] = useState<'demo' | 'benchmark' | 'full'>('demo');
  const [cellLines, setCellLines] = useState<string[]>(['A549']);
  const [compounds, setCompounds] = useState<string[]>([]);

  const { runSimulation, design, status, loading, error, isPolling, progress } = useSimulation();
  const { data: designs, loading: loadingDesigns, refetch: refetchDesigns } = useDesigns();

  const availableCellLines = ['A549', 'HepG2', 'U2OS'];
  const availableCompounds = [
    'tBHQ',
    'H2O2',
    'tunicamycin',
    'thapsigargin',
    'CCCP',
    'oligomycin',
    'etoposide',
    'MG132',
    'nocodazole',
    'paclitaxel',
  ];

  // Auto-select all compounds and both cell lines when switching to full mode
  useEffect(() => {
    if (mode === 'full') {
      if (compounds.length === 0) {
        setCompounds(availableCompounds);
      }
      if (cellLines.length < 2) {
        setCellLines(['A549', 'HepG2']);
      }
    }
  }, [mode]);

  const handleRun = async () => {
    await runSimulation({
      cell_lines: cellLines,
      compounds: compounds.length > 0 ? compounds : undefined,
      mode,
    });
  };

  // Watch for completion and auto-navigate
  React.useEffect(() => {
    if (status?.status === 'completed' && design && !isPolling) {
      refetchDesigns();
      onSimulationComplete(design.design_id);
    }
  }, [status, design, isPolling, refetchDesigns, onSimulationComplete]);

  const getModeDescription = (m: string) => {
    switch (m) {
      case 'demo':
        return '8 wells, ~30 seconds - tBHQ dose-response with realistic curve (0.1→100%, 1→90%, 10→70%, 100→20%)';
      case 'benchmark':
        return '96 wells, ~10 seconds - Full 96-well plate (2 cell lines, 10 compounds, 4 doses, 16 DMSO controls)';
      case 'full':
        return '10 compounds, 2 cell lines - Complete Phase 0 campaign (576 total wells)';
      default:
        return '';
    }
  };

  const getWellBreakdown = () => {
    if (mode === 'demo') {
      return {
        total: 8,
        experimental: 5,
        sentinels: 3,
        show: false // Don't show breakdown for demo
      };
    }

    if (mode === 'benchmark') {
      // 1 plate mode: 2 cell lines × (10 compounds × 4 doses + 8 DMSO controls)
      return {
        total: 96,
        experimental: 80,
        sentinels: 16,
        show: true
      };
    }

    // Full mode: use actual selected cell lines and compounds
    const numCellLines = cellLines.length || 2;
    const numCompounds = compounds.length || 10;

    // Experimental wells: cell_lines × compounds × doses × timepoints × plates × days × operators
    const experimental = numCellLines * numCompounds * 4 * 2 * 3 * 2 * 2;

    // Sentinel wells: 8 sentinels per (cell_line × timepoint × plate × day × operator)
    const sentinels = numCellLines * 2 * 3 * 2 * 2 * 8;

    return {
      total: experimental + sentinels,
      experimental,
      sentinels,
      show: true
    };
  };

  const getEstimatedWells = () => {
    return getWellBreakdown().total;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Run Phase 0 Simulation</h2>
        <p className="text-slate-400">
          Configure and execute Cell Thalamus campaigns to validate measurement variance
        </p>
      </div>

      {/* Configuration Card */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-6">
        {/* Mode Selection */}
        <div>
          <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-3">
            Run Mode
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(['demo', 'benchmark', 'full'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                disabled={loading || isPolling}
                className={`
                  p-4 rounded-lg border-2 transition-all text-left
                  ${
                    mode === m
                      ? 'border-violet-500 bg-violet-500/10'
                      : 'border-slate-700 hover:border-slate-600'
                  }
                  ${loading || isPolling ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                `}
              >
                <div className="font-semibold text-white mb-1 capitalize">
                  {m === 'benchmark' ? '1 Plate' : m} Mode
                </div>
                <div className="text-xs text-slate-400">{getModeDescription(m)}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Compounds info (full mode uses all 10 compounds) */}
        {mode === 'full' && (
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Compounds
            </div>
            <div className="text-xs text-slate-400">
              Full mode uses all 10 compounds across 6 stress axes: tBHQ, H₂O₂, tunicamycin, thapsigargin,
              etoposide, CCCP, oligomycin, MG132, nocodazole, paclitaxel
            </div>
          </div>
        )}

        {/* Summary */}
        <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-violet-400">{getEstimatedWells()}</div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Wells</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-violet-400">
                {mode === 'demo' ? 1 : 2}
              </div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Cell Lines</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-violet-400">
                {mode === 'demo' ? '1' : 10}
              </div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">
                {mode === 'demo' ? 'Compound (tBHQ)' : 'Compounds'}
              </div>
            </div>
            <div>
              <div className="text-2xl font-bold text-violet-400">
                {mode === 'demo' ? '~30s' : mode === 'benchmark' ? '~5min' : '~1.5h'}
              </div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Duration</div>
            </div>
          </div>

          {/* Well Calculation Breakdown */}
          {getWellBreakdown().show && (
            <div className="mt-3 pt-3 border-t border-slate-700">
              <div className="text-xs text-slate-400 space-y-1">
                {mode === 'benchmark' ? (
                  <>
                    <div className="flex justify-between">
                      <span>Experimental wells:</span>
                      <span className="font-mono text-slate-300">
                        2 cell lines × 10 compounds × 4 doses = {getWellBreakdown().experimental}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>DMSO sentinel wells (QC):</span>
                      <span className="font-mono text-slate-300">
                        8 DMSO/cell line × 2 cell lines = {getWellBreakdown().sentinels}
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex justify-between">
                      <span>Experimental wells:</span>
                      <span className="font-mono text-slate-300">
                        2 cell lines × 10 compounds × 4 doses × 2 timepoints × 3 plates × 2 days × 2 operators = {getWellBreakdown().experimental}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Sentinel wells (QC):</span>
                      <span className="font-mono text-slate-300">
                        2 cell lines × 2 timepoints × 3 plates × 2 days × 2 operators × 8 sentinels/plate = {getWellBreakdown().sentinels}
                      </span>
                    </div>
                  </>
                )}
                <div className="flex justify-between pt-1 border-t border-slate-700/50 font-semibold">
                  <span>Total:</span>
                  <span className="font-mono text-violet-400">{getWellBreakdown().total} wells</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Run Button */}
        <button
          onClick={handleRun}
          disabled={loading || isPolling || cellLines.length === 0}
          className={`
            w-full py-4 rounded-lg font-bold text-lg transition-all
            ${
              loading || isPolling || cellLines.length === 0
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-violet-600 hover:bg-violet-500 text-white shadow-lg hover:shadow-violet-500/25 transform hover:scale-[1.02] active:scale-[0.98]'
            }
          `}
        >
          {loading
            ? 'Starting Simulation...'
            : isPolling
            ? 'Simulation Running...'
            : 'Run Campaign'}
        </button>

        {/* Status Messages */}
        {design && (
          <div className="bg-blue-900/30 border border-blue-500/50 rounded-lg p-4">
            <div className="text-sm text-blue-300">
              <strong>Design ID:</strong> {design.design_id.slice(0, 8)}...
            </div>
            {isPolling && (
              <div className="text-xs text-blue-400 mt-2 flex items-center gap-2">
                <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full"></div>
                Simulation in progress...
              </div>
            )}
          </div>
        )}

        {status?.status === 'completed' && (
          <div className="bg-green-900/30 border border-green-500/50 rounded-lg p-4">
            <div className="text-sm text-green-300">
              ✓ Simulation completed successfully! Navigate to other tabs to explore results.
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4">
            <div className="text-sm text-red-300">
              <strong>Error:</strong> {error}
            </div>
          </div>
        )}
      </div>

      {/* Live Progress Visualization */}
      {isPolling && progress && (
        <SimulationProgress progress={progress} mode={mode} />
      )}

      {/* Plate Map Preview */}
      {!isPolling && <PlateMapPreview cellLines={cellLines} compounds={compounds} mode={mode} />}

      {/* Recent Designs */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Designs</h3>
        {loadingDesigns ? (
          <div className="text-slate-400 text-sm">Loading designs...</div>
        ) : designs && designs.length > 0 ? (
          <div className="space-y-2">
            {designs.slice(0, 5).map((d) => (
              <div
                key={d.design_id}
                className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-700"
              >
                <div className="flex-1">
                  <div className="text-sm font-mono text-slate-300">
                    {d.design_id.slice(0, 8)}...
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {d.cell_lines.join(', ')} • {d.compounds.length} compounds
                  </div>
                </div>
                <div
                  className={`
                    px-3 py-1 rounded-full text-xs font-semibold
                    ${
                      d.status === 'completed'
                        ? 'bg-green-500/20 text-green-400'
                        : d.status === 'failed'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                    }
                  `}
                >
                  {d.status}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-slate-400 text-sm">No designs yet. Run your first simulation!</div>
        )}
      </div>
    </div>
  );
};

export default RunSimulationTab;
