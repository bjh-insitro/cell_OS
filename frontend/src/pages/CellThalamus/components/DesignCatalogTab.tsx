/**
 * Design Catalog Tab - Browse experimental design versions
 *
 * Displays the design catalog with:
 * - All design versions with status (current/archived)
 * - Evolution history with evidence
 * - Design principles and guidelines
 * - Ability to view full design details
 */

import React, { useState, useEffect } from 'react';
import DesignPlatePreview from './DesignPlatePreview';

interface Design {
  design_id: string;
  version: string;
  filename: string;
  created_at: string;
  status: string;
  design_type: string;
  description: string;
  metadata: Record<string, any>;
  features: string[];
  improvements_over_previous?: string[];
  supersedes?: string;
  superseded_by?: string;
  chart_definitions?: any[];
  validation_targets?: Record<string, any>;
  next_iteration_ideas?: string[];
  notes?: string;
  buffer_well_rationale?: {
    summary: string;
    positions: string[];
    purpose: string;
    technical_necessity: string[];
    epistemic_function: string;
    phase_dependency: string;
    information_economics: string;
    design_principle: string;
  };
  cell_line_separation_rationale?: {
    summary: string;
    plate_allocation: Record<string, string>;
    why_separation: string[];
    when_mixing_makes_sense: string;
    phase0_recommendation: string;
    design_principle: string;
  };
}

interface FullDesignData {
  catalog_entry: Design;
  design_data: {
    design_id: string;
    design_type: string;
    description: string;
    metadata: Record<string, any>;
    wells: any[];
  };
}

interface EvolutionEntry {
  from_version: string | null;
  to_version: string;
  date: string;
  reason: string;
  key_changes: string[];
  evidence?: Record<string, any>;
}

interface Catalog {
  catalog_version: string;
  description: string;
  designs: Design[];
  design_evolution_log: EvolutionEntry[];
  design_principles: Record<string, string>;
  glossary: Record<string, string>;
}

