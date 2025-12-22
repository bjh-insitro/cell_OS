/**
 * PlateResultsViewer - Display simulation results with plate map and charts
 *
 * Shows:
 * - Clickable plate map colored by measurement values
 * - Channel selector (DNA, ER, AGP, Mito, RNA)
 * - Sentinel chart showing values over well index
 */

import React, { useState } from 'react';
import PlateViewer, { WellData } from './PlateViewer';
import SentinelChart, { SentinelDataPoint } from './SentinelChart';

export interface CellPaintingChannel {
  id: string;
  name: string;
  color: string;
  description?: string;
}

export interface WellMeasurement {
  wellId: string;
  row: string;
  col: number;
  channels: {
    [channelId: string]: number;  // channel id -> measurement value
  };
  metadata?: {
    cellLine?: string;
    treatment?: string;
    dose?: number;
    [key: string]: any;
  };
}

export interface PlateResultsViewerProps {
  plateId: string;
  format: '96' | '384' | '1536';
  measurements: WellMeasurement[];
  channels: CellPaintingChannel[];
  isDarkMode?: boolean;
  title?: string;
  showSentinelChart?: boolean;
  onWellClick?: (wellId: string) => void;
}

const DEFAULT_CHANNELS: CellPaintingChannel[] = [
  { id: 'dna', name: 'DNA (Hoechst)', color: '#3b82f6', description: 'Nucleus' },
  { id: 'er', name: 'ER (Concanavalin A)', color: '#10b981', description: 'Endoplasmic Reticulum' },
  { id: 'agp', name: 'AGP (WGA)', color: '#f59e0b', description: 'Golgi & Plasma Membrane' },
  { id: 'mito', name: 'Mito (MitoTracker)', color: '#ef4444', description: 'Mitochondria' },
  { id: 'rna', name: 'RNA (SYTO)', color: '#8b5cf6', description: 'Nucleoli & Cytoplasmic RNA' },
];

