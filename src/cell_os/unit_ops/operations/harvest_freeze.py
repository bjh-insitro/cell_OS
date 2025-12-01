"""
Harvest and freeze operations.
"""
from typing import List, Optional
from cell_os.unit_ops.base import UnitOp
from .base_operation import BaseOperation

class HarvestFreezeOps(BaseOperation):
    """Operations for harvesting and cryopreservation."""
    
    def harvest(self, vessel_id: str, dissociation_method: str = None, cell_line: str = None, name: str = None):
        """Harvest cells for freezing or analysis."""
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            return self.get_price(item_id)
        
        # Auto-detect dissociation method if not provided
        if dissociation_method is None:
            dissociation_method = "trypsin"  # Default
            if cell_line:
                profile = self.get_cell_line_profile(cell_line)
                if profile and profile.dissociation_method:
                    dissociation_method = profile.dissociation_method
                elif cell_line.lower() in ["ipsc", "hesc"]:
                    dissociation_method = "accutase"
        
        # Determine media type for quench
        media = "mtesr_plus_kit" if cell_line and cell_line.lower() in ["ipsc", "hesc"] else "dmem_10fbs"
        
        # 1. Aspirate media (15mL for T75)
        steps.append(self.lh.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=15.0,
            material_cost_usd=get_single_cost("pipette_10ml") * 2,
            name="Aspirate 15.0mL from T-75 Flask"
        ))
        
        # 2. Wash with PBS
        steps.append(self.lh.op_dispense(
            vessel_id=vessel_id,
            volume_ml=5.0,
            liquid_name="pbs",
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Dispense 5.0mL pbs into T-75 Flask"
        ))
        steps.append(self.lh.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=5.0,
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Aspirate 5.0mL from T-75 Flask"
        ))
        
        # 3. Add dissociation reagent
        steps.append(self.lh.op_dispense(
            vessel_id=vessel_id,
            volume_ml=2.0,
            liquid_name=dissociation_method,
            material_cost_usd=0.0,
            name=f"Dispense 2.0mL {dissociation_method} into T-75 Flask"
        ))
        
        # 4. Incubate
        steps.append(self.lh.op_incubate(
            vessel_id=vessel_id,
            duration_min=10.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5,
            name="Incubate 10.0 min @ 37.0C"
        ))
        
        # 5. Quench with 5mL media
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        steps.append(self.lh.op_dispense(
            vessel_id=vessel_id,
            volume_ml=5.0,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_10ml") + (5.0 * media_cost_per_ml),
            name=f"Quench with 5.0mL {media}"
        ))
        
        # 6. Collect cells into 15mL tube (7mL total)
        tube_id = "tube_15ml"
        steps.append(self.lh.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=7.0,
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Aspirate 7.0mL from T-75 Flask"
        ))
        steps.append(self.lh.op_dispense(
            vessel_id=tube_id,
            volume_ml=7.0,
            liquid_name="cells",
            material_cost_usd=get_single_cost("tube_15ml_conical"),
            name="Dispense into 15mL tube"
        ))
        
        # 7. Count cells (sample 100uL)
        steps.append(self.lh.op_aspirate(
            vessel_id=tube_id,
            volume_ml=0.1,
            material_cost_usd=get_single_cost("tip_200ul_lr"),
            name="Sample 100uL for count"
        ))
        
        # 8. Centrifuge
        if hasattr(self.lh, 'op_centrifuge'):
            steps.append(self.lh.op_centrifuge(
                vessel_id=tube_id,
                duration_min=5.0,
                speed_rpm=1200,
                temp_c=25.0,
                instrument_cost_usd=0.5,
                name="Centrifuge 5min @ 1200rpm"
            ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        dissociation_cost = 2.0 * (2.0 if dissociation_method == "accutase" else 0.5)
        pbs_cost = 5.0 * 0.01  # PBS is cheap
        
        return UnitOp(
            uo_id=f"Harvest_{vessel_id}",
            name=name if name else f"Harvest cells from {vessel_id} ({dissociation_method})",
            layer="culture",
            category="harvest",
            time_score=30,
            cost_score=2,
            automation_fit=3,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet + Centrifuge",
            material_cost_usd=total_mat + dissociation_cost + pbs_cost,
            instrument_cost_usd=total_inst + 3.0,
            sub_steps=steps
        )

    def freeze(self, num_vials: int = 10, freezing_media: str = "cryostor_cs10", cell_line: str = None):
        """Freeze cells into cryovials."""
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            return self.get_price(item_id)
        
        # Use 0.35mL per vial for iPSC/hESC, 0.5mL for others (Micronic 0.75mL tubes)
        volume_per_vial = 0.35 if cell_line and cell_line.lower() in ["ipsc", "hesc"] else 0.5
        vial_type = "micronic_tube"  # Default to Micronic 0.75mL tubes as requested
        
        # 1. Aspirate supernatant (after centrifuge from harvest)
        tube_id = "tube_15ml"
        steps.append(self.lh.op_aspirate(
            vessel_id=tube_id,
            volume_ml=6.9,  # Leave pellet with ~100uL
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Aspirate supernatant"
        ))
        
        # 2. Resuspend pellet in CryoStor to achieve target concentration
        # Target: 1e6 cells per 0.35mL (or per 1.0mL for other cell types)
        # Total volume needed = num_vials * volume_per_vial
        total_volume_ml = num_vials * volume_per_vial
        
        cryostor_cost_per_ml = 5.0  # CryoStor CS10 is expensive
        steps.append(self.lh.op_dispense(
            vessel_id=tube_id,
            volume_ml=total_volume_ml,
            liquid_name=freezing_media,
            material_cost_usd=get_single_cost("pipette_2ml") + (total_volume_ml * cryostor_cost_per_ml),
            name=f"Resuspend in {total_volume_ml:.2f}mL {freezing_media}"
        ))
        
        # 3. Mix by pipetting
        steps.append(self.lh.op_aspirate(
            vessel_id=tube_id,
            volume_ml=min(1.0, total_volume_ml),
            material_cost_usd=0.0,  # Reuse pipette
            name="Mix by pipetting"
        ))
        steps.append(self.lh.op_dispense(
            vessel_id=tube_id,
            volume_ml=min(1.0, total_volume_ml),
            liquid_name="cell_suspension",
            material_cost_usd=0.0,
            name="Mix by pipetting"
        ))
        
        # 4. Aliquot into vials
        for i in range(num_vials):
            vial_id = f"vial_{i+1}"
            steps.append(self.lh.op_aspirate(
                vessel_id=tube_id,
                volume_ml=volume_per_vial,
                material_cost_usd=get_single_cost("pipette_2ml") if i == 0 else 0.0,  # First vial pays for pipette
                name=f"Aspirate {volume_per_vial}mL for vial {i+1}"
            ))
            steps.append(self.lh.op_dispense(
                vessel_id=vial_id,
                volume_ml=volume_per_vial,
                liquid_name="cell_suspension",
                material_cost_usd=get_single_cost(vial_type),  # Each vial has a cost
                name=f"Dispense into vial {i+1}"
            ))
        
        # 5. Controlled rate freezing
        steps.append(self.lh.op_incubate(
            vessel_id="controlled_rate_freezer",
            duration_min=120.0,  # 2 hours
            temp_c=-80.0,
            material_cost_usd=0.0,
            instrument_cost_usd=10.0,  # Controlled rate freezer is expensive to run
            name="Controlled rate freezing to -80C"
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Freeze_{num_vials}vials",
            name=f"Freeze {num_vials} vials ({freezing_media}, {volume_per_vial}mL each)",
            layer="banking",
            category="culture",
            time_score=60,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet + Controlled Rate Freezer",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 5.0,
            sub_steps=steps
        )
