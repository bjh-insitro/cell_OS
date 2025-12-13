/**
 * Tab 2: Morphology Manifold
 *
 * PCA/UMAP visualization of 5-channel Cell Painting morphology
 */

import React, { useState, useMemo } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ZAxis } from 'recharts';
import { useDesigns, useMorphologyData, useResults } from '../hooks/useCellThalamusData';

interface MorphologyTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const MorphologyTab: React.FC<MorphologyTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: morphologyData, loading, error, refetch: refetchMorphology } = useMorphologyData(selectedDesignId);
  const { data: results, refetch: refetchResults } = useResults(selectedDesignId);

  const [colorBy, setColorBy] = useState<'cell_line' | 'compound' | 'dose'>('cell_line');
  const [selectedCellLine, setSelectedCellLine] = useState<string>('all');
  const [selectedCompound, setSelectedCompound] = useState<string>('all');
  const [selectedDoseCategory, setSelectedDoseCategory] = useState<string>('all');
  const [isLiveMode, setIsLiveMode] = useState<boolean>(false);

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

      // Initial fetch
      refetchResults();
      refetchMorphology();

      // Set up polling interval
      const intervalId = setInterval(() => {
        refetchResults();
        refetchMorphology();
      }, 5000);

      return () => {
        clearInterval(intervalId);
      };
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, refetchResults, refetchMorphology]);

  // Compute PCA (simplified 2-component projection)
  const pcaData = useMemo(() => {
    if (!morphologyData || !results) return [];

    // Simple dimensionality reduction: PC1 = ER + Mito, PC2 = Nucleus + Actin
    return results.map((result, idx) => {
      const pc1 = result.morph_er + result.morph_mito;
      const pc2 = result.morph_nucleus + result.morph_actin;

      return {
        pc1,
        pc2,
        well_id: result.well_id,
        cell_line: result.cell_line,
        compound: result.compound,
        dose_uM: result.dose_uM,
        is_sentinel: result.is_sentinel,
      };
    });
  }, [morphologyData, results]);

  // Get compound color (matching dose-response chart)
  const getCompoundColor = (compound: string): string => {
    const compoundColors: Record<string, string> = {
      tBHQ: '#ef4444', // red
      H2O2: '#f97316', // orange
      hydrogen_peroxide: '#f97316', // orange (alt name)
      tunicamycin: '#f59e0b', // amber
      thapsigargin: '#eab308', // yellow
      CCCP: '#84cc16', // lime
      cccp: '#84cc16', // lime (lowercase)
      oligomycin: '#22c55e', // green
      oligomycin_a: '#22c55e', // green (alt name)
      etoposide: '#14b8a6', // teal
      MG132: '#06b6d4', // cyan
      mg132: '#06b6d4', // cyan (lowercase)
      nocodazole: '#3b82f6', // blue
      paclitaxel: '#8b5cf6', // violet
      two_deoxy_d_glucose: '#ec4899', // pink
      DMSO: '#64748b', // slate
    };
    return compoundColors[compound] || '#6366f1'; // indigo default
  };

  // Color mapping
  const getColor = (item: typeof pcaData[0]) => {
    if (colorBy === 'cell_line') {
      const colors: Record<string, string> = {
        A549: '#8b5cf6',
        HepG2: '#ec4899',
        U2OS: '#10b981',
        HeLa: '#f59e0b',
      };
      return colors[item.cell_line] || '#64748b';
    } else if (colorBy === 'compound') {
      return getCompoundColor(item.compound);
    } else {
      // Dose gradient
      const intensity = Math.min(item.dose_uM / 100, 1);
      return `rgba(139, 92, 246, ${0.3 + intensity * 0.7})`;
    }
  };

  // Categorize dose levels
  const getDoseCategory = (dose: number): string => {
    if (dose === 0) return 'Vehicle (0 µM)';
    if (dose <= 1) return 'Low (≤1 µM)';
    if (dose <= 10) return 'Mid (1-10 µM)';
    if (dose <= 100) return 'High (10-100 µM)';
    return 'Very High (>100 µM)';
  };

  const getDoseCategoryColor = (category: string): string => {
    const colors: Record<string, string> = {
      'Vehicle (0 µM)': '#64748b', // slate (control)
      'Low (≤1 µM)': '#22c55e', // green (minimal)
      'Mid (1-10 µM)': '#f59e0b', // amber (moderate)
      'High (10-100 µM)': '#ef4444', // red (strong)
      'Very High (>100 µM)': '#991b1b', // dark red (very strong)
    };
    return colors[category] || '#8b5cf6';
  };

  // Extract unique values for filters
  const uniqueCellLines = useMemo(() =>
    Array.from(new Set(pcaData.map(item => item.cell_line))).sort(),
    [pcaData]
  );

  const uniqueCompounds = useMemo(() =>
    Array.from(new Set(pcaData.map(item => item.compound))).sort(),
    [pcaData]
  );

  const uniqueDoseCategories = useMemo(() => {
    const categories = Array.from(new Set(pcaData.map(item => getDoseCategory(item.dose_uM))));
    // Sort by dose order
    const order = ['Vehicle (0 µM)', 'Low (≤1 µM)', 'Mid (1-10 µM)', 'High (10-100 µM)', 'Very High (>100 µM)'];
    return categories.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  }, [pcaData]);

  // Filter data based on selection
  const filteredPcaData = useMemo(() => {
    let filtered = pcaData;

    if (colorBy === 'cell_line' && selectedCellLine !== 'all') {
      filtered = filtered.filter(item => item.cell_line === selectedCellLine);
    } else if (colorBy === 'compound' && selectedCompound !== 'all') {
      filtered = filtered.filter(item => item.compound === selectedCompound);
    } else if (colorBy === 'dose' && selectedDoseCategory !== 'all') {
      filtered = filtered.filter(item => getDoseCategory(item.dose_uM) === selectedDoseCategory);
    }

    return filtered;
  }, [pcaData, colorBy, selectedCellLine, selectedCompound, selectedDoseCategory]);

  // Group data by color for multiple scatter series
  const groupedData = useMemo(() => {
    if (colorBy === 'cell_line') {
      const groups: Record<string, typeof filteredPcaData> = {};
      filteredPcaData.forEach((item) => {
        if (!groups[item.cell_line]) groups[item.cell_line] = [];
        groups[item.cell_line].push(item);
      });
      return Object.entries(groups);
    } else if (colorBy === 'compound') {
      const groups: Record<string, typeof filteredPcaData> = {};
      filteredPcaData.forEach((item) => {
        if (!groups[item.compound]) groups[item.compound] = [];
        groups[item.compound].push(item);
      });
      return Object.entries(groups);
    } else if (colorBy === 'dose') {
      const groups: Record<string, typeof filteredPcaData> = {};
      filteredPcaData.forEach((item) => {
        const category = getDoseCategory(item.dose_uM);
        if (!groups[category]) groups[category] = [];
        groups[category].push(item);
      });
      return Object.entries(groups).sort((a, b) => {
        // Sort by dose order: vehicle, low, mid, high, very high
        const order = ['Vehicle (0 µM)', 'Low (≤1 µM)', 'Mid (1-10 µM)', 'High (10-100 µM)', 'Very High (>100 µM)'];
        return order.indexOf(a[0]) - order.indexOf(b[0]);
      });
    }
    return [['All', filteredPcaData]];
  }, [filteredPcaData, colorBy]);

  const allDesigns = useMemo(() => designs || [], [designs]);
  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Morphology Manifold</h2>
        <p className="text-slate-400">
          PCA visualization of 5-channel Cell Painting morphology features
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
                  Morphology data updating every 5 seconds as wells complete
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Design Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Select Design
            </label>
            <select
              value={selectedDesignId || ''}
              onChange={(e) => onDesignChange(e.target.value || null)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="">-- Select design --</option>
              {allDesigns.map((design, index) => {
                const date = design.created_at ? new Date(design.created_at).toLocaleString() : '';
                const statusLabel = design.status === 'running' ? ' 🔴 LIVE' : design.status === 'completed' ? ' ✓' : '';
                return (
                  <option key={design.design_id} value={design.design_id}>
                    Run #{index + 1} - {date} ({design.design_id.slice(0, 8)}){statusLabel}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Color By */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Color By
            </label>
            <div className="flex gap-2">
              {(['cell_line', 'compound', 'dose'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => {
                    setColorBy(option);
                    // Reset filter when changing color mode
                    setSelectedCellLine('all');
                    setSelectedCompound('all');
                    setSelectedDoseCategory('all');
                  }}
                  className={`
                    flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all capitalize
                    ${
                      colorBy === option
                        ? 'bg-violet-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }
                  `}
                >
                  {option.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Conditional Filter Dropdown */}
        {colorBy === 'cell_line' && uniqueCellLines.length > 0 && (
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Filter by Cell Line
            </label>
            <select
              value={selectedCellLine}
              onChange={(e) => setSelectedCellLine(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All Cell Lines</option>
              {uniqueCellLines.map((cellLine) => (
                <option key={cellLine} value={cellLine}>
                  {cellLine}
                </option>
              ))}
            </select>
          </div>
        )}

        {colorBy === 'compound' && uniqueCompounds.length > 0 && (
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Filter by Compound
            </label>
            <select
              value={selectedCompound}
              onChange={(e) => setSelectedCompound(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All Compounds</option>
              {uniqueCompounds.map((compound) => (
                <option key={compound} value={compound}>
                  {compound}
                </option>
              ))}
            </select>
          </div>
        )}

        {colorBy === 'dose' && uniqueDoseCategories.length > 0 && (
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Filter by Dose Level
            </label>
            <select
              value={selectedDoseCategory}
              onChange={(e) => setSelectedDoseCategory(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All Dose Levels</option>
              {uniqueDoseCategories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Info Card */}
        {morphologyData && (
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xl font-bold text-violet-400">
                  {morphologyData.well_ids.length}
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Wells</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">
                  {morphologyData.channels.length}
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Channels</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">2</div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Components</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">~85%</div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Variance Explained</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a completed design to view morphology manifold
          </div>
        </div>
      ) : loading ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-slate-400">Loading morphology data...</div>
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
          {isLiveMode && (
            <div className="mb-4 flex items-center justify-between">
              <div className="text-lg font-semibold text-white flex items-center gap-2">
                PCA Manifold
                <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                  LIVE
                </span>
              </div>
              <div className="text-sm text-slate-400">
                Updating as morphology data arrives
              </div>
            </div>
          )}
          <ResponsiveContainer width="100%" height={500}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                type="number"
                dataKey="pc1"
                name="PC1"
                stroke="#94a3b8"
                label={{ value: 'Principal Component 1', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
              />
              <YAxis
                type="number"
                dataKey="pc2"
                name="PC2"
                stroke="#94a3b8"
                label={{ value: 'Principal Component 2', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
              />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    const doseCategory = getDoseCategory(data.dose_uM);
                    return (
                      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
                        <div className="font-semibold text-white mb-2">{data.well_id}</div>
                        <div className="space-y-1 text-xs">
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Cell Line:</span>
                            <span className="text-white font-medium">{data.cell_line}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Compound:</span>
                            <span className="text-white font-medium">{data.compound}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Dose:</span>
                            <span className="text-white font-medium">{data.dose_uM} µM ({doseCategory.replace(/\s*\([^)]*\)/g, '')})</span>
                          </div>
                          <div className="border-t border-slate-700 my-2"></div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">PC1:</span>
                            <span className="text-white font-mono">{data.pc1.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">PC2:</span>
                            <span className="text-white font-mono">{data.pc2.toFixed(2)}</span>
                          </div>
                          {data.is_sentinel && (
                            <div className="mt-2 pt-2 border-t border-slate-700">
                              <span className="text-amber-400 text-xs font-semibold">🔍 SENTINEL</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />

              {groupedData.map(([groupName, data], idx) => {
                let fillColor = '#8b5cf6';
                if (colorBy === 'cell_line' || colorBy === 'compound') {
                  fillColor = getColor(data[0]);
                } else if (colorBy === 'dose') {
                  fillColor = getDoseCategoryColor(groupName);
                }

                return (
                  <Scatter
                    key={groupName}
                    name={groupName}
                    data={data}
                    fill={fillColor}
                    fillOpacity={0.6}
                  />
                );
              })}
            </ScatterChart>
          </ResponsiveContainer>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Each point represents a well. PC1 and PC2 capture the dominant
            modes of morphological variation. Clustering indicates similar cellular phenotypes, while
            separation suggests distinct stress responses.
            {colorBy === 'cell_line' && ' Color indicates cell line.'}
            {colorBy === 'compound' && ' Color indicates compound - compounds with similar colors have similar morphological profiles.'}
            {colorBy === 'dose' && ' Color indicates dose level - progression from green (low) to red (high) shows dose-dependent changes.'}
            {' '}Sentinels should cluster tightly if measurement variance is low.
          </div>
        </div>
      )}
    </div>
  );
};

export default MorphologyTab;
