from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps

print("=== DISSOCIATION METHODS COMPARISON ===\n")

inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

dissociation_methods = ["accutase", "tryple", "trypsin", "versene", "scraping"]

print("PASSAGE (6-well plate):")
for method in dissociation_methods:
    try:
        op = ops.op_passage("plate_6well", dissociation_method=method)
        total = op.material_cost_usd + op.instrument_cost_usd
        print(f"  {method:12s}: ${total:6.2f} ({len(op.sub_steps):2d} steps, cost_score={op.cost_score}, automation={op.automation_fit})")
    except Exception as e:
        print(f"  {method:12s}: Error - {e}")

print("\nHARVEST (6-well plate):")
for method in dissociation_methods:
    try:
        op = ops.op_harvest("plate_6well", dissociation_method=method)
        total = op.material_cost_usd + op.instrument_cost_usd
        print(f"  {method:12s}: ${total:6.2f} ({len(op.sub_steps):2d} steps, cost_score={op.cost_score})")
    except Exception as e:
        print(f"  {method:12s}: Error - {e}")

print("\n=== FREEZING MEDIA COMPARISON ===\n")

freezing_media = ["cryostor", "fbs_dmso", "bambanker", "mfresr"]

print("FREEZE (10 vials):")
for media in freezing_media:
    try:
        op = ops.op_freeze(10, freezing_media=media)
        total = op.material_cost_usd + op.instrument_cost_usd
        print(f"  {media:12s}: ${total:6.2f} ({len(op.sub_steps):2d} steps, cost_score={op.cost_score})")
    except Exception as e:
        print(f"  {media:12s}: Error - {e}")

print("\n=== COST SAVINGS ===\n")

# Compare cheapest vs most expensive
try:
    accutase_op = ops.op_passage("plate_6well", dissociation_method="accutase")
    trypsin_op = ops.op_passage("plate_6well", dissociation_method="trypsin")
    
    accutase_cost = accutase_op.material_cost_usd + accutase_op.instrument_cost_usd
    trypsin_cost = trypsin_op.material_cost_usd + trypsin_op.instrument_cost_usd
    
    savings = accutase_cost - trypsin_cost
    pct = (savings / accutase_cost) * 100
    
    print(f"Passage: Trypsin vs Accutase saves ${savings:.2f} ({pct:.1f}%)")
except Exception as e:
    print(f"Passage comparison error: {e}")

try:
    cryostor_op = ops.op_freeze(10, freezing_media="cryostor")
    fbs_dmso_op = ops.op_freeze(10, freezing_media="fbs_dmso")
    
    cryostor_cost = cryostor_op.material_cost_usd + cryostor_op.instrument_cost_usd
    fbs_dmso_cost = fbs_dmso_op.material_cost_usd + fbs_dmso_op.instrument_cost_usd
    
    savings = cryostor_cost - fbs_dmso_cost
    pct = (savings / cryostor_cost) * 100
    
    print(f"Freeze: FBS+DMSO vs CryoStor saves ${savings:.2f} ({pct:.1f}%)")
except Exception as e:
    print(f"Freeze comparison error: {e}")
