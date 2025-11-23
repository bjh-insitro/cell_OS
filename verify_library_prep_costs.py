from src.inventory import Inventory
from src.unit_ops import get_lv_library_preparation_recipe, VesselLibrary, ParametricOps
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
                return UnitOp(
                    uo_id=uo_id, name=uo_id, layer="test", category="test", time_score=0, cost_score=0,
                    automation_fit=0, failure_risk=0, staff_attention=0, instrument=None,
                    material_cost_usd=0.0, instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)

    # Scenario 1: Small Library (100 genes, 250x) -> ~83k cells -> 6-well
    recipe_small = get_lv_library_preparation_recipe(ops, num_grnas=100, representation=250)
    score_small = recipe_small.derive_score(bridge)
    print(f"\n--- Small Library (100 genes, 250x) ---")
    print(f"Total Cost: ${score_small.total_usd:.2f}")
    print(f"Vessel: {recipe_small.name.split('_')[-1]}")

    # Scenario 2: Large Library (10,000 genes, 250x) -> ~8.3M cells -> T75
    recipe_large = get_lv_library_preparation_recipe(ops, num_grnas=10000, representation=250)
    score_large = recipe_large.derive_score(bridge)
    print(f"\n--- Large Library (10,000 genes, 250x) ---")
    print(f"Total Cost: ${score_large.total_usd:.2f}")
    print(f"Vessel: {recipe_large.name.split('_')[-1]}")
    
    # Scenario 3: Whole Genome (20,000 genes, 250x) -> ~16.6M cells -> T175
    recipe_wg = get_lv_library_preparation_recipe(ops, num_grnas=20000, representation=250)
    score_wg = recipe_wg.derive_score(bridge)
    print(f"\n--- Whole Genome (20,000 genes, 250x) ---")
    print(f"Total Cost: ${score_wg.total_usd:.2f}")
    print(f"Vessel: {recipe_wg.name.split('_')[-1]}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
