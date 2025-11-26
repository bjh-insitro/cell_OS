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

    # Re-implement complex composite ops that span categories
    
    def op_thaw(self, vessel_id: str, cell_line: str = None):
        v = self.vessels.get(vessel_id)
        steps = []
        
        # 1. Coat
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "laminin_521"))
        steps.append(self.op_incubate(vessel_id, 60))
        steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        # 2. Pre-warm
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        # 3. Thaw
        steps.append(self.op_incubate("vial", 2, 37.0))
        
        # 4. Transfer
        steps.append(self.op_dispense(vessel_id, 1.0, "cell_suspension"))
        
        # 5. Incubate
        steps.append(self.op_incubate(vessel_id, 960))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        vessel_cost = self.inv.get_price(vessel_id)
        
        from .base import UnitOp
        return UnitOp(
            uo_id=f"Thaw_{vessel_id}",
            name=f"Thaw into {v.name} (Granular)",
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
            
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, enzyme))
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
        steps.append(self.op_count(vessel_id))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, media))
        
        if supplements:
            for supp in supplements:
                steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.001, supp))
                
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        steps.append(self.op_dispense(vessel_id, virus_vol_ul / 1000.0, "lentivirus"))
        
        if method == "spinoculation":
            steps.append(self.op_centrifuge(vessel_id, 90, 1000))
            steps.append(self.op_incubate(vessel_id, 240))
        else:
            steps.append(self.op_incubate(vessel_id, 960))
            
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "dpbs"))
        for agent in agents:
            steps.append(self.op_dispense(vessel_id, v.coating_volume_ml * 0.00001, agent))
            
        steps.append(self.op_incubate(vessel_id, 60))
        steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        
        if method == "pei":
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.1, "fbs"))
            steps.append(self.op_dispense(vessel_id, 0.0001, "pei_transfection"))
            steps.append(self.op_incubate("tube", 15))
            steps.append(self.op_incubate(vessel_id, 960))
        else:
            # Simplified fallback for other methods
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "optimem"))
            steps.append(self.op_dispense(vessel_id, 0.001, method))
            steps.append(self.op_incubate(vessel_id, 240))
            
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, "accutase"))
        steps.append(self.op_incubate(vessel_id, 5))
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml * 0.2))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
        steps.append(self.op_aspirate("source", 10.0))
        steps.append(self.op_dispense("vials", 1.0 * num_vials, freezing_media))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        from .base import UnitOp
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
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 5.0,
            sub_steps=steps
        )