export default function PlateResultsViewer({
  plateId,
  format,
  measurements,
  channels = DEFAULT_CHANNELS,
  isDarkMode = true,
  title,
  showSentinelChart = true,
  onWellClick
}: PlateResultsViewerProps) {
  const [selectedChannel, setSelectedChannel] = useState<string>(channels[0]?.id || 'dna');

  // Get min/max for the selected channel to normalize colors
  const channelValues = measurements.map(m => m.channels[selectedChannel] || 0);
  const minValue = Math.min(...channelValues);
  const maxValue = Math.max(...channelValues);
  const range = maxValue - minValue;

  // Calculate statistics for sentinel chart
  const mean = channelValues.reduce((sum, v) => sum + v, 0) / channelValues.length;
  const variance = channelValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / channelValues.length;
  const std = Math.sqrt(variance);
  const ucl = mean + 3 * std;
  const lcl = mean - 3 * std;

  // Convert to color based on value (gradient from dark to bright for selected channel)
  const getWellColor = (value: number): string => {
    if (range === 0) return 'bg-slate-700/70';

    const normalized = (value - minValue) / range;
    const channelInfo = channels.find(c => c.id === selectedChannel);
    const baseColor = channelInfo?.color || '#8b5cf6';

    // Convert hex to rgb and apply opacity based on normalized value
    const opacity = 0.3 + (normalized * 0.7); // 30% to 100%

    // Tailwind-compatible approach: use predefined color classes
    if (selectedChannel === 'dna') {
      if (normalized < 0.2) return 'bg-blue-400/30';
      if (normalized < 0.4) return 'bg-blue-400/50';
      if (normalized < 0.6) return 'bg-blue-500/70';
      if (normalized < 0.8) return 'bg-blue-600/85';
      return 'bg-blue-700/100';
    } else if (selectedChannel === 'er') {
      if (normalized < 0.2) return 'bg-green-400/30';
      if (normalized < 0.4) return 'bg-green-400/50';
      if (normalized < 0.6) return 'bg-green-500/70';
      if (normalized < 0.8) return 'bg-green-600/85';
      return 'bg-green-700/100';
    } else if (selectedChannel === 'agp') {
      if (normalized < 0.2) return 'bg-amber-400/30';
      if (normalized < 0.4) return 'bg-amber-400/50';
      if (normalized < 0.6) return 'bg-amber-500/70';
      if (normalized < 0.8) return 'bg-amber-600/85';
      return 'bg-amber-700/100';
    } else if (selectedChannel === 'mito') {
      if (normalized < 0.2) return 'bg-red-400/30';
      if (normalized < 0.4) return 'bg-red-400/50';
      if (normalized < 0.6) return 'bg-red-500/70';
      if (normalized < 0.8) return 'bg-red-600/85';
      return 'bg-red-700/100';
    } else if (selectedChannel === 'rna') {
      if (normalized < 0.2) return 'bg-purple-400/30';
      if (normalized < 0.4) return 'bg-purple-400/50';
      if (normalized < 0.6) return 'bg-purple-500/70';
      if (normalized < 0.8) return 'bg-purple-600/85';
      return 'bg-purple-700/100';
    }

    return 'bg-slate-700/70';
  };

  // Build well data for plate viewer
  const wellData: WellData[] = measurements.map(m => {
    const value = m.channels[selectedChannel] || 0;
    const isOutlier = value > ucl || value < lcl;

    return {
      id: m.wellId,
      color: getWellColor(value),
      borderColor: isOutlier ? '#ef4444' : '#64748b',  // Red border for outliers
      borderWidth: isOutlier ? 3 : 1,                  // Thicker border for outliers
      tooltip: {
        title: m.wellId,
        lines: [
          `${channels.find(c => c.id === selectedChannel)?.name}: ${value.toFixed(2)}`,
          ...(isOutlier ? ['⚠️ OUTLIER (>3σ from mean)'] : []),
          ...(m.metadata?.cellLine ? [`Cell line: ${m.metadata.cellLine}`] : []),
          ...(m.metadata?.treatment ? [`Treatment: ${m.metadata.treatment}`] : []),
          ...(m.metadata?.dose !== undefined ? [`Dose: ${m.metadata.dose}µM`] : []),
        ],
      },
    };
  });

  // Build sentinel chart data
  const sentinelData: SentinelDataPoint[] = measurements.map((m, idx) => {
    const value = m.channels[selectedChannel] || 0;
    const isOutlier = value > ucl || value < lcl;

    return {
      index: idx + 1,
      value,
      isOutlier,
      wellId: m.wellId,
      label: m.wellId,
    };
  });

  const currentChannel = channels.find(c => c.id === selectedChannel);

  return (
    <div className="space-y-6">
      {/* Header */}
      {title && (
        <div>
          <h2 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
            {title}
          </h2>
          <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
            {plateId} - {measurements.length} wells
          </p>
        </div>
      )}

      {/* Channel Selector */}
      <div className={`rounded-lg border p-6 ${
        isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'
      }`}>
        <div className={`text-sm font-semibold mb-3 uppercase tracking-wider ${
          isDarkMode ? 'text-violet-400' : 'text-violet-600'
        }`}>
          Select Channel
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {channels.map(channel => (
            <button
              key={channel.id}
              onClick={() => setSelectedChannel(channel.id)}
              className={`p-3 rounded-lg border-2 transition-all text-left ${
                selectedChannel === channel.id
                  ? isDarkMode
                    ? 'bg-violet-900/50 border-violet-500 shadow-lg'
                    : 'bg-violet-50 border-violet-500 shadow-lg'
                  : isDarkMode
                    ? 'bg-slate-900 border-slate-700 hover:border-slate-600'
                    : 'bg-zinc-50 border-zinc-300 hover:border-zinc-400'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: channel.color }}
                />
                <div className={`font-bold text-sm ${
                  isDarkMode ? 'text-white' : 'text-zinc-900'
                }`}>
                  {channel.name}
                </div>
              </div>
              {channel.description && (
                <div className={`text-xs ${
                  isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                }`}>
                  {channel.description}
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Value Range Indicator */}
        <div className={`mt-4 p-3 rounded-lg border ${
          isDarkMode ? 'bg-slate-900/50 border-slate-700' : 'bg-zinc-50 border-zinc-200'
        }`}>
          <div className="flex items-center justify-between text-xs">
            <div>
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Min: </span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                {minValue.toFixed(2)}
              </span>
            </div>
            <div>
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Mean: </span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                {mean.toFixed(2)}
              </span>
            </div>
            <div>
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Max: </span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                {maxValue.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Color legend - stepped to match actual well colors */}
          <div className="mt-2">
            <div className={`text-xs mb-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
              Intensity scale:
            </div>
            <div className="flex items-stretch h-6 rounded overflow-hidden border border-slate-600">
              {/* 5 discrete steps matching getWellColor() logic */}
              {[
                { threshold: 0.0, label: minValue.toFixed(1) },
                { threshold: 0.2, label: '' },
                { threshold: 0.4, label: '' },
                { threshold: 0.6, label: '' },
                { threshold: 0.8, label: '' },
                { threshold: 1.0, label: maxValue.toFixed(1) },
              ].map((step, idx) => {
                if (idx === 5) return null; // Skip the last one (just a label marker)
                const normalized = (step.threshold + (idx < 4 ? 0.2 : 0)) / 2; // Midpoint of range
                const colorClass = getWellColor(minValue + normalized * range);
                return (
                  <div
                    key={idx}
                    className={`flex-1 ${colorClass}`}
                    title={`${(minValue + step.threshold * range).toFixed(2)} - ${(minValue + (step.threshold + 0.2) * range).toFixed(2)}`}
                  />
                );
              }).filter(Boolean)}
            </div>
            <div className="flex items-center justify-between text-xs mt-1">
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>{minValue.toFixed(1)}</span>
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                {((minValue + maxValue) / 2).toFixed(1)}
              </span>
              <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>{maxValue.toFixed(1)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Plate Map */}
      <div className={`rounded-lg border p-6 ${
        isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-zinc-200'
      }`}>
        <h3 className={`text-lg font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          Plate Map - {currentChannel?.name}
        </h3>
        <PlateViewer
          format={format}
          wells={wellData}
          isDarkMode={isDarkMode}
          size={format === '96' ? 'large' : 'medium'}
          showLabels={false}
          showAxisLabels={true}
          onWellClick={onWellClick}
        />
      </div>

      {/* Sentinel Chart */}
      {showSentinelChart && (
        <SentinelChart
          data={sentinelData}
          mean={mean}
          ucl={ucl}
          lcl={lcl}
          std={std}
          title={`${currentChannel?.name} - Well-by-Well Analysis`}
          subtitle="Sequential measurement showing spatial patterns and outliers"
          yAxisLabel={currentChannel?.name || 'Value'}
          xAxisLabel="Well Index"
          isDarkMode={isDarkMode}
          showStatistics={true}
          height={400}
        />
      )}
    </div>
  );
}
