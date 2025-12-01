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

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False


class ParametricOps(ProtocolOps):
    """Unified interface for all parametric operations.
    Inherits from all specialized operation classes.
    """
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        
        # Initialize parent classes
        # ProtocolOps initializes LiquidHandlingOps, IncubationOps, etc.
        ProtocolOps.__init__(self, vessel_lib, pricing_inv)
        
        # Resolver for protocol selection (optional)
        self.resolver = None

        # Initialize specialized operation handlers
        # We import here to avoid circular imports if any
        from .operations.cell_culture import CellCultureOps
        from .operations.transfection import TransfectionOps
        from .operations.vessel_ops import VesselOps
        from .operations.harvest_freeze import HarvestFreezeOps
        from .operations.qc_ops import QCOps
        
        # Pass self as liquid_handler to give access to inherited methods (op_aspirate, etc.)
        self.cell_culture_ops = CellCultureOps(vessel_lib, pricing_inv, self)
        self.transfection_ops = TransfectionOps(vessel_lib, pricing_inv, self)
        self.vessel_ops = VesselOps(vessel_lib, pricing_inv, self)
        self.harvest_freeze_ops = HarvestFreezeOps(vessel_lib, pricing_inv, self)
        self.qc_ops = QCOps(vessel_lib, pricing_inv, self)
    
    def get_cell_line_defaults(self, cell_line: str):
        """Get default parameters for a cell line from database."""
        if CELL_LINE_DB_AVAILABLE:
            return get_cell_line_profile(cell_line)
        return {}

    def op_centrifuge(self, vessel_id: str, duration_min: float, speed_rpm: float = 1000, temp_c: float = 25.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0, name: str = None):
        """Centrifuge a vessel."""
        return self.vessel_ops.centrifuge(vessel_id, duration_min, speed_rpm, temp_c, material_cost_usd, instrument_cost_usd, name)

    # --- TIER 1: CORE CELL CULTURE OPERATIONS ---
    
    def op_thaw(self, vessel_id: str, cell_line: str = None, skip_coating: bool = False):
        """Thaw cells from cryovial into culture vessel."""
        return self.cell_culture_ops.thaw(vessel_id, cell_line, skip_coating)

    def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase", cell_line: str = None):
        """Passage cells (dissociate, split, re-plate)."""
        return self.cell_culture_ops.passage(vessel_id, ratio, dissociation_method, cell_line)

    def op_feed(self, vessel_id: str, media: str = None, cell_line: str = None, supplements: List[str] = None, name: str = None):
        """Feed cells (media change)."""
        return self.cell_culture_ops.feed(vessel_id, media, cell_line, supplements, name)

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive"):
        """Transduce cells with viral vector."""
        return self.transfection_ops.transduce(vessel_id, virus_vol_ul, method)

    def op_coat(self, vessel_id: str, agents: List[str] = None, num_vessels: int = 1):
        """Coat vessel(s) with ECM proteins."""
        return self.vessel_ops.coat(vessel_id, agents, num_vessels)

    def op_transfect(self, vessel_id: str, method: str = "pei"):
        """Transfect cells with plasmid DNA."""
        return self.transfection_ops.transfect(vessel_id, method)
    
    def op_seed_plate(self, vessel_id: str, num_wells: int, volume_per_well_ml: float = 2.0, cell_line: str = None, name: str = None):
        """Seed cells into plate wells with detailed sub-steps."""
        return self.cell_culture_ops.seed_plate(vessel_id, num_wells, volume_per_well_ml, cell_line, name)

    def op_seed(self, vessel_id: str, num_cells: int, cell_line: str = None, name: str = None):
        """Seed cells into a vessel (generic/flask)."""
        return self.cell_culture_ops.seed(vessel_id, num_cells, cell_line, name)
    
    def op_harvest(self, vessel_id: str, dissociation_method: str = None, cell_line: str = None, name: str = None):
        """Harvest cells for freezing or analysis."""
        return self.harvest_freeze_ops.harvest(vessel_id, dissociation_method, cell_line, name)

    def op_freeze(self, num_vials: int = 10, freezing_media: str = "cryostor_cs10", cell_line: str = None):
        """Freeze cells into cryovials."""
        return self.harvest_freeze_ops.freeze(num_vials, freezing_media, cell_line)

    # --- TIER 2: QC OPERATIONS ---
    
    def op_mycoplasma_test(self, sample_id: str, method: str = "pcr"):
        """Test for mycoplasma contamination."""
        return self.qc_ops.mycoplasma_test(sample_id, method)
    
    def op_sterility_test(self, sample_id: str, duration_days: int = 7):
        """Test for bacterial/fungal contamination."""
        return self.qc_ops.sterility_test(sample_id, duration_days)
    
    def op_karyotype(self, sample_id: str, method: str = "g_banding"):
        """Karyotype analysis for chromosomal abnormalities."""
        return self.qc_ops.karyotype(sample_id, method)
