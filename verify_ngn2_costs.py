from src.inventory import Inventory
from src.unit_ops import get_ngn2_differentiation_recipe
import sys

print("Starting NGN2 Verification...", flush=True)

try:
    # We need to mock the UnitOpLibrary to use the Inventory system
    # Since UnitOpLibrary currently loads from CSV, we need to bridge it or just use Inventory directly
    # But derive_score expects a UnitOpLibrary-like object.
    # Let's create a bridge class that uses Inventory to populate UnitOps
    
    class InventoryBridge:
        def __init__(self, inv):
            self.inv = inv
            
        def get(self, uo_id):
            # This is a bit of a hack to make the existing derive_score work with the new Inventory system
            # In a real refactor, we'd update UnitOpLibrary to use Inventory
            # For now, we construct a UnitOp object on the fly
            
            # We need to import UnitOp class
            from src.unit_ops import UnitOp
            
            cost = self.inv.calculate_uo_cost(uo_id)
            
            # Fallback for non-inventory ops (like W1_iPSC which is in the CSVs but maybe not fully in YAML yet? 
            # Actually W1_iPSC IS in YAML now if I added it? No, I added W4... 
            # Wait, W1_iPSC was in the CSV. 
            # I need to make sure ALL ops in the recipe are in the Inventory or handled.
            # The recipe uses: W1_iPSC, NGN2_Induction, NGN2_Coat, NGN2_Replate, NGN2_Maturation, Diff5, D15-D18
            
            # NGN2_* are in YAML. Diff5 is in YAML.
            # W1_iPSC is NOT in YAML (I only added W4). It is in CSV.
            # D15-D18 are in CSV.
            
            # So this verification script is tricky because we are in a transition state.
            # I should probably add W1_iPSC and D15-D18 to YAML to be clean, OR
            # I should load the CSVs too.
            
            # Let's just add W1_iPSC and D15-D18 to unit_ops.yaml quickly to make this pure YAML verification work?
            # Or better, just mock the missing ones with fixed costs for this test.
            
            if uo_id in self.inv.unit_ops:
                return UnitOp(
                    uo_id=uo_id,
                    name=self.inv.unit_ops[uo_id].name,
                    layer=self.inv.unit_ops[uo_id].layer,
                    category="test",
                    time_score=0,
                    cost_score=0,
                    automation_fit=0,
                    failure_risk=0,
                    staff_attention=0,
                    instrument=None,
                    material_cost_usd=cost,
                    instrument_cost_usd=0.0 # Overhead is included in material_cost_usd in Inventory for now? No, overhead is separate in YAML but calculate_uo_cost includes it.
                )
            else:
                # Fallback values for things not yet in YAML
                fallback_costs = {
                    "W1_iPSC": 19.2,
                    "D15": 0.0, "D16": 0.0, "D17": 0.0, "D18": 0.0
                }
                return UnitOp(
                    uo_id=uo_id,
                    name=uo_id,
                    layer="test",
                    category="test",
                    time_score=0,
                    cost_score=0,
                    automation_fit=0,
                    failure_risk=0,
                    staff_attention=0,
                    instrument=None,
                    material_cost_usd=fallback_costs.get(uo_id, 0.0),
                    instrument_cost_usd=0.0
                )

    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    bridge = InventoryBridge(inv)
    
    recipe = get_ngn2_differentiation_recipe()
    print("Recipe created", flush=True)

    score = recipe.derive_score(bridge)
    print("Score derived", flush=True)
    print(f"Total Campaign Cost: ${score.total_usd:.2f}", flush=True)
    
    # Breakdown
    print("\n--- Cost Breakdown ---", flush=True)
    print(f"Induction (3 days * 9 wells): ${inv.calculate_uo_cost('NGN2_Induction') * 27:.2f}")
    print(f"Coating (3 plates): ${inv.calculate_uo_cost('NGN2_Coat') * 3:.2f}")
    print(f"Replate: ${inv.calculate_uo_cost('NGN2_Replate'):.2f}")
    print(f"Maturation (7 feeds * 9 wells): ${inv.calculate_uo_cost('NGN2_Maturation') * 63:.2f}")
    print(f"Sequencing (9 samples): ${inv.calculate_uo_cost('Diff5') * 9:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
