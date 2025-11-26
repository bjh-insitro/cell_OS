"""
Liquid handling operations.
"""

from typing import List, Optional
from .base import UnitOp, VesselLibrary

class LiquidHandlingOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_dispense(self, vessel_id: str, volume_ml: float, liquid_name: str) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
        # Calculate material cost
        unit_price = self.inv.get_price(liquid_name)
        mat_cost = unit_price * volume_ml
        
        # Calculate instrument cost (e.g. tip cost + machine time)
        # Assume 1 tip per dispense ($0.10) + $0.05 machine time
        inst_cost = 0.15
        
        return UnitOp(
            uo_id=f"Dispense_{liquid_name}_{volume_ml}ml",
            name=f"Dispense {volume_ml}mL {liquid_name} into {v.name}",
            layer="atomic",
            category="liquid_handling",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[]
        )

    def op_aspirate(self, vessel_id: str, volume_ml: float) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
        return UnitOp(
            uo_id=f"Aspirate_{volume_ml}ml",
            name=f"Aspirate {volume_ml}mL from {v.name}",
            layer="atomic",
            category="liquid_handling",
            time_score=1,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Liquid Handler",
            material_cost_usd=0.0,
            instrument_cost_usd=0.15,  # Tip + time
            sub_steps=[]
        )
