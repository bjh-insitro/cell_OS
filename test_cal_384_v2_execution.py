"""
Test: Can we execute CAL_384_RULES_WORLD_v2 plate design?

Check what's missing to run Cell Painting simulation on the calibration plate.
"""

import json
from pathlib import Path

# 1. Load the plate design
plate_json_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")

if not plate_json_path.exists():
    print(f"✗ Plate design not found: {plate_json_path}")
    exit(1)

with open(plate_json_path) as f:
    plate_design = json.load(f)

print("✓ Plate design loaded")
print(f"  Plate ID: {plate_design['plate']['plate_id']}")
print(f"  Format: {plate_design['plate']['format']}-well")
print(f"  Readouts: {plate_design['global_defaults']['readouts']}")

# 2. Check if BiologicalVirtualMachine exists and has cell_painting_assay
try:
    from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    print("✓ BiologicalVirtualMachine imported")

    # Check if cell_painting_assay method exists
    if hasattr(BiologicalVirtualMachine, 'cell_painting_assay'):
        print("✓ cell_painting_assay() method exists")
    else:
        print("✗ cell_painting_assay() method NOT found")
except ImportError as e:
    print(f"✗ Cannot import BiologicalVirtualMachine: {e}")
    exit(1)

# 3. Check if we can create a VM instance
try:
    vm = BiologicalVirtualMachine(seed=42)
    print("✓ BiologicalVirtualMachine instantiated")
except Exception as e:
    print(f"✗ Cannot instantiate BiologicalVirtualMachine: {e}")
    exit(1)

# 4. Check if epistemic agent world exists
try:
    from src.cell_os.epistemic_agent.world import ExperimentalWorld
    print("✓ ExperimentalWorld imported")
except ImportError as e:
    print(f"✗ Cannot import ExperimentalWorld: {e}")

# 5. Check if we have proposal/wellspec schemas
try:
    from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
    print("✓ Proposal and WellSpec schemas available")
except ImportError as e:
    print(f"✗ Cannot import schemas: {e}")

# 6. Summary: What's needed to execute?
print("\n" + "="*70)
print("EXECUTION PATHWAY CHECK")
print("="*70)

print("\n[Missing Component]")
print("Need: Function to convert JSON plate design → Proposal with WellSpec list")
print("")
print("Current state:")
print("  ✓ Plate design JSON exists (CAL_384_RULES_WORLD_v2.json)")
print("  ✓ BiologicalVirtualMachine.cell_painting_assay() exists")
print("  ✓ ExperimentalWorld.run_experiment(proposal) exists")
print("  ✓ Proposal/WellSpec schemas exist")
print("")
print("  ✗ NO PARSER: JSON → Proposal")
print("")
print("What needs to be built:")
print("  1. parse_plate_design(json_path) → List[WellSpec]")
print("     - Read JSON well definitions")
print("     - Extract: cell_line, compound, dose, timepoint, position")
print("     - Create WellSpec for each well")
print("")
print("  2. execute_plate_design(json_path, seed=42) → Results")
print("     - Call parse_plate_design()")
print("     - Create Proposal from WellSpec list")
print("     - Create ExperimentalWorld")
print("     - Call world.run_experiment(proposal)")
print("     - Return raw results")
print("")
print("LOC estimate: ~150-200 lines (parser + executor)")
