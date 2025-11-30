"""
Tests for BiologicalVirtualMachine
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, VesselState


class TestBiologicalVirtualMachine:
    
    def setup_method(self):
        self.vm = BiologicalVirtualMachine(simulation_speed=0.0)  # Instant execution
        
    def test_seed_and_count(self):
        """Test basic seeding and cell counting."""
        self.vm.seed_vessel("T75_1", "HEK293T", initial_count=1e6, capacity=1e7)
        
        result = self.vm.count_cells("T75_1", vessel_id="T75_1")
        
        assert result["status"] == "success"
        assert 0.8e6 < result["count"] < 1.2e6  # Within noise range
        assert 0.95 <= result["viability"] <= 1.0
        assert result["passage_number"] == 0
        
    def test_cell_growth(self):
        """Test that cells grow over time."""
        self.vm.seed_vessel("T75_1", "HEK293T", initial_count=1e6)
        
        # Incubate for 24 hours (one doubling time for HEK293T)
        self.vm.incubate(24 * 3600, 37.0)
        
        result = self.vm.count_cells("T75_1", vessel_id="T75_1")
        
        # Should approximately double (with lag phase, slightly less)
        # Lag phase reduces growth in first 12h, so expect ~1.7x instead of 2x
        assert 1.6e6 < result["count"] < 2.0e6
        
    def test_passage(self):
        """Test cell passaging."""
        self.vm.seed_vessel("T75_1", "HEK293T", initial_count=4e6)
        
        result = self.vm.passage_cells("T75_1", "T75_2", split_ratio=4.0)
        
        assert result["status"] == "success"
        assert 0.9e6 < result["cells_transferred"] < 1.1e6
        assert result["passage_number"] == 1
        
        # Check new vessel
        new_state = self.vm.get_vessel_state("T75_2")
        assert new_state is not None
        assert new_state["passage_number"] == 1
        
    def test_compound_treatment(self):
        """Test dose-response to compound treatment."""
        self.vm.seed_vessel("well_A1", "HEK293T", initial_count=1e5)
        
        # Treat with staurosporine at IC50 (should give ~50% viability)
        result = self.vm.treat_with_compound("well_A1", "staurosporine", dose_uM=0.05)
        
        assert result["status"] == "success"
        assert 0.4 < result["viability_effect"] < 0.6  # ~50% with noise
        
        # Verify vessel state updated
        state = self.vm.get_vessel_state("well_A1")
        assert state["viability"] < 0.6
        assert "staurosporine" in state["compounds"]
        
    def test_dose_response_curve(self):
        """Test that we get a proper dose-response curve."""
        doses = [0.001, 0.01, 0.05, 0.1, 1.0]  # IC50 for HEK293T/stauro is 0.05
        viabilities = []
        
        for i, dose in enumerate(doses):
            vessel_id = f"well_{i}"
            self.vm.seed_vessel(vessel_id, "HEK293T", initial_count=1e5)
            result = self.vm.treat_with_compound(vessel_id, "staurosporine", dose_uM=dose)
            viabilities.append(result["viability_effect"])
            
        # Check monotonic decrease
        assert viabilities[0] > viabilities[-1]
        # Check IC50 gives ~50% viability
        assert 0.3 < viabilities[2] < 0.7
        
    def test_confluence_effects(self):
        """Test that over-confluence reduces viability."""
        self.vm.seed_vessel("T75_1", "HEK293T", initial_count=1e6, capacity=1e7)
        
        # Grow for 5 doubling times (32x growth -> over-confluent)
        self.vm.incubate(5 * 24 * 3600, 37.0)
        
        result = self.vm.count_cells("T75_1", vessel_id="T75_1")
        
        # Should be over-confluent and viability should drop
        assert result["confluence"] > 0.9
        assert result["viability"] < 0.95  # Some viability loss
        
    def test_multiple_vessels(self):
        """Test tracking multiple vessels simultaneously."""
        self.vm.seed_vessel("T75_1", "HEK293T", initial_count=1e6)
        self.vm.seed_vessel("T75_2", "HeLa", initial_count=2e6)
        
        # Skip lag phase for clearer growth rate comparison
        self.vm.vessel_states["T75_1"].seed_time = -24.0
        self.vm.vessel_states["T75_2"].seed_time = -24.0
        
        # Incubate both
        self.vm.incubate(24 * 3600, 37.0)
        
        # HeLa should grow faster (20h doubling time vs 24h)
        hek_result = self.vm.count_cells("T75_1", vessel_id="T75_1")
        hela_result = self.vm.count_cells("T75_2", vessel_id="T75_2")
        
        # HeLa should have higher fold-change
        hek_fold = hek_result["count"] / 1e6
        hela_fold = hela_result["count"] / 2e6
        
        assert hela_fold > hek_fold
        
    def test_reproducibility(self):
        """Test that setting numpy seed gives reproducible results."""
        np.random.seed(42)
        vm1 = BiologicalVirtualMachine(simulation_speed=0.0)
        vm1.seed_vessel("T75_1", "HEK293T", initial_count=1e6)
        result1 = vm1.count_cells("T75_1", vessel_id="T75_1")
        
        np.random.seed(42)
        vm2 = BiologicalVirtualMachine(simulation_speed=0.0)
        vm2.seed_vessel("T75_1", "HEK293T", initial_count=1e6)
        result2 = vm2.count_cells("T75_1", vessel_id="T75_1")
        
        assert abs(result1["count"] - result2["count"]) < 1e3  # Very close
