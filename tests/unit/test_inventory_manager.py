"""
Tests for Inventory Manager
"""

import pytest
import tempfile
import os
from datetime import datetime
from cell_os.inventory import Inventory
from cell_os.inventory_manager import InventoryManager

class TestInventoryManager:
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        # Create a mock pricing file
        self.pricing_file = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
        with open(self.pricing_file.name, "w") as f:
            f.write("""
items:
  res-1:
    name: Test Reagent
    logical_unit: mL
    pack_size: 100
    pack_unit: mL
            """)
        
        self.inv = Inventory(self.pricing_file.name)
        self.manager = InventoryManager(self.inv, self.temp_db.name)
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
        if os.path.exists(self.pricing_file.name):
            os.unlink(self.pricing_file.name)
            
    def test_add_stock(self):
        self.manager.add_stock("res-1", 50.0)
        assert self.inv.resources["res-1"].stock_level == 50.0 + 1000.0 # Initial 10 packs * 100 = 1000 from Inventory.__init__
        
        # Wait, Inventory.__init__ sets stock to pack_size * 10.
        # Let's reset it to 0 for clarity in test
        self.inv.resources["res-1"].stock_level = 0
        self.manager._update_stock_level("res-1", 0)
        
        self.manager.add_stock("res-1", 50.0)
        assert self.inv.resources["res-1"].stock_level == 50.0
        
        lots = self.manager.get_lots("res-1")
        assert len(lots) == 2
        assert lots[0]["quantity"] == 50.0
        
    def test_consume_stock(self):
        # Reset stock
        self.inv.resources["res-1"].stock_level = 0
        self.manager._update_stock_level("res-1", 0)
        
        self.manager.add_stock("res-1", 100.0)
        self.manager.consume_stock("res-1", 30.0)
        
        assert self.inv.resources["res-1"].stock_level == 70.0
        
        lots = self.manager.get_lots("res-1")
        assert lots[0]["quantity"] == 70.0
        
    def test_fifo_consumption(self):
        # Reset stock
        self.inv.resources["res-1"].stock_level = 0
        self.manager._update_stock_level("res-1", 0)
        
        # Add old lot
        self.manager.add_stock("res-1", 50.0, lot_id="old-lot")
        # Add new lot
        self.manager.add_stock("res-1", 50.0, lot_id="new-lot")
        
        # Consume 60 (should take 50 from old, 10 from new)
        self.manager.consume_stock("res-1", 60.0)
        
        lots = self.manager.get_lots("res-1")
        old_lot = next(l for l in lots if l["lot_id"] == "old-lot")
        new_lot = next(l for l in lots if l["lot_id"] == "new-lot")
        
        assert old_lot["quantity"] == 0
        assert old_lot["status"] == "depleted"
        assert new_lot["quantity"] == 40.0
