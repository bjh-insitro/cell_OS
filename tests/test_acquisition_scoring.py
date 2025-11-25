"""Unit tests for acquisition scoring function."""

import pytest
import numpy as np

from cell_os.imaging_acquisition import compute_acquisition_score
from cell_os.imaging_goal import ImagingWindowGoal
from cell_os.acquisition_config import AcquisitionConfig


class TestAcquisitionScoring:
    """Test suite for compute_acquisition_score function."""
    
    def test_perfect_viability_no_penalty(self):
        """Score should have no viability penalty when inside band."""
        goal = ImagingWindowGoal(viability_min=0.8, viability_max=1.0)
        config = AcquisitionConfig.balanced()
        
        score = compute_acquisition_score(
            viability_mean=0.9,  # Inside band
            stress_mean=0.5,
            cells_per_field_pred=300.0,
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        # Should be close to stress term (0.5) with no viability penalty
        assert score > 0.4  # Some QC penalty might apply
        assert score <= 0.5
    
    def test_low_viability_penalty(self):
        """Score should decrease when viability is below minimum."""
        goal = ImagingWindowGoal(viability_min=0.8, viability_max=1.0)
        config = AcquisitionConfig.balanced()
        
        score_low = compute_acquisition_score(
            viability_mean=0.6,  # Below minimum
            stress_mean=0.5,
            cells_per_field_pred=300.0,
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        score_good = compute_acquisition_score(
            viability_mean=0.9,  # Inside band
            stress_mean=0.5,
            cells_per_field_pred=300.0,
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        assert score_low < score_good
    
    def test_qc_penalty_below_threshold(self):
        """Score should decrease when QC metrics are below thresholds."""
        goal = ImagingWindowGoal(
            viability_min=0.8,
            min_cells_per_field=280,
            min_fields_per_well=100,
        )
        config = AcquisitionConfig.balanced()
        
        score_low_qc = compute_acquisition_score(
            viability_mean=0.9,
            stress_mean=0.5,
            cells_per_field_pred=200.0,  # Below threshold
            good_fields_pred=50.0,  # Below threshold
            goal=goal,
            config=config,
        )
        
        score_good_qc = compute_acquisition_score(
            viability_mean=0.9,
            stress_mean=0.5,
            cells_per_field_pred=300.0,  # Above threshold
            good_fields_pred=200.0,  # Above threshold
            goal=goal,
            config=config,
        )
        
        assert score_low_qc < score_good_qc
    
    def test_stress_term_dominates_with_no_violations(self):
        """Higher stress should give higher score when constraints are met."""
        goal = ImagingWindowGoal(viability_min=0.8, viability_max=1.0)
        config = AcquisitionConfig.balanced()
        
        score_low_stress = compute_acquisition_score(
            viability_mean=0.9,
            stress_mean=0.3,
            cells_per_field_pred=300.0,
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        score_high_stress = compute_acquisition_score(
            viability_mean=0.9,
            stress_mean=0.7,
            cells_per_field_pred=300.0,
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        assert score_high_stress > score_low_stress
    
    def test_personality_weights_affect_score(self):
        """Different personalities should produce different scores."""
        goal = ImagingWindowGoal(
            viability_min=0.8,
            min_cells_per_field=280,
        )
        
        # Ambitious postdoc: low viability penalty
        score_ambitious = compute_acquisition_score(
            viability_mean=0.7,  # Below threshold
            stress_mean=0.8,
            cells_per_field_pred=250.0,  # Below threshold
            good_fields_pred=200.0,
            goal=goal,
            config=AcquisitionConfig.ambitious_postdoc(),
        )
        
        # Cautious operator: high viability penalty
        score_cautious = compute_acquisition_score(
            viability_mean=0.7,  # Below threshold
            stress_mean=0.8,
            cells_per_field_pred=250.0,  # Below threshold
            good_fields_pred=200.0,
            goal=goal,
            config=AcquisitionConfig.cautious_operator(),
        )
        
        # Ambitious should tolerate violations better
        assert score_ambitious > score_cautious
    
    def test_posh_optimizer_accepts_mild_violations(self):
        """POSH optimizer should accept mild violations for high stress."""
        goal = ImagingWindowGoal(
            viability_min=0.8,
            min_cells_per_field=280,
        )
        config = AcquisitionConfig.posh_optimizer()
        
        # Mild violations but high stress
        score = compute_acquisition_score(
            viability_mean=0.75,  # Slightly below
            stress_mean=0.7,  # High stress
            cells_per_field_pred=260.0,  # Slightly below
            good_fields_pred=200.0,
            goal=goal,
            config=config,
        )
        
        # Should still have positive score
        assert score > 0.0


class TestPersonalityConfigs:
    """Test that personality configs have expected properties."""
    
    def test_posh_optimizer_weights(self):
        """POSH optimizer should balance stress and constraints."""
        config = AcquisitionConfig.posh_optimizer()
        assert config.w_stress == 1.0
        assert config.w_viab == 1.5
        assert config.w_qc == 1.2
        assert config.personality == "posh_optimizer"
    
    def test_ambitious_postdoc_weights(self):
        """Ambitious postdoc should heavily favor stress."""
        config = AcquisitionConfig.ambitious_postdoc()
        assert config.w_stress == 1.0
        assert config.w_viab < 0.5  # Low penalty
        assert config.w_qc < 0.5  # Low penalty
    
    def test_cautious_operator_weights(self):
        """Cautious operator should heavily penalize violations."""
        config = AcquisitionConfig.cautious_operator()
        assert config.w_viab >= 1.0  # High penalty
        assert config.w_qc >= 1.0  # High penalty
    
    def test_balanced_is_default(self):
        """Balanced config should be returned when no config specified."""
        config = AcquisitionConfig()
        balanced = AcquisitionConfig.balanced()
        assert config.w_stress == balanced.w_stress
        assert config.w_viab == balanced.w_viab
        assert config.w_qc == balanced.w_qc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
