import React from 'react';

interface CommentaryPanelProps {
  cycle: number;
  cycleEvents: any[];
  isDarkMode: boolean;
  budgetRemaining: number;
  totalBudget: number;
}

/**
 * Director's Commentary Panel
 *
 * Provides interpretation and context for the current cycle.
 * This is NOT a chatbot - it's a passive voice that updates with cycle changes.
 *
 * Tone rules:
 * 1. Explain, don't justify
 * 2. Name constraints without embarrassment
 * 3. Acknowledge suboptimality explicitly
 * 4. Never celebrate gates
 * 5. Never apologize for refusals
 * 6. Prefer calm certainty over dramatic language
 * 7. Assume the viewer is smart but impatient
 */
export default function CommentaryPanel({
  cycle,
  cycleEvents,
  isDarkMode,
  budgetRemaining,
  totalBudget,
}: CommentaryPanelProps) {
  const commentary = generateCommentary(cycle, cycleEvents, budgetRemaining, totalBudget);

  if (!commentary) {
    return null;
  }

  return (
    <div
      className={`fixed top-20 right-6 w-[380px] max-h-[calc(100vh-120px)] overflow-y-auto rounded-lg p-6 shadow-lg ${
        isDarkMode
          ? 'bg-slate-900/40 backdrop-blur-sm border border-slate-700/50'
          : 'bg-white/40 backdrop-blur-sm border border-zinc-200/50'
      }`}
    >
      {/* Header */}
      <div className={`text-xs uppercase tracking-wider mb-4 ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
        Commentary · Cycle {cycle}
      </div>

      {/* Body */}
      <div className={`space-y-4 text-sm leading-relaxed ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
        {commentary.paragraphs.map((para, idx) => (
          <p key={idx}>{para}</p>
        ))}
      </div>

      {/* Footer context (if present) */}
      {commentary.context && (
        <div
          className={`mt-4 pt-4 border-t text-xs ${
            isDarkMode ? 'border-slate-700/50 text-slate-500' : 'border-zinc-200 text-zinc-600'
          }`}
        >
          {commentary.context}
        </div>
      )}
    </div>
  );
}

interface Commentary {
  paragraphs: string[];
  context?: string;
}

function generateCommentary(
  cycle: number,
  cycleEvents: any[],
  budgetRemaining: number,
  totalBudget: number
): Commentary | null {
  if (cycleEvents.length === 0) return null;

  const decision = cycleEvents.find((e) => e.source === 'decisions');
  const evidenceEvents = cycleEvents.filter((e) => e.source === 'evidence');
  const diagnosticEvents = cycleEvents.filter((e) => e.source === 'diagnostics');

  if (!decision) return null;

  // Check for refusal in diagnostics
  const refusalDiag = diagnosticEvents.find((e) => e.payload?.event_type === 'epistemic_debt_status' && !e.payload?.action_allowed);
  if (refusalDiag) {
    const payload = refusalDiag.payload ?? {};
    const debtBits = payload.debt_bits ?? 0;
    const isDeadlocked = payload.is_deadlocked ?? false;
    const blockedByReserve = payload.blocked_by_reserve ?? false;

    if (isDeadlocked) {
      return {
        paragraphs: [
          "Refusal: epistemic debt threshold exceeded.",
          `The agent accumulated ${debtBits.toFixed(1)} bits of overclaim—it made statements with more confidence than the data warranted.`,
          "Now it's blocked. Any non-calibration action would cost 1.5× normal budget due to debt inflation. But budget remaining is insufficient even for that.",
          "This is epistemic deadlock. The agent cannot do science (debt blocks it), calibrate (budget too low), or recover (no path forward).",
          "This isn't a bug. It's a feature. The agent refuses to continue when honest operation is impossible.",
          "Terminal failure.",
        ],
        context: `Debt: ${debtBits.toFixed(1)} bits · Budget: ${budgetRemaining} wells`,
      };
    }

    if (blockedByReserve) {
      return {
        paragraphs: [
          "Action refused: budget reserve violation.",
          `The agent would need to reserve ${payload.required_reserve ?? 0} wells for potential epistemic recovery.`,
          "Executing this action would leave insufficient budget for calibration if debt increases further.",
          "This is deadlock prevention—refusing early to avoid terminal failure later.",
        ],
        context: `Debt: ${debtBits.toFixed(1)} bits · Budget: ${budgetRemaining} wells`,
      };
    }

    return {
      paragraphs: [
        "Action refused: epistemic debt exceeded threshold.",
        `The agent accumulated ${debtBits.toFixed(1)} bits of overclaim. Only calibration actions are permitted until debt is repaid.`,
        "This asymmetric enforcement means: overclaiming blocks you, underclaiming doesn't.",
      ],
      context: `Debt: ${debtBits.toFixed(1)} bits · Budget: ${budgetRemaining} wells`,
    };
  }

  const rationale = decision.payload?.rationale ?? decision.payload?.selected_candidate ?? {};
  const template = decision.payload?.chosen_template ?? decision.payload?.selected ?? '';
  const regime = rationale.regime ?? '';
  const forced = rationale.forced ?? false;
  const gateState = rationale.gate_state ?? {};
  const chosenKwargs = decision.payload?.chosen_kwargs ?? {};

  // Check for special cycle types
  const trigger = decision.payload?.selected_candidate?.trigger ?? chosenKwargs?.purpose ?? '';
  const isCycle0 = trigger === 'cycle0_required' || chosenKwargs?.purpose === 'instrument_shape_learning';

  // Check for gates earned this cycle
  const gatesEarned = evidenceEvents.filter((e) => e.payload?.belief?.includes('gate_event:'));
  const gatesLost = evidenceEvents.filter((e) => e.payload?.belief?.includes('gate_loss:'));
  const noiseStable = evidenceEvents.some(
    (e) => e.payload?.belief === 'noise_sigma_stable' && e.payload?.new === true
  );

  // Cycle 0: Instrument shape learning
  if (isCycle0 || cycle === 0) {
    return {
      paragraphs: [
        "The agent hasn't started science yet. This is forced calibration—learning the \"shape\" of the instrument before making any claims.",
        "Think of this as: \"Before I tell you what I see, let me verify that my microscope isn't lying to me.\"",
        "The Moran's I test checks for spatial confounding. If controls show gradients (edge effects, plate artifacts), the agent learns that before attributing patterns to biology.",
        "This looks like overhead. But without it, every conclusion later would be contaminated by instrument noise.",
      ],
      context: `Cost: ~96 wells. Unavoidable.`,
    };
  }

  // Forced calibration (pre-gate regime)
  if (regime === 'pre_gate' || forced) {
    const batchSizing = chosenKwargs.batch_sizing ?? {};
    const costPerDf = batchSizing.cost_per_df;
    const inflationNote = costPerDf && costPerDf > 20 ? ' Notice the cost inflation.' : '';

    return {
      paragraphs: [
        "Still calibrating. The agent wants to test compounds, but refuses.",
        "Why? The noise estimate (σ) is too uncertain. If you don't know measurement precision, you can't distinguish signal from noise.",
        `The cost inflation you see is epistemic debt—every claim made without sufficient calibration makes future actions more expensive.${inflationNote}`,
        "The agent is trading short-term progress for long-term identifiability. A human scientist under deadline pressure might gamble here.",
        "The agent refuses.",
      ],
    };
  }

  // Gate earned
  if (noiseStable || gatesEarned.length > 0) {
    const gateName = gatesEarned[0]?.payload?.belief?.split(':')[1] ?? 'noise_sigma';
    const batchSizing = chosenKwargs.batch_sizing ?? {};
    const wellsUsed = batchSizing.wells_used ?? 96;
    const sizeNote = wellsUsed < 50 ? ' Notice wells drop to optimized batches.' : '';

    return {
      paragraphs: [
        `Gate earned: ${gateName}.`,
        "This isn't a celebration. It's a permission slip.",
        "The agent can now make statements like \"compound X reduced viability by 40%\" with known uncertainty bounds.",
        "Before this gate: every measurement was suspect. After this gate: measurements can support or refute hypotheses.",
        `The batch sizing changes here—fixed costs are amortized. Now the agent optimizes for information density, not df accumulation.${sizeNote}`,
        "This is the inflection point.",
      ],
      context: `Budget remaining: ${budgetRemaining} wells`,
    };
  }

  // Normal science (in-gate regime)
  if (regime === 'in_gate') {
    const hypothesis = decision.payload?.hypothesis ?? '';
    const nReps = chosenKwargs.n_reps ?? 4;

    return {
      paragraphs: [
        "Operating with earned calibration.",
        `The agent chose ${template} (${nReps} replicates). This design trades coverage for resolution.`,
        hypothesis
          ? `Hypothesis: "${hypothesis}". This isn't a fishing expedition—it's a structured bet on where information is hiding.`
          : "The agent is no longer in survival mode.",
      ],
      context: `Budget remaining: ${budgetRemaining} wells`,
    };
  }

  // Gate lost
  if (gatesLost.length > 0) {
    return {
      paragraphs: [
        "Gate lost. Calibration degraded.",
        "The agent must recalibrate before continuing. This isn't optional—measurement trust has been violated.",
        "This could be noise drift, contamination, or instrument change. The agent doesn't diagnose. It just stops.",
      ],
    };
  }

  // Default fallback (should rarely trigger)
  return {
    paragraphs: [
      `The agent updated beliefs and chose ${template}.`,
      rationale.summary ?? "Continuing structured exploration.",
    ],
    context: `Budget remaining: ${budgetRemaining} wells`,
  };
}
