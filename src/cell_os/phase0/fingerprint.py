"""
Phase 0 Thresholds Fingerprint

Stable identifier for threshold configuration + simulator version.
When someone says "Phase 0 used to pass," you can answer with a hash, not a story.
"""

import hashlib
import json
from typing import Dict, Any, Optional

from .config import Phase0Thresholds


def compute_thresholds_fingerprint(
    thresholds: Phase0Thresholds,
    simulator_version: Optional[str] = None,
    noise_model_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Compute stable fingerprint of Phase 0 threshold configuration.

    Args:
        thresholds: Phase0Thresholds configuration
        simulator_version: Version string or git commit of simulator
        noise_model_params: Noise model parameters if stored separately

    Returns:
        16-character hex hash identifying this threshold configuration

    Example:
        >>> from cell_os.phase0 import DEFAULT_PHASE0_THRESHOLDS
        >>> fingerprint = compute_thresholds_fingerprint(
        ...     DEFAULT_PHASE0_THRESHOLDS,
        ...     simulator_version="standalone_cell_thalamus_v1.0",
        ...     noise_model_params={"biological_cv": 0.15, "technical_cv": 0.02}
        ... )
        >>> fingerprint
        'a3f4c8d1e2b5a9c7'
    """
    canonical = {
        "sentinel_drift_cv": dict(sorted(thresholds.sentinel_drift_cv.items())),
        "measurement_cv": dict(sorted(thresholds.measurement_cv.items())),
        "edge_effect_rel": dict(sorted(thresholds.edge_effect_rel.items())),
        "positive_effect_rel": dict(sorted(thresholds.positive_effect_rel.items())),
        "simulator_version": simulator_version or "unknown",
        "noise_model_params": noise_model_params or {},
    }

    canonical_json = json.dumps(canonical, sort_keys=True)
    hash_bytes = hashlib.sha256(canonical_json.encode('utf-8')).digest()
    return hash_bytes.hex()[:16]


def verify_thresholds_fingerprint(
    thresholds: Phase0Thresholds,
    expected_fingerprint: str,
    simulator_version: Optional[str] = None,
    noise_model_params: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Verify that threshold configuration matches expected fingerprint.

    Returns:
        True if fingerprint matches, False otherwise
    """
    actual = compute_thresholds_fingerprint(thresholds, simulator_version, noise_model_params)
    return actual == expected_fingerprint
