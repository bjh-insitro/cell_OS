"""
Provisional penalties: handling multi-step credit assignment.

PHILOSOPHY: Not all entropy increases are immediately bad. Sometimes an
experiment widens entropy temporarily but enables a decisive follow-up.

Example:
  - scRNA reveals subpopulation heterogeneity (entropy ↑)
  - But this enables targeted follow-up (entropy ↓↓)
  - Initial widening was PRODUCTIVE, not self-harm

This module handles delayed credit assignment: provisional penalties that
can be refunded if the widening leads to later resolution.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProvisionalPenalty:
    """
    A penalty that may be refunded if entropy collapses later.

    Attributes:
        action_id: Action that caused widening
        penalty_amount: Provisional penalty (held in escrow)
        settlement_horizon: Episodes until settlement (DEPRECATED - use settlement_time_h)
        episodes_remaining: Countdown to settlement (DEPRECATED)
        settlement_time_h: Real time (hours) until settlement (default: 12h)
        time_elapsed_h: Real time elapsed since penalty added
        prior_entropy: Entropy before the action
        settled: Whether penalty has been finalized or refunded
    """

    action_id: str
    penalty_amount: float
    settlement_horizon: int  # Kept for backward compatibility
    prior_entropy: float
    settlement_time_h: float = 12.0  # NEW: Time-based settlement
    time_elapsed_h: float = 0.0      # NEW: Elapsed time tracker
    episodes_remaining: int = 0
    settled: bool = False

    def __post_init__(self):
        self.episodes_remaining = self.settlement_horizon


@dataclass
class ProvisionalPenaltyTracker:
    """
    Tracks provisional penalties and settles them based on downstream outcomes.

    Philosophy: Temporary uncertainty is acceptable if it leads to resolution.
    This tracker distinguishes productive uncertainty from self-harm.
    """

    provisional_penalties: Dict[str, ProvisionalPenalty] = field(default_factory=dict)
    total_escrowed: float = 0.0
    total_refunded: float = 0.0
    total_finalized: float = 0.0

    def add_provisional_penalty(
        self,
        action_id: str,
        penalty_amount: float,
        prior_entropy: float,
        settlement_horizon: int = 3,
        settlement_time_h: float = 12.0,
    ) -> str:
        """
        Add a provisional penalty that will be settled later.

        Args:
            action_id: Action that caused widening
            penalty_amount: Penalty to hold in escrow
            prior_entropy: Entropy before action (for settlement comparison)
            settlement_horizon: Episodes before settlement (DEPRECATED - use settlement_time_h)
            settlement_time_h: Real time (hours) until settlement (default: 12h)

        Returns:
            Provisional penalty ID
        """
        penalty = ProvisionalPenalty(
            action_id=action_id,
            penalty_amount=penalty_amount,
            settlement_horizon=settlement_horizon,
            prior_entropy=prior_entropy,
            settlement_time_h=settlement_time_h,
            time_elapsed_h=0.0,
        )

        self.provisional_penalties[action_id] = penalty
        self.total_escrowed += penalty_amount

        logger.info(
            f"Added provisional penalty: {action_id}, "
            f"amount={penalty_amount:.3f}, "
            f"settlement_time={settlement_time_h:.1f}h"
        )

        return action_id

    def step(self, current_entropy: float, time_increment_h: float = 0.0) -> float:
        """
        Step time forward and settle expired provisional penalties.

        Args:
            current_entropy: Current posterior entropy
            time_increment_h: Real time elapsed since last step (hours)
                             If 0, uses episode-based settlement (backward compat)

        Returns:
            Total penalties finalized this step (positive = penalty applied)
        """
        finalized_this_step = 0.0

        for action_id, penalty in list(self.provisional_penalties.items()):
            if penalty.settled:
                continue

            # Update time-based tracking
            if time_increment_h > 0:
                penalty.time_elapsed_h += time_increment_h

            # Also update episode-based (backward compat)
            penalty.episodes_remaining -= 1

            # Check settlement criteria (prefer time-based if specified)
            should_settle = False
            if time_increment_h > 0:
                should_settle = penalty.time_elapsed_h >= penalty.settlement_time_h
            else:
                should_settle = penalty.episodes_remaining <= 0

            if should_settle:
                # Time to settle
                if current_entropy < penalty.prior_entropy:
                    # Entropy collapsed below prior → refund penalty
                    logger.info(
                        f"Refunding provisional penalty: {action_id}, "
                        f"entropy {current_entropy:.3f} < prior {penalty.prior_entropy:.3f}, "
                        f"time_elapsed={penalty.time_elapsed_h:.1f}h"
                    )
                    self.total_refunded += penalty.penalty_amount
                    self.total_escrowed -= penalty.penalty_amount
                    penalty.settled = True
                    # Don't apply penalty
                else:
                    # Entropy still high → finalize penalty
                    logger.info(
                        f"Finalizing provisional penalty: {action_id}, "
                        f"entropy {current_entropy:.3f} >= prior {penalty.prior_entropy:.3f}, "
                        f"time_elapsed={penalty.time_elapsed_h:.1f}h"
                    )
                    self.total_finalized += penalty.penalty_amount
                    self.total_escrowed -= penalty.penalty_amount
                    finalized_this_step += penalty.penalty_amount
                    penalty.settled = True

        return finalized_this_step

    def refund_penalty(self, action_id: str) -> bool:
        """
        Manually refund a provisional penalty (entropy collapsed early).

        Args:
            action_id: Action to refund

        Returns:
            True if refunded, False if not found or already settled
        """
        if action_id not in self.provisional_penalties:
            logger.warning(f"No provisional penalty found for {action_id}")
            return False

        penalty = self.provisional_penalties[action_id]

        if penalty.settled:
            logger.warning(f"Penalty {action_id} already settled")
            return False

        logger.info(f"Manually refunding provisional penalty: {action_id}")
        self.total_refunded += penalty.penalty_amount
        self.total_escrowed -= penalty.penalty_amount
        penalty.settled = True

        return True

    def finalize_penalty(self, action_id: str) -> float:
        """
        Manually finalize a provisional penalty (confirmed as self-harm).

        Args:
            action_id: Action to finalize

        Returns:
            Penalty amount applied
        """
        if action_id not in self.provisional_penalties:
            logger.warning(f"No provisional penalty found for {action_id}")
            return 0.0

        penalty = self.provisional_penalties[action_id]

        if penalty.settled:
            logger.warning(f"Penalty {action_id} already settled")
            return 0.0

        logger.info(f"Manually finalizing provisional penalty: {action_id}")
        self.total_finalized += penalty.penalty_amount
        self.total_escrowed -= penalty.penalty_amount
        penalty.settled = True

        return penalty.penalty_amount

    def get_statistics(self) -> Dict[str, float]:
        """Get summary statistics for auditing."""
        active_count = sum(1 for p in self.provisional_penalties.values() if not p.settled)

        return {
            "total_escrowed": self.total_escrowed,
            "total_refunded": self.total_refunded,
            "total_finalized": self.total_finalized,
            "active_provisional_count": active_count,
            "refund_rate": self.total_refunded / max(1e-6, self.total_refunded + self.total_finalized),
        }
