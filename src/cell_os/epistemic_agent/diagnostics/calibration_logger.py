"""
Agent 3: Calibration Diagnostic Logger

Pure instrumentation for mechanism posterior calibration tracking.
Emits JSONL diagnostics to track ECE over time.

Philosophy:
- Non-blocking (never raises exceptions)
- No policy coupling
- Pure side effects (logging only)
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from cell_os.hardware.mechanism_posterior_v2 import (
    MechanismCalibrationTracker,
    Mechanism
)

logger = logging.getLogger(__name__)


# Agent 3: Global tracker (singleton pattern for simplicity)
# In production, this could be per-run or per-session
_global_tracker: Optional[MechanismCalibrationTracker] = None


def get_global_tracker() -> MechanismCalibrationTracker:
    """
    Get or create the global calibration tracker.

    Agent 3: Singleton for simplicity. Could be enhanced to per-run tracking.
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MechanismCalibrationTracker(min_samples_for_stability=30)
    return _global_tracker


def reset_global_tracker() -> None:
    """Reset the global tracker (e.g., between runs)."""
    global _global_tracker
    _global_tracker = None


def record_classification(
    predicted: Mechanism,
    true_mechanism: Mechanism,
    posterior: dict,
    silent_on_error: bool = True
) -> None:
    """
    Record a mechanism classification for calibration tracking.

    Args:
        predicted: Predicted mechanism (argmax of posterior)
        true_mechanism: Ground truth mechanism
        posterior: Posterior distribution (dict or MechanismPosterior.probabilities)
        silent_on_error: If True, log errors but don't raise

    Agent 3: Call this on EVERY classification, no filtering.
    """
    try:
        tracker = get_global_tracker()
        tracker.record(
            predicted=predicted,
            true_mechanism=true_mechanism,
            posterior=posterior
        )
    except Exception as e:
        if silent_on_error:
            logger.warning(f"Failed to record calibration event: {e}")
        else:
            raise


def emit_calibration_diagnostic(
    output_file: Path,
    force_emit: bool = False
) -> Optional[dict]:
    """
    Emit calibration diagnostic to JSONL.

    Args:
        output_file: Path to diagnostics.jsonl
        force_emit: If True, emit even if unstable (for debugging)

    Returns:
        Diagnostic event dict (or None if not emitted)

    Agent 3: Non-blocking. Never raises exceptions.
    """
    try:
        tracker = get_global_tracker()
        stats = tracker.get_statistics()

        # Don't emit if no data
        if stats["n_samples"] == 0:
            return None

        # Don't emit if unstable (unless forced)
        if not force_emit and not stats["is_stable"]:
            logger.debug(
                f"Calibration diagnostic not emitted: "
                f"n_samples={stats['n_samples']} < {tracker.min_samples_for_stability}"
            )
            return None

        # Build diagnostic event
        event = {
            "event": "mechanism_calibration",
            "ece": stats["ece"],
            "n_samples": stats["n_samples"],
            "n_bins": 10,
            "mean_confidence": stats["mean_confidence"],
            "accuracy": stats["accuracy"],
            "unstable": not stats["is_stable"],
            "timestamp": datetime.now().isoformat(),
        }

        # Write to JSONL
        with open(output_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        logger.info(
            f"Calibration diagnostic emitted: "
            f"ECE={stats['ece']:.3f}, n={stats['n_samples']}, "
            f"accuracy={stats['accuracy']:.2%}"
        )

        return event

    except Exception as e:
        logger.error(f"Failed to emit calibration diagnostic: {e}")
        return None


# Agent 3: Alert threshold
ECE_ALERT_THRESHOLD = 0.15


def check_and_emit_alert(
    output_file: Path,
    force_check: bool = False
) -> Optional[dict]:
    """
    Check if calibration alert should be emitted.

    Alert conditions:
    - ECE > 0.15 (threshold)
    - n_samples >= min_samples_for_stability (stable)

    Args:
        output_file: Path to diagnostics.jsonl
        force_check: If True, check even if unstable

    Returns:
        Alert event dict (or None if no alert)

    Agent 3: Non-blocking. Never raises exceptions.
    """
    try:
        tracker = get_global_tracker()
        ece, is_stable = tracker.compute_ece()

        # Skip if not enough data
        if tracker.events == 0:
            return None

        # Skip if unstable (unless forced)
        if not force_check and not is_stable:
            return None

        # Check threshold
        if ece <= ECE_ALERT_THRESHOLD:
            return None

        # Emit alert
        alert = {
            "event": "mechanism_calibration_alert",
            "ece": ece,
            "threshold": ECE_ALERT_THRESHOLD,
            "n_samples": len(tracker.events),
            "is_stable": is_stable,
            "message": "Mechanism posteriors appear miscalibrated",
            "timestamp": datetime.now().isoformat(),
        }

        with open(output_file, "a") as f:
            f.write(json.dumps(alert) + "\n")

        logger.warning(
            f"⚠️  CALIBRATION ALERT: ECE={ece:.3f} > {ECE_ALERT_THRESHOLD:.3f}. "
            f"Mechanism posteriors may be overconfident or underconfident."
        )

        return alert

    except Exception as e:
        logger.error(f"Failed to check calibration alert: {e}")
        return None
