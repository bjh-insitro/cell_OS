from src.cell_line_database import (
    get_cell_line_profile,
    get_optimal_methods,
    list_cell_lines,
    get_cell_lines_by_type,
    get_cell_lines_by_cost_tier,
    CELL_LINE_DATABASE
)
from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps

print("=== CELL LINE DATABASE VERIFICATION ===\n")

# List all supported cell lines
print(f"Total cell lines in database: {len(CELL_LINE_DATABASE)}\n")

# Group by type
for cell_type in ["immortalized", "iPSC", "hESC", "primary", "differentiated"]:
    lines = get_cell_lines_by_type(cell_type)
    if lines:
        print(f"{cell_type.upper()}: {', '.join(lines)}")

print("\n=== COST COMPARISON BY CELL TYPE ===\n")

# Initialize ops
inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

# Compare costs for different cell types
test_cell_lines = ["HEK293", "iPSC", "Primary_Neurons", "iMicroglia"]

for cell_line in test_cell_lines:
    profile = get_cell_line_profile(cell_line)
    if not profile:
        continue
    
    print(f"=== {profile.name} ({profile.cost_tier.upper()}) ===")
    
    # Passage cost
    try:
        passage_op = ops.op_passage("plate_6well", dissociation_method=profile.dissociation_method)
        passage_cost = passage_op.material_cost_usd + passage_op.instrument_cost_usd
        print(f"  Passage: ${passage_cost:.2f} ({profile.dissociation_method})")
        print(f"    → {profile.dissociation_notes}")
    except Exception as e:
        print(f"  Passage: Error - {e}")
    
    # Freeze cost
    try:
        freeze_op = ops.op_freeze(10, freezing_media=profile.freezing_media)
        freeze_cost = freeze_op.material_cost_usd + freeze_op.instrument_cost_usd
        print(f"  Freeze: ${freeze_cost:.2f} ({profile.freezing_media})")
        print(f"    → {profile.freezing_notes}")
    except Exception as e:
        print(f"  Freeze: Error - {e}")
    
    # Transfection cost
    try:
        transfect_op = ops.op_transfect("flask_t175", method=profile.transfection_method)
        transfect_cost = transfect_op.material_cost_usd + transfect_op.instrument_cost_usd
        print(f"  Transfection: ${transfect_cost:.2f} ({profile.transfection_method}, {profile.transfection_efficiency} efficiency)")
        print(f"    → {profile.transfection_notes}")
    except Exception as e:
        print(f"  Transfection: Error - {e}")
    
    print()

print("\n=== BUDGET vs PREMIUM COMPARISON ===\n")

# Compare budget (HEK293) vs premium (iPSC) for a typical experiment
hek293_profile = get_cell_line_profile("HEK293")
ipsc_profile = get_cell_line_profile("iPSC")

hek293_passage = ops.op_passage("plate_6well", dissociation_method=hek293_profile.dissociation_method)
ipsc_passage = ops.op_passage("plate_6well", dissociation_method=ipsc_profile.dissociation_method)

hek293_freeze = ops.op_freeze(10, freezing_media=hek293_profile.freezing_media)
ipsc_freeze = ops.op_freeze(10, freezing_media=ipsc_profile.freezing_media)

hek293_total = (hek293_passage.material_cost_usd + hek293_passage.instrument_cost_usd +
                hek293_freeze.material_cost_usd + hek293_freeze.instrument_cost_usd)
ipsc_total = (ipsc_passage.material_cost_usd + ipsc_passage.instrument_cost_usd +
              ipsc_freeze.material_cost_usd + ipsc_freeze.instrument_cost_usd)

print(f"HEK293 (Budget): ${hek293_total:.2f}")
print(f"  - Passage ({hek293_profile.dissociation_method}): ${hek293_passage.material_cost_usd + hek293_passage.instrument_cost_usd:.2f}")
print(f"  - Freeze ({hek293_profile.freezing_media}): ${hek293_freeze.material_cost_usd + hek293_freeze.instrument_cost_usd:.2f}")

print(f"\niPSC (Premium): ${ipsc_total:.2f}")
print(f"  - Passage ({ipsc_profile.dissociation_method}): ${ipsc_passage.material_cost_usd + ipsc_passage.instrument_cost_usd:.2f}")
print(f"  - Freeze ({ipsc_profile.freezing_media}): ${ipsc_freeze.material_cost_usd + ipsc_freeze.instrument_cost_usd:.2f}")

savings = ipsc_total - hek293_total
pct = (savings / ipsc_total) * 100
print(f"\nCost difference: ${savings:.2f} ({pct:.1f}% more expensive for iPSC)")
print("Justification: iPSCs require gentler, more expensive reagents to maintain pluripotency")
