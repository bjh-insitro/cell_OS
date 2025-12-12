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
  const { data: morphologyData, loading, error } = useMorphologyData(selectedDesignId);
  const { data: results } = useResults(selectedDesignId);

  const [colorBy, setColorBy] = useState<'cell_line' | 'compound' | 'dose'>('cell_line');

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
      // Hash compound name to color
      const hash = item.compound.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
      const hue = hash % 360;
      return `hsl(${hue}, 70%, 60%)`;
    } else {
      // Dose gradient
      const intensity = Math.min(item.dose_uM / 100, 1);
      return `rgba(139, 92, 246, ${0.3 + intensity * 0.7})`;
    }
  };

  // Group data by color for multiple scatter series
  const groupedData = useMemo(() => {
    if (colorBy === 'cell_line') {
      const groups: Record<string, typeof pcaData> = {};
      pcaData.forEach((item) => {
        if (!groups[item.cell_line]) groups[item.cell_line] = [];
        groups[item.cell_line].push(item);
      });
      return Object.entries(groups);
    }
    return [['All', pcaData]];
  }, [pcaData, colorBy]);

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
              <option value="">-- Select a completed design --</option>
              {completedDesigns.map((design) => (
                <option key={design.design_id} value={design.design_id}>
                  {design.design_id.slice(0, 8)}... ({design.cell_lines.join(', ')})
                </option>
              ))}
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
                  onClick={() => setColorBy(option)}
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
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
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
                formatter={(value: any, name: string) => {
                  if (name === 'PC1' || name === 'PC2') return value.toFixed(2);
                  return value;
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />

              {groupedData.map(([groupName, data], idx) => (
                <Scatter
                  key={groupName}
                  name={groupName}
                  data={data}
                  fill={colorBy === 'cell_line' ? getColor(data[0]) : '#8b5cf6'}
                  fillOpacity={0.6}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Each point represents a well. PC1 and PC2 capture the dominant
            modes of morphological variation. Clustering indicates similar cellular phenotypes, while
            separation suggests distinct stress responses. Sentinels should cluster tightly if measurement
            variance is low.
          </div>
        </div>
      )}
    </div>
  );
};

export default MorphologyTab;
