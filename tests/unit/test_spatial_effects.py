"""
Tests for Spatial Effects Simulation
"""

import pytest
import numpy as np
from cell_os.simulation.spatial_effects import (
    SpatialEffectsSimulator,
    PlateGeometry,
    PLATE_96,
    PLATE_384
)


class TestPlateGeometry:
    
    def test_well_position_conversion(self):
        """Test converting between well IDs and positions."""
        plate = PLATE_96
        
        # Test A1 (top-left)
        row, col = plate.get_well_position("A1")
        assert row == 0 and col == 0
        
        # Test H12 (bottom-right for 96-well)
        row, col = plate.get_well_position("H12")
        assert row == 7 and col == 11
        
        # Test round-trip
        well_id = plate.get_well_id(3, 5)
        row, col = plate.get_well_position(well_id)
        assert row == 3 and col == 5
    
    def test_edge_detection(self):
        """Test edge well detection."""
        plate = PLATE_96
        
        # Corners are edges
        assert plate.is_edge_well(0, 0)  # A1
        assert plate.is_edge_well(7, 11)  # H12
        
        # Center is not edge
        assert not plate.is_edge_well(3, 5)
        
        # Top row is edge
        assert plate.is_edge_well(0, 5)
        
        # Left column is edge
        assert plate.is_edge_well(3, 0)
    
    def test_distance_from_center(self):
        """Test distance calculation."""
        plate = PLATE_96
        
        # Center should have distance ~0
        center_row = 3.5  # (7-1)/2
        center_col = 5.5  # (11-1)/2
        dist_center = plate.get_distance_from_center(int(center_row), int(center_col))
        assert dist_center < 1.0
        
        # Corner should be furthest
        dist_corner = plate.get_distance_from_center(0, 0)
        assert dist_corner > dist_center


class TestSpatialEffects:
    
    def setup_method(self):
        self.simulator = SpatialEffectsSimulator(PLATE_96, random_seed=42)
    
    def test_edge_evaporation(self):
        """Test that edge wells lose volume."""
        base_value = 100.0
        
        # Edge well should have reduced value
        edge_value = self.simulator.apply_edge_effects("A1", base_value, "evaporation")
        assert edge_value < base_value
        
        # Center well should be unchanged
        center_value = self.simulator.apply_edge_effects("D6", base_value, "evaporation")
        assert center_value == base_value
    
    def test_temperature_gradient(self):
        """Test temperature varies across plate."""
        temps = []
        for well_id in ["A1", "D6", "H12"]:
            temp = self.simulator.apply_temperature_gradient(well_id, base_temperature=37.0)
            temps.append(temp)
        
        # Should have variation
        assert max(temps) - min(temps) > 0.1
        
        # Should be close to 37°C
        assert all(36.5 < t < 37.5 for t in temps)
    
    def test_pipetting_error(self):
        """Test pipetting accuracy varies by position."""
        target = 100.0
        
        # Run multiple times to check variation
        volumes = []
        for _ in range(10):
            vol = self.simulator.apply_pipetting_error("A1", target)
            volumes.append(vol)
        
        # Should have variation
        assert np.std(volumes) > 0
        
        # Should be close to target
        assert 95 < np.mean(volumes) < 105
    
    def test_cross_contamination(self):
        """Test cross-contamination detection."""
        # Temporarily increase probability for testing
        original_prob = self.simulator.cross_contamination_prob
        self.simulator.cross_contamination_prob = 0.05  # 5% for testing
        
        contaminated = {"A1", "A2"}
        
        # A3 is adjacent to A2, might get contaminated
        # Run multiple times due to randomness
        contamination_events = 0
        for _ in range(1000):
            if self.simulator.check_cross_contamination("A3", contaminated):
                contamination_events += 1
        
        # Should have some contamination events
        assert contamination_events > 10  # With 5% rate, expect ~50
        
        # Restore original probability
        self.simulator.cross_contamination_prob = original_prob
    
    def test_plate_heatmap(self):
        """Test heatmap generation."""
        heatmap = self.simulator.generate_plate_heatmap("evaporation")
        
        # Should be correct shape
        assert heatmap.shape == (8, 12)
        
        # Edge wells should have non-zero values
        assert heatmap[0, 0] > 0  # A1
        assert heatmap[7, 11] > 0  # H12
        
        # Center wells should be zero
        assert heatmap[3, 5] == 0
    
    def test_full_plate_simulation(self):
        """Test simulating a complete plate experiment."""
        # Create base values for all wells
        base_values = {}
        for row in range(8):
            for col in range(12):
                well_id = PLATE_96.get_well_id(row, col)
                base_values[well_id] = 100.0
        
        # Simulate with all effects
        results = self.simulator.simulate_plate_experiment(
            base_values,
            apply_evaporation=True,
            apply_temperature=True,
            apply_pipetting=True
        )
        
        # Should have all wells
        assert len(results) == 96
        
        # Edge wells should differ from center
        edge_val = results["A1"]
        center_val = results["D6"]
        assert abs(edge_val - center_val) > 1.0  # Noticeable difference


class TestPlateFormats:
    
    def test_96_well_plate(self):
        """Test 96-well plate geometry."""
        assert PLATE_96.rows == 8
        assert PLATE_96.cols == 12
        assert PLATE_96.well_volume_ul == 200
    
    def test_384_well_plate(self):
        """Test 384-well plate geometry."""
        assert PLATE_384.rows == 16
        assert PLATE_384.cols == 24
        assert PLATE_384.well_volume_ul == 50
