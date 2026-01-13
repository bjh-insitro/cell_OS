"""
Imaging module for dose-response imaging experiments.

This package contains:
- acquisition: Experiment planning and acquisition scoring
- cost: Imaging cost calculations
- goal: Imaging window goals and objectives
- loop: Dose-response imaging loop
"""

# Re-export main public API
from .goal import ImagingWindowGoal
from .cost import (
    ImagingCost,
    calculate_imaging_cost,
    calculate_batch_cost,
    get_cost_per_information_bit,
)
from .acquisition import (
    ExperimentPlan,
    ExperimentResult,
    compute_acquisition_score,
    propose_imaging_doses,
)
from .loop import (
    WorldModelLike,
    ExecutorLike,
    BatchPlan,
    ImagingDoseLoop,
)

__all__ = [
    # Goal
    'ImagingWindowGoal',
    # Cost
    'ImagingCost',
    'calculate_imaging_cost',
    'calculate_batch_cost',
    'get_cost_per_information_bit',
    # Acquisition
    'ExperimentPlan',
    'ExperimentResult',
    'compute_acquisition_score',
    'propose_imaging_doses',
    # Loop
    'WorldModelLike',
    'ExecutorLike',
    'BatchPlan',
    'ImagingDoseLoop',
]
