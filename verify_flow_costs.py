from src.inventory import Inventory
from src.inventory import Inventory
import sys

print("Starting Flow Cytometry Verification...", flush=True)

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
                # Fallback for generic ops
                return UnitOp(
                    uo_id=uo_id, name=uo_id, layer="test", category="test", time_score=0, cost_score=0,
                    automation_fit=0, failure_risk=0, staff_attention=0, instrument=None,
                    material_cost_usd=1.0, instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    # 1. Live Flow
    from src.unit_ops import get_flow_live_condition_recipe, get_flow_fixed_condition_recipe
    
    live_recipe = get_flow_live_condition_recipe()
    live_score = live_recipe.derive_score(bridge)
    print(f"\n--- Live Flow (1 Condition, 3 Reps) ---")
    print(f"Total Cost: ${live_score.total_usd:.2f}")
    print(f"Cost per Rep: ${live_score.total_usd/3:.2f}")
    
    # 2. Fixed Flow
    fixed_recipe = get_flow_fixed_condition_recipe()
    fixed_score = fixed_recipe.derive_score(bridge)
    print(f"\n--- Fixed Flow (1 Condition, 3 Reps) ---")
    print(f"Total Cost: ${fixed_score.total_usd:.2f}")
    print(f"Cost per Rep: ${fixed_score.total_usd/3:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
