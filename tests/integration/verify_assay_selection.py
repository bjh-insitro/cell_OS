from src.assay_selector import GreedyROISelector, get_assay_candidates
from src.inventory import Inventory
from src.unit_ops import UnitOpLibrary
import sys

print("Starting Assay Selector Verification...", flush=True)

try:
    # Load dependencies
    inv = Inventory('data/raw/pricing.yaml', 'data/raw/unit_ops.yaml')
    lib = UnitOpLibrary([
        'data/raw/unit_ops_genetic_supply.csv', 
        'data/raw/unit_ops_cell_prep.csv', 
        'data/raw/unit_ops_phenotyping.csv', 
        'data/raw/unit_ops_compute.csv'
    ])
    
    # Get candidates
    candidates = get_assay_candidates(lib, inv)
    print(f"\nLoaded {len(candidates)} candidates:", flush=True)
    for c in candidates:
        print(f"- {c.recipe.name}: Cost=${c.cost_usd:.2f}, Info={c.information_score}, ROI={c.roi:.4f} bits/$", flush=True)
        
    selector = GreedyROISelector()
    
    # Scenario 1: Low Budget ($100)
    print("\n--- Scenario 1: Budget $100 ---", flush=True)
    choice = selector.select(candidates, 100.0)
    if choice:
        print(f"Selected: {choice.recipe.name} (Cost: ${choice.cost_usd:.2f})")
    else:
        print("No assay selected (Budget too low)")
        
    # Scenario 2: Medium Budget ($1000)
    print("\n--- Scenario 2: Budget $1000 ---", flush=True)
    choice = selector.select(candidates, 1000.0)
    if choice:
        print(f"Selected: {choice.recipe.name} (Cost: ${choice.cost_usd:.2f})")
        
    # Scenario 3: High Budget ($5000)
    print("\n--- Scenario 3: Budget $5000 ---", flush=True)
    choice = selector.select(candidates, 5000.0)
    if choice:
        print(f"Selected: {choice.recipe.name} (Cost: ${choice.cost_usd:.2f})")

except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
