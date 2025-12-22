import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, Zap } from 'lucide-react';
import PlateDesignCatalog from '../components/PlateDesignCatalog';
import CalibrationPlateViewer from '../components/CalibrationPlateViewer';
import RunsBrowser from '../components/RunsBrowser';
import PlateViewer, { WellData } from '../components/shared/PlateViewer';
import PlateLegend, { LegendItem } from '../components/shared/PlateLegend';

type AnyJson = Record<string, any>;

type EpisodeEvent = {
  t: number;
  cycle: number;
  kind: string;
  summary: string;
  payload: AnyJson;
  source: "evidence" | "decisions" | "diagnostics" | "unknown";
  priority: number; // For stable ordering within cycle
};

type KeyMoment = {
  index: number;
  cycle: number;
  kind: "refusal" | "gate" | "noise" | "stall" | "regime_change";
  summary: string;
};

function parseJsonl(text: string): AnyJson[] {
  return text
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.length > 0)
    .map(l => {
      try { return JSON.parse(l); }
      catch { return { _parse_error: true, _raw: l }; }
    });
}

function asNumber(x: any, fallback = 0): number {
  const n = typeof x === "number" ? x : Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function smartSummarizeEvidence(row: AnyJson): string {
  const belief = row.belief ?? "";
  const note = row.note ?? "";

  // Gate events - make them pop
  if (belief.includes("gate_event:")) {
    const gate = belief.replace("gate_event:", "");
    return `✓ Gate earned: ${gate}`;
  }
  if (belief.includes("gate_loss:")) {
    const gate = belief.replace("gate_loss:", "");
    return `✗ Gate lost: ${gate}`;
  }

  // Noise stability - clear language
  if (belief === "noise_sigma_stable") {
    return row.new ? "✓ Noise calibration stable" : "✗ Noise calibration degraded";
  }

  // Dose/time discoveries
  if (belief === "dose_curvature_seen") {
    return "📈 Nonlinear dose-response detected";
  }
  if (belief === "time_dependence_seen") {
    return "⏱ Time-dependent response detected";
  }

  // Edge effects
  if (belief === "edge_effect_confident") {
    return row.new ? "✓ Edge effects characterized" : "Edge effects uncertain";
  }

  // Fallback to note if present, otherwise belief name
  if (note) return note;
  return belief || "evidence";
}

function smartSummarizeDecision(row: AnyJson): string {
  const selected = row.chosen_template ?? row.selected ?? "";
  const chosenKwargs = row.chosen_kwargs ?? {};
  const rationale = row.rationale ?? {};
  const reason = chosenKwargs.reason ?? row.reason ?? "";
  const candidate = row.selected_candidate ?? rationale;
  const gateState = candidate.gate_state ?? {};
  const regime = candidate.regime ?? "";

  // Forced calibration - highlight urgency
  if (candidate.forced) {
    return `🔴 FORCED: ${reason}`;
  }

  // Regime changes
  if (regime === "pre_gate") {
    return `🔧 Calibrating: ${reason}`;
  }
  if (regime === "in_gate") {
    // Check if just earned gate
    if (gateState.noise_sigma === "earned") {
      return `🎯 ${selected}: ${reason}`;
    }
  }

  // Default with template name
  return `${selected}: ${reason}`;
}

function smartSummarizeDiagnostic(row: AnyJson): string {
  const name = row.name ?? row.diagnostic ?? row.kind ?? "diagnostic";
  const msg = row.message ?? row.note ?? row.summary;
  if (msg) return `${String(name)}: ${String(msg)}`;
  return String(name);
}

function toEpisodeEvents(rows: AnyJson[], source: EpisodeEvent["source"]): EpisodeEvent[] {
  // Priority for stable ordering within cycle: decisions first, evidence second, diagnostics last
  const priority = source === "decisions" ? 0 : source === "evidence" ? 1 : 2;

  return rows.map((row, idx) => {
    const cycle = asNumber(row.cycle ?? row.step ?? row.iteration, -1);
    const kind =
      source === "evidence" ? "EVIDENCE" :
      source === "decisions" ? "DECISION" :
      source === "diagnostics" ? "DIAGNOSTIC" : "EVENT";

    const summary =
      source === "evidence" ? smartSummarizeEvidence(row) :
      source === "decisions" ? smartSummarizeDecision(row) :
      source === "diagnostics" ? smartSummarizeDiagnostic(row) :
      (row.summary ?? row.message ?? kind);

    return {
      t: idx,
      cycle,
      kind,
      summary,
      payload: row,
      source,
      priority,
    };
  });
}

function groupByCycle(events: EpisodeEvent[]): Map<number, EpisodeEvent[]> {
  const m = new Map<number, EpisodeEvent[]>();
  for (const e of events) {
    const c = Number.isFinite(e.cycle) ? e.cycle : -1;
    if (!m.has(c)) m.set(c, []);
    m.get(c)!.push(e);
  }
  return m;
}

function detectKeyMoments(events: EpisodeEvent[]): KeyMoment[] {
  const moments: KeyMoment[] = [];

  events.forEach((e, i) => {
    const summary = e.summary.toLowerCase();
    const belief = e.payload.belief ?? "";
    const selected = e.payload.selected ?? "";

    // Refusal detection
    if (summary.includes("refuse") || summary.includes("refusal") || summary.includes("blocked")) {
      moments.push({ index: i, cycle: e.cycle, kind: "refusal", summary: "Agent refused action" });
    }

    // Gate events
    if (belief.includes("gate_event:") || belief.includes("gate_loss:")) {
      moments.push({
        index: i,
        cycle: e.cycle,
        kind: "gate",
        summary: belief.includes("gate_loss:") ? "Gate lost" : "Gate earned"
      });
    }

    // Noise diagnostics
    if (belief === "noise_sigma_stable" || summary.includes("noise") || summary.includes("calibrat")) {
      const isStable = e.payload.new === true && belief === "noise_sigma_stable";
      if (isStable) {
        moments.push({ index: i, cycle: e.cycle, kind: "noise", summary: "Noise gate earned" });
      }
    }

    // Regime changes
    if (e.source === "decisions") {
      const candidate = e.payload.selected_candidate ?? {};
      const regime = candidate.regime ?? "";
      const prevRegime = i > 0 ? events[i-1].payload.selected_candidate?.regime : null;

      if (regime && regime !== prevRegime) {
        moments.push({
          index: i,
          cycle: e.cycle,
          kind: "regime_change",
          summary: `Entered ${regime} regime`
        });
      }
    }

    // Stalls (if present)
    if (summary.includes("stall") || summary.includes("cannot proceed") || summary.includes("blocked")) {
      moments.push({ index: i, cycle: e.cycle, kind: "stall", summary: "Agent stalled" });
    }
  });

  return moments;
}

function generateCycleNarrator(cycleEvents: EpisodeEvent[]): string {
  // Check what happened in this cycle
  const hasRefusal = cycleEvents.some(e =>
    e.summary.toLowerCase().includes("refuse") || e.summary.toLowerCase().includes("blocked")
  );
  const hasGateEarned = cycleEvents.some(e =>
    e.payload.belief?.includes("gate_event:")
  );
  const hasGateLost = cycleEvents.some(e =>
    e.payload.belief?.includes("gate_loss:")
  );
  const hasNoiseStable = cycleEvents.some(e =>
    e.payload.belief === "noise_sigma_stable" && e.payload.new === true
  );
  const hasForcedCalibration = cycleEvents.some(e =>
    e.payload.rationale?.forced === true || e.payload.selected_candidate?.forced === true
  );
  const decisions = cycleEvents.filter(e => e.source === "decisions");
  const regime = decisions[0]?.payload.rationale?.regime ?? decisions[0]?.payload.selected_candidate?.regime;

  // Extract cost information if available
  const decision = decisions[0];
  const chosenKwargs = decision?.payload.chosen_kwargs ?? {};
  const rationale = decision?.payload.rationale ?? {};
  const batchSizing = chosenKwargs.batch_sizing ?? decision?.payload.selected_candidate?.batch_sizing;
  const nReps = chosenKwargs.n_reps ?? decision?.payload.selected_candidate?.n_reps;
  const wellsUsed = batchSizing?.wells_used || (nReps ? nReps * 16 : 12);
  const costPerDf = batchSizing?.cost_per_df;

  // Priority-based narrator with cost context
  if (hasRefusal) return "The agent refused to act due to epistemic constraints.";
  if (hasGateLost) return "Calibration degraded—gate lost.";
  if (hasNoiseStable) {
    if (costPerDf) {
      return `Noise calibration achieved—gate earned! Used ${wellsUsed} wells at $${costPerDf.toFixed(1)}/df.`;
    }
    return "Noise calibration achieved—gate earned.";
  }
  if (hasGateEarned) return "The agent earned a capability gate.";
  if (hasForcedCalibration) return "Forced to recalibrate before proceeding.";
  if (regime === "pre_gate") {
    if (costPerDf && wellsUsed > 50) {
      return `Earning trust in the instrument. Using ${wellsUsed} wells to amortize fixed costs ($${costPerDf.toFixed(1)}/df).`;
    }
    return "Earning trust in the instrument.";
  }
  if (regime === "in_gate") return "Operating with earned calibration.";

  return "The agent updated beliefs and chose next action.";
}

// Cost Tracker Component
interface CostTrackerProps {
  visibleEvents: EpisodeEvent[];
  isDarkMode: boolean;
}

function CostTracker({ visibleEvents, isDarkMode }: CostTrackerProps) {
  // Extract all decisions with cost information
  const decisions = visibleEvents.filter(e => e.source === "decisions");

  let cumulativeCost = 0;
  let cumulativeDf = 0;
  let cycleCount = 0;

  const costPerCycle: Array<{cycle: number, cost: number, df: number, costPerDf: number}> = [];

  decisions.forEach(decision => {
    const chosenKwargs = decision.payload.chosen_kwargs ?? {};
    const rationale = decision.payload.rationale ?? {};
    const batchSizing = chosenKwargs.batch_sizing ?? decision.payload.selected_candidate?.batch_sizing;
    const calibrationPlan = rationale.calibration_plan ?? decision.payload.selected_candidate?.calibration_plan;

    if (batchSizing) {
      cycleCount++;
      const dfGain = batchSizing.df_gain_expected || 11;
      const costPerDf = batchSizing.cost_per_df || 0;
      const cycleCost = costPerDf * dfGain;

      cumulativeCost += cycleCost;
      cumulativeDf += dfGain;

      costPerCycle.push({
        cycle: decision.cycle,
        cost: cycleCost,
        df: dfGain,
        costPerDf: costPerDf
      });
    }
  });

  const avgCostPerDf = cumulativeDf > 0 ? cumulativeCost / cumulativeDf : 0;

  return (
    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
      <div className={`font-bold text-lg mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
        Cost Efficiency Tracker
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
          <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>Total Cost</div>
          <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
            ${cumulativeCost.toFixed(0)}
          </div>
        </div>

        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
          <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>Degrees of Freedom</div>
          <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
            {cumulativeDf}
          </div>
        </div>

        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
          <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>Avg Cost/DF</div>
          <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
            ${avgCostPerDf.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Cycle-by-cycle breakdown */}
      {costPerCycle.length > 0 && (
        <div>
          <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
            Per-Cycle Breakdown
          </div>
          <div className="space-y-1">
            {costPerCycle.map((c, idx) => (
              <div key={idx} className={`flex justify-between text-xs p-2 rounded ${isDarkMode ? 'bg-slate-900/30' : 'bg-zinc-50'}`}>
                <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  Cycle {c.cycle}
                </span>
                <span className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                  ${c.cost.toFixed(0)} / {c.df} df = ${c.costPerDf.toFixed(1)}/df
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Efficiency insight */}
      {cycleCount > 0 && (
        <div className={`mt-4 p-3 rounded text-sm ${isDarkMode ? 'bg-indigo-900/20 border border-indigo-700/50' : 'bg-indigo-50 border border-indigo-200'}`}>
          <div className={`font-bold mb-1 ${isDarkMode ? 'text-indigo-300' : 'text-indigo-900'}`}>
            💡 Efficiency Insight
          </div>
          <div className={isDarkMode ? 'text-indigo-200' : 'text-indigo-800'}>
            {cycleCount === 1 ? (
              `Earned gate in 1 cycle using large batches to amortize fixed costs.`
            ) : cycleCount <= 3 ? (
              `Completed calibration in ${cycleCount} cycles with average efficiency of $${avgCostPerDf.toFixed(1)}/df.`
            ) : (
              `Took ${cycleCount} cycles to calibrate. Small batches increase per-df costs due to fixed costs (~$465/cycle for plate + imaging + analyst).`
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Cycle Detail View Component
interface CycleDetailProps {
  cycle: number;
  events: EpisodeEvent[];
  isDarkMode: boolean;
}

function CycleDetailView({ cycle, events, isDarkMode }: CycleDetailProps) {
  // Extract decision and evidence events
  const decision = events.find(e => e.source === "decisions");
  const evidenceEvents = events.filter(e => e.source === "evidence");

  if (!decision) return null;

  const rationale = decision.payload.rationale ?? decision.payload.selected_candidate ?? {};
  const chosenKwargs = decision.payload.chosen_kwargs ?? {};
  const gateState = rationale.gate_state ?? {};
  const metrics = rationale.metrics ?? {};
  const calibrationPlan = rationale.calibration_plan;
  const batchSizing = chosenKwargs.batch_sizing;

  return (
    <div className="space-y-4">
      {/* Pre-Cycle: What Agent Knows */}
      <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`font-bold text-sm mb-3 ${isDarkMode ? 'text-indigo-300' : 'text-indigo-900'}`}>
          📚 Knowledge Going Into Cycle {cycle}
        </div>

        {/* Gate Status */}
        <div className="space-y-2 text-sm">
          <div className={`font-bold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
            Gate Status:
          </div>
          <div className="grid grid-cols-2 gap-2 pl-3">
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Noise: <span className={gateState.noise_sigma === "earned" ? "text-green-400 font-bold" : "text-yellow-400"}>{gateState.noise_sigma || "unknown"}</span>
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Edge: <span className={gateState.edge_effect === "confident" ? "text-green-400 font-bold" : "text-yellow-400"}>{gateState.edge_effect || "unknown"}</span>
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              LDH: <span className={gateState.ldh === "earned" ? "text-green-400 font-bold" : "text-yellow-400"}>{gateState.ldh || "lost"}</span>
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Cell Paint: <span className={gateState.cell_paint === "earned" ? "text-green-400 font-bold" : "text-yellow-400"}>{gateState.cell_paint || "lost"}</span>
            </div>
          </div>

          {/* Metrics */}
          {Object.keys(metrics).length > 0 && (
            <>
              <div className={`font-bold mt-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                Current Metrics:
              </div>
              <div className="pl-3 space-y-1">
                {metrics.noise_rel_width !== undefined && (
                  <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                    Noise CI width: {(metrics.noise_rel_width * 100).toFixed(1)}% {metrics.noise_rel_width <= 0.25 ? "✓" : ""}
                  </div>
                )}
                {metrics.df_needed !== undefined && (
                  <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                    DF needed: {metrics.df_needed} (current: {calibrationPlan?.df_current ?? 0})
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Decision: Why This Action */}
      <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`font-bold text-sm mb-3 ${isDarkMode ? 'text-green-300' : 'text-green-900'}`}>
          🎯 Decision: {decision.payload.chosen_template || decision.payload.selected}
        </div>

        <div className="space-y-2 text-sm">
          <div className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
            <span className="font-bold">Reasoning:</span> {rationale.summary || chosenKwargs.reason}
          </div>

          {rationale.regime && (
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              <span className="font-bold">Regime:</span> {rationale.regime}
              {rationale.forced && <span className="text-red-400 font-bold ml-2">⚠ FORCED</span>}
            </div>
          )}

          {batchSizing && (
            <div className={`p-2 rounded mt-2 ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
              <div className={`font-bold mb-1 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                Batch Sizing:
              </div>
              <div className="space-y-0.5 pl-2">
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  Wells: {batchSizing.wells_used}
                </div>
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  Expected DF: {batchSizing.df_gain_expected}
                </div>
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  Cost/DF: {batchSizing.cost_per_df !== null && batchSizing.cost_per_df !== undefined ? `$${batchSizing.cost_per_df.toFixed(1)}` : "N/A"}
                </div>
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  Strategy: {batchSizing.reason_code}
                </div>
              </div>
            </div>
          )}

          {rationale.rules_fired && rationale.rules_fired.length > 0 && (
            <div className="pt-2">
              <div className={`text-xs font-bold ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                Rules Fired:
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {rationale.rules_fired.map((rule: string, i: number) => (
                  <span key={i} className={`text-xs px-2 py-0.5 rounded ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-200 text-zinc-700'}`}>
                    {rule}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Plate Map */}
      <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`font-bold text-sm mb-3 ${isDarkMode ? 'text-purple-300' : 'text-purple-900'}`}>
          🧪 Plate Layout
        </div>
        <PlatePreview
          template={decision.payload.chosen_template ?? decision.payload.selected}
          nReps={chosenKwargs.n_reps}
          regime={rationale.regime}
          forced={rationale.forced}
          calibrationPlan={calibrationPlan}
          batchSizing={batchSizing}
          isDarkMode={isDarkMode}
        />
      </div>

      {/* Post-Cycle: What Was Learned */}
      {evidenceEvents.length > 0 && (
        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
          <div className={`font-bold text-sm mb-3 ${isDarkMode ? 'text-yellow-300' : 'text-yellow-900'}`}>
            💡 Evidence Gathered ({evidenceEvents.length} events)
          </div>

          <div className="space-y-1 text-xs max-h-60 overflow-auto">
            {evidenceEvents.map((e, i) => {
              const belief = e.payload.belief ?? "";
              const note = e.payload.note ?? "";

              // Highlight important events
              const isGate = belief.includes("gate_event") || belief.includes("gate_loss");
              const isCalibration = belief.includes("noise_") || belief.includes("_sigma_");

              return (
                <div
                  key={i}
                  className={`p-2 rounded ${
                    isGate
                      ? isDarkMode ? 'bg-green-900/30 border border-green-700' : 'bg-green-50 border border-green-200'
                      : isCalibration
                        ? isDarkMode ? 'bg-blue-900/30 border border-blue-700' : 'bg-blue-50 border border-blue-200'
                        : isDarkMode ? 'bg-slate-900/30' : 'bg-zinc-50'
                  }`}
                >
                  <div className={`font-mono ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {belief}
                  </div>
                  <div className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>
                    {note || e.summary}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// Simple Plate Preview Component
interface PlatePreviewProps {
  template: string;
  nReps?: number;
  regime?: string;
  forced?: boolean;
  calibrationPlan?: {
    df_current?: number;
    df_needed?: number;
    wells_needed?: number;
    rel_width?: number;
  };
  batchSizing?: {
    wells_used?: number;
    df_gain_expected?: number;
    cost_per_df?: number;
    reason_code?: string;
  };
  isDarkMode: boolean;
}

function PlatePreview({ template, nReps, regime, forced, calibrationPlan, isDarkMode, batchSizing }: PlatePreviewProps) {
  // Estimate wells based on template - this is per-cycle, not total needed
  const getWellEstimate = () => {
    if (batchSizing?.wells_used) return batchSizing.wells_used;
    if (template === "baseline_replicates") return nReps ? nReps * 16 : 12;
    if (template === "dose_ladder_coarse") return 16; // 4 doses x 4 reps typical
    if (template === "dose_ladder_fine") return 32;
    if (template === "edge_center_test") return 24;
    return 12;
  };

  const wellsThisCycle = getWellEstimate();
  const rows = 16;  // 384-well plate
  const cols = 24;

  // Create a simple pattern based on template type
  const isWellFilled = (r: number, c: number) => {
    const idx = r * cols + c;
    if (template === "baseline_replicates") {
      // Fill first N wells in row A
      return r === 0 && c < wellsThisCycle;
    }
    if (template.includes("dose_ladder")) {
      // Fill in vertical strips (dose ladder pattern)
      return c < Math.ceil(wellsThisCycle / 4) && r < 4;
    }
    if (template.includes("edge_center")) {
      // Edge and center wells
      return (r === 0 || r === 7 || c === 0 || c === 11) && idx < wellsThisCycle;
    }
    return idx < wellsThisCycle;
  };

  const getWellColor = (r: number, c: number) => {
    if (!isWellFilled(r, c)) return null;

    if (forced) {
      return isDarkMode ? 'bg-red-500/80' : 'bg-red-400/80';
    }
    if (regime === "pre_gate") {
      return isDarkMode ? 'bg-yellow-500/80' : 'bg-yellow-400/80';
    }
    if (regime === "in_gate") {
      return isDarkMode ? 'bg-green-500/80' : 'bg-green-400/80';
    }
    return isDarkMode ? 'bg-indigo-500/80' : 'bg-indigo-400/80';
  };

  // Generate well data for standardized PlateViewer
  const wellData: WellData[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const wellId = `${String.fromCharCode(65 + r)}${c + 1}`;
      const color = getWellColor(r, c);
      if (color) {
        wellData.push({
          id: wellId,
          color: color,
          borderColor: isDarkMode ? '#475569' : '#d4d4d8',
          borderWidth: 1,
        });
      }
    }
  }

  // Legend items
  const legendItems: LegendItem[] = [];
  if (forced) {
    legendItems.push({
      label: 'Forced',
      color: isDarkMode ? 'bg-red-500' : 'bg-red-400',
    });
  }
  if (regime === "pre_gate") {
    legendItems.push({
      label: 'Pre-gate',
      color: isDarkMode ? 'bg-yellow-500' : 'bg-yellow-400',
    });
  }
  if (regime === "in_gate") {
    legendItems.push({
      label: 'In-gate',
      color: isDarkMode ? 'bg-green-500' : 'bg-green-400',
    });
  }

  return (
    <div className="space-y-2">
      <div className={`text-xs space-y-0.5 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
        <div><b>Template:</b> {template}</div>
        <div><b>This cycle:</b> {wellsThisCycle} wells / 384 available ({((wellsThisCycle/384)*100).toFixed(1)}% used)</div>
        {calibrationPlan && (
          <div className="space-y-0.5 pt-1 border-t border-slate-700/50">
            <div><b>Calibration progress:</b></div>
            <div className="pl-2">
              <div>Current df: {calibrationPlan.df_current ?? 0}</div>
              <div>Need: {calibrationPlan.df_needed ?? '?'} df ({calibrationPlan.wells_needed ?? '?'} wells total)</div>
              {calibrationPlan.rel_width && (
                <div>CI width: {(calibrationPlan.rel_width * 100).toFixed(1)}%</div>
              )}
            </div>
          </div>
        )}
        {batchSizing && (
          <div className="space-y-0.5 pt-1 border-t border-slate-700/50">
            <div><b>Cost analysis:</b></div>
            <div className="pl-2">
              <div>Wells used: {batchSizing.wells_used ?? wellsThisCycle}</div>
              <div>DF expected: {batchSizing.df_gain_expected ?? '?'}</div>
              {batchSizing.cost_per_df && (
                <div className="font-bold text-green-400">Cost/DF: ${batchSizing.cost_per_df.toFixed(1)}</div>
              )}
            </div>
          </div>
        )}
        {regime && <div><b>Regime:</b> {regime}</div>}
        {forced && <div className="text-red-400 font-bold">⚠ FORCED (must calibrate)</div>}
      </div>

      {/* 384-well plate using standardized PlateViewer */}
      <div className={`p-2 rounded ${isDarkMode ? 'bg-slate-950/50' : 'bg-white'}`}>
        <PlateViewer
          format="384"
          wells={wellData}
          isDarkMode={isDarkMode}
          size="small"
          showLabels={false}
          showAxisLabels={true}
        />
      </div>

      {/* Legend using standardized PlateLegend */}
      {legendItems.length > 0 && (
        <PlateLegend
          items={legendItems}
          isDarkMode={isDarkMode}
          layout="horizontal"
        />
      )}
    </div>
  );
}

type TabType = 'timeline' | 'catalog' | 'calibration' | 'runs';

const AVAILABLE_DESIGNS = [
  { id: 'v1', name: 'CAL_384_RULES_WORLD_v1', description: 'Simple calibration' },
  { id: 'v2', name: 'CAL_384_RULES_WORLD_v2', description: 'Advanced calibration' },
  { id: 'microscope', name: 'CAL_384_MICROSCOPE_BEADS_DYES_v1', description: 'Microscope calibration' },
  { id: 'lh', name: 'CAL_384_LH_ARTIFACTS_v1', description: 'Liquid handler artifacts' },
  { id: 'variance', name: 'CAL_VARIANCE_PARTITION_v1', description: 'Variance components' },
  { id: 'wash', name: 'CAL_EL406_WASH_DAMAGE_v1', description: 'Wash stress' },
  { id: 'dynamic', name: 'CAL_DYNAMIC_RANGE_v1', description: 'Dynamic range' }
];

export default function EpistemicDocumentaryPage() {
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('timeline');
  const [selectedDesign, setSelectedDesign] = useState('v1');
  const [showSimulateModal, setShowSimulateModal] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [plateData, setPlateData] = useState<any>(null);

  const RUN_BASE = "/demo_results/epistemic_agent/run_20251221_212354";

  const [events, setEvents] = useState<EpisodeEvent[]>([]);
  const [selected, setSelected] = useState<EpisodeEvent | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [speed, setSpeed] = useState(2);

  const generateJHCommand = (plateId: string, seed: number = 42) => {
    const platePath = `validation_frontend/public/plate_designs/${plateId}.json`;
    return `cd ~/repos/cell_OS && PYTHONPATH=. python3 src/cell_os/plate_executor_v2_parallel.py ${platePath} --seed ${seed} --auto-pull --auto-commit`;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2000);
  };

  const handleSimulate = (data: any) => {
    setPlateData(data);
    setShowSimulateModal(true);
  };

  useEffect(() => {
    async function load() {
      const [evidenceText, decisionsText] = await Promise.all([
        fetch(`${RUN_BASE}_evidence.jsonl`).then(r => r.text()),
        fetch(`${RUN_BASE}_decisions.jsonl`).then(r => r.text()),
      ]);

      let diagnosticsText = "";
      try {
        diagnosticsText = await fetch(`${RUN_BASE}_diagnostics.jsonl`).then(r => r.ok ? r.text() : "");
      } catch { diagnosticsText = ""; }

      const evidenceRows = parseJsonl(evidenceText);
      const decisionRows = parseJsonl(decisionsText);
      const diagnosticRows = diagnosticsText ? parseJsonl(diagnosticsText) : [];

      const ev = [
        ...toEpisodeEvents(evidenceRows, "evidence"),
        ...toEpisodeEvents(decisionRows, "decisions"),
        ...toEpisodeEvents(diagnosticRows, "diagnostics"),
      ];

      // Sort by cycle, then priority (decisions first), then original order
      ev.sort((a, b) => {
        const ac = Number.isFinite(a.cycle) ? a.cycle : 1e9;
        const bc = Number.isFinite(b.cycle) ? b.cycle : 1e9;
        if (ac !== bc) return ac - bc;
        if (a.priority !== b.priority) return a.priority - b.priority;
        return a.t - b.t;
      });

      const normalized = ev.map((x, i) => ({ ...x, t: i }));

      setEvents(normalized);
      setSelected(normalized[0] ?? null);
      setCursor(0);
      setIsPlaying(false);
    }
    load();
  }, []);

  // Playback
  useEffect(() => {
    if (!isPlaying) return;
    if (cursor >= events.length - 1) return;

    const intervalMs = Math.max(20, Math.floor(1000 / Math.max(0.25, speed)));
    const id = window.setInterval(() => {
      setCursor(c => Math.min(events.length - 1, c + 1));
    }, intervalMs);

    return () => window.clearInterval(id);
  }, [isPlaying, cursor, events.length, speed]);

  const visibleEvents = useMemo(() => events.slice(0, cursor + 1), [events, cursor]);
  const keyMoments = useMemo(() => detectKeyMoments(events), [events]);

  const cycles = useMemo(() => {
    const grouped = groupByCycle(visibleEvents);
    const keys = Array.from(grouped.keys()).sort((a, b) => a - b);
    return keys.map(k => {
      const cycleEvents = grouped.get(k)!;
      return {
        cycle: k,
        events: cycleEvents,
        narrator: generateCycleNarrator(cycleEvents)
      };
    });
  }, [visibleEvents]);

  const current = events[cursor] ?? null;

  // Economy HUD - extract gate state from most recent decision
  const recentDecisions = visibleEvents.filter(e => e.source === "decisions");
  const latestDecision = recentDecisions[recentDecisions.length - 1];
  const gateState = latestDecision?.payload.selected_candidate?.gate_state ?? {};
  const noiseGate = gateState.noise_sigma ?? "unknown";
  const edgeGate = gateState.edge_effect ?? "unknown";

  // Find next key moments after cursor
  const nextRefusal = keyMoments.find(m => m.index > cursor && m.kind === "refusal");
  const nextGate = keyMoments.find(m => m.index > cursor && m.kind === "gate");
  const nextNoise = keyMoments.find(m => m.index > cursor && m.kind === "noise");
  const nextRegimeChange = keyMoments.find(m => m.index > cursor && m.kind === "regime_change");

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDarkMode
      ? 'bg-gradient-to-b from-slate-900 to-slate-800'
      : 'bg-gradient-to-b from-zinc-50 to-white'
      }`}>
      {/* Header */}
      <div className={`backdrop-blur-sm border-b sticky top-0 z-50 transition-colors duration-300 ${isDarkMode
        ? 'bg-slate-800/80 border-slate-700'
        : 'bg-white/80 border-zinc-200'
        }`}>
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <button
                onClick={() => navigate('/')}
                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${isDarkMode
                  ? 'text-slate-400 hover:text-white'
                  : 'text-zinc-500 hover:text-zinc-900'
                  }`}
              >
                ← Back to Home
              </button>
              <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'
                }`}>
                Epistemic Documentary
              </h1>
              <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                }`}>
                Watch an agent learn to do science
              </p>
            </div>

            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`p-2 rounded-lg transition-all ${isDarkMode
                ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                }`}
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className={`border-b ${isDarkMode ? 'bg-slate-800/30 border-slate-700' : 'bg-zinc-50 border-zinc-200'}`}>
        <div className="container mx-auto px-6">
          <div className="flex space-x-1">
            <button
              onClick={() => setActiveTab('timeline')}
              className={`px-4 py-3 text-sm font-medium transition-all ${
                activeTab === 'timeline'
                  ? isDarkMode
                    ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50'
                    : 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
                  : isDarkMode
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800/30'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className="mr-2">📊</span>
              Timeline
            </button>
            <button
              onClick={() => setActiveTab('catalog')}
              className={`px-4 py-3 text-sm font-medium transition-all ${
                activeTab === 'catalog'
                  ? isDarkMode
                    ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50'
                    : 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
                  : isDarkMode
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800/30'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className="mr-2">🧪</span>
              Plate Designs
            </button>
            <button
              onClick={() => setActiveTab('calibration')}
              className={`px-4 py-3 text-sm font-medium transition-all ${
                activeTab === 'calibration'
                  ? isDarkMode
                    ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50'
                    : 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
                  : isDarkMode
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800/30'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className="mr-2">🔬</span>
              Calibration Plate
            </button>
            <button
              onClick={() => setActiveTab('runs')}
              className={`px-4 py-3 text-sm font-medium transition-all ${
                activeTab === 'runs'
                  ? isDarkMode
                    ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50'
                    : 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
                  : isDarkMode
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800/30'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className="mr-2">🔄</span>
              Runs
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-6">
        {activeTab === 'catalog' ? (
          <PlateDesignCatalog isDarkMode={isDarkMode} />
        ) : activeTab === 'calibration' ? (
          <div className="space-y-4">
            {/* Design Selector */}
            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
              <div className="flex items-center justify-between">
                <div className={`text-lg font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                  Calibration Plate Design
                </div>
                <select
                  value={selectedDesign}
                  onChange={(e) => setSelectedDesign(e.target.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${
                    isDarkMode
                      ? 'bg-slate-700 text-white border border-slate-600'
                      : 'bg-white text-zinc-900 border border-zinc-300'
                  }`}
                >
                  {AVAILABLE_DESIGNS.map(design => (
                    <option key={design.id} value={design.id}>
                      {design.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className={`text-sm mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                {AVAILABLE_DESIGNS.find(d => d.id === selectedDesign)?.description}
              </div>
            </div>

            <CalibrationPlateViewer
              designVersion={selectedDesign}
              isDarkMode={isDarkMode}
              onSimulate={handleSimulate}
            />
          </div>
        ) : activeTab === 'runs' ? (
          <RunsBrowser isDarkMode={isDarkMode} />
        ) : (
          <>
            {/* Simple Progress Bar */}
            <div className={`mb-4 p-3 rounded-lg flex items-center gap-4 ${isDarkMode
              ? 'bg-slate-800/50 border border-slate-700'
              : 'bg-white border border-zinc-200'
              }`}>
              <div className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                Cycle {current?.cycle ?? 0} / 20
              </div>
              <div className="flex-1">
                <div className={`h-2 rounded-full ${isDarkMode ? 'bg-slate-700' : 'bg-zinc-200'}`}>
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all"
                    style={{ width: `${((current?.cycle ?? 0) / 20) * 100}%` }}
                  />
                </div>
              </div>
              <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                {visibleEvents.filter(e => e.source === 'decisions').length} decisions made
              </div>
            </div>

        {/* Playback Controls */}
        <div className={`flex items-center gap-3 mb-4 p-4 rounded-lg ${isDarkMode ? 'bg-slate-800/50' : 'bg-white'
          }`}>
          <button
            onClick={() => setIsPlaying(p => !p)}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
              ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
              : 'bg-indigo-500 hover:bg-indigo-600 text-white'
              }`}
          >
            {isPlaying ? "⏸ Pause" : "▶ Play"}
          </button>
          <button
            onClick={() => setCursor(c => Math.max(0, c - 1))}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
              ? 'bg-slate-700 hover:bg-slate-600 text-white'
              : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
              }`}
          >
            ⏮ Back
          </button>
          <button
            onClick={() => setCursor(c => Math.min(events.length - 1, c + 1))}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
              ? 'bg-slate-700 hover:bg-slate-600 text-white'
              : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
              }`}
          >
            Forward ⏭
          </button>
          <button
            onClick={() => { setCursor(0); setIsPlaying(false); }}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
              ? 'bg-slate-700 hover:bg-slate-600 text-white'
              : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
              }`}
          >
            ⏪ Reset
          </button>

          <label className="flex items-center gap-2 ml-4">
            <span className={isDarkMode ? 'text-slate-300' : 'text-zinc-700'}>Speed</span>
            <input
              type="range"
              min={0.5}
              max={10}
              step={0.5}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="w-24"
            />
            <span className={`min-w-[3rem] ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              {speed.toFixed(1)}x
            </span>
          </label>
        </div>

        {/* Cycle-by-Cycle Detail View */}
        <div className={`rounded-lg p-6 max-h-[75vh] overflow-auto ${isDarkMode
          ? 'bg-slate-800/50 border border-slate-700'
          : 'bg-white border border-zinc-200'
          }`}>
          {cycles.map(group => (
            <div key={group.cycle} className="mb-10 last:mb-0">
              <div className="mb-4">
                <div className={`font-bold text-2xl ${isDarkMode ? 'text-white' : 'text-zinc-900'
                  }`}>
                  {group.cycle >= 0 ? `Cycle ${group.cycle}` : "Uncycled"}
                </div>
                <div className={`text-sm italic mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'
                  }`}>
                  {group.narrator}
                </div>
              </div>

              <CycleDetailView
                cycle={group.cycle}
                events={group.events}
                isDarkMode={isDarkMode}
              />
            </div>
          ))}
        </div>
          </>
        )}
      </div>

      {/* Simulate Modal */}
      {showSimulateModal && plateData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`max-w-3xl w-full rounded-lg shadow-xl ${isDarkMode ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
            {/* Modal Header */}
            <div className={`p-6 border-b ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    🚀 Run on JupyterHub
                  </div>
                  <div className={`text-sm mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {plateData.plate.plate_id} - Parallel Execution
                  </div>
                </div>
                <button
                  onClick={() => setShowSimulateModal(false)}
                  className={`text-2xl ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-zinc-400 hover:text-zinc-900'}`}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {/* Instructions */}
              <div>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  Instructions:
                </div>
                <ol className={`text-sm space-y-1 list-decimal list-inside ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  <li>Copy the command below</li>
                  <li>Open a terminal on JupyterHub</li>
                  <li>Paste and run the command</li>
                  <li>Results will auto-pull locally and appear in the Runs tab (~2-3 minutes)</li>
                </ol>
              </div>

              {/* Command Box */}
              <div>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  Command:
                </div>
                <div className="relative">
                  <pre className={`p-4 rounded-lg text-sm font-mono overflow-x-auto ${isDarkMode ? 'bg-slate-900 text-green-400' : 'bg-zinc-100 text-zinc-900'}`}>
                    {generateJHCommand(plateData.plate.plate_id)}
                  </pre>
                  <button
                    onClick={() => copyToClipboard(generateJHCommand(plateData.plate.plate_id))}
                    className={`absolute top-2 right-2 px-3 py-1 rounded text-xs font-medium transition-all ${
                      copiedCommand
                        ? isDarkMode
                          ? 'bg-green-600 text-white'
                          : 'bg-green-500 text-white'
                        : isDarkMode
                          ? 'bg-slate-700 hover:bg-slate-600 text-white'
                          : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                    }`}
                  >
                    {copiedCommand ? '✓ Copied!' : 'Copy'}
                  </button>
                </div>
              </div>

              {/* Execution Details */}
              <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  What happens:
                </div>
                <ul className={`text-sm space-y-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  <li>✓ Auto-pulls latest code</li>
                  <li>✓ Generates unique run ID (timestamp-based)</li>
                  <li>✓ Executes 384 wells in parallel</li>
                  <li>✓ Updates runs manifest</li>
                  <li>✓ Auto-commits and pushes results</li>
                  <li>✓ Expected duration: ~2-3 minutes</li>
                </ul>
              </div>
            </div>

            {/* Modal Footer */}
            <div className={`p-6 border-t ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowSimulateModal(false)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                    ? 'bg-slate-700 hover:bg-slate-600 text-white'
                    : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                  }`}
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    copyToClipboard(generateJHCommand(plateData.plate.plate_id));
                  }}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                    ? 'bg-green-600 hover:bg-green-500 text-white'
                    : 'bg-green-500 hover:bg-green-600 text-white'
                  }`}
                >
                  {copiedCommand ? '✓ Copied!' : 'Copy Command'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
