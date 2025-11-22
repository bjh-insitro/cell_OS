from src.unit_ops import UnitOpLibrary, get_ipsc_maintenance_recipe
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

    recipe = get_ipsc_maintenance_recipe()
    print("Recipe created", flush=True)

    score = recipe.derive_score(lib)
    print("Score derived", flush=True)
    print(score, flush=True)
    print(f"Annual Cost (52 weeks): ${score.total_usd * 52:.2f}", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
