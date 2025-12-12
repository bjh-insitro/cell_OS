/**
 * Tab 4: Variance Analysis
 *
 * Mixed model variance partitioning - biological vs technical sources
 */

import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { useDesigns, useVarianceAnalysis } from '../hooks/useCellThalamusData';

interface VarianceTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const VarianceTab: React.FC<VarianceTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: analysis, loading, error } = useVarianceAnalysis(selectedDesignId);

  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  // Prepare chart data
  const chartData = analysis?.components.map((comp) => ({
    name: comp.source,
    variance: comp.variance,
    fraction: comp.fraction * 100,
  })) || [];

  // Color code: biological = green, technical = orange
  const getColor = (source: string) => {
    const biologicalSources = ['cell_line', 'compound', 'dose', 'timepoint'];
    const technicalSources = ['plate', 'day', 'operator'];

    if (biologicalSources.includes(source)) return '#10b981'; // green
    if (technicalSources.includes(source)) return '#f59e0b'; // orange
    return '#64748b'; // gray
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Variance Analysis</h2>
        <p className="text-slate-400">
          Mixed model decomposition: biological signal vs technical noise
        </p>
      </div>

      {/* Controls */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

          {analysis && (
            <div className="flex items-end">
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 w-full">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Metric</div>
                <div className="text-lg font-bold text-white mt-1">{analysis.metric}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Success Criteria */}
      {analysis && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Success Criteria</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Biological Dominance */}
            <div
              className={`
                p-4 rounded-lg border-2 transition-all
                ${
                  analysis.criteria.biological_dominance
                    ? 'bg-green-900/20 border-green-500/50'
                    : 'bg-red-900/20 border-red-500/50'
                }
              `}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-white">Biological Dominance</span>
                <span className="text-2xl">
                  {analysis.criteria.biological_dominance ? '✓' : '✗'}
                </span>
              </div>
              <div className="text-xs text-slate-300 mb-2">
                Target: {'>'} 70% biological variance
              </div>
              <div className="text-lg font-bold text-white">
                {(analysis.biological_fraction * 100).toFixed(1)}%
              </div>
            </div>

            {/* Technical Minimal */}
            <div
              className={`
                p-4 rounded-lg border-2 transition-all
                ${
                  analysis.criteria.technical_minimal
                    ? 'bg-green-900/20 border-green-500/50'
                    : 'bg-red-900/20 border-red-500/50'
                }
              `}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-white">Technical Minimal</span>
                <span className="text-2xl">
                  {analysis.criteria.technical_minimal ? '✓' : '✗'}
                </span>
              </div>
              <div className="text-xs text-slate-300 mb-2">
                Target: {'<'} 30% technical variance
              </div>
              <div className="text-lg font-bold text-white">
                {(analysis.technical_fraction * 100).toFixed(1)}%
              </div>
            </div>

            {/* Sentinel Stable */}
            <div
              className={`
                p-4 rounded-lg border-2 transition-all
                ${
                  analysis.criteria.sentinel_stable
                    ? 'bg-green-900/20 border-green-500/50'
                    : 'bg-red-900/20 border-red-500/50'
                }
              `}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-white">Sentinel Stable</span>
                <span className="text-2xl">
                  {analysis.criteria.sentinel_stable ? '✓' : '✗'}
                </span>
              </div>
              <div className="text-xs text-slate-300 mb-2">
                Target: All sentinels within 3σ
              </div>
              <div className="text-lg font-bold text-white">
                {(analysis.pass_rate * 100).toFixed(0)}% pass
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a completed design to view variance analysis
          </div>
        </div>
      ) : loading ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-slate-400">Computing variance decomposition...</div>
        </div>
      ) : error ? (
        <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6">
          <div className="text-red-300">Error: {error}</div>
        </div>
      ) : (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Variance Component Breakdown</h3>

          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                dataKey="name"
                stroke="#94a3b8"
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: 'Variance Fraction (%)',
                  angle: -90,
                  position: 'insideLeft',
                  fill: '#94a3b8',
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                }}
                formatter={(value: any, name: string) => {
                  if (name === 'fraction') return `${value.toFixed(1)}%`;
                  return value.toFixed(4);
                }}
              />
              <Legend />
              <Bar dataKey="fraction" name="Variance Fraction (%)">
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getColor(entry.name)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-4 justify-center text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded"></div>
              <span className="text-slate-300">Biological Sources</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-orange-500 rounded"></div>
              <span className="text-slate-300">Technical Sources</span>
            </div>
          </div>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Variance decomposition shows what drives measurement variability.
            <strong className="text-green-400"> Biological sources</strong> (cell_line, compound, dose, timepoint)
            represent real biology - this is signal we want to detect.
            <strong className="text-orange-400"> Technical sources</strong> (plate, day, operator) represent
            measurement noise - this should be minimized. Goal: {'>'}70% biological, {'<'}30% technical.
          </div>

          {/* Detailed Table */}
          {analysis && (
            <div className="mt-6">
              <h4 className="text-sm font-semibold text-white mb-3">Detailed Component Table</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-900/50 border-b border-slate-700">
                    <tr>
                      <th className="text-left px-4 py-2 text-slate-300">Source</th>
                      <th className="text-right px-4 py-2 text-slate-300">Variance</th>
                      <th className="text-right px-4 py-2 text-slate-300">Fraction (%)</th>
                      <th className="text-left px-4 py-2 text-slate-300">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.components.map((comp, idx) => (
                      <tr key={idx} className="border-b border-slate-800 hover:bg-slate-900/30">
                        <td className="px-4 py-2 font-medium text-white capitalize">
                          {comp.source}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-300 font-mono">
                          {comp.variance.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-300 font-mono">
                          {(comp.fraction * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`
                              px-2 py-1 rounded text-xs font-semibold
                              ${
                                ['cell_line', 'compound', 'dose', 'timepoint'].includes(comp.source)
                                  ? 'bg-green-500/20 text-green-400'
                                  : 'bg-orange-500/20 text-orange-400'
                              }
                            `}
                          >
                            {['cell_line', 'compound', 'dose', 'timepoint'].includes(comp.source)
                              ? 'Biological'
                              : 'Technical'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-900/50 border-t-2 border-slate-700 font-bold">
                    <tr>
                      <td className="px-4 py-2 text-white">Total</td>
                      <td className="px-4 py-2 text-right text-white font-mono">
                        {analysis.total_variance.toFixed(4)}
                      </td>
                      <td className="px-4 py-2 text-right text-white">100%</td>
                      <td className="px-4 py-2"></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default VarianceTab;
