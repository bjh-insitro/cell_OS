"""
Transfection and transduction operations.
"""
from typing import List, Optional
from cell_os.unit_ops.base import UnitOp
from .base_operation import BaseOperation
from cell_os.inventory import BOMItem

class TransfectionOps(BaseOperation):
    """Operations for genetic modification (transfection, transduction)."""
    
    def transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive"):
        """Transduce cells with viral vector."""
        steps = []
        items = []
        
        # 1. Add virus to media
        steps.append(self.lh.op_dispense(
            vessel_id=vessel_id,
            volume_ml=virus_vol_ul / 1000.0,
            liquid_name="lentivirus",
            material_cost_usd=self.get_price("pipette_200ul")
        ))
        items.append(BOMItem(resource_id="pipette_200ul", quantity=1))
        items.append(BOMItem(resource_id="lentivirus", quantity=virus_vol_ul)) # Assuming resource is in uL or we need to convert? Let's assume uL for now or handle in pricing.
        
        # 2. If spinoculation, centrifuge
        if method == "spinoculation":
            if hasattr(self.lh, 'op_centrifuge'):
                steps.append(self.lh.op_centrifuge(
                    vessel_id=vessel_id,
                    duration_min=90.0,
                    speed_rpm=1000,
                    temp_c=32.0,
                    material_cost_usd=0.0,
                    instrument_cost_usd=5.0
                ))
                items.append(BOMItem(resource_id="centrifuge_usage", quantity=1))
        
        # 3. Incubate
        incubation_time = 240.0 if method == "passive" else 120.0  # 4h passive, 2h spinoculation
        steps.append(self.lh.op_incubate(
            vessel_id=vessel_id,
            duration_min=incubation_time,
            temp_c=37.0,
            co2_pct=5.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0
        ))
        items.append(BOMItem(resource_id="incubator_usage", quantity=incubation_time/60.0))
        
        # Calculate total costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            total_mat = sum(s.material_cost_usd for s in steps)
            total_inst = sum(s.instrument_cost_usd for s in steps)
            virus_cost = virus_vol_ul * 10.0  # $10/µL estimate
            mat_cost = total_mat + virus_cost
            inst_cost = total_inst
        
        return UnitOp(
            uo_id=f"Transduce_{vessel_id}_{method}",
            name=f"Transduce {vessel_id} ({method}, {virus_vol_ul}µL virus)",
            layer="genetic_modification",
            category="transduction",
            time_score=240 if method == "passive" else 210,
            cost_score=4,
            automation_fit=2,
            failure_risk=3,
            staff_attention=2,
            instrument="Biosafety Cabinet" + (" + Centrifuge" if method == "spinoculation" else ""),
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=steps,
            items=items
        )

    def transfect(self, vessel_id: str, method: str = "pei"):
        """Transfect cells with plasmid DNA."""
        steps = []
        items = []
        
        # 1. Prepare transfection complex
        # (simplified - real protocol has multiple steps)
        steps.append(self.lh.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=1.0,
            liquid_name="opti_mem",
            material_cost_usd=self.get_price("tube_15ml_conical")
        ))
        items.append(BOMItem(resource_id="tube_15ml_conical", quantity=1))
        items.append(BOMItem(resource_id="opti_mem", quantity=1.0))
        
        # 2. Add DNA
        steps.append(self.lh.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.01,
            liquid_name="plasmid_dna",
            material_cost_usd=self.get_price("pipette_200ul")
        ))
        items.append(BOMItem(resource_id="pipette_200ul", quantity=1))
        items.append(BOMItem(resource_id="plasmid_dna", quantity=10.0)) # ug?
        
        # 3. Add transfection reagent
        reagent = method.lower()  # pei, lipofectamine, etc.
        steps.append(self.lh.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.05,
            liquid_name=reagent,
            material_cost_usd=self.get_price("pipette_200ul")
        ))
        items.append(BOMItem(resource_id="pipette_200ul", quantity=1))
        items.append(BOMItem(resource_id=reagent, quantity=0.05)) # mL?
        
        # 4. Incubate complex
        steps.append(self.lh.op_incubate(
            vessel_id="tube_15ml",
            duration_min=20.0,
            temp_c=25.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 5. Add to cells
        steps.append(self.lh.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name="transfection_complex",
            material_cost_usd=self.get_price("pipette_2ml")
        ))
        items.append(BOMItem(resource_id="pipette_2ml", quantity=1))
        
        # Calculate total costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            total_mat = sum(s.material_cost_usd for s in steps)
            total_inst = sum(s.instrument_cost_usd for s in steps)
            reagent_cost = 10.0 if method == "pei" else 50.0  # Lipofectamine is expensive
            dna_cost = 20.0  # Plasmid prep cost
            mat_cost = total_mat + reagent_cost + dna_cost
            inst_cost = total_inst + 2.0
        
        return UnitOp(
            uo_id=f"Transfect_{vessel_id}_{method}",
            name=f"Transfect {vessel_id} ({method})",
            layer="genetic_modification",
            category="transfection",
            time_score=40,
            cost_score=3,
            automation_fit=2,
            failure_risk=3,
            staff_attention=3,
            instrument="Biosafety Cabinet",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=steps,
            items=items
        )
