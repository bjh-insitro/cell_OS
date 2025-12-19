"""
Phase 0 Distribution Sanity Gate

Enforces that simulator distributions haven't drifted across changes.
This is the covenant equivalent of "no silent changes to what 'good' means."

Usage:
    1. Run N seeds, collect summary stats (drift CV, replicate CV, edge rel, positive rel)
    2. Save baseline distribution snapshot (mean, std, p95)
    3. On future runs, compare against saved baseline
    4. Fail if any metric's p95 shifts by more than threshold (e.g., 10% relative)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import statistics

from .exceptions import Phase0GateFailure


@dataclass(frozen=True)
class DistributionSnapshot:
    """
    Statistical summary of Phase 0 metric distributions across multiple runs.

    Captures:
    - mean: Central tendency
    - std: Spread
    - p95: 95th percentile threshold (what we use for gates)
    - n_samples: Number of runs in this snapshot
    """
    metric_name: str
    gate: str  # "sentinel_drift", "measurement_cv", "edge_effect", "positive_control"
    mean: float
    std: float
    p95: float
    n_samples: int


def compute_distribution_snapshot(
    values: List[float],
    metric_name: str,
    gate: str,
) -> DistributionSnapshot:
    """
    Compute statistical snapshot from list of measurements.

    Args:
        values: List of measured values across multiple runs
        metric_name: Name of metric (e.g., "LDH")
        gate: Name of gate (e.g., "sentinel_drift")

    Returns:
        DistributionSnapshot with mean, std, p95, n_samples
    """
    if len(values) < 3:
        raise ValueError(f"Need at least 3 samples to compute distribution, got {len(values)}")

    sorted_vals = sorted(values)
    p95_idx = int(0.95 * len(sorted_vals))
    p95 = sorted_vals[p95_idx]

    return DistributionSnapshot(
        metric_name=metric_name,
        gate=gate,
        mean=statistics.mean(values),
        std=statistics.pstdev(values),
        p95=p95,
        n_samples=len(values),
    )


def assert_distribution_stability(
    current: DistributionSnapshot,
    baseline: DistributionSnapshot,
    max_p95_shift_rel: float = 0.10,  # 10% relative shift
) -> None:
    """
    Assert that current distribution hasn't drifted from baseline.

    Args:
        current: Current distribution snapshot
        baseline: Baseline distribution snapshot (from calibration)
        max_p95_shift_rel: Maximum allowed relative shift in p95 (e.g., 0.10 = 10%)

    Raises:
        Phase0GateFailure: If p95 shifts by more than threshold
    """
    if current.metric_name != baseline.metric_name or current.gate != baseline.gate:
        raise ValueError(
            f"Snapshot mismatch: current=({current.metric_name}, {current.gate}) "
            f"vs baseline=({baseline.metric_name}, {baseline.gate})"
        )

    if baseline.p95 == 0:
        # Can't compute relative shift if baseline is zero
        abs_shift = abs(current.p95 - baseline.p95)
        if abs_shift > max_p95_shift_rel:  # Treat as absolute in this case
            raise Phase0GateFailure(
                criterion="distribution_stability",
                measured=abs_shift,
                threshold=max_p95_shift_rel,
                message=(
                    f"Distribution p95 shifted for {current.metric_name} ({current.gate}): "
                    f"abs_shift={abs_shift:.4f} > {max_p95_shift_rel:.4f}"
                ),
                details={
                    "metric_name": current.metric_name,
                    "gate": current.gate,
                    "current_p95": current.p95,
                    "baseline_p95": baseline.p95,
                    "current_mean": current.mean,
                    "baseline_mean": baseline.mean,
                },
            )
    else:
        rel_shift = abs((current.p95 - baseline.p95) / baseline.p95)
        if rel_shift > max_p95_shift_rel:
            raise Phase0GateFailure(
                criterion="distribution_stability",
                measured=rel_shift,
                threshold=max_p95_shift_rel,
                message=(
                    f"Distribution p95 shifted for {current.metric_name} ({current.gate}): "
                    f"rel_shift={rel_shift:.4f} > {max_p95_shift_rel:.4f}"
                ),
                details={
                    "metric_name": current.metric_name,
                    "gate": current.gate,
                    "current_p95": current.p95,
                    "baseline_p95": baseline.p95,
                    "current_mean": current.mean,
                    "baseline_mean": baseline.mean,
                },
            )


# TODO: Implement calibration runner CLI
# python -m cell_os.phase0.calibrate --seeds 0-199 --out artifacts/phase0_calibration.json
# This should:
# 1. Run Phase 0 sims across N seeds
# 2. Collect distributions for each gate + metric
# 3. Compute DistributionSnapshot for each
# 4. Save to JSON with thresholds_fingerprint
# 5. Emit recommended thresholds (p95 values)
