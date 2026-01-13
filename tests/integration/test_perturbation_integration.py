"""Integration test for perturbation acquisition loop Phase 0.1."""

import pytest
import pandas as pd

from cell_os.perturbation_goal import (
    PerturbationGoal,
    PerturbationPosterior,
)
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.simulation.simulated_perturbation_executor import SimulatedPerturbationExecutor


class TestPerturbationLoopIntegration:
    """Integration tests for the full perturbation loop."""
    
    def test_full_cycle_with_simulated_executor(self):
        """Test complete cycle: propose -> execute -> update."""
        # Setup
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        goal = PerturbationGoal(
            max_perturbations=5,
            min_guides_per_gene=3,
            min_replicates=2,
        )
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        # Run one cycle
        candidate_genes = ["TP53", "MDM2", "ATM", "BRCA1", "PTEN", "MYC", "KRAS"]
        batch = loop.run_one_cycle(candidate_genes)
        
        # Assertions
        assert len(batch.plans) == 5  # max_perturbations
        assert batch.total_cost_usd > 0.0  # Cost calculated
        assert batch.expected_diversity > 0.0  # Diversity calculated (Phase 0.2)
        
        # Check that posterior was updated
        assert len(posterior.history) == 1
        assert len(posterior.embeddings) == 5  # One per gene
        assert len(posterior.phenotype_scores) == 5
        
        # Check that plans have correct structure
        for plan in batch.plans:
            assert len(plan.guides) == 3  # min_guides_per_gene
            assert len(plan.guide_ids) == 3
            assert plan.replicates == 2  # min_replicates
    
    def test_cost_calculation(self):
        """Test that cost is calculated correctly."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        goal = PerturbationGoal(
            max_perturbations=2,
            min_guides_per_gene=3,
            min_replicates=2,
        )
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        batch = loop.run_one_cycle(["TP53", "MDM2"])
        
        # Cost should be: 2 genes × 3 guides × 2 replicates × $5 = $60
        expected_cost = 2 * 3 * 2 * 5.0
        assert batch.total_cost_usd == expected_cost
    
    def test_gene_ranking_is_deterministic(self):
        """Test that gene ranking is stable across runs."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        goal = PerturbationGoal(max_perturbations=3)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        candidate_genes = ["TP53", "MDM2", "ATM", "BRCA1", "PTEN"]
        
        # Run twice
        batch1 = loop.propose(candidate_genes)
        batch2 = loop.propose(candidate_genes)
        
        # Should select same genes in same order
        genes1 = [p.gene for p in batch1.plans]
        genes2 = [p.gene for p in batch2.plans]
        
        assert genes1 == genes2
    
    def test_executor_generates_embeddings(self):
        """Test that executor generates morphological embeddings."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor(embedding_dim=10)
        goal = PerturbationGoal(max_perturbations=2)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        batch = loop.run_one_cycle(["TP53", "MDM2"])
        
        # Check results structure
        results = posterior.history[0]
        assert isinstance(results, pd.DataFrame)
        assert 'gene' in results.columns
        assert 'guide_id' in results.columns
        assert 'replicate' in results.columns
        assert 'viability' in results.columns
        assert 'morphology_embedding' in results.columns
        
        # Check embedding dimensionality
        embedding = results.iloc[0]['morphology_embedding']
        assert len(embedding) == 10
    
    def test_embeddings_are_gene_specific(self):
        """Test that different genes get different embeddings."""
        executor = SimulatedPerturbationExecutor()
        
        # Generate embeddings for two genes
        emb1 = executor._generate_gene_embedding("TP53")
        emb2 = executor._generate_gene_embedding("MDM2")
        
        # Should be different
        assert not (emb1 == emb2).all()
        
        # But same gene should give same embedding
        emb1_again = executor._generate_gene_embedding("TP53")
        assert (emb1 == emb1_again).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
