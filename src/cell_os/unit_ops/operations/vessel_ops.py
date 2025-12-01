"""
Vessel-related operations (centrifuge, coat).
"""
from typing import List, Optional
from cell_os.unit_ops.base import UnitOp
from .base_operation import BaseOperation
from cell_os.inventory import BOMItem

class VesselOps(BaseOperation):
    """Operations for vessel handling and preparation."""
    
    def centrifuge(self, vessel_id: str, duration_min: float, speed_rpm: float = 1000, temp_c: float = 25.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0, name: str = None):
        """Centrifuge a vessel."""
        items = []
        
        if name is None:
            name = f"Centrifuge {vessel_id} ({duration_min}min @ {speed_rpm}rpm)"
        
        items.append(BOMItem(resource_id="centrifuge_usage", quantity=1))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
            # Add any passed-in material cost (e.g. if part of a larger op)
            mat_cost += material_cost_usd 
            # If instrument cost was passed, use max or sum? Usually this op is standalone or sub-step.
            # If standalone, use calculated. If sub-step, caller might override.
            # For now, let's respect passed instrument cost if > 0, else use calculated.
            if instrument_cost_usd > 0:
                inst_cost = instrument_cost_usd
        else:
            mat_cost = material_cost_usd
            inst_cost = instrument_cost_usd if instrument_cost_usd > 0 else 0.5

        return UnitOp(
            uo_id=f"Centrifuge_{vessel_id}",
            name=name,
            layer="atomic",
            category="separation",
            time_score=duration_min,
            cost_score=1,
            automation_fit=3,
            failure_risk=1,
            staff_attention=1,
            instrument="Centrifuge",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def coat(self, vessel_id: str, agents: List[str] = None, num_vessels: int = 1):
        """Coat vessel(s) with ECM proteins."""
        
        if agents is None:
            agents = ["matrigel"]
        
        steps = []
        items = []
        
        # Vessel-specific coating volumes (working solution) PER VESSEL
        if "plate_6well" in vessel_id:
            coating_vol_per_vessel = 6.0 # 1mL per well * 6
        elif "flask_t75" in vessel_id.lower():
            coating_vol_per_vessel = 12.5 # mL for T75
        else:
            coating_vol_per_vessel = 5.0 # Default
        
        # Total volume needed for all vessels
        total_coating_vol = coating_vol_per_vessel * num_vessels
        
        for agent in agents:
            # Vitronectin requires dilution in PBS
            if agent == "vitronectin":
                # Stock: 0.5 mg/mL (5mg in 10mL)
                # Working: 10 µg/mL (0.01 mg/mL)
                # Dilution: 50x
                stock_vol_ml = total_coating_vol / 50.0
                pbs_vol_ml = total_coating_vol - stock_vol_ml
                
                # Costs
                pbs_cost = pbs_vol_ml * self.get_price("dpbs")
                stock_cost = stock_vol_ml * self.get_price("vitronectin")
                
                # 1. Prepare Solution in Tube
                # Add PBS
                steps.append(self.lh.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=pbs_vol_ml,
                    liquid_name="pbs",
                    material_cost_usd=self.get_price("pipette_10ml") + pbs_cost,
                    name=f"Dispense {pbs_vol_ml:.2f}mL PBS into Tube"
                ))
                items.append(BOMItem(resource_id="pipette_10ml", quantity=1))
                items.append(BOMItem(resource_id="dpbs", quantity=pbs_vol_ml))
                
                # Add Vitronectin
                steps.append(self.lh.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=stock_vol_ml,
                    liquid_name=agent,
                    material_cost_usd=self.get_price("pipette_2ml") + stock_cost,
                    name=f"Dispense {stock_vol_ml:.2f}mL {agent} into Tube"
                ))
                items.append(BOMItem(resource_id="pipette_2ml", quantity=1))
                items.append(BOMItem(resource_id="vitronectin", quantity=stock_vol_ml))
                
                # Mix (Aspirate/Dispense)
                steps.append(self.lh.op_aspirate(
                    vessel_id="tube_50ml",
                    volume_ml=5.0,
                    material_cost_usd=0.0,
                    name="Mix Solution (Aspirate)"
                ))
                steps.append(self.lh.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=5.0,
                    liquid_name="mixture",
                    material_cost_usd=0.0,
                    name="Mix Solution (Dispense)"
                ))
                
                # 2. Transfer to Vessels
                for i in range(num_vessels):
                    steps.append(self.lh.op_aspirate(
                        vessel_id="tube_50ml",
                        volume_ml=coating_vol_per_vessel,
                        material_cost_usd=self.get_price("pipette_10ml"),
                        name=f"Aspirate {coating_vol_per_vessel:.1f}mL from Tube"
                    ))
                    steps.append(self.lh.op_dispense(
                        vessel_id=vessel_id,
                        volume_ml=coating_vol_per_vessel,
                        liquid_name=agent,
                        material_cost_usd=0.0,
                        name=f"Dispense {coating_vol_per_vessel:.1f}mL into {vessel_id} {i+1}"
                    ))
                    items.append(BOMItem(resource_id="pipette_10ml", quantity=1))
                
                # 3. Incubate
                steps.append(self.lh.op_incubate(
                    vessel_id=vessel_id,
                    duration_min=60.0,
                    temp_c=37.0,
                    material_cost_usd=0.0,
                    instrument_cost_usd=1.0,
                    name=f"Incubate {num_vessels} {vessel_id}(s) for 1h @ 37C"
                ))
                items.append(BOMItem(resource_id="incubator_usage", quantity=1.0))
                
                items.append(BOMItem(resource_id="tube_50ml_conical", quantity=1))
                
            else:
                # Other agents (matrigel, etc.) - simplified
                agent_cost = total_coating_vol * 2.0  # Estimate
                steps.append(self.lh.op_dispense(
                    vessel_id=vessel_id,
                    volume_ml=total_coating_vol,
                    liquid_name=agent,
                    material_cost_usd=self.get_price("pipette_10ml") + agent_cost,
                    name=f"Coat {num_vessels} {vessel_id}(s) with {agent}"
                ))
                items.append(BOMItem(resource_id="pipette_10ml", quantity=1))
                items.append(BOMItem(resource_id=agent, quantity=total_coating_vol))
                
                steps.append(self.lh.op_incubate(
                    vessel_id=vessel_id,
                    duration_min=60.0,
                    temp_c=37.0,
                    material_cost_usd=0.0,
                    instrument_cost_usd=1.0,
                    name=f"Incubate {num_vessels} {vessel_id}(s) for 1h @ 37C"
                ))
                items.append(BOMItem(resource_id="incubator_usage", quantity=1.0))
        
        # Calculate total costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            total_mat = sum(s.material_cost_usd for s in steps)
            total_inst = sum(s.instrument_cost_usd for s in steps)
            tube_cost = self.get_price("tube_50ml_conical") if "vitronectin" in agents else 0.0
            mat_cost = total_mat + tube_cost
            inst_cost = total_inst
        
        vessel_desc = f"{num_vessels} {vessel_id}(s)" if num_vessels > 1 else vessel_id
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}",
            name=f"Coat {vessel_desc} with {', '.join(agents)}",
            layer="culture",
            category="coating",
            time_score=90,
            cost_score=2,
            automation_fit=2,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=steps,
            items=items
        )
