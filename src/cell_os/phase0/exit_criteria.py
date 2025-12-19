from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import math
import statistics

from cell_os.phase0.exceptions import Phase0GateFailure


# -------------------------
# Minimal run summary schema
# -------------------------

@dataclass(frozen=True)
class SentinelObs:
    """
    One observation for a sentinel well.

    metric_name: e.g. "LDH", "CP_PC1", "nuc_area"
    value: numeric measurement
    """
    plate_id: str
    well_pos: str
    metric_name: str
    value: float


@dataclass(frozen=True)
class EdgeObs:
    """
    Observation for an edge-vs-center comparison.

    region: "edge" or "center"
    """
    plate_id: str
    well_pos: str
    metric_name: str
    region: str
    value: float


@dataclass(frozen=True)
class PositiveControlObs:
    """
    Observation for positive control effect checks.

    control_name: e.g. "CCCP_mid" or "tunicamycin_mid"
    baseline_name: e.g. "vehicle"
    """
    metric_name: str
    control_name: str
    baseline_name: str
    control_value: float
    baseline_value: float


@dataclass(frozen=True)
class RunSummary:
    sentinels: Sequence[SentinelObs]
    edge_effects: Sequence[EdgeObs]
    positive_controls: Sequence[PositiveControlObs]
    measurement_replicates: Mapping[str, Sequence[float]]
    # measurement_replicates maps metric_name -> replicate values for CV


# -------------------------
# Helper math
# -------------------------

def _is_finite(x: float) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))


def _cv(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if _is_finite(v)]
    if len(vals) < 2:
        return float("nan")
    m = statistics.mean(vals)
    if m == 0:
        return float("inf")
    sd = statistics.pstdev(vals)
    return abs(sd / m)


def _group_by(items: Iterable, key_fn):
    out: Dict[str, List] = {}
    for it in items:
        k = key_fn(it)
        out.setdefault(k, []).append(it)
    return out


# -------------------------
# Exit criteria
# -------------------------

def assert_sentinel_drift_below(
    threshold_cv: float,
    run: RunSummary,
    *,
    min_plates: int = 2,
    metrics: Optional[Sequence[str]] = None,
) -> None:
    """
    Criterion #1: Sentinel stability.

    For each metric, compute CV of plate means across plates.
    Gate fails if any metric CV >= threshold_cv.

    This targets plate-to-plate drift, not within-plate noise.
    """
    if threshold_cv <= 0:
        raise ValueError("threshold_cv must be > 0")

    sentinels = list(run.sentinels)
    if metrics is not None:
        metrics_set = set(metrics)
        sentinels = [s for s in sentinels if s.metric_name in metrics_set]

    if not sentinels:
        raise Phase0GateFailure(
            criterion="sentinel_stability",
            measured=float("nan"),
            threshold=threshold_cv,
            message="No sentinel observations provided",
            details={"min_plates": min_plates, "metrics": metrics},
        )

    # group by metric then by plate
    by_metric = _group_by(sentinels, lambda s: s.metric_name)
    failures = []

    for metric, obs in by_metric.items():
        by_plate = _group_by(obs, lambda s: s.plate_id)
        if len(by_plate) < min_plates:
            raise Phase0GateFailure(
                criterion="sentinel_stability",
                measured=float("nan"),
                threshold=threshold_cv,
                message=f"Not enough plates for sentinel drift calculation for metric={metric}",
                details={"metric": metric, "plates_found": sorted(by_plate.keys()), "min_plates": min_plates},
            )

        plate_means = []
        for plate_id, plate_obs in by_plate.items():
            vals = [o.value for o in plate_obs if _is_finite(o.value)]
            if not vals:
                continue
            plate_means.append(statistics.mean(vals))

        measured = _cv(plate_means)
        if not _is_finite(measured):
            raise Phase0GateFailure(
                criterion="sentinel_stability",
                measured=measured,
                threshold=threshold_cv,
                message=f"Sentinel drift CV undefined for metric={metric}",
                details={"metric": metric, "plate_means": plate_means},
            )
        if measured >= threshold_cv:
            failures.append((metric, measured, plate_means))

    if failures:
        worst = max(failures, key=lambda t: t[1])
        metric, measured, plate_means = worst
        raise Phase0GateFailure(
            criterion="sentinel_stability",
            measured=measured,
            threshold=threshold_cv,
            message=f"Sentinel drift too high for metric={metric}: CV={measured:.4f} >= {threshold_cv:.4f}",
            details={"metric": metric, "plate_means": plate_means, "all_failures": failures},
        )


