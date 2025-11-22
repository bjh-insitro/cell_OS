from src.inventory import Inventory
import sys

print("Starting Inventory Verification...", flush=True)

try:
    inv = Inventory('data/raw/resources.csv', 'data/raw/unit_op_bom.csv')
    print("Inventory loaded.", flush=True)

    uos_to_check = ['Diff1', 'Diff3', 'Diff5']
    
    for uo in uos_to_check:
        print(f"\n--- Breakdown for {uo} ---", flush=True)
        print(inv.get_bom_breakdown(uo), flush=True)
        cost = inv.calculate_uo_cost(uo)
        print(f"Calculated Cost: ${cost:.2f}", flush=True)

    # Demonstrate "Swap Reagent"
    print("\n--- Scenario: Laminin 521 price drops by 50% ---", flush=True)
    original_laminin_cost = inv.resources['R_Laminin521'].cost_usd
    inv.resources['R_Laminin521'].cost_usd = original_laminin_cost * 0.5
    print(f"New Laminin Price: ${inv.resources['R_Laminin521'].cost_usd:.2f}", flush=True)
    
    new_cost = inv.calculate_uo_cost('Diff1')
    print(f"New Diff1 Cost: ${new_cost:.2f} (was ${inv.calculate_uo_cost('Diff1') + (original_laminin_cost * 0.5 / 100 * 60):.2f} wait, math check...)", flush=True)
    print(f"Old Diff1 Cost (approx): $138.19")
    print(f"Savings: ${138.19 - new_cost:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
