"""
Assay simulators for BiologicalVirtualMachine.

Each assay is a read-only measurement function that observes vessel state
and returns synthetic data with realistic noise characteristics.
"""

from .base import AssaySimulator
from .cell_painting import CellPaintingAssay
from .scrna_seq import ScRNASeqAssay
from .supplemental_if import SupplementalIFAssay
from .viability import CytotoxAssay

# Backward compatibility alias
LDHViabilityAssay = CytotoxAssay

__all__ = [
    "AssaySimulator",
    "CellPaintingAssay",
    "CytotoxAssay",
    "LDHViabilityAssay",  # Backward compatibility
    "ScRNASeqAssay",
    "SupplementalIFAssay",
]
