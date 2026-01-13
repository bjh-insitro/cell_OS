"""
Simulated Imaging Executor for the Imaging Dose Loop.

Generates synthetic imaging data based on viability and stress models.
"""
from typing import List
import numpy as np
from dataclasses import dataclass

from cell_os.imaging.acquisition import ExperimentPlan, ExperimentResult
from cell_os.imaging.goal import ImagingWindowGoal


@dataclass
class SimulatedImagingExecutor:
    """
    Simulates running an imaging experiment.
    Generates synthetic data based on ideal dose-response curves.
    """
    goal: ImagingWindowGoal
    noise_level: float = 0.05
    
    def run_batch(self, plans: List[ExperimentPlan]) -> List[ExperimentResult]:
        """
        Simulate running the experiments and return synthetic results.
        """
        results = []
        for plan in plans:
            # Synthetic viability: starts at 1.0, drops with dose
            # Simple Hill equation: V = 1 / (1 + (dose/EC50)^n)
            ec50_viab = 5.0  # uM
            hill_viab = 2.0
            viability = 1.0 / (1.0 + (plan.dose_uM / ec50_viab) ** hill_viab)
            viability += np.random.normal(0, self.noise_level)
            viability = np.clip(viability, 0.01, 0.99)
            
            # Synthetic stress: starts low, increases with dose, plateaus
            # S = S_max * (dose^n / (EC50^n + dose^n))
            ec50_stress = 2.0  # uM
            hill_stress = 1.5
            s_max = 10.0
            stress = s_max * (plan.dose_uM ** hill_stress) / (ec50_stress ** hill_stress + plan.dose_uM ** hill_stress)
            stress += np.random.normal(0, self.noise_level * s_max)
            stress = np.clip(stress, 0.1, s_max)
            
            # Cell quality metrics
            cells_per_field = int(viability * 400)  # High viability = more cells
            good_fields = int(viability * 120)  # Healthy plate has more good fields
            
            result = ExperimentResult(
                slice_key=plan.slice_key,
                dose_uM=plan.dose_uM,
                viability_value=viability,
                stress_value=stress,
                cells_per_field_observed=cells_per_field,
                good_fields_per_well_observed=good_fields
            )
            results.append(result)
        
        return results
