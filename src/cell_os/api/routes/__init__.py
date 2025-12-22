"""
API Routes for Cell Thalamus

Modular route organization by domain.
"""

from . import simulations
from . import designs
from . import results
from . import analysis
from . import catalog
from . import watcher
from . import plates
from . import epistemic

__all__ = [
    'simulations',
    'designs',
    'results',
    'analysis',
    'catalog',
    'watcher',
    'plates',
    'epistemic',
]
