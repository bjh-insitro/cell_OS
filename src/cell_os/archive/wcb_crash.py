"""
WCB Crash Test Library

Reusable library for running Working Cell Bank (WCB) crash test simulations.
Simulates the expansion of a single Master Cell Bank (MCB) vial into a large Working Cell Bank.
"""

import json
import base64
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.workflow_executor import WorkflowExecutor
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.failure_modes import FailureModeSimulator
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cell_os.workflows import Workflow


@dataclass
class WCBTestConfig:
    """Configuration for WCB crash test simulation."""
    num_simulations: int = 100
    target_wcb_vials: int = 100
    cells_per_vial: float = 1e6
    random_seed: Optional[int] = 123
    enable_failures: bool = True
    output_dir: Optional[str] = None
    cell_line: str = "U2OS"
    starting_mcb_passage: int = 3
    workflow: Optional['Workflow'] = None


@dataclass
class WCBTestResult:
    """Result of WCB crash test simulation."""
    summary: Dict[str, Any]
    run_results: pd.DataFrame
    daily_metrics: pd.DataFrame


from cell_os.simulation.workflow_simulator import WorkflowSimulator, SimulationConfig

class WCBSimulation:
    """
    Single WCB simulation run.
    Refactored to delegate to the shared WorkflowSimulator.
    """
    
    def __init__(self, run_id: int, config: WCBTestConfig, rng: np.random.Generator):
        self.run_id = run_id
        self.config = config
        self.rng = rng
        
    def run(self):
        """Execute the full WCB workflow using WorkflowSimulator."""
        # Map WCBTestConfig to SimulationConfig
        sim_config = SimulationConfig(
            target_vials=self.config.target_wcb_vials,
            cells_per_vial=self.config.cells_per_vial,
            starting_vials=1, # WCB starts with 1 MCB vial
            cell_line=self.config.cell_line,
            enable_failures=self.config.enable_failures,
            workflow=self.config.workflow
        )
        
        # Instantiate and run simulator
        simulator = WorkflowSimulator(sim_config, self.rng)
        result = simulator.run()
        
        # Estimate max passage (WorkflowSimulator doesn't explicitly return it in summary yet)
        # Assuming passage every ~3-4 days
        estimated_passages = int(result.duration_days / 3.5)
        max_passage = self.config.starting_mcb_passage + estimated_passages
        
        # Convert daily metrics DataFrame to list of dicts
        daily_metrics_list = result.daily_metrics.to_dict('records') if not result.daily_metrics.empty else []
        
        return {
            "run_id": self.run_id,
            "duration_days": result.duration_days,
            "final_vials": result.vials_generated,
            "waste_vials": result.summary.get("waste_vials", 0),
            "waste_cells": result.summary.get("waste_cells", 0.0),
            "waste_vials_equivalent": result.summary.get("waste_vials_equivalent", 0.0),
            "waste_fraction": result.summary.get("waste_fraction", 0.0),
            "had_contamination": "contamination" in str(result.failures).lower(),
            "terminal_failure": not result.success,
            "failed_reason": str(result.failures) if result.failures else "",
            "total_media_l": result.summary.get("total_media_l", 0.0),
            "max_passage": max_passage,
            "failures": result.failures,
            "violations": result.violations,
            "daily_metrics": daily_metrics_list
        }


def run_wcb_crash_test(config: WCBTestConfig) -> WCBTestResult:
    """Run WCB crash test simulations."""
    if config.random_seed is not None:
        rng = np.random.default_rng(config.random_seed)
    else:
        rng = np.random.default_rng()
    
    results = []
    all_daily = []
    
    for i in range(config.num_simulations):
        sim = WCBSimulation(i, config, rng)
        res = sim.run()
        results.append(res)
        
        for d in res["daily_metrics"]:
            d["run_id"] = i
            all_daily.append(d)
    
    df_results = pd.DataFrame(results)
    df_daily = pd.DataFrame(all_daily) if all_daily else pd.DataFrame(columns=["run_id", "day", "total_cells"])
    
    # Summary
    success_runs = len(df_results[df_results["final_vials"] > 0])
    summary = {
        "total_runs": config.num_simulations,
        "successful_runs": success_runs,
        "success_rate": success_runs / config.num_simulations,
        "contaminated_runs": len(df_results[df_results["had_contamination"] == True]),
        "failed_runs": len(df_results[df_results["terminal_failure"] == True]),
        "vials_p50": float(df_results["final_vials"].median()),
        "waste_fraction_p50": float(df_results["waste_fraction"].median()),
        "duration_p50": float(df_results["duration_days"].median()),
        "max_passage_p95": float(df_results["max_passage"].quantile(0.95))
    }
    
    if config.output_dir:
        output_path = Path(config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "wcb_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        df_results.to_csv(output_path / "wcb_run_results.csv", index=False)
        df_daily.to_csv(output_path / "wcb_daily_metrics.csv", index=False)
        
    return WCBTestResult(summary=summary, run_results=df_results, daily_metrics=df_daily)
