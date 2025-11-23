from src.inventory import Inventory
from src.unit_ops import get_lv_production_recipe
import sys

print("Starting LV Production Verification...", flush=True)

try:
    # Mock Bridge
    class InventoryBridge:
        def __init__(self, inv):
            self.inv = inv
        def get(self, uo_id):
            from src.unit_ops import UnitOp
            cost = self.inv.calculate_uo_cost(uo_id)
            if uo_id in self.inv.unit_ops:
                return UnitOp(
                    uo_id=uo_id, name=self.inv.unit_ops[uo_id].name, layer=self.inv.unit_ops[uo_id].layer,
                    category="test", time_score=0, cost_score=0, automation_fit=0, failure_risk=0, staff_attention=0,
                    instrument=None, material_cost_usd=cost, instrument_cost_usd=0.0
                )
            else:
                return UnitOp(
                    uo_id=uo_id, name=uo_id, layer="test", category="test", time_score=0, cost_score=0,
                    automation_fit=0, failure_risk=0, staff_attention=0, instrument=None,
                    material_cost_usd=0.0, instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    recipe = get_lv_production_recipe()
    score = recipe.derive_score(bridge)
    
    print(f"\n--- LV Production (Outsourced Cloning + In-House Prep) ---")
    print(f"Total Cost: ${score.total_usd:.2f}")
    
    # Breakdown
    cloning_cost = (
        inv.calculate_uo_cost("Outsource_Oligo_Syn") + 
        inv.calculate_uo_cost("Outsource_Cloning") + 
        inv.calculate_uo_cost("Outsource_NGS_QC") +
        inv.calculate_uo_cost("Outsource_Plasmid_Exp")
    )
    prod_cost = (
        inv.calculate_uo_cost("LV_Transfect") + 
        inv.calculate_uo_cost("LV_Harvest_Conc") + 
        inv.calculate_uo_cost("LV_Titration")
    )
    
    print(f"  Outsourced Cloning: ${cloning_cost:.2f}")
    print(f"  In-House Production: ${prod_cost:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
