"""
Instrument Health Reward: Multi-objective QC optimization.

Teaches the agent to treat measurement quality as a first-class objective,
preventing the pathology where optimal epistemic gain destroys instrument reliability.

Design principles:
1. Observables-only: uses nuclei_qc fields, not ground truth
2. Multi-objective: tracked separately, not collapsed into epistemic term
3. Bounded: can't dominate discovery forever, but provides steering signal
4. Failure-aware: triggers mitigation when thresholds violated

This is the "don't gouge your own eyes out" layer.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class InstrumentHealthMetrics:
    """Per-cycle instrument health summary."""
    mean_segmentation_quality: float
    mean_nuclei_cv: float
    min_segmentation_quality: float
    max_nuclei_cv: float
    n_wells_measured: int
    n_qc_failures: int  # Wells below quality threshold
    health_score: float  # Composite [0, 1]
    health_reward: float  # Reward component


def compute_instrument_health_reward(
    observations: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    thresholds: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Compute instrument health reward from observation nuclei_qc fields.

    This is a multi-objective term that should be tracked separately from
    epistemic gain. The agent should optimize *both*, not collapse them.

    Args:
        observations: List of observation dicts with nuclei_qc fields
        weights: Optional weight dict with keys:
            - quality_weight: reward for high segmentation_quality (default 1.0)
            - cv_penalty: penalty for high nuclei_cv (default 0.5)
            - failure_penalty: hard penalty for missing/invalid qc (default 5.0)
        thresholds: Optional threshold dict with keys:
            - min_quality: segmentation_quality threshold (default 0.6)
            - max_cv: nuclei_cv threshold (default 0.25)

    Returns:
        Dict with:
            - health_metrics: InstrumentHealthMetrics
            - health_reward: float (total reward component)
            - qc_failures: list of well IDs that failed QC
            - mitigation_triggered: bool
    """
    # Default weights
    if weights is None:
        weights = {
            'quality_weight': 1.0,
            'cv_penalty': 0.5,
            'failure_penalty': 5.0,
        }

    # Default thresholds
    if thresholds is None:
        thresholds = {
            'min_quality': 0.6,  # Below this = low quality
            'max_cv': 0.25,  # Above this = too noisy
        }

    # Edge case: no observations
    if len(observations) == 0:
        health_metrics = InstrumentHealthMetrics(
            mean_segmentation_quality=0.0,
            mean_nuclei_cv=0.0,
            min_segmentation_quality=0.0,
            max_nuclei_cv=0.0,
            n_wells_measured=0,
            n_qc_failures=0,
            health_score=0.0,
            health_reward=0.0,
        )
        return {
            'health_metrics': health_metrics,
            'health_reward': 0.0,
            'qc_failures': [],
            'mitigation_triggered': False,
        }

    # Extract nuclei_qc from observations
    qc_data = []
    qc_failures = []
    missing_qc_count = 0

    for obs in observations:
        well_id = obs.get('well_id', 'unknown')

        # Check if nuclei_qc exists
        if 'nuclei_qc' not in obs:
            missing_qc_count += 1
            qc_failures.append(well_id)
            continue

        nuclei_qc = obs['nuclei_qc']

        # Validate fields
        if 'segmentation_quality' not in nuclei_qc or 'nuclei_cv' not in nuclei_qc:
            missing_qc_count += 1
            qc_failures.append(well_id)
            continue

        seg_quality = float(nuclei_qc['segmentation_quality'])
        nuclei_cv = float(nuclei_qc['nuclei_cv'])

        qc_data.append({
            'well_id': well_id,
            'segmentation_quality': seg_quality,
            'nuclei_cv': nuclei_cv,
        })

        # Check thresholds
        if seg_quality < thresholds['min_quality'] or nuclei_cv > thresholds['max_cv']:
            qc_failures.append(well_id)

    # If no valid QC data, return hard penalty
    if len(qc_data) == 0:
        health_metrics = InstrumentHealthMetrics(
            mean_segmentation_quality=0.0,
            mean_nuclei_cv=1.0,
            min_segmentation_quality=0.0,
            max_nuclei_cv=1.0,
            n_wells_measured=len(observations),
            n_qc_failures=len(observations),
            health_score=0.0,
            health_reward=-weights['failure_penalty'] * len(observations),
        )

        return {
            'health_metrics': health_metrics,
            'health_reward': health_metrics.health_reward,
            'qc_failures': qc_failures,
            'mitigation_triggered': True,  # Hard failure
        }

    # Compute aggregate metrics
    seg_qualities = [d['segmentation_quality'] for d in qc_data]
    nuclei_cvs = [d['nuclei_cv'] for d in qc_data]

    mean_seg_quality = float(np.mean(seg_qualities))
    mean_nuclei_cv = float(np.mean(nuclei_cvs))
    min_seg_quality = float(np.min(seg_qualities))
    max_nuclei_cv = float(np.max(nuclei_cvs))

    # Compute health score [0, 1]
    # High quality → high score, low CV → high score
    quality_component = mean_seg_quality  # Already in [0, 1]
    cv_component = 1.0 - np.clip(mean_nuclei_cv / thresholds['max_cv'], 0.0, 1.0)

    health_score = 0.6 * quality_component + 0.4 * cv_component
    health_score = float(np.clip(health_score, 0.0, 1.0))

    # Compute reward (bounded to avoid dominating epistemic term)
    # Reward for high quality
    quality_reward = weights['quality_weight'] * mean_seg_quality

    # Penalty for high CV (nonlinear: worse at extremes)
    cv_penalty = weights['cv_penalty'] * (mean_nuclei_cv / thresholds['max_cv'])

    # Hard penalty for missing QC
    missing_penalty = weights['failure_penalty'] * missing_qc_count

    # Total reward (bounded in [-10, +2] to avoid dominating)
    health_reward = quality_reward - cv_penalty - missing_penalty
    health_reward = float(np.clip(health_reward, -10.0, 2.0))

    # Determine if mitigation should trigger
    mitigation_triggered = (
        mean_seg_quality < thresholds['min_quality'] or
        mean_nuclei_cv > thresholds['max_cv'] or
        len(qc_failures) > len(observations) * 0.3  # >30% failure rate
    )

    health_metrics = InstrumentHealthMetrics(
        mean_segmentation_quality=mean_seg_quality,
        mean_nuclei_cv=mean_nuclei_cv,
        min_segmentation_quality=min_seg_quality,
        max_nuclei_cv=max_nuclei_cv,
        n_wells_measured=len(qc_data),
        n_qc_failures=len(qc_failures),
        health_score=health_score,
        health_reward=health_reward,
    )

    return {
        'health_metrics': health_metrics,
        'health_reward': health_reward,
        'qc_failures': qc_failures,
        'mitigation_triggered': mitigation_triggered,
    }


