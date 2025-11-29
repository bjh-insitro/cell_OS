"""
Tests for HamiltonInterface
"""

import pytest
import os
import pandas as pd
import shutil
from cell_os.hardware.hamilton import HamiltonInterface

class TestHamiltonInterface:
    
    def setup_method(self):
        self.test_dir = "data/test_worklists"
        self.interface = HamiltonInterface(worklist_dir=self.test_dir)
        self.interface.connect()
        
    def teardown_method(self):
        self.interface.disconnect()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_worklist_generation(self):
        """Test generating a basic worklist."""
        self.interface.aspirate(100.0, "Plate1_A01")
        self.interface.dispense(100.0, "Plate2_A01")
        self.interface.move_plate("Pos1", "Pos2")
        
        filepath = self.interface.execute_batch("test_list.csv")
        
        assert os.path.exists(filepath)
        
        df = pd.read_csv(filepath)
        assert len(df) == 3
        assert df.iloc[0]["Action"] == "Aspirate"
        assert df.iloc[0]["Volume"] == 100.0
        assert df.iloc[1]["Action"] == "Dispense"
        assert df.iloc[2]["Action"] == "MovePlate"
        
    def test_mix_operation(self):
        """Test mix operation."""
        self.interface.mix(50.0, 5, "Plate1_A01")
        filepath = self.interface.execute_batch("mix_list.csv")
        
        df = pd.read_csv(filepath)
        assert len(df) == 1
        assert df.iloc[0]["Action"] == "Mix"
        assert df.iloc[0]["Repetitions"] == 5
