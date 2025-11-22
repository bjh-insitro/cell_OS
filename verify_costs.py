from src.unit_ops import UnitOpLibrary, AssayRecipe
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

    weekly_maintenance = AssayRecipe('Weekly_Maintenance_2_Lines', {'cell_prep': [('C_Pass_T75', 8)]})
    print("Recipe created", flush=True)

    score = weekly_maintenance.derive_score(lib)
    print("Score derived", flush=True)
    print(score, flush=True)
    print(f"Annual Cost (52 weeks): ${score.total_usd * 52:.2f}", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
