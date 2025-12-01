"""
Parametric Operations.
Unifies all operation types (Liquid Handling, Protocols, Imaging, Analysis) 
into a single access interface.
"""

from typing import List, Optional
from .base import VesselLibrary
from .liquid_handling import LiquidHandlingOps
from .protocols import ProtocolOps
from .imaging import ImagingOps
from .analysis import AnalysisOps

# Import Mixins
from .culture_ops import CultureOpsMixin
from .cloning_ops import CloningOpsMixin
from .analysis_ops import AnalysisOpsMixin

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False


class ParametricOps(CultureOpsMixin, CloningOpsMixin, AnalysisOpsMixin, ProtocolOps):
    """Unified interface for all parametric operations.
    Inherits from all specialized operation classes.
    """
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        
        # Initialize parent classes
        # ProtocolOps initializes LiquidHandlingOps, IncubationOps, ImagingOps, AnalysisOps
        ProtocolOps.__init__(self, vessel_lib, pricing_inv)
        
        # Resolver for protocol selection (optional)
        self.resolver = None
    
    def get_cell_line_defaults(self, cell_line: str):
        """Get default parameters for a cell line from database."""
        if CELL_LINE_DB_AVAILABLE:
            return get_cell_line_profile(cell_line)
        return {}
