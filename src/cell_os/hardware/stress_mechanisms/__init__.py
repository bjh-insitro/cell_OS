"""
Stress mechanism simulators for BiologicalVirtualMachine.

Each stress mechanism updates latent stress states and proposes death hazards
based on compound exposure, nutrient levels, and confluence.
"""

from .base import StressMechanism
from .er_stress import ERStressMechanism
from .mito_dysfunction import MitoDysfunctionMechanism
from .transport_dysfunction import TransportDysfunctionMechanism
from .nutrient_depletion import NutrientDepletionMechanism
from .mitotic_catastrophe import MitoticCatastropheMechanism

__all__ = [
    'StressMechanism',
    'ERStressMechanism',
    'MitoDysfunctionMechanism',
    'TransportDysfunctionMechanism',
    'NutrientDepletionMechanism',
    'MitoticCatastropheMechanism',
]
