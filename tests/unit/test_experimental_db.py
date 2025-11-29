"""
Tests for ExperimentalDatabase
"""

import pytest
import tempfile
import os
import pandas as pd
from cell_os.experimental_db import ExperimentalDatabase

class TestExperimentalDatabase:
    
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = ExperimentalDatabase(self.temp_db.name)
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_add_and_retrieve_measurements(self):
        """Test adding and retrieving measurements."""
        data = {
            "plate_id": ["P1", "P1"],
            "well_id": ["A01", "A02"],
            "cell_line": ["HepG2", "HepG2"],
            "compound": ["DMSO", "DrugX"],
            "dose_uM": [0.0, 1.0],
            "time_h": [24.0, 24.0],
            "raw_signal": [1000.0, 500.0],
            "is_control": [1, 0],
            "date": ["2025-01-01", "2025-01-01"],
            "viability_norm": [1.0, 0.5]
        }
        df = pd.DataFrame(data)
        
        self.db.add_measurements(df)
        
        # Retrieve all
        retrieved = self.db.get_measurements()
        assert len(retrieved) == 2
        assert retrieved.iloc[0]["plate_id"] == "P1"
        assert retrieved.iloc[1]["compound"] == "DrugX"
        
    def test_filtering(self):
        """Test filtering measurements."""
        data = {
            "plate_id": ["P1", "P2"],
            "well_id": ["A01", "A01"],
            "cell_line": ["HepG2", "HeLa"],
            "compound": ["DMSO", "DMSO"],
            "dose_uM": [0.0, 0.0],
            "time_h": [24.0, 24.0],
            "raw_signal": [1000.0, 1000.0],
            "is_control": [1, 1],
            "date": ["2025-01-01", "2025-01-01"],
            "viability_norm": [1.0, 1.0]
        }
        df = pd.DataFrame(data)
        self.db.add_measurements(df)
        
        # Filter by cell line
        hepg2 = self.db.get_measurements(cell_line="HepG2")
        assert len(hepg2) == 1
        assert hepg2.iloc[0]["cell_line"] == "HepG2"
        
        # Filter by plate
        p2 = self.db.get_measurements(plate_id="P2")
        assert len(p2) == 1
        assert p2.iloc[0]["plate_id"] == "P2"
        
    def test_summary_stats(self):
        """Test summary statistics."""
        data = {
            "plate_id": ["P1", "P2"],
            "well_id": ["A01", "A01"],
            "cell_line": ["HepG2", "HeLa"],
            "compound": ["DMSO", "DrugX"],
            "dose_uM": [0.0, 1.0],
            "time_h": [24.0, 24.0],
            "raw_signal": [1000.0, 500.0],
            "is_control": [1, 0],
            "date": ["2025-01-01", "2025-01-01"],
            "viability_norm": [1.0, 0.5]
        }
        df = pd.DataFrame(data)
        self.db.add_measurements(df)
        
        stats = self.db.get_summary_stats()
        assert stats["total_measurements"] == 2
        assert len(stats["cell_lines"]) == 2
        assert len(stats["compounds"]) == 2
        assert stats["plates"] == 2
