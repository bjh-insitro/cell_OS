from dataclasses import dataclass
from typing import Optional

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary, design_posh_library


@dataclass
class ScreenDesignResult:
    """Top-level design artifact for a POSH stress screen (V1)."""

    scenario: POSHScenario
    library: POSHLibrary
    # Later: lv_batch, moi_models, bank_plans, stress_doses, screen_layout, cost, etc.


def run_posh_screen_design(world: LabWorldModel, scenario: POSHScenario) -> ScreenDesignResult:
    """
    Top level pipeline for designing a POSH stress screen.

    V1: only performs library design. Later versions will add LV/MOI, banks,
    stress window, and full screen layout.
    """
    library = design_posh_library(world, scenario)
    return ScreenDesignResult(scenario=scenario, library=library)
