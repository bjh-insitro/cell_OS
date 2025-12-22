"""
Epistemic Agent Diagnostics

Agent 3: Calibration tracking and diagnostic logging.
"""

from .calibration_logger import (
    get_global_tracker,
    reset_global_tracker,
    record_classification,
    emit_calibration_diagnostic,
    check_and_emit_alert,
    ECE_ALERT_THRESHOLD,
)

__all__ = [
    "get_global_tracker",
    "reset_global_tracker",
    "record_classification",
    "emit_calibration_diagnostic",
    "check_and_emit_alert",
    "ECE_ALERT_THRESHOLD",
]
