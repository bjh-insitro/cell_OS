/**
 * Tab 4: Variance Analysis
 *
 * Mixed model variance partitioning - biological vs technical sources
 */

import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { useDesigns, useVarianceAnalysis, useAllVarianceAnalysis } from '../hooks/useCellThalamusData';

interface VarianceTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const VarianceTab: React.FC<VarianceTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const [selectedMetric, setSelectedMetric] = React.useState<string>('atp_signal');
  const { data: analysis, loading, error, refetch: refetchAnalysis } = useVarianceAnalysis(selectedDesignId, selectedMetric);
  const { data: allVarianceData, loading: heatmapLoading, refetch: refetchHeatmap } = useAllVarianceAnalysis(selectedDesignId);
  const [isLiveMode, setIsLiveMode] = React.useState<boolean>(false);

  const allDesigns = React.useMemo(() => designs || [], [designs]);
  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  // Check if selected design is currently running
  const isDesignRunning = React.useMemo(() => {
    if (!selectedDesignId || !designs) return false;
    const design = designs.find(d => d.design_id === selectedDesignId);
    return design?.status === 'running';
  }, [selectedDesignId, designs]);

  // Live polling: refetch analysis every 5 seconds when design is running
  React.useEffect(() => {
    if (isDesignRunning && selectedDesignId) {
      setIsLiveMode(true);
      refetchAnalysis();
      refetchHeatmap();

      const intervalId = setInterval(() => {
        refetchAnalysis();
        refetchHeatmap();
      }, 5000);

      return () => clearInterval(intervalId);
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, refetchAnalysis, refetchHeatmap]);

  // Prepare chart data
  const chartData = analysis?.components.map((comp) => ({
    name: comp.source,
    variance: comp.variance,
    fraction: comp.fraction * 100,
  })) || [];

  // Color code: biological = green, technical = orange, residual = gray
  const getColor = (source: string) => {
    const biologicalSources = ['cell_line', 'compound', 'dose', 'timepoint'];
    const technicalSources = ['plate', 'day', 'operator'];

    if (biologicalSources.includes(source)) return '#10b981'; // green
    if (technicalSources.includes(source)) return '#f59e0b'; // orange
    if (source === 'residual') return '#64748b'; // gray (unexplained)
    return '#64748b'; // gray default
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

      {/* Live Mode Indicator */}
      {isLiveMode && analysis && (
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
                  Variance analysis updating every 5 seconds as data arrives
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

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

          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Select Metric
            </label>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="atp_signal">LDH Cytotoxicity (Viability)</option>
              <option value="morph_er">ER Morphology</option>
              <option value="morph_mito">Mitochondria Morphology</option>
              <option value="morph_nucleus">Nucleus Morphology</option>
              <option value="morph_actin">Actin Morphology</option>
              <option value="morph_rna">RNA Morphology</option>
            </select>
          </div>
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
        <div className={`bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all ${
          isLiveMode
            ? 'border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
            : 'border-slate-700'
        }`}>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            Variance Component Breakdown
            {isLiveMode && (
              <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                LIVE
              </span>
            )}
          </h3>

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
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-slate-500 rounded"></div>
              <span className="text-slate-300">Residual (Unexplained)</span>
            </div>
          </div>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Variance decomposition shows what drives measurement variability.
            <strong className="text-green-400"> Biological sources</strong> (cell_line, compound, dose, timepoint)
            represent real biology - this is signal we want to detect.
            <strong className="text-orange-400"> Technical sources</strong> (plate, day, operator) represent
            measurement noise - this should be minimized.
            <strong className="text-slate-300"> Residual</strong> is unexplained variance not captured by measured factors.
            Goal: {'>'}70% biological, {'<'}30% technical. All components sum to 100%.
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
                                  : comp.source === 'residual'
                                  ? 'bg-slate-500/20 text-slate-400'
                                  : 'bg-orange-500/20 text-orange-400'
                              }
                            `}
                          >
                            {['cell_line', 'compound', 'dose', 'timepoint'].includes(comp.source)
                              ? 'Biological'
                              : comp.source === 'residual'
                              ? 'Residual'
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

      {/* Variance Heatmap - All Metrics */}
      {selectedDesignId && allVarianceData && allVarianceData.all_metrics && (
        <div className={`bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all ${
          isLiveMode
            ? 'border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
            : 'border-slate-700'
        }`}>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            Variance Heatmap - All Metrics
            {isLiveMode && (
              <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                LIVE
              </span>
            )}
          </h3>

          {(() => {
            const metrics = Object.keys(allVarianceData.all_metrics);
            const metricLabels: Record<string, string> = {
              'atp_signal': 'LDH',
              'morph_er': 'ER',
              'morph_mito': 'Mito',
              'morph_nucleus': 'Nucleus',
              'morph_actin': 'Actin',
              'morph_rna': 'RNA'
            };

            // Get all unique sources across all metrics
            const allSources = new Set<string>();
            metrics.forEach(metric => {
              allVarianceData.all_metrics[metric].components.forEach((comp: any) => {
                allSources.add(comp.source);
              });
            });

            const sources = Array.from(allSources);

            // Helper to get color based on source type and fraction
            const getHeatmapColor = (source: string, fraction: number): string => {
              const biologicalSources = ['cell_line', 'compound', 'dose', 'timepoint'];
              const technicalSources = ['plate', 'day', 'operator'];

              const intensity = Math.min(fraction * 100, 100);

              if (biologicalSources.includes(source)) {
                // Green for biological (higher is better)
                if (intensity < 10) return '#134e4a'; // very dark green
                if (intensity < 20) return '#166534';
                if (intensity < 30) return '#15803d';
                if (intensity < 40) return '#16a34a';
                if (intensity < 50) return '#22c55e';
                return '#4ade80'; // bright green
              } else if (technicalSources.includes(source)) {
                // Orange/Red for technical (lower is better)
                if (intensity < 5) return '#422006'; // very dark amber
                if (intensity < 10) return '#713f12';
                if (intensity < 15) return '#92400e';
                if (intensity < 20) return '#b45309';
                if (intensity < 30) return '#f59e0b';
                return '#fb923c'; // bright orange
              } else {
                // Gray for residual
                if (intensity < 10) return '#1e293b';
                if (intensity < 20) return '#334155';
                if (intensity < 30) return '#475569';
                if (intensity < 40) return '#64748b';
                return '#94a3b8';
              }
            };

            return (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-slate-300 border-b border-slate-700">
                        Source
                      </th>
                      {metrics.map(metric => (
                        <th key={metric} className="px-3 py-2 text-center text-xs font-semibold text-slate-300 border-b border-slate-700">
                          {metricLabels[metric] || metric}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map(source => (
                      <tr key={source} className="border-b border-slate-800 hover:bg-slate-900/30">
                        <td className="px-3 py-2 text-xs font-medium text-white capitalize">
                          {source}
                        </td>
                        {metrics.map(metric => {
                          const comp = allVarianceData.all_metrics[metric].components.find(
                            (c: any) => c.source === source
                          );
                          const fraction = comp ? comp.fraction : 0;
                          const color = getHeatmapColor(source, fraction);

                          return (
                            <td
                              key={`${source}-${metric}`}
                              className="px-3 py-2 text-center text-xs font-mono"
                              style={{ backgroundColor: color }}
                            >
                              <span className="text-white font-semibold">
                                {(fraction * 100).toFixed(1)}%
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}

          {/* Heatmap Legend */}
          <div className="mt-4 flex flex-wrap gap-6 justify-center text-xs">
            <div>
              <div className="font-semibold text-green-400 mb-2">Biological Sources (high = good)</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-[#134e4a] border border-slate-600"></div>
                <span className="text-slate-400">Low</span>
                <div className="w-4 h-4 bg-[#16a34a]"></div>
                <div className="w-4 h-4 bg-[#22c55e]"></div>
                <div className="w-4 h-4 bg-[#4ade80]"></div>
                <span className="text-slate-400">High</span>
              </div>
            </div>
            <div>
              <div className="font-semibold text-orange-400 mb-2">Technical Sources (low = good)</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-[#422006] border border-slate-600"></div>
                <span className="text-slate-400">Low</span>
                <div className="w-4 h-4 bg-[#b45309]"></div>
                <div className="w-4 h-4 bg-[#f59e0b]"></div>
                <div className="w-4 h-4 bg-[#fb923c]"></div>
                <span className="text-slate-400">High</span>
              </div>
            </div>
            <div>
              <div className="font-semibold text-slate-400 mb-2">Residual (unexplained)</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-[#1e293b] border border-slate-600"></div>
                <span className="text-slate-400">Low</span>
                <div className="w-4 h-4 bg-[#475569]"></div>
                <div className="w-4 h-4 bg-[#94a3b8]"></div>
                <span className="text-slate-400">High</span>
              </div>
            </div>
          </div>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> This heatmap shows variance fractions across all metrics simultaneously.
            <strong className="text-green-400"> Green cells</strong> (biological sources) should be bright = high variance = good signal.
            <strong className="text-orange-400"> Orange cells</strong> (technical sources) should be dark = low variance = low noise.
            Compare columns to identify which metrics are most reliable for your assay.
          </div>
        </div>
      )}
    </div>
  );
};

export default VarianceTab;
