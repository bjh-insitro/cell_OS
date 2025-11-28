"""
Tests for Multi-Assay Simulation
"""

import pytest
from cell_os.simulation.multi_assay import (
    MultiAssaySimulator,
    AssayType,
    FlowCytometryResult,
    ImagingResult,
    qPCRResult,
    ELISAResult,
    WesternBlotResult
)


class TestMultiAssaySimulator:
    
    def setup_method(self):
        self.simulator = MultiAssaySimulator(random_seed=42)
    
    def test_flow_cytometry_basic(self):
        """Test basic flow cytometry simulation."""
        result = self.simulator.simulate_flow_cytometry(viability=0.95)
        
        assert isinstance(result, FlowCytometryResult)
        assert 90 < result.live_cells_percent < 100
        assert result.dead_cells_percent >= 0
        assert result.apoptotic_cells_percent >= 0
        
        # Populations should sum to ~100%
        total = result.live_cells_percent + result.dead_cells_percent + result.apoptotic_cells_percent
        assert 99 < total < 101
    
    def test_flow_cytometry_with_treatment(self):
        """Test flow cytometry with treatment effect."""
        # No treatment
        control = self.simulator.simulate_flow_cytometry(viability=0.95, treatment_effect=0.0)
        
        # With treatment
        treated = self.simulator.simulate_flow_cytometry(viability=0.95, treatment_effect=0.8)
        
        # Treatment should increase apoptosis
        assert treated.apoptotic_cells_percent > control.apoptotic_cells_percent
    
    def test_flow_cytometry_markers(self):
        """Test flow cytometry with cell markers."""
        markers = {"CD4": 45.0, "CD8": 30.0}
        result = self.simulator.simulate_flow_cytometry(
            viability=0.95,
            markers=markers
        )
        
        assert "CD4" in result.marker_positive_percent
        assert "CD8" in result.marker_positive_percent
        
        # Should be close to input values
        assert 40 < result.marker_positive_percent["CD4"] < 50
        assert 25 < result.marker_positive_percent["CD8"] < 35
    
    def test_imaging_basic(self):
        """Test basic imaging simulation."""
        result = self.simulator.simulate_imaging(
            cell_count=1000,
            viability=0.95
        )
        
        assert isinstance(result, ImagingResult)
        assert result.cell_count > 0
        assert result.mean_cell_area > 0
        assert result.mean_nuclear_area > 0
        assert 0 < result.morphology_score <= 1
        assert 0 < result.field_quality <= 1
    
    def test_imaging_with_treatment(self):
        """Test imaging with treatment effect."""
        # No treatment
        control = self.simulator.simulate_imaging(
            cell_count=1000,
            viability=0.95,
            treatment_effect=0.0
        )
        
        # With treatment
        treated = self.simulator.simulate_imaging(
            cell_count=1000,
            viability=0.95,
            treatment_effect=0.8
        )
        
        # Treatment should reduce morphology score
        assert treated.morphology_score < control.morphology_score
        
        # Treatment should increase N/C ratio
        assert treated.nuclear_cytoplasmic_ratio > control.nuclear_cytoplasmic_ratio
    
    def test_imaging_organelles(self):
        """Test imaging organelle features."""
        result = self.simulator.simulate_imaging(
            cell_count=1000,
            viability=0.95,
            treatment_effect=0.5
        )
        
        assert "mitochondria_intensity" in result.organelle_features
        assert "lysosome_count" in result.organelle_features
        assert "stress_granules" in result.organelle_features
    
    def test_qpcr_upregulation(self):
        """Test qPCR with upregulated gene."""
        result = self.simulator.simulate_qpcr(
            gene_name="IL6",
            fold_change=10.0  # 10-fold upregulation
        )
        
        assert isinstance(result, qPCRResult)
        assert result.gene_name == "IL6"
        assert result.fold_change > 5.0  # Should be upregulated
        assert result.ct_value < 25.0  # Lower Ct for higher expression
        assert 0 < result.p_value < 1
    
    def test_qpcr_downregulation(self):
        """Test qPCR with downregulated gene."""
        result = self.simulator.simulate_qpcr(
            gene_name="GAPDH",
            fold_change=0.1  # 10-fold downregulation
        )
        
        assert result.fold_change < 0.5  # Should be downregulated
        assert result.ct_value > 25.0  # Higher Ct for lower expression
    
    def test_elisa_basic(self):
        """Test basic ELISA simulation."""
        result = self.simulator.simulate_elisa(
            analyte="TNF-alpha",
            true_concentration=250.0  # pg/mL
        )
        
        assert isinstance(result, ELISAResult)
        assert result.analyte == "TNF-alpha"
        assert result.concentration_pg_ml > 0
        assert 0 < result.od_450nm < 3.0
        assert result.cv_percent > 0
    
    def test_elisa_range_detection(self):
        """Test ELISA detects out-of-range values."""
        # Within range
        in_range = self.simulator.simulate_elisa("IL-6", 500.0)
        assert in_range.within_range
        
        # Too low
        too_low = self.simulator.simulate_elisa("IL-6", 1.0)
        assert not too_low.within_range
        
        # Too high
        too_high = self.simulator.simulate_elisa("IL-6", 10000.0)
        assert not too_high.within_range
    
    def test_western_blot_basic(self):
        """Test basic Western blot simulation."""
        result = self.simulator.simulate_western_blot(
            protein="p53",
            expression_level=1.5,  # 1.5x control
            molecular_weight=53.0
        )
        
        assert isinstance(result, WesternBlotResult)
        assert result.protein == "p53"
        assert result.band_intensity > 0
        assert result.normalized_intensity > 0
        assert 50 < result.molecular_weight_kda < 56  # Close to 53
    
    def test_western_blot_expression_levels(self):
        """Test Western blot with different expression levels."""
        # Low expression
        low = self.simulator.simulate_western_blot("GAPDH", 0.5)
        
        # High expression
        high = self.simulator.simulate_western_blot("GAPDH", 2.0)
        
        # Higher expression should have higher intensity
        assert high.band_intensity > low.band_intensity


class TestAssayReproducibility:
    
    def test_reproducible_with_seed(self):
        """Test that results are reproducible with same seed."""
        sim1 = MultiAssaySimulator(random_seed=42)
        sim2 = MultiAssaySimulator(random_seed=42)
        
        result1 = sim1.simulate_flow_cytometry(viability=0.95)
        result2 = sim2.simulate_flow_cytometry(viability=0.95)
        
        assert result1.live_cells_percent == result2.live_cells_percent
        assert result1.mean_fsc == result2.mean_fsc
    
    def test_different_without_seed(self):
        """Test that results vary without fixed seed."""
        sim1 = MultiAssaySimulator()
        sim2 = MultiAssaySimulator()
        
        result1 = sim1.simulate_flow_cytometry(viability=0.95)
        result2 = sim2.simulate_flow_cytometry(viability=0.95)
        
        # Percentages might round to same value, but scatter should differ
        assert result1.mean_fsc != result2.mean_fsc or result1.mean_ssc != result2.mean_ssc
