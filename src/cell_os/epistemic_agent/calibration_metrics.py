"""
Calibration metrics computation from observations.

Extracts QC-relevant metrics from calibration cycles and computes a single
"cleanliness" score that measures instrument quality.

Design principle: Cleanliness is not about biology, it's about the ruler.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class CalibrationMetrics:
    """QC metrics extracted from calibration observation."""
    morans_i: Optional[float] = None  # Spatial autocorrelation (lower is better)
    nuclei_cv: Optional[float] = None  # Nuclei count CV (lower is better)
    segmentation_quality: Optional[float] = None  # Segmentation quality score (higher is better)
    edge_failure_rate: Optional[float] = None  # Fraction of edge wells failed
    valid_well_fraction: Optional[float] = None  # Fraction of wells passed QC
    cleanliness_score: float = 0.5  # Overall cleanliness [0, 1] (1 = perfect)


def extract_calibration_metrics_from_observation(observation) -> CalibrationMetrics:
    """
    Extract QC metrics from calibration observation.

    Calibration observations should contain only controls (DMSO), so we're
    measuring instrument quality, not biological response.

    Args:
        observation: Observation object from calibration cycle

    Returns:
        CalibrationMetrics with QC scores
    """
    # Initialize metrics
    metrics = CalibrationMetrics()

    # Extract from QC flags (best effort parsing)
    # TODO: Make this more structured when QC metrics are standardized
    if hasattr(observation, 'qc_flags') and observation.qc_flags:
        for flag in observation.qc_flags:
            # Parse Moran's I
            if "Moran's I" in flag or "morans_i" in flag.lower():
                try:
                    # Try to extract float from flag string
                    parts = flag.split('=')
                    if len(parts) > 1:
                        value_str = parts[1].split()[0].rstrip(',)')
                        metrics.morans_i = float(value_str)
                except (ValueError, IndexError):
                    pass

            # Parse nuclei CV
            if "nuclei_cv" in flag.lower() or "CV" in flag:
                try:
                    parts = flag.split('=')
                    if len(parts) > 1:
                        value_str = parts[1].split()[0].rstrip(',)')
                        metrics.nuclei_cv = float(value_str)
                except (ValueError, IndexError):
                    pass

            # Parse segmentation quality
            if "segmentation" in flag.lower() or "quality" in flag.lower():
                try:
                    parts = flag.split('=')
                    if len(parts) > 1:
                        value_str = parts[1].split()[0].rstrip(',)')
                        metrics.segmentation_quality = float(value_str)
                except (ValueError, IndexError):
                    pass

    # Extract from conditions if available
    if hasattr(observation, 'conditions'):
        # Compute mean CV across conditions
        cvs = [c.cv for c in observation.conditions if hasattr(c, 'cv')]
        if cvs:
            metrics.nuclei_cv = sum(cvs) / len(cvs)

        # Compute valid well fraction
        n_total = sum(c.n_wells for c in observation.conditions if hasattr(c, 'n_wells'))
        n_failed = sum(getattr(c, 'n_failed', 0) for c in observation.conditions)
        if n_total > 0:
            metrics.valid_well_fraction = (n_total - n_failed) / n_total

        # Compute edge failure rate (if position_tag available)
        edge_wells = [c for c in observation.conditions if hasattr(c, 'position_tag') and c.position_tag == 'edge']
        if edge_wells:
            n_edge_total = sum(c.n_wells for c in edge_wells if hasattr(c, 'n_wells'))
            n_edge_failed = sum(getattr(c, 'n_failed', 0) for c in edge_wells)
            if n_edge_total > 0:
                metrics.edge_failure_rate = n_edge_failed / n_edge_total

    # Compute overall cleanliness score
    metrics.cleanliness_score = compute_cleanliness_score(metrics)

    return metrics


def compute_cleanliness_score(metrics: CalibrationMetrics) -> float:
    """
    Compute single cleanliness score [0, 1] from QC metrics.

    Perfect calibration (cleanliness = 1.0):
    - Moran's I < 0.10 (no spatial autocorrelation)
    - Nuclei CV < 0.15 (low variability)
    - Segmentation quality > 0.85 (high quality)
    - Valid well fraction > 0.95 (few failures)

    Poor calibration (cleanliness = 0.0):
    - Moran's I > 0.30
    - Nuclei CV > 0.30
    - Segmentation quality < 0.60
    - Valid well fraction < 0.70

    Args:
        metrics: CalibrationMetrics with extracted values

    Returns:
        Cleanliness score [0, 1]
    """
    cleanliness = 1.0

    # Component 1: Spatial autocorrelation (Moran's I)
    if metrics.morans_i is not None:
        if metrics.morans_i <= 0.10:
            # Perfect
            pass
        elif metrics.morans_i <= 0.15:
            # Good (slight penalty)
            cleanliness -= 0.1
        elif metrics.morans_i <= 0.20:
            # Acceptable (moderate penalty)
            cleanliness -= 0.2
        else:
            # Poor (large penalty)
            penalty = (metrics.morans_i - 0.20) * 2.0
            cleanliness -= min(0.4, penalty)

    # Component 2: Nuclei CV
    if metrics.nuclei_cv is not None:
        if metrics.nuclei_cv <= 0.15:
            # Perfect
            pass
        elif metrics.nuclei_cv <= 0.20:
            # Good
            cleanliness -= 0.05
        elif metrics.nuclei_cv <= 0.25:
            # Acceptable
            cleanliness -= 0.15
        else:
            # Poor
            penalty = (metrics.nuclei_cv - 0.25) * 1.5
            cleanliness -= min(0.3, penalty)

    # Component 3: Segmentation quality
    if metrics.segmentation_quality is not None:
        if metrics.segmentation_quality >= 0.85:
            # Perfect
            pass
        elif metrics.segmentation_quality >= 0.80:
            # Good
            cleanliness -= 0.05
        elif metrics.segmentation_quality >= 0.70:
            # Acceptable
            cleanliness -= 0.15
        else:
            # Poor
            penalty = (0.70 - metrics.segmentation_quality) * 1.0
            cleanliness -= min(0.25, penalty)

    # Component 4: Valid well fraction
    if metrics.valid_well_fraction is not None:
        if metrics.valid_well_fraction >= 0.95:
            # Perfect
            pass
        elif metrics.valid_well_fraction >= 0.90:
            # Good
            cleanliness -= 0.05
        elif metrics.valid_well_fraction >= 0.80:
            # Acceptable
            cleanliness -= 0.10
        else:
            # Poor
            penalty = (0.80 - metrics.valid_well_fraction) * 0.5
            cleanliness -= min(0.15, penalty)

    # Clamp to [0, 1]
    cleanliness = max(0.0, min(1.0, cleanliness))

    return cleanliness


def calibration_metrics_to_dict(metrics: CalibrationMetrics) -> Dict[str, Any]:
    """
    Convert CalibrationMetrics to dict for belief updates and logging.

    Args:
        metrics: CalibrationMetrics object

    Returns:
        Dict with keys matching apply_calibration_result() expectations
    """
    return {
        "morans_i": metrics.morans_i if metrics.morans_i is not None else 0.10,
        "nuclei_cv": metrics.nuclei_cv if metrics.nuclei_cv is not None else 0.15,
        "segmentation_quality": metrics.segmentation_quality if metrics.segmentation_quality is not None else 0.85,
        "edge_failure_rate": metrics.edge_failure_rate if metrics.edge_failure_rate is not None else 0.0,
        "valid_well_fraction": metrics.valid_well_fraction if metrics.valid_well_fraction is not None else 1.0,
        "cleanliness_score": metrics.cleanliness_score,
    }
