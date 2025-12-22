"""
Boundary Detection Module

Phase 2: Boundary-aware acquisition for autonomous loop.

Architecture:
- types.py: Core dataclasses (WellRecord, SentinelSpec, BatchFrame)
- anchor_budgeter.py: Sentinel well allocation with spatial distribution
- boundary_model.py: Decision boundaries with batch normalization
- band_selector.py: High-uncertainty region selection
- acquisition_planner.py: Next experiment generation + utility functions

Usage:
    from cell_os.cell_thalamus.boundary_detection import (
        AnchorBudgeter,
        BoundaryModel,
        BoundaryBandSelector,
        AcquisitionPlanner,
        analyze_boundaries
    )
"""

from .types import (
    ConditionKey,
    WellRecord,
    SentinelSpec,
    BatchFrame,
)

from .anchor_budgeter import AnchorBudgeter
from .boundary_model import BoundaryModel
from .band_selector import BoundaryBandSelector

from .acquisition_planner import (
    AcquisitionPlanner,
    compute_integration_test_metrics,
    build_batch_frames,
    analyze_boundaries,
)

__all__ = [
    # Types
    'ConditionKey',
    'WellRecord',
    'SentinelSpec',
    'BatchFrame',
    # Classes
    'AnchorBudgeter',
    'BoundaryModel',
    'BoundaryBandSelector',
    'AcquisitionPlanner',
    # Utility functions
    'compute_integration_test_metrics',
    'build_batch_frames',
    'analyze_boundaries',
]
