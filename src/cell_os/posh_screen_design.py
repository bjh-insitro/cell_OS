from dataclasses import dataclass
from typing import Optional

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary, design_posh_library
from cell_os.posh_lv_moi import LVDesignBundle, design_lv_for_scenario


@dataclass
class ScreenDesignResult:
    """Top-level design artifact for a POSH stress screen (V1)."""

    scenario: POSHScenario
    library: POSHLibrary
    lv_design: Optional[LVDesignBundle] = None
    # Later: bank_plans, stress_doses, screen_layout, cost, etc.


def run_posh_screen_design(world: LabWorldModel, scenario: POSHScenario) -> ScreenDesignResult:
    """
    Top level pipeline for designing a POSH stress screen.

    V1: performs library design and LV titration planning.
    """
    library = design_posh_library(world, scenario)
    
    # Design LV batch and titration plans
    lv_design = design_lv_for_scenario(world, scenario, library)
    
    return ScreenDesignResult(
        scenario=scenario, 
        library=library,
        lv_design=lv_design
    )
