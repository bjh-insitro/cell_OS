"""
campaign.py

Defines the Campaign Manager and Goal protocols for autonomous scientific campaigns.
"""

from typing import Protocol, List, Optional
import pandas as pd
from src.schema import Phase0WorldModel

class CampaignGoal(Protocol):
    """Protocol for a scientific goal."""
    def is_met(self, world_model: Phase0WorldModel) -> bool:
        """Check if the goal has been achieved based on the current world model."""
        ...
    
    def description(self) -> str:
        """Return a human-readable description of the goal."""
        ...

class PotencyGoal:
    """
    Goal: Find a compound with an IC50 below a certain threshold for a specific cell line.
    """
    def __init__(self, cell_line: str, ic50_threshold_uM: float = 1.0):
        self.cell_line = cell_line
        self.threshold = ic50_threshold_uM
        self.met_by: Optional[str] = None # Store which compound met the goal

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        """
        Check if any compound for the target cell line has a modeled IC50 < threshold.
        
        Note: In a real scenario, we would extract the IC50 from the GP model.
        Since our GP model (DoseResponseGP) doesn't explicitly expose IC50 yet,
        we will infer it from the data or add an IC50 estimator.
        
        For this prototype, we will check if we have observed any *data point* 
        with viability < 0.5 at a dose < threshold. This is a proxy for IC50.
        """
        # Iterate over all slices in the world model
        for key, gp in world_model.gp_models.items():
            if key.cell_line != self.cell_line:
                continue
            
            # We can't easily query the GP for parameters without refactoring modeling.py
            # So let's look at the raw data associated with the GP if possible, 
            # or just query the GP at the threshold dose.
            
            # Let's predict viability at the threshold dose
            # If predicted viability is < 0.5, then IC50 is likely < threshold
            pred = gp.predict([self.threshold])
            viability_at_threshold = pred[0]
            
            if viability_at_threshold < 0.5:
                self.met_by = key.compound
                return True
                
        return False

    def description(self) -> str:
        return f"Find a compound for {self.cell_line} with IC50 < {self.threshold} uM"

class SelectivityGoal:
    """
    Goal: Find a compound that is potent against a target cell line (IC50 < threshold)
    AND safe for a reference cell line (IC50 > safety_threshold).
    """
    def __init__(
        self, 
        target_cell: str, 
        safe_cell: str, 
        potency_threshold_uM: float = 1.0,
        safety_threshold_uM: float = 1.0
    ):
        self.target_cell = target_cell
        self.safe_cell = safe_cell
        self.potency_threshold = potency_threshold_uM
        self.safety_threshold = safety_threshold_uM
        self.met_by: Optional[str] = None

    def is_met(self, world_model: Phase0WorldModel) -> bool:
        # Group models by compound
        compounds = set(k.compound for k in world_model.gp_models.keys())
        
        for compound in compounds:
            # Check Target Potency
            target_key = None
            for k in world_model.gp_models:
                if k.compound == compound and k.cell_line == self.target_cell:
                    target_key = k
                    break
            
            if not target_key:
                continue
                
            # Check Safe Potency
            safe_key = None
            for k in world_model.gp_models:
                if k.compound == compound and k.cell_line == self.safe_cell:
                    safe_key = k
                    break
            
            if not safe_key:
                continue
                
            # Evaluate
            gp_target = world_model.gp_models[target_key]
            gp_safe = world_model.gp_models[safe_key]
            
            # Predict at thresholds
            # Target: Viability should be LOW (< 0.5) at potency_threshold
            pred_target = gp_target.predict([self.potency_threshold])[0]
            is_potent = pred_target < 0.5
            
            # Safe: Viability should be HIGH (> 0.5) at safety_threshold
            pred_safe = gp_safe.predict([self.safety_threshold])[0]
            is_safe = pred_safe > 0.5
            
            if is_potent and is_safe:
                self.met_by = compound
                return True
                
        return False

    def description(self) -> str:
        return (
            f"Find compound: {self.target_cell} IC50 < {self.potency_threshold} uM "
            f"AND {self.safe_cell} IC50 > {self.safety_threshold} uM"
        )

class Campaign:
    """
    Manages the execution of a scientific campaign.
    """
    def __init__(self, goal: CampaignGoal, max_cycles: int = 5):
        self.goal = goal
        self.max_cycles = max_cycles
        self.current_cycle = 0
        self.is_complete = False
        self.success = False

    def check_goal(self, world_model: Phase0WorldModel) -> bool:
        """Check if the goal is met and update status."""
        if self.goal.is_met(world_model):
            self.success = True
            self.is_complete = True
            return True
        
        if self.current_cycle >= self.max_cycles:
            self.is_complete = True
            return False
            
        return False
