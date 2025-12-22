/**
 * SentinelChart - Reusable Statistical Process Control (SPC) chart
 *
 * Shows a line chart with control limits (mean, UCL, LCL) and outlier detection.
 * Can be used for any sequential measurement data.
 */

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';

export interface SentinelDataPoint {
  index: number;
  value: number;
  isOutlier?: boolean;
  label?: string;
  wellId?: string;
}

export interface SentinelChartProps {
  data: SentinelDataPoint[];
  mean: number;
  ucl: number;  // Upper control limit
  lcl: number;  // Lower control limit
  std: number;
  title?: string;
  subtitle?: string;
  yAxisLabel?: string;
  xAxisLabel?: string;
  isDarkMode?: boolean;
  showStatistics?: boolean;
  height?: number;
  isLiveMode?: boolean;
}

export default function SentinelChart({
  data,
  mean,
  ucl,
  lcl,
  std,
  title,
  subtitle = 'Control limits: mean ± 3σ (99.7% confidence interval)',
  yAxisLabel = 'Value',
  xAxisLabel = 'Measurement Number',
  isDarkMode = true,
  showStatistics = true,
  height = 400,
  isLiveMode = false
}: SentinelChartProps) {
  const outlierCount = data.filter(p => p.isOutlier).length;

  const chartColors = {
    grid: isDarkMode ? '#475569' : '#cbd5e1',
    axis: isDarkMode ? '#94a3b8' : '#64748b',
    line: isDarkMode ? '#8b5cf6' : '#7c3aed',
    dot: isDarkMode ? '#8b5cf6' : '#7c3aed',
    dotOutlier: isDarkMode ? '#ef4444' : '#dc2626',
    mean: isDarkMode ? '#8b5cf6' : '#7c3aed',
    controlLimit: isDarkMode ? '#10b981' : '#059669',
    tooltipBg: isDarkMode ? '#1e293b' : '#f8fafc',
    tooltipBorder: isDarkMode ? '#475569' : '#cbd5e1',
    tooltipText: isDarkMode ? '#e2e8f0' : '#1e293b',
  };

  return (
    <div className={`backdrop-blur-sm border rounded-xl p-6 transition-all ${
      isDarkMode
        ? isLiveMode
          ? 'bg-slate-800/50 border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
          : 'bg-slate-800/50 border-slate-700'
        : isLiveMode
          ? 'bg-white border-red-400 shadow-lg shadow-red-400/20 animate-pulse'
          : 'bg-white border-zinc-200'
    }`}>
      {/* Header */}
      {(title || showStatistics) && (
        <div className="mb-4">
          {title && (
            <div>
              <h3 className={`text-lg font-semibold flex items-center gap-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                {title}
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              {subtitle && (
                <p className={`text-sm mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  {subtitle}
                </p>
              )}
            </div>
          )}

          {/* Statistics Summary */}
          {showStatistics && (
            <div className={`rounded-lg p-4 border mt-4 ${
              isDarkMode ? 'bg-slate-900/50 border-slate-700' : 'bg-zinc-50 border-zinc-200'
            }`}>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                <div>
                  <div className={`text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    Mean
                  </div>
                  <div className={`text-lg font-bold mt-1 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
                    {mean.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className={`text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    Std Dev
                  </div>
                  <div className={`text-lg font-bold mt-1 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
                    {std.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className={`text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    UCL
                  </div>
                  <div className={`text-lg font-bold mt-1 ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
                    {ucl.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className={`text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    LCL
                  </div>
                  <div className={`text-lg font-bold mt-1 ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
                    {lcl.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className={`text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    Outliers
                  </div>
                  <div className={`text-lg font-bold mt-1 ${
                    outlierCount > 0
                      ? isDarkMode ? 'text-red-400' : 'text-red-600'
                      : isDarkMode ? 'text-green-400' : 'text-green-600'
                  }`}>
                    {outlierCount} / {data.length}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis
            dataKey="index"
            stroke={chartColors.axis}
            label={{
              value: xAxisLabel,
              position: 'insideBottom',
              offset: -10,
              fill: chartColors.axis
            }}
          />
          <YAxis
            stroke={chartColors.axis}
            label={{
              value: yAxisLabel,
              angle: -90,
              position: 'insideLeft',
              fill: chartColors.axis,
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: chartColors.tooltipBg,
              border: `1px solid ${chartColors.tooltipBorder}`,
              borderRadius: '8px',
              color: chartColors.tooltipText,
            }}
            formatter={(value: any, name: string) => {
              if (name === 'value') return Number(value).toFixed(2);
              return value;
            }}
            labelFormatter={(label) => `Measurement ${label}`}
          />
          <Legend />

          {/* Control limits */}
          <ReferenceLine
            y={mean}
            stroke={chartColors.mean}
            strokeWidth={2}
            strokeDasharray="5 5"
            label={{ value: 'Mean', fill: chartColors.mean, position: 'right' }}
          />
          <ReferenceLine
            y={ucl}
            stroke={chartColors.controlLimit}
            strokeWidth={2}
            strokeDasharray="3 3"
            label={{ value: 'UCL', fill: chartColors.controlLimit, position: 'right' }}
          />
          <ReferenceLine
            y={lcl}
            stroke={chartColors.controlLimit}
            strokeWidth={2}
            strokeDasharray="3 3"
            label={{ value: 'LCL', fill: chartColors.controlLimit, position: 'right' }}
          />

          {/* Data line */}
          <Line
            type="monotone"
            dataKey="value"
            stroke={chartColors.line}
            strokeWidth={2}
            dot={(props: any) => {
              const { cx, cy, payload } = props;
              return (
                <circle
                  cx={cx}
                  cy={cy}
                  r={5}
                  fill={payload.isOutlier ? chartColors.dotOutlier : chartColors.dot}
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
      <div className={`mt-4 text-xs rounded-lg p-4 border ${
        isDarkMode
          ? 'text-slate-400 bg-slate-900/50 border-slate-700'
          : 'text-zinc-600 bg-zinc-50 border-zinc-200'
      }`}>
        <strong>Interpretation:</strong> Points should remain within control limits (mean ± 3σ).
        <span className={isDarkMode ? 'text-red-400' : 'text-red-600'}> Red points</span> are outliers
        indicating measurement instability or artifacts.
        Goal: All points within 3σ limits.
      </div>

      {/* Outlier Details */}
      {outlierCount > 0 && (
        <div className={`mt-4 rounded-lg p-4 border ${
          isDarkMode
            ? 'bg-red-900/20 border-red-500/50'
            : 'bg-red-50 border-red-300'
        }`}>
          <h4 className={`text-sm font-semibold mb-2 ${isDarkMode ? 'text-red-300' : 'text-red-700'}`}>
            ⚠️ {outlierCount} Out-of-Control Point{outlierCount > 1 ? 's' : ''}
          </h4>
          <div className="space-y-1 text-xs">
            {data
              .filter(p => p.isOutlier)
              .map((point, idx) => (
                <div key={idx} className={isDarkMode ? 'text-red-300' : 'text-red-700'}>
                  Measurement #{point.index}: {point.wellId || point.label || 'Well'} = {point.value.toFixed(2)}
                  {point.isOutlier && ` (outside ${ucl > mean ? 'UCL' : 'LCL'})`}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Status Badge */}
      <div className="mt-4 flex justify-center">
        <div className={`px-6 py-3 rounded-full font-bold text-sm border-2 ${
          outlierCount === 0
            ? isDarkMode
              ? 'bg-green-500/20 text-green-400 border-green-500/50'
              : 'bg-green-50 text-green-700 border-green-400'
            : isDarkMode
              ? 'bg-red-500/20 text-red-400 border-red-500/50'
              : 'bg-red-50 text-red-700 border-red-400'
        }`}>
          {outlierCount === 0
            ? '✓ Process In Control'
            : `⚠️ Process Out of Control (${outlierCount} outliers)`}
        </div>
      </div>
    </div>
  );
}
