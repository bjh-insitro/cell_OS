from src.unit_ops import UnitOpLibrary, get_mcb_to_wcb_recipe
import sys

print("Starting verification...", flush=True)

try:
    lib = UnitOpLibrary([
        'data/raw/unit_ops_genetic_supply.csv', 
        'data/raw/unit_ops_cell_prep.csv', 
        'data/raw/unit_ops_phenotyping.csv', 
        'data/raw/unit_ops_compute.csv'
    ])
    print(f"Library loaded with {len(lib.ops)} ops", flush=True)

    print("\n--- Immortalized MCB -> WCB ---", flush=True)
    recipe_imm = get_mcb_to_wcb_recipe("immortalized")
    score_imm = recipe_imm.derive_score(lib)
    print(score_imm, flush=True)
    print(f"Total Consumables: ${score_imm.total_usd:.2f}", flush=True)
    print(f"Cost per WCB vial: ${score_imm.total_usd / 10:.2f}", flush=True)

    print("\n--- iPSC MCB -> WCB ---", flush=True)
    recipe_ipsc = get_mcb_to_wcb_recipe("iPSC")
    score_ipsc = recipe_ipsc.derive_score(lib)
    print(score_ipsc, flush=True)
    print(f"Total Consumables: ${score_ipsc.total_usd:.2f}", flush=True)
    print(f"Cost per WCB vial: ${score_ipsc.total_usd / 10:.2f}", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
