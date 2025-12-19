"""
Phase 0: Infrastructure Validation

Phase 0 is not "exploratory work." It is a set of executable, numerical gates
that MUST pass before any biological conclusions can be drawn.

If Phase 0 doesn't end with hard criteria, it never ends. It just "feels done"
until it ruins Phase 1.

Exit criteria:
1. Sentinel stability: plate-to-plate drift < threshold
2. Measurement precision: within-condition replicate CV < threshold
3. Plate edge effects: controlled or at least measurable
4. Positive control validation: known signals must be detectable

See exit_criteria.py for the actual gates.
"""

from .exit_criteria import (
    RunSummary,
    SentinelObs,
    EdgeObs,
    PositiveControlObs,
    assert_sentinel_drift_below,
    assert_measurement_cv_below,
    assert_plate_edge_effect_detectable_or_absent,
    assert_effect_recovery_for_known_controls,
    assert_phase0_exit,
)
from .exceptions import Phase0ExitCriteriaFailed, Phase0GateFailure

__all__ = [
    "RunSummary",
    "SentinelObs",
    "EdgeObs",
    "PositiveControlObs",
    "assert_sentinel_drift_below",
    "assert_measurement_cv_below",
    "assert_plate_edge_effect_detectable_or_absent",
    "assert_effect_recovery_for_known_controls",
    "assert_phase0_exit",
    "Phase0ExitCriteriaFailed",
    "Phase0GateFailure",
]
