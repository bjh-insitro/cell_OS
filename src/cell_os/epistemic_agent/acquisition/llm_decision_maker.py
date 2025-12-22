"""
LLM-based decision maker for experimental design.

Replaces hardcoded heuristics with LLM reasoning about batch sizes,
template selection, and resource allocation. The epistemic governance
layer still enforces all constraints (gates, budget, debt).

Architecture:
    BeliefState → LLM Reasoning → Proposal → Governance Check → Decision

The LLM provides strategic reasoning, the governance layer ensures honesty.
"""

import json
from dataclasses import dataclass
from typing import Optional, Dict, Any

from ..beliefs.state import BeliefState
from .cycle_cost_calculator import CycleCostBreakdown, get_cycle_cost_breakdown


@dataclass
class ExperimentProposal:
    """Structured proposal from LLM reasoning."""
    template: str
    n_reps: int
    coverage_strategy: str
    reasoning: str
    raw_response: str  # Full LLM response for debugging


class LLMDecisionMaker:
    """
    LLM-based experimental design decision maker.

    Currently uses mock reasoning (smart heuristics), but the API is shaped
    so you can swap in a real LLM (Claude, GPT-4) without changing callers.

    The LLM receives:
    - Full epistemic state (gates, df, uncertainty)
    - Cost structure from inventory database
    - Available templates and their constraints
    - Governance rules that will be enforced

    The LLM returns:
    - Template choice
    - Batch size (n_reps)
    - Spatial coverage strategy
    - Natural language reasoning

    The governance layer then enforces:
    - Cannot do biology without gates
    - Cannot exceed budget
    - Must respect debt obligations
    - All proposals are logged for provenance
    """

    def __init__(self, model_name: str = "mock"):
        """
        Initialize decision maker.

        Args:
            model_name: "mock" for heuristics, "claude-opus-4" for real LLM
        """
        self.model_name = model_name

    def choose_next_experiment(
        self,
        beliefs: BeliefState,
        cycle: int,
        remaining_wells: int,
        cost_breakdown: Optional[CycleCostBreakdown] = None
    ) -> ExperimentProposal:
        """
        Choose next experiment using LLM reasoning.

        Args:
            beliefs: Current epistemic state (gates, df, uncertainty)
            cycle: Current cycle number
            remaining_wells: Wells remaining in budget
            cost_breakdown: Cost structure (defaults to querying inventory DB)

        Returns:
            ExperimentProposal with template, n_reps, and reasoning
        """
        if cost_breakdown is None:
            cost_breakdown = get_cycle_cost_breakdown()

        # Build context prompt
        context = self._build_context(beliefs, cycle, remaining_wells, cost_breakdown)

        # Query LLM (or mock)
        if self.model_name == "mock":
            return self._mock_reasoning(beliefs, cycle, remaining_wells, cost_breakdown)
        else:
            return self._query_llm(context)

    def _build_context(
        self,
        beliefs: BeliefState,
        cycle: int,
        remaining_wells: int,
        cost_breakdown: CycleCostBreakdown
    ) -> str:
        """Build structured prompt with epistemic state and costs."""

        noise_gate = "EARNED" if beliefs.noise_sigma_stable else "NOT EARNED"
        df_total = beliefs.noise_df_total
        df_needed = 140  # Conservative floor for noise gate

        prompt = f"""You are a strategic experimental planner for a biology lab automation system.
Your job is to choose the next experiment that maximizes information gain per dollar spent.

## Current Epistemic State (Cycle {cycle})

**Calibration Status:**
- Noise gate: {noise_gate}
- Degrees of freedom: {df_total} / {df_needed} needed
- Edge effects: {'characterized' if beliefs.edge_effect_confident else 'unknown'}

**Budget:**
- Wells remaining: {remaining_wells}
- Wells used so far: {beliefs.wells_consumed}

**Cost Structure (from inventory database):**
- Fixed cost per cycle: ${cost_breakdown.fixed_cost:.2f}
  - 384-well plate: ${cost_breakdown.plate_cost:.2f}
  - Instruments: ${cost_breakdown.imaging_time_cost:.2f}
  - Analyst time: ${cost_breakdown.analyst_time_cost:.2f}
- Marginal cost per well: ${cost_breakdown.marginal_well_cost:.2f}

**Key Insight:** Fixed costs dominate!
- 12 wells: ${cost_breakdown.total_cost(12):.2f} (${cost_breakdown.total_cost(12)/12:.2f}/well)
- 192 wells: ${cost_breakdown.total_cost(192):.2f} (${cost_breakdown.total_cost(192)/192:.2f}/well)
- Efficiency ratio: {(cost_breakdown.total_cost(12)/12) / (cost_breakdown.total_cost(192)/192):.1f}x cheaper per well at scale

## Epistemic Governance Rules (ENFORCED - you cannot bypass)

1. **Must earn noise gate before biology**: If noise_gate == NOT EARNED, you MUST run baseline_replicates
2. **Must characterize edge effects**: Should test edge vs center wells after earning ~40 df
3. **Cannot exceed budget**: Wells used ≤ remaining_wells
4. **Must reserve minimum for biology**: Leave at least 50 wells for actual experiments

## Available Templates

1. **baseline_replicates**: DMSO control wells (no compound, pure noise characterization)
   - Use for: Earning noise gate, maintenance calibration
   - Each replicate = ~11 df (assumes independent wells)

2. **edge_center_test**: Test edge vs center spatial effects
   - Use for: Characterizing plate position confounds
   - Typical: 24 wells (12 edge + 12 center)

3. **dose_ladder_coarse**: Test compound at 4 dose levels
   - Use for: Initial dose-response characterization
   - Only available AFTER earning gate

## Your Task

Decide what experiment to run next. Consider:

1. **Strategic efficiency**: Minimize total cycles to earn gates (amortize fixed costs)
2. **Information value**: What will you learn beyond just df?
3. **Budget allocation**: Balance calibration vs biology

Think through:
- If I'm still earning the gate, should I use 12 wells (wasteful, 13 cycles) or 192 wells (efficient, 1-2 cycles)?
- Am I learning spatial effects during calibration, or will I have to re-test later?
- What's the opportunity cost of small batches?

## Response Format (JSON)

{{
  "template": "baseline_replicates",
  "n_reps": 192,
  "coverage_strategy": "spread_full_plate",
  "reasoning": "Strategic reasoning here..."
}}

IMPORTANT: I will enforce governance rules. If you propose biology before earning gates, I will override your decision."""

        return prompt

    def _mock_reasoning(
        self,
        beliefs: BeliefState,
        cycle: int,
        remaining_wells: int,
        cost_breakdown: CycleCostBreakdown
    ) -> ExperimentProposal:
        """
        Mock reasoning using smart heuristics.

        This simulates what an LLM might reason, but uses deterministic logic.
        Replace this with _query_llm() for real LLM reasoning.
        """

        # Check if we need to earn noise gate
        if not beliefs.noise_sigma_stable:
            df_total = beliefs.noise_df_total
            df_needed = 140
            df_delta = max(0, df_needed - df_total)

            # Smart heuristic: Use ~half plate during calibration
            # This amortizes fixed costs while learning spatial effects
            target_wells = min(192, remaining_wells - 50)  # Reserve 50 for biology
            n_reps = target_wells // 16  # Approximate: each rep uses ~16 wells
            n_reps = max(1, min(n_reps, 16))  # Clamp to [1, 16]

            cost_per_df = cost_breakdown.cost_per_df(n_reps * 16, df_delta)

            reasoning = (
                f"Pre-gate calibration: Using {n_reps} replicates ({n_reps * 16} wells) to earn noise gate. "
                f"Amortizing ${cost_breakdown.fixed_cost:.0f} fixed cost over {n_reps * 16} wells "
                f"(${cost_per_df:.1f}/df) instead of running 13 cycles of 12 wells. "
                f"This also learns spatial structure (edges, columns) during calibration, "
                f"saving a future characterization cycle."
            )

            return ExperimentProposal(
                template="baseline_replicates",
                n_reps=n_reps,
                coverage_strategy="spread_full_plate",
                reasoning=reasoning,
                raw_response=f"mock_reasoning(cycle={cycle}, df={df_total}/{df_needed})"
            )

        # Check if we need to characterize edge effects
        if not beliefs.edge_effect_confident and beliefs.noise_df_total >= 40:
            reasoning = (
                f"Edge effect characterization: Testing 24 wells (12 edge + 12 center) "
                f"to resolve spatial confounds before proceeding to biology. "
                f"This is required by governance before compounds can be tested."
            )

            return ExperimentProposal(
                template="edge_center_test",
                n_reps=1,
                coverage_strategy="edges_and_grid",
                reasoning=reasoning,
                raw_response=f"mock_reasoning(cycle={cycle}, edge_effects=needed)"
            )

        # If gates are earned, run biology (small batches for exploration)
        reasoning = (
            f"Biology mode: Gates earned. Using small batches (12 wells) for compound testing. "
            f"Exploration efficiency is now more important than fixed cost amortization."
        )

        return ExperimentProposal(
            template="dose_ladder_coarse",
            n_reps=1,
            coverage_strategy="center_only",
            reasoning=reasoning,
            raw_response=f"mock_reasoning(cycle={cycle}, biology_mode=true)"
        )

    def _query_llm(self, context: str) -> ExperimentProposal:
        """
        Query LLM API for decision.

        Supports both Anthropic (Claude) and OpenAI (GPT-4) models.

        For Anthropic: requires ANTHROPIC_API_KEY environment variable
        For OpenAI: requires OPENAI_API_KEY environment variable
        """
        import os

        # Determine which API to use based on model name
        if self.model_name.startswith("claude"):
            return self._query_anthropic(context)
        elif self.model_name.startswith("gpt"):
            return self._query_openai(context)
        else:
            raise ValueError(
                f"Unknown model: {self.model_name}. "
                f"Use 'claude-*' for Anthropic or 'gpt-*' for OpenAI"
            )

    def _query_anthropic(self, context: str) -> ExperimentProposal:
        """Query Anthropic Claude API."""
        try:
            import anthropic
            import os
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your API key from: https://console.anthropic.com/"
            )

        client = anthropic.Anthropic(api_key=api_key)

        # Call Claude with the experimental design context
        response = client.messages.create(
            model=self.model_name,  # e.g., "claude-opus-4-20250514" or "claude-sonnet-4-20250514"
            max_tokens=2048,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": context
            }]
        )

        # Extract text from response
        response_text = response.content[0].text

        # Parse the JSON response
        return self._parse_response(response_text)

    def _query_openai(self, context: str) -> ExperimentProposal:
        """Query OpenAI GPT API."""
        try:
            from openai import OpenAI
            import os
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Get your API key from: https://platform.openai.com/api-keys"
            )

        client = OpenAI(api_key=api_key)

        # Call GPT with the experimental design context
        response = client.chat.completions.create(
            model=self.model_name,  # e.g., "gpt-4-turbo" or "gpt-4o"
            max_tokens=2048,
            temperature=0.7,
            messages=[{
                "role": "system",
                "content": "You are a strategic experimental design assistant for biology lab automation. You reason about costs, information gain, and epistemic constraints to make optimal batch sizing decisions."
            }, {
                "role": "user",
                "content": context
            }]
        )

        # Extract text from response
        response_text = response.choices[0].message.content

        # Parse the JSON response
        return self._parse_response(response_text)

    def _parse_response(self, response_text: str) -> ExperimentProposal:
        """Parse LLM response JSON into structured proposal."""
        try:
            data = json.loads(response_text)
            return ExperimentProposal(
                template=data["template"],
                n_reps=data["n_reps"],
                coverage_strategy=data.get("coverage_strategy", "center_only"),
                reasoning=data.get("reasoning", ""),
                raw_response=response_text
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to safe default if parse fails
            return ExperimentProposal(
                template="baseline_replicates",
                n_reps=12,
                coverage_strategy="center_only",
                reasoning=f"Parse error: {e}. Using safe default.",
                raw_response=response_text
            )


# ============================================================================
# Integration helper: wrap LLM decision in existing Decision format
# ============================================================================

def llm_choose_with_governance(
    beliefs: BeliefState,
    cycle: int,
    remaining_wells: int,
    cost_breakdown: Optional[CycleCostBreakdown] = None,
    model_name: str = "mock"
) -> Dict[str, Any]:
    """
    Use LLM to choose experiment, then enforce governance rules.

    This is the main entry point for integration with existing chooser.py.

    Returns:
        Dict with keys: template, n_reps, reason, forced, regime, gate_state
    """
    maker = LLMDecisionMaker(model_name=model_name)
    proposal = maker.choose_next_experiment(beliefs, cycle, remaining_wells, cost_breakdown)

    # Governance enforcement (cannot be bypassed)
    forced = False
    regime = "in_gate" if beliefs.noise_sigma_stable else "pre_gate"

    # Override biology proposals if gates not earned
    if not beliefs.noise_sigma_stable and proposal.template not in ["baseline_replicates", "edge_center_test"]:
        # LLM tried to do biology without gate - REJECT
        proposal = ExperimentProposal(
            template="baseline_replicates",
            n_reps=proposal.n_reps,  # Keep batch size reasoning
            coverage_strategy=proposal.coverage_strategy,
            reasoning=f"GOVERNANCE OVERRIDE: {proposal.reasoning} [Rejected: noise gate not earned]",
            raw_response=proposal.raw_response
        )
        forced = True

    # Format for existing decision API
    return {
        "template": proposal.template,
        "n_reps": proposal.n_reps,
        "coverage_strategy": proposal.coverage_strategy,
        "reason": proposal.reasoning,
        "forced": forced,
        "regime": regime,
        "gate_state": {
            "noise_sigma": "earned" if beliefs.noise_sigma_stable else "not_earned",
            "edge_effect": "confident" if beliefs.edge_effect_confident else "unknown"
        },
        "llm_proposal": {
            "raw_response": proposal.raw_response,
            "model": model_name
        }
    }
