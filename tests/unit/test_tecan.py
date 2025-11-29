"""
Tests for TecanInterface
"""

import pytest
import os
import shutil
from cell_os.hardware.tecan import TecanInterface

class TestTecanInterface:
    
    def setup_method(self):
        self.test_dir = "data/test_worklists_tecan"
        self.interface = TecanInterface(worklist_dir=self.test_dir)
        self.interface.connect()
        
    def teardown_method(self):
        self.interface.disconnect()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_worklist_generation(self):
        """Test generating a basic GWL worklist."""
        self.interface.aspirate(100.0, "Plate1_1")
        self.interface.dispense(100.0, "Plate2_1")
        
        filepath = self.interface.execute_batch("test.gwl")
        
        assert os.path.exists(filepath)
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        assert len(lines) == 2
        assert lines[0].startswith("A;Plate1;;;1;;100.0;")
        assert lines[1].startswith("D;Plate2;;;1;;100.0;")
