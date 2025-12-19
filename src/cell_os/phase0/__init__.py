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
from .config import (
    Phase0Thresholds,
    DEFAULT_PHASE0_THRESHOLDS,
    BASELINE_FLOOR,
    get_threshold,
    get_sentinel_drift_cv,
    get_measurement_cv,
    get_edge_effect_rel,
    get_positive_effect_rel,
    get_baseline_floor,
)
from .fingerprint import (
    compute_thresholds_fingerprint,
    verify_thresholds_fingerprint,
)
from .distribution import (
    DistributionSnapshot,
    compute_distribution_snapshot,
    assert_distribution_stability,
)

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
    "Phase0Thresholds",
    "DEFAULT_PHASE0_THRESHOLDS",
    "BASELINE_FLOOR",
    "get_threshold",
    "get_sentinel_drift_cv",
    "get_measurement_cv",
    "get_edge_effect_rel",
    "get_positive_effect_rel",
    "get_baseline_floor",
    "compute_thresholds_fingerprint",
    "verify_thresholds_fingerprint",
    "DistributionSnapshot",
    "compute_distribution_snapshot",
    "assert_distribution_stability",
]
