from src.inventory import Inventory
import sys

print("Starting YAML Inventory Verification...", flush=True)

try:
    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    print("Inventory loaded.", flush=True)

    uos_to_check = ['Diff1', 'Diff3', 'Diff5']
    
    for uo in uos_to_check:
        print(f"\n--- Breakdown for {uo} ---", flush=True)
        print(inv.get_bom_breakdown(uo), flush=True)
        cost = inv.calculate_uo_cost(uo)
        print(f"Calculated Cost: ${cost:.2f}", flush=True)

    # Demonstrate "Swap Reagent"
    print("\n--- Scenario: Laminin 521 price drops by 50% ---", flush=True)
    original_laminin_price = inv.resources['laminin_521'].unit_price_usd
    inv.resources['laminin_521'].unit_price_usd = original_laminin_price * 0.5
    print(f"New Laminin Price: ${inv.resources['laminin_521'].unit_price_usd:.2f}/ug", flush=True)
    
    new_cost = inv.calculate_uo_cost('Diff1')
    print(f"New Diff1 Cost: ${new_cost:.2f}")
    print(f"Old Diff1 Cost (approx): $139.43") # 136.63 + 2.8 overhead
    print(f"Savings: ${139.43 - new_cost:.2f}")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
