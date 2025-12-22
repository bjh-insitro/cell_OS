"""
Boundary Detection for Autonomous Loop (Phase 2)

DEPRECATED: This file is now a compatibility shim.
Import from boundary_detection submodule instead:

    from cell_os.cell_thalamus.boundary_detection import (
        AnchorBudgeter,
        BoundaryModel,
        BoundaryBandSelector,
        AcquisitionPlanner
    )

The module has been refactored into:
- boundary_detection/types.py: Core dataclasses
- boundary_detection/anchor_budgeter.py: Sentinel allocation
- boundary_detection/boundary_model.py: Decision boundaries
- boundary_detection/band_selector.py: High-uncertainty selection
- boundary_detection/acquisition_planner.py: Experiment planning + utilities

Design principle: Boundaries are about DECISIONS, not clusters.
Nuisance is a first-class citizen, not an afterthought.
"""

# Re-export everything from submodule for backward compatibility
from .boundary_detection import (
    # Types
    ConditionKey,
    WellRecord,
    SentinelSpec,
    BatchFrame,
    # Classes
    AnchorBudgeter,
    BoundaryModel,
    BoundaryBandSelector,
    AcquisitionPlanner,
    # Utility functions
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
