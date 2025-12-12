/**
 * Tab 3: Dose-Response Explorer
 *
 * Interactive dose-response curves for compounds across cell lines
 */

import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useDesigns, useDoseResponse, useResults } from '../hooks/useCellThalamusData';

interface DoseResponseTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

const DoseResponseTab: React.FC<DoseResponseTabProps> = ({ selectedDesignId, onDesignChange }) => {
  const { data: designs } = useDesigns();
  const { data: results } = useResults(selectedDesignId);

  const [selectedCompound, setSelectedCompound] = useState<string | null>(null);
  const [selectedCellLine, setSelectedCellLine] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>('atp_signal');

  const { data: doseResponse, loading, error } = useDoseResponse(
    selectedDesignId,
    selectedCompound,
    selectedCellLine,
    selectedMetric
  );

  // Extract unique values from results
  const compounds = Array.from(new Set(results?.map((r) => r.compound) || [])).filter(
    (c) => c !== 'DMSO'
  );
  const cellLines = Array.from(new Set(results?.map((r) => r.cell_line) || []));
  const metrics = [
    { value: 'atp_signal', label: 'ATP Viability' },
    { value: 'morph_er', label: 'ER Morphology' },
    { value: 'morph_mito', label: 'Mito Morphology' },
    { value: 'morph_nucleus', label: 'Nucleus Morphology' },
    { value: 'morph_actin', label: 'Actin Morphology' },
    { value: 'morph_rna', label: 'RNA Morphology' },
  ];

  // Format data for chart
  const chartData = doseResponse
    ? doseResponse.doses.map((dose, idx) => ({
        dose,
        value: doseResponse.values[idx],
      }))
    : [];

  const completedDesigns = designs?.filter((d) => d.status === 'completed') || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Dose-Response Explorer</h2>
        <p className="text-slate-400">
          Explore compound potency and efficacy across cell lines
        </p>
      </div>

      {/* Controls */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
                setSelectedCellLine(null);
              }}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="">-- Select design --</option>
              {completedDesigns.map((design) => (
                <option key={design.design_id} value={design.design_id}>
                  {design.design_id.slice(0, 8)}...
                </option>
              ))}
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

          {/* Cell Line Selector */}
          <div>
            <label className="block text-sm font-semibold text-violet-400 uppercase tracking-wider mb-2">
              Cell Line
            </label>
            <select
              value={selectedCellLine || ''}
              onChange={(e) => setSelectedCellLine(e.target.value || null)}
              disabled={!selectedDesignId}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            >
              <option value="">-- Select cell line --</option>
              {cellLines.map((line) => (
                <option key={line} value={line}>
                  {line}
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
      </div>

      {/* Chart */}
      {!selectedDesignId ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a design to explore dose-response curves
          </div>
        </div>
      ) : !selectedCompound || !selectedCellLine ? (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-slate-400 text-lg">
            Select a compound and cell line to view dose-response
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
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-white">
              {selectedCompound} on {selectedCellLine}
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              {metrics.find((m) => m.value === selectedMetric)?.label}
            </p>
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis
                dataKey="dose"
                stroke="#94a3b8"
                label={{ value: 'Dose (μM)', position: 'insideBottom', offset: -10, fill: '#94a3b8' }}
                scale="log"
                domain={[0.1, 'auto']}
              />
              <YAxis
                stroke="#94a3b8"
                label={{
                  value: selectedMetric === 'atp_signal' ? 'Viability (%)' : 'Morphology Score',
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
                formatter={(value: any) => value.toFixed(2)}
                labelFormatter={(label) => `Dose: ${label} μM`}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#8b5cf6"
                strokeWidth={3}
                dot={{ fill: '#8b5cf6', r: 5 }}
                activeDot={{ r: 7 }}
                name={metrics.find((m) => m.value === selectedMetric)?.label}
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Help Text */}
          <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <strong>Interpretation:</strong> Dose-response curves show how cellular responses change with
            compound concentration. For ATP viability, decreasing curves indicate cytotoxicity. For
            morphology channels, changes indicate stress-specific phenotypes. EC50 is the dose producing
            half-maximal effect.
          </div>

          {/* Statistics (placeholder) */}
          {doseResponse && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Min Dose</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.min(...doseResponse.doses).toFixed(1)} μM
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Max Dose</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.max(...doseResponse.doses).toFixed(1)} μM
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Min Response</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.min(...doseResponse.values).toFixed(2)}
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Max Response</div>
                <div className="text-lg font-bold text-violet-400 mt-1">
                  {Math.max(...doseResponse.values).toFixed(2)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DoseResponseTab;
