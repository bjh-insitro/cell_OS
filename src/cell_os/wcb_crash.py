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


@dataclass
class WCBTestConfig:
    """Configuration for WCB crash test simulation."""
    num_simulations: int = 100
    target_wcb_vials: int = 10
    cells_per_vial: float = 1e6
    random_seed: Optional[int] = 123
    enable_failures: bool = True
    output_dir: Optional[str] = None
    cell_line: str = "U2OS"
    starting_mcb_passage: int = 3  # MCB usually frozen at P3-P5
    include_qc: bool = True


@dataclass
class WCBTestResult:
    """Result of WCB crash test simulation."""
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
            "culture_bottle": 3.00,
            "agar_plate": 1.50,
        }
        return prices.get(item_id, 0.0)
    
    def consume_stock(self, resource_id, quantity, transaction_meta=None):
        pass


class WCBSimulation:
    """Single WCB simulation run driven by WorkflowBuilder."""
    
    def __init__(self, run_id: int, config: WCBTestConfig, rng: np.random.Generator):
        self.run_id = run_id
        self.config = config
        self.rng = rng
        
        self.vm = BiologicalVirtualMachine(simulation_speed=1000.0)
        self.executor = WorkflowExecutor(db_path=":memory:", hardware=self.vm, inventory_manager=MockInventory())
        self.vessels = VesselLibrary()
        self.ops = ParametricOps(self.vessels, MockInventory())
        
        if config.enable_failures:
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
        self.max_passage = 0
        
    def run(self):
        """Execute the WCB workflow defined by WorkflowBuilder."""
        try:
            # 1. Build Workflow
            from cell_os.workflows import WorkflowBuilder
            builder = WorkflowBuilder(self.ops)
            workflow = builder.build_working_cell_bank(
                target_vials=self.config.target_wcb_vials,
                cells_per_vial=self.config.cells_per_vial,
                starting_passage=self.config.starting_mcb_passage,
                include_qc=self.config.include_qc
            )
            
            # 2. Execute Ops
            ops = workflow.processes[0].ops
            for op in ops:
                self._execute_op(op)
                if self.terminal_failure:
                    break
                
        except Exception as e:
            self.failures.append(f"Exception: {str(e)}")
            self.terminal_failure = True
            self.failed_reason = f"Exception: {str(e)}"
            
        return self._compile_results()

    def _execute_op(self, op):
        """Map UnitOp to simulation logic."""
        self._track_resources(op)
        
        # Map op type to logic
        if "Thaw" in op.uo_id:
            self._phase_thaw()
        elif "Feed" in op.uo_id:
            # Feed implies maintenance/growth
            # We simulate growth until confluence or max time
            self._phase_grow()
        elif "Passage" in op.uo_id:
            # Not expected in 1->10 workflow, but handled if present
            self._perform_passage(self.active_flasks)
        elif "Harvest" in op.uo_id:
            pass # Just a logical step, actual harvest happens at freeze
        elif "Freeze" in op.uo_id:
            self._phase_freeze()
        elif "Myco" in op.uo_id or "Sterility" in op.uo_id:
            self._perform_qc(op)

    def _phase_thaw(self):
        """Thaw 1 MCB vial into T75."""
        flask_id = "Flask_WCB_Start"
        
        # MCB vial typically has 1e6 cells
        initial_cells = self.rng.normal(1e6, 1e5)
        
        # Seed with starting passage number
        self.vm.seed_vessel(flask_id, self.config.cell_line, initial_cells, capacity=2.5e7)
        state = self.vm.vessel_states[flask_id]
        state.passage_number = self.config.starting_mcb_passage
        self.max_passage = state.passage_number
        
        self.active_flasks.append(flask_id)
        
    def _phase_grow(self):
        """Simulate growth period (Feed step)."""
        # Grow for up to 7 days or until confluent
        for _ in range(7):
            self.day += 1
            self.vm.advance_time(24.0)
            self._record_daily_metrics()
            
            # Check contamination
            self._check_contamination()
            if self.terminal_failure:
                return
            
            # Check confluence
            ready = True
            for f in self.active_flasks:
                state = self.vm.get_vessel_state(f)
                if state["confluence"] < 0.8:
                    ready = False
            
            if ready:
                break

    def _check_contamination(self):
        if self.failure_sim:
            for flask_id in self.active_flasks:
                vessel_obj = self.vm.vessel_states.get(flask_id)
                days_in_culture = (self.vm.simulated_time - vessel_obj.last_passage_time) / 24.0
                failure = self.failure_sim.check_for_contamination(flask_id, days_in_culture)
                if failure:
                    self.had_contamination = True
                    self.terminal_failure = True
                    self.failed_reason = failure.description
                    self.failures.append(f"TERMINAL: {failure.description} in {flask_id}")
                    self.active_flasks = []
                    return

    def _perform_passage(self, source_flasks: List[str]):
        """Passage cells (if needed)."""
        # Simplified passage logic for compatibility
        new_flasks = []
        for source_id in source_flasks:
            state = self.vm.get_vessel_state(source_id)
            if not state: continue
            
            total_cells = state["cell_count"]
            current_p = state["passage_number"]
            
            # 1:5 split
            split_ratio = 5
            cells_per_new_flask = total_cells / split_ratio
            
            for i in range(split_ratio):
                new_id = f"Flask_P{current_p+1}_{self.day}_{i}"
                self.vm.seed_vessel(new_id, self.config.cell_line, cells_per_new_flask, capacity=2.5e7)
                self.vm.vessel_states[new_id].passage_number = current_p + 1
                new_flasks.append(new_id)
                
            del self.vm.vessel_states[source_id]
            
        self.active_flasks = new_flasks

    def _phase_freeze(self):
        """Harvest and freeze WCB vials."""
        total_cells = self._get_total_cells()
        potential_vials = int(total_cells / self.config.cells_per_vial)
        
        num_vials = min(potential_vials, self.config.target_wcb_vials)
        
        if potential_vials > num_vials:
            discarded_vials = potential_vials - num_vials
            discarded_cells = discarded_vials * self.config.cells_per_vial
            self.waste_vials = discarded_vials
            self.waste_cells = discarded_cells
        
        self.frozen_vials = num_vials

    def _perform_qc(self, op):
        """Simulate QC steps."""
        # Simulate QC failure (low probability)
        if self.failure_sim:
            # 0.5% chance of QC failure
            if self.rng.random() < 0.005:
                self.terminal_failure = True
                self.failed_reason = f"QC FAILURE: {op.name}"
                self.frozen_vials = 0

    def _get_total_cells(self):
        total = 0
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                total += state["cell_count"]
        return total

    def _record_daily_metrics(self):
        total_cells = self._get_total_cells()
        
        # Estimate Labor/BSC hours
        current_ops_load = self._calculate_daily_load()
        
        self.daily_metrics.append({
            "day": self.day,
            "total_cells": total_cells,
            "flask_count": len(self.active_flasks),
            "media_consumed": self.media_consumed_ml,
            "bsc_hours": current_ops_load['bsc'],
            "staff_hours": current_ops_load['staff']
        })

    def _calculate_daily_load(self):
        """Estimate load based on current state."""
        load = {'bsc': 0.0, 'staff': 0.0}
        
        if self.day == 1:
             load['bsc'] += 1.0
             load['staff'] += 1.0
             
        for f in self.active_flasks:
            state = self.vm.get_vessel_state(f)
            if not state: continue
            
            if state['confluence'] > 0.8:
                load['bsc'] += 0.5
                load['staff'] += 0.75
            else:
                load['bsc'] += 0.1
                load['staff'] += 0.15
                
        return load

    def _track_resources(self, op):
        if "Feed" in op.name or "Passage" in op.name:
            self.media_consumed_ml += 15.0
        elif "Thaw" in op.name:
            self.media_consumed_ml += 50.0
        elif "Myco" in op.name:
            self.media_consumed_ml += 5.0 # Sample volume
        elif "Sterility" in op.name:
            self.media_consumed_ml += 10.0

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
            "max_passage": self.max_passage,
            "failures": self.failures,
            "violations": self.violations,
            "daily_metrics": self.daily_metrics
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
