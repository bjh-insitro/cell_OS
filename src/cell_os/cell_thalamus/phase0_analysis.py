"""
Phase 0 Thalamus Analysis Functions.

Implements the core analyses from the Phase 0 Thalamus Analysis Plan:
1. Pathology exclusion gate (γ-H2AX)
2. Dose nomination (maximal-separation, non-collapse operating point)
3. Reproducibility assessment
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PathologyGateResult:
    """Result of pathology exclusion gate check."""

    status: str  # "PASS", "WARNING", "EXCLUDED"
    reason: str
    pct_exceeding_p95: float
    median_ratio: float
    vehicle_p95: float
    vehicle_median: float
    treated_median: float
    criteria_met: list[str]


def check_pathology_gate(
    treated_intensities: np.ndarray, vehicle_intensities: np.ndarray
) -> PathologyGateResult:
    """
    Check γ-H2AX pathology exclusion gate.

    From Phase 0 Thalamus Analysis Plan:
    - EXCLUDED if ≥60% of nuclei exceed vehicle P95, OR
    - EXCLUDED if ≥40% exceed P95 AND median is ≥3× vehicle

    Args:
        treated_intensities: Array of nuclear γ-H2AX intensities (treated)
        vehicle_intensities: Array of nuclear γ-H2AX intensities (vehicle)

    Returns:
        PathologyGateResult with status and metrics
    """
    vehicle_p95 = float(np.percentile(vehicle_intensities, 95))
    vehicle_median = float(np.median(vehicle_intensities))
    treated_median = float(np.median(treated_intensities))

    pct_exceeding = float(np.mean(treated_intensities > vehicle_p95))
    median_ratio = treated_median / max(vehicle_median, 1e-9)

    criteria_met = []

    if pct_exceeding >= 0.60:
        criteria_met.append("≥60% nuclei exceed vehicle P95")

    if pct_exceeding >= 0.40 and median_ratio >= 3.0:
        criteria_met.append("≥40% exceed P95 AND median ≥3× vehicle")

    if criteria_met:
        status = "EXCLUDED"
        reason = f"Saturated damage regime: {'; '.join(criteria_met)}"
    elif pct_exceeding >= 0.30 or median_ratio >= 2.0:
        status = "WARNING"
        reason = "Approaching pathology threshold"
    else:
        status = "PASS"
        reason = "Within acceptable damage range"

    return PathologyGateResult(
        status=status,
        reason=reason,
        pct_exceeding_p95=pct_exceeding,
        median_ratio=median_ratio,
        vehicle_p95=vehicle_p95,
        vehicle_median=vehicle_median,
        treated_median=treated_median,
        criteria_met=criteria_met,
    )


@dataclass
class DoseNominationResult:
    """Result of dose nomination analysis."""

    nominated_dose: str | None
    nominated_timepoint: str | None
    morphology_separation: float
    reproducibility_score: float
    viability_pct: float
    pathology_status: str
    decision_path: list[str]


def nominate_operating_point(
    dose_data: dict[str, dict[str, Any]], decision_order: list[str] = None
) -> DoseNominationResult:
    """
    Nominate optimal dose-timepoint operating point.

    Decision order (from Phase 0 plan):
    morphology separation → reproducibility → viability → pathology exclusion

    Args:
        dose_data: Dict mapping dose to metrics:
            - morphology_separation: Distance from vehicle in feature space
            - reproducibility_score: Cross-replicate agreement (0-1)
            - viability_pct: % viable cells
            - pathology_status: "PASS", "WARNING", or "EXCLUDED"
        decision_order: Custom decision order (default: plan order)

    Returns:
        DoseNominationResult with nominated point and reasoning
    """
    if decision_order is None:
        decision_order = ["morphology_separation", "reproducibility", "viability", "pathology"]

    # Filter out excluded doses
    valid_doses = {
        dose: data for dose, data in dose_data.items() if data.get("pathology_status") != "EXCLUDED"
    }

    if not valid_doses:
        return DoseNominationResult(
            nominated_dose=None,
            nominated_timepoint=None,
            morphology_separation=0.0,
            reproducibility_score=0.0,
            viability_pct=0.0,
            pathology_status="ALL_EXCLUDED",
            decision_path=["All doses excluded by pathology gate"],
        )

    decision_path = []

    # Sort by morphology separation (descending)
    sorted_doses = sorted(
        valid_doses.items(), key=lambda x: x[1].get("morphology_separation", 0), reverse=True
    )

    # Find maximum separation with acceptable reproducibility
    for dose, data in sorted_doses:
        separation = data.get("morphology_separation", 0)
        repro = data.get("reproducibility_score", 0)
        viability = data.get("viability_pct", 100)
        pathology = data.get("pathology_status", "PASS")

        # Check reproducibility threshold
        if repro < 0.7:
            decision_path.append(f"{dose}: Rejected (reproducibility {repro:.2f} < 0.7)")
            continue

        # Check viability hasn't collapsed
        if viability < 20:
            decision_path.append(f"{dose}: Rejected (viability {viability:.1f}% < 20%)")
            continue

        # This dose passes all criteria
        decision_path.append(f"{dose}: NOMINATED (separation={separation:.2f}, repro={repro:.2f})")

        return DoseNominationResult(
            nominated_dose=dose,
            nominated_timepoint=data.get("timepoint"),
            morphology_separation=separation,
            reproducibility_score=repro,
            viability_pct=viability,
            pathology_status=pathology,
            decision_path=decision_path,
        )

    # No dose met all criteria
    return DoseNominationResult(
        nominated_dose=None,
        nominated_timepoint=None,
        morphology_separation=0.0,
        reproducibility_score=0.0,
        viability_pct=0.0,
        pathology_status="NO_VALID_DOSE",
        decision_path=decision_path + ["No dose met all criteria"],
    )
