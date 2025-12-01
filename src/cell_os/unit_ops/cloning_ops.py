"""
Cloning Operations Mixin.
Contains genetic modification operations: Transduce, Transfect, Centrifuge.
"""

from typing import List, Optional

class CloningOpsMixin:
    """Mixin for cloning and genetic modification operations."""
    
    # Note: This mixin assumes self.inv (Inventory) and self.op_dispense/aspirate/incubate exist.

    def op_centrifuge(self, vessel_id: str, duration_min: float, speed_rpm: float = 1000, temp_c: float = 25.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0, name: str = None):
        """Centrifuge a vessel."""
        from .base import UnitOp
        
        if name is None:
            name = f"Centrifuge {vessel_id} ({duration_min}min @ {speed_rpm}rpm)"
        
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
            material_cost_usd=material_cost_usd,
            instrument_cost_usd=instrument_cost_usd if instrument_cost_usd > 0 else 0.5,
            sub_steps=[]
        )

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive"):
        """Transduce cells with viral vector."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Add virus to media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=virus_vol_ul / 1000.0,
            liquid_name="lentivirus",
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 2. If spinoculation, centrifuge
        if method == "spinoculation":
            steps.append(self.op_centrifuge(
                vessel_id=vessel_id,
                duration_min=90.0,
                speed_rpm=1000,
                temp_c=32.0,
                material_cost_usd=0.0,
                instrument_cost_usd=5.0
            ))
        
        # 3. Incubate
        incubation_time = 240.0 if method == "passive" else 120.0  # 4h passive, 2h spinoculation
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=incubation_time,
            temp_c=37.0,
            co2_pct=5.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Virus is expensive
        virus_cost = virus_vol_ul * 10.0  # $10/µL estimate
        
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
            material_cost_usd=total_mat + virus_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_transfect(self, vessel_id: str, method: str = "pei"):
        """Transfect cells with plasmid DNA."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Prepare transfection complex
        # (simplified - real protocol has multiple steps)
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=1.0,
            liquid_name="opti_mem",
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 2. Add DNA
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.01,
            liquid_name="plasmid_dna",
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 3. Add transfection reagent
        reagent = method.lower()  # pei, lipofectamine, etc.
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.05,
            liquid_name=reagent,
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 4. Incubate complex
        steps.append(self.op_incubate(
            vessel_id="tube_15ml",
            duration_min=20.0,
            temp_c=25.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 5. Add to cells
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name="transfection_complex",
            material_cost_usd=self.inv.get_price("pipette_2ml")
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Reagent costs
        reagent_cost = 10.0 if method == "pei" else 50.0  # Lipofectamine is expensive
        dna_cost = 20.0  # Plasmid prep cost
        
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
            material_cost_usd=total_mat + reagent_cost + dna_cost,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )
