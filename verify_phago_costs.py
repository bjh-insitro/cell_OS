from src.inventory import Inventory
from src.unit_ops import get_imicroglia_phagocytosis_recipe
import sys

print("Starting Phagocytosis Verification...", flush=True)

try:
    # Mock Bridge (Same as before)
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
                fallback_costs = {"W1_iPSC": 19.2, "D13": 5.0}
                return UnitOp(
                    uo_id=uo_id, name=uo_id, layer="test", category="test", time_score=0, cost_score=0,
                    automation_fit=0, failure_risk=0, staff_attention=0, instrument=None,
                    material_cost_usd=fallback_costs.get(uo_id, 0.0), instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    recipe = get_imicroglia_phagocytosis_recipe()
    print("Recipe created", flush=True)

    score = recipe.derive_score(bridge)
    print("Score derived", flush=True)
    print(f"Total Campaign Cost: ${score.total_usd:.2f}", flush=True)
    
    # Breakdown
    print("\n--- Cost Breakdown ---", flush=True)
    print(f"Cell Prep (Differentiation): ${inv.calculate_uo_cost('Diff1')*3 + inv.calculate_uo_cost('Diff3')*9 + 19.2:.2f}")
    print(f"Phago Reagents (9 wells): ${inv.calculate_uo_cost('Phago_Stain_Incubate') * 9:.2f}")
    print(f"Imaging (3 plates): ${inv.calculate_uo_cost('Phago_Imaging') * 3:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
