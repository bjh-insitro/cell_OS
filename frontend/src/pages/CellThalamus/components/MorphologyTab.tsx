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
  const [selectedCellLine, setSelectedCellLine] = useState<string>('all');
  const [selectedCompound, setSelectedCompound] = useState<string>('all');
  const [selectedDoseCategory, setSelectedDoseCategory] = useState<string>('all');
  const [selectedTimepoint, setSelectedTimepoint] = useState<string>('all');
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
    const order = ['Vehicle (0 µM)', 'Low (≤1 µM)', 'Mid (1-10 µM)', 'High (10-100 µM)', 'Very High (>100 µM)'];
    return categories.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  }, [scatterData]);

  const uniqueTimepoints = useMemo(() =>
    Array.from(new Set(scatterData.map(item => item.timepoint_h))).sort((a, b) => a - b),
    [scatterData]
  );

  // Filter data based on selection (but don't filter sentinels - just grey them)
  const filteredPcaData = useMemo(() => {
    let filtered = scatterData;

    // Color-mode-specific filters (don't filter by sentinel - we'll handle that in color logic)
    if (colorBy === 'cell_line' && selectedCellLine !== 'all') {
      filtered = filtered.filter(item => item.cell_line === selectedCellLine);
    } else if (colorBy === 'compound' && selectedCompound !== 'all') {
      filtered = filtered.filter(item => item.compound === selectedCompound);
    } else if (colorBy === 'dose' && selectedDoseCategory !== 'all') {
      filtered = filtered.filter(item => getDoseCategory(item.dose_uM) === selectedDoseCategory);
    } else if (colorBy === 'timepoint' && selectedTimepoint !== 'all') {
      filtered = filtered.filter(item => item.timepoint_h === parseFloat(selectedTimepoint));
    }

    return filtered;
  }, [scatterData, colorBy, selectedCellLine, selectedCompound, selectedDoseCategory, selectedTimepoint]);

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
        const order = ['Vehicle (0 µM)', 'Low (≤1 µM)', 'Mid (1-10 µM)', 'High (10-100 µM)', 'Very High (>100 µM)'];
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {(['cell_line', 'compound', 'dose', 'timepoint'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => {
                    setColorBy(option);
                    // Reset all filters when changing color mode
                    setSelectedCellLine('all');
                    setSelectedCompound('all');
                    setSelectedDoseCategory('all');
                    setSelectedTimepoint('all');
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

        {colorBy === 'timepoint' && uniqueTimepoints.length > 0 && (
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Filter by Timepoint
            </label>
            <select
              value={selectedTimepoint}
              onChange={(e) => setSelectedTimepoint(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All Timepoints</option>
              {uniqueTimepoints.map((timepoint) => (
                <option key={timepoint} value={timepoint.toString()}>
                  {timepoint}h
                </option>
              ))}
            </select>
          </div>
        )}

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
              <Legend wrapperStyle={{ paddingTop: '20px' }} />

              {groupedData.map(([groupName, data], idx) => {
                // Check if this is the background (non-sentinel) layer
                const isBackground = groupName === 'Background (non-sentinel)';

                let fillColor = '#8b5cf6';
                let fillOpacity = 0.6;

                if (isBackground) {
                  // Grey out non-sentinel wells
                  fillColor = '#64748b';  // slate grey
                  fillOpacity = 0.15;     // very transparent
                } else {
                  // Normal coloring for sentinels (or all data if not in QC mode)
                  if (colorBy === 'cell_line' || colorBy === 'compound') {
                    fillColor = getColor(data[0]);
                  } else if (colorBy === 'dose') {
                    fillColor = getDoseCategoryColor(groupName);
                  } else if (colorBy === 'timepoint') {
                    const timepoint = parseFloat(groupName);
                    fillColor = getTimepointColor(timepoint);
                  }
                }

                return (
                  <Scatter
                    key={groupName}
                    name={groupName}
                    data={data}
                    fill={fillColor}
                    fillOpacity={fillOpacity}
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

          <ResponsiveContainer width="100%" height={500}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                type="number"
                dataKey="meanPC1"
                name="PC1"
                stroke="#94a3b8"
                label={{ value: 'Principal Component 1 (Mean)', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
              />
              <YAxis
                type="number"
                dataKey="meanPC2"
                name="PC2"
                stroke="#94a3b8"
                label={{ value: 'Principal Component 2 (Mean)', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
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
                    return (
                      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
                        <div className="font-semibold text-white mb-2">{data.groupName}</div>
                        <div className="space-y-1 text-xs">
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Mean PC1:</span>
                            <span className="text-white font-mono">{data.meanPC1.toFixed(2)} ± {data.stdPC1.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Mean PC2:</span>
                            <span className="text-white font-mono">{data.meanPC2.toFixed(2)} ± {data.stdPC2.toFixed(2)}</span>
                          </div>
                          <div className="border-t border-slate-700 my-2"></div>
                          <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Replicates:</span>
                            <span className="text-white font-medium">n = {data.n}</span>
                          </div>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />

              {/* Render variance blobs as circles + error bars */}
              {aggregatedData.map((item, idx) => (
                <Scatter
                  key={item.groupName}
                  name={item.groupName}
                  data={[item]}
                  fill={item.color}
                  fillOpacity={0.3}
                  shape={(props: any) => {
                    const { cx, cy } = props;
                    // Draw variance circle (2 SD radius)
                    const radiusX = item.stdPC1 * 2;
                    const radiusY = item.stdPC2 * 2;

                    return (
                      <g>
                        {/* Variance ellipse */}
                        <ellipse
                          cx={cx}
                          cy={cy}
                          rx={Math.abs(radiusX) * 10}  // Scale factor for visibility
                          ry={Math.abs(radiusY) * 10}
                          fill={item.color}
                          fillOpacity={0.2}
                          stroke={item.color}
                          strokeWidth={1.5}
                          strokeDasharray="3 3"
                        />
                        {/* Center point */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={5}
                          fill={item.color}
                          stroke="#fff"
                          strokeWidth={2}
                        />
                      </g>
                    );
                  }}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>

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
