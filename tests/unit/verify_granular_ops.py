from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps
import sys

print("Starting Granular Operations Verification...", flush=True)

try:
    inv = Inventory('data/raw/pricing.yaml')
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)
    
    # Test 1: Granular Passage
    print("\n=== Granular Passage (6-well) ===")
    passage_op = ops.op_passage("plate_6well")
    print(f"Total Cost: ${passage_op.material_cost_usd + passage_op.instrument_cost_usd:.2f}")
    print(f"  Material: ${passage_op.material_cost_usd:.2f}")
    print(f"  Instrument: ${passage_op.instrument_cost_usd:.2f}")
    print(f"  Sub-steps: {len(passage_op.sub_steps)}")
    print("\nDetailed Breakdown:")
    for i, step in enumerate(passage_op.sub_steps, 1):
        total = step.material_cost_usd + step.instrument_cost_usd
        print(f"  {i}. {step.name}: ${total:.4f}")
    
    # Test 2: Granular Thaw
    print("\n=== Granular Thaw (6-well) ===")
    thaw_op = ops.op_thaw("plate_6well")
    print(f"Total Cost: ${thaw_op.material_cost_usd + thaw_op.instrument_cost_usd:.2f}")
    print(f"  Material: ${thaw_op.material_cost_usd:.2f}")
    print(f"  Instrument: ${thaw_op.instrument_cost_usd:.2f}")
    print(f"  Sub-steps: {len(thaw_op.sub_steps)}")
    print("\nDetailed Breakdown:")
    for i, step in enumerate(thaw_op.sub_steps, 1):
        total = step.material_cost_usd + step.instrument_cost_usd
        print(f"  {i}. {step.name}: ${total:.4f}")
    
    # Test 3: Granular Freeze
    print("\n=== Granular Freeze (10 vials) ===")
    freeze_op = ops.op_freeze(10)
    print(f"Total Cost: ${freeze_op.material_cost_usd + freeze_op.instrument_cost_usd:.2f}")
    print(f"  Material: ${freeze_op.material_cost_usd:.2f}")
    print(f"  Instrument: ${freeze_op.instrument_cost_usd:.2f}")
    print(f"  Sub-steps: {len(freeze_op.sub_steps)}")
    print("\nDetailed Breakdown:")
    for i, step in enumerate(freeze_op.sub_steps, 1):
        total = step.material_cost_usd + step.instrument_cost_usd
        print(f"  {i}. {step.name}: ${total:.4f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
