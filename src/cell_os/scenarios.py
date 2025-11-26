# -*- coding: utf-8 -*-
"""Scenario presets for experiment planning.

Bundles configuration for common experimental scenarios including budget,
inventory, morphology engine, and acquisition parameters.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path


@dataclass
class Scenario:
    """Configuration bundle for an experimental scenario.
    
    Attributes
    ----------
    name : str
        Scenario identifier
    description : str
        Human-readable description
    budget_usd : float
        Total campaign budget in USD
    initial_inventory : Dict[str, float]
        Initial stock levels (resource_id -> quantity)
    morphology_engine : str
        Engine type: "fake" or "real"
    morphology_csv_path : Optional[str]
        Path to morphology CSV (required if engine="real")
    morphology_aggregation : str
        Aggregation mode: "first", "mean", or "median"
    acquisition_profile : str
        Profile name: "balanced", "ambitious_postdoc", etc.
    max_perturbations : int
        Maximum number of perturbations
    max_cycles : int
        Maximum campaign cycles
    failure_mode : str
        "fail_fast" or "graceful"
    """
    
    name: str
    description: str
    budget_usd: float
    initial_inventory: Dict[str, float] = field(default_factory=dict)
    morphology_engine: str = "fake"
    morphology_csv_path: Optional[str] = None
    morphology_aggregation: str = "first"
    acquisition_profile: str = "balanced"
    max_perturbations: int = 50
    max_cycles: int = 5
    failure_mode: str = "fail_fast"


# Preset scenarios
SCENARIOS = {
    "cheap_pilot": Scenario(
        name="cheap_pilot",
        description="Low-budget pilot study with limited resources",
        budget_usd=500.0,
        initial_inventory={
            "plate_6well": 5.0,  # 5 plates
            "dmem_high_glucose": 100.0,  # 100 mL
            "fbs": 10.0,  # 10 mL
        },
        morphology_engine="fake",
        acquisition_profile="cautious_operator",
        max_perturbations=20,
        max_cycles=3,
        failure_mode="graceful",  # Degrade gracefully on resource limits
    ),
    
    "posh_window_finding": Scenario(
        name="posh_window_finding",
        description="Standard POSH screen for stress window optimization",
        budget_usd=2000.0,
        initial_inventory={
            "plate_6well": 20.0,  # 20 plates
            "dmem_high_glucose": 500.0,  # 500 mL
            "fbs": 50.0,  # 50 mL
        },
        morphology_engine="fake",
        morphology_aggregation="mean",
        acquisition_profile="balanced",
        max_perturbations=50,
        max_cycles=5,
        failure_mode="fail_fast",
    ),
    
    "high_risk_morphology": Scenario(
        name="high_risk_morphology",
        description="Aggressive morphology exploration with high stress tolerance",
        budget_usd=5000.0,
        initial_inventory={
            "plate_6well": 50.0,  # 50 plates
            "dmem_high_glucose": 2000.0,  # 2 L
            "fbs": 200.0,  # 200 mL
        },
        morphology_engine="real",
        morphology_csv_path="data/morphology/example_embeddings.csv",
        morphology_aggregation="mean",
        acquisition_profile="ambitious_postdoc",
        max_perturbations=100,
        max_cycles=10,
        failure_mode="fail_fast",
    ),
}


def get_scenario(name: str) -> Scenario:
    """Get a scenario by name.
    
    Parameters
    ----------
    name : str
        Scenario name
    
    Returns
    -------
    scenario : Scenario
        Scenario configuration
    
    Raises
    ------
    KeyError
        If scenario not found
    
    Examples
    --------
    >>> scenario = get_scenario("cheap_pilot")
    >>> scenario.budget_usd
    500.0
    """
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario: {name}. Available: {available}")
    
    return SCENARIOS[name]


def list_scenarios() -> Dict[str, str]:
    """List available scenarios with descriptions.
    
    Returns
    -------
    scenarios : Dict[str, str]
        Mapping of scenario name to description
    """
    return {name: s.description for name, s in SCENARIOS.items()}


def apply_scenario(scenario: Scenario):
    """Apply a scenario configuration.
    
    Creates and configures:
    - Inventory with initial stock
    - Campaign with budget
    - Morphology engine
    
    Parameters
    ----------
    scenario : Scenario
        Scenario to apply
    
    Returns
    -------
    inventory : Inventory
        Configured inventory
    morphology_engine : MorphologyEngine
        Configured morphology engine
    campaign_config : dict
        Campaign configuration parameters
    
    Examples
    --------
    >>> scenario = get_scenario("cheap_pilot")
    >>> inv, engine, config = apply_scenario(scenario)
    >>> inv.check_stock("plate_6well")
    5.0
    """
    from cell_os.inventory import Inventory
    from cell_os.morphology_engine import create_morphology_engine
    
    # Create inventory with initial stock
    inventory = Inventory("data/raw/pricing.yaml")
    
    # Set initial stock levels
    for resource_id, quantity in scenario.initial_inventory.items():
        resource = inventory.get_resource(resource_id)
        resource.stock_level = quantity
    
    # Create morphology engine
    if scenario.morphology_engine == "real" and scenario.morphology_csv_path:
        engine = create_morphology_engine(
            "real",
            csv_path=scenario.morphology_csv_path
        )
    else:
        engine = create_morphology_engine("fake")
    
    # Campaign configuration
    campaign_config = {
        "budget_total_usd": scenario.budget_usd,
        "max_cycles": scenario.max_cycles,
        "failure_mode": scenario.failure_mode,
    }
    
    return inventory, engine, campaign_config
