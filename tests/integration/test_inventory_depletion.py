"""
Integration tests for inventory depletion tracking.

Tests resource consumption and availability checking.
"""

import os

import pytest
from cell_os.inventory import Inventory, BOMItem, OutOfStockError


def test_consume_success():
    """Test successful reagent consumption."""
    inventory = Inventory("data/raw/pricing.yaml")
    
    # Check initial stock
    initial_stock = inventory.resources["dmem_high_glucose"].stock_level
    
    # Consume some
    inventory.consume("dmem_high_glucose", 100.0, "mL")
    
    assert inventory.resources["dmem_high_glucose"].stock_level == initial_stock - 100.0
    print("✓ Consumption successful")


def test_consume_out_of_stock():
    """Test consumption failure when out of stock."""
    inventory = Inventory("data/raw/pricing.yaml")
   
    # Try to consume more than available
    resource_id = list(inventory.resources.keys())[0]
    huge_amount = inventory.resources[resource_id].stock_level + 1000.0
    
    with pytest.raises(Exception):  # OutOfStockError
        inventory.consume(resource_id, huge_amount, inventory.resources[resource_id].logical_unit)
    
    # Exception raised, test passes
    print("✓ Out-of-stock handled correctly")


def test_check_availability_all_available():
    """Test availability check when all items in stock."""
    inventory = Inventory("data/raw/pricing.yaml")
    
    # Small BOM that should be available
    bom = [
        BOMItem("dmem_high_glucose", 50.0),
        BOMItem("fbs", 10.0)
    ]
    
    availability = inventory.check_availability(bom)
    
    assert availability["dmem_high_glucose"] == True
    assert availability["fbs"] == True
    print("✓ All items available")


def test_check_availability_partial():
    """Test availability check with some items unavailable."""
    inventory = Inventory("data/raw/pricing.yaml")
    
    # Deplete one resource
    resource_id_1 = "dmem_high_glucose"
    resource_id_2 = "fbs"
    inventory.resources[resource_id_1].stock_level = 100.0
    inventory.resources[resource_id_2].stock_level = 0.0

    # BOM with one available and one unavailable item
    bom = [
        BOMItem(resource_id_1, 5.0),   # Available
        BOMItem(resource_id_2, 5.0),   # Not available
    ]

    availability = inventory.check_availability(bom)

    # First item available, second not
    results = list(availability.values())
    assert True in results and False in results
    print("✓ Partial availability detected")


def test_restock():
    """Test restocking functionality."""
    inventory = Inventory("data/raw/pricing.yaml")
    
    resource_id = "dmem_high_glucose"
    initial = inventory.resources[resource_id].stock_level
    
    # Consume
    inventory.consume(resource_id, 100.0, "mL")
    
    # Restock
    inventory.add_stock(resource_id, 200.0, "mL")
    
    final = inventory.resources[resource_id].stock_level
    assert final == initial - 100.0 + 200.0
    print("✓ Restock working")


def test_consume_and_restock_cycle():
    """Test multiple consume/restock cycles."""
    inventory = Inventory("data/raw/pricing.yaml")
    
    resource_id = "fbs"
    transactions = [
        ("consume", 50.0),
        ("restock", 100.0),
        ("consume", 75.0),
        ("consume", 25.0),
        ("restock", 50.0)
    ]
    
    for action, amount in transactions:
        if action == "consume":
            inventory.consume(resource_id, amount, "mL")
        else:
            inventory.add_stock(resource_id, amount, "mL")
    
    # Should still have stock
    assert inventory.resources[resource_id].stock_level > 0
    print("✓ Multiple transactions handled")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
