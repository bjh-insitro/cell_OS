"""
POSH (Pooled Optical Screens in Human cells) module.

This package contains all POSH-related functionality:
- scenario: POSHScenario configuration
- library_design: Library design and POSHLibrary
- lv_moi: Lentiviral MOI calculations and screen simulation
- decision_engine: Decision engine for POSH workflows
- screen_design: Screen design orchestration
- screen_designer: Screen designer utilities
- viz: Visualization utilities
"""

# Re-export main public API
from .scenario import POSHScenario
from .library_design import POSHLibrary, design_posh_library, LibraryDesignError
from .lv_moi import (
    ScreenConfig,
    ScreenSimulator,
    LVTransductionModel,
    TiterPosterior,
    TitrationReport,
    LVDesignBundle,
    LVBatch,
    LVTitrationPlan,
)
from .decision_engine import POSHDecisionEngine, UserRequirements
from .screen_design import run_posh_screen_design, ScreenDesignResult
from .screen_designer import create_screen_design

__all__ = [
    # Scenario
    'POSHScenario',
    # Library design
    'POSHLibrary',
    'design_posh_library',
    'LibraryDesignError',
    # LV/MOI
    'ScreenConfig',
    'ScreenSimulator',
    'LVTransductionModel',
    'TiterPosterior',
    'TitrationReport',
    'LVDesignBundle',
    'LVBatch',
    'LVTitrationPlan',
    # Decision engine
    'POSHDecisionEngine',
    'UserRequirements',
    # Screen design
    'run_posh_screen_design',
    'ScreenDesignResult',
    'create_screen_design',
]
