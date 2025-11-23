"""
Verification script for Inventory Management.

Tests stock tracking and OutOfStockError handling.
"""

from src.inventory import Inventory, OutOfStockError

def verify_inventory():
    print("=" * 70)
    print("INVENTORY MANAGEMENT VERIFICATION")
    print("=" * 70)
    
    # 1. Initialize Inventory
    print("\n[1] Initializing Inventory...")
    inv = Inventory('data/raw/pricing.yaml')
    
    # Pick a test resource (e.g., DMEM)
    # We need to find a valid resource ID from pricing.yaml
    # Let's assume 'R_DMEM_HighGlucose' exists or find one
    test_resource_id = list(inv.resources.keys())[0]
    resource = inv.resources[test_resource_id]
    
    print(f"  Test Resource: {resource.name} ({test_resource_id})")
    print(f"  Initial Stock: {resource.stock_level} {resource.logical_unit}")
    
    initial_stock = resource.stock_level
    
    # 2. Deplete Stock
    print("\n[2] Depleting Stock...")
    consume_amount = 1.0
    inv.deplete_stock(test_resource_id, consume_amount)
    
    current_stock = inv.resources[test_resource_id].stock_level
    print(f"  Consumed: {consume_amount}")
    print(f"  Current Stock: {current_stock}")
    
    if current_stock == initial_stock - consume_amount:
        print("  SUCCESS: Stock depleted correctly.")
    else:
        print(f"  FAILURE: Stock mismatch! Expected {initial_stock - consume_amount}, got {current_stock}")
        
    # 3. Test OutOfStockError
    print("\n[3] Testing OutOfStockError...")
    try:
        # Try to consume more than available
        excess_amount = current_stock + 100.0
        print(f"  Attempting to consume {excess_amount} (Available: {current_stock})...")
        inv.deplete_stock(test_resource_id, excess_amount)
        print("  FAILURE: Did not raise OutOfStockError!")
    except OutOfStockError as e:
        print(f"  SUCCESS: Caught expected error: {e}")
        
    # 4. Restock
    print("\n[4] Restocking...")
    inv.restock(test_resource_id, 100.0)
    print(f"  Restocked 100.0. New Level: {inv.resources[test_resource_id].stock_level}")

if __name__ == "__main__":
    verify_inventory()
