"""
Epistemic Controller Integration for Agent Workflow.

This module wires the epistemic controller into the agent's design-execute-observe loop:
1. Claims are made when designs are proposed
2. Gains are measured when observations arrive
3. Debt accumulates from miscalibration
4. Costs inflate with debt

Architecture:
    Agent → Propose (claim) → Bridge → Execute → Observe (resolve) → Agent

Key invariants:
- Every design proposal creates a claim (even if design rejected)
- Every observation resolves a claim (even if gain negative)
- Debt persists across cycles (no episode reset)
- Cost inflation applies to all expensive actions (scRNA, imaging)
"""

import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from cell_os.epistemic_agent.control import (
    EpistemicController,
    EpistemicControllerConfig,
)
from cell_os.hardware.mechanism_posterior_v2 import MechanismPosterior

logger = logging.getLogger(__name__)


@dataclass
class ClaimMetadata:
    """
    Metadata for epistemic claim tracking.

    Associates claims with designs and observations for resolution.
    """
    design_id: str
    cycle: int
    hypothesis: str
    modalities: Tuple[str, ...]
    wells_count: int
    estimated_cost_usd: float


class EpistemicIntegration:
    """
    Integration layer between epistemic controller and agent workflow.

    This class:
    1. Tracks claims when designs are proposed
    2. Measures gains when observations arrive
    3. Inflates costs based on accumulated debt
    4. Provides audit trail for agent calibration

    Usage:
        integration = EpistemicIntegration()

        # When agent proposes design
        claim_id = integration.claim_design(
            design_id="design_001",
            expected_gain_bits=0.8,
            hypothesis="ER stress mechanism",
            modalities=("cell_painting",),
            wells_count=16,
            estimated_cost_usd=50.0
        )

        # When observations arrive
        integration.resolve_design(
            claim_id=claim_id,
            prior_posterior=prior,
            posterior=posterior
        )

        # When planning next action
        inflated_cost = integration.get_inflated_cost(base_cost=200.0)
    """

    def __init__(
        self,
        controller: Optional[EpistemicController] = None,
        config: Optional[EpistemicControllerConfig] = None,
        enable: bool = True
    ):
        """
        Initialize epistemic integration.

        Args:
            controller: Existing controller (or None to create new)
            config: Controller configuration
            enable: Enable epistemic control (False for testing/debugging)
        """
        self.enable = enable

        if not enable:
            self.controller = None
            logger.info("Epistemic integration DISABLED (testing mode)")
            return

        self.controller = controller or EpistemicController(config)

        # Track claims awaiting resolution
        self.pending_claims: Dict[str, ClaimMetadata] = {}

        # Track baseline entropy (set during first observation)
        self.baseline_set = False

        logger.info("Epistemic integration ENABLED")

    def claim_design(
        self,
        design_id: str,
        cycle: int,
        expected_gain_bits: float,
        hypothesis: str,
        modalities: Tuple[str, ...],
        wells_count: int,
        estimated_cost_usd: float,
        prior_modalities: Optional[Tuple[str, ...]] = None,
    ) -> str:
        """
        Record epistemic claim when agent proposes design.

        This happens BEFORE design validation, so claims are made even if
        design is rejected. This prevents gaming by proposing cheap designs
        after expensive ones fail.

        Args:
            design_id: Design identifier
            cycle: Current cycle number
            expected_gain_bits: Agent's claimed information gain
            hypothesis: Agent's hypothesis for this design
            modalities: Modalities in this design (e.g., ("cell_painting", "scrna_seq"))
            wells_count: Number of wells in design
            estimated_cost_usd: Estimated cost (for cost inflation)
            prior_modalities: Modalities already measured (for marginal gain)

        Returns:
            claim_id: Unique identifier for this claim
        """
        if not self.enable:
            return f"disabled_{design_id}"

        claim_id = f"claim_{cycle}_{design_id}"

        # Store metadata for resolution
        self.pending_claims[claim_id] = ClaimMetadata(
            design_id=design_id,
            cycle=cycle,
            hypothesis=hypothesis,
            modalities=modalities,
            wells_count=wells_count,
            estimated_cost_usd=estimated_cost_usd
        )

        # Compute action type from modalities
        action_type = "+".join(sorted(modalities))

        # Record claim in controller
        self.controller.claim_action(
            action_id=claim_id,
            action_type=action_type,
            expected_gain_bits=expected_gain_bits,
            prior_modalities=prior_modalities,
        )

        logger.info(
            f"Claimed design {design_id}: "
            f"expected_gain={expected_gain_bits:.3f} bits, "
            f"modalities={modalities}"
        )

        return claim_id

    def resolve_design(
        self,
        claim_id: str,
        prior_posterior: MechanismPosterior,
        posterior: MechanismPosterior,
    ) -> Dict[str, float]:
        """
        Resolve epistemic claim when observations arrive.

        Measures realized information gain and accumulates debt if agent
        overclaimed or underclaimed.

        Args:
            claim_id: Claim to resolve
            prior_posterior: Posterior before this design
            posterior: Posterior after this design

        Returns:
            Dict with realized_gain, debt_increment, total_debt
        """
        if not self.enable:
            return {"realized_gain": 0.0, "debt_increment": 0.0, "total_debt": 0.0}

        if claim_id not in self.pending_claims:
            logger.warning(f"Attempted to resolve unknown claim: {claim_id}")
            return {"realized_gain": 0.0, "debt_increment": 0.0, "total_debt": 0.0}

        metadata = self.pending_claims.pop(claim_id)

        # Set baseline entropy on first observation
        if not self.baseline_set:
            self.controller.set_baseline_entropy(prior_posterior.entropy)
            self.baseline_set = True

        # Measure information gain
        realized_gain = self.controller.measure_information_gain(
            prior_entropy=prior_posterior.entropy,
            posterior_entropy=posterior.entropy
        )

        # Resolve claim and accumulate debt
        action_type = "+".join(sorted(metadata.modalities))
        debt_increment = self.controller.resolve_action(
            action_id=claim_id,
            actual_gain_bits=realized_gain,
            action_type=action_type
        )

        total_debt = self.controller.get_total_debt()

        logger.info(
            f"Resolved claim {claim_id}: "
            f"realized_gain={realized_gain:.3f} bits, "
            f"debt_increment={debt_increment:.3f}, "
            f"total_debt={total_debt:.3f}"
        )

        return {
            "realized_gain": realized_gain,
            "debt_increment": debt_increment,
            "total_debt": total_debt,
            "cost_multiplier": self.controller.get_cost_multiplier()
        }

    def get_inflated_cost(
        self,
        base_cost: float,
        action_type: str = "unknown"
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Get cost inflated by epistemic debt.

        This is called when planning expensive actions (scRNA, large imaging campaigns).
        Debt makes future actions more expensive, creating economic pressure toward
        calibrated justifications.

        Args:
            base_cost: Base cost without debt penalty
            action_type: Type of action (for logging)

        Returns:
            (inflated_cost, inflation_details)
        """
        if not self.enable:
            return base_cost, {"multiplier": 1.0, "debt": 0.0}

        inflated_cost = self.controller.get_inflated_cost(base_cost)
        multiplier = self.controller.get_cost_multiplier(base_cost)
        total_debt = self.controller.get_total_debt()

        inflation_details = {
            "base_cost": base_cost,
            "inflated_cost": inflated_cost,
            "multiplier": multiplier,
            "total_debt": total_debt,
            "inflation_amount": inflated_cost - base_cost
        }

        if multiplier > 1.1:  # Log significant inflation
            logger.warning(
                f"Cost inflation for {action_type}: "
                f"${base_cost:.0f} → ${inflated_cost:.0f} "
                f"(multiplier={multiplier:.2f}×, debt={total_debt:.3f} bits)"
            )

        return inflated_cost, inflation_details

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

        This is the enforcement mechanism. When debt accumulates from overclaiming,
        actions become either too expensive (soft block) or outright forbidden
        (hard block).

        Args:
            template_name: Name of experiment template (e.g., "baseline", "dose_response")
            base_cost_wells: Base cost in wells without inflation
            budget_remaining: Wells remaining in budget
            debt_hard_threshold: Debt threshold above which non-calibration actions blocked
            calibration_templates: Templates that reduce debt (always allowed)

        Returns:
            (should_refuse, refusal_reason, context)
            - should_refuse: True if action must be blocked
            - refusal_reason: "epistemic_debt_budget_exceeded" or "epistemic_debt_action_blocked"
            - context: Dict with debt_bits, inflated_cost, etc.
        """
        if not self.enable:
            return (False, "", {})

        return self.controller.should_refuse_action(
            template_name=template_name,
            base_cost_wells=base_cost_wells,
            budget_remaining=budget_remaining,
            debt_hard_threshold=debt_hard_threshold,
            calibration_templates=calibration_templates,
        )

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

        Wrapper around controller.compute_repayment for integration layer.

        Args:
            action_id: Action that may earn repayment
            action_type: Type of action
            is_calibration: True if calibration template
            noise_improvement: Optional noise reduction
            timestamp: When repayment occurred

        Returns:
            Repayment amount in bits
        """
        if not self.enable:
            return 0.0

        return self.controller.compute_repayment(
            action_id=action_id,
            action_type=action_type,
            is_calibration=is_calibration,
            noise_improvement=noise_improvement,
            timestamp=timestamp
        )

    def get_penalty(
        self,
        action_type: str,
        prior_entropy: float,
        posterior_entropy: float
    ) -> Dict[str, Any]:
        """
        Compute epistemic penalty for an action (widening penalty).

        Args:
            action_type: Type of action
            prior_entropy: Entropy before action
            posterior_entropy: Entropy after action

        Returns:
            Penalty details (entropy_penalty, horizon_multiplier, etc.)
        """
        if not self.enable:
            return {"entropy_penalty": 0.0, "horizon_multiplier": 1.0}

        result = self.controller.compute_penalty(
            action_type=action_type,
            prior_entropy=prior_entropy,
            posterior_entropy=posterior_entropy
        )

        return {
            "entropy_penalty": result.entropy_penalty,
            "horizon_multiplier": result.horizon_multiplier,
            "did_widen": result.did_widen,
            "info_gain": result.info_gain
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics."""
        if not self.enable:
            return {"enabled": False}

        stats = self.controller.get_statistics()
        stats["enabled"] = True
        stats["pending_claims"] = len(self.pending_claims)
        stats["baseline_set"] = self.baseline_set

        return stats

    def save(self, path: Path) -> None:
        """Save controller state."""
        if self.enable:
            self.controller.save(path)

    @classmethod
    def load(
        cls,
        path: Path,
        config: Optional[EpistemicControllerConfig] = None,
        enable: bool = True
    ) -> "EpistemicIntegration":
        """Load controller state from disk."""
        if not enable:
            return cls(enable=False)

        controller = EpistemicController.load(path, config)
        return cls(controller=controller, enable=True)

    def reset(self) -> None:
        """Reset controller state (WARNING: loses all debt history)."""
        if self.enable:
            self.controller.reset()
            self.pending_claims.clear()
            self.baseline_set = False
            logger.warning("Epistemic controller RESET - all debt cleared")


# Convenience function for testing
def compute_information_gain(
    prior_posterior: MechanismPosterior,
    posterior: MechanismPosterior
) -> float:
    """
    Compute information gain between two posteriors.

    Args:
        prior_posterior: Posterior before observation
        posterior: Posterior after observation

    Returns:
        Information gain in bits (can be negative if widened)
    """
    from cell_os.epistemic_agent.debt import compute_information_gain_bits
    return compute_information_gain_bits(
        prior_posterior.entropy,
        posterior.entropy
    )
