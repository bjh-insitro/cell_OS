"""
Parametric Operations.
Combines all operation types into a single interface.
"""

from typing import List, Optional
from .base import VesselLibrary
from .liquid_handling import LiquidHandlingOps
from .incubation import IncubationOps
from .imaging import ImagingOps
from .analysis import AnalysisOps

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False

class ParametricOps(LiquidHandlingOps, IncubationOps, ImagingOps, AnalysisOps):
    """
    Unified interface for all parametric operations.
    Inherits from all specialized operation classes.
    """
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        
        # Initialize parent classes
        LiquidHandlingOps.__init__(self, vessel_lib, pricing_inv)
        IncubationOps.__init__(self, vessel_lib, pricing_inv)
        ImagingOps.__init__(self, vessel_lib, pricing_inv)
        AnalysisOps.__init__(self, vessel_lib, pricing_inv)

    def get_cell_line_defaults(self, cell_line: str):
        if not CELL_LINE_DB_AVAILABLE:
            raise ValueError("Cell line database not available.")
        return get_optimal_methods(cell_line)

    # --- NEW COMPOSITE UO: DETAILED THAW PROTOCOL (MCB) ---
    def op_thaw(self, vessel_id: str, cell_line: str = None):
        v = self.vessels.get(vessel_id)
        steps = []
        
        # --- CRITICAL FIX: Explicitly import UnitOp here to resolve scope issues ---
        from .base import UnitOp
        
        # Helper to retrieve price for a single disposable item (Unit Cost)
        def get_single_cost(item_id: str):
            """Retrieves the price for one logical unit (unit_price_usd)."""
            return self.inv.get_price(item_id) if item_id else 0.0

        # --- LOGIC START ---
        
        # 0. Conditional Coating Check (Logic added in previous step)
        coating_needed = False
        if cell_line and CELL_LINE_DB_AVAILABLE:
            profile = get_cell_line_profile(cell_line)
            if profile and profile.get('coating_required', False):
                coating_needed = True
        
        if coating_needed:
            # Coating steps should be done 24h in advance, but we model the cost here.
            steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "laminin_521"))
            steps.append(self.op_incubate(vessel_id, 60))
            steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        # 1. Aliquot Required Media into 50mL Tube (using 25mL pipette)
        media_vol = 40.0 # Estimated 40mL total required 
        tube_50ml_cost = get_single_cost("tube_50ml_conical")
        pipette_25ml_cost = get_single_cost("pipette_25ml")
        
        # The cost includes the tube, the pipette used for transfer, and the media cost
        steps.append(UnitOp(
            uo_id="Aliquot_Media_50mL", 
            name="Aliquot 40mL Media to 50mL Tube",
            material_cost_usd=tube_50ml_cost + pipette_25ml_cost + self.ops.op_dispense(None, media_vol, "mtesr_plus_kit").material_cost_usd,
            instrument="Manual", sub_steps=[]))
            
        # 2. Put Media into Flask (Pre-warm) (using 10mL pipette)
        pipette_10ml_cost = get_single_cost("pipette_10ml")
        steps.append(self.op_dispense(vessel_id, v.max_volume_ml, "mtesr_plus_kit", 
                                      material_cost_usd=pipette_10ml_cost,
                                      name="Pre-warm Media in Flask")) 
        
        # 3. Aliquot Wash/Dilution Media into 15mL Tube (using 5mL pipette)
        tube_15ml_cost = get_single_cost("tube_15ml_conical")
        pipette_5ml_cost = get_single_cost("pipette_5ml")
        steps.append(UnitOp(
            uo_id="Aliquot_Wash_15mL", 
            name="Aliquot 5mL Wash Media to 15mL Tube",
            material_cost_usd=tube_15ml_cost + pipette_5ml_cost + self.ops.op_dispense(None, 5.0, "mtesr_plus_kit").material_cost_usd,
            instrument="Manual", sub_steps=[]))
        
        # 4. Thaw Vial (Incubate)
        steps.append(self.op_incubate("vial", 2, 37.0))
        
        # 5. Transfer Vial Contents (using 1mL tip) and Wash
        tip_1ml_cost = get_single_cost("tip_1000ul_lr")
        
        # Transfer
        steps.append(UnitOp(
            uo_id="Transfer_Vial_Contents", 
            name="Transfer Vial Contents to 15mL Tube",
            material_cost_usd=tip_1ml_cost, # Consumes 1mL tip
            instrument="Manual", sub_steps=[]))
        
        # Wash Vial (using 2mL pipette)
        pipette_2ml_cost = get_single_cost("pipette_2ml")
        steps.append(self.op_dispense(None, 1.0, "mtesr_plus_kit", 
                                      material_cost_usd=pipette_2ml_cost, 
                                      name="Wash Vial with 1mL Media (2mL Pipette)"))
        
        # 6. Centrifuge
        steps.append(self.op_centrifuge("tube_15ml_conical", 5))

        # 7. Aspirate Supernatant (using 2mL pipette + 200uL filter tip)
        tip_200ul_cost = get_single_cost("tip_200ul_lr")
        steps.append(self.op_aspirate(None, 5.0, 
                                      material_cost_usd=pipette_2ml_cost + tip_200ul_cost, 
                                      name="Aspirate Supernatant (2mL Pipette + Tip)"))
        
        # 8. Re-suspend & Sample for Count (using 2mL pipette)
        steps.append(self.op_dispense(None, 1.0, "mtesr_plus_kit", 
                                      material_cost_usd=pipette_2ml_cost, 
                                      name="Resuspend in 1mL Media"))
        
        # Sample 100uL for Count (Assuming 200uL tip for accuracy)
        steps.append(self.ops.op_count("tube_15ml_conical", method="nc-202",
                                       material_cost_usd=get_single_cost("tip_200ul_lr"))) # Consumes 1 tip for sampling
        
        # 9. Transfer the required amount of cells into the required vessel
        steps.append(self.op_dispense(vessel_id, 1.0, "cell_suspension", name="Transfer Cells to Flask (2mL Pipette)"))
        
        # 10. Put in the incubator (Final Incubate)
        steps.append(self.op_incubate(vessel_id, 960))
        
        # --- FINAL COST CALCULATION ---
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        vessel_cost = self.inv.get_price(vessel_id) 
        
        from .base import UnitOp # This import is redundant but kept for robustness 
        return UnitOp(
            uo_id=f"Thaw_{vessel_id}",
            name=f"Thaw into {v.name} (Coating: {'Yes' if coating_needed else 'No'})", 
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + vessel_cost, 
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase"):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # 1. Aspirate
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        
        if dissociation_method == "scraping":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            # Manual scrape op would go here
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            needs_quench = False
        elif dissociation_method == "versene":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, "versene_edta"))
            steps.append(self.op_incubate(vessel_id, 10))
            needs_quench = False
        else:
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            enzyme = "accutase"
            if dissociation_method == "tryple": enzyme = "tryple_express"
            elif dissociation_method == "trypsin": enzyme = "trypsin_edta"
            
            # NOTE: Assuming a 5mL pipette for enzyme dispense
            pipette_5ml_cost = self.inv.get_price("pipette_5ml")
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, enzyme, material_cost_usd=pipette_5ml_cost))
            steps.append(self.op_incubate(vessel_id, 5))
            needs_quench = True
            
        if needs_quench:
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 1.2))
        elif dissociation_method != "scraping":
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 0.2))
            
        steps.append(self.op_centrifuge(vessel_id, 5))
        
        if needs_quench:
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 1.2))
        else:
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        steps.append(self.ops.op_count(vessel_id)) # Note: Assumes op_count handles its own consumables (e.g. hemocytometer/tip)
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Passage_{dissociation_method}_{vessel_id}",
            name=f"Passage {v.name} ({dissociation_method}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=2 if dissociation_method == "accutase" else 1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_feed(self, vessel_id: str, media: str = "mtesr_plus_kit", supplements: List[str] = None):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, media, material_cost_usd=pipette_10ml_cost))
        
        if supplements:
            for supp in supplements:
                # Assuming tips are used for small supplement volumes
                tip_200ul_cost = self.inv.get_price("tip_200ul_lr")
                steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.001, supp, material_cost_usd=tip_200ul_cost))
                
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Feed_{vessel_id}_{media}",
            name=f"Feed {v.name} ({media}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 0.5,
            sub_steps=steps
        )

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive"):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for media handling
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        tip_200ul_cost = self.inv.get_price("tip_200ul_lr")
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit", material_cost_usd=pipette_10ml_cost))
        # Virus dispense uses a dedicated tip
        steps.append(self.op_dispense(vessel_id, virus_vol_ul / 1000.0, "lentivirus", material_cost_usd=tip_200ul_cost))
        
        if method == "spinoculation":
            steps.append(self.op_centrifuge(vessel_id, 90, 1000))
            steps.append(self.op_incubate(vessel_id, 240))
        else:
            steps.append(self.op_incubate(vessel_id, 960))
            
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Transduce_{method}_{vessel_id}",
            name=f"Transduce in {v.name} ({method}) (Granular)",
            layer="genetic_supply_chain",
            category="perturbation",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_coat(self, vessel_id: str, agents: List[str] = None):
        if agents is None: agents = ["laminin_521"]
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        tip_200ul_cost = self.inv.get_price("tip_200ul_lr")
        
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "dpbs", material_cost_usd=pipette_10ml_cost))
        for agent in agents:
            steps.append(self.op_dispense(vessel_id, v.coating_volume_ml * 0.00001, agent, material_cost_usd=tip_200ul_cost))
            
        steps.append(self.op_incubate(vessel_id, 60))
        steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml, material_cost_usd=pipette_10ml_cost))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}_{'_'.join(agents)}",
            name=f"Coat {v.name} with {', '.join(agents)} (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_transfect(self, vessel_id: str, method: str = "pei"):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for media handling
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        tip_200ul_cost = self.inv.get_price("tip_200ul_lr")
        
        if method == "pei":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.1, "fbs", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_dispense(vessel_id, 0.0001, "pei_transfection", material_cost_usd=tip_200ul_cost))
            steps.append(self.op_incubate("tube", 15))
            steps.append(self.op_incubate(vessel_id, 960))
        else:
            # Simplified fallback for other methods
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "optimem", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_dispense(vessel_id, 0.001, method, material_cost_usd=tip_200ul_cost))
            steps.append(self.op_incubate(vessel_id, 240))
            
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Transfect_{method}_{vessel_id}",
            name=f"Transfect {v.name} ({method}) (Granular)",
            layer="genetic_supply_chain",
            category="perturbation",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 3.0,
            sub_steps=steps
        )

    def op_harvest(self, vessel_id: str, dissociation_method: str = "accutase"):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
        
        # FIX: Ensure the correct enzyme is used based on dissociation_method argument
        if dissociation_method == "trypsin":
             enzyme_reagent = "trypsin_edta"
        else:
             enzyme_reagent = "accutase"
             
        # NOTE: Assuming a 5mL pipette for enzyme dispense
        pipette_5ml_cost = self.inv.get_price("pipette_5ml")
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, enzyme_reagent, material_cost_usd=pipette_5ml_cost))
        steps.append(self.op_incubate(vessel_id, 5))
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 0.2, material_cost_usd=pipette_10ml_cost))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Harvest_{dissociation_method}_{vessel_id}",
            name=f"Harvest from {v.name} ({dissociation_method}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )

    def op_freeze(self, num_vials: int = 10, freezing_media: str = "cryostor"):
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        
        steps.append(self.op_aspirate("source", 10.0, material_cost_usd=pipette_10ml_cost))
        steps.append(self.op_dispense("vials", 1.0 * num_vials, freezing_media, material_cost_usd=pipette_10ml_cost))
        
        # --- NEW CODE: ACCOUNT FOR FINAL VIALS AND MEDIA COST ---
        vial_cost = self.inv.get_price("cryovial_1_8ml") * num_vials
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Freeze_{num_vials}vials",
            name=f"Freeze {num_vials} vials ({freezing_media})",
            layer="banking",
            category="culture",
            time_score=60,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + vial_cost,
            instrument_cost_usd=total_inst + 5.0,
            sub_steps=steps
        )