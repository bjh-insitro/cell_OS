"""
Realism Injection System

Architecture for adding coupled, low-level realities to the biological simulator.

Each injection module follows a consistent interface:
- State variables (what becomes first-class truth)
- Invariants (conservation-style rules)
- Hooks (where they plug into physics, ops, assay, pipeline)
- Exploit blocking (what agent cheats get killed)
- New pathologies (what reality punishes you with)

Design Philosophy:
- Realism comes from interfaces between subsystems
- Couplings matter more than individual knobs
- "What would a smart agent exploit that a real lab would punish?"
- If the agent starts losing, fix the world, not the reward
"""

from .base import InjectionState, Injection, InjectionContext
from .volume_evaporation import VolumeEvaporationInjection
from .coating_quality import CoatingQualityInjection
from .pipetting_variance import PipettingVarianceInjection
from .mixing_gradients import MixingGradientsInjection
from .measurement_backaction import MeasurementBackActionInjection
from .stress_memory import StressMemoryInjection
from .lumpy_time import LumpyTimeInjection
from .death_modes import DeathModesInjection
from .assay_deception import AssayDeceptionInjection
from .identifiability_limits import IdentifiabilityLimitsInjection
from .cursed_plate import CursedPlateInjection
from .segmentation_failure import SegmentationFailureInjection
from .plate_map_error import PlateMapErrorInjection

__all__ = [
    'InjectionState',
    'Injection',
    'InjectionContext',
    'VolumeEvaporationInjection',
    'CoatingQualityInjection',
    'PipettingVarianceInjection',
    'MixingGradientsInjection',
    'MeasurementBackActionInjection',
    'StressMemoryInjection',
    'LumpyTimeInjection',
    'DeathModesInjection',
    'AssayDeceptionInjection',
    'IdentifiabilityLimitsInjection',
    'CursedPlateInjection',
    'SegmentationFailureInjection',
    'PlateMapErrorInjection',
]
