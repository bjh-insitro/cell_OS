"""Stub tests for perturbation acquisition loop.

These tests verify the API structure but don't test logic (which doesn't exist yet).
"""

import pytest

from cell_os.perturbation_goal import (
    PerturbationGoal,
    PerturbationPlan,
    PerturbationBatch,
    PerturbationPosterior,
)
from cell_os.perturbation_loop import PerturbationAcquisitionLoop


class TestPerturbationDataStructures:
    """Test that data structures can be instantiated."""
    
    def test_perturbation_goal_creation(self):
        """PerturbationGoal should instantiate with defaults."""
        goal = PerturbationGoal()
        assert goal.objective == "maximize_diversity"
        assert goal.min_guides_per_gene == 3
        assert goal.max_perturbations == 200
    
    def test_perturbation_goal_with_params(self):
        """PerturbationGoal should accept custom parameters."""
        goal = PerturbationGoal(
            objective="target_pathway",
            target_genes=["TP53", "MDM2"],
            max_perturbations=100,
            budget_usd=5000.0,
        )
        assert goal.objective == "target_pathway"
        assert goal.target_genes == ["TP53", "MDM2"]
        assert goal.max_perturbations == 100
        assert goal.budget_usd == 5000.0
    
    def test_perturbation_plan_creation(self):
        """PerturbationPlan should instantiate with required fields."""
        plan = PerturbationPlan(
            gene="TP53",
            guides=["GACTCCAGTGGTAATCTAC"],
            guide_ids=["TP53_g1"],
        )
        assert plan.gene == "TP53"
        assert len(plan.guides) == 1
        assert plan.replicates == 2  # default
    
    def test_perturbation_batch_creation(self):
        """PerturbationBatch should instantiate."""
        batch = PerturbationBatch()
        assert batch.plans == []
        assert batch.total_cost_usd == 0.0
    
    def test_perturbation_posterior_creation(self):
        """PerturbationPosterior should instantiate."""
        posterior = PerturbationPosterior()
        assert posterior.history == []
        assert posterior.embeddings == {}


class TestPerturbationAcquisitionLoop:
    """Test that loop can be instantiated (no logic tests yet)."""
    
    def test_loop_creation(self):
        """Loop should instantiate with required components."""
        posterior = PerturbationPosterior()
        goal = PerturbationGoal()
        
        # Mock executor (no real executor yet)
        class MockExecutor:
            def run_batch(self, batch):
                return None
        
        executor = MockExecutor()
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        assert loop.posterior is posterior
        assert loop.executor is executor
        assert loop.goal is goal
    
    def test_propose_returns_batch(self):
        """propose() should return a PerturbationBatch."""
        posterior = PerturbationPosterior()
        goal = PerturbationGoal()
        
        class MockExecutor:
            def run_batch(self, batch):
                return None
        
        loop = PerturbationAcquisitionLoop(posterior, MockExecutor(), goal)
        batch = loop.propose(candidate_genes=["TP53", "MDM2"])
        
        assert isinstance(batch, PerturbationBatch)
        # Batch is empty for now (no logic implemented)
        assert batch.plans == []
    
    def test_run_one_cycle_returns_batch(self):
        """run_one_cycle() should return a PerturbationBatch."""
        posterior = PerturbationPosterior()
        goal = PerturbationGoal()
        
        class MockExecutor:
            def run_batch(self, batch):
                return None
        
        loop = PerturbationAcquisitionLoop(posterior, MockExecutor(), goal)
        batch = loop.run_one_cycle(candidate_genes=["TP53", "MDM2"])
        
        assert isinstance(batch, PerturbationBatch)


class TestPerturbationPosterior:
    """Test posterior API (placeholder methods)."""
    
    def test_update_with_results(self):
        """update_with_results() should accept results dict."""
        posterior = PerturbationPosterior()
        results = {"gene": "TP53", "phenotype": 0.8}
        
        # Should not raise
        posterior.update_with_results(results)
        assert len(posterior.history) == 1
    
    def test_get_diversity_score(self):
        """get_diversity_score() should return a float."""
        posterior = PerturbationPosterior()
        score = posterior.get_diversity_score(["TP53", "MDM2"])
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
