from dataclasses import dataclass
from typing import Optional, Dict

from cell_os.lab_world_model import LabWorldModel
from .scenario import POSHScenario
from .library_design import POSHLibrary, design_posh_library
from .lv_moi import (
    LVDesignBundle,
    design_lv_for_scenario,
    ScreenSimulator,
    ScreenConfig
)


@dataclass
class ScreenDesignResult:
    """Top-level design artifact for a POSH stress screen (V1)."""

    scenario: POSHScenario
    library: POSHLibrary
    lv_design: Optional[LVDesignBundle] = None
    risk_assessment: Optional[Dict[str, float]] = None # Probability of Success per cell line
    # Later: bank_plans, stress_doses, screen_layout, cost, etc.


def run_posh_screen_design(
    world: LabWorldModel, 
    scenario: POSHScenario,
    run_simulation: bool = False
) -> ScreenDesignResult:
    """
    Top level pipeline for designing a POSH stress screen.

    V1: performs library design and LV titration planning.
    """
    library = design_posh_library(world, scenario)
    
    # Design LV batch and titration plans
    lv_design = design_lv_for_scenario(world, scenario, library)
    
    risk_assessment = {}
    if run_simulation and lv_design.models:
        # If we have models (e.g. re-running design with data), run risk sim
        config = ScreenConfig(
            num_guides=library.num_guides_total,
            # Map scenario fields to config if possible, else use defaults
            target_bfp=0.30 
        )
        
        for cell_line, model in lv_design.models.items():
            if model.posterior:
                sim = ScreenSimulator(model, config)
                pos = sim.get_probability_of_success()
                risk_assessment[cell_line] = pos
    
    return ScreenDesignResult(
        scenario=scenario, 
        library=library,
        lv_design=lv_design,
        risk_assessment=risk_assessment if risk_assessment else None
    )
