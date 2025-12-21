"""
Sandbagging detection: identifying systematic underclaiming.

PHILOSOPHY: Current system penalizes overclaiming but not underclaiming.
This creates an incentive to "sandbag" - claim conservatively to avoid debt.

Problem: Agent that always claims 0.1 bits but realizes 0.8 bits doesn't
learn proper calibration and misses optimization opportunities.

Solution: Track "surprise ratio" (realized / claimed). If consistently high,
agent is sandbagging. Apply discount: "You only get credit for gains you predicted."
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SandbaggingDetector:
    """
    Detects systematic underclaiming (sandbagging).

    Philosophy: You should get credit for gains you predicted, not lucky surprises.
    If you consistently claim low and realize high, you're not learning to plan.

    Attributes:
        surprise_ratios: Recent realized/claimed ratios
        window_size: How many ratios to track
        sandbagging_threshold: Threshold for "consistent surprise" (default: 2.0)
        credit_discount: How much to discount surprising gains (default: 0.5)
    """

    surprise_ratios: List[float] = field(default_factory=list)
    window_size: int = 10
    sandbagging_threshold: float = 2.0  # realized > 2× claimed consistently
    credit_discount: float = 0.5  # Surprising gains worth 50% less

    def add_observation(self, claimed: float, realized: float) -> None:
        """
        Record a claim/realized pair.

        Args:
            claimed: Expected information gain (bits)
            realized: Actual information gain (bits)
        """
        if claimed < 1e-6:
            # Avoid division by zero, treat as max surprise
            ratio = 10.0
        else:
            ratio = realized / claimed

        self.surprise_ratios.append(ratio)

        if len(self.surprise_ratios) > self.window_size:
            self.surprise_ratios.pop(0)

    def compute_mean_surprise(self) -> float:
        """
        Compute mean surprise ratio.

        Returns:
            Mean of realized/claimed over window
        """
        if not self.surprise_ratios:
            return 1.0

        return float(np.mean(self.surprise_ratios))

    def is_sandbagging(self) -> bool:
        """
        Detect if agent is systematically underclaiming.

        Returns:
            True if mean surprise > threshold
        """
        if len(self.surprise_ratios) < 3:
            return False  # Need data

        mean_surprise = self.compute_mean_surprise()
        return mean_surprise > self.sandbagging_threshold

    def compute_credit_discount(self, claimed: float, realized: float) -> float:
        """
        Compute how much credit to give for this gain.

        If agent is sandbagging, discount surprising gains.

        Args:
            claimed: Expected gain
            realized: Actual gain

        Returns:
            Credited gain (may be less than realized if sandbagging)
        """
        if not self.is_sandbagging():
            # Not sandbagging, full credit
            return realized

        # Agent is sandbagging
        surprise = realized / max(claimed, 1e-6)

        if surprise <= self.sandbagging_threshold:
            # Within normal range, full credit
            return realized

        # Surprising gain → discount
        # Formula: Give credit for claimed + partial credit for excess
        excess = realized - claimed
        credited = claimed + (excess * self.credit_discount)

        logger.info(
            f"Sandbagging penalty: claimed={claimed:.3f}, "
            f"realized={realized:.3f}, credited={credited:.3f}"
        )

        return credited

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for monitoring."""
        if not self.surprise_ratios:
            return {
                "mean_surprise": 1.0,
                "is_sandbagging": False,
                "observation_count": 0,
            }

        return {
            "mean_surprise": self.compute_mean_surprise(),
            "is_sandbagging": self.is_sandbagging(),
            "observation_count": len(self.surprise_ratios),
            "min_surprise": min(self.surprise_ratios),
            "max_surprise": max(self.surprise_ratios),
        }

    def reset(self) -> None:
        """Reset detector (for new episode)."""
        self.surprise_ratios.clear()


# Convenience function
def detect_sandbagging(
    claimed_gains: List[float],
    realized_gains: List[float],
    threshold: float = 2.0,
) -> bool:
    """
    Detect sandbagging from claim/realized history.

    Args:
        claimed_gains: List of claimed information gains
        realized_gains: List of realized information gains
        threshold: Surprise threshold

    Returns:
        True if mean realized/claimed > threshold
    """
    if len(claimed_gains) != len(realized_gains):
        raise ValueError("Claimed and realized lists must have same length")

    if len(claimed_gains) < 3:
        return False

    ratios = []
    for claimed, realized in zip(claimed_gains, realized_gains):
        if claimed < 1e-6:
            ratio = 10.0
        else:
            ratio = realized / claimed
        ratios.append(ratio)

    mean_ratio = np.mean(ratios)
    return mean_ratio > threshold
