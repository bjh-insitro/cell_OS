from src.inventory import Inventory
from src.unit_ops import get_lv_functional_titer_recipe, VesselLibrary, ParametricOps
import sys

print("Starting verification...", flush=True)

try:
    # Mock Bridge
    class InventoryBridge:
        def __init__(self, inv):
            self.inv = inv
        def get(self, uo_id):
            from src.unit_ops import UnitOp
            cost = self.inv.calculate_uo_cost(uo_id)
            if uo_id in self.inv.unit_ops:
                uo = self.inv.unit_ops[uo_id]
                return UnitOp(
                    uo_id=uo_id, name=uo.name, layer=uo.layer,
                    category="test", time_score=0, cost_score=0, automation_fit=0, failure_risk=0, staff_attention=0,
                    instrument=None, material_cost_usd=cost, instrument_cost_usd=0.0
                )
            else:
                # print(f"WARNING: UnitOp {uo_id} not found in Inventory!")
                return UnitOp(
                    uo_id=uo_id, name=uo_id, layer="test", category="test", time_score=0, cost_score=0,
                    automation_fit=0, failure_risk=0, staff_attention=0, instrument=None,
                    material_cost_usd=0.0, instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)

    recipe = get_lv_functional_titer_recipe(ops)
    score = recipe.derive_score(bridge)
    
    print(f"\n--- LV Functional Titer (24-well, 6-point) ---")
    print(f"Total Cost: ${score.total_usd:.2f}")
    print(f"Breakdown:")
    print(score)

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
