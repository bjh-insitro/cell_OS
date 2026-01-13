from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary, ParametricOps

print("Comparing Transfection Methods...\n")

inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

methods = ["pei", "lipofectamine", "fugene", "calcium_phosphate"]

for method in methods:
    try:
        transfect_op = ops.op_transfect("flask_t175", method=method)
        total_cost = transfect_op.material_cost_usd + transfect_op.instrument_cost_usd
        
        print(f"=== {method.upper()} ===")
        print(f"Total Cost: ${total_cost:.2f}")
        print(f"  Material: ${transfect_op.material_cost_usd:.2f}")
        print(f"  Instrument: ${transfect_op.instrument_cost_usd:.2f}")
        print(f"  Cost Score: {transfect_op.cost_score}")
        print(f"  Sub-steps: {len(transfect_op.sub_steps)}")
        print(f"  Steps:")
        for i, step in enumerate(transfect_op.sub_steps, 1):
            step_cost = step.material_cost_usd + step.instrument_cost_usd
            print(f"    {i}. {step.name}: ${step_cost:.4f}")
        print()
    except Exception as e:
        print(f"=== {method.upper()} ===")
        print(f"Error: {e}")
        print(f"(Missing reagent in pricing.yaml)\n")
