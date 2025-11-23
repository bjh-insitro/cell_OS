"""
Verification script for Zombie POSH (PerturbView) workflow.

Tests the complete Decross-linking → T7 IVT → Multimodal → SBS workflow
and compares with Vanilla POSH.
"""

from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps, get_zombie_posh_complete_recipe, get_vanilla_posh_complete_recipe
import sys

print("=" * 70)
print("ZOMBIE POSH (PerturbView) WORKFLOW VERIFICATION")
print("=" * 70)

try:
    # Initialize
    inv = Inventory('data/raw/pricing.yaml')
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)
    
    # Test 1: Individual Zombie POSH Operations
    print("\n[1] Testing Individual Zombie POSH Operations...")
    
    print("\n  Decross-linking (4h @ 65°C, cells):")
    decross_op = ops.op_decross_linking("plate_6well", duration_h=4.0, tissue=False)
    print(f"    Cost: ${decross_op.material_cost_usd + decross_op.instrument_cost_usd:.2f}")
    print(f"    Time: 4h")
    
    print("\n  Decross-linking (24h @ 65°C, tissue):")
    decross_tissue_op = ops.op_decross_linking("plate_6well", duration_h=24.0, tissue=True)
    print(f"    Cost: ${decross_tissue_op.material_cost_usd + decross_tissue_op.instrument_cost_usd:.2f}")
    print(f"    Time: 24h")
    
    print("\n  T7 In Vitro Transcription (4h @ 37°C):")
    t7_op = ops.op_t7_ivt("plate_6well", duration_h=4.0)
    print(f"    Cost: ${t7_op.material_cost_usd + t7_op.instrument_cost_usd:.2f}")
    print(f"    Time: 4h")
    
    print("\n  HCR FISH (3 genes):")
    hcr_op = ops.op_hcr_fish("plate_6well", num_genes=3)
    print(f"    Cost: ${hcr_op.material_cost_usd + hcr_op.instrument_cost_usd:.2f}")
    
    print("\n  IBEX Immunofluorescence (4 proteins):")
    ibex_op = ops.op_ibex_immunofluorescence("plate_6well", num_proteins=4)
    print(f"    Cost: ${ibex_op.material_cost_usd + ibex_op.instrument_cost_usd:.2f}")
    
    # Test 2: Simple Zombie POSH Recipe (6-well, manual)
    print("\n[2] Testing Simple Zombie POSH Recipe (6-well, manual)...")
    
    zombie_simple = get_zombie_posh_complete_recipe(
        ops,
        num_grnas=1000,
        vessel="plate_6well",
        multimodal=False,
        automated=False
    )
    
    print(f"\n  Recipe: {zombie_simple.name}")
    
    score_simple = zombie_simple.derive_score(None)
    print(f"\n  Total Cost: ${score_simple.total_usd:.2f}")
    print(f"  Time Score: {score_simple.total_time_score}")
    
    print("\n  Breakdown by Layer:")
    for layer_name, layer_score in score_simple.layer_scores.items():
        if layer_score.count > 0:
            total = layer_score.total_material_usd + layer_score.total_instrument_usd
            print(f"    {layer_name}: ${total:.2f} ({layer_score.count} ops)")
    
    # Test 3: Multimodal Zombie POSH Recipe
    print("\n[3] Testing Multimodal Zombie POSH Recipe (HCR FISH + IBEX)...")
    
    zombie_multi = get_zombie_posh_complete_recipe(
        ops,
        num_grnas=1000,
        vessel="plate_6well",
        multimodal=True,
        num_rna_genes=3,
        num_proteins=4,
        automated=False
    )
    
    score_multi = zombie_multi.derive_score(None)
    print(f"\n  Total Cost: ${score_multi.total_usd:.2f}")
    print(f"  Multimodal cost increase: ${score_multi.total_usd - score_simple.total_usd:.2f}")
    
    # Test 4: Automated Zombie POSH
    print("\n[4] Testing Automated Zombie POSH...")
    
    zombie_auto = get_zombie_posh_complete_recipe(
        ops,
        num_grnas=1000,
        vessel="plate_6well",
        automated=True
    )
    
    score_auto = zombie_auto.derive_score(None)
    print(f"\n  Total Cost: ${score_auto.total_usd:.2f}")
    print(f"  Automation cost increase: ${score_auto.total_usd - score_simple.total_usd:.2f}")
    
    # Test 5: Comparison with Vanilla POSH
    print("\n[5] Comparing Zombie POSH vs Vanilla POSH (6-well, manual)...")
    
    vanilla = get_vanilla_posh_complete_recipe(
        ops,
        num_grnas=1000,
        vessel="plate_6well",
        automated=False
    )
    
    score_vanilla = vanilla.derive_score(None)
    
    print(f"\n  Vanilla POSH: ${score_vanilla.total_usd:.2f}")
    print(f"  Zombie POSH:  ${score_simple.total_usd:.2f}")
    print(f"  Savings:      ${score_vanilla.total_usd - score_simple.total_usd:.2f} ({((score_vanilla.total_usd - score_simple.total_usd) / score_vanilla.total_usd * 100):.1f}%)")
    
    # Test 6: Tissue Processing
    print("\n[6] Testing Tissue Processing (Zombie POSH)...")
    
    zombie_tissue = get_zombie_posh_complete_recipe(
        ops,
        num_grnas=1000,
        vessel="plate_6well",
        tissue=True,
        automated=False
    )
    
    score_tissue = zombie_tissue.derive_score(None)
    print(f"\n  Tissue processing cost: ${score_tissue.total_usd:.2f}")
    print(f"  Additional cost vs cells: ${score_tissue.total_usd - score_simple.total_usd:.2f}")
    
    # Test 7: Workflow Time Comparison
    print("\n[7] Workflow Time Comparison...")
    
    # Vanilla POSH: RT (16h) + Gap fill (1.5h) + RCA (16h) = 33.5h
    vanilla_time = 33.5
    # Zombie POSH: Decross-linking (4h) + T7 IVT (4h) = 8h
    zombie_time = 8.0
    
    print(f"\n  Vanilla POSH molecular steps: {vanilla_time}h")
    print(f"  Zombie POSH molecular steps:  {zombie_time}h")
    print(f"  Time savings: {vanilla_time - zombie_time}h ({((vanilla_time - zombie_time) / vanilla_time * 100):.1f}%)")
    
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    
    print("\n** KEY FINDINGS **")
    print(f"  • Zombie POSH saves ${score_vanilla.total_usd - score_simple.total_usd:.2f} per plate vs Vanilla POSH")
    print(f"  • Zombie POSH is {vanilla_time - zombie_time}h faster (molecular steps only)")
    print(f"  • Multimodal imaging adds ${score_multi.total_usd - score_simple.total_usd:.2f}")
    print(f"  • Automation adds ${score_auto.total_usd - score_simple.total_usd:.2f}")
    print(f"  • Nuclear localization enables better segmentation")
    print(f"  • Higher signal (T7 IVT ~10,000x vs RCA ~1,000x)")

except Exception as e:
    print(f"\nError: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
