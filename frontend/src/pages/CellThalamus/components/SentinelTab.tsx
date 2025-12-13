/**
 * Tab 5: Sentinel Monitor
 *
 * Statistical Process Control (SPC) charts for sentinel QC wells
 */

import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useDesigns, useSentinelData } from '../hooks/useCellThalamusData';

interface SentinelTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const SentinelTab: React.FC<SentinelTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: sentinelData, loading, error, refetch: refetchSentinels } = useSentinelData(selectedDesignId);

  const [selectedSentinel, setSelectedSentinel] = useState<number>(0);
  const [selectedMetric, setSelectedMetric] = useState<string>('atp_signal');
  const [isLiveMode, setIsLiveMode] = React.useState<boolean>(false);

  const allDesigns = React.useMemo(() => designs || [], [designs]);
  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  // Check if selected design is currently running
  const isDesignRunning = React.useMemo(() => {
    if (!selectedDesignId || !designs) return false;
    const design = designs.find(d => d.design_id === selectedDesignId);
    return design?.status === 'running';
  }, [selectedDesignId, designs]);

  // Live polling
  React.useEffect(() => {
    if (isDesignRunning && selectedDesignId) {
      setIsLiveMode(true);
      refetchSentinels();

      const intervalId = setInterval(() => {
        refetchSentinels();
      }, 5000);

      return () => clearInterval(intervalId);
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, refetchSentinels]);

  const metrics = [
    { value: 'atp_signal', label: 'ATP Viability' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
  ];

  // Get current sentinel and metric data
  const currentSentinel = sentinelData?.[selectedSentinel];
  const currentMetricData = currentSentinel?.metric === selectedMetric ? currentSentinel : null;

  // Format data for chart
  const chartData = currentMetricData?.points.map((point, idx) => ({
    index: idx + 1,
    value: point.value,
    isOutlier: point.is_outlier,
    label: `P${point.plate_id}-D${point.day}-${point.operator}`,
  })) || [];

  const outlierCount = currentMetricData?.points.filter((p) => p.is_outlier).length || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Sentinel Monitor</h2>
        <p className="text-slate-400">
          Statistical Process Control (SPC) for QC sentinel wells
        </p>
      </div>

      {/* Live Mode Indicator */}
      {isLiveMode && sentinelData && sentinelData.length > 0 && (
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
                  Sentinel data updating every 5 seconds as wells complete
                </div>
              </div>
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
                setSelectedSentinel(0);
              }}
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

          {/* Sentinel Type Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Sentinel Type
            </label>
            <select
              value={selectedSentinel}
              onChange={(e) => setSelectedSentinel(Number(e.target.value))}
              disabled={!selectedDesignId || !sentinelData}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            >
              {sentinelData?.map((sentinel, idx) => (
                <option key={idx} value={idx}>
                  {sentinel.sentinel_type}
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

        {/* Statistics Summary */}
        {currentMetricData && (
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Mean</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {currentMetricData.mean.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Std Dev</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {currentMetricData.std.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">UCL</div>
                <div className="text-lg font-bold text-green-400 mt-1">
                  {currentMetricData.ucl.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">LCL</div>
                <div className="text-lg font-bold text-green-400 mt-1">
                  {currentMetricData.lcl.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider">Outliers</div>
                <div
                  className={`text-lg font-bold mt-1 ${
                    outlierCount > 0 ? 'text-red-400' : 'text-green-400'
                  }`}
                >
                  {outlierCount} / {currentMetricData.points.length}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a design to view sentinel SPC charts
          </div>
        </div>
      ) : loading ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-slate-400">Loading sentinel data...</div>
        </div>
      ) : error ? (
        <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6">
          <div className="text-red-300">Error: {error}</div>
        </div>
      ) : !currentMetricData ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            No data available for this sentinel/metric combination
          </div>
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
                {currentSentinel?.sentinel_type} - {metrics.find((m) => m.value === selectedMetric)?.label}
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                Control limits: mean ± 3σ (99.7% confidence interval)
              </p>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                dataKey="index"
                stroke="#94a3b8"
                label={{ value: 'Measurement Number', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: metrics.find((m) => m.value === selectedMetric)?.label || 'Value',
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
                  if (name === 'value') return value.toFixed(2);
                  return value;
                }}
                labelFormatter={(label) => `Measurement ${label}`}
              />
              <Legend />

              {/* Control limits */}
              <ReferenceLine
                y={currentMetricData.mean}
                stroke="#8b5cf6"
                strokeWidth={2}
                strokeDasharray="5 5"
                label={{ value: 'Mean', fill: '#8b5cf6', position: 'right' }}
              />
              <ReferenceLine
                y={currentMetricData.ucl}
                stroke="#10b981"
                strokeWidth={2}
                strokeDasharray="3 3"
                label={{ value: 'UCL', fill: '#10b981', position: 'right' }}
              />
              <ReferenceLine
                y={currentMetricData.lcl}
                stroke="#10b981"
                strokeWidth={2}
                strokeDasharray="3 3"
                label={{ value: 'LCL', fill: '#10b981', position: 'right' }}
              />

              {/* Data line */}
              <Line
                type="monotone"
                dataKey="value"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={(props: any) => {
                  const { cx, cy, payload } = props;
                  return (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={5}
                      fill={payload.isOutlier ? '#ef4444' : '#8b5cf6'}
                      stroke={payload.isOutlier ? '#dc2626' : '#7c3aed'}
                      strokeWidth={2}
                    />
                  );
                }}
                activeDot={{ r: 7 }}
                name="Measurement"
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Sentinel wells use identical conditions across all plates, days,
            and operators to track measurement stability. Points should remain within control limits (mean ± 3σ).
            <span className="text-red-400"> Red points</span> are outliers indicating process instability.
            Goal: All sentinels within 3σ limits.
          </div>

          {/* Outlier Details */}
          {outlierCount > 0 && (
            <div className="mt-4 bg-red-900/20 border border-red-500/50 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-red-300 mb-2">
                ⚠️ {outlierCount} Out-of-Control Point{outlierCount > 1 ? 's' : ''}
              </h4>
              <div className="space-y-1 text-xs">
                {currentMetricData.points
                  .map((point, idx) => ({ ...point, index: idx + 1 }))
                  .filter((p) => p.is_outlier)
                  .map((point) => (
                    <div key={point.index} className="text-red-300">
                      Measurement #{point.index}: Plate {point.plate_id}, Day {point.day}, Operator{' '}
                      {point.operator} = {point.value.toFixed(2)}
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Status Badge */}
          <div className="mt-4 flex justify-center">
            <div
              className={`
                px-6 py-3 rounded-full font-bold text-sm
                ${
                  outlierCount === 0
                    ? 'bg-green-500/20 text-green-400 border-2 border-green-500/50'
                    : 'bg-red-500/20 text-red-400 border-2 border-red-500/50'
                }
              `}
            >
              {outlierCount === 0
                ? '✓ Process In Control'
                : `⚠️ Process Out of Control (${outlierCount} outliers)`}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SentinelTab;
