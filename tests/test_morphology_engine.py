"""Tests for morphology engine."""

import numpy as np
import pytest

from cell_os.morphology_engine import FakeMorphologyEngine
from cell_os.perturbation_goal import PerturbationPosterior


class TestFakeMorphologyEngine:
    """Test fake morphology engine."""
    
    def test_fake_engine_generates_stable_embeddings(self):
        """Same paths should always give same features."""
        engine = FakeMorphologyEngine(dim=10)
        paths = ["image_a.tif", "image_b.tif"]
        
        e1 = engine.extract_features(paths)
        e2 = engine.extract_features(paths)
        
        assert e1.shape == (2, 10)
        assert np.allclose(e1, e2)
    
    def test_fake_engine_different_paths_different_features(self):
        """Different paths should give different features."""
        engine = FakeMorphologyEngine(dim=10)
        
        e1 = engine.extract_features(["image_a.tif"])
        e2 = engine.extract_features(["image_b.tif"])
        
        assert not np.allclose(e1, e2)
    
    def test_fake_engine_empty_paths(self):
        """Empty paths should return empty array."""
        engine = FakeMorphologyEngine(dim=10)
        feats = engine.extract_features([])
        
        assert feats.shape == (0, 10)
    
    def test_reduce_dimensionality_is_noop(self):
        """Dimensionality reduction should be no-op for fake engine."""
        engine = FakeMorphologyEngine(dim=10)
        feats = engine.extract_features(["image_a.tif"])
        reduced = engine.reduce_dimensionality(feats)
        
        assert np.allclose(feats, reduced)


class TestPerturbationPosteriorWithMorphology:
    """Test posterior with morphology engine integration."""
    
    def test_posterior_updates_with_fake_embeddings(self):
        """Posterior should store embeddings from images."""
        posterior = PerturbationPosterior()
        pid = "GENE1"
        paths = ["img1.tif", "img2.tif"]
        
        posterior.update_with_images(pid, paths)
        
        assert pid in posterior.embeddings
        emb = posterior.embeddings[pid]
        assert emb.shape[0] == posterior.morphology_engine.dim
    
    def test_posterior_with_custom_engine(self):
        """Posterior should accept custom morphology engine."""
        engine = FakeMorphologyEngine(dim=20)
        posterior = PerturbationPosterior(morphology_engine=engine)
        
        posterior.update_with_images("GENE1", ["img.tif"])
        
        assert posterior.embeddings["GENE1"].shape[0] == 20
    
    def test_update_with_empty_paths(self):
        """Empty paths should not create embedding."""
        posterior = PerturbationPosterior()
        posterior.update_with_images("GENE1", [])
        
        assert "GENE1" not in posterior.embeddings
    
    def test_diversity_scoring_with_embeddings(self):
        """Diversity score should use real embeddings when available."""
        posterior = PerturbationPosterior()
        pids = ["GENE1", "GENE2", "GENE3"]
        
        for i, pid in enumerate(pids):
            posterior.update_with_images(pid, [f"img_{pid}.tif"])
        
        score = posterior.diversity_score(pids)
        
        # Should be a finite positive number
        assert isinstance(score, float)
        assert score >= 0.0
    
    def test_diversity_score_falls_back_without_embeddings(self):
        """Diversity score should fall back to legacy method without embeddings."""
        posterior = PerturbationPosterior()
        pids = ["GENE1", "GENE2", "GENE3"]
        
        # Don't add any embeddings
        score = posterior.diversity_score(pids)
        
        # Should still return a valid score (using legacy method)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    
    def test_embeddings_are_deterministic(self):
        """Same images should always give same embeddings."""
        posterior1 = PerturbationPosterior()
        posterior2 = PerturbationPosterior()
        
        paths = ["img1.tif", "img2.tif"]
        
        posterior1.update_with_images("GENE1", paths)
        posterior2.update_with_images("GENE1", paths)
        
        assert np.allclose(
            posterior1.embeddings["GENE1"],
            posterior2.embeddings["GENE1"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
