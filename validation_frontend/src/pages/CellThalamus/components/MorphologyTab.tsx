/**
 * Tab 2: Morphology Manifold
 *
 * PCA/UMAP visualization of 5-channel Cell Painting morphology
 */

import React, { useState, useMemo } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ZAxis, Line } from 'recharts';
import { useDesigns, useMorphologyData, useResults, usePCAData } from '../hooks/useCellThalamusData';

interface MorphologyTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const MorphologyTab: React.FC<MorphologyTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: morphologyData, loading, error, refetch: refetchMorphology } = useMorphologyData(selectedDesignId);
  const { data: results, refetch: refetchResults } = useResults(selectedDesignId);

  // Channel selection for PCA
  const ALL_CHANNELS = ['er', 'mito', 'nucleus', 'actin', 'rna'];
  const [selectedChannels, setSelectedChannels] = useState<string[]>(ALL_CHANNELS);

  // Fetch real PCA data
  const { data: pcaData, loading: pcaLoading, error: pcaError, refetch: refetchPCA } = usePCAData(
    selectedDesignId,
    selectedChannels.length === ALL_CHANNELS.length ? null : selectedChannels
  );

  const [colorBy, setColorBy] = useState<'cell_line' | 'compound' | 'dose' | 'timepoint'>('cell_line');
  const [selectedCellLines, setSelectedCellLines] = useState<Set<string>>(new Set());
  const [selectedCompounds, setSelectedCompounds] = useState<Set<string>>(new Set());
  const [selectedDoseCategories, setSelectedDoseCategories] = useState<Set<string>>(new Set());
  const [selectedTimepoints, setSelectedTimepoints] = useState<Set<string>>(new Set());
  const [showOnlySentinels, setShowOnlySentinels] = useState<boolean>(false);
  const [showDoseTrajectories, setShowDoseTrajectories] = useState<boolean>(false);
  const [showBiplotArrows, setShowBiplotArrows] = useState<boolean>(false);
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
      refetchPCA();

      // Set up polling interval
      const intervalId = setInterval(() => {
        refetchResults();
        refetchMorphology();
        refetchPCA();
      }, 5000);

      return () => {
        clearInterval(intervalId);
      };
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, refetchResults, refetchMorphology, refetchPCA]);

  // Transform real PCA data into chart format
  const scatterData = useMemo(() => {
    if (!pcaData || !pcaData.pc_scores || !pcaData.well_metadata) return [];

    // Combine PC scores with well metadata
    return pcaData.pc_scores.map((scores, idx) => {
      const metadata = pcaData.well_metadata[idx];
      return {
        pc1: scores[0],
        pc2: scores[1],
        well_id: metadata.well_id,
        cell_line: metadata.cell_line,
        compound: metadata.compound,
        dose_uM: metadata.dose_uM,
        timepoint_h: metadata.timepoint_h,
        is_sentinel: metadata.is_sentinel,
      };
    });
  }, [pcaData]);

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

  // Timepoint color mapping
  const getTimepointColor = (timepoint: number): string => {
    const colors: Record<number, string> = {
      12: '#22c55e',  // green (early)
      24: '#f59e0b',  // amber (mid)
      48: '#ef4444',  // red (late)
      72: '#991b1b',  // dark red (very late)
    };
    return colors[timepoint] || '#8b5cf6'; // violet default
  };

  // Color mapping
  const getColor = (item: typeof scatterData[0]) => {
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
    } else if (colorBy === 'timepoint') {
      return getTimepointColor(item.timepoint_h);
    } else {
      // Dose gradient
      const intensity = Math.min(item.dose_uM / 100, 1);
      return `rgba(139, 92, 246, ${0.3 + intensity * 0.7})`;
    }
  };

  // Categorize dose levels
  const getDoseCategory = (dose: number): string => {
    if (dose === 0) return 'Vehicle';
    if (dose <= 1) return 'Low';
    if (dose <= 10) return 'Mid';
    if (dose <= 100) return 'High';
    return 'Very High';
  };

  const getDoseCategoryColor = (category: string): string => {
    const colors: Record<string, string> = {
      'Vehicle': '#06b6d4', // cyan (control)
      'Low': '#22c55e', // green (minimal)
      'Mid': '#f59e0b', // amber (moderate)
      'High': '#ef4444', // red (strong)
      'Very High': '#991b1b', // dark red (very strong)
    };
    return colors[category] || '#8b5cf6';
  };

  // Extract unique values for filters
  const uniqueCellLines = useMemo(() =>
    Array.from(new Set(scatterData.map(item => item.cell_line))).sort(),
    [scatterData]
  );

  const uniqueCompounds = useMemo(() =>
    Array.from(new Set(scatterData.map(item => item.compound))).sort(),
    [scatterData]
  );

  const uniqueDoseCategories = useMemo(() => {
    const categories = Array.from(new Set(scatterData.map(item => getDoseCategory(item.dose_uM))));
    // Sort by dose order
    const order = ['Vehicle', 'Low', 'Mid', 'High', 'Very High'];
    return categories.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  }, [scatterData]);

  const uniqueTimepoints = useMemo(() =>
    Array.from(new Set(scatterData.map(item => item.timepoint_h))).sort((a, b) => a - b),
    [scatterData]
  );

  // Don't filter data - we'll grey out instead of removing
  const filteredPcaData = useMemo(() => {
    return scatterData;
  }, [scatterData]);

  // Group data by color for multiple scatter series
  const groupedData = useMemo(() => {
    // If showing only sentinels, separate into grey background and colored sentinels
    if (showOnlySentinels) {
      const nonSentinels = filteredPcaData.filter(item => !item.is_sentinel);
      const sentinels = filteredPcaData.filter(item => item.is_sentinel);

      // Group sentinels by the current colorBy mode
      const sentinelGroups: Record<string, typeof sentinels> = {};

      if (colorBy === 'cell_line') {
        sentinels.forEach(item => {
          if (!sentinelGroups[item.cell_line]) sentinelGroups[item.cell_line] = [];
          sentinelGroups[item.cell_line].push(item);
        });
      } else if (colorBy === 'compound') {
        sentinels.forEach(item => {
          if (!sentinelGroups[item.compound]) sentinelGroups[item.compound] = [];
          sentinelGroups[item.compound].push(item);
        });
      } else if (colorBy === 'timepoint') {
        sentinels.forEach(item => {
          const key = `${item.timepoint_h}h`;
          if (!sentinelGroups[key]) sentinelGroups[key] = [];
          sentinelGroups[key].push(item);
        });
      } else if (colorBy === 'dose') {
        sentinels.forEach(item => {
          const category = getDoseCategory(item.dose_uM);
          if (!sentinelGroups[category]) sentinelGroups[category] = [];
          sentinelGroups[category].push(item);
        });
      }

      // Return grey background layer + colored sentinel groups
      const result: [string, typeof filteredPcaData][] = [];
      if (nonSentinels.length > 0) {
        result.push(['Background (non-sentinel)', nonSentinels]);
      }
      result.push(...Object.entries(sentinelGroups));
      return result;
    }

    // Normal mode - group by colorBy
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
    } else if (colorBy === 'timepoint') {
      const groups: Record<string, typeof filteredPcaData> = {};
      filteredPcaData.forEach((item) => {
        const key = `${item.timepoint_h}h`;
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
      });
      return Object.entries(groups).sort((a, b) => {
        // Sort by timepoint order: 12h, 24h, 48h, etc.
        const aTime = parseFloat(a[0]);
        const bTime = parseFloat(b[0]);
        return aTime - bTime;
      });
    } else if (colorBy === 'dose') {
      const groups: Record<string, typeof filteredPcaData> = {};
      filteredPcaData.forEach((item) => {
        const category = getDoseCategory(item.dose_uM);
        if (!groups[category]) groups[category] = [];
        groups[category].push(item);
      });
      return Object.entries(groups).sort((a, b) => {
        // Sort by dose order: vehicle, low, mid, high, very high
        const order = ['Vehicle', 'Low', 'Mid', 'High', 'Very High'];
        return order.indexOf(a[0]) - order.indexOf(b[0]);
      });
    }
    return [['All', filteredPcaData]];
  }, [filteredPcaData, colorBy, showOnlySentinels]);

  // Aggregate data for variance blob visualization
  const aggregatedData = useMemo(() => {
    const aggregated: Array<{
      groupName: string;
      meanPC1: number;
      meanPC2: number;
      stdPC1: number;
      stdPC2: number;
      n: number;
      color: string;
    }> = [];

    groupedData.forEach(([groupName, data]) => {
      // Skip background (non-sentinel) layer
      if (groupName === 'Background (non-sentinel)') return;
      if (data.length === 0) return;

      // Calculate mean and std for PC1 and PC2
      const pc1Values = data.map(d => d.pc1);
      const pc2Values = data.map(d => d.pc2);

      const meanPC1 = pc1Values.reduce((sum, v) => sum + v, 0) / pc1Values.length;
      const meanPC2 = pc2Values.reduce((sum, v) => sum + v, 0) / pc2Values.length;

      const variancePC1 = pc1Values.reduce((sum, v) => sum + (v - meanPC1) ** 2, 0) / Math.max(pc1Values.length - 1, 1);
      const variancePC2 = pc2Values.reduce((sum, v) => sum + (v - meanPC2) ** 2, 0) / Math.max(pc2Values.length - 1, 1);

      const stdPC1 = Math.sqrt(variancePC1);
      const stdPC2 = Math.sqrt(variancePC2);

      // Determine color
      let color = '#8b5cf6';
      if (colorBy === 'cell_line' || colorBy === 'compound') {
        color = getColor(data[0]);
      } else if (colorBy === 'dose') {
        color = getDoseCategoryColor(groupName);
      } else if (colorBy === 'timepoint') {
        const timepoint = parseFloat(groupName);
        color = getTimepointColor(timepoint);
      }

      aggregated.push({
        groupName,
        meanPC1,
        meanPC2,
        stdPC1,
        stdPC2,
        n: data.length,
        color,
      });
    });

    return aggregated;
  }, [groupedData, colorBy]);

  // Calculate scale factors for converting data units to pixels in variance ellipses
  const ellipseScaleFactors = useMemo(() => {
    if (scatterData.length === 0) {
      return { pixelsPerUnitPC1: 1, pixelsPerUnitPC2: 1 };
    }

    // Use FULL scatter data range (all individual wells), not just aggregated means
    // The chart axes are scaled to fit all individual points
    const allPC1Values = scatterData.map(d => d.pc1);
    const allPC2Values = scatterData.map(d => d.pc2);
    const dataRangePC1 = Math.max(...allPC1Values) - Math.min(...allPC1Values);
    const dataRangePC2 = Math.max(...allPC2Values) - Math.min(...allPC2Values);

    // Chart dimensions (from tooltip coordinate calibration)
    const chartWidthPx = 1233 - 371;   // 862 pixels
    const chartHeightPx = 360 - 21;    // 339 pixels

    // Calculate pixels per data unit
    return {
      pixelsPerUnitPC1: chartWidthPx / dataRangePC1,
      pixelsPerUnitPC2: chartHeightPx / dataRangePC2,
    };
  }, [scatterData]);

  // Dose trajectory data: mean positions by (compound, cell_line, timepoint, dose)
  const doseTrajectories = useMemo(() => {
    if (!scatterData || scatterData.length === 0 || !showDoseTrajectories) return [];

    // Group by compound, cell_line, and timepoint
    const trajectories: Array<{
      key: string;
      compound: string;
      cell_line: string;
      timepoint_h: number;
      color: string;
      points: Array<{ dose: number; pc1: number; pc2: number; n: number }>;
    }> = [];

    // Group wells by (compound, cell_line, timepoint, dose)
    const grouped = new Map<string, typeof scatterData>();
    scatterData.forEach(item => {
      // Skip sentinels for trajectories
      if (item.is_sentinel) return;

      const key = `${item.compound}_${item.cell_line}_${item.timepoint_h}`;
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)!.push(item);
    });

    // For each trajectory group, aggregate by dose
    grouped.forEach((wells, key) => {
      const [compound, cell_line, timepoint_h] = key.split('_');

      // Group by dose and compute means
      const doseGroups = new Map<number, typeof wells>();
      wells.forEach(w => {
        if (!doseGroups.has(w.dose_uM)) {
          doseGroups.set(w.dose_uM, []);
        }
        doseGroups.get(w.dose_uM)!.push(w);
      });

      // Compute mean PC1/PC2 at each dose
      const points = Array.from(doseGroups.entries()).map(([dose, doseWells]) => {
        const meanPC1 = doseWells.reduce((sum, w) => sum + w.pc1, 0) / doseWells.length;
        const meanPC2 = doseWells.reduce((sum, w) => sum + w.pc2, 0) / doseWells.length;
        return { dose, pc1: meanPC1, pc2: meanPC2, n: doseWells.length };
      });

      // Sort by dose to create trajectory
      points.sort((a, b) => a.dose - b.dose);

      // Need at least 2 dose points to draw a trajectory
      if (points.length >= 2) {
        trajectories.push({
          key,
          compound,
          cell_line,
          timepoint_h: parseFloat(timepoint_h),
          color: getCompoundColor(compound),
          points,
        });
      }
    });

    return trajectories;
  }, [scatterData, showDoseTrajectories]);

  // Biplot arrow data: scale loadings for visibility
  const biplotData = useMemo(() => {
    if (!pcaData || !pcaData.loadings || !showBiplotArrows) return [];

    // Scale factor to make arrows visible (adjust based on typical PC score range)
    const scaleFactor = 3.0;

    return pcaData.channels.map((channel, idx) => ({
      channel,
      pc1: pcaData.loadings[idx][0] * scaleFactor,
      pc2: pcaData.loadings[idx][1] * scaleFactor,
      loading_pc1: pcaData.loadings[idx][0],
      loading_pc2: pcaData.loadings[idx][1],
    }));
  }, [pcaData, showBiplotArrows]);

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
                    {date} ({design.design_id.slice(0, 8)}) - {design.well_count || '?'} wells{statusLabel}
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {(['cell_line', 'compound', 'dose', 'timepoint'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => {
                    setColorBy(option);
                    // Reset all filters when changing color mode
                    setSelectedCellLines(new Set());
                    setSelectedCompounds(new Set());
                    setSelectedDoseCategories(new Set());
                    setSelectedTimepoints(new Set());
                  }}
                  className={`
                    py-2 px-4 rounded-lg text-sm font-medium transition-all capitalize
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


        {/* Sentinel Filter Toggle */}
        <div className="flex items-center gap-3 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <input
            type="checkbox"
            id="sentinel-toggle"
            checked={showOnlySentinels}
            onChange={(e) => setShowOnlySentinels(e.target.checked)}
            className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-violet-600 focus:ring-2 focus:ring-violet-500 focus:ring-offset-0"
          />
          <label htmlFor="sentinel-toggle" className="flex-1 cursor-pointer">
            <div className="text-sm font-semibold text-white">Highlight Sentinels</div>
            <div className="text-xs text-slate-400 mt-1">
              Grey out experimental wells to focus on QC sentinels (tight clusters = low variance)
            </div>
          </label>
          {showOnlySentinels && (
            <div className="px-3 py-1 bg-amber-500/20 border border-amber-500/50 rounded-full text-xs font-semibold text-amber-400">
              QC MODE
            </div>
          )}
        </div>

        {/* Dose Trajectory Toggle */}
        <div className="flex items-center gap-3 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <input
            type="checkbox"
            id="trajectory-toggle"
            checked={showDoseTrajectories}
            onChange={(e) => setShowDoseTrajectories(e.target.checked)}
            className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-violet-600 focus:ring-2 focus:ring-violet-500 focus:ring-offset-0"
          />
          <label htmlFor="trajectory-toggle" className="flex-1 cursor-pointer">
            <div className="text-sm font-semibold text-white">Show Dose Trajectories</div>
            <div className="text-xs text-slate-400 mt-1">
              Draw arrows showing path through morphology space as dose increases (vehicle → low → mid → high)
            </div>
          </label>
          {showDoseTrajectories && (
            <div className="px-3 py-1 bg-blue-500/20 border border-blue-500/50 rounded-full text-xs font-semibold text-blue-400">
              TRAJECTORIES
            </div>
          )}
        </div>

        {/* Channel Selection for PCA */}
        <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <div className="text-sm font-semibold text-white mb-3">PCA Channel Selection</div>
          <div className="text-xs text-slate-400 mb-3">
            Select which morphology channels to include in PCA computation. Fewer channels = simpler interpretation.
          </div>
          <div className="flex flex-wrap gap-3">
            {ALL_CHANNELS.map((channel) => (
              <label
                key={channel}
                className="flex items-center gap-2 cursor-pointer bg-slate-800 hover:bg-slate-700 rounded-lg px-3 py-2 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedChannels.includes(channel)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedChannels([...selectedChannels, channel]);
                    } else {
                      // Require at least 2 channels for PCA
                      if (selectedChannels.length > 2) {
                        setSelectedChannels(selectedChannels.filter(c => c !== channel));
                      }
                    }
                  }}
                  className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-violet-600 focus:ring-2 focus:ring-violet-500 focus:ring-offset-0"
                />
                <span className="text-sm font-medium text-white capitalize">{channel}</span>
              </label>
            ))}
          </div>
          {selectedChannels.length < ALL_CHANNELS.length && (
            <div className="mt-3 px-3 py-2 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs text-blue-300">
              Using {selectedChannels.length}/{ALL_CHANNELS.length} channels: {selectedChannels.join(', ').toUpperCase()}
            </div>
          )}
        </div>

        {/* Biplot Arrows Toggle */}
        <div className="flex items-center gap-3 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <input
            type="checkbox"
            id="biplot-toggle"
            checked={showBiplotArrows}
            onChange={(e) => setShowBiplotArrows(e.target.checked)}
            className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-violet-600 focus:ring-2 focus:ring-violet-500 focus:ring-offset-0"
          />
          <label htmlFor="biplot-toggle" className="flex-1 cursor-pointer">
            <div className="text-sm font-semibold text-white">Show Biplot Arrows</div>
            <div className="text-xs text-slate-400 mt-1">
              Overlay arrows showing which channels contribute to PC1 and PC2 (longer = stronger contribution)
            </div>
          </label>
          {showBiplotArrows && (
            <div className="px-3 py-1 bg-green-500/20 border border-green-500/50 rounded-full text-xs font-semibold text-green-400">
              BIPLOT
            </div>
          )}
        </div>

        {/* Info Card */}
        {pcaData && (
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xl font-bold text-violet-400">
                  {pcaData.n_wells}
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Wells</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">
                  {pcaData.channels.length}
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Channels</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">2</div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">Components</div>
              </div>
              <div>
                <div className="text-xl font-bold text-violet-400">
                  {(pcaData.variance_explained.total * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-1">
                  Variance Explained
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  PC1: {(pcaData.variance_explained.pc1 * 100).toFixed(1)}%, PC2: {(pcaData.variance_explained.pc2 * 100).toFixed(1)}%
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
          <div className="flex gap-4 items-center">
            <div className="flex-1">
              <ResponsiveContainer width="100%" height={500}>
                <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                  <XAxis
                    type="number"
                    dataKey="pc1"
                    name="PC1"
                    stroke="#94a3b8"
                    label={{ value: 'PC1', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
                  />
                  <YAxis
                    type="number"
                    dataKey="pc2"
                    name="PC2"
                    stroke="#94a3b8"
                    label={{ value: 'PC2', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
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
                                <span className="text-white font-medium">{doseCategory}</span>
                              </div>
                              <div className="flex justify-between gap-4">
                                <span className="text-slate-400">Timepoint:</span>
                                <span className="text-white font-medium">{data.timepoint_h}h</span>
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

                  {groupedData
                    // Sort so unselected (greyed out) items render first, selected items render last (on top)
                    .sort(([groupNameA], [groupNameB]) => {
                      const isBackgroundA = groupNameA === 'Background (non-sentinel)';
                      const isBackgroundB = groupNameB === 'Background (non-sentinel)';

                      // Background always renders first (bottom layer)
                      if (isBackgroundA && !isBackgroundB) return -1;
                      if (!isBackgroundA && isBackgroundB) return 1;

                      // If in sentinel mode, all sentinel groups render on top (after background)
                      // No need for further sorting by selection in sentinel mode
                      if (showOnlySentinels) {
                        return 0;  // Keep original order for sentinels
                      }

                      // Normal mode: check if items are selected
                      let isSelectedA = true;
                      let isSelectedB = true;

                      if (colorBy === 'cell_line' && selectedCellLines.size > 0) {
                        isSelectedA = selectedCellLines.has(groupNameA);
                        isSelectedB = selectedCellLines.has(groupNameB);
                      } else if (colorBy === 'compound' && selectedCompounds.size > 0) {
                        isSelectedA = selectedCompounds.has(groupNameA);
                        isSelectedB = selectedCompounds.has(groupNameB);
                      } else if (colorBy === 'dose' && selectedDoseCategories.size > 0) {
                        isSelectedA = selectedDoseCategories.has(groupNameA);
                        isSelectedB = selectedDoseCategories.has(groupNameB);
                      } else if (colorBy === 'timepoint' && selectedTimepoints.size > 0) {
                        isSelectedA = selectedTimepoints.has(groupNameA);
                        isSelectedB = selectedTimepoints.has(groupNameB);
                      }

                      // Then unselected items
                      if (!isSelectedA && isSelectedB) return -1;
                      if (isSelectedA && !isSelectedB) return 1;

                      // Keep original order for items in same category
                      return 0;
                    })
                    .map(([groupName, data], idx) => {
                    // Check if this is the background (non-sentinel) layer
                    const isBackground = groupName === 'Background (non-sentinel)';

                    // Check if this item is selected when a filter is active
                    let isSelectedGroup = true;
                    if (colorBy === 'cell_line' && selectedCellLines.size > 0) {
                      isSelectedGroup = selectedCellLines.has(groupName);
                    } else if (colorBy === 'compound' && selectedCompounds.size > 0) {
                      isSelectedGroup = selectedCompounds.has(groupName);
                    } else if (colorBy === 'dose' && selectedDoseCategories.size > 0) {
                      isSelectedGroup = selectedDoseCategories.has(groupName);
                    } else if (colorBy === 'timepoint' && selectedTimepoints.size > 0) {
                      isSelectedGroup = selectedTimepoints.has(groupName);
                    }

                    let fillColor = '#8b5cf6';
                    let fillOpacity = 0.8;

                    if (isBackground) {
                      // Grey out non-sentinel wells - make VERY faint so sentinels show on top
                      fillColor = '#64748b';  // slate grey
                      fillOpacity = 0.03;     // extremely transparent
                    } else if (!isSelectedGroup) {
                      // Grey out non-selected items
                      fillColor = '#64748b';  // slate grey
                      fillOpacity = 0.1;      // very transparent
                    } else {
                      // Normal coloring for selected items - make them more opaque
                      if (colorBy === 'cell_line' || colorBy === 'compound') {
                        fillColor = getColor(data[0]);
                      } else if (colorBy === 'dose') {
                        fillColor = getDoseCategoryColor(groupName);
                      } else if (colorBy === 'timepoint') {
                        const timepoint = parseFloat(groupName);
                        fillColor = getTimepointColor(timepoint);
                      }
                      fillOpacity = 0.8;  // More opaque for selected items
                    }

                    return (
                      <Scatter
                        key={groupName}
                        name={groupName}
                        data={data}
                        fill={fillColor}
                        fillOpacity={fillOpacity}
                        legendType="none"
                        shape={(props: any) => {
                          const { cx, cy } = props;
                          // Make background dots much smaller
                          const radius = isBackground ? 2 : 4;
                          return (
                            <circle
                              cx={cx}
                              cy={cy}
                              r={radius}
                              fill={fillColor}
                              fillOpacity={fillOpacity}
                            />
                          );
                        }}
                      />
                    );
                  })}

                  {/* Dose Trajectories - render as connected scatter with lines */}
                  {showDoseTrajectories && doseTrajectories.map((trajectory, trajIdx) => {
                    // Create scatter data with all trajectory points
                    const trajData = trajectory.points.map((p, idx) => ({
                      pc1: p.pc1,
                      pc2: p.pc2,
                      dose: p.dose,
                      pointIndex: idx,
                      isLast: idx === trajectory.points.length - 1
                    }));

                    return (
                      <Scatter
                        key={`trajectory-${trajectory.key}`}
                        name={`${trajectory.compound} ${trajectory.cell_line} ${trajectory.timepoint_h}h`}
                        data={trajData}
                        fill={trajectory.color}
                        line={{ stroke: trajectory.color, strokeWidth: 2, strokeDasharray: '5 3' }}
                        lineType="joint"
                        legendType="none"
                        shape={(props: any) => {
                          const { cx, cy, payload } = props;

                          // Draw a small circle at each dose point
                          return (
                            <g>
                              <circle
                                cx={cx}
                                cy={cy}
                                r={4}
                                fill={trajectory.color}
                                fillOpacity={0.8}
                                stroke="white"
                                strokeWidth={1}
                              />
                              {/* Add arrowhead at the last point */}
                              {payload.isLast && (
                                <polygon
                                  points={`${cx},${cy-8} ${cx-5},${cy-3} ${cx+5},${cy-3}`}
                                  fill={trajectory.color}
                                  fillOpacity={0.8}
                                />
                              )}
                            </g>
                          );
                        }}
                      />
                    );
                  })}

                  {/* Biplot Arrows - show channel contributions to PCs */}
                  {showBiplotArrows && biplotData.length > 0 && biplotData.map((arrow, idx) => {
                    // Create line data from origin to arrow tip
                    const lineData = [
                      { pc1: 0, pc2: 0 },  // Origin
                      { pc1: arrow.pc1, pc2: arrow.pc2 }  // Arrow tip
                    ];

                    const channelColors: Record<string, string> = {
                      er: '#ef4444',        // red
                      mito: '#22c55e',      // green
                      nucleus: '#3b82f6',   // blue
                      actin: '#f59e0b',     // amber
                      rna: '#8b5cf6',       // violet
                    };
                    const arrowColor = channelColors[arrow.channel] || '#64748b';

                    return (
                      <Scatter
                        key={`biplot-${arrow.channel}`}
                        name={`${arrow.channel.toUpperCase()} Loading`}
                        data={lineData}
                        fill={arrowColor}
                        line={{ stroke: arrowColor, strokeWidth: 3, strokeOpacity: 0.8 }}
                        lineType="joint"
                        legendType="none"
                        shape={(props: any) => {
                          const { cx, cy, index } = props;

                          // Only draw at the arrow tip (index 1)
                          if (index !== 1) return null;

                          // Calculate angle for arrowhead
                          const angle = Math.atan2(arrow.pc2, arrow.pc1);
                          const arrowSize = 8;

                          return (
                            <g>
                              {/* Arrow tip circle */}
                              <circle
                                cx={cx}
                                cy={cy}
                                r={5}
                                fill={arrowColor}
                                stroke="white"
                                strokeWidth={2}
                              />
                              {/* Channel label */}
                              <text
                                x={cx + 12}
                                y={cy + 4}
                                fill={arrowColor}
                                fontSize="12"
                                fontWeight="bold"
                                style={{ textShadow: '0 0 3px #000, 0 0 3px #000' }}
                              >
                                {arrow.channel.toUpperCase()}
                              </text>
                            </g>
                          );
                        }}
                      />
                    );
                  })}
                </ScatterChart>
              </ResponsiveContainer>
            </div>

            {/* Custom Legend on the Right */}
            <div className="bg-slate-900/50 rounded px-2 py-1.5 border border-slate-700" style={{ marginTop: '-50px' }}>
              <div className="text-xs font-semibold text-violet-400 mb-0.5">Legend (multi-select)</div>
              <div className="space-y-px">
                {(() => {
                  // If coloring by compound, group by color families
                  if (colorBy === 'compound') {
                    const compoundGroups = [
                      ['tBHQ', 'H2O2'],
                      ['tunicamycin', 'thapsigargin'],
                      ['CCCP', 'oligomycin'],
                      ['etoposide', 'MG132'],
                      ['nocodazole', 'paclitaxel'],
                      ['DMSO']
                    ];

                    return compoundGroups.flatMap((group, groupIdx) =>
                      group.map(compound => {
                        const dataEntry = groupedData.find(([name]) => name === compound);
                        if (!dataEntry) return null;
                        const [groupName, data] = dataEntry;
                        const fillColor = getColor(data[0]);
                        const isSelected = selectedCompounds.has(groupName);

                        return (
                          <div
                            key={groupName}
                            className={`flex items-center gap-1.5 cursor-pointer hover:bg-slate-800 px-1 py-0.5 rounded transition-colors ${isSelected ? 'font-semibold' : ''}`}
                            onClick={() => {
                              const newSet = new Set(selectedCompounds);
                              if (isSelected) {
                                newSet.delete(groupName);
                              } else {
                                newSet.add(groupName);
                              }
                              setSelectedCompounds(newSet);
                            }}
                          >
                            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: fillColor }}></div>
                            <span className="text-xs text-slate-300">{groupName}</span>
                          </div>
                        );
                      })
                    );
                  }

                  // Otherwise, display in order
                  return groupedData.map(([groupName, data]) => {
                    // Skip background layer from legend
                    if (groupName === 'Background (non-sentinel)') return null;

                    let fillColor = '#8b5cf6';
                    let isSelected = false;
                    let handleClick = () => {};

                    if (colorBy === 'cell_line') {
                      fillColor = getColor(data[0]);
                      isSelected = selectedCellLines.has(groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedCellLines);
                        if (isSelected) {
                          newSet.delete(groupName);
                        } else {
                          newSet.add(groupName);
                        }
                        setSelectedCellLines(newSet);
                      };
                    } else if (colorBy === 'dose') {
                      fillColor = getDoseCategoryColor(groupName);
                      isSelected = selectedDoseCategories.has(groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedDoseCategories);
                        if (isSelected) {
                          newSet.delete(groupName);
                        } else {
                          newSet.add(groupName);
                        }
                        setSelectedDoseCategories(newSet);
                      };
                    } else if (colorBy === 'timepoint') {
                      const timepoint = parseFloat(groupName);
                      fillColor = getTimepointColor(timepoint);
                      isSelected = selectedTimepoints.has(groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedTimepoints);
                        if (isSelected) {
                          newSet.delete(groupName);
                        } else {
                          newSet.add(groupName);
                        }
                        setSelectedTimepoints(newSet);
                      };
                    }

                    return (
                      <div
                        key={groupName}
                        className={`flex items-center gap-1.5 cursor-pointer hover:bg-slate-800 px-1 py-0.5 rounded transition-colors ${isSelected ? 'font-semibold' : ''}`}
                        onClick={handleClick}
                      >
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: fillColor }}></div>
                        <span className="text-xs text-slate-300">{groupName}</span>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          </div>

          {/* Dose Trajectory Info */}
          {showDoseTrajectories && doseTrajectories.length > 0 && (
            <div className="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3 border border-slate-700">
              <div className="font-semibold text-blue-400 mb-1">
                📈 Showing {doseTrajectories.length} dose trajectories
              </div>
              <div>
                Each arrow shows the path through morphology space as dose increases.
                Trajectory = mean position at each dose level (vehicle → low → mid → high).
                Color indicates compound. Filter by cell line or timepoint to reduce clutter.
              </div>
            </div>
          )}

          {/* Biplot Arrows Info */}
          {showBiplotArrows && biplotData.length > 0 && (
            <div className="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3 border border-slate-700">
              <div className="font-semibold text-green-400 mb-1">
                🎯 Biplot Loadings: Channel Contributions to Principal Components
              </div>
              <div className="mb-2">
                Each arrow shows how a morphology channel contributes to PC1 (horizontal) and PC2 (vertical).
                <strong> Arrow direction</strong> = which PC the channel drives.
                <strong> Arrow length</strong> = strength of contribution.
              </div>
              <div className="flex flex-wrap gap-2">
                {biplotData.map((arrow) => {
                  const channelColors: Record<string, string> = {
                    er: '#ef4444', mito: '#22c55e', nucleus: '#3b82f6',
                    actin: '#f59e0b', rna: '#8b5cf6'
                  };
                  const color = channelColors[arrow.channel];
                  return (
                    <div key={arrow.channel} className="flex items-center gap-2 bg-slate-800 rounded px-2 py-1">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }}></div>
                      <span style={{ color }} className="font-semibold uppercase text-xs">
                        {arrow.channel}
                      </span>
                      <span className="text-slate-500 text-xs">
                        ({arrow.loading_pc1 >= 0 ? '+' : ''}{arrow.loading_pc1.toFixed(2)} PC1,
                        {arrow.loading_pc2 >= 0 ? ' +' : ' '}{arrow.loading_pc2.toFixed(2)} PC2)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Each point represents a well. PC1 and PC2 capture the dominant
            modes of morphological variation. Clustering indicates similar cellular phenotypes, while
            separation suggests distinct stress responses.
            {colorBy === 'cell_line' && ' Color indicates cell line.'}
            {colorBy === 'compound' && ' Color indicates compound - compounds with similar colors have similar morphological profiles.'}
            {colorBy === 'dose' && ' Color indicates dose level - progression from green (low) to red (high) shows dose-dependent changes.'}
            {colorBy === 'timepoint' && ' Color indicates timepoint - green (early, 12h) to red (late, 48h+) shows temporal progression from adaptive to damage phenotypes.'}
            {showOnlySentinels ? (
              <span className="text-amber-400">
                {' '}<strong>QC Mode:</strong> Sentinel wells are highlighted in color while experimental wells are greyed out.
                Sentinels have identical conditions across all plates - tight clustering indicates low technical variance.
                Wide spread indicates day/operator/plate effects - investigate in Variance Analysis tab.
              </span>
            ) : (
              <span>
                {' '}Sentinels should cluster tightly if measurement variance is low. Use "Show Only Sentinels" to highlight QC well clustering.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Aggregated Variance Blob Chart */}
      {selectedDesignId && !loading && !error && aggregatedData.length > 0 && (
        <div className={`bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all ${
          isLiveMode
            ? 'border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
            : 'border-slate-700'
        }`}>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                Aggregated PCA (Mean ± Variance)
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                Each blob represents mean position with variance in both PC dimensions
              </p>
            </div>
          </div>

          <div className="flex gap-4 items-center">
            <div className="flex-1">
              <ResponsiveContainer width="100%" height={500}>
                <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                  <XAxis
                    type="number"
                    dataKey="meanPC1"
                    name="PC1"
                    stroke="#94a3b8"
                    label={{ value: 'PC1', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
                    domain={(() => {
                      // Calculate domain to include full ellipse extent (mean ± 2*std)
                      const minExtent = Math.min(...aggregatedData.map(d => d.meanPC1 - 2 * d.stdPC1));
                      const maxExtent = Math.max(...aggregatedData.map(d => d.meanPC1 + 2 * d.stdPC1));
                      return [minExtent, maxExtent];
                    })()}
                    tickFormatter={(value) => value.toFixed(2)}
                  />
                  <YAxis
                    type="number"
                    dataKey="meanPC2"
                    name="PC2"
                    stroke="#94a3b8"
                    label={{ value: 'PC2', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
                    domain={(() => {
                      // Calculate domain to include full ellipse extent (mean ± 2*std)
                      const minExtent = Math.min(...aggregatedData.map(d => d.meanPC2 - 2 * d.stdPC2));
                      const maxExtent = Math.max(...aggregatedData.map(d => d.meanPC2 + 2 * d.stdPC2));
                      return [minExtent, maxExtent];
                    })()}
                    tickFormatter={(value) => value.toFixed(2)}
                  />
                  <ZAxis type="category" dataKey="groupName" name="Group" />
                  <Tooltip
                    shared={false}
                    cursor={{ strokeDasharray: '3 3' }}
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #475569',
                      borderRadius: '8px',
                      color: '#e2e8f0',
                    }}
                    content={({ active, payload, label, coordinate }) => {
                      if (active && payload && payload.length) {
                        // Find all "Group" items (from ZAxis) which represent our scatter series
                        const groupItems = payload.filter(p => p.name === "Group");


                        if (groupItems.length === 0) {
                          return null;
                        }

                        // If there's only one, use it
                        let selectedGroupItem = groupItems[0];

                        // If there are multiple, find which one is rendered on top (based on our sort order)
                        if (groupItems.length > 1) {
                          // Check if any filter is active
                          const hasActiveFilter =
                            (colorBy === 'cell_line' && selectedCellLines.size > 0) ||
                            (colorBy === 'compound' && selectedCompounds.size > 0) ||
                            (colorBy === 'dose' && selectedDoseCategories.size > 0) ||
                            (colorBy === 'timepoint' && selectedTimepoints.size > 0);

                          if (hasActiveFilter) {
                            // Filter is active - find which items are selected
                            const groupNameToCheck = (name: string) => {
                              if (colorBy === 'cell_line') return selectedCellLines.has(name);
                              if (colorBy === 'compound') return selectedCompounds.has(name);
                              if (colorBy === 'dose') return selectedDoseCategories.has(name);
                              if (colorBy === 'timepoint') return selectedTimepoints.has(name);
                              return false;
                            };

                            const selectedItems = groupItems.filter(item => groupNameToCheck(item.payload?.groupName));
                            if (selectedItems.length > 0) {
                              // If multiple selected items, find closest to mouse
                              if (selectedItems.length > 1 && coordinate) {
                                selectedGroupItem = selectedItems[0];
                                let minDist = Infinity;
                                selectedItems.forEach(item => {
                                  const itemData = aggregatedData.find(d => d.groupName === item.payload?.groupName);
                                  if (itemData && coordinate.x !== undefined && coordinate.y !== undefined) {
                                    // Calculate distance from mouse to item position (rough estimate)
                                    const dx = Math.abs(coordinate.x - 400);  // Rough approximation
                                    const dy = Math.abs(coordinate.y - 250);
                                    const dist = Math.sqrt(dx * dx + dy * dy);
                                    if (dist < minDist) {
                                      minDist = dist;
                                      selectedGroupItem = item;
                                    }
                                  }
                                });
                              } else {
                                selectedGroupItem = selectedItems[0];
                              }
                            }
                          } else {
                            // No filter active - Recharts gives us ALL scatter points in payload
                            // Calculate which compound is closest to the mouse cursor
                            if (coordinate && coordinate.x !== undefined && coordinate.y !== undefined) {
                              // Estimate the chart dimensions and data range
                              // The chart is 500px tall with margins (top: 20, bottom: 60)
                              // The chart is responsive width but typically around 800-1000px with margins (left: 60, right: 20)

                              // Get the range of PC1 and PC2 values
                              const pc1Values = groupItems.map(g => g.payload?.meanPC1 || 0);
                              const pc2Values = groupItems.map(g => g.payload?.meanPC2 || 0);

                              const minPC1 = Math.min(...pc1Values);
                              const maxPC1 = Math.max(...pc1Values);
                              const minPC2 = Math.min(...pc2Values);
                              const maxPC2 = Math.max(...pc2Values);

                              // Estimate chart area by calculating from known positions
                              // X-axis: DMSO at PC1=0.2112 (max) appears at pixel x=1233
                              //         nocodazole at PC1=-0.0337 appears at pixel x=601
                              // Y-axis: tunicamycin at PC2=0.189 (max) appears at pixel y≈21
                              //         DMSO at PC2=-0.141 appears at pixel y=360
                              const chartLeft = 371;   // calculated: 1233 - 862
                              const chartRight = 1233; // from DMSO position
                              const chartTop = 21;     // from tunicamycin position
                              const chartBottom = 360; // from DMSO position (not 440 - margin is applied separately)

                              // Convert mouse coordinates to data coordinates (approximate)
                              const mouseDataX = minPC1 + ((coordinate.x - chartLeft) / (chartRight - chartLeft)) * (maxPC1 - minPC1);
                              const mouseDataY = maxPC2 - ((coordinate.y - chartTop) / (chartBottom - chartTop)) * (maxPC2 - minPC2);

                              // Find the closest compound
                              let minDistance = Infinity;
                              let closestItem = groupItems[0];

                              groupItems.forEach(item => {
                                const pc1 = item.payload?.meanPC1 || 0;
                                const pc2 = item.payload?.meanPC2 || 0;
                                const distance = Math.sqrt(
                                  Math.pow(pc1 - mouseDataX, 2) +
                                  Math.pow(pc2 - mouseDataY, 2)
                                );

                                if (distance < minDistance) {
                                  minDistance = distance;
                                  closestItem = item;
                                }
                              });

                              selectedGroupItem = closestItem;
                            } else {
                              selectedGroupItem = groupItems[groupItems.length - 1];
                            }
                          }
                        }

                        const groupName = selectedGroupItem?.payload?.groupName;

                        // Use the groupName directly from the payload
                        const matchedItem = aggregatedData.find(d => d.groupName === groupName);

                        if (!matchedItem) {
                          return null;
                        }

                        return (
                          <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
                            <div className="font-semibold text-white mb-2">{matchedItem.groupName}</div>
                            <div className="space-y-1 text-xs">
                              <div className="flex justify-between gap-4">
                                <span className="text-slate-400">Mean PC1:</span>
                                <span className="text-white font-mono">{matchedItem.meanPC1.toFixed(2)} ± {matchedItem.stdPC1.toFixed(2)}</span>
                              </div>
                              <div className="flex justify-between gap-4">
                                <span className="text-slate-400">Mean PC2:</span>
                                <span className="text-white font-mono">{matchedItem.meanPC2.toFixed(2)} ± {matchedItem.stdPC2.toFixed(2)}</span>
                              </div>
                              <div className="border-t border-slate-700 my-2"></div>
                              <div className="flex justify-between gap-4">
                                <span className="text-slate-400">Replicates:</span>
                                <span className="text-white font-medium">n = {matchedItem.n}</span>
                              </div>
                            </div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />

                  {/* Render variance blobs as circles + error bars */}
                  {[...aggregatedData]
                    // Sort a COPY so we don't mutate the original array (which causes React issues)
                    .sort((itemA, itemB) => {
                      // Check if items are selected
                      let isSelectedA = true;
                      let isSelectedB = true;

                      if (colorBy === 'cell_line' && selectedCellLines.size > 0) {
                        isSelectedA = selectedCellLines.has(itemA.groupName);
                        isSelectedB = selectedCellLines.has(itemB.groupName);
                      } else if (colorBy === 'compound' && selectedCompounds.size > 0) {
                        isSelectedA = selectedCompounds.has(itemA.groupName);
                        isSelectedB = selectedCompounds.has(itemB.groupName);
                      } else if (colorBy === 'dose' && selectedDoseCategories.size > 0) {
                        isSelectedA = selectedDoseCategories.has(itemA.groupName);
                        isSelectedB = selectedDoseCategories.has(itemB.groupName);
                      } else if (colorBy === 'timepoint' && selectedTimepoints.size > 0) {
                        isSelectedA = selectedTimepoints.has(itemA.groupName);
                        isSelectedB = selectedTimepoints.has(itemB.groupName);
                      }

                      // Unselected items render first (return -1), selected items render last (return 1)
                      if (!isSelectedA && isSelectedB) return -1;
                      if (isSelectedA && !isSelectedB) return 1;

                      // Keep original order for items in same category
                      return 0;
                    })
                    .map((item, idx) => {
                    // Check if this item is selected when a filter is active
                    let isSelectedGroup = true;
                    if (colorBy === 'cell_line' && selectedCellLines.size > 0) {
                      isSelectedGroup = selectedCellLines.has(item.groupName);
                    } else if (colorBy === 'compound' && selectedCompounds.size > 0) {
                      isSelectedGroup = selectedCompounds.has(item.groupName);
                    } else if (colorBy === 'dose' && selectedDoseCategories.size > 0) {
                      isSelectedGroup = selectedDoseCategories.has(item.groupName);
                    } else if (colorBy === 'timepoint' && selectedTimepoints.size > 0) {
                      isSelectedGroup = selectedTimepoints.has(item.groupName);
                    }

                    const displayColor = isSelectedGroup ? item.color : '#64748b'; // grey out if not selected
                    const displayOpacity = isSelectedGroup ? 0.5 : 0.08;

                    // Create a factory function to avoid closure issues
                    const createShapeRenderer = (currentItem: typeof item, currentColor: string, currentIsSelected: boolean) => {
                      return (props: any) => {
                        const { cx, cy, payload } = props;
                        // Draw variance circle (2 SD radius)
                        const radiusX = currentItem.stdPC1 * 2;  // 2 standard deviations in data units
                        const radiusY = currentItem.stdPC2 * 2;

                        // Convert from data units to pixels using calculated scale factors
                        const ellipseRadiusX = Math.abs(radiusX) * ellipseScaleFactors.pixelsPerUnitPC1;
                        const ellipseRadiusY = Math.abs(radiusY) * ellipseScaleFactors.pixelsPerUnitPC2;

                        return (
                          <g data-groupname={currentItem.groupName}>
                            {/* Variance ellipse */}
                            <ellipse
                              cx={cx}
                              cy={cy}
                              rx={ellipseRadiusX}
                              ry={ellipseRadiusY}
                              fill={currentColor}
                              fillOpacity={currentIsSelected ? 0.3 : 0.05}
                              stroke={currentColor}
                              strokeWidth={currentIsSelected ? 2 : 1}
                              strokeDasharray="3 3"
                              strokeOpacity={currentIsSelected ? 0.8 : 0.3}
                            />
                            {/* Center point */}
                            <circle
                              cx={cx}
                              cy={cy}
                              r={currentIsSelected ? 6 : 4}
                              fill={currentColor}
                              fillOpacity={currentIsSelected ? 1 : 0.5}
                              stroke="#fff"
                              strokeWidth={2}
                            />
                          </g>
                        );
                      };
                    };

                    // Pass the item directly in an array - don't spread to avoid reference issues
                    return (
                      <Scatter
                        key={`${item.groupName}-${idx}`}
                        name={item.groupName}
                        data={[item]}
                        fill={displayColor}
                        fillOpacity={displayOpacity}
                        legendType="none"
                        shape={createShapeRenderer(item, displayColor, isSelectedGroup)}
                      />
                    );
                  })}
                </ScatterChart>
              </ResponsiveContainer>
            </div>

            {/* Custom Legend on the Right */}
            <div className="bg-slate-900/50 rounded px-2 py-1.5 border border-slate-700" style={{ marginTop: '-50px' }}>
              <div className="text-xs font-semibold text-violet-400 mb-0.5">Legend (multi-select)</div>
              <div className="space-y-px">
                {(() => {
                  // If coloring by compound, group by color families
                  if (colorBy === 'compound') {
                    const compoundGroups = [
                      ['tBHQ', 'H2O2'],
                      ['tunicamycin', 'thapsigargin'],
                      ['CCCP', 'oligomycin'],
                      ['etoposide', 'MG132'],
                      ['nocodazole', 'paclitaxel'],
                      ['DMSO']
                    ];

                    return compoundGroups.flatMap((group) =>
                      group.map(compound => {
                        const item = aggregatedData.find(d => d.groupName === compound);
                        if (!item) return null;
                        const isSelected = selectedCompounds.has(item.groupName);

                        return (
                          <div
                            key={item.groupName}
                            className={`flex items-center gap-1.5 cursor-pointer hover:bg-slate-800 px-1 py-0.5 rounded transition-colors ${isSelected ? 'font-semibold' : ''}`}
                            onClick={() => {
                              const newSet = new Set(selectedCompounds);
                              if (isSelected) {
                                newSet.delete(item.groupName);
                              } else {
                                newSet.add(item.groupName);
                              }
                              setSelectedCompounds(newSet);
                            }}
                          >
                            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }}></div>
                            <span className="text-xs text-slate-300">{item.groupName}</span>
                          </div>
                        );
                      })
                    );
                  }

                  // Otherwise, display in order
                  return aggregatedData.map((item) => {
                    let isSelected = false;
                    let handleClick = () => {};

                    if (colorBy === 'cell_line') {
                      isSelected = selectedCellLines.has(item.groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedCellLines);
                        if (isSelected) {
                          newSet.delete(item.groupName);
                        } else {
                          newSet.add(item.groupName);
                        }
                        setSelectedCellLines(newSet);
                      };
                    } else if (colorBy === 'dose') {
                      isSelected = selectedDoseCategories.has(item.groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedDoseCategories);
                        if (isSelected) {
                          newSet.delete(item.groupName);
                        } else {
                          newSet.add(item.groupName);
                        }
                        setSelectedDoseCategories(newSet);
                      };
                    } else if (colorBy === 'timepoint') {
                      isSelected = selectedTimepoints.has(item.groupName);
                      handleClick = () => {
                        const newSet = new Set(selectedTimepoints);
                        if (isSelected) {
                          newSet.delete(item.groupName);
                        } else {
                          newSet.add(item.groupName);
                        }
                        setSelectedTimepoints(newSet);
                      };
                    }

                    return (
                      <div
                        key={item.groupName}
                        className={`flex items-center gap-1.5 cursor-pointer hover:bg-slate-800 px-1 py-0.5 rounded transition-colors ${isSelected ? 'font-semibold' : ''}`}
                        onClick={handleClick}
                      >
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }}></div>
                        <span className="text-xs text-slate-300">{item.groupName}</span>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          </div>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Each colored blob shows the mean PC1/PC2 position (center dot) with a variance ellipse (dashed outline).
            The ellipse size represents ±2 standard deviations in each PC dimension.
            <strong className="text-green-400"> Tight ellipses</strong> indicate low replicate variance (good reproducibility).
            <strong className="text-orange-400"> Large ellipses</strong> indicate high variance (investigate technical factors).
            This view aggregates all {aggregatedData.reduce((sum, d) => sum + d.n, 0)} wells into {aggregatedData.length} mean positions.
          </div>
        </div>
      )}
    </div>
  );
};

export default MorphologyTab;
