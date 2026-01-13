"""
Epistemic control: integrated debt tracking and penalty computation.

This module provides high-level interfaces for:
1. Tracking epistemic debt (claimed vs realized information gain)
2. Computing penalties for posterior widening
3. Inflating costs based on accumulated debt
4. Auditing agent calibration

Usage pattern:

    # Initialize controller
    controller = EpistemicController()

    # Before expensive action
    controller.claim_action(
        action_id="scrna_001",
        action_type="scrna_seq",
        expected_gain_bits=0.8
    )

    # After action, measure realized gain
    realized_gain = controller.measure_information_gain(
        prior_posterior=prior,
        posterior=posterior
    )

    # Resolve claim and accumulate debt
    controller.resolve_action(
        action_id="scrna_001",
        actual_gain_bits=realized_gain
    )

    # Compute penalty for widening
    penalty = controller.compute_penalty(
        action_type="scrna_seq"
    )

    # Get inflated cost for next action
    inflated_cost = controller.get_inflated_cost(base_cost=200.0)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import logging

from .debt import (
    EpistemicDebtLedger,
    compute_information_gain_bits,
)
from .penalty import (
    EpistemicPenaltyConfig,
    compute_full_epistemic_penalty,
    EpistemicPenaltyResult,
    EntropySource,
)
from .provisional import ProvisionalPenaltyTracker
from .volatility import (
    EntropyVolatilityTracker,
    CalibrationStabilityTracker,
)
from .sandbagging import SandbaggingDetector

logger = logging.getLogger(__name__)


# Agent 3: Budget reserve to prevent epistemic deadlock
# Minimum cost of any calibration template (baseline_replicates uses 12 wells)
# This must always be affordable, or agent can't escape debt
MIN_CALIBRATION_COST_WELLS = 12


@dataclass
class EpistemicControllerConfig:
    """
    Configuration for epistemic controller.

    Attributes:
        debt_sensitivity: How much debt affects cost (default: 50% per bit)
            Agent 3: Increased from 0.1 to 0.5 to make debt *painful* before hard block
        debt_decay_rate: Optional debt forgiveness per action (default: 0)
        penalty_config: Configuration for entropy penalties
        enable_debt_tracking: Enable debt accumulation (default: True)
            WARNING: Disabling this CONTAMINATES the run. Use only for debugging.
        enable_penalties: Enable entropy penalties (default: True)

    IMPORTANT: Debt enforcement is NON-OPTIONAL by default.
    If enable_debt_tracking=False, the run is marked as contaminated in diagnostics.
    """

    debt_sensitivity: float = 0.5  # Agent 3: Tightened from 0.1 to make debt felt
    debt_decay_rate: float = 0.0
    penalty_config: EpistemicPenaltyConfig = field(default_factory=EpistemicPenaltyConfig)
    enable_debt_tracking: bool = True
    enable_penalties: bool = True


class EpistemicController:
    """
    High-level controller for epistemic debt and penalties.

    This class coordinates:
    - Debt tracking (claimed vs realized info gain)
    - Penalty computation (widening hurts)
    - Cost inflation (debt increases future costs)
    - Auditing and logging
    """

    def __init__(self, config: Optional[EpistemicControllerConfig] = None):
        self.config = config or EpistemicControllerConfig()

        # Debt ledger
        self.ledger = EpistemicDebtLedger(
            debt_decay_rate=self.config.debt_decay_rate
        )

        # Provisional penalty tracker (multi-step credit assignment)
        self.provisional_tracker = ProvisionalPenaltyTracker()

        # Volatility tracking (detects thrashing)
        self.volatility_tracker = EntropyVolatilityTracker()

        # Calibration stability tracking (detects erratic calibration)
        self.stability_tracker = CalibrationStabilityTracker()

        # Sandbagging detection (systematic underclaiming)
        self.sandbagging_detector = SandbaggingDetector()

        # Track entropy history for penalty computation
        self.prior_entropy: Optional[float] = None
        self.posterior_entropy: Optional[float] = None
        self.baseline_entropy: float = 2.0  # Default baseline, should be set per run

        # Last action info for penalty computation
        self.last_action_type: Optional[str] = None
        self.entropy_source: EntropySource = EntropySource.PRIOR

        # CONTAMINATION TRACKING: Log if enforcement is disabled
        self.is_contaminated: bool = not self.config.enable_debt_tracking
        self.contamination_reason: Optional[str] = None

        if self.is_contaminated:
            self.contamination_reason = "DEBT_ENFORCEMENT_DISABLED"
            logger.warning(
                "⚠️  CONTAMINATED RUN: Epistemic debt enforcement is disabled. "
                "This run does not enforce honesty constraints. "
                "Results are not comparable to enforced runs."
            )

    def set_baseline_entropy(self, entropy: float) -> None:
        """
        Set baseline entropy for horizon shrinkage computation.

        This should be called at the start of an experiment to establish
        what "normal" uncertainty looks like.
        """
        self.baseline_entropy = entropy
        logger.info(f"Set baseline entropy to {entropy:.3f} bits")

    def claim_action(
        self,
        action_id: str,
        action_type: str,
        expected_gain_bits: float,
        timestamp: Optional[str] = None,
        prior_modalities: Optional[Tuple[str, ...]] = None,
        claimed_marginal_gain: Optional[float] = None,
    ) -> None:
        """
        Record a claim about expected information gain from an action.

        Args:
            action_id: Unique identifier for this action
            action_type: Type of action (e.g., "scrna_seq")
            expected_gain_bits: Claimed information gain in bits
            timestamp: Optional timestamp
            prior_modalities: Modalities already measured (for marginal gain)
            claimed_marginal_gain: Expected marginal gain accounting for prior measurements
        """
        if not self.config.enable_debt_tracking:
            return

        if timestamp is None:
            timestamp = datetime.now().isoformat()

        self.ledger.claim(
            action_id=action_id,
            action_type=action_type,
            expected_gain_bits=expected_gain_bits,
            timestamp=timestamp,
            prior_modalities=prior_modalities,
            claimed_marginal_gain=claimed_marginal_gain,
        )

    def measure_information_gain(
        self,
        prior_entropy: float,
        posterior_entropy: float,
        entropy_source: Optional[EntropySource] = None,
    ) -> float:
        """
        Measure realized information gain.

        Args:
            prior_entropy: Entropy before action
            posterior_entropy: Entropy after action
            entropy_source: Source of entropy (prior vs measurement-induced)

        Returns:
            Information gain in bits (can be negative)
        """
        gain = compute_information_gain_bits(prior_entropy, posterior_entropy)

        # Store for penalty computation
        self.prior_entropy = prior_entropy
        self.posterior_entropy = posterior_entropy

        # Track entropy for volatility detection
        self.volatility_tracker.add(posterior_entropy)

        # Store entropy source
        if entropy_source is not None:
            self.entropy_source = entropy_source
        else:
            # Infer source from gain
            if gain > 0:
                self.entropy_source = EntropySource.MEASUREMENT_NARROWING
            elif gain < -0.1:  # Significant widening
                self.entropy_source = EntropySource.MEASUREMENT_CONTRADICTORY
            else:
                self.entropy_source = EntropySource.MEASUREMENT_AMBIGUOUS

        return gain

    def resolve_action(
        self,
        action_id: str,
        actual_gain_bits: float,
        action_type: Optional[str] = None,
    ) -> float:
        """
        Resolve an epistemic claim with actual information gain.

        Now includes sandbagging detection: systematic underclaiming is penalized
        by discounting surprising gains.

        Args:
            action_id: Action to resolve
            actual_gain_bits: Realized information gain (can be negative)
            action_type: Optional action type for penalty computation

        Returns:
            Debt increment (positive if overclaimed)
        """
        if not self.config.enable_debt_tracking:
            return 0.0

        # Store action type for penalty computation
        if action_type is not None:
            self.last_action_type = action_type

        # Find the claim to get claimed amount
        claimed_gain = 0.0
        for claim in self.ledger.claims:
            if claim.action_id == action_id and not claim.is_resolved:
                claimed_gain = claim.claimed_gain_bits
                break

        # Apply sandbagging credit discount
        if actual_gain_bits > 0 and claimed_gain > 0:
            # Track in sandbagging detector
            self.sandbagging_detector.add_observation(claimed_gain, actual_gain_bits)

            # Apply discount if sandbagging detected
            credited_gain = self.sandbagging_detector.compute_credit_discount(
                claimed_gain, actual_gain_bits
            )

            # Log if discount applied
            if credited_gain < actual_gain_bits:
                logger.info(
                    f"Sandbagging discount applied: {action_id}, "
                    f"realized={actual_gain_bits:.3f}, "
                    f"credited={credited_gain:.3f}"
                )
        else:
            # No discount for negative gains or zero claims
            credited_gain = actual_gain_bits

        # Resolve claim and accumulate debt using credited gain
        debt_increment = self.ledger.realize(action_id, credited_gain)

        # Track calibration error for stability (use credited gain)
        # Find the claim for this action
        for claim in self.ledger.claims:
            if claim.action_id == action_id and claim.is_resolved:
                self.stability_tracker.add_error(
                    claim.claimed_gain_bits,
                    credited_gain  # Use credited, not actual
                )
                break

        # Apply decay
        self.ledger.apply_decay()

        return debt_increment

    def compute_penalty(
        self,
        action_type: Optional[str] = None,
        prior_entropy: Optional[float] = None,
        posterior_entropy: Optional[float] = None,
        entropy_source: Optional[EntropySource] = None,
    ) -> EpistemicPenaltyResult:
        """
        Compute epistemic penalty for an action.

        Args:
            action_type: Type of action (uses last_action_type if None)
            prior_entropy: Entropy before action (uses stored if None)
            posterior_entropy: Entropy after action (uses stored if None)
            entropy_source: Source of entropy (uses stored if None)

        Returns:
            EpistemicPenaltyResult with penalty components
        """
        if not self.config.enable_penalties:
            # Return zero penalty
            return EpistemicPenaltyResult(
                entropy_penalty=0.0,
                horizon_multiplier=1.0,
                prior_entropy=prior_entropy or self.prior_entropy or 0.0,
                posterior_entropy=posterior_entropy or self.posterior_entropy or 0.0,
            )

        # Use stored values if not provided
        action_type = action_type or self.last_action_type or "unknown"
        prior_entropy = prior_entropy or self.prior_entropy or 0.0
        posterior_entropy = posterior_entropy or self.posterior_entropy or 0.0
        entropy_source = entropy_source or self.entropy_source

        # Compute base penalty
        penalty = compute_full_epistemic_penalty(
            prior_entropy=prior_entropy,
            posterior_entropy=posterior_entropy,
            action_type=action_type,
            baseline_entropy=self.baseline_entropy,
            config=self.config.penalty_config,
            entropy_source=entropy_source,
        )

        # Add volatility penalty (thrashing)
        volatility_penalty = self.volatility_tracker.compute_penalty()
        penalty.entropy_penalty += volatility_penalty

        if volatility_penalty > 0:
            logger.info(f"Added volatility penalty: {volatility_penalty:.3f}")

        return penalty

    def get_inflated_cost(
        self,
        base_cost: float,
        sensitivity: Optional[float] = None,
        is_calibration: bool = False,
        calibration_cap: float = 1.5,
    ) -> float:
        """
        Get cost inflated by epistemic debt.

        Agent 3 Deadlock Fix: Calibration inflation is CAPPED to prevent
        circular trap where debt requires calibration but calibration is
        unaffordable due to debt.

        Args:
            base_cost: Base cost without debt penalty
            sensitivity: Debt sensitivity (uses config default if None)
            is_calibration: If True, apply capped inflation
            calibration_cap: Maximum multiplier for calibration (default: 1.5×)

        Returns:
            Inflated cost

        Deadlock Prevention:
        - Exploration: Full inflation (can be 2×, 3×, etc.)
        - Calibration: Capped at calibration_cap (default 1.5×)
        - This ensures recovery path is always survivable
        """
        if not self.config.enable_debt_tracking:
            return base_cost

        sensitivity = sensitivity or self.config.debt_sensitivity

        # Get full inflation
        full_inflated = self.ledger.get_inflated_cost(base_cost, sensitivity)

        # Agent 3: Cap calibration inflation to prevent deadlock
        if is_calibration:
            multiplier = full_inflated / base_cost if base_cost > 0 else 1.0
            capped_multiplier = min(multiplier, calibration_cap)
            return base_cost * capped_multiplier

        # Exploration gets full inflation
        return full_inflated

    def get_cost_multiplier(self, base_cost: float = 100.0, sensitivity: Optional[float] = None) -> float:
        """
        Get current cost multiplier due to debt and instability.

        Args:
            base_cost: Base cost of action (affects scaling)
            sensitivity: Debt sensitivity (uses config default if None)

        Returns:
            Combined multiplier from debt + instability
        """
        if not self.config.enable_debt_tracking:
            return 1.0

        sensitivity = sensitivity or self.config.debt_sensitivity

        # Base multiplier from debt
        debt_mult = self.ledger.get_cost_multiplier(base_cost, sensitivity)

        # Additional multiplier from calibration instability
        instability_mult = 1.0 + self.stability_tracker.compute_penalty()

        return debt_mult * instability_mult

    def get_total_debt(self) -> float:
        """Get current total epistemic debt."""
        return self.ledger.total_debt

    def compute_repayment(
        self,
        action_id: str,
        action_type: str,
        is_calibration: bool,
        noise_improvement: Optional[float] = None,
        timestamp: Optional[str] = None
    ) -> float:
        """
        Compute debt repayment earned by calibration work.

        Hybrid repayment model:
        - Base repayment: 0.25 bits for any successful calibration
        - Bonus repayment: up to 0.75 bits for measurable noise improvement
        - Cap: 1.0 bit total per action

        Args:
            action_id: Action that may earn repayment
            action_type: Type of action ("baseline", "edge_test", etc.)
            is_calibration: True if action was a calibration template
            noise_improvement: Optional fractional reduction in noise (rel_width_prev - rel_width_new)
            timestamp: When repayment occurred

        Returns:
            Repayment amount in bits (0 if not earned)
        """
        if not is_calibration:
            return 0.0  # Only calibration earns repayment

        # Base repayment for successful calibration
        BASE_REPAYMENT = 0.25
        MAX_BONUS_REPAYMENT = 0.75
        REPAYMENT_CAP = 1.0

        repay_bits = BASE_REPAYMENT
        repayment_reason = "calibration_base"
        evidence = {"action_type": action_type}

        # Bonus repayment for measurable noise improvement
        if noise_improvement is not None and noise_improvement > 0:
            # Bonus proportional to improvement: 0.75 bits for 10% improvement
            bonus = min(MAX_BONUS_REPAYMENT, noise_improvement * 7.5)
            repay_bits += bonus
            repayment_reason = "calibration_with_noise_improvement"
            evidence["noise_improvement"] = noise_improvement
            evidence["bonus_repayment"] = bonus

        # Apply cap
        repay_bits = min(repay_bits, REPAYMENT_CAP)
        evidence["total_repayment"] = repay_bits

        # Apply repayment to ledger
        actual_repayment = self.ledger.apply_repayment(
            action_id=action_id,
            action_type=action_type,
            repay_bits=repay_bits,
            repayment_reason=repayment_reason,
            evidence=evidence,
            timestamp=timestamp or datetime.now().isoformat()
        )

        return actual_repayment

    def should_refuse_action(
        self,
        template_name: str,
        base_cost_wells: int,
        budget_remaining: int,
        debt_hard_threshold: float = 2.0,
        calibration_templates: Optional[set] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check whether an action should be refused due to epistemic debt.

        Agent 3 enforcement with deadlock prevention:
        1. Hard threshold: debt > 2.0 bits blocks non-calibration actions
        2. Cost inflation: debt increases cost (soft block)
        3. Budget reserve: non-calibration actions must leave MIN_CALIBRATION_COST_WELLS
           available for recovery (prevents epistemic bankruptcy)

        Returns:
            (should_refuse, refusal_reason, context)
            - should_refuse: True if action must be blocked
            - refusal_reason: One of:
                * "epistemic_debt_action_blocked" - hard threshold exceeded
                * "epistemic_debt_budget_exceeded" - cost inflation exceeds budget
                * "insufficient_budget_for_epistemic_recovery" - would prevent calibration
            - context: Dict with debt_bits, inflated_cost, etc. for RefusalEvent
        """
        if not self.config.enable_debt_tracking:
            return (False, "", {})

        if calibration_templates is None:
            calibration_templates = {"baseline", "calibration", "dmso_replicates", "baseline_replicates"}

        # Agent 3 Deadlock Fix: Determine calibration BEFORE inflation
        is_calibration = template_name in calibration_templates

        debt = self.get_total_debt()

        # Agent 3 Deadlock Fix: Pass is_calibration to get capped inflation
        inflated_cost = self.get_inflated_cost(
            base_cost=float(base_cost_wells),
            is_calibration=is_calibration
        )

        # Agent 3: Budget reserve enforcement
        # Non-calibration actions must leave enough budget for recovery
        budget_after_action = budget_remaining - inflated_cost
        blocked_by_reserve = (not is_calibration) and (budget_after_action < MIN_CALIBRATION_COST_WELLS)

        # Check cost inflation (soft block)
        blocked_by_cost = inflated_cost > budget_remaining

        # Check debt threshold (hard block for non-calibration actions)
        blocked_by_threshold = (debt > debt_hard_threshold) and not is_calibration

        # Agent 3 Deadlock Fix: Detect epistemic deadlock explicitly
        # Deadlock = debt requires calibration BUT calibration is unaffordable
        is_deadlocked = False
        if debt > debt_hard_threshold:
            # Agent must calibrate to recover
            # Check if ANY calibration action is affordable
            min_calib_inflated = self.get_inflated_cost(
                base_cost=MIN_CALIBRATION_COST_WELLS,
                is_calibration=True  # Capped inflation
            )
            # Deadlock: calibration required but unaffordable
            is_deadlocked = (min_calib_inflated > budget_remaining)

        # Determine refusal reason (precedence matters for clarity)
        should_refuse = blocked_by_threshold or blocked_by_cost or blocked_by_reserve or is_deadlocked

        if is_deadlocked:
            refusal_reason = "epistemic_deadlock_detected"
        elif blocked_by_threshold:
            refusal_reason = "epistemic_debt_action_blocked"
        elif blocked_by_reserve:
            refusal_reason = "insufficient_budget_for_epistemic_recovery"
        elif blocked_by_cost:
            refusal_reason = "epistemic_debt_budget_exceeded"
        else:
            refusal_reason = ""

        context = {
            "debt_bits": debt,
            "base_cost_wells": base_cost_wells,
            "inflated_cost_wells": int(inflated_cost),
            "budget_remaining": budget_remaining,
            "budget_after_action": int(budget_after_action),
            "required_reserve": MIN_CALIBRATION_COST_WELLS,
            "debt_threshold": debt_hard_threshold,
            "blocked_by_threshold": blocked_by_threshold,
            "blocked_by_cost": blocked_by_cost,
            "blocked_by_reserve": blocked_by_reserve,
            "is_calibration": is_calibration,
            "is_deadlocked": is_deadlocked,
        }

        return (should_refuse, refusal_reason, context)

    def add_provisional_penalty(
        self,
        action_id: str,
        penalty_amount: float,
        settlement_horizon: int = 3,
    ) -> str:
        """
        Add a provisional penalty for multi-step credit assignment.

        Used when an action widens entropy but may lead to later resolution.

        Args:
            action_id: Action that caused widening
            penalty_amount: Penalty to hold in escrow
            settlement_horizon: Episodes before settlement

        Returns:
            Provisional penalty ID
        """
        prior_entropy = self.prior_entropy or 0.0
        return self.provisional_tracker.add_provisional_penalty(
            action_id=action_id,
            penalty_amount=penalty_amount,
            prior_entropy=prior_entropy,
            settlement_horizon=settlement_horizon,
        )

    def step_provisional_penalties(self, time_increment_h: float = 0.0) -> float:
        """
        Step provisional penalties forward and settle expired ones.

        Args:
            time_increment_h: Real time elapsed since last step (hours)
                             If 0, uses episode-based settlement

        Returns:
            Total penalties finalized this step
        """
        current_entropy = self.posterior_entropy or 0.0
        return self.provisional_tracker.step(current_entropy, time_increment_h)

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics for auditing."""
        stats = self.ledger.get_statistics()
        stats["cost_multiplier"] = self.get_cost_multiplier()
        stats["baseline_entropy"] = self.baseline_entropy

        # Add contamination status
        stats["is_contaminated"] = self.is_contaminated
        if self.contamination_reason:
            stats["contamination_reason"] = self.contamination_reason

        # Add provisional penalty stats
        prov_stats = self.provisional_tracker.get_statistics()
        stats.update({
            f"provisional_{k}": v for k, v in prov_stats.items()
        })

        # Add volatility stats
        vol_stats = self.volatility_tracker.get_statistics()
        stats.update({
            f"volatility_{k}": v for k, v in vol_stats.items()
        })

        # Add stability stats
        stab_stats = self.stability_tracker.get_statistics()
        stats.update({
            f"stability_{k}": v for k, v in stab_stats.items()
        })

        # Add sandbagging stats
        sandbag_stats = self.sandbagging_detector.get_statistics()
        stats.update({
            f"sandbagging_{k}": v for k, v in sandbag_stats.items()
        })

        return stats

    def save(self, path: Path) -> None:
        """Save controller state to disk."""
        self.ledger.save(path)

    @classmethod
    def load(cls, path: Path, config: Optional[EpistemicControllerConfig] = None) -> "EpistemicController":
        """Load controller state from disk."""
        controller = cls(config)
        controller.ledger = EpistemicDebtLedger.load(path)
        return controller

    def reset(self) -> None:
        """Reset controller state (for new episode/experiment)."""
        self.ledger = EpistemicDebtLedger(debt_decay_rate=self.config.debt_decay_rate)
        self.provisional_tracker = ProvisionalPenaltyTracker()
        self.volatility_tracker.reset()
        self.stability_tracker.reset()
        self.sandbagging_detector.reset()
        self.prior_entropy = None
        self.posterior_entropy = None
        self.last_action_type = None
        self.entropy_source = EntropySource.PRIOR
        logger.info("Epistemic controller reset")


# Convenience function for standalone usage
def measure_and_penalize(
    prior_entropy: float,
    posterior_entropy: float,
    action_type: str,
    baseline_entropy: float = 2.0,
    penalty_weight: float = 1.0,
    entropy_source: Optional[EntropySource] = None,
) -> Dict[str, float]:
    """
    Convenience function to measure info gain and compute penalty in one call.

    Args:
        prior_entropy: Entropy before action
        posterior_entropy: Entropy after action
        action_type: Type of action
        baseline_entropy: Baseline for horizon computation
        penalty_weight: Weight for entropy penalty
        entropy_source: Source of entropy (prior vs measurement-induced)

    Returns:
        Dict with info_gain, entropy_penalty, horizon_multiplier
    """
    config = EpistemicPenaltyConfig(entropy_penalty_weight=penalty_weight)

    result = compute_full_epistemic_penalty(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        action_type=action_type,
        baseline_entropy=baseline_entropy,
        config=config,
        entropy_source=entropy_source,
    )

    return {
        "info_gain": result.info_gain,
        "entropy_penalty": result.entropy_penalty,
        "horizon_multiplier": result.horizon_multiplier,
        "did_widen": result.did_widen,
    }
