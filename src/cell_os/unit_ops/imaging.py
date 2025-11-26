"""
Imaging operations.
"""

from typing import List, Optional
from .base import UnitOp, VesselLibrary
import cell_os.cellpaint_panels as cp

class ImagingOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_imaging(self, vessel_id: str, magnification: int = 20, channels: int = 5, fields: int = 9) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
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
        inst_cost = (total_time_min / 60.0) * 50.0
        
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
            material_cost_usd=0.0,
            instrument_cost_usd=inst_cost,
            sub_steps=[]
        )

    def op_cell_painting(self, vessel_id: str) -> UnitOp:
        """Standard Cell Painting Staining Protocol."""
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. MitoTracker (Live)
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
            material_cost_usd=cp.get_panel_cost("mitotracker", v.working_volume_ml),
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        
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
        
        # 4. Staining (Phalloidin, ConA, Hoechst, Syto14, WGA)
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
            material_cost_usd=cp.get_panel_cost("standard_cocktail", v.working_volume_ml),
            instrument_cost_usd=1.0,
            sub_steps=[]
        ))
        
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
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        total_time = sum(s.time_score for s in steps)
        
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
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_fix_cells(self, vessel_id: str) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
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
            material_cost_usd=0.5,
            instrument_cost_usd=1.0,
            sub_steps=[]
        )
