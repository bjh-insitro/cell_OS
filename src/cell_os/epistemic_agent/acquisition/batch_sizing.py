"""
Centralized batch sizing decisions for epistemic agent calibration.

Agent 3 mandate: Amortize fixed costs during calibration, minimize wells during biology.

The core insight:
- Pre-gate: We MUST calibrate before biology. Minimize CYCLES (amortize fixed costs).
- Post-gate: Biology is the priority. Minimize WELLS (save budget for biology).

This module provides a single decision surface for all calibration batch sizing,
replacing 13 scattered hardcoded `n_reps=12` decisions.

Cost data comes from inventory database (data/cell_os_inventory.db):
- Fixed: ~$332/cycle (plate + imaging + analyst time)
- Marginal: ~$1.91/well (media + staining + LDH)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .cycle_cost_calculator import get_cycle_cost_breakdown, CycleCostBreakdown


class CoverageStrategy(str, Enum):
    """Spatial coverage strategies for plate layout."""
    SPREAD_FULL_PLATE = "spread_full_plate"  # Learn edge effects, column effects
    EDGES_AND_GRID = "edges_and_grid"        # Edge characterization + sampling
    CENTER_ONLY = "center_only"              # Minimal positional variance


# CostModel is now provided by cycle_cost_calculator.py
# It queries the inventory database for actual pricing data


@dataclass
class BatchSizingResult:
    """Structured decision output from batch sizing logic.

    Includes both the decision (n_reps, coverage_strategy) and the reasoning
    (reason_code, reason_text) for observability and debugging.
    """
    n_reps: int
    coverage_strategy: CoverageStrategy
    reason_code: str
    reason_text: str
    df_gain_expected: int
    cost_per_df: float
    wells_used: int

    def summary(self) -> str:
        """Human-readable summary for logging."""
        return (
            f"Batch: {self.n_reps} reps, {self.coverage_strategy.value} "
            f"({self.wells_used}/{self.df_gain_expected} wells/df, "
            f"${self.cost_per_df:.1f}/df) - {self.reason_text}"
        )


def choose_calibration_batch_size(
    regime: str,
    df_current: int,
    df_needed: int,
    remaining_budget_wells: int,
    learn_plate_effects: bool = True,
    cost_breakdown: Optional[CycleCostBreakdown] = None,
    absolute_minimum_reserve: int = 50,
    scarcity_mode: bool = False
) -> BatchSizingResult:
    """Centralized batch sizing decision for calibration experiments.

    Core logic:
    - Pre-gate: Minimize CYCLES (amortize fixed costs)
        → Use as many wells as needed to earn gate in ONE cycle
        → Learn spatial effects (edges, columns) during calibration
    - Post-gate: Minimize WELLS (biology is priority)
        → Use small batches for maintenance calibration
        → Reserve budget for biology experiments

    Args:
        regime: "pre_gate", "in_gate", or "maintenance"
        df_current: Current degrees of freedom accumulated
        df_needed: Degrees of freedom needed to earn gate
        remaining_budget_wells: Wells remaining in budget
        learn_plate_effects: If True, use spatial coverage to learn edge/column effects
        cost_breakdown: Cost structure from database (defaults to querying inventory DB)
        absolute_minimum_reserve: Absolute minimum wells to reserve for biology
        scarcity_mode: If True, we're in scarcity and must be conservative

    Returns:
        BatchSizingResult with decision + reasoning
    """
    if cost_breakdown is None:
        cost_breakdown = get_cycle_cost_breakdown()

    df_delta = max(0, df_needed - df_current)
    df_per_rep = 11  # Each replicate yields ~11 df (baseline assumption)

    # ------------------------------------------------------------------
    # PRE-GATE: Minimize cycles (amortize fixed costs)
    # ------------------------------------------------------------------
    if regime == "pre_gate":
        # Strategy: Use enough wells to earn gate in ONE cycle
        reps_needed = (df_delta + df_per_rep - 1) // df_per_rep

        # If learning plate effects, spread wells across plate
        if learn_plate_effects:
            # Use substantial fraction of plate to learn spatial effects
            # Target: ~50% of plate (192 wells) for edge/column characterization
            target_wells = min(192, remaining_budget_wells - absolute_minimum_reserve)
            target_reps = max(reps_needed, target_wells // 16)  # Assume ~16 wells per rep

            # Clamp to available budget
            if scarcity_mode:
                # In scarcity, respect absolute minimum reserve strictly
                max_affordable = (remaining_budget_wells - absolute_minimum_reserve) // 16
                target_reps = min(target_reps, max_affordable)
            else:
                # Normal mode: use generous reserve fraction
                reserve_wells = int(remaining_budget_wells * 0.5)
                max_affordable = (remaining_budget_wells - reserve_wells) // 16
                target_reps = min(target_reps, max_affordable)

            n_reps = max(reps_needed, min(target_reps, 16))  # Cap at 16 for sanity
            wells_used = n_reps * 16  # Approximate
            coverage = CoverageStrategy.SPREAD_FULL_PLATE
            reason_code = "pre_gate_amortize_fixed_costs"
            reason_text = (
                f"Pre-gate calibration: amortizing ${cost_breakdown.fixed_cost:.0f} fixed cost "
                f"over {wells_used} wells (${cost_breakdown.cost_per_df(wells_used, df_delta):.1f}/df) "
                f"while learning spatial effects"
            )
        else:
            # Not learning plate effects: use minimum wells to earn gate
            n_reps = reps_needed
            wells_used = n_reps * 12  # Baseline replicates use 12 wells
            coverage = CoverageStrategy.CENTER_ONLY
            reason_code = "pre_gate_minimal"
            reason_text = f"Pre-gate calibration: minimum wells to earn gate ({wells_used} wells)"

        return BatchSizingResult(
            n_reps=n_reps,
            coverage_strategy=coverage,
            reason_code=reason_code,
            reason_text=reason_text,
            df_gain_expected=df_delta,
            cost_per_df=cost_breakdown.cost_per_df(wells_used, df_delta),
            wells_used=wells_used
        )

    # ------------------------------------------------------------------
    # POST-GATE: Minimize wells (biology is priority)
    # ------------------------------------------------------------------
    elif regime in ["in_gate", "maintenance"]:
        # Strategy: Use small batches for maintenance, save wells for biology
        # Typical maintenance: 12 reps = 12 wells baseline
        n_reps = 12
        wells_used = 12
        coverage = CoverageStrategy.CENTER_ONLY

        reason_code = "post_gate_minimal"
        reason_text = (
            f"Post-gate maintenance: minimal batch (12 wells) to preserve budget for biology"
        )

        return BatchSizingResult(
            n_reps=n_reps,
            coverage_strategy=coverage,
            reason_code=reason_code,
            reason_text=reason_text,
            df_gain_expected=df_per_rep if regime == "maintenance" else 0,
            cost_per_df=cost_breakdown.cost_per_df(wells_used, df_per_rep) if regime == "maintenance" else 0.0,
            wells_used=wells_used
        )

    # ------------------------------------------------------------------
    # FALLBACK: Unknown regime
    # ------------------------------------------------------------------
    else:
        # Conservative default: 12 reps
        n_reps = 12
        wells_used = 12
        coverage = CoverageStrategy.CENTER_ONLY
        reason_code = "fallback_unknown_regime"
        reason_text = f"Unknown regime '{regime}': using conservative default (12 reps)"

        return BatchSizingResult(
            n_reps=n_reps,
            coverage_strategy=coverage,
            reason_code=reason_code,
            reason_text=reason_text,
            df_gain_expected=0,
            cost_per_df=0.0,
            wells_used=wells_used
        )
