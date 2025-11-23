import sys
import os
sys.path.append(os.getcwd())

from src.unit_ops import ParametricOps, VesselLibrary
from src.inventory import Inventory
import src.upstream as up

def verify_upstream_workflow():
    print("=" * 80)
    print("VERIFYING PATH A: GENETIC SUPPLY CHAIN")
    print("=" * 80)

    # Initialize
    vessels = VesselLibrary("data/raw/vessels.yaml")
    inv = Inventory("data/raw/pricing.yaml")
    ops = ParametricOps(vessels, inv)
    
    # Mock a vessel for cloning
    vessel_id = "cloning_tube_1"
    ops.vessels.vessels[vessel_id] = vessels.get("flask_t25") # Use flask as generic container

    # 1. Library Design
    print("\n[Step 1] Library Design")
    genes = [up.GeneTarget(f"GENE_{i}", f"ID_{i}") for i in range(100)] # 100 genes
    design = up.LibraryDesign("Test_Lib_100", genes)
    op_design = ops.op_design_guides(design)
    print(f"  Designed {design.total_guides()} guides.")
    print(f"  Cost: ${op_design.material_cost_usd:.2f} (Mat) + ${op_design.instrument_cost_usd:.2f} (Inst)")

    # 2. Order Oligos
    print("\n[Step 2] Order Oligos")
    pool = up.OligoPool(design, vendor="Twist Bioscience")
    op_order = ops.op_order_oligos(pool)
    print(f"  Vendor: {pool.vendor}")
    print(f"  Cost: ${op_order.material_cost_usd:.2f} (Mat) + ${op_order.instrument_cost_usd:.2f} (Inst)")
    
    # 3. Cloning (Golden Gate)
    print("\n[Step 3] Golden Gate Assembly")
    op_gg = ops.op_golden_gate_assembly(vessel_id)
    print(f"  Cost: ${op_gg.material_cost_usd:.2f} (Mat) + ${op_gg.instrument_cost_usd:.2f} (Inst)")
    
    # 4. Transformation
    print("\n[Step 4] Transformation")
    op_trans = ops.op_transformation(vessel_id)
    print(f"  Cost: ${op_trans.material_cost_usd:.2f} (Mat) + ${op_trans.instrument_cost_usd:.2f} (Inst)")

    # 5. Plasmid Prep
    print("\n[Step 5] Plasmid Maxiprep")
    op_prep = ops.op_plasmid_prep(vessel_id)
    print(f"  Cost: ${op_prep.material_cost_usd:.2f} (Mat) + ${op_prep.instrument_cost_usd:.2f} (Inst)")

    # 6. NGS Verification
    print("\n[Step 6] NGS Verification")
    op_ngs = ops.op_ngs_verification(vessel_id)
    print(f"  Cost: ${op_ngs.material_cost_usd:.2f} (Mat) + ${op_ngs.instrument_cost_usd:.2f} (Inst)")

    # 7. Virus Production
    print("\n[Step 7] Virus Production (Transfection + Harvest)")
    op_transfect = ops.op_transfect_hek293t(vessel_id)
    op_harvest = ops.op_harvest_virus(vessel_id)
    print(f"  Transfection Cost: ${op_transfect.material_cost_usd:.2f}")
    print(f"  Harvest Cost: ${op_harvest.material_cost_usd:.2f}")

    # Total Cost
    total_mat = (op_design.material_cost_usd + op_order.material_cost_usd + 
                 op_gg.material_cost_usd + op_trans.material_cost_usd + 
                 op_prep.material_cost_usd + op_ngs.material_cost_usd + 
                 op_transfect.material_cost_usd + op_harvest.material_cost_usd)
    
    print("\n" + "=" * 80)
    print(f"TOTAL UPSTREAM COST: ${total_mat:.2f}")
    print("=" * 80)
    
    if total_mat > 1500 and total_mat < 3500:
        print("[PASS] Cost is within expected range ($1.5k-$3.5k for a small library).")
    else:
        print(f"[WARN] Cost seems off. Expected ~$2000-$3000.")

if __name__ == "__main__":
    verify_upstream_workflow()
