/**
 * Tab 1: Run Simulation
 *
 * Configure and execute Cell Thalamus Phase 0 simulations
 */

import React, { useState, useEffect } from 'react';
import { useSimulation } from '../hooks/useSimulation';
import { useDesigns } from '../hooks/useCellThalamusData';
import PlateMapPreview from './PlateMapPreview';

interface RunSimulationTabProps {
  onSimulationComplete: (designId: string) => void;
}

const RunSimulationTab: React.FC<RunSimulationTabProps> = ({ onSimulationComplete }) => {
  const [mode, setMode] = useState<'demo' | 'quick' | 'full' | 'custom'>('demo');
  const [cellLines, setCellLines] = useState<string[]>(['A549']);
  const [compounds, setCompounds] = useState<string[]>([]);

  const { runSimulation, design, status, loading, error, isPolling } = useSimulation();
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

  // Auto-select all compounds when switching to full mode
  useEffect(() => {
    if (mode === 'full' && compounds.length === 0) {
      setCompounds(availableCompounds);
    }
  }, [mode]);

  const handleRun = async () => {
    await runSimulation({
      cell_lines: cellLines,
      compounds: compounds.length > 0 ? compounds : undefined,
      mode,
    });

    if (status?.status === 'completed' && design) {
      refetchDesigns();
      onSimulationComplete(design.design_id);
    }
  };

  const getModeDescription = (m: string) => {
    switch (m) {
      case 'demo':
        return '7 wells, ~30 seconds - Fast test for UI exploration';
      case 'quick':
        return '3 compounds, ~20 minutes - Quick validation';
      case 'full':
        return '10 compounds, full panel - Complete Phase 0 campaign';
      case 'custom':
        return 'User-selected compounds - Flexible custom design';
      default:
        return '';
    }
  };

  const getEstimatedWells = () => {
    if (mode === 'demo') return 7;
    if (mode === 'quick') return 480;
    if (mode === 'custom') {
      const numCompounds = compounds.length || 0;
      if (numCompounds === 0) return 0;
      return cellLines.length * numCompounds * 4 * 2 * 3 * 2 * 2; // doses × timepoints × plates × days × operators
    }
    const numCompounds = compounds.length || 10;
    return cellLines.length * numCompounds * 4 * 2 * 3 * 2 * 2; // doses × timepoints × plates × days × operators
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {(['demo', 'quick', 'full', 'custom'] as const).map((m) => (
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
                <div className="font-semibold text-white mb-1 capitalize">{m} Mode</div>
                <div className="text-xs text-slate-400">{getModeDescription(m)}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Cell Lines */}
        <div>
          <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-3">
            Cell Lines
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {availableCellLines.map((line) => (
              <label
                key={line}
                className={`
                  flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-all
                  ${
                    cellLines.includes(line)
                      ? 'border-violet-500 bg-violet-500/10'
                      : 'border-slate-700 hover:border-slate-600'
                  }
                  ${loading || isPolling ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                <input
                  type="checkbox"
                  checked={cellLines.includes(line)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setCellLines([...cellLines, line]);
                    } else {
                      setCellLines(cellLines.filter((l) => l !== line));
                    }
                  }}
                  disabled={loading || isPolling}
                  className="rounded text-violet-500 focus:ring-violet-500"
                />
                <span className="text-sm">{line}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Compounds (for full and custom modes) */}
        {(mode === 'full' || mode === 'custom') && (
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-3">
              Compounds (optional - defaults to all 10)
            </label>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {availableCompounds.map((compound) => (
                <label
                  key={compound}
                  className={`
                    flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all text-xs
                    ${
                      compounds.includes(compound)
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-slate-700 hover:border-slate-600'
                    }
                    ${loading || isPolling ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  <input
                    type="checkbox"
                    checked={compounds.includes(compound)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCompounds([...compounds, compound]);
                      } else {
                        setCompounds(compounds.filter((c) => c !== compound));
                      }
                    }}
                    disabled={loading || isPolling}
                    className="rounded text-violet-500 focus:ring-violet-500"
                  />
                  <span>{compound}</span>
                </label>
              ))}
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
              <div className="text-2xl font-bold text-violet-400">{cellLines.length}</div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Cell Lines</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-violet-400">
                {mode === 'demo' ? 2 : mode === 'quick' ? 3 : compounds.length || 10}
              </div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Compounds</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-violet-400">
                {mode === 'demo' ? '~30s' : mode === 'quick' ? '~20m' : '~1h'}
              </div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Duration</div>
            </div>
          </div>
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

      {/* Plate Map Preview */}
      <PlateMapPreview cellLines={cellLines} compounds={compounds} mode={mode} />

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
