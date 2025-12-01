"""
Liquid handling operations.
"""

from typing import List, Optional, Tuple
from .base import UnitOp, VesselLibrary
from cell_os.inventory import BOMItem

class LiquidHandlingOps:
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

    def op_dispense(self, vessel_id: str, volume_ml: float, liquid_name: str, material_cost_usd: float = None, name: str = None) -> UnitOp:
        v = self.vessels.get(vessel_id)
        items = []
        
        # Add liquid item
        items.append(BOMItem(resource_id=liquid_name, quantity=volume_ml))
        
        # Add tip item (heuristic based on volume)
        tip_type = "pipette_10ml" if volume_ml > 5.0 else ("pipette_2ml" if volume_ml > 0.2 else "tip_200ul_lr")
        items.append(BOMItem(resource_id=tip_type, quantity=1))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
            # Override if material_cost_usd is explicitly provided (legacy support or specific override)
            if material_cost_usd is not None:
                mat_cost = material_cost_usd
            
            # Add base instrument cost for dispense action
            inst_cost += 0.05
        else:
            # Legacy fallback
            if material_cost_usd is None:
                unit_price = self.inv.get_price(liquid_name)
                mat_cost = unit_price * volume_ml
            else:
                mat_cost = material_cost_usd
            inst_cost = 0.15
        
        op_name = name if name else f"Dispense {volume_ml}mL {liquid_name} into {v.name}"

        return UnitOp(
            uo_id=f"Dispense_{liquid_name}_{volume_ml}ml",
            name=op_name,
            layer="atomic",
            category="liquid_handling",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Liquid Handler",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_aspirate(self, vessel_id: str, volume_ml: float, material_cost_usd: float = None, name: str = None) -> UnitOp:
        v = self.vessels.get(vessel_id)
        items = []
        
        # Add tip item (heuristic based on volume)
        tip_type = "pipette_10ml" if volume_ml > 5.0 else ("pipette_2ml" if volume_ml > 0.2 else "tip_200ul_lr")
        items.append(BOMItem(resource_id=tip_type, quantity=1))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
            # Override if material_cost_usd is explicitly provided
            if material_cost_usd is not None:
                mat_cost = material_cost_usd
            
            # Add base instrument cost for aspirate action
            inst_cost += 0.05
        else:
            mat_cost = material_cost_usd if material_cost_usd is not None else 0.0
            inst_cost = 0.15

        op_name = name if name else f"Aspirate {volume_ml}mL from {v.name}"

        return UnitOp(
            uo_id=f"Aspirate_{volume_ml}ml",
            name=op_name,
            layer="atomic",
            category="liquid_handling",
            time_score=1,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Liquid Handler",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_incubate(self, vessel_id: str, duration_min: float, temp_c: float = 37.0, co2_pct: float = 5.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0, name: str = None) -> UnitOp:
        """Incubate a vessel."""
        items = []
        
        # Add incubator usage
        # Assuming incubator usage is tracked in hours
        items.append(BOMItem(resource_id="incubator_usage", quantity=duration_min / 60.0))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
            mat_cost += material_cost_usd
            if instrument_cost_usd > 0:
                inst_cost = instrument_cost_usd
        else:
            mat_cost = material_cost_usd
            inst_cost = instrument_cost_usd if instrument_cost_usd > 0 else (duration_min / 60.0) * 0.5 # $0.50/hr estimate fallback
            
        if name is None:
            name = f"Incubate {vessel_id} ({duration_min}min @ {temp_c}C)"
            
        return UnitOp(
            uo_id=f"Incubate_{vessel_id}",
            name=name,
            layer="atomic",
            category="incubation",
            time_score=duration_min,
            cost_score=1,
            automation_fit=3,
            failure_risk=0,
            staff_attention=0,
            instrument="Incubator",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )
