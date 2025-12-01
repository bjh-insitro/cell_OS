"""
Tests for BiologicalVirtualMachine CellROX and segmentation quality simulation.
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


class TestBiologicalVMExtensions:
    """Test new CellROX and segmentation quality methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.vm = BiologicalVirtualMachine(simulation_speed=0.001)
        
    def test_cellrox_signal_baseline(self):
        """Test CellROX signal at zero dose (baseline)."""
        # Seed a vessel
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        # Measure baseline signal (no tBHP)
        signal = self.vm.simulate_cellrox_signal("test_well", "tbhp", 0.0)
        
        # Should be around baseline (100 AU for U2OS)
        assert 80 < signal < 120  # Allow for noise
        
    def test_cellrox_signal_dose_response(self):
        """Test CellROX signal increases with dose."""
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        # Test increasing doses
        signal_0 = self.vm.simulate_cellrox_signal("test_well", "tbhp", 0.0)
        signal_25 = self.vm.simulate_cellrox_signal("test_well", "tbhp", 25.0)
        signal_50 = self.vm.simulate_cellrox_signal("test_well", "tbhp", 50.0)  # EC50
        signal_100 = self.vm.simulate_cellrox_signal("test_well", "tbhp", 100.0)
        
        # Signal should increase with dose
        assert signal_0 < signal_25 < signal_50 < signal_100
        
        # At EC50, should be roughly halfway to max
        # max_fold = 5.0, so max signal ≈ 500
        # At EC50, should be around 300 (baseline + half of increase)
        assert 200 < signal_50 < 400
        
    def test_cellrox_signal_cell_line_differences(self):
        """Test different cell lines have different CellROX responses."""
        # Seed vessels for different cell lines
        self.vm.seed_vessel("u2os_well", "U2OS", 1e6)
        self.vm.seed_vessel("hepg2_well", "HepG2", 1e6)
        self.vm.seed_vessel("a549_well", "A549", 1e6)
        
        dose = 50.0  # Test at same dose
        
        signal_u2os = self.vm.simulate_cellrox_signal("u2os_well", "tbhp", dose)
        signal_hepg2 = self.vm.simulate_cellrox_signal("hepg2_well", "tbhp", dose)
        signal_a549 = self.vm.simulate_cellrox_signal("a549_well", "tbhp", dose)
        
        # All should be positive
        assert signal_u2os > 0
        assert signal_hepg2 > 0
        assert signal_a549 > 0
        
        # A549 should have highest signal (most sensitive, EC50=40)
        # HepG2 should have lowest (most resistant, EC50=75)
        # This is at dose=50, which is above A549 EC50 but below HepG2 EC50
        assert signal_a549 > signal_u2os  # A549 more sensitive
        
    def test_segmentation_quality_baseline(self):
        """Test segmentation quality at zero dose (perfect)."""
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        quality = self.vm.simulate_segmentation_quality("test_well", "tbhp", 0.0)
        
        # Should be near 1.0 (perfect segmentation)
        assert 0.8 < quality <= 1.0
        
    def test_segmentation_quality_degradation(self):
        """Test segmentation quality degrades with high dose."""
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        # Test increasing doses
        quality_0 = self.vm.simulate_segmentation_quality("test_well", "tbhp", 0.0)
        quality_100 = self.vm.simulate_segmentation_quality("test_well", "tbhp", 100.0)
        quality_200 = self.vm.simulate_segmentation_quality("test_well", "tbhp", 200.0)  # IC50
        quality_400 = self.vm.simulate_segmentation_quality("test_well", "tbhp", 400.0)
        
        # Quality should decrease with dose
        assert quality_0 > quality_100 > quality_200 > quality_400
        
        # At very high dose, should approach min_quality (0.3 for U2OS)
        assert quality_400 < 0.5
        
    def test_segmentation_quality_viability_dependence(self):
        """Test segmentation quality depends on viability."""
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        # Reduce viability by treating with high dose
        self.vm.treat_with_compound("test_well", "tbhp", 150.0)  # High dose kills cells
        
        # Segmentation quality should be reduced even at low tBHP dose
        # because viability is low
        quality = self.vm.simulate_segmentation_quality("test_well", "tbhp", 10.0)
        
        # Should be lower than perfect due to low viability
        assert quality < 0.9
        
    def test_multi_readout_consistency(self):
        """Test that all three readouts work together."""
        self.vm.seed_vessel("test_well", "U2OS", 1e6)
        
        dose = 75.0  # Moderate dose
        
        # Get all three readouts
        self.vm.treat_with_compound("test_well", "tbhp", dose)
        viability_result = self.vm.get_vessel_state("test_well")
        cellrox = self.vm.simulate_cellrox_signal("test_well", "tbhp", dose)
        segmentation = self.vm.simulate_segmentation_quality("test_well", "tbhp", dose)
        
        # All should be valid
        assert 0 < viability_result["viability"] <= 1.0
        assert cellrox > 0
        assert 0 < segmentation <= 1.0
        
        # At this dose:
        # - Viability should be reduced (IC50=100, so ~60-70% viable)
        # - CellROX should be elevated (EC50=50, so high signal)
        # - Segmentation should be good (degradation IC50=200, so still decent)
        assert viability_result["viability"] < 0.8  # Some cell death
        assert cellrox > 200  # Elevated signal
        assert segmentation > 0.45  # Still segmentable with moderate quality margin
        
    def test_nonexistent_vessel(self):
        """Test methods handle nonexistent vessels gracefully."""
        cellrox = self.vm.simulate_cellrox_signal("nonexistent", "tbhp", 50.0)
        segmentation = self.vm.simulate_segmentation_quality("nonexistent", "tbhp", 50.0)
        
        assert cellrox == 0.0
        assert segmentation == 0.0
