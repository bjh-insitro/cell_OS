"""
WCB Simulation Wrapper.

Provides a clean API for simulating Working Cell Bank generation for the dashboard.
Wraps the underlying WCBSimulation logic but focuses on single-run artifact generation.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from cell_os.simulation.workflow_simulator import WorkflowSimulator, SimulationConfig
from cell_os.workflows import WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.utils import MockInventory

@dataclass
class MCBVialSpec:
    """Specification for a starting MCB vial."""
    cell_line: str
    vial_id: str
    passage_number: int = 3
    cells_per_vial: float = 1e6
    viability: float = 0.95

@dataclass
class WCBVial:
    """Metadata for a generated WCB vial."""
    vial_id: str
    cell_line: str
    passage_number: int
    cells_per_vial: float
    viability: float
    created_at_day: int
    source_mcb_vial_id: str
    location: str = "Freezer_2"

@dataclass
class WCBResultBundle:
    """Result of a single WCB generation run."""
    cell_line: str
    vials: List[WCBVial]
    daily_metrics: pd.DataFrame
    logs: List[str]
    success: bool
    summary: Dict[str, Any]

def simulate_wcb_generation(
    spec: MCBVialSpec,
    target_vials: int = 100,
    cells_per_vial: float = 1e6,
    random_seed: int = 42
) -> WCBResultBundle:
    """
    Simulate WCB generation from an MCB vial.
    
    Args:
        spec: MCB vial specification
        target_vials: Number of vials to bank
        cells_per_vial: Target cells per vial
        random_seed: Seed for reproducibility
        
    Returns:
        WCBResultBundle containing generated vials and metrics
    """
    # Build the workflow to get the recipe
    vessels = VesselLibrary()
    inventory = MockInventory()
    ops = ParametricOps(vessels, inventory)
    builder = WorkflowBuilder(ops)
    
    workflow = builder.build_working_cell_bank(
        flask_size="flask_T75",
        cell_line=spec.cell_line,
        target_vials=target_vials,
        cells_per_vial=int(cells_per_vial)
    )

    # Configure simulation
    config = SimulationConfig(
        workflow=workflow,
        target_vials=target_vials,
        cells_per_vial=cells_per_vial,
        cell_line=spec.cell_line,
        enable_failures=False,
        random_seed=random_seed,
        starting_vials=1
    )
    
    rng = np.random.default_rng(random_seed)
    simulator = WorkflowSimulator(config, rng)
    
    # Run simulation
    result = simulator.run()
    
    # Convert to WCBResultBundle
    generated_vials = []
    if result.success:
        num_vials = result.vials_generated
        final_viability = result.daily_metrics["avg_viability"].iloc[-1] if not result.daily_metrics.empty else 0.95
        day_banked = result.duration_days
        
        for i in range(num_vials):
            vial = WCBVial(
                vial_id=f"WCB-{spec.cell_line}-{i+1:03d}",
                cell_line=spec.cell_line,
                passage_number=spec.passage_number + 2,  # Typically +2 from MCB
                cells_per_vial=cells_per_vial,
                viability=final_viability,
                created_at_day=day_banked,
                source_mcb_vial_id=spec.vial_id
            )
            generated_vials.append(vial)
    
    # Logs
    logs = [f"Started WCB simulation for {spec.cell_line}"]
    if result.success:
        logs.append(f"Successfully banked {len(generated_vials)} WCB vials on day {result.duration_days}")
    else:
        logs.append(f"Simulation failed: {result.summary.get('failed_reason', 'Unknown')}")
        
    return WCBResultBundle(
        cell_line=spec.cell_line,
        vials=generated_vials,
        daily_metrics=result.daily_metrics,
        logs=logs,
        success=result.success,
        summary=result.summary
    )
