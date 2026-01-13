"""
Epistemic Agency: Agent that learns about its world from scratch.

The agent starts knowing:
- What knobs it can turn (cell line, compound, dose, time, assay, position)
- That experiments are noisy and cost wells
- That budget is finite

The agent does NOT know:
- IC50 values, optimal doses, or that "mid-dose is special"
- That edge effects exist (it may hypothesize and test)
- That death signatures converge at high dose
- That 12h is the "mechanism window"

It must discover all of this through experiments.

Submodules:
- control: High-level epistemic controller (debt tracking, penalties)
- debt: Epistemic debt ledger and information gain computation
- penalty: Penalty computation for posterior widening
- provisional: Provisional penalty tracking
- sandbagging: Sandbagging detection
- volatility: Entropy volatility and calibration stability tracking
"""

__version__ = "0.1.0"

# Re-export main public API from control module
from .control import (
    EpistemicController,
    EpistemicControllerConfig,
    EntropySource,
    MIN_CALIBRATION_COST_WELLS,
    measure_and_penalize,
)
from .debt import (
    EpistemicDebtLedger,
    compute_information_gain_bits,
)
from .penalty import (
    EpistemicPenaltyConfig,
    compute_full_epistemic_penalty,
    EpistemicPenaltyResult,
    compute_entropy_penalty,
    compute_planning_horizon_shrinkage,
)
from .provisional import ProvisionalPenaltyTracker
from .sandbagging import SandbaggingDetector, detect_sandbagging
from .volatility import EntropyVolatilityTracker, CalibrationStabilityTracker

__all__ = [
    # Control
    'EpistemicController',
    'EpistemicControllerConfig',
    'EntropySource',
    'MIN_CALIBRATION_COST_WELLS',
    'measure_and_penalize',
    # Debt
    'EpistemicDebtLedger',
    'compute_information_gain_bits',
    # Penalty
    'EpistemicPenaltyConfig',
    'compute_full_epistemic_penalty',
    'EpistemicPenaltyResult',
    'compute_entropy_penalty',
    'compute_planning_horizon_shrinkage',
    # Provisional
    'ProvisionalPenaltyTracker',
    # Sandbagging
    'SandbaggingDetector',
    'detect_sandbagging',
    # Volatility
    'EntropyVolatilityTracker',
    'CalibrationStabilityTracker',
]
