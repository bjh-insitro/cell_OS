"""
Parametric Operations.
Unifies all operation types (Liquid Handling, Protocols, Imaging, Analysis) 
into a single access interface.
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
        self.resolver = None
        
        # Initialize parent classes
        LiquidHandlingOps.__init__(self, vessel_lib, pricing_inv)
        IncubationOps.__init__(self, vessel_lib, pricing_inv)
        ImagingOps.__init__(self, vessel_lib, pricing_inv)
        AnalysisOps.__init__(self, vessel_lib, pricing_inv)
        # NOTE: ProtocolsOps is not initialized here yet, as per previous discussion,
        # but the methods are implemented here for the time being.

    def get_cell_line_defaults(self, cell_line: str):
        if not CELL_LINE_DB_AVAILABLE:
            raise ValueError("Cell line database not available.")
        return get_optimal_methods(cell_line)

    # --- NEW COMPOSITE UO: DETAILED THAW PROTOCOL (MCB) ---
    def op_thaw(self, vessel_id: str, cell_line: str = None):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Ensure UnitOp is in scope
        
        # Helper to retrieve price for a single disposable item (Unit Cost)
        def get_single_cost(item_id: str):
            """Retrieves the price for one logical unit (unit_price_usd)."""
            return self.inv.get_price(item_id) if item_id else 0.0

        # --- LOGIC START ---
        
        # Try to get config from resolver
        config = None
        if self.resolver and cell_line:
            try:
                config = self.resolver.get_thaw_config(cell_line, vessel_id)
            except (ValueError, KeyError):
                pass  # Fall back to legacy
        
        # Determine parameters from config or legacy
        if config:
            coating_needed = config["coating_required"]
            coating_reagent = config["coating_reagent"]
            media = config["media"]
            volumes = config["volumes_mL"]
        else:
            # Legacy path
            coating_needed = False
            coating_reagent = "laminin_521"
            media = "mtesr_plus_kit"
            volumes = {
                "media_aliquot": 40.0,
                "pre_warm": v.max_volume_ml,  # Legacy used max_volume_ml
                "wash_aliquot": 5.0,
                "wash_vial": 1.0,
                "resuspend": 1.0,
                "transfer": 1.0
            }
            
            # Legacy coating check
            if cell_line:
                if self.resolver:
                    profile = self.resolver.get_cell_line_profile(cell_line)
                    if profile and getattr(profile, 'coating_required', False):
                        coating_needed = True
                        reagent_attr = getattr(profile, "coating_reagent", getattr(profile, "coating", coating_reagent))
                        if reagent_attr and reagent_attr != "none":
                            coating_reagent = reagent_attr
                elif CELL_LINE_DB_AVAILABLE:
                    profile = get_cell_line_profile(cell_line)
                    if profile and getattr(profile, 'coating_required', False):
                        coating_needed = True
                        reagent_attr = getattr(profile, "coating_reagent", getattr(profile, "coating", coating_reagent))
                        if reagent_attr and reagent_attr != "none":
                            coating_reagent = reagent_attr
        
        # 0. Conditional Coating
        if coating_needed:
            steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, coating_reagent))
            steps.append(self.op_incubate(vessel_id, 60))
            steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        # 1. Aliquot Required Media into 50mL Tube (using 25mL pipette)
        media_vol = volumes["media_aliquot"]
        tube_50ml_cost = get_single_cost("tube_50ml_conical")
        pipette_25ml_cost = get_single_cost("pipette_25ml")
        
        steps.append(UnitOp(
            uo_id="Aliquot_Media_50mL", 
            name=f"Aliquot {media_vol}mL Media to 50mL Tube",
            material_cost_usd=tube_50ml_cost + pipette_25ml_cost + self.op_dispense(None, media_vol, media).material_cost_usd,
            instrument="Manual", sub_steps=[]))
            
        # 2. Put Media into Flask (Pre-warm)
        pre_warm_vol = volumes["pre_warm"]
        pipette_10ml_cost = get_single_cost("pipette_10ml")
        steps.append(self.op_dispense(vessel_id, pre_warm_vol, media, 
                                      material_cost_usd=pipette_10ml_cost,
                                      name="Pre-warm Media in Flask")) 
        
        # 3. Aliquot Wash/Dilution Media into 15mL Tube
        wash_vol = volumes["wash_aliquot"]
        tube_15ml_cost = get_single_cost("tube_15ml_conical")
        pipette_5ml_cost = get_single_cost("pipette_5ml")
        
        steps.append(UnitOp(
            uo_id="Aliquot_Wash_15mL", 
            name=f"Aliquot {wash_vol}mL Wash Media to 15mL Tube",
            material_cost_usd=tube_15ml_cost + pipette_5ml_cost + self.op_dispense(None, wash_vol, media).material_cost_usd,
            instrument="Manual", sub_steps=[]))
        
        # 4. Thaw Vial (Incubate)
        steps.append(self.op_incubate("vial", 2, 37.0))
        
        # 5. Transfer Vial Contents (using 1mL tip) and Wash
        tip_1ml_cost = get_single_cost("tip_1000ul_lr")
        
        steps.append(UnitOp(
            uo_id="Transfer_Vial_Contents", 
            name="Transfer Vial Contents to 15mL Tube",
            material_cost_usd=tip_1ml_cost,
            instrument="Manual", sub_steps=[]))
        
        wash_vial_vol = volumes["wash_vial"]
        pipette_2ml_cost = get_single_cost("pipette_2ml")
        steps.append(self.op_dispense(None, wash_vial_vol, media, 
                                      material_cost_usd=pipette_2ml_cost, 
                                      name=f"Wash Vial with {wash_vial_vol}mL Media (2mL Pipette)"))
        
        # 6. Centrifuge
        steps.append(self.op_centrifuge("tube_15ml_conical", 5))

        # 7. Aspirate Supernatant
        tip_200ul_cost = get_single_cost("tip_200ul_lr")
        steps.append(self.op_aspirate(None, wash_vol, 
                                      material_cost_usd=pipette_2ml_cost + tip_200ul_cost, 
                                      name="Aspirate Supernatant (2mL Pipette + Tip)"))
        
        # 8. Re-suspend & Sample for Count
        resuspend_vol = volumes["resuspend"]
        steps.append(self.op_dispense(None, resuspend_vol, media, 
                                      material_cost_usd=pipette_2ml_cost, 
                                      name=f"Resuspend in {resuspend_vol}mL Media"))
        
        steps.append(self.op_count("tube_15ml_conical", method="nc-202",
                                   material_cost_usd=get_single_cost("tip_200ul_lr")))
        
        # 9. Transfer the required amount of cells into the required vessel
        transfer_vol = volumes["transfer"]
        steps.append(self.op_dispense(vessel_id, transfer_vol, "cell_suspension", 
                                      name=f"Transfer {transfer_vol}mL Cells to Flask (2mL Pipette)"))
        
        # 10. Final Incubate
        steps.append(self.op_incubate(vessel_id, 960))
        
        # --- FINAL COST CALCULATION ---
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        # Use vessel's consumable_id to look up price, fallback to vessel_id for backwards compatibility
        pricing_key = v.consumable_id if v.consumable_id else vessel_id
        vessel_cost = self.inv.get_price(pricing_key) 
        
        from .base import UnitOp # This is redundant but kept for robustness 
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

    # --- op_passage (Cell Expansion) ---
    def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase", cell_line: str = None):
        # 1. Try to resolve using ProtocolResolver if available
        if self.resolver:
            target_cell_line = cell_line
            if not target_cell_line:
                # Heuristic inference
                if dissociation_method == "trypsin":
                    target_cell_line = "HEK293"
                elif dissociation_method == "accutase":
                    target_cell_line = "iPSC"
            
            if target_cell_line:
                # Infer vessel type
                parts = vessel_id.split('_')
                if len(parts) > 1 and parts[0] == "flask":
                     vessel_type = parts[1].upper()
                else:
                     vessel_type = parts[-1].upper()
                
                try:
                    ops = self.resolver.resolve_passage_protocol(target_cell_line, vessel_type)
                    
                    # Append Seeding Step (Legacy op_passage includes seeding)
                    growth_media = self.resolver.cell_lines[target_cell_line]["growth_media"]
                    v = self.vessels.get(vessel_id)
                    pipette_10ml_cost = self.inv.get_price("pipette_10ml")
                    
                    sub_steps = ops[:]
                    sub_steps.append(self.op_dispense(vessel_id, v.working_volume_ml, growth_media, material_cost_usd=pipette_10ml_cost))
                    
                    total_mat = sum(s.material_cost_usd for s in sub_steps)
                    total_inst = sum(s.instrument_cost_usd for s in sub_steps)
                    
                    from .base import UnitOp
                    return UnitOp(
                        uo_id=f"Passage_{target_cell_line}_{vessel_id}",
                        name=f"Passage {target_cell_line} in {vessel_id} (Resolved)",
                        layer="cell_prep",
                        category="culture",
                        time_score=1,
                        cost_score=1,
                        automation_fit=1,
                        failure_risk=1,
                        staff_attention=1,
                        instrument="Biosafety Cabinet",
                        material_cost_usd=total_mat,
                        instrument_cost_usd=total_inst + 2.8,
                        sub_steps=sub_steps
                    )
                except Exception:
                    # Fallback to legacy if resolution fails (e.g. unknown cell line)
                    pass

        # Legacy implementation
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")

        # 1. Aspirate
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
        
        if dissociation_method == "scraping":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
            needs_quench = False
        elif dissociation_method == "versene":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, "versene_edta", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_incubate(vessel_id, 10))
            needs_quench = False
        else:
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
            
            enzyme = "accutase"
            if dissociation_method == "tryple": enzyme = "tryple_express"
            elif dissociation_method == "trypsin": enzyme = "trypsin_edta"
            
            # NOTE: Assuming a 5mL pipette for enzyme dispense
            pipette_5ml_cost = self.inv.get_price("pipette_5ml")
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, enzyme, material_cost_usd=pipette_5ml_cost))
            steps.append(self.op_incubate(vessel_id, 5))
            needs_quench = True
            
        if needs_quench:
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit", material_cost_usd=pipette_10ml_cost))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 1.2, material_cost_usd=pipette_10ml_cost))
        elif dissociation_method != "scraping":
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 0.2, material_cost_usd=pipette_10ml_cost))
            
        steps.append(self.op_centrifuge(vessel_id, 5))
        
        if needs_quench:
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 1.2, material_cost_usd=pipette_10ml_cost))
        else:
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, material_cost_usd=pipette_10ml_cost))
            
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit", material_cost_usd=pipette_10ml_cost))
        
        # FIX: Replaced self.ops.op_count with self.op_count
        steps.append(self.op_count(vessel_id)) # Note: Assumes op_count handles its own consumables (e.g. hemocytometer/tip)
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit", material_cost_usd=pipette_10ml_cost))
        
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

    # --- op_feed (Cell Feeding) ---
    def op_feed(self, vessel_id: str, media: str = None, cell_line: str = None, supplements: List[str] = None):
        v = self.vessels.get(vessel_id)
        steps = []
        
        from .base import UnitOp # Added for consistency
        
        # Try to get config from resolver
        config = None
        if self.resolver and cell_line:
            try:
                config = self.resolver.get_feed_config(cell_line, vessel_id)
            except (ValueError, KeyError):
                pass  # Fall back to legacy
        
        # Determine parameters from config or arguments/legacy
        if config:
            feed_media = media if media else config["media"]
            feed_volume = config["volume_ml"]
        else:
            # Legacy path
            feed_media = media if media else "mtesr_plus_kit"
            feed_volume = v.working_volume_ml
        
        # NOTE: Using 10mL pipette cost for these manual steps
        pipette_10ml_cost = self.inv.get_price("pipette_10ml")
        
        steps.append(self.op_aspirate(vessel_id, feed_volume, material_cost_usd=pipette_10ml_cost))
        steps.append(self.op_dispense(vessel_id, feed_media, feed_volume, material_cost_usd=pipette_10ml_cost))
        
        if supplements:
            for supp in supplements:
                # Assuming tips are used for small supplement volumes
                tip_200ul_cost = self.inv.get_price("tip_200ul_lr")
                steps.append(self.op_dispense(vessel_id, feed_volume * 0.001, supp, material_cost_usd=tip_200ul_cost))
                
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Feed_{vessel_id}_{feed_media}",
            name=f"Feed {v.name} ({feed_media}) (Granular)",
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

    # --- op_transduce (Lentivirus Addition) ---
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