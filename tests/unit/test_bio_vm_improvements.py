"""
Tests for BiologicalVirtualMachine Improvements (Lag Phase & Edge Effects)
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

class TestBioVMImprovements:
    
    def setup_method(self):
        self.vm = BiologicalVirtualMachine(simulation_speed=0.0, use_database=False)
        
    def test_lag_phase(self):
        """Test that growth is slower immediately after seeding."""
        # Seed two vessels
        # 1. "Fresh" vessel (just seeded)
        self.vm.seed_vessel("fresh", "HEK293T", 1e5)
        
        # 2. "Acclimated" vessel (seeded 24h ago)
        # We simulate this by manually setting seed_time
        self.vm.seed_vessel("acclimated", "HEK293T", 1e5)
        self.vm.vessel_states["acclimated"].seed_time = -24.0 # Seeded 24h ago
        
        # Advance 1 hour
        self.vm.advance_time(1.0)
        
        fresh_count = self.vm.vessel_states["fresh"].cell_count
        acclimated_count = self.vm.vessel_states["acclimated"].cell_count
        
        # Acclimated should have grown more
        # Fresh is in lag phase (linear ramp 0->1 over 12h), so at t=0 it grows very slowly
        assert acclimated_count > fresh_count
        
        # Verify fresh growth is minimal (lag factor close to 0 at start)
        # Expected growth for acclimated: exp(ln(2)/24 * 1) ~= 1.029 (2.9%)
        # Fresh starts at lag=0, ramps to 1/12 in first hour. Avg lag ~ 0.04.
        growth_ratio_fresh = fresh_count / 1e5
        growth_ratio_acc = acclimated_count / 1e5
        
        assert growth_ratio_acc > 1.02 # Should be normal growth
        assert growth_ratio_fresh < 1.01 # Should be suppressed

    def test_edge_effects(self):
        """Test that edge wells grow slower (comparing growth RATES, not counts).

        Hardware artifacts during seeding can cause different initial cell counts,
        so we must compare growth rates rather than final counts to test edge effects.
        """
        # Seed center well vs edge well
        # Both acclimated to ignore lag phase
        self.vm.seed_vessel("Plate1_B06", "HEK293T", 1e5) # Center
        self.vm.seed_vessel("Plate1_A01", "HEK293T", 1e5) # Edge (Row A, Col 1)

        # Skip lag phase
        self.vm.vessel_states["Plate1_B06"].seed_time = -24.0
        self.vm.vessel_states["Plate1_A01"].seed_time = -24.0

        # Record initial counts AFTER hardware artifacts applied during seeding
        center_initial = self.vm.vessel_states["Plate1_B06"].cell_count
        edge_initial = self.vm.vessel_states["Plate1_A01"].cell_count

        # Advance 24 hours
        self.vm.advance_time(24.0)

        center_final = self.vm.vessel_states["Plate1_B06"].cell_count
        edge_final = self.vm.vessel_states["Plate1_A01"].cell_count

        # Calculate growth multipliers (not raw counts)
        center_growth = center_final / center_initial
        edge_growth = edge_final / edge_initial

        # Edge should grow SLOWER due to penalty (evaporation/temperature gradients)
        assert edge_growth < center_growth, (
            f"Edge well should grow slower than center: "
            f"edge_growth={edge_growth:.3f}x vs center_growth={center_growth:.3f}x"
        )

        # Default edge penalty is 0.15 (15% reduction in growth rate)
        # Verify edge grows noticeably slower (at least 10% less growth)
        growth_ratio = (edge_growth - 1) / (center_growth - 1) if center_growth > 1 else 1
        assert growth_ratio < 0.95, (
            f"Edge penalty should reduce growth by at least 5%: "
            f"growth_ratio={growth_ratio:.3f}"
        )
        print(f"Center growth: {center_growth:.3f}x, Edge growth: {edge_growth:.3f}x, Ratio: {growth_ratio:.3f}")
        
    def test_edge_detection(self):
        """Test the regex for edge detection."""
        assert self.vm._is_edge_well("Plate1_A01") # Row A, Col 1
        assert self.vm._is_edge_well("Plate1_H12") # Row H, Col 12
        assert self.vm._is_edge_well("B01")        # Col 1
        assert self.vm._is_edge_well("G12")        # Col 12
        assert self.vm._is_edge_well("A06")        # Row A
        
        assert not self.vm._is_edge_well("Plate1_B02") # Center
        assert not self.vm._is_edge_well("C06")        # Center
        assert not self.vm._is_edge_well("G11")        # Center
