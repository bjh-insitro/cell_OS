from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary, ParametricOps

print("=== TRANSFECTION METHODS ===\n")

inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

transfection_methods = ["pei", "lipofectamine", "fugene", "calcium_phosphate", "nucleofection"]

for method in transfection_methods:
    try:
        op = ops.op_transfect("flask_t175", method=method)
        total = op.material_cost_usd + op.instrument_cost_usd
        
        print(f"{method.upper()}: ${total:.2f} ({len(op.sub_steps)} steps, cost_score={op.cost_score})")
    except Exception as e:
        print(f"{method.upper()}: Error - {e}")

print("\n=== TRANSDUCTION METHODS ===\n")

transduction_methods = ["passive", "spinoculation"]

for method in transduction_methods:
    try:
        op = ops.op_transduce("plate_24well", method=method)
        total = op.material_cost_usd + op.instrument_cost_usd
        
        print(f"{method.upper()}: ${total:.2f} ({len(op.sub_steps)} steps)")
        for i, step in enumerate(op.sub_steps, 1):
            step_cost = step.material_cost_usd + step.instrument_cost_usd
            print(f"  {i}. {step.name}: ${step_cost:.4f}")
    except Exception as e:
        print(f"{method.upper()}: Error - {e}")
    print()
