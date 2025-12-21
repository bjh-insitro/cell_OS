"""
Epistemic debt: tracking the gap between claimed and realized information gain.

PHILOSOPHY: Agents that consistently overpromise information gain should face
higher costs for expensive assays. This creates pressure toward calibration
without hardcoding thresholds.

The asymmetry matters:
- Overclaiming hurts more than underclaiming helps
- Conservative estimates are rewarded (low debt)
- Aggressive estimates must be correct or accumulate debt

Debt is cumulative and bleeds into future action costs, creating long-term
memory of epistemic failures.

═══════════════════════════════════════════════════════════════════════════════
HARD REGIME SEMANTICS (ENFORCED)
═══════════════════════════════════════════════════════════════════════════════

This system implements a HARD debt regime with the following contract:

1. WHAT IS ONE BIT OF DEBT?
   One bit of debt = one bit of overclaimed information gain.

   If agent claims "this experiment will reduce entropy by 1.5 bits"
   but it only reduces by 0.5 bits, debt increases by 1.0 bit.

   Debt accumulates over time as overclaim penalties compound.

2. WHAT CAUSES DEBT TO INCREASE?
   - Agent proposes experiment claiming X bits of expected gain
   - Experiment executes, actual gain is measured
   - If actual < claimed: debt += (claimed - actual)
   - Only overclaims accumulate debt (underclaims do not reduce debt)

3. WHAT REPAYS DEBT?
   - Calibration actions (baseline, edge tests, noise characterization)
   - Each successful calibration repays 0.25 bits (base)
   - Measurable noise improvement grants bonus repayment (up to 0.75 bits)
   - Maximum 1.0 bit repayment per calibration action
   - Repayment requires evidence (logged in RepaymentEvent)

4. WHAT HAPPENS AT EACH DEBT LEVEL?

   debt = 0 bits:
     → Full access to all experimental templates
     → No cost inflation

   0 < debt < 2.0 bits:
     → WARNING zone
     → Cost inflation applies (makes expensive assays costlier)
     → Biology experiments still permitted
     → Agent should calibrate voluntarily to reduce debt

   debt >= 2.0 bits (THRESHOLD):
     → HARD BLOCK zone
     → Non-calibration actions are REFUSED
     → Agent must propose calibration to reduce debt below threshold
     → Calibration actions remain accessible
     → Access restored when debt < 2.0 bits

5. BEHAVIORAL CONTRACT:
   - System blocks non-calibration actions when debt >= threshold
   - Agent detects insolvency via `epistemic_insolvent` flag
   - Agent must switch strategy to calibration templates
   - Calibration reduces debt → access restored
   - If agent cannot recover after 3 refusals → bankruptcy (abort)

6. ENFORCEMENT:
   - Debt enforcement is NON-OPTIONAL by default
   - Disabling enforcement contaminates the run (logged to diagnostics)
   - Silent bypasses are forbidden
   - All debt changes are audited with timestamps

This is not a soft suggestion. This is a forcing function.
Agents that overclaim will lose access to biology until they calibrate.
═══════════════════════════════════════════════════════════════════════════════
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EpistemicClaim:
    """A single claim about expected information gain from an action."""

    action_id: str
    action_type: str  # e.g., "scrna_seq", "cell_painting"
    claimed_gain_bits: float
    realized_gain_bits: Optional[float] = None
    timestamp: str = ""

    # Marginal info gain accounting (prevents redundancy spam)
    prior_modalities: Optional[Tuple[str, ...]] = None  # What was already measured
    claimed_marginal_gain: Optional[float] = None  # Info gain accounting for prior measurements

    @property
    def is_resolved(self) -> bool:
        """Has this claim been resolved with actual information gain?"""
        return self.realized_gain_bits is not None

    @property
    def overclaim(self) -> float:
        """How much did we overclaim? (positive = overpromised, negative = underpromised)"""
        if not self.is_resolved:
            return 0.0
        return self.claimed_gain_bits - self.realized_gain_bits

    @property
    def overclaim_penalty(self) -> float:
        """Penalty for overclaiming (asymmetric: overclaim hurts, underclaim doesn't help)."""
        return max(0.0, self.overclaim)


@dataclass
class RepaymentEvent:
    """
    A debt repayment event from calibration work.

    Debt repayment is earned by calibration actions that measurably improve
    epistemic conditions (reduced noise, deconfounded nuisance, etc.).

    This is NOT free forgiveness. Every repayment must have evidence.
    """
    action_id: str
    action_type: str  # "baseline", "edge_test", etc.
    repay_bits: float  # Non-negative repayment amount
    repayment_reason: str  # Why repayment was granted
    evidence: Dict[str, Any]  # Measurement evidence justifying repayment
    timestamp: str = ""

    def __post_init__(self):
        """Enforce non-negative repayment."""
        if self.repay_bits < 0:
            raise ValueError(f"Repayment must be non-negative, got {self.repay_bits}")


@dataclass
class EpistemicDebtLedger:
    """
    Track gap between claimed and realized information gain.

    Debt accumulates when agents overclaim. High debt increases costs for
    future expensive actions, creating pressure toward calibrated justifications.

    Debt is reduced through calibration work that measurably improves epistemic
    conditions (reduced noise, deconfounded nuisance, etc.).

    Attributes:
        total_debt: Cumulative overclaim penalty (bits)
        claims: History of all epistemic claims
        repayments: History of all debt repayments (calibration work)
        debt_decay_rate: Optional decay per action (deprecated, use repayments instead)
    """

    total_debt: float = 0.0
    claims: List[EpistemicClaim] = field(default_factory=list)
    repayments: List[RepaymentEvent] = field(default_factory=list)
    debt_decay_rate: float = 0.0  # Deprecated: use evidence-based repayments instead

    def claim(
        self,
        action_id: str,
        action_type: str,
        expected_gain_bits: float,
        timestamp: str = "",
        prior_modalities: Optional[Tuple[str, ...]] = None,
        claimed_marginal_gain: Optional[float] = None,
    ) -> None:
        """
        Record a claim about expected information gain.

        Args:
            action_id: Unique identifier for this action
            action_type: Type of action (e.g., "scrna_seq")
            expected_gain_bits: Claimed information gain in bits
            timestamp: Optional timestamp for auditing
            prior_modalities: Modalities already measured (for marginal gain tracking)
            claimed_marginal_gain: Expected marginal gain accounting for prior measurements
        """
        claim = EpistemicClaim(
            action_id=action_id,
            action_type=action_type,
            claimed_gain_bits=expected_gain_bits,
            timestamp=timestamp,
            prior_modalities=prior_modalities,
            claimed_marginal_gain=claimed_marginal_gain,
        )
        self.claims.append(claim)

        if claimed_marginal_gain is not None:
            logger.debug(
                f"Epistemic claim: {action_id} expects {expected_gain_bits:.3f} bits "
                f"(marginal: {claimed_marginal_gain:.3f} after {prior_modalities})"
            )
        else:
            logger.debug(f"Epistemic claim: {action_id} expects {expected_gain_bits:.3f} bits")

    def realize(self, action_id: str, actual_gain_bits: float) -> float:
        """
        Update with actual information gain and compute debt increment.

        Args:
            action_id: Action to resolve
            actual_gain_bits: Realized information gain (can be negative if posterior widened)

        Returns:
            Debt increment (positive if overclaimed)
        """
        # Find unresolved claim with this action_id
        for claim in self.claims:
            if claim.action_id == action_id and not claim.is_resolved:
                claim.realized_gain_bits = actual_gain_bits
                penalty = claim.overclaim_penalty
                self.total_debt += penalty

                logger.info(
                    f"Epistemic claim resolved: {action_id} "
                    f"claimed={claim.claimed_gain_bits:.3f}, "
                    f"realized={actual_gain_bits:.3f}, "
                    f"overclaim_penalty={penalty:.3f}, "
                    f"total_debt={self.total_debt:.3f}"
                )

                return penalty

        logger.warning(f"No unresolved claim found for action {action_id}")
        return 0.0

    def apply_decay(self) -> None:
        """Apply debt decay (DEPRECATED: use apply_repayment instead)."""
        if self.debt_decay_rate > 0:
            old_debt = self.total_debt
            self.total_debt = max(0.0, self.total_debt - self.debt_decay_rate)
            if old_debt != self.total_debt:
                logger.debug(f"Debt decay: {old_debt:.3f} → {self.total_debt:.3f}")

    def apply_repayment(
        self,
        action_id: str,
        action_type: str,
        repay_bits: float,
        repayment_reason: str,
        evidence: Dict[str, Any],
        timestamp: str = ""
    ) -> float:
        """
        Apply debt repayment from calibration work.

        Debt can only be repaid through measurable epistemic improvements.
        Every repayment must have evidence justifying it.

        Args:
            action_id: Action that earned repayment
            action_type: Type of calibration action
            repay_bits: Amount of debt to repay (must be non-negative)
            repayment_reason: Why repayment was granted (for audit)
            evidence: Measurement evidence justifying repayment
            timestamp: When repayment occurred

        Returns:
            Actual debt reduction (may be capped by remaining debt)
        """
        if repay_bits < 0:
            raise ValueError(f"Repayment must be non-negative, got {repay_bits}")

        if repay_bits == 0:
            return 0.0

        # Cap repayment at remaining debt (no negative debt allowed)
        actual_repayment = min(repay_bits, self.total_debt)
        old_debt = self.total_debt
        self.total_debt = max(0.0, self.total_debt - actual_repayment)

        # Record repayment event
        repayment = RepaymentEvent(
            action_id=action_id,
            action_type=action_type,
            repay_bits=actual_repayment,
            repayment_reason=repayment_reason,
            evidence=evidence,
            timestamp=timestamp
        )
        self.repayments.append(repayment)

        logger.info(
            f"Debt repayment: {action_id} ({action_type}) "
            f"repaid={actual_repayment:.3f} bits "
            f"(reason: {repayment_reason}), "
            f"debt: {old_debt:.3f} → {self.total_debt:.3f}"
        )

        return actual_repayment

    def get_cost_multiplier(
        self,
        base_cost: float,
        sensitivity: float = 0.1,
        global_sensitivity: float = 0.02,
    ) -> float:
        """
        Convert debt to cost multiplier for future actions.

        Uses two-tier inflation:
        1. Global inflation (2% per bit): Affects ALL actions (prevents debt farming)
        2. Action-specific inflation (10% per bit): Affects expensive actions more

        Args:
            base_cost: Base cost of the action (e.g., $200 for scRNA, $20 for imaging)
            sensitivity: Action-specific sensitivity (default: 10% per bit)
            global_sensitivity: Global sensitivity (default: 2% per bit)

        Returns:
            Cost multiplier (1.0 = no inflation, >1.0 = debt penalty)

        Example:
            debt = 2.0 bits
            Cheap assay ($20):  1.04× (4% from global)
            Expensive assay ($200): 1.24× (4% global + 20% specific)
        """
        # Global inflation: affects all actions
        global_mult = 1.0 + global_sensitivity * self.total_debt

        # Action-specific inflation: scales with cost
        # More expensive actions face higher penalty
        cost_ratio = base_cost / 100.0  # Normalize to $100
        specific_mult = 1.0 + sensitivity * cost_ratio * self.total_debt

        # Combined
        return global_mult * specific_mult

    def get_inflated_cost(
        self,
        base_cost: float,
        sensitivity: float = 0.1,
        global_sensitivity: float = 0.02,
    ) -> float:
        """
        Get cost inflated by epistemic debt.

        Args:
            base_cost: Base cost without debt penalty
            sensitivity: Action-specific debt sensitivity
            global_sensitivity: Global debt sensitivity

        Returns:
            Inflated cost
        """
        multiplier = self.get_cost_multiplier(base_cost, sensitivity, global_sensitivity)
        return base_cost * multiplier

    def get_statistics(self) -> Dict[str, float]:
        """
        Compute summary statistics for auditing.

        Returns:
            Dict with mean_overclaim, overclaim_rate, total_claims, resolved_claims
        """
        resolved = [c for c in self.claims if c.is_resolved]

        if not resolved:
            return {
                "total_claims": len(self.claims),
                "resolved_claims": 0,
                "mean_overclaim": 0.0,
                "overclaim_rate": 0.0,
                "total_debt": self.total_debt,
            }

        overclaims = [c.overclaim for c in resolved]
        mean_overclaim = sum(overclaims) / len(overclaims)
        overclaim_rate = sum(1 for oc in overclaims if oc > 0) / len(overclaims)

        return {
            "total_claims": len(self.claims),
            "resolved_claims": len(resolved),
            "mean_overclaim": mean_overclaim,
            "overclaim_rate": overclaim_rate,
            "total_debt": self.total_debt,
        }

    def save(self, path: Path) -> None:
        """Save ledger to JSON for auditing."""
        data = {
            "total_debt": self.total_debt,
            "debt_decay_rate": self.debt_decay_rate,
            "claims": [
                {
                    "action_id": c.action_id,
                    "action_type": c.action_type,
                    "claimed_gain_bits": c.claimed_gain_bits,
                    "realized_gain_bits": c.realized_gain_bits,
                    "timestamp": c.timestamp,
                }
                for c in self.claims
            ],
            "statistics": self.get_statistics(),
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved epistemic debt ledger to {path}")

    @classmethod
    def load(cls, path: Path) -> "EpistemicDebtLedger":
        """Load ledger from JSON."""
        with open(path) as f:
            data = json.load(f)

        claims = [
            EpistemicClaim(
                action_id=c["action_id"],
                action_type=c["action_type"],
                claimed_gain_bits=c["claimed_gain_bits"],
                realized_gain_bits=c.get("realized_gain_bits"),
                timestamp=c.get("timestamp", ""),
            )
            for c in data["claims"]
        ]

        return cls(
            total_debt=data["total_debt"],
            claims=claims,
            debt_decay_rate=data.get("debt_decay_rate", 0.0),
        )


def compute_information_gain_bits(prior_entropy: float, posterior_entropy: float) -> float:
    """
    Compute information gain in bits.

    I(mechanism; data) = H(prior) - H(posterior)

    Positive: posterior is more certain (gained information)
    Negative: posterior is less certain (lost information / widened)
    Zero: no change in uncertainty

    Args:
        prior_entropy: Entropy before observation (bits)
        posterior_entropy: Entropy after observation (bits)

    Returns:
        Information gain in bits (can be negative)
    """
    gain = prior_entropy - posterior_entropy
    return gain
