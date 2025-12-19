"""
Phase 0 Exit Criteria Configuration

Thresholds are calibrated against the simulator's noise model (~2-3% CV).
These are NOT arbitrary. They are derived from:

1. Simulator's baked-in biological noise (15% CV)
2. Observed plate-to-plate drift in baseline runs
3. 95th percentile of "good" Phase 0 runs

DO NOT relax these thresholds without:
1. Updating the simulator's noise model first
2. Regenerating thresholds from distributions
3. Documenting why the change is necessary

SIMULATOR VERSION: standalone_cell_thalamus (commit: 7bc4ec2)
NOISE MODEL: biological_cv=0.15, technical_cv=0.02-0.03
CALIBRATION DATE: 2025-12-19
"""

from dataclasses import dataclass
from typing import Dict, Optional

# Baseline floor for positive control denominator
# Prevents division by near-zero when baseline is anomalous
BASELINE_FLOOR = {
    "LDH": 100.0,          # 1% of typical vehicle baseline (~2,500)
    "CP_PC1": 0.01,        # Normalized units, 1% of typical range
    "CP_PC2": 0.01,
    "CP_PC3": 0.01,
    "nuc_area": 10.0,      # Typical area in pixels
    "nuc_intensity": 1.0,  # Typical intensity units
    "_default": 1.0,       # Conservative default
}


@dataclass(frozen=True)
class Phase0Thresholds:
    """
    Metric-specific thresholds for Phase 0 exit criteria.

    All CV thresholds are relative (e.g., 0.025 = 2.5% CV).
    All effect thresholds are relative (e.g., 0.50 = 50% effect size).
    Edge effect thresholds are relative to center mean (e.g., 0.05 = 5% delta).
    """

    # Sentinel stability: CV of plate means across plates
    sentinel_drift_cv: Dict[str, float]

    # Measurement precision: CV of technical replicates
    measurement_cv: Dict[str, float]

    # Edge effects: relative delta from center mean
    edge_effect_rel: Dict[str, float]

    # Positive controls: relative effect size from baseline
    positive_effect_rel: Dict[str, float]


# Default Phase 0 thresholds calibrated against simulator
DEFAULT_PHASE0_THRESHOLDS = Phase0Thresholds(
    sentinel_drift_cv={
        "LDH": 0.025,          # 2.5% CV - stricter for scalar readout
        "CP_PC1": 0.030,       # 3.0% CV
        "CP_PC2": 0.030,
        "CP_PC3": 0.030,
        "nuc_area": 0.035,     # 3.5% CV - morphology is noisier
        "nuc_intensity": 0.035,
        "_default": 0.030,     # Default for any other metric
    },
    measurement_cv={
        "LDH": 0.035,          # 3.5% CV - technical replicate noise
        "CP_PC1": 0.045,       # 4.5% CV - CP features noisier than LDH
        "CP_PC2": 0.045,
        "CP_PC3": 0.045,
        "nuc_area": 0.050,     # 5.0% CV - morphology most variable
        "nuc_intensity": 0.050,
        "_default": 0.045,
    },
    edge_effect_rel={
        "LDH": 0.05,           # 5% relative delta from center mean
        "CP_PC1": 0.06,        # 6% - CP slightly more sensitive to spatial
        "CP_PC2": 0.06,
        "CP_PC3": 0.06,
        "nuc_area": 0.08,      # 8% - morphology very sensitive to edge
        "nuc_intensity": 0.08,
        "_default": 0.06,
    },
    positive_effect_rel={
        # Positive control must show strong effect to pass
        # For LDH: vehicle ~2,500, strong cytotoxic ~35,000 = 13x fold change
        # Threshold of 5.0 = 500% increase = 6x fold change minimum
        "LDH": 5.0,            # 500% effect (6x fold change)
        "CP_PC1": 0.30,        # 30% effect - morphology may shift less
        "CP_PC2": 0.30,
        "CP_PC3": 0.30,
        "nuc_area": 0.40,      # 40% effect
        "nuc_intensity": 0.40,
        "_default": 0.50,      # 50% effect for unknown metrics
    },
)


def get_threshold(
    metric_name: str,
    threshold_dict: Dict[str, float],
    strict: bool = False,
) -> float:
    """
    Get threshold for a specific metric, falling back to _default if not found.

    Args:
        metric_name: Name of the metric (e.g., "LDH", "CP_PC1")
        threshold_dict: Dict mapping metric names to thresholds
        strict: If True, raise ValueError for unknown metrics instead of using _default

    Returns:
        Threshold value for the metric

    Raises:
        ValueError: If strict=True and metric not explicitly listed
    """
    if metric_name in threshold_dict:
        return threshold_dict[metric_name]

    if strict and metric_name != "_default":
        raise ValueError(
            f"Unknown metric '{metric_name}' and strict mode enabled. "
            f"Add explicit threshold for this metric or disable strict mode."
        )

    return threshold_dict.get("_default", 0.05)


# Convenience: extract per-gate defaults
def get_sentinel_drift_cv(metric_name: str) -> float:
    return get_threshold(metric_name, DEFAULT_PHASE0_THRESHOLDS.sentinel_drift_cv)


def get_measurement_cv(metric_name: str) -> float:
    return get_threshold(metric_name, DEFAULT_PHASE0_THRESHOLDS.measurement_cv)


def get_edge_effect_rel(metric_name: str) -> float:
    return get_threshold(metric_name, DEFAULT_PHASE0_THRESHOLDS.edge_effect_rel)


def get_positive_effect_rel(metric_name: str) -> float:
    return get_threshold(metric_name, DEFAULT_PHASE0_THRESHOLDS.positive_effect_rel)


def get_baseline_floor(metric_name: str) -> float:
    """
    Get denominator floor for positive control calculations.
    Prevents explosion when baseline is near zero.
    """
    return BASELINE_FLOOR.get(metric_name, BASELINE_FLOOR["_default"])
