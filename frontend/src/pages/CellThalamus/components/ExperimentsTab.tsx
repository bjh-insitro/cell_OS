/**
 * Experiments Tab - View all Cell Thalamus designs
 *
 * Shows a comprehensive list of all experimental designs with metadata
 */

import React from 'react';
import { useDesigns } from '../hooks/useCellThalamusData';

interface ExperimentsTabProps {
  onSelectDesign?: (designId: string) => void;
  selectedDesignId?: string;
}

const ExperimentsTab: React.FC<ExperimentsTabProps> = ({ onSelectDesign, selectedDesignId }) => {
  const { data: designs, loading, error, refetch } = useDesigns();

  const getModeFromMetadata = (design: any): string => {
    try {
      // Try to parse metadata to get mode
      if (design.metadata) {
        const metadata = typeof design.metadata === 'string'
          ? JSON.parse(design.metadata)
          : design.metadata;
        if (metadata.mode) return metadata.mode;
      }
    } catch (e) {
      // Continue to fallback
    }

    // Fallback: intelligently guess mode from compounds and cell lines
    try {
      const compounds = Array.isArray(design.compounds)
        ? design.compounds
        : JSON.parse(design.compounds || '[]');

      const cellLines = Array.isArray(design.cell_lines)
        ? design.cell_lines
        : JSON.parse(design.cell_lines || '[]');

      // Demo: 1-2 compounds (usually tBHQ or tBHQ+tunicamycin), 1 cell line, <20 wells
      if (compounds.length <= 2 && cellLines.length === 1) {
        return 'demo';
      }

      // Benchmark: 3-4 compounds, 2 cell lines, ~96 wells
      if (compounds.length >= 3 && compounds.length <= 5 && cellLines.length === 2) {
        return 'benchmark';
      }

      // Full: 10 compounds, 2 cell lines, 2000+ wells
      if (compounds.length >= 8 && cellLines.length >= 2) {
        return 'full';
      }

      // If still unclear, use compound count as primary signal
      if (compounds.length <= 2) return 'demo';
      if (compounds.length <= 5) return 'benchmark';
      return 'full';
    } catch (e) {
      return 'legacy';  // Instead of "unknown", call it "legacy" (pre-mode tracking)
    }
  };

  const getWellCount = (design: any): string => {
    const mode = getModeFromMetadata(design);
    const cellLines = Array.isArray(design.cell_lines)
      ? design.cell_lines
      : JSON.parse(design.cell_lines || '[]');
    const compounds = Array.isArray(design.compounds)
      ? design.compounds
      : JSON.parse(design.compounds || '[]');

    if (mode === 'demo') return '8 wells';
    if (mode === 'benchmark') return '96 wells';

    // Legacy or Full mode: calculate based on actual configuration
    const numCellLines = cellLines.length || 2;
    const numCompounds = compounds.length || 10;

    // If it looks like demo/benchmark based on counts, return those
    if (numCompounds <= 2 && numCellLines === 1) return '~8 wells';
    if (numCompounds <= 5 && numCellLines === 2) return '~96 wells';

    // Full mode calculation
    const experimental = numCellLines * numCompounds * 4 * 2 * 3 * 2 * 2;
    const sentinels = numCellLines * 2 * 3 * 2 * 2 * 8;
    return `${experimental + sentinels} wells`;
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch (e) {
      return dateString;
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Experimental Designs</h2>
          <p className="text-slate-400">View all Cell Thalamus experimental runs</p>
        </div>
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
          <div className="text-slate-400 text-sm">Loading designs...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Experimental Designs</h2>
          <p className="text-slate-400">View all Cell Thalamus experimental runs</p>
        </div>
        <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6">
          <div className="text-sm text-red-300">
            <strong>Error:</strong> {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Experimental Designs</h2>
          <p className="text-slate-400">
            {designs?.length || 0} total runs • Browse and compare Cell Thalamus campaigns
          </p>
        </div>
        <button
          onClick={refetch}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-slate-700 hover:bg-slate-600 text-slate-300 transition-all"
        >
          <svg className="w-4 h-4 inline-block mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Designs List */}
      {designs && designs.length > 0 ? (
        <div className="grid gap-4">
          {designs.map((design) => {
            const cellLines = Array.isArray(design.cell_lines)
              ? design.cell_lines
              : JSON.parse(design.cell_lines || '[]');
            const compounds = Array.isArray(design.compounds)
              ? design.compounds
              : JSON.parse(design.compounds || '[]');
            const mode = getModeFromMetadata(design);
            const wellCount = getWellCount(design);
            const isSelected = design.design_id === selectedDesignId;

            return (
              <div
                key={design.design_id}
                onClick={() => onSelectDesign?.(design.design_id)}
                className={`
                  bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all
                  ${isSelected
                    ? 'border-violet-500 ring-2 ring-violet-500/20'
                    : 'border-slate-700 hover:border-slate-600'
                  }
                  ${onSelectDesign ? 'cursor-pointer' : ''}
                `}
              >
                <div className="flex items-start justify-between mb-4">
                  {/* Left: Design Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white font-mono">
                        {design.design_id.slice(0, 8)}...
                      </h3>
                      <span className={`
                        px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider
                        ${mode === 'demo'
                          ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                          : mode === 'benchmark'
                          ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                          : mode === 'legacy'
                          ? 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                          : 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                        }
                      `}>
                        {mode === 'benchmark' ? '1 Plate' : mode}
                      </span>
                      <span className={`
                        px-3 py-1 rounded-full text-xs font-semibold
                        ${design.status === 'completed'
                          ? 'bg-green-500/20 text-green-400'
                          : design.status === 'failed'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                        }
                      `}>
                        {design.status}
                      </span>
                    </div>

                    {/* Timestamp */}
                    {design.created_at && (
                      <div className="text-xs text-slate-500 mb-3">
                        <svg className="w-4 h-4 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {formatDate(design.created_at)}
                      </div>
                    )}

                    {/* Details Grid */}
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-slate-500 text-xs uppercase tracking-wider mb-1">Wells</div>
                        <div className="text-white font-semibold">{wellCount}</div>
                      </div>
                      <div>
                        <div className="text-slate-500 text-xs uppercase tracking-wider mb-1">Cell Lines</div>
                        <div className="text-white font-semibold">{cellLines.length}</div>
                        <div className="text-slate-400 text-xs mt-1">{cellLines.join(', ')}</div>
                      </div>
                      <div>
                        <div className="text-slate-500 text-xs uppercase tracking-wider mb-1">Compounds</div>
                        <div className="text-white font-semibold">{compounds.length}</div>
                        <div className="text-slate-400 text-xs mt-1">
                          {compounds.length <= 3
                            ? compounds.join(', ')
                            : `${compounds.slice(0, 2).join(', ')}, +${compounds.length - 2} more`
                          }
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  {onSelectDesign && (
                    <div className="ml-4">
                      <svg
                        className={`w-6 h-6 transition-colors ${isSelected ? 'text-violet-400' : 'text-slate-600'}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  )}
                </div>

                {/* Phase Info */}
                <div className="pt-3 border-t border-slate-700">
                  <div className="text-xs text-slate-500">
                    Phase {design.phase} • {
                      mode === 'demo' ? 'Rapid demo' :
                      mode === 'benchmark' ? 'Single plate benchmark' :
                      mode === 'legacy' ? 'Custom configuration (pre-mode tracking)' :
                      'Full campaign with variance analysis'
                    }
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <svg className="w-16 h-16 text-slate-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div className="text-slate-400 text-lg font-semibold mb-2">No Experiments Yet</div>
          <div className="text-slate-500 text-sm">
            Run your first simulation to see experimental designs here
          </div>
        </div>
      )}
    </div>
  );
};

export default ExperimentsTab;
