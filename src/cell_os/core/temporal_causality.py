"""
Temporal causality enforcement.

This module provides the temporal contract and validation for the entire system.
No observation may occur before its causal treatment.

TEMPORAL CONTRACT
-----------------

1. observation_time_h:
   - Represents the END of the observation window (point measurement)
   - Measured in hours since the universal time origin (t=0)
   - Must be >= 0 (no negative time)
   - Is the moment when the assay readout is captured

2. treatment_start_time_h:
   - Time when treatment is applied, in hours since t=0
   - Defaults to 0.0 (treatment at experiment start)
   - Must be >= 0 (no time travel)
   - Is the causal anchor: effects cannot precede this moment

3. Causality invariant:
   observation_time_h >= treatment_start_time_h

   This ensures observations cannot report on treatments that haven't happened yet.

4. Observation windows:
   - Current model: instantaneous point measurements (no window)
   - Future: could add observation_window_h for integration periods
   - If added, must validate: observation_time_h - window >= treatment_start_time_h

ENFORCEMENT STRATEGY
--------------------

Validation happens at:
1. Well construction (fail fast on invalid specs)
2. Experiment execution (guard against runtime violations)
3. Observation creation (final defense)

All violations raise TemporalCausalityError with enough context to debug.
No warnings, no silent corrections - fail hard.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .experiment import Well
    from .observation import RawWellResult


class TemporalCausalityError(Exception):
    """Raised when temporal causality is violated.

    Examples:
    - Observation time is negative
    - Observation occurs before treatment starts
    - Treatment start time is negative
    - Observation window overlaps treatment start (future)
    """
    pass


def validate_well_temporal_causality(well: "Well") -> None:
    """Validate that a well respects temporal causality.

    Checks:
    1. observation_time_h >= 0
    2. treatment_start_time_h >= 0
    3. observation_time_h >= treatment_start_time_h

    Args:
        well: Well to validate

    Raises:
        TemporalCausalityError: If any causality constraint is violated
    """
    # Check observation time is non-negative
    if well.observation_time_h < 0:
        raise TemporalCausalityError(
            f"Observation time cannot be negative. "
            f"Got observation_time_h={well.observation_time_h:.3f}h "
            f"for well with treatment={well.treatment.compound}"
        )

    # Check treatment start time is non-negative
    if well.treatment_start_time_h < 0:
        raise TemporalCausalityError(
            f"Treatment start time cannot be negative. "
            f"Got treatment_start_time_h={well.treatment_start_time_h:.3f}h "
            f"for well with treatment={well.treatment.compound}"
        )

    # Check causality: observation must not precede treatment
    if well.observation_time_h < well.treatment_start_time_h:
        raise TemporalCausalityError(
            f"Observation cannot occur before treatment. "
            f"Got observation_time_h={well.observation_time_h:.3f}h < "
            f"treatment_start_time_h={well.treatment_start_time_h:.3f}h "
            f"for well with treatment={well.treatment.compound}"
        )


def validate_raw_well_result_temporal_causality(result: "RawWellResult") -> None:
    """Validate that a raw well result respects temporal causality.

    Checks:
    1. observation_time_h >= 0
    2. treatment_start_time_h >= 0 (if present in treatment)
    3. observation_time_h >= treatment_start_time_h (if present)

    Args:
        result: RawWellResult to validate

    Raises:
        TemporalCausalityError: If any causality constraint is violated
    """
    # Check observation time is non-negative
    if result.observation_time_h < 0:
        raise TemporalCausalityError(
            f"Observation time cannot be negative. "
            f"Got observation_time_h={result.observation_time_h:.3f}h "
            f"in result for {result.location}"
        )

    # If treatment has start time, validate causality
    if hasattr(result.treatment, 'treatment_start_time_h'):
        if result.treatment.treatment_start_time_h < 0:
            raise TemporalCausalityError(
                f"Treatment start time cannot be negative. "
                f"Got treatment_start_time_h={result.treatment.treatment_start_time_h:.3f}h "
                f"in result for {result.location}"
            )

        if result.observation_time_h < result.treatment.treatment_start_time_h:
            raise TemporalCausalityError(
                f"Observation cannot occur before treatment. "
                f"Got observation_time_h={result.observation_time_h:.3f}h < "
                f"treatment_start_time_h={result.treatment.treatment_start_time_h:.3f}h "
                f"in result for {result.location}"
            )
