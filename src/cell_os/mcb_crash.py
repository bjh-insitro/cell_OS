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


@dataclass
class MCBTestResult:
    """Result of MCB crash test simulation."""
    summary: Dict[str, Any]
    run_results: pd.DataFrame
    daily_metrics: pd.DataFrame


class MockInventory:
    """Mock inventory for simulation."""
    def get_price(self, item_id: str) -> float:
        prices = {
            "tube_50ml_conical": 0.50,
            "tube_15ml_conical": 0.30,
            "pipette_25ml": 0.40,
            "pipette_10ml": 0.30,
            "pipette_5ml": 0.25,
            "pipette_2ml": 0.20,
            "tip_1000ul_lr": 0.05,
            "tip_200ul_lr": 0.02,
            "cryovial_1_8ml": 0.75,
            "flask_T75": 2.50,
            "flask_T175": 4.00,
            "flask_T225": 5.50,
        }
        return prices.get(item_id, 0.0)
    
    def consume_stock(self, resource_id, quantity, transaction_meta=None):
        pass


class MCBSimulation:
    """Single MCB simulation run."""
    
    def __init__(self, run_id: int, config: MCBTestConfig, rng: np.random.Generator):
        self.run_id = run_id
        self.config = config
        self.rng = rng
        
        self.vm = BiologicalVirtualMachine(simulation_speed=1000.0)
        self.executor = WorkflowExecutor(db_path=":memory:", hardware=self.vm, inventory_manager=MockInventory())
        self.vessels = VesselLibrary()
        self.ops = ParametricOps(self.vessels, MockInventory())
        
        if config.enable_failures:
            # Use the same RNG for failure simulator
            self.failure_sim = FailureModeSimulator(rng=rng)
        else:
            self.failure_sim = None
        
        # Metrics
        self.history = []
        self.daily_metrics = []
        self.failures = []
        self.violations = []
        self.media_consumed_ml = 0.0
        self.waste_vials = 0
        self.waste_cells = 0.0
        
        # Failure tracking
        self.had_contamination = False
        self.terminal_failure = False
        self.failed_reason = None
        
        # State
        self.active_flasks = []
        self.frozen_vials = 0
        self.day = 0
        
    def run(self):
        """Execute the full MCB workflow."""
        try:
            self._phase_thaw()
            
            target_total_cells = self.config.target_mcb_vials * self.config.cells_per_vial
            
            while self._get_total_cells() < target_total_cells:
                self.day += 1
                self.vm.advance_time(24.0)
                self._record_daily_metrics()
                
                if not self.active_flasks:
                    self.failures.append("All flasks lost")
                    break
                    
                self._manage_culture()
                
                if self.day > 60:
                    self.failures.append("Timeout: Expansion took too long")
                    break
            
            if self.active_flasks:
                self._phase_freeze()
                
        except Exception as e:
            self.failures.append(f"Exception: {str(e)}")
            
        return self._compile_results()

    def _phase_thaw(self):
        """Thaw vendor vials into T75 flasks."""
        for i in range(self.config.starting_vials):
            flask_id = f"Flask_P1_{i+1}"
            
            op = self.ops.op_thaw(flask_id, cell_line=self.config.cell_line)
            self._track_resources(op)
            
            initial_cells = self.rng.normal(1e6, 1e5)
            self.vm.seed_vessel(flask_id, self.config.cell_line, initial_cells, capacity=2.5e7)
            self.active_flasks.append(flask_id)

    def _manage_culture(self):
        """Check status and feed or passage."""
        to_passage = []
        surviving_flasks = []
        
        for flask_id in self.active_flasks:
            vessel_obj = self.vm.vessel_states.get(flask_id)
            if not vessel_obj:
                continue
            
            # Check for contamination if enabled
            if self.failure_sim:
                days_in_culture = (self.vm.simulated_time - vessel_obj.last_passage_time) / 24.0
                failure = self.failure_sim.check_for_contamination(flask_id, days_in_culture)
                if failure:
                    self.had_contamination = True
                    self.terminal_failure = True
                    self.failed_reason = failure.description
                    self.failures.append(f"TERMINAL: {failure.description} in {flask_id}")
                    # Clear all flasks
                    for fid in self.active_flasks:
                        if fid in self.vm.vessel_states:
                            del self.vm.vessel_states[fid]
                    self.active_flasks = []
                    return
                
            surviving_flasks.append(flask_id)
            
            state = self.vm.get_vessel_state(flask_id)
            
            if state["confluence"] > 1.0:
                self.violations.append(f"Overconfluence in {flask_id}: {state['confluence']:.2f}")
            
            if state["confluence"] > 0.8:
                to_passage.append(flask_id)
            elif state["confluence"] < 0.1 and self.day > 5:
                self.violations.append(f"Stagnation in {flask_id}")
            else:
                op = self.ops.op_feed(flask_id, media="mtesr_plus_kit")
                self._track_resources(op)
        
        self.active_flasks = surviving_flasks
        
        if to_passage:
            self._perform_passage(to_passage)

    def _perform_passage(self, source_flasks: List[str]):
        """Passage cells, expanding to more flasks."""
        new_flasks = []
        
        for source_id in source_flasks:
            state = self.vm.get_vessel_state(source_id)
            if not state:
                continue
            
            total_cells = state["cell_count"]
            viability = state["viability"]
            
            cells_per_flask = 0.5e6
            num_new_flasks = int(total_cells / cells_per_flask)
            if num_new_flasks < 1:
                num_new_flasks = 1
            
            if num_new_flasks > 20:
                num_new_flasks = 20
                self.violations.append(f"Split ratio capped for {source_id}")
            
            split_ratio = total_cells / (num_new_flasks * cells_per_flask)
            
            op = self.ops.op_passage(source_id, ratio=int(split_ratio), cell_line=self.config.cell_line)
            self._track_resources(op)
            
            passage_stress = 0.025
            new_viability = viability * (1.0 - passage_stress)
            cells_per_new_flask = total_cells / num_new_flasks
            
            current_p = state["passage_number"]
            for i in range(num_new_flasks):
                new_id = f"Flask_P{current_p+1}_{self.day}_{i}_{source_id[-3:]}"
                self.vm.seed_vessel(new_id, self.config.cell_line, cells_per_new_flask, capacity=2.5e7)
                new_state = self.vm.vessel_states[new_id]
                new_state.viability = new_viability
                new_state.passage_number = current_p + 1
                new_flasks.append(new_id)
                
            if source_id in self.vm.vessel_states:
                del self.vm.vessel_states[source_id]
            self.active_flasks.remove(source_id)
            
        self.active_flasks.extend(new_flasks)

    def _phase_freeze(self):
        """Harvest all and freeze target number of vials, discarding excess."""
        total_cells = self._get_total_cells()
        potential_vials = int(total_cells / self.config.cells_per_vial)
        
        num_vials = min(potential_vials, self.config.target_mcb_vials)
        
        if potential_vials > num_vials:
            discarded_vials = potential_vials - num_vials
            discarded_cells = discarded_vials * self.config.cells_per_vial
            self.waste_vials = discarded_vials
            self.waste_cells = discarded_cells
        
        op = self.ops.op_freeze(num_vials=num_vials)
        self._track_resources(op)
        
        self.frozen_vials = num_vials

    def _get_total_cells(self):
        total = 0
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                total += state["cell_count"]
        return total

    def _record_daily_metrics(self):
        total_cells = self._get_total_cells()
        
        # Estimate Labor/BSC hours for this day
        # Base load
        bsc_hours = 0.0
        staff_hours = 0.1 # Daily check
        
        # We need to know what operations happened TODAY.
        # This is tricky because _manage_culture runs AFTER this record call in the loop.
        # Let's move _record_daily_metrics to END of loop or track ops during the day.
        
        # Better: Track ops in a list for the current day
        current_ops_load = self._calculate_daily_load()
        bsc_hours += current_ops_load['bsc']
        staff_hours += current_ops_load['staff']
        
        # Calculate average confluence and viability
        confluences = []
        viabilities = []
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                confluences.append(state["confluence"])
                viabilities.append(state["viability"])
        
        avg_confluence = sum(confluences) / len(confluences) if confluences else 0.0
        avg_viability = sum(viabilities) / len(viabilities) if viabilities else 0.0

        self.daily_metrics.append({
            "day": self.day,
            "total_cells": total_cells,
            "flask_count": len(self.active_flasks),
            "media_consumed": self.media_consumed_ml,
            "bsc_hours": bsc_hours,
            "staff_hours": staff_hours,
            "avg_confluence": avg_confluence,
            "avg_viability": avg_viability
        })
        
        # Reset daily counters if any (we don't have them yet, so we rely on state)

    def _calculate_daily_load(self):
        """Estimate load based on current state and likely actions."""
        load = {'bsc': 0.0, 'staff': 0.0}
        
        # If day 0 (Thaw) - handled outside loop usually, but let's approximate
        if self.day == 1: # First day of expansion
             load['bsc'] += 1.0 # Thaw cleanup / first check
             load['staff'] += 1.0
             
        # For each flask, check if it needs feeding or passage
        for f in self.active_flasks:
            state = self.vm.get_vessel_state(f)
            if not state: continue
            
            if state['confluence'] > 0.8:
                # Passage
                load['bsc'] += 0.5
                load['staff'] += 0.75
            else:
                # Feed
                load['bsc'] += 0.1
                load['staff'] += 0.15
                
        return load

    def _track_resources(self, op):
        """Extract cost and media usage from UnitOp."""
        if "Feed" in op.name or "Passage" in op.name:
            self.media_consumed_ml += 15.0
        elif "Thaw" in op.name:
            self.media_consumed_ml += 50.0

    def _compile_results(self):
        final_cells_banked = self.frozen_vials * self.config.cells_per_vial
        total_cells_produced = final_cells_banked + self.waste_cells
        waste_fraction = self.waste_cells / total_cells_produced if total_cells_produced > 0 else 0.0
        
        return {
            "run_id": self.run_id,
            "duration_days": self.day,
            "final_vials": self.frozen_vials,
            "waste_vials": self.waste_vials,
            "waste_cells": self.waste_cells,
            "waste_vials_equivalent": self.waste_cells / self.config.cells_per_vial,
            "waste_fraction": waste_fraction,
            "had_contamination": self.had_contamination,
            "terminal_failure": self.terminal_failure,
            "failed_reason": self.failed_reason if self.failed_reason else "",
            "total_media_l": self.media_consumed_ml / 1000.0,
            "failures": self.failures,
            "violations": self.violations,
            "daily_metrics": self.daily_metrics
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
