import sys
import os
sys.path.append(os.getcwd())

from src.unit_ops import ParametricOps
from src.inventory import Inventory
import src.cellpaint_panels as cp

def verify_cellpaint_panels():
    print("=" * 80)
    print("VERIFYING MODULAR CELL PAINTING PANELS")
    print("=" * 80)

    # Initialize
    from src.unit_ops import VesselLibrary
    vessels = VesselLibrary("data/raw/vessels.yaml") # Assuming this path exists, or we can mock it
    inv = Inventory("data/raw/pricing.yaml")
    ops = ParametricOps(vessels, inv)
    
    # Mock a vessel
    vessel_id = "test_plate_1"
    # We need to ensure the vessel exists in ops.vessels or we mock it
    # ParametricOps loads vessels from yaml, let's see if we can add one dynamically
    # Looking at unit_ops.py, self.vessels is a dict.
    # We can just inject a mock vessel object if we knew the class, 
    # or just rely on a default one if it exists.
    # Let's check if we can add a dummy vessel.
    class MockVessel:
        def __init__(self, vid):
            self.id = vid
            self.working_volume_ml = 0.1 # 100 uL per well? No, usually per well volume is small but 'working_volume_ml' in unit_ops usually refers to the total volume per vessel or per well?
            # In unit_ops, it often uses v.working_volume_ml. 
            # If it's a plate, it might be total volume. 
            # Let's assume 10 mL for a full plate for simplicity of calculation.
            self.working_volume_ml = 10.0 
            
    ops.vessels.vessels[vessel_id] = MockVessel(vessel_id)

    # Test Cases
    panels_to_test = [
        "standard_5channel",
        "posh_5channel",
        "posh_6channel", # Custom pS6
        "neuropaint",    # Should have primary Ab steps
        "alspaint",      # Should have multiple primaries
    ]

    for panel_name in panels_to_test:
        print(f"\nTesting Panel: {panel_name}")
        try:
            op = ops.op_cell_painting(vessel_id, dye_panel=panel_name)
            print(f"  Name: {op.name}")
            print(f"  Total Cost: ${op.material_cost_usd:.2f} (Mat) + ${op.instrument_cost_usd:.2f} (Inst)")
            print(f"  Step Count: {len(op.sub_steps)}")
            
            # Analyze steps
            step_names = [s.name for s in op.sub_steps]
            
            # Check for Primary Antibody steps (incubate 60 min at 4C)
            # Name format: "Incubate {duration_min} min @ {temp_c}C"
            has_primary_incubation = any("Incubate 60 min @ 4.0C" in s.name for s in op.sub_steps)
            
            if panel_name in ["neuropaint", "alspaint", "posh_6channel"]:
                if has_primary_incubation:
                    print("  [PASS] Primary antibody incubation detected.")
                else:
                    print("  [FAIL] Missing primary antibody incubation!")
            else:
                if not has_primary_incubation:
                    print("  [PASS] No primary antibody incubation (as expected).")
                else:
                    print("  [FAIL] Unexpected primary antibody incubation!")

            # Check for specific reagents
            if panel_name == "neuropaint":
                # Check for map2_chicken
                has_map2 = any("map2_chicken" in s.name for s in op.sub_steps)
                if has_map2:
                     print("  [PASS] MAP2 antibody detected.")
                else:
                     print("  [FAIL] MAP2 antibody missing!")

        except Exception as e:
            print(f"  [ERROR] Failed to generate recipe: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)

if __name__ == "__main__":
    verify_cellpaint_panels()
