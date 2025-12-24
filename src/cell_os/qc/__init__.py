"""
Quality control utilities for cell_OS.

This module provides QC checks and diagnostics for experimental data.
"""

from .spatial_diagnostics import (
    compute_morans_i,
    check_spatial_autocorrelation,
    extract_channel_values,
)

__all__ = [
    "compute_morans_i",
    "check_spatial_autocorrelation",
    "extract_channel_values",
]
