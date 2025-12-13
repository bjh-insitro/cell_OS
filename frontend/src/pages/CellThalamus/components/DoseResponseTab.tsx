/**
 * Tab 3: Dose-Response Explorer
 *
 * Interactive dose-response curves for compounds across cell lines
 */

import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
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
        const responses = await Promise.all(
          cellLines.map(cellLine =>
            fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${selectedCompound}&cell_line=${cellLine}&metric=${selectedMetric}`)
              .then(res => res.json())
              .then(data => ({ cellLine, data }))
          )
        );

        setDoseResponseData(responses);
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
        const responses = await Promise.all(
          compounds.flatMap(compound =>
            cellLines.map(cellLine =>
              fetch(`http://localhost:8000/api/thalamus/designs/${selectedDesignId}/dose-response?compound=${compound}&cell_line=${cellLine}&metric=${normalizedMetric}`)
                .then(res => res.json())
                .then(data => ({ compound, cellLine, data }))
            )
          )
        );

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
    { value: 'atp_signal', label: 'ATP Signal (raw)' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
  ];

  // Format data for normalized comparison chart (all compounds, categorized doses)
  const normalizedChartData = React.useMemo(() => {
    if (!allCompoundsData || allCompoundsData.length === 0) return [];

    // Create data structure: { dose_category: string, [compound_cellLine]: value }
    const categories = ['vehicle', 'low', 'mid', 'high'];

    return categories.map((category, categoryIndex) => {
      const point: any = { category };

      allCompoundsData.forEach((response: any) => {
        if (response.data.doses && response.data.values) {
          // Sort doses and map to categories by index
          const sortedIndices = response.data.doses
            .map((dose: number, idx: number) => ({ dose, idx, value: response.data.values[idx] }))
            .sort((a: any, b: any) => a.dose - b.dose);

          // Map the sorted doses to categories: smallest=vehicle, then low, mid, high
          if (sortedIndices[categoryIndex]) {
            const key = `${response.compound}_${response.cellLine}`;
            point[key] = sortedIndices[categoryIndex].value;
          }
        }
      });

      return point;
    });
  }, [allCompoundsData]);

  // Format data for chart - merge all cell lines by dose
  const chartData = React.useMemo(() => {
    if (!doseResponseData || doseResponseData.length === 0) return [];

    // Get all unique doses
    const allDoses = new Set<number>();
    doseResponseData.forEach((response: any) => {
      if (response.data.doses) {
        response.data.doses.forEach((dose: number) => allDoses.add(dose));
      }
    });

    // Create data points with values for each cell line
    const sortedDoses = Array.from(allDoses).sort((a, b) => a - b);
    return sortedDoses.map(dose => {
      const point: any = { dose };

      doseResponseData.forEach((response: any) => {
        const doseIndex = response.data.doses?.indexOf(dose);
        if (doseIndex !== -1 && doseIndex !== undefined) {
          point[response.cellLine] = response.data.values[doseIndex];
        }
      });

      return point;
    });
  }, [doseResponseData]);

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
                    Run #{index + 1} - {date} ({design.design_id.slice(0, 8)}){statusLabel}
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
            Showing raw ATP signal instead of normalized viability percentage.
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
                tickFormatter={(value) => value.toFixed(1)}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: selectedMetric === 'viability_pct' ? 'Viability (%)' :
                         selectedMetric === 'atp_signal' ? 'ATP Signal' : 'Morphology Score',
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
                formatter={(value: any) => value.toFixed(2)}
                labelFormatter={(label) => `Dose: ${label} μM`}
              />
              <Legend />
              {/* Render a line for each cell line */}
              {cellLines.map((cellLine, index) => {
                const baseColor = selectedCompound ? getCompoundColor(selectedCompound) : '#8b5cf6';
                // Use solid color for first cell line, dashed for second
                const strokeDasharray = index === 0 ? undefined : "5 5";

                return (
                  <Line
                    key={cellLine}
                    type="monotone"
                    dataKey={cellLine}
                    stroke={baseColor}
                    strokeWidth={index === 0 ? 3 : 2}
                    strokeDasharray={strokeDasharray}
                    dot={{ r: 4, fill: baseColor, strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 6, fill: baseColor }}
                    name={cellLine}
                    connectNulls={false}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="mt-4 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm font-semibold text-violet-400 mb-2">
              {selectedCompound} - Cell Line Comparison:
            </div>
            <div className="flex flex-wrap gap-6 text-xs">
              {cellLines.map((cellLine, index) => (
                <div key={cellLine} className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <div
                      className="w-8 h-0.5"
                      style={{
                        backgroundColor: selectedCompound ? getCompoundColor(selectedCompound) : '#8b5cf6',
                        borderTop: index === 0 ? 'none' : `2px dashed ${selectedCompound ? getCompoundColor(selectedCompound) : '#8b5cf6'}`
                      }}
                    ></div>
                  </div>
                  <span className="text-slate-300">{cellLine} {index === 0 ? '(solid)' : '(dashed)'}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
              <strong>Interpretation:</strong> Color matches compound. Line style distinguishes cell lines.
              {selectedMetric === 'viability_pct' ? (
                <span> Viability is normalized to DMSO control (100%). Decreasing values indicate cytotoxicity.</span>
              ) : selectedMetric === 'atp_signal' ? (
                <span> For ATP signal (raw), decreasing values indicate cytotoxicity.</span>
              ) : (
                <span> Morphology scores show phenotypic changes relative to control.</span>
              )}
              {' '}Sentinel wells (QC replicates) are excluded from this view - see the Sentinel Monitor tab for QC data.
            </div>
          </div>

          {/* Statistics */}
          {chartData.length > 0 && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
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

            {/* Metric Selector for Normalized Chart */}
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
                         normalizedMetric === 'atp_signal' ? 'ATP Signal' : 'Morphology Score',
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
                formatter={(value: any) => value?.toFixed(2) || 'N/A'}
              />
              <Legend />
              {/* Render a line for each compound-cellLine combination */}
              {compounds.flatMap(compound =>
                cellLines.map((cellLine, cellLineIndex) => {
                  const key = `${compound}_${cellLine}`;
                  const color = getCompoundColor(compound);
                  const strokeDasharray = cellLineIndex === 0 ? undefined : "5 5";
                  const strokeWidth = cellLineIndex === 0 ? 2 : 1.5;

                  return (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      stroke={color}
                      strokeWidth={strokeWidth}
                      strokeDasharray={strokeDasharray}
                      dot={{ r: 3, fill: color, strokeWidth: 1, stroke: '#fff' }}
                      name={`${compound} (${cellLine})`}
                      connectNulls={false}
                    />
                  );
                })
              )}
            </LineChart>
          </ResponsiveContainer>

          {/* Legend for normalized chart */}
          <div className="mt-4 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm font-semibold text-violet-400 mb-3">
              Dose Categories:
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs mb-4">
              <div>
                <span className="font-semibold text-slate-300">Vehicle:</span>
                <span className="text-slate-400 ml-1">0 µM (control)</span>
              </div>
              <div>
                <span className="font-semibold text-slate-300">Low:</span>
                <span className="text-slate-400 ml-1">0.1× EC50</span>
              </div>
              <div>
                <span className="font-semibold text-slate-300">Mid:</span>
                <span className="text-slate-400 ml-1">1× EC50</span>
              </div>
              <div>
                <span className="font-semibold text-slate-300">High:</span>
                <span className="text-slate-400 ml-1">10× EC50</span>
              </div>
            </div>
            <div className="pt-3 border-t border-slate-700 text-xs text-slate-400">
              <strong>Interpretation:</strong> This view normalizes doses relative to each compound's EC50,
              allowing direct comparison of compound potencies. Colors indicate compounds,
              solid lines = {cellLines[0] || 'first cell line'}, dashed lines = {cellLines[1] || 'second cell line'}.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DoseResponseTab;
