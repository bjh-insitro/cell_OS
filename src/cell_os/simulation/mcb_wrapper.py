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

from cell_os.mcb_crash import MCBSimulation, MCBTestConfig

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
    # Configure simulation
    config = MCBTestConfig(
        num_simulations=1,
        target_mcb_vials=target_vials,
        cells_per_vial=cells_per_vial,
        random_seed=random_seed,
        enable_failures=False, # Assume happy path for campaign planning unless requested
        cell_line=spec.cell_line,
        starting_vials=1 # Start with 1 vendor vial
    )
    
    rng = np.random.default_rng(random_seed)
    sim = MCBSimulation(run_id=1, config=config, rng=rng)
    
    # Run simulation
    result = sim.run()
    
    # Extract vials
    # MCBSimulation.run() returns a dict with keys like 'final_vials', 'terminal_failure'
    
    success = result["final_vials"] > 0 and not result["terminal_failure"]
    
    generated_vials = []
    if success:
        num_vials = result["final_vials"]
        
        # Daily metrics is a list of dicts in the result
        daily_metrics_df = pd.DataFrame(result["daily_metrics"])
        
        final_viability = daily_metrics_df["avg_viability"].iloc[-1] if not daily_metrics_df.empty else 0.95
        day_banked = result["duration_days"]
        
        for i in range(num_vials):
            vial = MCBVial(
                vial_id=f"MCB-{spec.cell_line}-{i+1:03d}",
                cell_line=spec.cell_line,
                passage_number=3, # Typically p+3 from vendor
                cells_per_vial=cells_per_vial,
                viability=final_viability,
                created_at_day=day_banked,
                source_vendor_vial_id=spec.vial_id
            )
            generated_vials.append(vial)
    else:
        daily_metrics_df = pd.DataFrame(result["daily_metrics"])
            
    # Logs
    logs = [f"Started simulation for {spec.cell_line}"]
    if success:
        logs.append(f"Successfully banked {len(generated_vials)} vials on day {result['duration_days']}")
    else:
        logs.append(f"Simulation failed: {result.get('failed_reason', 'Unknown')}")
        
    return MCBResultBundle(
        cell_line=spec.cell_line,
        vials=generated_vials,
        daily_metrics=daily_metrics_df,
        logs=logs,
        success=success,
        summary=result
    )