const DesignCatalogTab: React.FC = () => {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDesign, setExpandedDesign] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'designs' | 'evolution' | 'comparison' | 'principles'>('designs');
  const [fullDesignData, setFullDesignData] = useState<Record<string, FullDesignData>>({});
  const [loadingDesigns, setLoadingDesigns] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchCatalog();
  }, []);

  const fetchCatalog = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/thalamus/catalog');
      if (!response.ok) throw new Error('Failed to fetch catalog');
      const data = await response.json();
      setCatalog(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchFullDesign = async (designId: string) => {
    if (fullDesignData[designId] || loadingDesigns.has(designId)) return;

    setLoadingDesigns((prev) => new Set(prev).add(designId));

    try {
      const response = await fetch(
        `http://localhost:8000/api/thalamus/catalog/designs/${designId}`
      );
      if (!response.ok) throw new Error('Failed to fetch design data');
      const data = await response.json();
      setFullDesignData((prev) => ({ ...prev, [designId]: data }));
    } catch (err) {
      console.error(`Error fetching design ${designId}:`, err);
    } finally {
      setLoadingDesigns((prev) => {
        const newSet = new Set(prev);
        newSet.delete(designId);
        return newSet;
      });
    }
  };

  const handleToggleExpand = (designId: string) => {
    if (expandedDesign === designId) {
      setExpandedDesign(null);
    } else {
      setExpandedDesign(designId);
      fetchFullDesign(designId);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading design catalog...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
        <p className="text-red-400">Error loading catalog: {error}</p>
      </div>
    );
  }

  if (!catalog) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-900/30 to-blue-900/30 border border-violet-700/30 rounded-lg p-6">
        <h2 className="text-2xl font-bold text-white mb-2">📐 Design Catalog</h2>
        <p className="text-slate-300">{catalog.description}</p>
        <p className="text-slate-400 text-sm mt-1">Version {catalog.catalog_version}</p>
      </div>

      {/* View Selector */}
      <div className="flex gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-700 w-fit">
        <button
          onClick={() => setActiveView('designs')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'designs'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📋 Designs
        </button>
        <button
          onClick={() => setActiveView('evolution')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'evolution'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          🔄 Evolution
        </button>
        <button
          onClick={() => setActiveView('comparison')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'comparison'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📊 Comparison
        </button>
        <button
          onClick={() => setActiveView('principles')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'principles'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📖 Principles
        </button>
      </div>

      {/* Designs View */}
      {activeView === 'designs' && (
        <div className="space-y-4">
          {catalog.designs.map((design) => (
            <div
              key={design.design_id}
              className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden"
            >
              {/* Design Header */}
              <div
                className="p-4 cursor-pointer hover:bg-slate-700/30 transition-colors"
                onClick={() => handleToggleExpand(design.design_id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">
                        {design.status === 'current' ? '✓' : '○'}
                      </span>
                      <div>
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                          {design.design_id}
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              design.status === 'current'
                                ? 'bg-green-900/30 text-green-400 border border-green-700'
                                : 'bg-slate-700/30 text-slate-400 border border-slate-600'
                            }`}
                          >
                            {design.status}
                          </span>
                          <span className="text-xs px-2 py-1 rounded-full bg-violet-900/30 text-violet-400 border border-violet-700">
                            {design.version}
                          </span>
                        </h3>
                        <p className="text-slate-400 text-sm mt-1">{design.description}</p>
                      </div>
                    </div>

                    {/* Metadata Summary */}
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                      {design.metadata.n_plates && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded flex items-center gap-1">
                          <span className="text-violet-400">🧫</span>
                          {design.metadata.n_plates} plates
                        </span>
                      )}
                      {design.metadata.wells_per_plate && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.wells_per_plate} wells/plate
                        </span>
                      )}
                      {design.metadata.n_wells && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded font-semibold text-white">
                          {design.metadata.n_wells} total wells
                        </span>
                      )}
                      {design.metadata.timepoints_h && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded flex items-center gap-1">
                          <span className="text-blue-400">⏱</span>
                          {design.metadata.timepoints_h.join('h, ')}h
                        </span>
                      )}
                      {design.metadata.n_compounds && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.n_compounds} compounds
                        </span>
                      )}
                      {design.metadata.n_cell_lines && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.n_cell_lines} cell lines
                        </span>
                      )}
                      {design.metadata.cell_lines && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.cell_lines.join(', ')}
                        </span>
                      )}
                      {design.metadata.operators && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.operators.length} operators
                        </span>
                      )}
                      {design.metadata.days && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.days.length} days
                        </span>
                      )}
                      <span className="bg-slate-700/30 px-2 py-1 rounded">
                        {design.created_at}
                      </span>
                    </div>
                  </div>

                  <button className="text-slate-400 hover:text-white transition-colors">
                    {expandedDesign === design.design_id ? '▼' : '▶'}
                  </button>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedDesign === design.design_id && (
                <div className="border-t border-slate-700 p-4 space-y-4">
                  {/* Loading indicator */}
                  {loadingDesigns.has(design.design_id) && (
                    <div className="text-center py-4 text-slate-400">
                      Loading design details...
                    </div>
                  )}

                  {/* Plate Map Preview */}
                  {fullDesignData[design.design_id] && (
                    <div>
                      <h4 className="text-sm font-semibold text-cyan-400 mb-3 flex items-center gap-2">
                        <span>🗺️</span>
                        <span>Plate Layout Preview</span>
                        <span className="text-xs text-slate-500 font-normal">
                          ({fullDesignData[design.design_id].design_data.wells.length} wells)
                        </span>
                      </h4>
                      <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                        {/* Horizontal scroll container */}
                        <div className="overflow-x-auto pb-2">
                          <div className="flex gap-4 min-w-max">
                            {/* Group wells by plate_id */}
                            {Object.entries(
                              fullDesignData[design.design_id].design_data.wells.reduce(
                                (acc: Record<string, any[]>, well: any) => {
                                  if (!acc[well.plate_id]) acc[well.plate_id] = [];
                                  acc[well.plate_id].push(well);
                                  return acc;
                                },
                                {}
                              )
                            )
                              .sort(([a], [b]) => {
                                // Extract numeric part for proper numeric sorting
                                const numA = parseInt(a.match(/\d+/)?.[0] || '0');
                                const numB = parseInt(b.match(/\d+/)?.[0] || '0');
                                return numA - numB;
                              })
                              .map(([plateId, plateWells]) => (
                                <DesignPlatePreview
                                  key={plateId}
                                  plateId={plateId}
                                  wells={plateWells}
                                  width={220}
                                  height={150}
                                />
                              ))}
                          </div>
                        </div>
                        {/* Legend */}
                        <div className="mt-4 pt-3 border-t border-slate-700">
                          <div className="text-xs font-semibold text-slate-300 mb-2">Compounds (fill):</div>
                          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#ef4444] flex-shrink-0"></div>
                              <span className="text-slate-300">tBHQ</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#22c55e] flex-shrink-0"></div>
                              <span className="text-slate-300">oligomycin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#f97316] flex-shrink-0"></div>
                              <span className="text-slate-300">H₂O₂</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#14b8a6] flex-shrink-0"></div>
                              <span className="text-slate-300">etoposide</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#f59e0b] flex-shrink-0"></div>
                              <span className="text-slate-300">tunicamycin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#06b6d4] flex-shrink-0"></div>
                              <span className="text-slate-300">MG132</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#eab308] flex-shrink-0"></div>
                              <span className="text-slate-300">thapsigargin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#3b82f6] flex-shrink-0"></div>
                              <span className="text-slate-300">nocodazole</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#84cc16] flex-shrink-0"></div>
                              <span className="text-slate-300">CCCP</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#8b5cf6] flex-shrink-0"></div>
                              <span className="text-slate-300">paclitaxel</span>
                            </div>
                          </div>
                          <div className="mt-3 pt-3 border-t border-slate-700/50">
                            <div className="flex items-center gap-4 text-xs mb-2 flex-wrap">
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded bg-white flex-shrink-0"></div>
                                <span className="text-slate-400">Sentinel (vehicle)</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded flex-shrink-0" style={{background: 'linear-gradient(135deg, #ffffff 50%, #ef4444 50%)'}}></div>
                                <span className="text-slate-400">Sentinel (compound)</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded bg-slate-600 flex-shrink-0"></div>
                                <span className="text-slate-400">DMSO</span>
                              </div>
                            </div>
                            <div className="text-xs font-semibold text-slate-300 mb-1.5">Cell lines (border):</div>
                            <div className="flex items-center gap-4 text-xs">
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded border-2 border-[#8b5cf6] bg-slate-700 flex-shrink-0"></div>
                                <span className="text-slate-400">A549</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded border-2 border-[#ec4899] bg-slate-700 flex-shrink-0"></div>
                                <span className="text-slate-400">HepG2</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Features */}
                  {design.features && design.features.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-violet-400 mb-2">Features</h4>
                      <ul className="space-y-1">
                        {design.features.map((feature, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-violet-400">•</span>
                            {feature}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Improvements */}
                  {design.improvements_over_previous && design.improvements_over_previous.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-green-400 mb-2">
                        Improvements Over Previous
                      </h4>
                      <ul className="space-y-1">
                        {design.improvements_over_previous.map((improvement, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-green-400">✓</span>
                            {improvement}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Chart Definitions */}
                  {design.chart_definitions && design.chart_definitions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-blue-400 mb-2">Chart Definitions</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {design.chart_definitions.map((chart: any, idx: number) => (
                          <div key={idx} className="bg-slate-900/50 border border-slate-600 rounded p-3">
                            <div className="font-mono text-sm text-blue-300">{chart.chart_id}</div>
                            <div className="text-xs text-slate-400 mt-1">
                              Use: {chart.intended_use}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">
                              Capabilities: {chart.capabilities.join(', ')}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Notes */}
                  {design.notes && (
                    <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                      <h4 className="text-sm font-semibold text-amber-400 mb-1">Notes</h4>
                      <p className="text-sm text-slate-300">{design.notes}</p>
                    </div>
                  )}

                  {/* Buffer Well Rationale */}
                  {design.buffer_well_rationale && (
                    <div className="bg-indigo-900/10 border border-indigo-700/30 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-indigo-400 mb-3 flex items-center gap-2">
                        <span>🎯</span>
                        <span>Buffer Well Strategy</span>
                      </h4>

                      <div className="space-y-3">
                        {/* Summary */}
                        <div>
                          <p className="text-sm text-slate-300 italic">
                            {design.buffer_well_rationale.summary}
                          </p>
                        </div>

                        {/* Positions */}
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-400">Reserved positions:</span>
                          <div className="flex gap-1">
                            {design.buffer_well_rationale.positions.map((pos) => (
                              <span key={pos} className="bg-slate-800 px-2 py-1 rounded font-mono text-indigo-400 border border-slate-700">
                                {pos}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Technical Necessity */}
                        <div>
                          <h5 className="text-xs font-semibold text-indigo-300 mb-2">Technical Necessity</h5>
                          <ul className="space-y-1.5">
                            {design.buffer_well_rationale.technical_necessity.map((point, idx) => (
                              <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                                <span className="text-indigo-400 mt-0.5">•</span>
                                <span>{point}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Epistemic Function */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-indigo-300 mb-1">Epistemic Function</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.epistemic_function}</p>
                        </div>

                        {/* Information Economics */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-green-300 mb-1">Information Economics</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.information_economics}</p>
                        </div>

                        {/* Phase Dependency */}
                        <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-amber-300 mb-1">Phase Dependency</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.phase_dependency}</p>
                        </div>

                        {/* Design Principle */}
                        <div className="bg-violet-900/10 border border-violet-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-violet-300 mb-1">Design Principle</h5>
                          <p className="text-xs text-slate-300 italic font-semibold">{design.buffer_well_rationale.design_principle}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Cell Line Separation Rationale */}
                  {design.cell_line_separation_rationale && (
                    <div className="bg-emerald-900/10 border border-emerald-700/30 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
                        <span>🧬</span>
                        <span>Cell Line Separation Strategy</span>
                      </h4>

                      <div className="space-y-3">
                        {/* Summary */}
                        <div>
                          <p className="text-sm text-slate-300 italic">
                            {design.cell_line_separation_rationale.summary}
                          </p>
                        </div>

                        {/* Plate Allocation */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-emerald-300 mb-2">Plate Allocation</h5>
                          <div className="space-y-1">
                            {Object.entries(design.cell_line_separation_rationale.plate_allocation).map(
                              ([cellLine, plates]) => (
                                <div key={cellLine} className="text-xs font-mono">
                                  <span className="text-emerald-400">{cellLine}:</span>{' '}
                                  <span className="text-white">{plates}</span>
                                </div>
                              )
                            )}
                          </div>
                        </div>

                        {/* Why Separation */}
                        <div>
                          <h5 className="text-xs font-semibold text-emerald-300 mb-2">
                            Why Separation (Not Mixing)
                          </h5>
                          <ul className="space-y-1.5">
                            {design.cell_line_separation_rationale.why_separation.map((point, idx) => (
                              <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                                <span className="text-emerald-400 mt-0.5">•</span>
                                <span>{point}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* When Mixing Makes Sense */}
                        <div className="bg-blue-900/10 border border-blue-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-blue-300 mb-1">
                            When Mixing Makes Sense
                          </h5>
                          <p className="text-xs text-slate-300">
                            {design.cell_line_separation_rationale.when_mixing_makes_sense}
                          </p>
                        </div>

                        {/* Phase 0 Recommendation */}
                        <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-amber-300 mb-1">
                            Phase 0 Recommendation
                          </h5>
                          <p className="text-xs text-slate-300">
                            {design.cell_line_separation_rationale.phase0_recommendation}
                          </p>
                        </div>

                        {/* Design Principle */}
                        <div className="bg-violet-900/10 border border-violet-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-violet-300 mb-1">Design Principle</h5>
                          <p className="text-xs text-slate-300 italic font-semibold">
                            {design.cell_line_separation_rationale.design_principle}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Next Iteration Ideas */}
                  {design.next_iteration_ideas && design.next_iteration_ideas.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-cyan-400 mb-2">
                        Next Iteration Ideas
                      </h4>
                      <ul className="space-y-1">
                        {design.next_iteration_ideas.map((idea, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-cyan-400">→</span>
                            {idea}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Evolution View */}
      {activeView === 'evolution' && (
        <div className="space-y-4">
          {catalog.design_evolution_log.map((entry, idx) => (
            <div key={idx} className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="text-2xl">{idx + 1}</div>
                <div className="flex items-center gap-2 text-lg font-semibold text-white">
                  <span className="text-slate-400">{entry.from_version || 'initial'}</span>
                  <span className="text-violet-400">→</span>
                  <span>{entry.to_version}</span>
                  <span className="text-sm text-slate-400 font-normal">({entry.date})</span>
                </div>
              </div>

              <div className="space-y-3">
                {/* Reason */}
                <div>
                  <h4 className="text-sm font-semibold text-amber-400 mb-1">Reason</h4>
                  <p className="text-sm text-slate-300">{entry.reason}</p>
                </div>

                {/* Evidence */}
                {entry.evidence && Object.keys(entry.evidence).length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-red-400 mb-2">Evidence</h4>
                    <div className="bg-slate-900/50 border border-slate-600 rounded p-3 space-y-1">
                      {Object.entries(entry.evidence).map(([key, value]) => (
                        <div key={key} className="text-sm font-mono">
                          <span className="text-slate-400">{key}:</span>{' '}
                          <span className="text-white">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Changes */}
                <div>
                  <h4 className="text-sm font-semibold text-green-400 mb-2">Key Changes</h4>
                  <ul className="space-y-1">
                    {entry.key_changes.map((change, changeIdx) => (
                      <li
                        key={changeIdx}
                        className="text-sm text-slate-300 flex items-start gap-2"
                      >
                        <span className="text-green-400">•</span>
                        {change}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Evolution View */}
      {activeView === 'comparison' && (
        <div className="space-y-6">
          {/* Comparison Header */}
          <div className="bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-700/30 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-white mb-2">📊 Design Comparison</h2>
            <p className="text-slate-300">Head-to-head statistical power analysis across all design versions</p>
          </div>

          {/* Overview Table */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Overview</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">Total Wells</th>
                    <th className="text-right py-3 px-4 text-slate-300">Plates</th>
                    <th className="text-right py-3 px-4 text-slate-300">Wells/Plate</th>
                    <th className="text-right py-3 px-4 text-slate-300">Sentinels</th>
                    <th className="text-right py-3 px-4 text-slate-300">Experimental</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4">2,304</td>
                    <td className="text-right py-3 px-4">24</td>
                    <td className="text-right py-3 px-4">96</td>
                    <td className="text-right py-3 px-4">384</td>
                    <td className="text-right py-3 px-4">1,920</td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4">2,112</td>
                    <td className="text-right py-3 px-4">24</td>
                    <td className="text-right py-3 px-4">88</td>
                    <td className="text-right py-3 px-4">688</td>
                    <td className="text-right py-3 px-4">1,424</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">12 (50% ↓)</td>
                    <td className="text-right py-3 px-4">96</td>
                    <td className="text-right py-3 px-4">416</td>
                    <td className="text-right py-3 px-4">736</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-Cell-Line Replication */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Per-Cell-Line Replication</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">A549 Wells</th>
                    <th className="text-right py-3 px-4 text-slate-300">HepG2 Wells</th>
                    <th className="text-left py-3 px-4 text-slate-300">Strategy</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Mixed on same plates</td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4">1,056</td>
                    <td className="text-right py-3 px-4">1,056</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Separated (Plates 1-12 vs 13-24)</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">576 (1.8× ↓)</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">576 (1.8× ↓)</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Checkerboard (both on same plate)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Statistical Power */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Statistical Power Analysis</h3>
            <p className="text-sm text-slate-400 mb-4">
              EC50 confidence interval width from dose-response curve fitting (bootstrap, 50 iterations). Lower = better precision.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">Mean EC50 CI Width (µM)</th>
                    <th className="text-right py-3 px-4 text-slate-300">vs v2 Ratio</th>
                    <th className="text-left py-3 px-4 text-slate-300">Interpretation</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">1.39</td>
                    <td className="text-right py-3 px-4 text-green-400">0.53×</td>
                    <td className="py-3 px-4">
                      <span className="bg-green-900/30 text-green-400 px-2 py-1 rounded text-xs border border-green-700">
                        HIGH POWER ✓
                      </span>
                    </td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">2.64</td>
                    <td className="text-right py-3 px-4">1.00×</td>
                    <td className="py-3 px-4">
                      <span className="bg-green-900/30 text-green-400 px-2 py-1 rounded text-xs border border-green-700">
                        HIGH POWER ✓
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4 text-amber-400 font-semibold">10.08</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">3.82× ↑</td>
                    <td className="py-3 px-4">
                      <span className="bg-amber-900/30 text-amber-400 px-2 py-1 rounded text-xs border border-amber-700">
                        MODERATE POWER
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Key Trade-offs */}
          <div className="bg-gradient-to-r from-red-900/20 to-amber-900/20 border border-red-700/30 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">⚠️ Key Trade-offs: v3 vs v2</h3>

            <div className="grid md:grid-cols-2 gap-6 mb-4">
              <div className="bg-slate-900/50 border border-green-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-green-400 mb-3 flex items-center gap-2">
                  <span>✓</span>
                  <span>Throughput Gains (v3)</span>
                </h4>
                <ul className="space-y-2 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>50% fewer plates (12 vs 24)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>Checkerboard eliminates spatial confounding</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>Paired cell-line comparisons under identical conditions</span>
                  </li>
                </ul>
              </div>

              <div className="bg-slate-900/50 border border-red-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                  <span>✗</span>
                  <span>Statistical Power Loss (v3)</span>
                </h4>
                <ul className="space-y-2 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>1.8× fewer replicates per cell line</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>3.82× wider EC50 confidence intervals</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>~75% loss in statistical power for dose-response</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="bg-red-900/10 border border-red-700/30 rounded p-4">
              <h4 className="text-sm font-semibold text-red-300 mb-2">✗ VERDICT: SEVERE Power Loss</h4>
              <p className="text-sm text-slate-300 mb-3">
                v3's throughput gain (50% fewer plates) comes at a steep cost: EC50 estimates are 3.82× less precise.
                This makes dose-response characterization significantly less reliable.
              </p>
              <p className="text-sm text-slate-400 italic">
                Recommendation: Use v3 for cost-constrained screening or when rough dose-response is sufficient.
                Use v2 for establishing founder datasets or when precise EC50 estimates are critical.
              </p>
            </div>
          </div>

          {/* When to Use Each Design */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">When to Use Each Design</h3>
            <div className="space-y-4">
              <div className="bg-slate-900/50 border border-violet-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-violet-400 mb-2">Use v2 (Separated, High Power)</h4>
                <ul className="space-y-1 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Establishing founder/reference datasets</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Need precise EC50 estimates for dose selection</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Statistical power is critical for downstream decisions</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Cost/throughput is not the limiting factor</span>
                  </li>
                </ul>
              </div>

              <div className="bg-slate-900/50 border border-cyan-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-cyan-400 mb-2">Use v3 (Mixed Checkerboard, Lower Power)</h4>
                <ul className="space-y-1 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Cost/plate supply is limiting</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Rough dose-response screening is sufficient</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Already have good EC50 estimates from v2</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Prioritizing paired cell-line comparisons</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Principles View */}
      {activeView === 'principles' && (
        <div className="space-y-6">
          {/* Design Principles */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Design Principles</h3>
            <div className="space-y-4">
              {Object.entries(catalog.design_principles).map(([key, value]) => (
                <div key={key}>
                  <h4 className="text-sm font-semibold text-violet-400 mb-1 capitalize">
                    {key.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-sm text-slate-300">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Glossary */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Glossary</h3>
            <div className="space-y-3">
              {Object.entries(catalog.glossary).map(([term, definition]) => (
                <div key={term}>
                  <h4 className="text-sm font-semibold text-blue-400 mb-1 capitalize">
                    {term.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-sm text-slate-300">{definition}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DesignCatalogTab;
