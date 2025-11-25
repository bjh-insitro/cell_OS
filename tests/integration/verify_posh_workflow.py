"""
Verification script for POSH screening workflow.

Tests the new POSH-specific operations:
- Stressor treatment
- Cell fixation
- Cell painting
- High-content imaging
"""

from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary, ParametricOps, get_posh_screening_recipe
import sys

print("=" * 70)
print("POSH SCREENING WORKFLOW VERIFICATION")
print("=" * 70)

try:
    # Initialize
    inv = Inventory('data/raw/pricing.yaml')
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)
    
    # Test 1: Individual Operations
    print("\n[1] Testing Individual POSH Operations...")
    
    print("\n  Stressor Treatment (tBHP, 100µM, 24h on 96-well plate):")
    stressor_op = ops.op_stressor_treatment("plate_96well", stressor="tbhp", concentration_um=100.0, duration_h=24.0)
    print(f"    Cost: ${stressor_op.material_cost_usd + stressor_op.instrument_cost_usd:.2f}")
    print(f"    Sub-steps: {len(stressor_op.sub_steps)}")
    
    print("\n  Cell Fixation (4% PFA, 15min):")
    fix_op = ops.op_fix_cells("plate_96well")
    print(f"    Cost: ${fix_op.material_cost_usd + fix_op.instrument_cost_usd:.2f}")
    print(f"    Sub-steps: {len(fix_op.sub_steps)}")
    
    print("\n  Cell Painting (5-channel standard panel):")
    painting_op = ops.op_cell_painting("plate_96well", dye_panel="standard_5channel")
    print(f"    Cost: ${painting_op.material_cost_usd + painting_op.instrument_cost_usd:.2f}")
    print(f"    Sub-steps: {len(painting_op.sub_steps)}")
    print(f"    Dyes: Hoechst, ConA-647, Phalloidin-488, WGA-594, MitoTracker")
    
    print("\n  High-Content Imaging (96-well, 9 sites/well, 5 channels, 20x):")
    imaging_op = ops.op_imaging("plate_96well", num_sites_per_well=9, channels=5, objective="20x")
    print(f"    Cost: ${imaging_op.material_cost_usd + imaging_op.instrument_cost_usd:.2f}")
    print(f"    Total images: {96 * 9 * 5} = 4,320 images")
    
    # Test 2: Full POSH Recipe
    print("\n[2] Testing Full POSH Screening Recipe...")
    
    posh_recipe = get_posh_screening_recipe(
        ops,
        num_grnas=1000,
        representation=250,
        vessel="plate_96well",
        stressor="tbhp",
        stressor_conc_um=100.0,
        treatment_duration_h=24.0
    )
    
    print(f"\n  Recipe: {posh_recipe.name}")
    
    # Calculate cost
    score = posh_recipe.derive_score(None)
    print(f"\n  Total Cost: ${score.total_usd:.2f}")
    print(f"  Time Score: {score.total_time_score}")
    print(f"  Cost Score: {score.total_cost_score}")
    
    print("\n  Breakdown by Layer:")
    for layer_name, layer_score in score.layer_scores.items():
        if layer_score.count > 0:
            total = layer_score.total_material_usd + layer_score.total_instrument_usd
            print(f"    {layer_name}: ${total:.2f} ({layer_score.count} ops)")
    
    # Test 3: Different Stressors
    print("\n[3] Testing Different Stressors...")
    
    stressors = [
        ("tbhp", "Oxidative stress (tert-Butyl hydroperoxide)"),
        ("tunicamycin", "ER stress (N-glycosylation inhibitor)"),
        ("thapsigargin", "ER stress (SERCA pump inhibitor)")
    ]
    
    for stressor_id, description in stressors:
        recipe = get_posh_screening_recipe(ops, vessel="plate_96well", stressor=stressor_id)
        score = recipe.derive_score(None)
        print(f"    {stressor_id}: ${score.total_usd:.2f} - {description}")
    
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

except Exception as e:
    print(f"\nError: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