def assert_measurement_cv_below(
    threshold_cv: float,
    run: RunSummary,
    *,
    metrics: Optional[Sequence[str]] = None,
    min_reps: int = 3,
) -> None:
    """
    Criterion #2: Measurement precision (within-condition replicate noise).
    Gate fails if any metric replicate CV >= threshold_cv.
    """
    if threshold_cv <= 0:
        raise ValueError("threshold_cv must be > 0")

    reps = dict(run.measurement_replicates)
    if metrics is not None:
        metrics_set = set(metrics)
        reps = {k: v for k, v in reps.items() if k in metrics_set}

    if not reps:
        raise Phase0GateFailure(
            criterion="measurement_precision",
            measured=float("nan"),
            threshold=threshold_cv,
            message="No measurement replicates provided",
            details={"min_reps": min_reps, "metrics": metrics},
        )

    failures = []
    for metric, values in reps.items():
        vals = [float(v) for v in values if _is_finite(v)]
        if len(vals) < min_reps:
            raise Phase0GateFailure(
                criterion="measurement_precision",
                measured=float("nan"),
                threshold=threshold_cv,
                message=f"Not enough replicates for metric={metric}",
                details={"metric": metric, "rep_count": len(vals), "min_reps": min_reps},
            )

        measured = _cv(vals)
        if not _is_finite(measured):
            raise Phase0GateFailure(
                criterion="measurement_precision",
                measured=measured,
                threshold=threshold_cv,
                message=f"Replicate CV undefined for metric={metric}",
                details={"metric": metric, "values": vals},
            )

        if measured >= threshold_cv:
            failures.append((metric, measured, vals))

    if failures:
        worst = max(failures, key=lambda t: t[1])
        metric, measured, vals = worst
        raise Phase0GateFailure(
            criterion="measurement_precision",
            measured=measured,
            threshold=threshold_cv,
            message=f"Measurement CV too high for metric={metric}: CV={measured:.4f} >= {threshold_cv:.4f}",
            details={"metric": metric, "values": vals, "all_failures": failures},
        )


