/**
 * Tab 3: Dose-Response Explorer
 *
 * Interactive dose-response curves for compounds across cell lines
 */

import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ErrorBar } from 'recharts';
import { useDesigns, useDoseResponse, useResults } from '../hooks/useCellThalamusData';
import PlateMapPreview from './PlateMapPreview';

interface DoseResponseTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const DoseResponseTab: React.FC<DoseResponseTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: results, refetch: refetchResults } = useResults(selectedDesignId);

  const [selectedCompound, setSelectedCompound] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>('viability_pct');
  const [normalizedMetric, setNormalizedMetric] = useState<string>('viability_pct');
  const [isLiveMode, setIsLiveMode] = useState<boolean>(false);
  const [normalizedTimepoint, setNormalizedTimepoint] = useState<number>(12);
  const [selectedLines, setSelectedLines] = useState<Set<string>>(new Set()); // Stores "CellLine_Timepoint" e.g. "A549_12h"
  const [selectedCellLines, setSelectedCellLines] = useState<Set<string>>(new Set()); // For normalized chart

  // Get all designs including running ones for live mode
  const allDesigns = React.useMemo(() => designs || [], [designs]);

  // Get completed designs
  const completedDesigns = React.useMemo(() =>
    designs?.filter((d) => d.status === 'completed') || [],
    [designs]
  );

  // Check if selected design is currently running
  const isDesignRunning = React.useMemo(() => {
    if (!selectedDesignId || !designs) return false;
    const design = designs.find(d => d.design_id === selectedDesignId);
    return design?.status === 'running';
  }, [selectedDesignId, designs]);

  // Live polling: refetch results every 5 seconds when design is running
  React.useEffect(() => {
    if (isDesignRunning && selectedDesignId) {
      setIsLiveMode(true);

      // Initial fetch
      refetchResults();

      // Set up polling interval
      const intervalId = setInterval(() => {
        refetchResults();
      }, 5000); // Poll every 5 seconds

      return () => {
        clearInterval(intervalId);
      };
    } else {
      setIsLiveMode(false);
    }
  }, [isDesignRunning, selectedDesignId, refetchResults]);

  // Check if DMSO controls exist in results
  const hasDMSO = React.useMemo(() => {
    if (!results) return false;
    return results.some((r) => r.compound === 'DMSO');
  }, [results]);

  // Auto-switch to atp_signal if no DMSO and viability_pct is selected
  React.useEffect(() => {
    if (!hasDMSO && selectedMetric === 'viability_pct') {
      setSelectedMetric('atp_signal');
    }
  }, [hasDMSO, selectedMetric]);

  // Auto-switch normalized metric too
  React.useEffect(() => {
    if (!hasDMSO && normalizedMetric === 'viability_pct') {
      setNormalizedMetric('atp_signal');
    }
  }, [hasDMSO, normalizedMetric]);

  // Auto-select most recent design when tab loads
  React.useEffect(() => {
    if (!selectedDesignId && completedDesigns.length > 0) {
      // Select the first (most recent) completed design
      onDesignChange(completedDesigns[0].design_id);
    }
  }, [completedDesigns, selectedDesignId, onDesignChange]);

  // Extract unique values from results
  const compounds = React.useMemo(() =>
    Array.from(new Set(results?.map((r) => r.compound) || [])).filter((c) => c !== 'DMSO'),
    [results]
  );
  const cellLines = React.useMemo(() =>
    Array.from(new Set(results?.map((r) => r.cell_line) || [])),
    [results]
  );

  // Auto-select first compound when results load
  React.useEffect(() => {
    if (results && results.length > 0 && !selectedCompound && compounds.length > 0) {
      setSelectedCompound(compounds[0]);
    }
  }, [results, compounds, selectedCompound]);

  // Detect mode based on number of results
  const detectedMode = React.useMemo(() => {
    if (!results) return 'demo';
    const count = results.length;
    if (count <= 8) return 'demo';
    if (count <= 96) return 'benchmark';
    return 'full';
  }, [results]);

  // Fetch dose-response data for ALL cell lines
  const [doseResponseData, setDoseResponseData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (!selectedDesignId || !selectedCompound || cellLines.length === 0) {
      setDoseResponseData(null);
      return;
    }

    const fetchAllCellLines = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch for both 12h and 48h timepoints
        const responses12h = await Promise.all(
          cellLines.map(cellLine =>
            fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${selectedCompound}&cell_line=${cellLine}&metric=${selectedMetric}&timepoint=12`)
              .then(res => res.json())
              .then(data => ({ cellLine, data, timepoint: 12 }))
          )
        );

        const responses48h = await Promise.all(
          cellLines.map(cellLine =>
            fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${selectedCompound}&cell_line=${cellLine}&metric=${selectedMetric}&timepoint=48`)
              .then(res => res.json())
              .then(data => ({ cellLine, data, timepoint: 48 }))
          )
        );

        setDoseResponseData([...responses12h, ...responses48h]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setLoading(false);
      }
    };

    fetchAllCellLines();
  }, [selectedDesignId, selectedCompound, selectedMetric, cellLines]);

  // Fetch dose-response data for ALL compounds and ALL cell lines (normalized view)
  const [allCompoundsData, setAllCompoundsData] = useState<any>(null);
  const [loadingAllCompounds, setLoadingAllCompounds] = useState(false);

  React.useEffect(() => {
    if (!selectedDesignId || compounds.length === 0 || cellLines.length === 0) {
      setAllCompoundsData(null);
      return;
    }

    const fetchAllCompounds = async () => {
      setLoadingAllCompounds(true);

      try {
        // Fetch for both 12h and 48h timepoints
        const responses12h = await Promise.all(
          compounds.flatMap(compound =>
            cellLines.map(cellLine =>
              fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${compound}&cell_line=${cellLine}&metric=${normalizedMetric}&timepoint=12`)
                .then(res => res.json())
                .then(data => ({ compound, cellLine, data, timepoint: 12 }))
            )
          )
        );

        const responses48h = await Promise.all(
          compounds.flatMap(compound =>
            cellLines.map(cellLine =>
              fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${compound}&cell_line=${cellLine}&metric=${normalizedMetric}&timepoint=48`)
                .then(res => res.json())
                .then(data => ({ compound, cellLine, data, timepoint: 48 }))
            )
          )
        );

        const responses = [...responses12h, ...responses48h];

        setAllCompoundsData(responses);
      } catch (err) {
        console.error('Failed to fetch all compounds data:', err);
      } finally {
        setLoadingAllCompounds(false);
      }
    };

    fetchAllCompounds();
  }, [selectedDesignId, normalizedMetric, compounds, cellLines]);

  const metrics = [
    { value: 'viability_pct', label: 'Viability (%)' },
    { value: 'atp_signal', label: 'LDH Cytotoxicity (raw)' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
  ];

  // Format data for normalized comparison chart (all compounds, categorized doses)
  const normalizedChartData = React.useMemo(() => {
    if (!allCompoundsData || allCompoundsData.length === 0) return [];

    // Filter by selected timepoint
    const filteredData = allCompoundsData.filter((r: any) => r.timepoint === normalizedTimepoint);

    // Create data structure: { dose_category: string, [compound_cellLine]: value, [compound_cellLine_error]: std }
    const categories = ['vehicle', 'low', 'mid', 'high'];

    return categories.map((category, categoryIndex) => {
      const point: any = { category };

      filteredData.forEach((response: any) => {
        if (response.data.doses && response.data.values) {
          // Data is already aggregated (mean, std per dose)
          // Just sort by dose and map to categories
          const doseData = response.data.doses.map((dose: number, idx: number) => ({
            dose,
            mean: response.data.values[idx],
            std: response.data.std?.[idx] || 0,
            n: response.data.n?.[idx] || 1,
          })).sort((a: any, b: any) => a.dose - b.dose);

          // Map the sorted dose levels to categories: smallest=vehicle, then low, mid, high
          if (doseData[categoryIndex]) {
            const key = `${response.compound}_${response.cellLine}`;
            point[key] = doseData[categoryIndex].mean;
            point[`${key}_error`] = doseData[categoryIndex].std;
            point[`${key}_n`] = doseData[categoryIndex].n;
          }
        }
      });

      return point;
    });
  }, [allCompoundsData, normalizedTimepoint]);

  // Format data for chart - merge all cell lines by dose with error bars (12h)
  const chartData12h = React.useMemo(() => {
    if (!doseResponseData || doseResponseData.length === 0) return [];

    const data12h = doseResponseData.filter((r: any) => r.timepoint === 12);

    // Get all unique doses
    const allDoses = new Set<number>();
    data12h.forEach((response: any) => {
      if (response.data.doses) {
        response.data.doses.forEach((dose: number) => allDoses.add(dose));
      }
    });

    // Create data points with values and error bars for each cell line
    const sortedDoses = Array.from(allDoses).sort((a, b) => a - b);
    return sortedDoses.map(dose => {
      const point: any = { dose };

      data12h.forEach((response: any) => {
        const doseIndex = response.data.doses?.indexOf(dose);
        if (doseIndex !== -1 && doseIndex !== undefined) {
          // Mean value
          point[response.cellLine] = response.data.values[doseIndex];
          // Error bar (std)
          point[`${response.cellLine}_error`] = response.data.std?.[doseIndex] || 0;
          // Sample size (for tooltip)
          point[`${response.cellLine}_n`] = response.data.n?.[doseIndex] || 1;
        }
      });

      return point;
    });
  }, [doseResponseData]);

  // Format data for chart - merge all cell lines by dose with error bars (48h)
  const chartData48h = React.useMemo(() => {
    if (!doseResponseData || doseResponseData.length === 0) return [];

    const data48h = doseResponseData.filter((r: any) => r.timepoint === 48);

    // Get all unique doses
    const allDoses = new Set<number>();
    data48h.forEach((response: any) => {
      if (response.data.doses) {
        response.data.doses.forEach((dose: number) => allDoses.add(dose));
      }
    });

    // Create data points with values and error bars for each cell line
    const sortedDoses = Array.from(allDoses).sort((a, b) => a - b);
    return sortedDoses.map(dose => {
      const point: any = { dose };

      data48h.forEach((response: any) => {
        const doseIndex = response.data.doses?.indexOf(dose);
        if (doseIndex !== -1 && doseIndex !== undefined) {
          // Mean value
          point[response.cellLine] = response.data.values[doseIndex];
          // Error bar (std)
          point[`${response.cellLine}_error`] = response.data.std?.[doseIndex] || 0;
          // Sample size (for tooltip)
          point[`${response.cellLine}_n`] = response.data.n?.[doseIndex] || 1;
        }
      });

      return point;
    });
  }, [doseResponseData]);

  // Combine 12h and 48h data into single dataset with all 4 lines
  const chartDataCombined = React.useMemo(() => {
    if (chartData12h.length === 0 && chartData48h.length === 0) return [];

    // Get all unique doses from both timepoints
    const allDoses = new Set<number>();
    [...chartData12h, ...chartData48h].forEach(point => allDoses.add(point.dose));

    const sortedDoses = Array.from(allDoses).sort((a, b) => a - b);

    return sortedDoses.map(dose => {
      const point: any = { dose };

      // Add 12h data for each cell line
      const point12h = chartData12h.find(p => p.dose === dose);
      if (point12h) {
        cellLines.forEach(cellLine => {
          if (point12h[cellLine] !== undefined) {
            point[`${cellLine}_12h`] = point12h[cellLine];
            point[`${cellLine}_12h_error`] = point12h[`${cellLine}_error`];
            point[`${cellLine}_12h_n`] = point12h[`${cellLine}_n`];
          }
        });
      }

      // Add 48h data for each cell line
      const point48h = chartData48h.find(p => p.dose === dose);
      if (point48h) {
        cellLines.forEach(cellLine => {
          if (point48h[cellLine] !== undefined) {
            point[`${cellLine}_48h`] = point48h[cellLine];
            point[`${cellLine}_48h_error`] = point48h[`${cellLine}_error`];
            point[`${cellLine}_48h_n`] = point48h[`${cellLine}_n`];
          }
        });
      }

      return point;
    });
  }, [chartData12h, chartData48h, cellLines]);

  const chartData = chartDataCombined;

  // Get compound base color (matching plate map)
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

  // Get color for dose with compound-specific base color (matching plate map)
  const getDoseColor = (dose: number, compound: string): string => {
    const baseColor = getCompoundColor(compound);

    // Parse hex color to RGB
    const r = parseInt(baseColor.slice(1, 3), 16);
    const g = parseInt(baseColor.slice(3, 5), 16);
    const b = parseInt(baseColor.slice(5, 7), 16);

    // Map dose to opacity (matching plate map logic)
    let opacity = 0.5;
    if (dose <= 0.1) opacity = 0.3;
    else if (dose <= 1) opacity = 0.5;
    else if (dose <= 10) opacity = 0.7;
    else opacity = 0.9;

    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  };

  // Custom dot renderer with dose-based colors
  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    const color = getDoseColor(payload.dose, selectedCompound || '');

    return (
      <circle
        cx={cx}
        cy={cy}
        r={6}
        fill={color}
        stroke="#fff"
        strokeWidth={2}
      />
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Dose-Response Explorer</h2>
        <p className="text-slate-400">
          Explore compound potency and efficacy across cell lines
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
                  Simulation running - charts updating every 5 seconds with new results
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
                setSelectedCompound(null);
              }}
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

          {/* Compound Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Compound
            </label>
            <select
              value={selectedCompound || ''}
              onChange={(e) => setSelectedCompound(e.target.value || null)}
              disabled={!selectedDesignId}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            >
              <option value="">-- Select compound --</option>
              {compounds.map((compound) => (
                <option key={compound} value={compound}>
                  {compound}
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
                <option
                  key={metric.value}
                  value={metric.value}
                  disabled={metric.value === 'viability_pct' && !hasDMSO}
                >
                  {metric.label}{metric.value === 'viability_pct' && !hasDMSO ? ' (requires DMSO)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Notice for designs without DMSO */}
      {!hasDMSO && selectedDesignId && results && results.length > 0 && (
        <div className="bg-blue-900/30 border border-blue-500/50 rounded-xl p-4">
          <div className="text-sm text-blue-300">
            <strong>Note:</strong> This design does not include DMSO controls.
            Showing raw LDH cytotoxicity instead of normalized viability percentage.
          </div>
        </div>
      )}

      {/* Chart */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a design to explore dose-response curves
          </div>
        </div>
      ) : !selectedCompound ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a compound to view dose-response across all cell lines
          </div>
        </div>
      ) : loading ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-slate-400">Loading dose-response data...</div>
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
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                {selectedCompound} - All Cell Lines
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                {metrics.find((m) => m.value === selectedMetric)?.label}
              </p>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 20, right: 30, left: 80, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                dataKey="dose"
                stroke="#94a3b8"
                label={{ value: 'Dose (μM)', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
                type="number"
                domain={['dataMin', 'dataMax']}
                ticks={chartData.map(d => d.dose)}
                tickFormatter={(value) => Number(value).toFixed(1)}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: selectedMetric === 'viability_pct' ? 'Viability (%)' :
                         selectedMetric === 'atp_signal' ? 'LDH Cytotoxicity' : 'Morphology Score',
                  angle: -90,
                  position: 'insideLeft',
                  fill: '#94a3b8',
                }}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                }}
                formatter={(value: any, name: any, props: any) => {
                  const payload = props.payload;
                  const cellLine = name;
                  const n = payload[`${cellLine}_n`];
                  const error = payload[`${cellLine}_error`];

                  if (n && error !== undefined) {
                    return [`${value.toFixed(2)} ± ${error.toFixed(2)} (n=${n})`, cellLine];
                  }
                  return value.toFixed(2);
                }}
                labelFormatter={(label) => `Dose: ${label} μM`}
              />
              {/* Render lines for each cell line at both timepoints (4 lines total) */}
              {cellLines.flatMap((cellLine, cellLineIndex) => {
                const strokeDasharray = cellLineIndex === 0 ? undefined : "5 5";

                // Check individual timepoint selections
                const is12hSelected = selectedLines.size === 0 || selectedLines.has(`${cellLine}_12h`);
                const is48hSelected = selectedLines.size === 0 || selectedLines.has(`${cellLine}_48h`);

                const baseColor = selectedCompound ? getCompoundColor(selectedCompound) : '#8b5cf6';

                return [
                  // 12h timepoint - lighter/thinner
                  <Line
                    key={`${cellLine}_12h`}
                    type="monotone"
                    dataKey={`${cellLine}_12h`}
                    stroke={is12hSelected ? baseColor : '#64748b'}
                    strokeWidth={cellLineIndex === 0 ? 2 : 1.5}
                    strokeDasharray={strokeDasharray}
                    strokeOpacity={is12hSelected ? 0.6 : 0.2}
                    dot={{ r: 3, fill: is12hSelected ? baseColor : '#64748b', fillOpacity: is12hSelected ? 0.6 : 0.2, strokeWidth: 1, stroke: '#fff' }}
                    activeDot={{ r: 5, fill: baseColor }}
                    name={`${cellLine} (12h)`}
                    connectNulls={false}
                  >
                    <ErrorBar dataKey={`${cellLine}_12h_error`} stroke={is12hSelected ? baseColor : '#64748b'} strokeWidth={1} strokeOpacity={is12hSelected ? 0.6 : 0.2} />
                  </Line>,
                  // 48h timepoint - darker/thicker
                  <Line
                    key={`${cellLine}_48h`}
                    type="monotone"
                    dataKey={`${cellLine}_48h`}
                    stroke={is48hSelected ? baseColor : '#64748b'}
                    strokeWidth={cellLineIndex === 0 ? 3 : 2}
                    strokeDasharray={strokeDasharray}
                    strokeOpacity={is48hSelected ? 1 : 0.2}
                    dot={{ r: 4, fill: is48hSelected ? baseColor : '#64748b', strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 6, fill: baseColor }}
                    name={`${cellLine} (48h)`}
                    connectNulls={false}
                  >
                    <ErrorBar dataKey={`${cellLine}_48h_error`} stroke={is48hSelected ? baseColor : '#64748b'} strokeWidth={1.5} strokeOpacity={is48hSelected ? 1 : 0.2} />
                  </Line>
                ];
              })}
            </LineChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="mt-4 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="text-xs font-semibold text-violet-400 mb-3">Cell Lines + Timepoints (multi-select)</div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              {cellLines.map((cellLine, index) => {
                const isSolid = index === 0;
                const baseColor = selectedCompound ? getCompoundColor(selectedCompound) : '#8b5cf6';

                const is12hSelected = selectedLines.has(`${cellLine}_12h`);
                const is48hSelected = selectedLines.has(`${cellLine}_48h`);

                return (
                  <div key={cellLine} className="space-y-2">
                    <div className="font-semibold text-violet-400">{cellLine}</div>

                    {/* 12h timepoint - individually clickable */}
                    <div
                      className={`flex items-center gap-2 cursor-pointer hover:bg-slate-800 px-2 py-1 rounded transition-colors ${is12hSelected ? 'font-semibold' : ''}`}
                      onClick={() => {
                        const newSet = new Set(selectedLines);
                        const key = `${cellLine}_12h`;
                        if (is12hSelected) {
                          newSet.delete(key);
                        } else {
                          newSet.add(key);
                        }
                        setSelectedLines(newSet);
                      }}
                    >
                      {isSolid ? (
                        <div className="w-8 h-0.5" style={{ backgroundColor: (selectedLines.size === 0 || is12hSelected) ? baseColor : '#64748b', opacity: (selectedLines.size === 0 || is12hSelected) ? 0.6 : 0.2 }}></div>
                      ) : (
                        <svg width="32" height="2" className="flex-shrink-0">
                          <line x1="0" y1="1" x2="32" y2="1" stroke={(selectedLines.size === 0 || is12hSelected) ? baseColor : '#64748b'} strokeWidth="1.5" strokeDasharray="5 5" opacity={(selectedLines.size === 0 || is12hSelected) ? 0.6 : 0.2} />
                        </svg>
                      )}
                      <span className="text-slate-400">12h</span>
                    </div>

                    {/* 48h timepoint - individually clickable */}
                    <div
                      className={`flex items-center gap-2 cursor-pointer hover:bg-slate-800 px-2 py-1 rounded transition-colors ${is48hSelected ? 'font-semibold' : ''}`}
                      onClick={() => {
                        const newSet = new Set(selectedLines);
                        const key = `${cellLine}_48h`;
                        if (is48hSelected) {
                          newSet.delete(key);
                        } else {
                          newSet.add(key);
                        }
                        setSelectedLines(newSet);
                      }}
                    >
                      {isSolid ? (
                        <div className="w-8 h-0.5" style={{ backgroundColor: (selectedLines.size === 0 || is48hSelected) ? baseColor : '#64748b', opacity: (selectedLines.size === 0 || is48hSelected) ? 1 : 0.2 }}></div>
                      ) : (
                        <svg width="32" height="2" className="flex-shrink-0">
                          <line x1="0" y1="1" x2="32" y2="1" stroke={(selectedLines.size === 0 || is48hSelected) ? baseColor : '#64748b'} strokeWidth="2" strokeDasharray="5 5" opacity={(selectedLines.size === 0 || is48hSelected) ? 1 : 0.2} />
                        </svg>
                      )}
                      <span className="text-slate-300">48h</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Statistics */}
          {chartData.length > 0 && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Min Dose</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.min(...chartData.map(d => d.dose)).toFixed(1)} μM
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Max Dose</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.max(...chartData.map(d => d.dose)).toFixed(1)} μM
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Cell Lines</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {cellLines.length}
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Dose Points</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {chartData.length}
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Wells/Condition</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {(() => {
                    // Calculate average n across all data points and cell lines
                    let totalN = 0;
                    let count = 0;
                    chartData.forEach(point => {
                      cellLines.forEach(cellLine => {
                        const n = point[`${cellLine}_n`];
                        if (n) {
                          totalN += n;
                          count++;
                        }
                      });
                    });
                    return count > 0 ? Math.round(totalN / count) : 0;
                  })()}
                </div>
              </div>
            </div>
          )}

          {/* Plate Map */}
          <div className="mt-6">
            <PlateMapPreview
              cellLines={cellLines}
              compounds={selectedCompound ? [selectedCompound] : []}
              mode={detectedMode}
            />
          </div>
        </div>
      )}

      {/* Normalized Comparison Chart - All Compounds */}
      {selectedDesignId && normalizedChartData.length > 0 && (
        <div className={`bg-slate-800/50 backdrop-blur-sm border rounded-xl p-6 transition-all ${
          isLiveMode
            ? 'border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse'
            : 'border-slate-700'
        }`}>
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                All Compounds - Normalized Dose Comparison
                {isLiveMode && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full border border-red-500/50 animate-pulse">
                    LIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-slate-400 mt-1">
                Comparing responses across compounds at normalized dose levels (vehicle, low, mid, high)
              </p>
            </div>

            {/* Selectors for Normalized Chart */}
            <div className="flex gap-4">
              {/* Timepoint Selector */}
              <div className="min-w-[150px]">
                <label className="block text-xs font-semibold text-violet-400 uppercase tracking-wider mb-2">
                  Timepoint
                </label>
                <select
                  value={normalizedTimepoint}
                  onChange={(e) => setNormalizedTimepoint(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  <option value={12}>12 hours</option>
                  <option value={48}>48 hours</option>
                </select>
              </div>

              {/* Metric Selector */}
              <div className="min-w-[200px]">
                <label className="block text-xs font-semibold text-violet-400 uppercase tracking-wider mb-2">
                  Metric
                </label>
                <select
                  value={normalizedMetric}
                  onChange={(e) => setNormalizedMetric(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  {metrics.map((metric) => (
                  <option
                    key={metric.value}
                    value={metric.value}
                    disabled={metric.value === 'viability_pct' && !hasDMSO}
                  >
                    {metric.label}{metric.value === 'viability_pct' && !hasDMSO ? ' (requires DMSO)' : ''}
                  </option>
                ))}
              </select>
              </div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={500}>
            <LineChart data={normalizedChartData} margin={{ top: 20, right: 30, left: 80, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                dataKey="category"
                stroke="#94a3b8"
                label={{ value: 'Dose Level', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: normalizedMetric === 'viability_pct' ? 'Viability (%)' :
                         normalizedMetric === 'atp_signal' ? 'LDH Cytotoxicity' : 'Morphology Score',
                  angle: -90,
                  position: 'insideLeft',
                  fill: '#94a3b8',
                }}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                }}
                formatter={(value: any, name: any, props: any) => {
                  const payload = props.payload;
                  const key = name.split(' (')[0];  // Extract compound name from "compound (cellLine)"
                  const cellLineMatch = name.match(/\(([^)]+)\)/);  // Extract cell line
                  const cellLine = cellLineMatch ? cellLineMatch[1] : '';
                  const dataKey = `${key}_${cellLine}`;
                  const n = payload[`${dataKey}_n`];
                  const error = payload[`${dataKey}_error`];

                  if (n && error !== undefined) {
                    return [`${value?.toFixed(2) || 'N/A'} ± ${error.toFixed(2)} (n=${n})`, name];
                  }
                  return value?.toFixed(2) || 'N/A';
                }}
              />
              {/* Render a line for each compound-cellLine combination with error bars */}
              {compounds.flatMap(compound =>
                cellLines.map((cellLine, cellLineIndex) => {
                  const key = `${compound}_${cellLine}`;
                  const isSelected = selectedCellLines.size === 0 || selectedCellLines.has(cellLine);
                  const color = isSelected ? getCompoundColor(compound) : '#64748b';
                  const strokeDasharray = cellLineIndex === 0 ? undefined : "5 5";
                  const strokeWidth = cellLineIndex === 0 ? 2 : 1.5;
                  const opacity = isSelected ? 1 : 0.2;

                  return (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      stroke={color}
                      strokeWidth={strokeWidth}
                      strokeDasharray={strokeDasharray}
                      strokeOpacity={opacity}
                      dot={{ r: 3, fill: color, strokeWidth: 1, stroke: '#fff', fillOpacity: opacity }}
                      name={`${compound} (${cellLine})`}
                      connectNulls={false}
                    >
                      <ErrorBar dataKey={`${key}_error`} stroke={color} strokeWidth={1} strokeOpacity={opacity} />
                    </Line>
                  );
                })
              )}
            </LineChart>
          </ResponsiveContainer>

          {/* Legend for normalized chart */}
          <div className="mt-4 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="space-y-4">
              {/* Compound Legend - Grouped by Color Families */}
              <div>
                <div className="text-sm font-semibold text-violet-400 mb-2">
                  Compounds:
                </div>
                <div className="grid grid-cols-5 gap-x-6 gap-y-2 text-xs">
                  {(() => {
                    // Define color groups - each array is a vertical column
                    const colorGroups = [
                      ['tBHQ', 'H2O2'],              // Red/Orange column
                      ['tunicamycin', 'thapsigargin'], // Yellow column
                      ['CCCP', 'oligomycin'],        // Green column
                      ['etoposide', 'MG132'],        // Cyan/Teal column
                      ['nocodazole', 'paclitaxel']   // Blue/Violet column
                    ];

                    return colorGroups.map((group, groupIndex) => (
                      <div key={groupIndex} className="space-y-2">
                        {group.map((compound) => {
                          // Only show if compound exists in data
                          if (!compounds.includes(compound)) return null;
                          return (
                            <div key={compound} className="flex items-center gap-2">
                              <div
                                className="w-8 h-0.5"
                                style={{ backgroundColor: getCompoundColor(compound) }}
                              ></div>
                              <span className="text-slate-300">{compound}</span>
                            </div>
                          );
                        })}
                      </div>
                    ));
                  })()}
                </div>
              </div>

              {/* Cell Line Legend */}
              <div className="pt-3 border-t border-slate-700">
                <div className="text-sm font-semibold text-violet-400 mb-2">
                  Cell Lines (multi-select):
                </div>
                <div className="flex flex-wrap gap-4 text-xs">
                  {cellLines.map((cellLine, index) => {
                    const isSelected = selectedCellLines.has(cellLine);
                    const color = (selectedCellLines.size === 0 || isSelected) ? '#94a3b8' : '#64748b';
                    const opacity = (selectedCellLines.size === 0 || isSelected) ? 1 : 0.3;

                    return (
                      <div
                        key={cellLine}
                        className={`flex items-center gap-2 cursor-pointer hover:bg-slate-800 px-2 py-1 rounded transition-colors ${isSelected ? 'font-semibold' : ''}`}
                        onClick={() => {
                          const newSet = new Set(selectedCellLines);
                          if (isSelected) {
                            newSet.delete(cellLine);
                          } else {
                            newSet.add(cellLine);
                          }
                          setSelectedCellLines(newSet);
                        }}
                      >
                        {index === 0 ? (
                          <div className="w-8 h-0.5" style={{ backgroundColor: color, opacity }}></div>
                        ) : (
                          <svg width="32" height="2" className="flex-shrink-0">
                            <line x1="0" y1="1" x2="32" y2="1" stroke={color} strokeWidth="2" strokeDasharray="4 2" opacity={opacity} />
                          </svg>
                        )}
                        <span className="text-slate-300">{cellLine}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DoseResponseTab;
