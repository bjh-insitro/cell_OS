"""
Tests for Experimental Design Validation
"""

import pytest
import pandas as pd
import numpy as np
from cell_os.simulation.design_validation import (
    ExperimentalDesignValidator,
    PowerAnalysisResult,
    BatchConfoundingResult,
    ReplicationResult
)


class TestPowerAnalysis:
    
    def setup_method(self):
        self.validator = ExperimentalDesignValidator()
    
    def test_power_analysis_small_effect(self):
        """Test power analysis with small effect size."""
        result = self.validator.power_analysis(
            effect_size=0.2,  # Small effect
            alpha=0.05,
            power=0.80
        )
        
        assert isinstance(result, PowerAnalysisResult)
        assert result.required_sample_size > 100  # Need many samples for small effect
        assert 0.75 < result.achieved_power < 0.85
    
    def test_power_analysis_large_effect(self):
        """Test power analysis with large effect size."""
        result = self.validator.power_analysis(
            effect_size=1.0,  # Large effect
            alpha=0.05,
            power=0.80
        )
        
        assert result.required_sample_size < 50  # Fewer samples needed
        assert result.achieved_power >= 0.75  # Close to target power
    
    def test_power_analysis_high_power(self):
        """Test power analysis with high desired power."""
        result = self.validator.power_analysis(
            effect_size=0.5,
            alpha=0.05,
            power=0.95  # High power
        )
        
        # Higher power requires more samples
        result_low_power = self.validator.power_analysis(
            effect_size=0.5,
            alpha=0.05,
            power=0.80
        )
        
        assert result.required_sample_size > result_low_power.required_sample_size


class TestBatchConfounding:
    
    def setup_method(self):
        self.validator = ExperimentalDesignValidator()
    
    def test_no_confounding(self):
        """Test design with no batch confounding."""
        # Balanced design: each treatment in each batch
        design = pd.DataFrame({
            "treatment": ["A", "A", "B", "B", "C", "C"],
            "batch": ["Batch1", "Batch2", "Batch1", "Batch2", "Batch1", "Batch2"]
        })
        
        result = self.validator.detect_batch_confounding(design)
        
        assert isinstance(result, BatchConfoundingResult)
        assert not result.is_confounded
        assert result.confounding_score < 0.7
    
    def test_perfect_confounding(self):
        """Test design with perfect batch confounding."""
        # Each treatment in only one batch
        design = pd.DataFrame({
            "treatment": ["A", "A", "B", "B", "C", "C"],
            "batch": ["Batch1", "Batch1", "Batch2", "Batch2", "Batch3", "Batch3"]
        })
        
        result = self.validator.detect_batch_confounding(design)
        
        assert result.is_confounded
        assert len(result.problematic_batches) > 0
    
    def test_suggested_layout(self):
        """Test that confounded design gets suggested fix."""
        design = pd.DataFrame({
            "treatment": ["A", "A", "B", "B"],
            "batch": ["Batch1", "Batch1", "Batch2", "Batch2"]
        })
        
        result = self.validator.detect_batch_confounding(design)
        
        if result.is_confounded and result.suggested_layout:
            suggested = result.suggested_layout["balanced_design"]
            assert isinstance(suggested, pd.DataFrame)
            assert len(suggested) > 0


class TestReplicationAssessment:
    
    def setup_method(self):
        self.validator = ExperimentalDesignValidator()
    
    def test_adequate_replication(self):
        """Test assessment with adequate replication."""
        result = self.validator.assess_replication(
            expected_cv=0.10,  # Low variability
            desired_ci_width=0.20
        )
        
        assert isinstance(result, ReplicationResult)
        # With low CV, few replicates should be adequate
        assert result.recommended_replicates < 20
    
    def test_inadequate_replication(self):
        """Test assessment with high variability."""
        result = self.validator.assess_replication(
            expected_cv=0.50,  # High variability
            desired_ci_width=0.10  # Narrow CI desired
        )
        
        # High CV + narrow CI = many replicates needed
        assert result.recommended_replicates > 10
    
    def test_cv_affects_replication(self):
        """Test that higher CV requires more replicates."""
        low_cv = self.validator.assess_replication(
            expected_cv=0.05,
            desired_ci_width=0.20
        )
        
        high_cv = self.validator.assess_replication(
            expected_cv=0.30,
            desired_ci_width=0.20
        )
        
        assert high_cv.recommended_replicates > low_cv.recommended_replicates


class TestPlateLayoutOptimization:
    
    def setup_method(self):
        self.validator = ExperimentalDesignValidator()
    
    def test_basic_layout(self):
        """Test basic plate layout generation."""
        layout = self.validator.optimize_plate_layout(
            treatments=["Control", "Treatment"],
            replicates=3
        )
        
        assert isinstance(layout, pd.DataFrame)
        assert len(layout) == 6  # 2 treatments * 3 replicates
        assert "well_id" in layout.columns
        assert "treatment" in layout.columns
        assert "is_edge" in layout.columns
    
    def test_edge_avoidance(self):
        """Test that inner wells are preferred."""
        layout = self.validator.optimize_plate_layout(
            treatments=["A", "B", "C"],
            replicates=4,
            randomize=False  # Deterministic for testing
        )
        
        # Count edge vs inner wells
        edge_count = layout["is_edge"].sum()
        inner_count = (~layout["is_edge"]).sum()
        
        # Should prefer inner wells
        assert inner_count >= edge_count
    
    def test_too_many_samples(self):
        """Test error when too many samples for plate."""
        with pytest.raises(ValueError):
            self.validator.optimize_plate_layout(
                treatments=["A"] * 100,
                replicates=10  # 1000 samples, too many for 96-well
            )


class TestDesignValidation:
    
    def setup_method(self):
        self.validator = ExperimentalDesignValidator()
    
    def test_balanced_design(self):
        """Test validation of balanced design."""
        design = pd.DataFrame({
            "treatment": ["A", "A", "A", "B", "B", "B", "C", "C", "C"]
        })
        
        results = self.validator.validate_design(design)
        
        assert results["balanced"]
        assert results["min_replicates"] == 3
        assert results["replication_adequate"]
        assert "✓" in results["overall"]
    
    def test_unbalanced_design(self):
        """Test validation of unbalanced design."""
        design = pd.DataFrame({
            "treatment": ["A", "A", "A", "A", "B", "B", "C"]
        })
        
        results = self.validator.validate_design(design)
        
        assert not results["balanced"]
        assert "⚠️" in results["overall"]
    
    def test_insufficient_replication(self):
        """Test detection of insufficient replication."""
        design = pd.DataFrame({
            "treatment": ["A", "A", "B", "B"]  # Only 2 replicates
        })
        
        results = self.validator.validate_design(design)
        
        assert not results["replication_adequate"]
        assert "Insufficient replication" in results["overall"]
    
    def test_with_batch_column(self):
        """Test validation with batch information."""
        design = pd.DataFrame({
            "treatment": ["A", "A", "B", "B"],
            "batch": ["Batch1", "Batch1", "Batch2", "Batch2"]
        })
        
        results = self.validator.validate_design(design, batch_col="batch")
        
        assert "batch_confounding" in results
        assert isinstance(results["batch_confounding"], BatchConfoundingResult)
