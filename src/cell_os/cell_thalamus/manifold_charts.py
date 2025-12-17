"""
Manifold Charts: First-class coordinate systems with capability gating

A "chart" is a coordinate system + assumptions + allowed operations.
12h is a mechanism chart (archetype geometry preserved).
48h is an endpoint chart (archetypes converge to shared fate phenotypes).

You cannot request "stress-axis boundary at 48h" because the chart doesn't allow it.
This is not a warning. This is architectural impossibility.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from enum import Enum
import numpy as np


class BoundaryType(Enum):
    """Types of boundaries that can be detected."""
    DEATH = "death"  # Alive vs dead (allowed on all charts if viability available)
    MECHANISM_AXIS = "mechanism_axis"  # ER vs mito vs proteostasis vs oxidative (requires geometry preservation)
    ENDPOINT_STATE = "endpoint_state"  # Senescence vs apoptosis vs autophagy (requires specific markers)


class ChartStatus(Enum):
    """Health status of a manifold chart."""
    PASS = "pass"  # All integration tests passed
    CONDITIONAL = "conditional"  # Some capabilities available, others blocked
    FAIL = "fail"  # No boundaries allowed


@dataclass
class ChartHealth:
    """Health metrics for a manifold chart."""
    geometry_preservation_median: float
    geometry_preservation_min: float
    sentinel_max_drift_normalized: float  # Max sentinel residual drift / within_scatter
    vehicle_drift_median_normalized: float  # Median vehicle drift / within_scatter
    n_batches: int

    def passes_mechanism_boundaries(self) -> bool:
        """Check if chart is healthy enough for mechanism-axis boundaries."""
        return (
            self.geometry_preservation_median > 0.90 and
            self.geometry_preservation_min > 0.80 and
            self.sentinel_max_drift_normalized < 0.8
        )

    def passes_death_boundaries(self) -> bool:
        """Check if chart is healthy enough for death boundaries."""
        # Death boundaries are more lenient - just need vehicle centering to work
        return self.vehicle_drift_median_normalized < 1.0


@dataclass
class ManifoldChart:
    """
    A coordinate system for morphology space.

    Charts define:
    - Which timepoint(s) are included
    - Whether archetype geometry is preserved (mechanism vs endpoint space)
    - Which boundary types are allowed
    - PCA basis (fitted per-chart, not shared)
    - Sentinel specs for batch normalization
    """
    chart_id: str
    timepoint_h: float
    status: ChartStatus
    health: ChartHealth
    allowed_boundary_types: List[BoundaryType]

    # Architectural notes
    chart_type: Literal["mechanism", "endpoint"]
    notes: str

    # Fitted components (set after initialization)
    pca_basis: Optional[np.ndarray] = None
    pca_explained_variance: Optional[np.ndarray] = None
    global_vehicle_mu: Optional[np.ndarray] = None
    global_sentinel_mus: Optional[Dict[str, np.ndarray]] = None

    def allows_boundary_type(self, boundary_type: BoundaryType) -> bool:
        """Check if this chart supports the requested boundary type."""
        return boundary_type in self.allowed_boundary_types

    def refuse_message(self, boundary_type: BoundaryType) -> Dict:
        """Generate structured error for disallowed boundary type."""
        return {
            "error": {
                "code": "CHART_CAPABILITY_VIOLATION",
                "message": f"{boundary_type.value} boundary not allowed on {self.chart_id}",
                "details": {
                    "chart_id": self.chart_id,
                    "timepoint_h": self.timepoint_h,
                    "chart_type": self.chart_type,
                    "requested_boundary": boundary_type.value,
                    "allowed_boundaries": [bt.value for bt in self.allowed_boundary_types],
                    "health": {
                        "geometry_preservation": self.health.geometry_preservation_median,
                        "sentinel_max_drift": self.health.sentinel_max_drift_normalized,
                        "status": self.status.value
                    },
                    "recommendation": self._get_recommendation(boundary_type)
                }
            }
        }

    def _get_recommendation(self, boundary_type: BoundaryType) -> str:
        """Generate actionable recommendation for rejected boundary request."""
        if boundary_type == BoundaryType.MECHANISM_AXIS:
            if self.timepoint_h >= 36:
                return (
                    f"Mechanism boundaries require geometry_preservation >= 0.90. "
                    f"This chart has {self.health.geometry_preservation_median:.3f}. "
                    f"Late timepoints ({self.timepoint_h}h) show archetype convergence (ER → apoptosis looks like Mito → apoptosis). "
                    f"Options: (1) Use earlier timepoint (12h or 24h), (2) Run dose-pair diagnostic to confirm saturation, "
                    f"(3) Accept {self.timepoint_h}h as endpoint chart and use death boundaries only."
                )
            else:
                return (
                    f"Mechanism boundaries require geometry_preservation >= 0.90. "
                    f"This chart has {self.health.geometry_preservation_median:.3f}. "
                    f"Run anchor tightening cycle (increase sentinel replicates) to improve geometry preservation."
                )
        elif boundary_type == BoundaryType.DEATH:
            return (
                f"Death boundaries require vehicle_drift < 1.0× within-scatter. "
                f"This chart has {self.health.vehicle_drift_median_normalized:.2f}×. "
                f"Run anchor tightening cycle to stabilize vehicle baseline."
            )
        else:
            return "Boundary type not supported on any chart yet."


def assess_chart_health(
    batch_diagnostics: List[Dict],
    integration_test: Dict,
    within_scatter: float
) -> ChartHealth:
    """
    Compute health metrics from integration test results.

    Args:
        batch_diagnostics: Per-batch diagnostics from analyze_boundaries
        integration_test: Integration test results
        within_scatter: RMS of vehicle well variances

    Returns:
        ChartHealth object
    """
    # Extract geometry preservation values
    geometry_values = []
    for batch in batch_diagnostics:
        if batch.get('geometry_preservation') is not None:
            geometry_values.append(batch['geometry_preservation'])

    geom_median = float(np.median(geometry_values)) if geometry_values else 0.0
    geom_min = float(np.min(geometry_values)) if geometry_values else 0.0

    # Extract sentinel drifts
    sentinel_drifts = []
    for batch in batch_diagnostics:
        for sentinel_name, drift in batch.get('sentinel_residual_drifts', {}).items():
            sentinel_drifts.append(drift / within_scatter)

    sentinel_max_drift = float(np.max(sentinel_drifts)) if sentinel_drifts else 0.0

    # Extract vehicle drifts
    vehicle_drifts = []
    for batch in batch_diagnostics:
        if batch.get('vehicle_drift_magnitude') is not None:
            vehicle_drifts.append(batch['vehicle_drift_magnitude'] / within_scatter)

    vehicle_drift_median = float(np.median(vehicle_drifts)) if vehicle_drifts else 0.0

    return ChartHealth(
        geometry_preservation_median=geom_median,
        geometry_preservation_min=geom_min,
        sentinel_max_drift_normalized=sentinel_max_drift,
        vehicle_drift_median_normalized=vehicle_drift_median,
        n_batches=len(batch_diagnostics)
    )


def create_chart_from_integration_test(
    timepoint_h: float,
    batch_diagnostics: List[Dict],
    integration_test: Dict,
    within_scatter: float
) -> ManifoldChart:
    """
    Create a ManifoldChart from integration test results.

    Automatically determines:
    - Chart status (pass/conditional/fail)
    - Allowed boundary types
    - Chart type (mechanism vs endpoint)
    """
    health = assess_chart_health(batch_diagnostics, integration_test, within_scatter)

    # Determine allowed boundary types based on health
    allowed_boundaries = []
    if health.passes_death_boundaries():
        allowed_boundaries.append(BoundaryType.DEATH)

    if health.passes_mechanism_boundaries():
        allowed_boundaries.append(BoundaryType.MECHANISM_AXIS)

    # Determine chart status
    if health.passes_mechanism_boundaries():
        status = ChartStatus.PASS
        chart_type = "mechanism"
        notes = "Archetype geometry preserved. Mechanism boundaries allowed."
    elif health.passes_death_boundaries():
        status = ChartStatus.CONDITIONAL
        # Late timepoints are endpoint charts
        if timepoint_h >= 36:
            chart_type = "endpoint"
            notes = (
                f"Archetype geometry collapsed (median {health.geometry_preservation_median:.3f}). "
                f"Likely biological convergence at late timepoint ({timepoint_h}h). "
                f"Only death boundaries allowed."
            )
        else:
            chart_type = "mechanism"
            notes = (
                f"Geometry below threshold (median {health.geometry_preservation_median:.3f}). "
                f"Run anchor tightening cycle. Only death boundaries allowed for now."
            )
    else:
        status = ChartStatus.FAIL
        chart_type = "endpoint"  # Default for failed charts
        notes = (
            f"Vehicle drift too high ({health.vehicle_drift_median_normalized:.2f}× within-scatter). "
            f"No boundaries allowed. Run anchor tightening cycle."
        )

    chart_id = f"T{int(timepoint_h):02d}h_{chart_type}_v1"

    return ManifoldChart(
        chart_id=chart_id,
        timepoint_h=timepoint_h,
        status=status,
        health=health,
        allowed_boundary_types=allowed_boundaries,
        chart_type=chart_type,
        notes=notes
    )


def compute_dose_pair_separation(
    low_dose_wells: List,
    high_dose_wells: List,
    embeddings_low: np.ndarray,
    embeddings_high: np.ndarray
) -> float:
    """
    Compute dose-pair separation metric Q_s.

    Q_s = ||mu_high - mu_low|| / sqrt(mean(tr(Sigma_low), tr(Sigma_high)))

    Interpretation:
    - Q >> 1: Doses are separated, not saturated
    - Q ~ 1: Borderline
    - Q << 1: Saturated or converged

    Args:
        low_dose_wells: Wells at low dose
        high_dose_wells: Wells at high dose
        embeddings_low: Embeddings for low dose wells
        embeddings_high: Embeddings for high dose wells

    Returns:
        Q_s metric
    """
    if len(embeddings_low) < 2 or len(embeddings_high) < 2:
        return 0.0

    # Compute means
    mu_low = embeddings_low.mean(axis=0)
    mu_high = embeddings_high.mean(axis=0)

    # Compute covariance traces
    cov_low = np.cov(embeddings_low.T)
    cov_high = np.cov(embeddings_high.T)

    trace_low = np.trace(cov_low) if cov_low.ndim == 2 else cov_low
    trace_high = np.trace(cov_high) if cov_high.ndim == 2 else cov_high

    # Compute separation metric
    distance = np.linalg.norm(mu_high - mu_low)
    mean_scatter = np.sqrt((trace_low + trace_high) / 2.0)

    if mean_scatter == 0:
        return 0.0

    Q = distance / mean_scatter

    return float(Q)


def compute_archetype_fanout(
    sentinel_mus: Dict[str, np.ndarray]
) -> float:
    """
    Compute archetype fan-out metric F(t).

    F(t) = mean pairwise distance between sentinel archetypes

    If F(48h) << F(12h), archetypes are converging (biological convergence).
    If only one archetype collapses while others remain spread, that archetype is nonlinear at late time.

    Args:
        sentinel_mus: Dict mapping sentinel name -> mean embedding

    Returns:
        F(t) metric
    """
    if len(sentinel_mus) < 2:
        return 0.0

    # Compute pairwise distances
    sentinel_names = list(sentinel_mus.keys())
    distances = []

    for i in range(len(sentinel_names)):
        for j in range(i + 1, len(sentinel_names)):
            mu_i = sentinel_mus[sentinel_names[i]]
            mu_j = sentinel_mus[sentinel_names[j]]
            dist = np.linalg.norm(mu_i - mu_j)
            distances.append(dist)

    return float(np.mean(distances)) if distances else 0.0
