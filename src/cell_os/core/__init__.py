"""
Core canonical types for cell_OS.

These types are the single source of truth for experimental semantics.
All legacy types (WellSpec, WellAssignment, etc.) must adapt to these.
"""

from .experiment import Well, Treatment, SpatialLocation, DesignSpec, Experiment
from .assay import AssayType
from .cell_painting_channel import CellPaintingChannel
from .decision import Decision, DecisionRationale
from .observation import RawWellResult, ConditionKey, Observation
from .capabilities import PlateGeometry, Capabilities, AllocationPolicy

__all__ = [
    'Well',
    'Treatment',
    'SpatialLocation',
    'DesignSpec',
    'Experiment',
    'AssayType',
    'CellPaintingChannel',
    'Decision',
    'DecisionRationale',
    'RawWellResult',
    'ConditionKey',
    'Observation',
    'PlateGeometry',
    'Capabilities',
    'AllocationPolicy',
]