def suggest_qc_mitigation(
    health_metrics: InstrumentHealthMetrics,
    qc_failures: List[str],
    cycle: int
) -> Optional[Dict[str, Any]]:
    """
    Suggest mitigation action when QC thresholds violated.

    This generalizes spatial QC mitigation to all QC failure modes.

    Args:
        health_metrics: Instrument health summary
        qc_failures: List of well IDs that failed QC
        cycle: Current cycle number

    Returns:
        Mitigation suggestion dict or None if no action needed
    """
    if len(qc_failures) == 0:
        return None

    failure_rate = health_metrics.n_qc_failures / max(1, health_metrics.n_wells_measured)

    # Catastrophic failure (>50% wells failed)
    if failure_rate > 0.5:
        return {
            'action': 'replate_with_altered_layout',
            'reason': f'Catastrophic QC failure: {failure_rate*100:.0f}% wells failed',
            'severity': 'critical',
            'cycle': cycle,
            'details': {
                'failed_wells': qc_failures,
                'mean_quality': health_metrics.mean_segmentation_quality,
                'mean_cv': health_metrics.mean_nuclei_cv,
            }
        }

    # High failure rate (30-50%)
    if failure_rate > 0.3:
        return {
            'action': 'increase_replicates',
            'reason': f'High QC failure rate: {failure_rate*100:.0f}% wells failed',
            'severity': 'high',
            'cycle': cycle,
            'details': {
                'failed_wells': qc_failures,
                'replicate_multiplier': 1.5,  # Increase by 50%
            }
        }

    # Moderate failure (10-30%)
    if failure_rate > 0.1:
        # Check if failures are edge-concentrated
        edge_failures = sum(1 for w in qc_failures if _is_edge_well(w))
        edge_fraction = edge_failures / max(1, len(qc_failures))

        if edge_fraction > 0.6:
            return {
                'action': 'avoid_edge_wells',
                'reason': f'Edge-concentrated QC failures: {edge_fraction*100:.0f}% on edges',
                'severity': 'moderate',
                'cycle': cycle,
                'details': {
                    'edge_failures': edge_failures,
                    'total_failures': len(qc_failures),
                }
            }
        else:
            return {
                'action': 'adjust_seeding_density',
                'reason': f'Spatially distributed QC failures: {failure_rate*100:.0f}%',
                'severity': 'moderate',
                'cycle': cycle,
                'details': {
                    'target_confluence': 0.5,  # Move toward optimal
                }
            }

    # Low failure (5-10%): warn but don't force action
    if failure_rate > 0.05:
        return {
            'action': 'monitor',
            'reason': f'Elevated QC failure rate: {failure_rate*100:.0f}%',
            'severity': 'low',
            'cycle': cycle,
            'details': {
                'failed_wells': qc_failures,
            }
        }

    return None


def _is_edge_well(well_id: str, plate_format: int = 384) -> bool:
    """Detect if well is on plate edge (384-well format)."""
    import re
    match = re.search(r'([A-P])(\d{1,2})$', well_id)
    if not match:
        return False

    row = match.group(1)
    col = int(match.group(2))

    if plate_format == 384:
        return row in ['A', 'P'] or col in [1, 24]
    elif plate_format == 96:
        return row in ['A', 'H'] or col in [1, 12]
    return False


def log_instrument_health_summary(
    cycle: int,
    health_metrics: InstrumentHealthMetrics,
    mitigation: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format instrument health summary for logging.

    Args:
        cycle: Current cycle
        health_metrics: Health metrics
        mitigation: Optional mitigation suggestion

    Returns:
        Formatted summary string
    """
    lines = [
        f"=== Cycle {cycle}: Instrument Health ===",
        f"Health Score: {health_metrics.health_score:.3f}",
        f"Segmentation Quality: {health_metrics.mean_segmentation_quality:.3f} (min={health_metrics.min_segmentation_quality:.3f})",
        f"Nuclei CV: {health_metrics.mean_nuclei_cv:.3f} (max={health_metrics.max_nuclei_cv:.3f})",
        f"Wells Measured: {health_metrics.n_wells_measured}",
        f"QC Failures: {health_metrics.n_qc_failures}",
        f"Health Reward: {health_metrics.health_reward:+.2f}",
    ]

    if mitigation:
        lines.append(f"MITIGATION: {mitigation['action']} ({mitigation['severity']}) - {mitigation['reason']}")

    return "\n".join(lines)