def assert_plate_edge_effect_detectable_or_absent(
    run: RunSummary,
    *,
    max_abs_edge_center_delta: float,
    metrics: Optional[Sequence[str]] = None,
    min_obs_per_region: int = 8,
) -> None:
    """
    Criterion #3: Plate edge effects are either controlled (small) or at least measurable.

    Here we enforce "small": for each metric and plate, compare mean(edge) vs mean(center).
    Fail if abs(delta) > max_abs_edge_center_delta for any plate+metric.

    Later you can add a "detectable" mode if you purposely spike an edge sentinel pattern.
    """
    if max_abs_edge_center_delta < 0:
        raise ValueError("max_abs_edge_center_delta must be >= 0")

    obs = list(run.edge_effects)
    if metrics is not None:
        metrics_set = set(metrics)
        obs = [o for o in obs if o.metric_name in metrics_set]

    if not obs:
        raise Phase0GateFailure(
            criterion="plate_edge_effects",
            measured=float("nan"),
            threshold=max_abs_edge_center_delta,
            message="No edge effect observations provided",
            details={"min_obs_per_region": min_obs_per_region, "metrics": metrics},
        )

    by_plate_metric = _group_by(obs, lambda o: f"{o.plate_id}::{o.metric_name}")
    failures = []

    for key, items in by_plate_metric.items():
        plate_id, metric = key.split("::", 1)
        edge_vals = [o.value for o in items if o.region == "edge" and _is_finite(o.value)]
        center_vals = [o.value for o in items if o.region == "center" and _is_finite(o.value)]

        if len(edge_vals) < min_obs_per_region or len(center_vals) < min_obs_per_region:
            raise Phase0GateFailure(
                criterion="plate_edge_effects",
                measured=float("nan"),
                threshold=max_abs_edge_center_delta,
                message=f"Not enough edge/center observations for plate={plate_id} metric={metric}",
                details={
                    "plate_id": plate_id,
                    "metric": metric,
                    "edge_n": len(edge_vals),
                    "center_n": len(center_vals),
                    "min_obs_per_region": min_obs_per_region,
                },
            )

        delta = statistics.mean(edge_vals) - statistics.mean(center_vals)
        measured = abs(delta)

        if measured > max_abs_edge_center_delta:
            failures.append((plate_id, metric, measured, delta))

    if failures:
        worst = max(failures, key=lambda t: t[2])
        plate_id, metric, measured, delta = worst
        raise Phase0GateFailure(
            criterion="plate_edge_effects",
            measured=measured,
            threshold=max_abs_edge_center_delta,
            message=f"Edge effect too large on plate={plate_id} metric={metric}: abs(delta)={measured:.4f} > {max_abs_edge_center_delta:.4f}",
            details={"plate_id": plate_id, "metric": metric, "delta": delta, "all_failures": failures},
        )


def assert_effect_recovery_for_known_controls(
    run: RunSummary,
    *,
    min_abs_effect: float,
    metrics: Optional[Sequence[str]] = None,
) -> None:
    """
    Criterion #4: Positive control validation.
    Fail if any positive control does not separate from baseline by at least min_abs_effect.

    This is intentionally crude. It forces you to maintain at least one known-good signal.
    """
    if min_abs_effect <= 0:
        raise ValueError("min_abs_effect must be > 0")

    obs = list(run.positive_controls)
    if metrics is not None:
        metrics_set = set(metrics)
        obs = [o for o in obs if o.metric_name in metrics_set]

    if not obs:
        raise Phase0GateFailure(
            criterion="positive_controls",
            measured=float("nan"),
            threshold=min_abs_effect,
            message="No positive control observations provided",
            details={"min_abs_effect": min_abs_effect, "metrics": metrics},
        )

    failures = []
    for o in obs:
        effect = abs(float(o.control_value) - float(o.baseline_value))
        if effect < min_abs_effect:
            failures.append((o.metric_name, o.control_name, o.baseline_name, effect))

    if failures:
        worst = min(failures, key=lambda t: t[3])
        metric, ctrl, base, effect = worst
        raise Phase0GateFailure(
            criterion="positive_controls",
            measured=effect,
            threshold=min_abs_effect,
            message=f"Positive control effect too small for metric={metric} control={ctrl} vs baseline={base}: {effect:.4f} < {min_abs_effect:.4f}",
            details={"worst": worst, "all_failures": failures},
        )


def assert_phase0_exit(
    run: RunSummary,
    *,
    sentinel_drift_cv: float,
    measurement_cv: float,
    max_edge_center_delta: float,
    min_positive_effect: float,
    metrics: Optional[Sequence[str]] = None,
) -> None:
    """
    Convenience: run all Phase 0 gates.
    """
    assert_sentinel_drift_below(sentinel_drift_cv, run, metrics=metrics)
    assert_measurement_cv_below(measurement_cv, run, metrics=metrics)
    assert_plate_edge_effect_detectable_or_absent(run, max_abs_edge_center_delta=max_edge_center_delta, metrics=metrics)
    assert_effect_recovery_for_known_controls(run, min_abs_effect=min_positive_effect, metrics=metrics)
