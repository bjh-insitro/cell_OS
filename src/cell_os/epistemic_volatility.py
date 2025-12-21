"""
Entropy volatility: detecting and penalizing epistemic thrashing.

PHILOSOPHY: It's not just about whether entropy increases or decreases.
If entropy oscillates wildly (2.0 → 2.3 → 1.9 → 2.4 → 2.0 → 2.5), that's
epistemic thrashing even if each step has small delta.

This indicates the agent doesn't have a coherent strategy. It's probing
randomly without a plan, hoping to get lucky.

Volatility penalty makes thrashing expensive, independent of whether
individual steps widen or narrow.
"""

from dataclasses import dataclass, field
from typing import List
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class EntropyVolatilityTracker:
    """
    Tracks entropy history and detects thrashing.

    Thrashing is defined as high volatility in entropy over recent steps,
    indicating the agent is probing without a coherent strategy.

    Attributes:
        history: Recent entropy values (fixed-size sliding window)
        window_size: How many steps to track (default: 10)
        volatility_threshold: Threshold for "high volatility" (default: 0.25)
        penalty_weight: How much to penalize volatility (default: 0.5)
    """

    history: List[float] = field(default_factory=list)
    window_size: int = 10
    volatility_threshold: float = 0.25
    penalty_weight: float = 0.5

    def add(self, entropy: float) -> None:
        """Add entropy measurement to history."""
        self.history.append(entropy)
        if len(self.history) > self.window_size:
            self.history.pop(0)

    def compute_volatility(self) -> float:
        """
        Compute volatility as standard deviation of recent entropy.

        Returns:
            Volatility (higher = more thrashing)
        """
        if len(self.history) < 3:
            return 0.0  # Need at least 3 points

        return float(np.std(self.history))

    def is_thrashing(self) -> bool:
        """
        Detect if agent is thrashing (high volatility).

        Returns:
            True if volatility exceeds threshold
        """
        return self.compute_volatility() > self.volatility_threshold

    def compute_penalty(self) -> float:
        """
        Compute penalty for volatility.

        Penalty = volatility * weight (if above threshold)

        Returns:
            Penalty to subtract from reward
        """
        volatility = self.compute_volatility()

        if volatility <= self.volatility_threshold:
            return 0.0  # Below threshold, no penalty

        # Penalty scales with excess volatility
        excess = volatility - self.volatility_threshold
        penalty = excess * self.penalty_weight

        logger.info(
            f"Volatility penalty: volatility={volatility:.3f}, "
            f"threshold={self.volatility_threshold:.3f}, "
            f"penalty={penalty:.3f}"
        )

        return penalty

    def get_statistics(self) -> dict:
        """Get statistics for monitoring."""
        volatility = self.compute_volatility()
        return {
            "volatility": volatility,
            "is_thrashing": self.is_thrashing(),
            "history_length": len(self.history),
            "recent_mean": np.mean(self.history) if self.history else 0.0,
            "recent_min": np.min(self.history) if self.history else 0.0,
            "recent_max": np.max(self.history) if self.history else 0.0,
        }

    def reset(self) -> None:
        """Reset history (for new episode)."""
        self.history.clear()


@dataclass
class CalibrationStabilityTracker:
    """
    Tracks calibration stability (consistency of errors).

    A good agent has consistent calibration errors.
    A bad agent is sometimes right, sometimes wildly wrong (high variance).

    This is different from mean overclaim: you can have low mean overclaim
    but high variance (lucky streaks masking bad calibration).

    Attributes:
        errors: Recent calibration errors (claimed - realized)
        window_size: How many to track
        instability_penalty_weight: Penalty for high variance
    """

    errors: List[float] = field(default_factory=list)
    window_size: int = 10
    instability_penalty_weight: float = 0.3

    def add_error(self, claimed: float, realized: float) -> None:
        """Add calibration error to history."""
        error = claimed - realized
        self.errors.append(error)
        if len(self.errors) > self.window_size:
            self.errors.pop(0)

    def compute_stability(self) -> float:
        """
        Compute stability as inverse of variance.

        High stability = consistent errors (good or bad)
        Low stability = erratic errors (sometimes right, sometimes wrong)

        Returns:
            Stability score in [0, 1] (higher = more stable)
        """
        if len(self.errors) < 3:
            return 1.0  # Insufficient data, assume stable

        variance = float(np.var(self.errors))
        # Use 8× variance to be more sensitive to instability
        stability = 1.0 / (1.0 + 8.0 * variance)

        return stability

    def compute_penalty(self) -> float:
        """
        Compute penalty for instability.

        Unstable agents face cost penalties even if mean error is low.

        Returns:
            Instability penalty (cost multiplier)
        """
        if len(self.errors) < 3:
            return 0.0

        stability = self.compute_stability()
        instability = 1.0 - stability

        penalty = instability * self.instability_penalty_weight

        logger.debug(
            f"Calibration stability: {stability:.3f}, "
            f"instability_penalty={penalty:.3f}"
        )

        return penalty

    def get_statistics(self) -> dict:
        """Get statistics for monitoring."""
        if not self.errors:
            return {
                "stability": 1.0,
                "mean_error": 0.0,
                "error_variance": 0.0,
            }

        return {
            "stability": self.compute_stability(),
            "mean_error": np.mean(self.errors),
            "error_variance": np.var(self.errors),
            "error_std": np.std(self.errors),
        }

    def reset(self) -> None:
        """Reset history."""
        self.errors.clear()
