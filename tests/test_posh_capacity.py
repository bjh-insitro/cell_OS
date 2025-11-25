"""Tests for POSH pooled capacity model."""

import pytest

from cell_os.perturbation_goal import POSHPooledCapacity, PerturbationGoal
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.perturbation_goal import PerturbationPosterior
from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor


class TestPOSHPooledCapacity:
    """Test POSH pooled capacity calculations."""
    
    def test_posh_pooled_capacity_a549_defaults(self):
        """A549 defaults: 500k cells, 60% efficiency, 1000 cells/gene → 300 genes."""
        cap = POSHPooledCapacity(
            cells_per_well=500_000,
            iss_efficiency=0.60,
            min_cells_per_gene=1000,
            guides_per_gene=4,
        )
        assert cap.effective_barcoded_cells == 300_000
        assert cap.max_genes == 300
        assert cap.max_guides == 1200
    
    def test_posh_capacity_with_higher_efficiency(self):
        """Higher ISS efficiency → more barcoded cells → more genes."""
        cap = POSHPooledCapacity(
            cells_per_well=500_000,
            iss_efficiency=0.80,  # Higher efficiency
            min_cells_per_gene=1000,
            guides_per_gene=4,
        )
        assert cap.effective_barcoded_cells == 400_000
        assert cap.max_genes == 400
        assert cap.max_guides == 1600
    
    def test_posh_capacity_with_more_cells_per_gene(self):
        """More cells required per gene → fewer genes."""
        cap = POSHPooledCapacity(
            cells_per_well=500_000,
            iss_efficiency=0.60,
            min_cells_per_gene=2000,  # More stringent
            guides_per_gene=4,
        )
        assert cap.effective_barcoded_cells == 300_000
        assert cap.max_genes == 150  # Half as many
        assert cap.max_guides == 600
    
    def test_goal_uses_posh_capacity_over_max_perturbations(self):
        """Goal should use POSH capacity if set, not max_perturbations."""
        cap = POSHPooledCapacity(
            cells_per_well=500_000,
            iss_efficiency=0.60,
            min_cells_per_gene=1000,
            guides_per_gene=4,
        )
        goal = PerturbationGoal(
            max_perturbations=50,  # This should be ignored
            posh_capacity=cap,
        )
        # Should use POSH capacity (300 genes), not 50
        assert goal.effective_max_genes() == 300
    
    def test_goal_without_posh_capacity_uses_max_perturbations(self):
        """Without POSH capacity, fall back to max_perturbations."""
        goal = PerturbationGoal(max_perturbations=50)
        assert goal.effective_max_genes() == 50


class TestPerturbationLoopWithPOSHCapacity:
    """Test that perturbation loop respects POSH pooled capacity."""
    
    def test_loop_respects_posh_capacity_limit(self):
        """Loop should limit to POSH capacity (300 genes for A549)."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        # A549 POSH capacity: 300 genes
        cap = POSHPooledCapacity(
            cells_per_well=500_000,
            iss_efficiency=0.60,
            min_cells_per_gene=1000,
            guides_per_gene=4,
        )
        goal = PerturbationGoal(
            max_perturbations=500,  # Higher than POSH capacity
            posh_capacity=cap,
        )
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        # Try to propose 400 genes
        candidate_genes = [f"GENE{i}" for i in range(400)]
        batch = loop.propose(candidate_genes)
        
        # Should be limited to 300 by POSH capacity
        assert len(batch.plans) == 300
    
    def test_loop_uses_posh_capacity_not_plate_constraints(self):
        """With POSH capacity, plate constraints should be ignored."""
        from cell_os.plate_constraints import PlateConstraints
        
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        # POSH capacity allows 300 genes
        cap = POSHPooledCapacity()
        goal = PerturbationGoal(posh_capacity=cap)
        
        # Plate constraints would allow only 184 (with 2 reps)
        plate_constraints = PlateConstraints(wells=384, controls_per_plate=16)
        
        loop = PerturbationAcquisitionLoop(
            posterior, executor, goal, plate_constraints
        )
        
        candidate_genes = [f"GENE{i}" for i in range(400)]
        batch = loop.propose(candidate_genes)
        
        # Should use POSH capacity (300), not plate capacity (184)
        assert len(batch.plans) == 300
    
    def test_posh_capacity_with_fewer_candidates(self):
        """If candidates < capacity, return all candidates."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        cap = POSHPooledCapacity()  # 300 genes
        goal = PerturbationGoal(posh_capacity=cap)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        # Only 50 candidates
        candidate_genes = [f"GENE{i}" for i in range(50)]
        batch = loop.propose(candidate_genes)
        
        # Should return all 50
        assert len(batch.plans) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
