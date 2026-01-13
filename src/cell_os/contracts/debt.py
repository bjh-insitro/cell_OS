"""
Epistemic debt enforcement contract.

The debt system penalizes overclaiming information gain. When an agent claims
more bits than they actually realize, they accrue debt. At high debt levels,
non-calibration actions are blocked.

Key thresholds:
- 0 bits: Clean state, all actions allowed
- 0-2 bits: Warning zone, cost inflation applies
- >= 2 bits: HARD BLOCK, only calibration actions allowed
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

# Hard block threshold: at or above this, non-calibration actions are refused
DEBT_HARD_BLOCK_THRESHOLD: float = 2.0

# Actions that are always allowed (reduce debt)
CALIBRATION_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "calibration",
        "baseline",
        "edge_test",
        "noise_characterization",
        "replicate_collection",
    }
)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class DebtViolation(Exception):
    """Raised when action attempted while epistemically insolvent.

    Contains forensic evidence:
    - action_type: What was attempted
    - current_debt: Current debt level
    - threshold: The blocking threshold
    - details: Additional context
    """

    action_type: str
    current_debt: float
    threshold: float = DEBT_HARD_BLOCK_THRESHOLD
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        msg = (
            f"Action '{self.action_type}' blocked: "
            f"debt={self.current_debt:.2f} >= threshold={self.threshold:.2f}. "
            f"Only calibration actions allowed until debt is repaid."
        )
        super().__init__(msg)


def is_calibration_action(action_type: str) -> bool:
    """Check if an action type is a calibration action (always allowed)."""
    return action_type.lower() in CALIBRATION_ACTION_TYPES


def check_debt_threshold(
    debt: float,
    action_type: str,
    threshold: float = DEBT_HARD_BLOCK_THRESHOLD,
) -> None:
    """Check if action is allowed given current debt level.

    Args:
        debt: Current epistemic debt in bits
        action_type: Type of action being attempted
        threshold: Debt level at which blocking occurs

    Raises:
        DebtViolation: If action blocked due to high debt
    """
    if debt >= threshold and not is_calibration_action(action_type):
        raise DebtViolation(
            action_type=action_type,
            current_debt=debt,
            threshold=threshold,
            details={
                "allowed_actions": list(CALIBRATION_ACTION_TYPES),
                "suggestion": "Run calibration actions to reduce debt",
            },
        )


def debt_enforced(
    action_type_param: str = "action_type",
    threshold: float = DEBT_HARD_BLOCK_THRESHOLD,
) -> Callable[[F], F]:
    """Decorator to enforce debt threshold before action execution.

    Checks the debt ledger before allowing non-calibration actions.
    The decorated method's class must have a `debt_ledger` attribute
    with a `total_debt` property.

    Args:
        action_type_param: Kwarg name containing action type (default: "action_type")
        threshold: Debt level at which blocking occurs

    Example:
        class Agent:
            def __init__(self):
                self.debt_ledger = EpistemicDebtLedger()

            @debt_enforced()
            def execute_action(self, action_type: str, **kwargs) -> None:
                # Blocked if debt >= 2.0 and action_type not in calibration set
                ...

    Raises:
        DebtViolation: If action blocked due to high debt
    """

    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Get debt level
            debt_ledger = getattr(self, "debt_ledger", None)
            if debt_ledger is None:
                # No debt tracking, allow action
                return method(self, *args, **kwargs)

            debt = getattr(debt_ledger, "total_debt", 0.0)

            # Get action type from kwargs or first positional arg
            action_type = kwargs.get(action_type_param)
            if action_type is None and args:
                action_type = str(args[0])
            if action_type is None:
                action_type = "unknown"

            # Check threshold
            check_debt_threshold(debt, action_type, threshold)

            return method(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def compute_cost_multiplier(
    debt: float,
    base_cost: float,
    reference_cost: float = 100.0,
    global_sensitivity: float = 0.02,
    cost_sensitivity: float = 0.10,
) -> float:
    """Compute cost inflation multiplier based on debt level.

    Higher debt makes actions more expensive (measured in resources/time).
    More expensive assays are penalized more heavily.

    Args:
        debt: Current epistemic debt in bits
        base_cost: Base cost of the action (e.g., in dollars)
        reference_cost: Reference cost for normalization (default: $100)
        global_sensitivity: Per-bit global cost increase (default: 2%)
        cost_sensitivity: Per-bit cost-proportional increase (default: 10%)

    Returns:
        Cost multiplier (>= 1.0)

    Example:
        - debt=1.0, base_cost=$20: multiplier ≈ 1.04 (4% increase)
        - debt=1.0, base_cost=$200: multiplier ≈ 1.22 (22% increase)
    """
    if debt <= 0:
        return 1.0

    cost_ratio = base_cost / reference_cost
    multiplier = 1.0 + global_sensitivity * debt + cost_sensitivity * cost_ratio * debt

    return max(1.0, multiplier)
