"""
Reward functions for Phase 3 policy pressure.

Design principle: Sparse, testable rewards that create real tradeoffs.
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class EpisodeReceipt:
    """
    Episode diagnostic information for debugging policy pressure.

    Logs mechanism engagement, death, and ops costs separately
    so tests can assert not just reward, but why.
    """
    # Mechanism engagement
    mechanism_hit: bool
    actin_struct_12h: float
    baseline_actin: float
    actin_fold_12h: float  # actin_struct_12h / baseline_actin

    # Death accounting
    viability_48h: float
    total_dead_48h: float

    # Operational costs (count-based)
    washout_count: int
    feed_count: int
    ops_cost: float

    # Reward components
    reward_mechanism: float
    reward_death_penalty: float
    reward_ops_cost: float
    reward_total: float

    def __str__(self):
        """Pretty print for test debugging."""
        return (
            f"EpisodeReceipt(\n"
            f"  Mechanism: {'HIT' if self.mechanism_hit else 'MISS'} "
            f"(actin={self.actin_fold_12h:.2f}× baseline)\n"
            f"  Death: {self.total_dead_48h:.1%} (penalty={self.reward_death_penalty:.2f})\n"
            f"  Ops: {self.washout_count} washouts, {self.feed_count} feeds "
            f"(cost={self.reward_ops_cost:.2f})\n"
            f"  Reward: {self.reward_total:.2f} = "
            f"{self.reward_mechanism:.2f} - {abs(self.reward_death_penalty):.2f} - {abs(self.reward_ops_cost):.2f}\n"
            f")"
        )


def compute_microtubule_mechanism_reward(
    actin_struct_12h: float,
    baseline_actin: float,
    viability_48h: float,
    washout_count: int = 0,
    feed_count: int = 0,
    lambda_dead: float = 2.0,
    lambda_ops: float = 0.1,
    actin_threshold: float = 1.4
) -> EpisodeReceipt:
    """
    Multi-objective reward for microtubule mechanism validation.

    Goal: Engage transport mechanism early (actin structural increase),
          minimize death late, minimize operational costs.

    Design constraints (Model B):
    - Uses morphology_struct['actin'] at 12h (acute + chronic signature)
    - Threshold 1.4× baseline captures strong mechanism engagement
      (full dysfunction = 1.6× baseline, so 1.4× = ~88% of full signal)
    - Death penalty is quadratic in death fraction (killing 50% is 4× worse than 25%)
    - Ops cost is linear in intervention COUNT (not time, to avoid double-counting)

    Args:
        actin_struct_12h: Actin structural value at 12h from morphology_struct
        baseline_actin: Baseline actin structural value (no compound, no dysfunction)
        viability_48h: Viability at 48h (0-1)
        washout_count: Number of washout operations
        feed_count: Number of feeding operations
        lambda_dead: Death penalty coefficient (default: 2.0)
        lambda_ops: Ops cost coefficient (default: 0.1)
        actin_threshold: Fold-change threshold for mechanism hit (default: 1.4)

    Returns:
        EpisodeReceipt with reward and diagnostics

    Example usage:
        morph_12h = vm.cell_painting_assay("test")
        actin_struct_12h = morph_12h['morphology_struct']['actin']
        baseline_actin = 100.0  # From baseline measurement

        receipt = compute_microtubule_mechanism_reward(
            actin_struct_12h=actin_struct_12h,
            baseline_actin=baseline_actin,
            viability_48h=vessel.viability,
            washout_count=1,
            feed_count=0
        )
    """
    # 1. Mechanism engagement at 12h (binary gate)
    # Uses structural actin (Model B: acute + chronic), NOT measured
    actin_fold_12h = actin_struct_12h / baseline_actin
    mechanism_hit = actin_fold_12h >= actin_threshold
    reward_mechanism = 1.0 if mechanism_hit else 0.0

    # 2. Death penalty at 48h (quadratic in death fraction)
    total_dead_48h = 1.0 - viability_48h
    reward_death_penalty = -lambda_dead * (total_dead_48h ** 2)

    # 3. Operational cost (count-based, NOT time-based)
    # Each intervention (washout or feed) has unit cost
    # Time cost is already implicit in the count (each operation takes time)
    intervention_count = washout_count + feed_count
    reward_ops_cost = -lambda_ops * intervention_count

    # Total reward
    reward_total = reward_mechanism + reward_death_penalty + reward_ops_cost

    # Build receipt
    receipt = EpisodeReceipt(
        mechanism_hit=mechanism_hit,
        actin_struct_12h=actin_struct_12h,
        baseline_actin=baseline_actin,
        actin_fold_12h=actin_fold_12h,
        viability_48h=viability_48h,
        total_dead_48h=total_dead_48h,
        washout_count=washout_count,
        feed_count=feed_count,
        ops_cost=abs(reward_ops_cost),
        reward_mechanism=reward_mechanism,
        reward_death_penalty=reward_death_penalty,
        reward_ops_cost=reward_ops_cost,
        reward_total=reward_total
    )

    return receipt
