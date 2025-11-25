# -*- coding: utf-8 -*-
"""Plate constraints for perturbation screens.

Defines physical constraints for plate-based POSH screens.
"""

from __future__ import annotations
from dataclasses import dataclass

from cell_os.perturbation_goal import PerturbationGoal


@dataclass
class PlateConstraints:
    """Physical constraints for a plate-based perturbation screen.
    
    Attributes
    ----------
    wells : int
        Total number of wells on the plate (default: 384)
    controls_per_plate : int
        Number of wells reserved for controls (default: 16)
    
    Examples
    --------
    >>> constraints = PlateConstraints(wells=384, controls_per_plate=16)
    >>> constraints.usable_wells
    368
    >>> goal = PerturbationGoal(min_replicates=2, max_perturbations=200)
    >>> constraints.max_perturbations(goal)
    184
    """
    
    wells: int = 384
    controls_per_plate: int = 16
    
    @property
    def usable_wells(self) -> int:
        """Number of wells available for perturbations (excluding controls)."""
        return self.wells - self.controls_per_plate
    
    def max_perturbations(self, goal: PerturbationGoal) -> int:
        """Compute maximum number of perturbations given replicates.
        
        Parameters
        ----------
        goal : PerturbationGoal
            Goal defining min_replicates and max_perturbations
        
        Returns
        -------
        max_perturbations : int
            Maximum number of perturbations that fit on the plate
        
        Notes
        -----
        Calculation:
        - Physical max = usable_wells // min_replicates
        - Actual max = min(physical_max, goal.max_perturbations)
        
        Examples
        --------
        >>> constraints = PlateConstraints(wells=384, controls_per_plate=16)
        >>> goal = PerturbationGoal(min_replicates=2, max_perturbations=200)
        >>> constraints.max_perturbations(goal)
        184  # 368 usable wells // 2 replicates = 184
        
        >>> goal = PerturbationGoal(min_replicates=2, max_perturbations=100)
        >>> constraints.max_perturbations(goal)
        100  # Goal is more restrictive
        """
        # Physical capacity
        physical_max = self.usable_wells // goal.min_replicates
        
        # Enforce goal's max_perturbations as upper bound
        return min(physical_max, goal.max_perturbations)
