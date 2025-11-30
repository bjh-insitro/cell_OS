"""
Incubation operations.
"""

from .base import UnitOp, VesselLibrary

class IncubationOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_incubate(self, vessel_id: str, duration_min: int, temp_c: float = 37.0, co2_pct: float = 5.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = None, name: str = None) -> UnitOp:
        # Cost of incubator space per minute
        cost_per_min = 0.001  # Very cheap
        
        if instrument_cost_usd is None:
            inst_cost = duration_min * cost_per_min
        else:
            inst_cost = instrument_cost_usd
        
        op_name = name if name else f"Incubate {duration_min} min @ {temp_c}C"

        return UnitOp(
            uo_id=f"Incubate_{duration_min}min",
            name=op_name,
            layer="atomic",
            category="incubation",
            time_score=duration_min,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Incubator",
            material_cost_usd=material_cost_usd,
            instrument_cost_usd=inst_cost,
            sub_steps=[]
        )

    def op_centrifuge(self, vessel_id: str, duration_min: int, speed_g: int = 300) -> UnitOp:
        inst_cost = 0.5 + (duration_min * 0.05)  # Base + time
        
        return UnitOp(
            uo_id=f"Centrifuge_{duration_min}min",
            name=f"Centrifuge {duration_min} min @ {speed_g}g",
            layer="atomic",
            category="separation",
            time_score=duration_min,
            cost_score=0,
            automation_fit=1,
            failure_risk=1,  # Balance issues
            staff_attention=1,
            instrument="Centrifuge",
            material_cost_usd=0.0,
            instrument_cost_usd=inst_cost,
            sub_steps=[]
        )
