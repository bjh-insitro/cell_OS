"""
Tests for Zombie POSH workflows.
"""

import pytest
from cell_os.workflows.zombie_posh_shopping_list import ZombiePOSHShoppingList


def test_zombie_shopping_list_import():
    """Test that ZombiePOSHShoppingList can be imported and instantiated."""
    generator = ZombiePOSHShoppingList(num_plates=2, wells_per_plate=6)
    assert generator.num_plates == 2
    assert generator.wells_per_plate == 6


def test_zombie_shopping_list_generation():
    """Test generating a shopping list."""
    generator = ZombiePOSHShoppingList(num_plates=1, wells_per_plate=6)
    items = generator.generate_shopping_list()
    
    assert len(items) > 0
    # Check for a core reagent
    assert any(item.name == "HiScribe T7 Quick High Yield RNA Synthesis Kit" for item in items)
