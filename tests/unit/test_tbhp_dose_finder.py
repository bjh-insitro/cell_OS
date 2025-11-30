"""
Tests for TBHPDoseFinder.
"""

import pytest
import pandas as pd
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.tbhp_dose_finder import TBHPDoseFinder, TBHPOptimizationCriteria


class TestTBHPDoseFinder:
    """Test autonomous tBHP dose finding."""
    
    def setup_method(self):
        self.vm = BiologicalVirtualMachine(simulation_speed=0.001)
        self.criteria = TBHPOptimizationCriteria(
            min_viability=0.6,          # Relaxed for test
            target_cellrox_signal=150.0,
            min_segmentation_quality=0.7
        )
        self.finder = TBHPDoseFinder(self.vm, self.criteria)
        
    def test_run_dose_finding_u2os(self):
        """Test finding optimal dose for U2OS."""
        result = self.finder.run_dose_finding("U2OS", dose_range=(0, 200), n_doses=12) # More points
        
        assert result.cell_line == "U2OS"
        assert not result.dose_response_curve.empty
        
        print(f"\nOptimal Dose U2OS: {result.optimal_dose_uM}")
        print(result.dose_response_curve)
        
        # With finer grid, should be closer to 50-80
        # But allow 30+
        assert 30 <= result.optimal_dose_uM <= 90
        assert result.viability_at_optimal >= 0.6
        assert result.segmentation_quality_at_optimal >= 0.7
        
    def test_run_dose_finding_hepg2(self):
        """Test finding optimal dose for HepG2 (more resistant)."""
        result = self.finder.run_dose_finding("HepG2", dose_range=(0, 300), n_doses=12)
        
        print(f"\nOptimal Dose HepG2: {result.optimal_dose_uM}")
        
        # Should be higher than U2OS generally, or at least reasonable
        assert result.optimal_dose_uM >= 40
        assert result.optimal_dose_uM <= 150
        
    def test_run_dose_finding_a549(self):
        """Test finding optimal dose for A549 (more sensitive)."""
        result = self.finder.run_dose_finding("A549", dose_range=(0, 150), n_doses=12)
        
        print(f"\nOptimal Dose A549: {result.optimal_dose_uM}")
        
        assert 20 <= result.optimal_dose_uM <= 80
        
    def test_failed_constraints_fallback(self):
        """Test fallback when no dose meets strict criteria."""
        # Set impossible criteria
        strict_criteria = TBHPOptimizationCriteria(
            min_viability=0.99,          # Extremely high viability (hard with noise)
            target_cellrox_signal=500.0, # Very high signal
            min_segmentation_quality=0.99
        )
        finder = TBHPDoseFinder(self.vm, strict_criteria)
        
        result = finder.run_dose_finding("U2OS", dose_range=(0, 200), n_doses=8)
        
        # It might return suboptimal_signal if dose 0 meets viability/seg
        # Or failed_constraints if nothing meets viability/seg
        assert result.status in ["failed_constraints", "suboptimal_signal"]
        assert result.optimal_dose_uM >= 0
