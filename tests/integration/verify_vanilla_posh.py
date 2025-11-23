"""
Verification script for Vanilla POSH (CellPaint-POSH) workflow.

Tests the complete RT-RCA-CellPainting-SBS workflow with cost calculations.
"""

from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps, get_vanilla_posh_complete_recipe
import sys

print("=" * 70)
print("VANILLA POSH (CellPaint-POSH) WORKFLOW VERIFICATION")
print("=" * 70)

try:
    # Initialize
    inv = Inventory('data/raw/pricing.yaml')
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)
    
    # Test 1: Individual POSH Operations
    print("\n[1] Testing Individual Vanilla POSH Operations...")
    
    print("\n  Reverse Transcription (16h @ 37°C):")
    rt_op = ops.op_reverse_transcription("plate_96well", duration_h=16.0, temp_c=37.0)
    print(f"    Cost: ${rt_op.material_cost_usd + rt_op.instrument_cost_usd:.2f}")
    print(f"    Time: {16}h")
    
    print("\n  Gap Fill & Ligation (90min @ 45°C):")
    gf_op = ops.op_gap_fill_ligation("plate_96well", duration_min=90, temp_c=45.0)
    print(f"    Cost: ${gf_op.material_cost_usd + gf_op.instrument_cost_usd:.2f}")
    print(f"    Time: {90}min")
    
    print("\n  Rolling Circle Amplification (16h @ 30°C):")
    rca_op = ops.op_rolling_circle_amplification("plate_96well", duration_h=16.0, temp_c=30.0)
    print(f"    Cost: ${rca_op.material_cost_usd + rca_op.instrument_cost_usd:.2f}")
    print(f"    Time: {16}h")
    
    print("\n  SBS Cycle 1 (Manual):")
    sbs_op = ops.op_sbs_cycle("plate_96well", cycle_number=1, automated=False)
    print(f"    Cost: ${sbs_op.material_cost_usd + sbs_op.instrument_cost_usd:.2f}")
    
    print("\n  SBS Cycle 1 (Automated):")
    sbs_auto_op = ops.op_sbs_cycle("plate_96well", cycle_number=1, automated=True)
    print(f"    Cost: ${sbs_auto_op.material_cost_usd + sbs_auto_op.instrument_cost_usd:.2f}")
    
    # Test 2: ISS-Compatible Cell Painting
    print("\n[2] Testing ISS-Compatible Cell Painting...")
    
    print("\n  POSH 5-Channel (Hoechst, ConA, WGA, Phalloidin, Mitoprobe):")
    cp_5ch = ops.op_cell_painting("plate_96well", dye_panel="posh_5channel")
    print(f"    Cost: ${cp_5ch.material_cost_usd + cp_5ch.instrument_cost_usd:.2f}")
    print(f"    Sub-steps: {len(cp_5ch.sub_steps)}")
    
    print("\n  POSH 6-Channel (+ pS6 biomarker):")
    cp_6ch = ops.op_cell_painting("plate_96well", dye_panel="posh_6channel")
    print(f"    Cost: ${cp_6ch.material_cost_usd + cp_6ch.instrument_cost_usd:.2f}")
    print(f"    Sub-steps: {len(cp_6ch.sub_steps)}")
    
    # Test 3: Complete Vanilla POSH Recipe (Manual)
    print("\n[3] Testing Complete Vanilla POSH Recipe (Manual)...")
    
    posh_manual = get_vanilla_posh_complete_recipe(
        ops,
        num_grnas=1000,
        representation=250,
        vessel="plate_96well",
        stressor="tbhp",
        stressor_conc_um=100.0,
        treatment_duration_h=24.0,
        num_sbs_cycles=13,
        use_ps6=False,
        automated=False
    )
    
    print(f"\n  Recipe: {posh_manual.name}")
    
    # Calculate cost
    score = posh_manual.derive_score(None)
    print(f"\n  Total Cost: ${score.total_usd:.2f}")
    print(f"  Time Score: {score.total_time_score}")
    print(f"  Cost Score: {score.total_cost_score}")
    
    print("\n  Breakdown by Layer:")
    for layer_name, layer_score in score.layer_scores.items():
        if layer_score.count > 0:
            total = layer_score.total_material_usd + layer_score.total_instrument_usd
            print(f"    {layer_name}: ${total:.2f} ({layer_score.count} ops)")
    
    # Test 4: Complete Vanilla POSH Recipe (Automated)
    print("\n[4] Testing Complete Vanilla POSH Recipe (Automated)...")
    
    posh_auto = get_vanilla_posh_complete_recipe(
        ops,
        num_grnas=1000,
        representation=250,
        vessel="plate_96well",
        stressor="tbhp",
        stressor_conc_um=100.0,
        treatment_duration_h=24.0,
        num_sbs_cycles=13,
        use_ps6=False,
        automated=True
    )
    
    print(f"\n  Recipe: {posh_auto.name}")
    
    score_auto = posh_auto.derive_score(None)
    print(f"\n  Total Cost: ${score_auto.total_usd:.2f}")
    print(f"  Cost Difference (Auto vs Manual): ${score_auto.total_usd - score.total_usd:.2f}")
    
    # Test 5: Different Scales
    print("\n[5] Testing Different Scales...")
    
    scales = [
        (124, "Small (PoC)"),
        (300, "Medium (MoA)"),
        (1640, "Large (Druggable Genome)")
    ]
    
    for num_genes, description in scales:
        recipe = get_vanilla_posh_complete_recipe(
            ops,
            num_grnas=num_genes,
            vessel="plate_96well",
            automated=False
        )
        score = recipe.derive_score(None)
        print(f"    {description} ({num_genes} genes): ${score.total_usd:.2f}")
    
    # Test 6: With pS6 Biomarker
    print("\n[6] Testing with pS6 Biomarker (6th channel)...")
    
    posh_ps6 = get_vanilla_posh_complete_recipe(
        ops,
        num_grnas=1640,
        vessel="plate_96well",
        use_ps6=True,
        automated=True
    )
    
    score_ps6 = posh_ps6.derive_score(None)
    print(f"    With pS6: ${score_ps6.total_usd:.2f}")
    print(f"    Cost increase for pS6: ${score_ps6.total_usd - score_auto.total_usd:.2f}")
    
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

except Exception as e:
    print(f"\nError: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
