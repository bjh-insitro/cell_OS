"""
Death accounting conservation contract.

The core invariant is:
    viable + Σ(all tracked death fields) = 1.0 ± DEATH_EPS

This is the most critical invariant in the simulation - violations indicate
either a bug or an exploit attempt. No silent corrections allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, TypeVar

from cell_os.hardware.constants import DEATH_EPS, TRACKED_DEATH_FIELDS

if TYPE_CHECKING:
    from cell_os.hardware.biological_virtual import Vessel

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ConservationViolation(Exception):
    """Raised when death accounting fails conservation law.

    Contains forensic evidence for debugging:
    - vessel_id: Which vessel violated
    - expected: Should be 1.0
    - actual: What we computed
    - details: Field-by-field breakdown
    """

    vessel_id: str
    expected: float
    actual: float
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        msg = (
            f"Conservation violated in {self.vessel_id}: "
            f"expected {self.expected:.9f}, got {self.actual:.9f}\n"
            f"Details: viability={self.details.get('viability', 'N/A')}, "
            f"death_total={self.details.get('death_total', 'N/A')}"
        )
        super().__init__(msg)


def assert_conservation(
    vessel: Vessel,
    tolerance: float = DEATH_EPS * 10,
) -> None:
    """Check death accounting invariant.

    Raises ConservationViolation on failure.

    Args:
        vessel: The vessel to check
        tolerance: Maximum allowed deviation from 1.0 (default: 10 * DEATH_EPS)

    The contract: viable + death_compound + death_starvation + ... = 1.0
    """
    death_total = sum(
        getattr(vessel, f, 0.0) for f in TRACKED_DEATH_FIELDS
    )
    viable = getattr(vessel, "viability", 1.0)
    accounting_sum = viable + death_total

    if abs(accounting_sum - 1.0) > tolerance:
        raise ConservationViolation(
            vessel_id=getattr(vessel, "well_id", "unknown"),
            expected=1.0,
            actual=accounting_sum,
            details={
                "viability": viable,
                "death_total": death_total,
                "tolerance": tolerance,
                "fields": {
                    f: getattr(vessel, f, 0.0) for f in TRACKED_DEATH_FIELDS
                },
            },
        )


def conserved_death(method: F) -> F:
    """Decorator to verify conservation after method execution.

    Use on methods that modify vessel state (step, apply_treatment, etc.).
    Checks all vessels after the method returns.

    Example:
        class BiologicalVirtualMachine:
            @conserved_death
            def step(self, dt: float) -> None:
                # Conservation checked after each step
                ...

    Raises:
        ConservationViolation: If any vessel violates conservation
    """

    @wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = method(self, *args, **kwargs)

        # Check all vessels
        vessels = getattr(self, "vessels", [])
        for vessel in vessels:
            assert_conservation(vessel)

        return result

    return wrapper  # type: ignore[return-value]


def check_monotonicity(
    vessel: Vessel,
    prev_deaths: Dict[str, float],
    tolerance: float = DEATH_EPS,
) -> None:
    """Check that death fields are monotone non-decreasing.

    Death can only accumulate, never decrease. This is a secondary invariant
    that helps catch subtle bugs.

    Args:
        vessel: Current vessel state
        prev_deaths: Previous death field values
        tolerance: Maximum allowed decrease (numerical noise)

    Raises:
        ValueError: If any death field decreased
    """
    for field_name in TRACKED_DEATH_FIELDS:
        current = getattr(vessel, field_name, 0.0)
        previous = prev_deaths.get(field_name, 0.0)

        if current < previous - tolerance:
            raise ValueError(
                f"Monotonicity violated: {field_name} decreased "
                f"from {previous:.9f} to {current:.9f}"
            )
