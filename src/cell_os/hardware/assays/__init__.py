"""
Assay simulators for BiologicalVirtualMachine.

Each assay is a read-only measurement function that observes vessel state
and returns synthetic data with realistic noise characteristics.
"""

from .base import AssaySimulator
from .cell_painting import CellPaintingAssay
from .viability import LDHViabilityAssay
from .scrna_seq import ScRNASeqAssay

__all__ = [
    'AssaySimulator',
    'CellPaintingAssay',
    'LDHViabilityAssay',
    'ScRNASeqAssay',
]
