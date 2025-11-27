from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# --- FIX: Import UnitOp from base.py ---
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import UnitOp 
# ----------------------------------------

# Mock Database if missing
@dataclass
class CellLineProfile:
    name: str
    cell_type: str          # immortalized, ipsc
    dissociation_method: str
    transfection_method: str
    freezing_media: str
    media: str
    coating: List[str]

DB = {
    "U2OS": CellLineProfile("U2OS", "immortalized", "trypsin_edta", "pei", "fbs_dmso", "media_dmem_complete", []),
    "A549": CellLineProfile("A549", "immortalized", "trypsin_edta", "pei", "fbs_dmso", "media_dmem_complete", []),
    "HepG2": CellLineProfile("HepG2", "immortalized", "trypsin_edta", "pei", "fbs_dmso", "media_dmem_complete", ["laminin_521"]),
    "iPSC": CellLineProfile("iPSC", "ipsc", "accutase", "lipofectamine", "mtesr_plus_kit", "mtesr_plus_kit", ["laminin_521"])
}

def get_cell_line_profile(name): return DB.get(name, DB["U2OS"])

@dataclass
class RecipeConstraints:
    cell_line: str
    budget_tier: str = "standard"
    automation_required: bool = False

class RecipeOptimizer:
    def __init__(self, ops: ParametricOps):
        self.ops = ops
    
    def _get_profile(self, cell_line: str):
        return get_cell_line_profile(cell_line)

    # --- TITRATION RECIPE (1 Well) ---
    def get_titration_recipe(self, cell_line: str) -> List[UnitOp]:
        profile = self._get_profile(cell_line)
        ops_list = []
        
        # 1. Coating
        if profile.coating:
            ops_list.append(self.ops.op_coat("plate_6well", agents=profile.coating))
            
        # 2. Seed/Feed
        ops_list.append(self.ops.op_feed("plate_6well", media=profile.media))
        
        # 3. Transduce
        ops_list.append(self.ops.op_transduce("plate_6well", virus_vol_ul=10.0))
        
        # 4. Harvest
        ops_list.append(self.ops.op_harvest("plate_6well", dissociation_method=profile.dissociation_method))
        
        # 5. Flow Prep
        ops_list.append(self.ops.op_feed("flow_tubes_5ml", media="flow_buffer"))
        
        return ops_list

    # --- SCREEN RECIPE (1 Flask) ---
    def get_screen_recipe(self, cell_line: str, flask_type: str = "flask_t175") -> List[UnitOp]:
        profile = self._get_profile(cell_line)
        ops_list = []
        
        # 1. Coating
        if profile.coating:
            ops_list.append(self.ops.op_coat(flask_type, agents=profile.coating))
            
        # 2. Seed
        ops_list.append(self.ops.op_feed(flask_type, media=profile.media))
        
        # 3. Transduce
        ops_list.append(self.ops.op_transduce(flask_type, virus_vol_ul=100.0))
        
        # 4. Harvest
        ops_list.append(self.ops.op_harvest(flask_type, dissociation_method=profile.dissociation_method))
        
        return ops_list

# Note: The budget_manager will now use these methods to calculate costs dynamically.