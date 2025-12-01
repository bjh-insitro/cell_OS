"""
MCB Simulation Wrapper.

Provides a clean API for simulating Master Cell Bank generation for the dashboard.
Wraps the underlying MCBSimulation logic but focuses on single-run artifact generation.
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
class VendorVialSpec:
    """Specification for a starting vendor vial."""
    cell_line: str
    vendor_name: str = "ATCC"
    initial_cells: float = 1e6
    lot_number: str = "LOT-DEFAULT"
    vial_id: str = "VENDOR-001"

@dataclass
class MCBVial:
    """Metadata for a generated MCB vial."""
    vial_id: str
    cell_line: str
    passage_number: int
    cells_per_vial: float
    viability: float
    created_at_day: int
    source_vendor_vial_id: str
    location: str = "Freezer_1"

@dataclass
class MCBResultBundle:
    """Result of a single MCB generation run."""
    cell_line: str
    vials: List[MCBVial]
    daily_metrics: pd.DataFrame
    logs: List[str]
    success: bool
    summary: Dict[str, Any]
    workflow: Optional[Any] = None  # Workflow object for rendering
    lineage_data: Optional[Dict[str, Any]] = None  # Lineage tree data
    resources: Optional[Dict[str, float]] = None  # Resource usage

def simulate_mcb_generation(
    spec: VendorVialSpec,
    target_vials: int = 30,
    cells_per_vial: float = 1e6,
    random_seed: int = 42
) -> MCBResultBundle:
    """
    Simulate MCB generation from a vendor vial.
    
    Args:
        spec: Vendor vial specification
        target_vials: Number of vials to bank
        cells_per_vial: Target cells per vial
        random_seed: Seed for reproducibility
        
    Returns:
        MCBResultBundle containing generated vials and metrics
    """
    # Build the workflow to get the recipe
    vessels = VesselLibrary()
    inventory = MockInventory()
    ops = ParametricOps(vessels, inventory)
    builder = WorkflowBuilder(ops)
    
    workflow = builder.build_master_cell_bank(
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
    
    # Convert to MCBResultBundle
    generated_vials = []
    if result.success:
        num_vials = result.vials_generated
        final_viability = result.daily_metrics["avg_viability"].iloc[-1] if not result.daily_metrics.empty else 0.95
        day_banked = result.duration_days
        
        for i in range(num_vials):
            vial = MCBVial(
                vial_id=f"MCB-{spec.cell_line}-{i+1:03d}",
                cell_line=spec.cell_line,
                passage_number=3,  # Typically p+3 from vendor
                cells_per_vial=cells_per_vial,
                viability=final_viability,
                created_at_day=day_banked,
                source_vendor_vial_id=spec.vial_id
            )
            generated_vials.append(vial)
    
    # Logs
    logs = [f"Started simulation for {spec.cell_line}"]
    if result.success:
        logs.append(f"Successfully banked {len(generated_vials)} vials on day {result.duration_days}")
    else:
        logs.append(f"Simulation failed: {result.summary.get('failed_reason', 'Unknown')}")
    
    # Build lineage data for visualization
    lineage_data = None
    if result.success and generated_vials:
        nodes = []
        edges = []
        
        # Vendor vial node
        nodes.append({
            "id": spec.vial_id,
            "type": "Vial",
            "cells": spec.initial_cells
        })
        
        # Expansion flask nodes (simplified - assume 2-3 expansion steps)
        expansion_steps = min(3, result.duration_days // 3)  # Rough estimate
        prev_id = spec.vial_id
        
        for i in range(expansion_steps):
            flask_id = f"Flask_P{i+1}"
            # Estimate cell count based on doubling
            cells = spec.initial_cells * (2 ** (i + 2))
            nodes.append({
                "id": flask_id,
                "type": "Flask",
                "cells": cells
            })
            edges.append({
                "source": prev_id,
                "target": flask_id,
                "op": "Passage" if i > 0 else "Thaw"
            })
            prev_id = flask_id
        
        # Final harvest flask
        harvest_flask = f"Flask_Harvest"
        total_cells_needed = cells_per_vial * target_vials
        nodes.append({
            "id": harvest_flask,
            "type": "Flask",
            "cells": total_cells_needed
        })
        edges.append({
            "source": prev_id,
            "target": harvest_flask,
            "op": "Passage"
        })
        
        # MCB vials (show first 5 to avoid clutter)
        vials_to_show = min(5, len(generated_vials))
        for i in range(vials_to_show):
            vial = generated_vials[i]
            nodes.append({
                "id": vial.vial_id,
                "type": "Vial",
                "cells": vial.cells_per_vial
            })
            edges.append({
                "source": harvest_flask,
                "target": vial.vial_id,
                "op": "Freeze"
            })
        
        # Add ellipsis node if more vials exist
        if len(generated_vials) > vials_to_show:
            nodes.append({
                "id": f"... +{len(generated_vials) - vials_to_show} more",
                "type": "Vial",
                "cells": cells_per_vial
            })
            edges.append({
                "source": harvest_flask,
                "target": f"... +{len(generated_vials) - vials_to_show} more",
                "op": "Freeze"
            })
        
        lineage_data = {
            "nodes": nodes,
            "edges": edges
        }
        
    return MCBResultBundle(
        cell_line=spec.cell_line,
        vials=generated_vials,
        daily_metrics=result.daily_metrics,
        logs=logs,
        success=result.success,
        summary=result.summary,
        workflow=workflow,  # Include workflow for rendering
        lineage_data=lineage_data  # Include lineage graph
    )
