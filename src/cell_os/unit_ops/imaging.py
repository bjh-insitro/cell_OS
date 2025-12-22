"""
Imaging operations.
"""

from typing import List, Optional, Tuple
from .base import UnitOp, VesselLibrary
from cell_os.inventory import BOMItem
import cell_os.cellpaint_panels as cp

class ImagingOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def get_price(self, item_id: str) -> float:
        """Get cost of a single item from pricing."""
        if hasattr(self.inv, 'get_price'):
            return self.inv.get_price(item_id)
        # Fallback for dict-based inventory
        try:
            return self.inv["items"][item_id]["unit_price_usd"]
        except (KeyError, TypeError):
            return 0.0

    def calculate_costs_from_items(self, items: List[BOMItem]) -> Tuple[float, float]:
        """Calculate material and instrument costs from BOM items."""
        material_cost = 0.0
        instrument_cost = 0.0
        
        for item in items:
            unit_cost = self.get_price(item.resource_id)
            total_item_cost = unit_cost * item.quantity
            
            # Heuristic to separate material vs instrument
            # This is a simplification. Ideally Resource definition has a type.
            if "_usage" in item.resource_id or "compute" in item.resource_id:
                instrument_cost += total_item_cost
            else:
                material_cost += total_item_cost
                
        return material_cost, instrument_cost

    def op_imaging(self, vessel_id: str, magnification: int = 20, channels: int = 5, fields: int = 9) -> UnitOp:
        v = self.vessels.get(vessel_id)
        items = []
        
        # Calculate imaging time
        # Assume 1 second per field per channel + 5 sec overhead per well
        time_per_well_sec = (fields * channels * 1.0) + 5.0
        
        # Scale by number of wells (approximate based on vessel type)
        num_wells = 1
        if "96" in vessel_id: num_wells = 96
        elif "384" in vessel_id: num_wells = 384
        elif "6" in vessel_id: num_wells = 6
        
        total_time_min = (time_per_well_sec * num_wells) / 60.0
        
        # Instrument cost ($50/hr for high content imager)
        # inst_cost = (total_time_min / 60.0) * 50.0
        items.append(BOMItem(resource_id="high_content_imager_usage", quantity=total_time_min / 60.0))
        
        mat_cost, inst_cost = self.calculate_costs_from_items(items)
        
        return UnitOp(
            uo_id=f"Image_{magnification}x_{channels}ch",
            name=f"Image {v.name} ({magnification}x, {channels}ch, {fields}f)",
            layer="readout",
            category="imaging",
            time_score=int(total_time_min),
            cost_score=2,
            automation_fit=1,
            failure_risk=1,  # Focus issues
            staff_attention=1,
            instrument="High Content Imager",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_cell_painting(self, vessel_id: str) -> UnitOp:
        """Standard Cell Painting Staining Protocol.

        Handles both macro-scale (flasks, 6/12-well plates) and micro-scale (96/384-well plates).
        Uses appropriate pipette types based on vessel scale.
        """
        v = self.vessels.get(vessel_id)

        # Detect plate scale for appropriate consumables
        is_microplate = "384" in vessel_id or "96" in vessel_id
        pipette_type = "pipette_tip_200ul_filter" if is_microplate else "pipette_10ml"

        steps = []
        items = []
        
        # 1. MitoTracker (Live)
        mito_cost = cp.get_panel_cost("mitotracker", v.working_volume_ml)
        steps.append(UnitOp(
            uo_id="Stain_Mito",
            name="Stain MitoTracker",
            layer="atomic",
            category="liquid_handling",
            time_score=30,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Liquid Handler",
            material_cost_usd=mito_cost,
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        items.append(BOMItem(resource_id="mitotracker", quantity=v.working_volume_ml)) # Assuming quantity matches volume for now
        items.append(BOMItem(resource_id=pipette_type, quantity=1)) # Tip usage
        
        # 2. Fixation
        steps.append(UnitOp(
            uo_id="Fix",
            name="Fix Cells",
            layer="atomic",
            category="liquid_handling",
            time_score=20,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=0.5,
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        items.append(BOMItem(resource_id="paraformaldehyde", quantity=v.working_volume_ml))
        items.append(BOMItem(resource_id=pipette_type, quantity=1))

        # 3. Permeabilization
        steps.append(UnitOp(
            uo_id="Perm",
            name="Permeabilize",
            layer="atomic",
            category="liquid_handling",
            time_score=20,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=0.2,
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        items.append(BOMItem(resource_id="triton_x100", quantity=v.working_volume_ml))
        items.append(BOMItem(resource_id=pipette_type, quantity=1))

        # 4. Staining (Phalloidin, ConA, Hoechst, Syto14, WGA)
        cocktail_cost = cp.get_panel_cost("standard_cocktail", v.working_volume_ml)
        steps.append(UnitOp(
            uo_id="Stain_Cocktail",
            name="Stain Cocktail",
            layer="atomic",
            category="liquid_handling",
            time_score=30,
            cost_score=2,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Liquid Handler",
            material_cost_usd=cocktail_cost,
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        items.append(BOMItem(resource_id="cell_painting_cocktail", quantity=v.working_volume_ml))
        items.append(BOMItem(resource_id=pipette_type, quantity=1))

        # 5. Wash
        steps.append(UnitOp(
            uo_id="Wash_Final",
            name="Final Wash",
            layer="atomic",
            category="liquid_handling",
            time_score=10,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=0.1,
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        items.append(BOMItem(resource_id="pbs", quantity=v.working_volume_ml * 3)) # 3 washes
        items.append(BOMItem(resource_id=pipette_type, quantity=1))
        
        # Liquid Handler usage for all steps
        items.append(BOMItem(resource_id="liquid_handler_usage", quantity=1.0)) # 1 run
        
        total_time = sum(s.time_score for s in steps)
        
        mat_cost, inst_cost = self.calculate_costs_from_items(items)
        
        return UnitOp(
            uo_id=f"CellPainting_{vessel_id}",
            name=f"Cell Painting Staining ({v.name})",
            layer="readout",
            category="staining",
            time_score=total_time,
            cost_score=3,
            automation_fit=1,
            failure_risk=2,
            staff_attention=1,
            instrument="Liquid Handler",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=steps,
            items=items
        )

    def op_fix_cells(self, vessel_id: str) -> UnitOp:
        v = self.vessels.get(vessel_id)
        items = []
        
        items.append(BOMItem(resource_id="paraformaldehyde", quantity=v.working_volume_ml))
        items.append(BOMItem(resource_id="pipette_10ml", quantity=1))
        items.append(BOMItem(resource_id="liquid_handler_usage", quantity=0.2)) # Short run
        
        mat_cost, inst_cost = self.calculate_costs_from_items(items)
        
        return UnitOp(
            uo_id=f"Fix_{vessel_id}",
            name=f"Fix Cells ({v.name})",
            layer="readout",
            category="liquid_handling",
            time_score=20,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )
