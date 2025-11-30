"""
MCB Crash Test Library

Reusable library for running Master Cell Bank (MCB) crash test simulations.
Supports configurable parameters, deterministic testing, and dashboard asset generation.
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
# Import Workflow type for type hinting (using string to avoid circular imports if any)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cell_os.workflows import Workflow


@dataclass
class MCBTestConfig:
    """Configuration for MCB crash test simulation."""
    num_simulations: int = 100
    target_mcb_vials: int = 30
    cells_per_vial: float = 1e6
    random_seed: Optional[int] = 123
    enable_failures: bool = True
    output_dir: Optional[str] = None  # None means no disk assets
    cell_line: str = "U2OS"
    starting_vials: int = 3
    workflow: Optional['Workflow'] = None


@dataclass
class MCBTestResult:
    """Result of MCB crash test simulation."""
    summary: Dict[str, Any]
    run_results: pd.DataFrame
    daily_metrics: pd.DataFrame


from cell_os.simulation.workflow_simulator import WorkflowSimulator, SimulationConfig

class MCBSimulation:
    """
    Single MCB simulation run.
    Refactored to delegate to the shared WorkflowSimulator.
    """
    
    def __init__(self, run_id: int, config: MCBTestConfig, rng: np.random.Generator):
        self.run_id = run_id
        self.config = config
        self.rng = rng
        
    def run(self):
        """Execute the full MCB workflow using WorkflowSimulator."""
        # Map MCBTestConfig to SimulationConfig
        sim_config = SimulationConfig(
            target_vials=self.config.target_mcb_vials,
            cells_per_vial=self.config.cells_per_vial,
            starting_vials=self.config.starting_vials,
            cell_line=self.config.cell_line,
            enable_failures=self.config.enable_failures,
            workflow=self.config.workflow
        )
        
        # Instantiate and run simulator
        simulator = WorkflowSimulator(sim_config, self.rng)
        result = simulator.run()
        
        # Convert SimulationResult to the dictionary format expected by the harness
        # This acts as an adapter to maintain compatibility with run_mcb_crash_test
        
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
            "had_contamination": "contamination" in str(result.failures).lower(), # Approximate check
            "terminal_failure": not result.success,
            "failed_reason": str(result.failures) if result.failures else "",
            "total_media_l": result.summary.get("total_media_l", 0.0),
            "failures": result.failures,
            "violations": result.violations,
            "daily_metrics": daily_metrics_list
        }


def run_mcb_crash_test(config: MCBTestConfig) -> MCBTestResult:
    """
    Run a pilot scale U2OS MCB crash test and return a summary dict.
    If output_dir is provided, also write CSV and JSON assets there.
    """
    # Set up RNG
    if config.random_seed is not None:
        rng = np.random.default_rng(config.random_seed)
    else:
        rng = np.random.default_rng()
    
    # Run simulations
    results = []
    all_daily = []
    
    for i in range(config.num_simulations):
        sim = MCBSimulation(i, config, rng)
        res = sim.run()
        results.append(res)
        
        for d in res["daily_metrics"]:
            d["run_id"] = i
            all_daily.append(d)
    
    # Create DataFrames
    df_results = pd.DataFrame(results)
    df_daily = pd.DataFrame(all_daily) if all_daily else pd.DataFrame(columns=["run_id", "day", "total_cells"])
    
    # Calculate summary
    contaminated_runs = len(df_results[df_results["had_contamination"] == True])
    failed_runs = len(df_results[df_results["terminal_failure"] == True])
    success_runs = len(df_results[df_results["final_vials"] > 0])
    
    summary = {
        "total_runs": config.num_simulations,
        "successful_runs": success_runs,
        "success_rate": success_runs / config.num_simulations,
        "contaminated_runs": contaminated_runs,
        "failed_runs": failed_runs,
        "vials_p5": float(df_results["final_vials"].quantile(0.05)),
        "vials_p50": float(df_results["final_vials"].median()),
        "vials_p95": float(df_results["final_vials"].quantile(0.95)),
        "waste_p50": float(df_results["waste_vials"].median()),
        "waste_total": float(df_results["waste_vials"].sum()),
        "waste_cells_p50": float(df_results["waste_cells"].median()),
        "waste_vials_eq_p50": float(df_results["waste_vials_equivalent"].median()),
        "waste_fraction_p50": float(df_results["waste_fraction"].median()),
        "duration_p50": float(df_results["duration_days"].median()),
        "failures": [f for sublist in df_results["failures"] for f in sublist],
        "violations": [v for sublist in df_results["violations"] for v in sublist]
    }
    
    # Write assets if output_dir specified
    if config.output_dir:
        output_path = Path(config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write summary JSON
        with open(output_path / "mcb_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        # Write CSVs
        df_results.to_csv(output_path / "mcb_run_results.csv", index=False)
        df_daily.to_csv(output_path / "mcb_daily_metrics.csv", index=False)
        
        # Generate plots
        plots = _generate_plots(df_results, df_daily, config)
        with open(output_path / "plots_manifest.json", "w") as f:
            json.dump(plots, f)
        
        # Generate dashboard manifest
        manifest = {
            "title": f"MCB Crash Test ({config.cell_line}) - Pilot Scale with Failures",
            "description": f"Simulation of {config.num_simulations} MCB generation runs starting from {config.starting_vials} vendor vials (Target: {config.target_mcb_vials} vials total). Success rate: {summary['success_rate']:.1%}",
            "components": [
                {"type": "metric", "title": "Success Rate", "value": f"{summary['success_rate']:.1%}"},
                {"type": "metric", "title": "Contaminated Runs", "value": summary["contaminated_runs"]},
                {"type": "metric", "title": "Failed Runs", "value": summary["failed_runs"]},
                {"type": "metric", "title": "Median Vials (Success)", "value": summary["vials_p50"]},
                {"type": "metric", "title": "Median Waste Fraction", "value": f"{summary['waste_fraction_p50']:.1%}"},
                {"type": "plot", "title": "Vial Distribution", "data": "dist_vials"},
                {"type": "plot", "title": "Waste Distribution", "data": "dist_waste"},
                {"type": "plot", "title": "Growth Trajectories", "data": "growth_curves"},
                {"type": "table", "title": "Run Results", "data": "mcb_run_results.csv"}
            ]
        }
        with open(output_path / "dashboard_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
    
    return MCBTestResult(summary=summary, run_results=df_results, daily_metrics=df_daily)


def _generate_plots(df_results: pd.DataFrame, df_daily: pd.DataFrame, config: MCBTestConfig) -> Dict[str, str]:
    """Generate base64-encoded plots."""
    plots = {}
    
    # Distribution of Vials
    plt.figure(figsize=(10, 6))
    plt.hist(df_results["final_vials"], bins=30, color='skyblue', edgecolor='black')
    plt.title("Distribution of MCB Vials Generated")
    plt.xlabel("Number of Vials")
    plt.ylabel("Frequency")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plots["dist_vials"] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    # Growth Curves
    plt.figure(figsize=(10, 6))
    if not df_daily.empty and "run_id" in df_daily.columns:
        for i in range(min(50, config.num_simulations)):
            run_data = df_daily[df_daily["run_id"] == i]
            if not run_data.empty:
                plt.plot(run_data["day"], run_data["total_cells"], alpha=0.3, color='green')
    plt.title("Cell Growth Trajectories (First 50 Runs)")
    plt.xlabel("Day")
    plt.ylabel("Total Cells")
    plt.yscale('log')
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plots["growth_curves"] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    # Waste Distribution
    plt.figure(figsize=(10, 6))
    plt.hist(df_results["waste_fraction"], bins=30, color='coral', edgecolor='black')
    plt.title("Distribution of Waste Fraction")
    plt.xlabel("Waste Fraction (waste_cells / total_cells_produced)")
    plt.ylabel("Frequency")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plots["dist_waste"] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    return plots
