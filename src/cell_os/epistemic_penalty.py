"""
Epistemic penalty: making posterior widening hurt.

PHILOSOPHY: Posterior widening should reduce expected value of future actions,
not just immediate reward. High uncertainty should:
- Reduce immediate reward
- Shorten planning horizon
- Increase exploration penalties
- Trigger "go back and clean instrumentation" behaviors

This is how you make agents allergic to unforced epistemic errors.

KEY DISTINCTION: Not all uncertainty is equal.
- Exploration uncertainty (haven't measured yet): ACCEPTABLE
- Measurement-induced confusion (measured and got more confused): PENALIZED
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EntropySource(Enum):
    """
    Source of entropy/uncertainty.

    This distinction is critical: we should penalize measurement-induced
    confusion but NOT penalize appropriate prior uncertainty.
    """
    PRIOR = "prior"  # Haven't measured yet, prior is broad
    MEASUREMENT_NARROWING = "measurement_narrowing"  # Measurement reduced entropy (GOOD)
    MEASUREMENT_AMBIGUOUS = "measurement_ambiguous"  # Measurement gave ambiguous signal
    MEASUREMENT_CONTRADICTORY = "measurement_contradictory"  # Measurement contradicted prior


@dataclass
class EpistemicPenaltyConfig:
    """
    Configuration for epistemic penalties.

    Attributes:
        entropy_penalty_weight: How much to penalize entropy increase (bits → reward units)
        only_penalize_agent_actions: If True, only penalize widening from agent actions (not world drift)
        horizon_shrinkage_rate: How much high entropy shrinks planning horizon (0-1)
        max_penalty: Cap on entropy penalty to avoid extreme punishments
    """

    entropy_penalty_weight: float = 1.0
    only_penalize_agent_actions: bool = True
    horizon_shrinkage_rate: float = 0.2
    max_penalty: float = 10.0


def compute_entropy_penalty(
    prior_entropy: float,
    posterior_entropy: float,
    action_type: str,
    config: EpistemicPenaltyConfig,
    entropy_source: Optional[EntropySource] = None,
) -> float:
    """
    Compute penalty for posterior widening.

    Penalizes UNFORCED increases in uncertainty. If entropy went up because
    the world drifted or batch went bad, that's not the agent's fault.
    If entropy went up because the agent chose an expensive, confounded assay
    without necessity, that IS the agent's fault.

    CRITICAL: Only penalizes MEASUREMENT-INDUCED confusion, not prior uncertainty.
    Being uncertain before you measure is fine. Getting more uncertain AFTER
    measuring is bad.

    Args:
        prior_entropy: Entropy before action (bits)
        posterior_entropy: Entropy after action (bits)
        action_type: Type of action taken
        config: Penalty configuration
        entropy_source: Source of entropy (prior vs measurement-induced)

    Returns:
        Penalty to subtract from reward (positive = bad)

    Example:
        prior_entropy = 2.0 bits
        posterior_entropy = 2.5 bits (widened by 0.5 bits)
        action_type = "scrna_seq" (agent-caused)
        entropy_source = MEASUREMENT_CONTRADICTORY
        penalty_weight = 1.0
        → penalty = 0.5 (subtract 0.5 from reward)
    """
    ΔH = posterior_entropy - prior_entropy

    # Only penalize widening (increases in entropy)
    if ΔH <= 0:
        return 0.0

    # CRITICAL: Don't penalize high prior entropy (exploration)
    # Only penalize measurement-induced confusion
    if entropy_source is not None and entropy_source == EntropySource.PRIOR:
        logger.debug("No penalty for prior uncertainty (exploration)")
        return 0.0

    # Only penalize agent-caused widening if configured
    if config.only_penalize_agent_actions:
        agent_caused_actions = [
            "scrna_seq",
            "cell_painting",
            "proteomics",
            "spatial_transcriptomics",
            "expensive_assay",
        ]
        if action_type not in agent_caused_actions:
            # World drift, batch effects, etc. - not penalized
            return 0.0

    # Compute penalty
    penalty = ΔH * config.entropy_penalty_weight

    # Scale penalty by source severity
    if entropy_source == EntropySource.MEASUREMENT_CONTRADICTORY:
        penalty *= 1.5  # Contradiction is worse than ambiguity
    elif entropy_source == EntropySource.MEASUREMENT_AMBIGUOUS:
        penalty *= 1.0  # Base penalty

    # Cap penalty to avoid extreme punishments
    penalty = min(penalty, config.max_penalty)

    logger.info(
        f"Entropy penalty: ΔH={ΔH:.3f} bits, "
        f"action={action_type}, "
        f"source={entropy_source}, "
        f"penalty={penalty:.3f}"
    )

    return penalty


def compute_planning_horizon_shrinkage(
    current_entropy: float,
    baseline_entropy: float,
    config: EpistemicPenaltyConfig,
) -> float:
    """
    Compute how much high entropy shrinks planning horizon.

    High uncertainty should make the agent more cautious and short-sighted.
    Low uncertainty permits bolder, longer-horizon planning.

    Args:
        current_entropy: Current belief entropy (bits)
        baseline_entropy: Baseline entropy (e.g., at start of experiment)
        config: Penalty configuration

    Returns:
        Horizon multiplier in [0, 1]
        1.0 = normal horizon
        0.5 = half horizon
        0.0 = myopic (1-step only)

    Example:
        current_entropy = 4.0 bits (high uncertainty)
        baseline_entropy = 2.0 bits
        shrinkage_rate = 0.2
        → multiplier = 1.0 - 0.2 * (4.0 / 2.0) = 0.6 (40% reduction)
    """
    if baseline_entropy <= 0:
        return 1.0

    # Entropy ratio (how much worse than baseline)
    entropy_ratio = current_entropy / baseline_entropy

    # Shrinkage (higher entropy → shorter horizon)
    shrinkage = config.horizon_shrinkage_rate * entropy_ratio

    # Horizon multiplier (clamped to [0, 1])
    multiplier = max(0.0, min(1.0, 1.0 - shrinkage))

    logger.debug(
        f"Planning horizon shrinkage: "
        f"entropy_ratio={entropy_ratio:.2f}, "
        f"multiplier={multiplier:.2f}"
    )

    return multiplier


@dataclass
class EpistemicPenaltyResult:
    """
    Result of epistemic penalty computation.

    Attributes:
        entropy_penalty: Immediate reward penalty for widening
        horizon_multiplier: Planning horizon shrinkage factor
        prior_entropy: Entropy before action
        posterior_entropy: Entropy after action
        info_gain: Information gain (can be negative)
    """

    entropy_penalty: float
    horizon_multiplier: float
    prior_entropy: float
    posterior_entropy: float

    @property
    def info_gain(self) -> float:
        """Information gain in bits (can be negative if posterior widened)."""
        return self.prior_entropy - self.posterior_entropy

    @property
    def did_widen(self) -> bool:
        """Did the posterior widen (lose information)?"""
        return self.info_gain < 0

    def to_dict(self) -> Dict:
        """Export for logging/auditing."""
        return {
            "entropy_penalty": self.entropy_penalty,
            "horizon_multiplier": self.horizon_multiplier,
            "prior_entropy": self.prior_entropy,
            "posterior_entropy": self.posterior_entropy,
            "info_gain": self.info_gain,
            "did_widen": self.did_widen,
        }


def compute_full_epistemic_penalty(
    prior_entropy: float,
    posterior_entropy: float,
    action_type: str,
    baseline_entropy: float,
    config: Optional[EpistemicPenaltyConfig] = None,
    entropy_source: Optional[EntropySource] = None,
) -> EpistemicPenaltyResult:
    """
    Compute full epistemic penalty (immediate + horizon shrinkage).

    This is the main entry point for penalty computation.

    Args:
        prior_entropy: Entropy before action
        posterior_entropy: Entropy after action
        action_type: Type of action taken
        baseline_entropy: Baseline entropy for horizon computation
        config: Penalty configuration (uses defaults if None)
        entropy_source: Source of entropy (prior vs measurement-induced)

    Returns:
        EpistemicPenaltyResult with all penalty components
    """
    if config is None:
        config = EpistemicPenaltyConfig()

    # Immediate penalty for widening
    entropy_penalty = compute_entropy_penalty(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        action_type=action_type,
        config=config,
        entropy_source=entropy_source,
    )

    # Horizon shrinkage from high uncertainty
    horizon_multiplier = compute_planning_horizon_shrinkage(
        current_entropy=posterior_entropy,
        baseline_entropy=baseline_entropy,
        config=config,
    )

    return EpistemicPenaltyResult(
        entropy_penalty=entropy_penalty,
        horizon_multiplier=horizon_multiplier,
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
    )
