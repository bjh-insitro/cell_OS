"""Test diversity scoring with cosine distance."""

import pytest
import numpy as np

from cell_os.perturbation_goal import PerturbationPosterior


class TestDiversityScoring:
    """Test Phase 0.2 diversity scoring with cosine distance."""
    
    def test_identical_embeddings_low_diversity(self):
        """Two genes with identical embeddings should have low diversity."""
        posterior = PerturbationPosterior()
        
        # Create identical embeddings
        embedding = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        posterior.embeddings['TP53'] = embedding
        posterior.embeddings['MDM2'] = embedding
        
        # Diversity should be very low (close to 0)
        score = posterior.get_diversity_score(['TP53', 'MDM2'])
        assert score < 0.01  # Essentially zero
    
    def test_orthogonal_embeddings_high_diversity(self):
        """Two genes with orthogonal embeddings should have high diversity."""
        posterior = PerturbationPosterior()
        
        # Create orthogonal embeddings
        emb1 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        emb2 = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        posterior.embeddings['TP53'] = emb1
        posterior.embeddings['MDM2'] = emb2
        
        # Diversity should be high (cosine distance = 1.0, normalized to 0.5)
        score = posterior.get_diversity_score(['TP53', 'MDM2'])
        assert score > 0.4  # Should be around 0.5
        assert score < 0.6
    
    def test_opposite_embeddings_max_diversity(self):
        """Two genes with opposite embeddings should have maximum diversity."""
        posterior = PerturbationPosterior()
        
        # Create opposite embeddings
        emb1 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        emb2 = np.array([-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        posterior.embeddings['TP53'] = emb1
        posterior.embeddings['MDM2'] = emb2
        
        # Diversity should be maximum (cosine distance = 2.0, normalized to 1.0)
        score = posterior.get_diversity_score(['TP53', 'MDM2'])
        assert score > 0.9  # Should be close to 1.0
    
    def test_pairwise_distance_matrix(self):
        """Test pairwise distance matrix computation."""
        posterior = PerturbationPosterior()
        
        # Create three embeddings
        embeddings = {
            'TP53': np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            'MDM2': np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            'ATM': np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),  # Same as TP53
        }
        
        distance_matrix = posterior.compute_pairwise_distance_matrix(embeddings)
        
        # Check shape
        assert distance_matrix.shape == (3, 3)
        
        # Diagonal should be zero (distance to self)
        assert np.allclose(np.diag(distance_matrix), 0.0)
        
        # TP53 and ATM should have zero distance (identical)
        assert distance_matrix[0, 2] < 0.01
        assert distance_matrix[2, 0] < 0.01
        
        # TP53 and MDM2 should have distance ~1.0 (orthogonal)
        assert 0.9 < distance_matrix[0, 1] < 1.1
    
    def test_diversity_with_placeholder_embeddings(self):
        """Test that genes without embeddings use placeholder vectors."""
        posterior = PerturbationPosterior()
        
        # No embeddings stored
        score = posterior.get_diversity_score(['TP53', 'MDM2'])
        
        # Should still return a valid score (using placeholders)
        assert 0.0 <= score <= 1.0
        assert score > 0.0  # Different genes should have some diversity
    
    def test_single_gene_zero_diversity(self):
        """Single gene should have zero diversity."""
        posterior = PerturbationPosterior()
        posterior.embeddings['TP53'] = np.random.randn(10)
        
        score = posterior.get_diversity_score(['TP53'])
        assert score == 0.0
    
    def test_diversity_increases_with_gene_set_size(self):
        """Larger, diverse gene sets should have higher diversity scores."""
        posterior = PerturbationPosterior()
        
        # Create diverse embeddings (random orthogonal-ish)
        rng = np.random.RandomState(42)
        for i, gene in enumerate(['TP53', 'MDM2', 'ATM', 'BRCA1', 'PTEN']):
            emb = np.zeros(10)
            emb[i] = 1.0  # Each gene gets a different basis vector
            posterior.embeddings[gene] = emb
        
        # Two genes
        score_2 = posterior.get_diversity_score(['TP53', 'MDM2'])
        
        # Five genes
        score_5 = posterior.get_diversity_score(['TP53', 'MDM2', 'ATM', 'BRCA1', 'PTEN'])
        
        # More genes with orthogonal embeddings should have similar or higher diversity
        # (average pairwise distance stays constant for orthogonal vectors)
        assert score_5 >= score_2 * 0.9  # Allow some tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
