"""Tests for plate constraints."""

import pytest

from cell_os.plate_constraints import PlateConstraints
from cell_os.perturbation_goal import PerturbationGoal


class TestPlateConstraints:
    """Test plate capacity constraints."""
    
    def test_default_plate_constraints(self):
        """Default should be 384-well plate with 16 controls."""
        constraints = PlateConstraints()
        assert constraints.wells == 384
        assert constraints.controls_per_plate == 16
        assert constraints.usable_wells == 368
    
    def test_custom_plate_constraints(self):
        """Should accept custom well counts."""
        constraints = PlateConstraints(wells=96, controls_per_plate=8)
        assert constraints.wells == 96
        assert constraints.controls_per_plate == 8
        assert constraints.usable_wells == 88
    
    def test_max_perturbations_with_replicates(self):
        """384-well plate with 16 controls, 2 replicates → max 184 perturbations."""
        constraints = PlateConstraints(wells=384, controls_per_plate=16)
        goal = PerturbationGoal(min_replicates=2, max_perturbations=200)
        
        max_pert = constraints.max_perturbations(goal)
        
        # 368 usable wells // 2 replicates = 184
        assert max_pert == 184
    
    def test_max_perturbations_goal_more_restrictive(self):
        """If goal.max_perturbations < physical max, use the goal."""
        constraints = PlateConstraints(wells=384, controls_per_plate=16)
        goal = PerturbationGoal(min_replicates=2, max_perturbations=100)
        
        max_pert = constraints.max_perturbations(goal)
        
        # Goal is more restrictive than physical capacity
        assert max_pert == 100
    
    def test_max_perturbations_with_more_replicates(self):
        """More replicates → fewer perturbations."""
        constraints = PlateConstraints(wells=384, controls_per_plate=16)
        
        goal_2_reps = PerturbationGoal(min_replicates=2, max_perturbations=200)
        goal_4_reps = PerturbationGoal(min_replicates=4, max_perturbations=200)
        
        max_2 = constraints.max_perturbations(goal_2_reps)
        max_4 = constraints.max_perturbations(goal_4_reps)
        
        # 368 // 2 = 184, 368 // 4 = 92
        assert max_2 == 184
        assert max_4 == 92
        assert max_4 < max_2
    
    def test_96_well_plate_capacity(self):
        """96-well plate should have lower capacity."""
        constraints = PlateConstraints(wells=96, controls_per_plate=8)
        goal = PerturbationGoal(min_replicates=3, max_perturbations=100)
        
        max_pert = constraints.max_perturbations(goal)
        
        # 88 usable wells // 3 replicates = 29
        assert max_pert == 29


class TestPerturbationLoopWithPlateConstraints:
    """Test that perturbation loop respects plate constraints."""
    
    def test_propose_respects_plate_capacity(self):
        """propose() should never return more plans than plate capacity allows."""
        from cell_os.perturbation_goal import PerturbationPosterior
        from cell_os.perturbation_loop import PerturbationAcquisitionLoop
        from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor
        
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        # Small plate: 96 wells, 8 controls, 3 replicates → max 29 perturbations
        constraints = PlateConstraints(wells=96, controls_per_plate=8)
        goal = PerturbationGoal(min_replicates=3, max_perturbations=100)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal, constraints)
        
        # Try to propose 50 genes
        candidate_genes = [f"GENE{i}" for i in range(50)]
        batch = loop.propose(candidate_genes)
        
        # Should be limited to 29 by plate capacity
        assert len(batch.plans) == 29
    
    def test_propose_uses_goal_if_more_restrictive(self):
        """If goal.max_perturbations < plate capacity, use goal."""
        from cell_os.perturbation_goal import PerturbationPosterior
        from cell_os.perturbation_loop import PerturbationAcquisitionLoop
        from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor
        
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        # Large plate capacity (184) but goal restricts to 10
        constraints = PlateConstraints(wells=384, controls_per_plate=16)
        goal = PerturbationGoal(min_replicates=2, max_perturbations=10)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal, constraints)
        
        candidate_genes = [f"GENE{i}" for i in range(50)]
        batch = loop.propose(candidate_genes)
        
        # Should be limited to 10 by goal
        assert len(batch.plans) == 10
    
    def test_default_constraints_used_if_none_provided(self):
        """Loop should use default 384-well constraints if none provided."""
        from cell_os.perturbation_goal import PerturbationPosterior
        from cell_os.perturbation_loop import PerturbationAcquisitionLoop
        from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor
        
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        goal = PerturbationGoal(min_replicates=2, max_perturbations=200)
        
        # No constraints provided
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        # Should use default 384-well plate
        assert loop.plate_constraints.wells == 384
        assert loop.plate_constraints.controls_per_plate == 16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
