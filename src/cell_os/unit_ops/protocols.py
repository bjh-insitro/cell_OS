"""
Protocol Operations.
Base class for complex laboratory protocols.
Most specific protocols have been moved to domain-specific operation handlers in `src/cell_os/unit_ops/operations/`.
This class remains as a potential integration point for future composite protocols.
"""

from typing import List, Optional
from .base import UnitOp, VesselLibrary
from .liquid_handling import LiquidHandlingOps # Needed for init
from .incubation import IncubationOps         # Needed for init
from .imaging import ImagingOps               # Needed for init
from .analysis import AnalysisOps             # Needed for init

# Import cell line database for conditional logic (copied from parametric.py)
try:
    from cell_os.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False


class ProtocolOps(LiquidHandlingOps, IncubationOps, ImagingOps, AnalysisOps):
    """
    A collection of complex, composite Unit Operations that define standard
    laboratory protocols.
    
    NOTE: Core protocols (Thaw, Passage, etc.) have been moved to Mixins.
    This class inherits from low-level functional classes and can be used
    for future composite protocols that don't fit into the specific mixins.
    """
    
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        # Note: self.ops is needed here to call op_count, op_dispense inside self
        # but the actual ops engine (ParametricOps) will handle the inheritance chain.

        # Initialize parent classes (Crucial for inheriting granular methods like op_incubate)
        LiquidHandlingOps.__init__(self, vessel_lib, pricing_inv)
        IncubationOps.__init__(self, vessel_lib, pricing_inv)
        ImagingOps.__init__(self, vessel_lib, pricing_inv)
        AnalysisOps.__init__(self, vessel_lib, pricing_inv)