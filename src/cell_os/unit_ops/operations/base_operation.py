"""
Base class for specialized operations.
"""
from typing import Dict, Any, Optional
from ..base import VesselLibrary, UnitOp

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False

class BaseOperation:
    """Base class for all specialized operation handlers."""
    
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv, liquid_handler):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        self.lh = liquid_handler # Access to low-level ops (aspirate, dispense, incubate)
    
    def get_price(self, item_id: str) -> float:
        """Get cost of a single item from pricing."""
        if hasattr(self.inv, 'get_price'):
            return self.inv.get_price(item_id)
        # Fallback for dict-based inventory
        try:
            return self.inv["items"][item_id]["unit_price_usd"]
        except (KeyError, TypeError):
            return 0.0
            
    def get_cell_line_profile(self, cell_line: str):
        """Get profile for a cell line."""
        if CELL_LINE_DB_AVAILABLE:
            return get_cell_line_profile(cell_line)
        return None

    def calculate_costs_from_items(self, items: list) -> tuple[float, float]:
        """Calculate material and instrument costs from BOMItems."""
        material_cost = 0.0
        instrument_cost = 0.0
        
        for item in items:
            # Determine category based on resource ID or lookup
            # For now, assume everything is material unless it ends in '_usage'
            is_instrument = item.resource_id.endswith('_usage')
            
            cost = item.quantity * self.get_price(item.resource_id)
            
            if is_instrument:
                instrument_cost += cost
            else:
                material_cost += cost
                
        return material_cost, instrument_cost
