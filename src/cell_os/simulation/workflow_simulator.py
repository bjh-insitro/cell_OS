"""
Workflow Simulator - Production simulation engine.

Simulates biological workflows with dynamic growth, resource tracking, and optional failure modes.
Separated from crash test harnesses for clarity and reusability.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cell_os.workflows import Workflow
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.failure_modes import FailureModeSimulator


@dataclass
class SimulationConfig:
    """Configuration for workflow simulation."""
    workflow: Workflow
    target_vials: int
    cells_per_vial: float
    cell_line: str
    enable_failures: bool = False
    random_seed: Optional[int] = None
    starting_vials: int = 1


@dataclass
class SimulationResult:
    """Result of a workflow simulation."""
    success: bool
    vials_generated: int
    duration_days: int
    daily_metrics: pd.DataFrame
    summary: Dict[str, Any]
    failures: List[str]
    violations: List[str]


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


class WorkflowSimulator:
    """
    Production simulation engine for biological workflows.
    
    Takes a Workflow object and simulates it with biological dynamics,
    resource tracking, and optional failure modes.
    """
    
    def __init__(self, config: SimulationConfig, rng: np.random.Generator):
        self.config = config
        self.rng = rng
        
        # Initialize virtual machine
        self.vm = BiologicalVirtualMachine(simulation_speed=1000.0)
        
        # Initialize operations
        self.vessels = VesselLibrary()
        self.ops = ParametricOps(self.vessels, MockInventory())
        
        # Failure simulator (optional)
        if config.enable_failures:
            self.failure_sim = FailureModeSimulator(rng=rng)
        else:
            self.failure_sim = None
        
        # Metrics tracking
        self.daily_metrics = []
        self.failures = []
        self.violations = []
        self.media_consumed_ml = 0.0
        self.waste_vials = 0
        self.waste_cells = 0.0
        
        # State
        self.active_flasks = []
        self.frozen_vials = 0
        self.day = 0
        self.terminal_failure = False
        self.failed_reason = None
        self.daily_ops = []  # Track operations for daily labor calculation
        
        # Extract params from workflow
        self.flask_type = "flask_T75"
        self._parse_workflow_params()
    
    def _parse_workflow_params(self):
        """Extract simulation parameters from the workflow."""
        if not self.config.workflow:
            return
            
        for op in self.config.workflow.all_ops:
            if "thaw" in op.name.lower():
                if hasattr(op, 'items'):
                    for item in op.items:
                        if "flask" in item.resource_id.lower():
                            self.flask_type = item.resource_id
                            break
    
    def run(self) -> SimulationResult:
        """
        Execute the workflow simulation.
        
        Returns:
            SimulationResult with success status, metrics, and generated vials
        """
        try:
            self.daily_ops = []
            self._phase_thaw()
            
            # Record Day 0 (Thaw day)
            self._record_daily_metrics()
            self.daily_ops = []
            
            target_total_cells = self.config.target_vials * self.config.cells_per_vial
            
            # Run until we have enough cells OR high enough confluence for harvest
            # Stop when EITHER condition is met to avoid over-expansion
            while True:
                total_cells = self._get_total_cells()
                avg_conf = self._get_avg_confluence()
                
                # Stop ONLY if we have enough cells AND confluence is ready for harvest (approx 80%)
                # User requirement: "stop at ~80% ... true for all cell lines"
                if total_cells >= target_total_cells and avg_conf >= 0.75:
                    break
                
                self.day += 1
                self.vm.advance_time(24.0)
                
                if not self.active_flasks:
                    self.failures.append("All flasks lost")
                    break
                    
                self._manage_culture()
                
                # Record metrics for this day (after operations)
                self._record_daily_metrics()
                self.daily_ops = []
                
                if self.day > 60:
                    self.failures.append("Timeout: Expansion took too long")
                    break
            
            if self.active_flasks:
                self._phase_freeze()
                # Record final day metrics (Freeze day)
                self.day += 1
                self._record_daily_metrics()
                self.daily_ops = []
                
        except Exception as e:
            self.failures.append(f"Exception: {str(e)}")
            
        return self._compile_results()
    
    def _phase_thaw(self):
        """Thaw starting vials into flasks."""
        for i in range(self.config.starting_vials):
            flask_id = f"Flask_P1_{i+1}"
            
            op = self.ops.op_thaw(flask_id, cell_line=self.config.cell_line)
            self._track_resources(op)
            self.daily_ops.append(op)
            
            initial_cells = self.rng.normal(1e6, 1e5)
            # Capacity depends on flask type
            capacity = 2.5e7  # Default T75
            if "175" in self.flask_type: capacity = 5.0e7
            if "225" in self.flask_type: capacity = 7.5e7
            
            self.vm.seed_vessel(flask_id, self.config.cell_line, initial_cells, capacity=capacity)
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
            
            # Only passage if we haven't reached our target yield yet
            # If we have enough cells, just let them grow to confluence for harvest
            target_reached = self._get_total_cells() >= (self.config.target_vials * self.config.cells_per_vial)
            
            if state["confluence"] > 0.75 and not target_reached:
                to_passage.append(flask_id)
            elif state["confluence"] < 0.1 and self.day > 5:
                self.violations.append(f"Stagnation in {flask_id}")
            else:
                op = self.ops.op_feed(flask_id, cell_line=self.config.cell_line)
                self._track_resources(op)
                self.daily_ops.append(op)
        
        self.active_flasks = surviving_flasks
        
        if to_passage:
            self._perform_passage(to_passage)
    
    def _perform_passage(self, source_flasks: List[str]):
        """Passage cells, expanding to more flasks."""
        new_flasks = []
        
        # Determine capacity based on flask_type
        capacity = 2.5e7
        if "175" in self.flask_type: capacity = 5.0e7
        if "225" in self.flask_type: capacity = 7.5e7
        
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
            self.daily_ops.append(op)
            
            passage_stress = 0.025
            new_viability = viability * (1.0 - passage_stress)
            cells_per_new_flask = total_cells / num_new_flasks
            
            current_p = state["passage_number"]
            for i in range(num_new_flasks):
                new_id = f"Flask_P{current_p+1}_{self.day}_{i}_{source_id[-3:]}"
                self.vm.seed_vessel(new_id, self.config.cell_line, cells_per_new_flask, capacity=capacity)
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
        
        num_vials = min(potential_vials, self.config.target_vials)
        
        if potential_vials > num_vials:
            discarded_vials = potential_vials - num_vials
            discarded_cells = discarded_vials * self.config.cells_per_vial
            self.waste_vials = discarded_vials
            self.waste_cells = discarded_cells
        
        op = self.ops.op_freeze(num_vials=num_vials)
        self._track_resources(op)
        
        self.frozen_vials = num_vials
        self.active_flasks = []  # Clear flasks to reflect harvest
    
    def _get_total_cells(self):
        total = 0
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                total += state["cell_count"]
        return total
    
    def _get_avg_confluence(self):
        """Calculate average confluence of active flasks."""
        if not self.active_flasks:
            return 0.0
            
        confluences = []
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                confluences.append(state["confluence"])
        
        return sum(confluences) / len(confluences) if confluences else 0.0
    
    def _record_daily_metrics(self):
        """Record metrics for the current day."""
        total_cells = self._get_total_cells()
        
        # Estimate Labor/BSC hours for this day
        current_ops_load = self._calculate_daily_load()
        bsc_hours = current_ops_load['bsc']
        staff_hours = 0.1 + current_ops_load['staff']  # Daily check + ops
        
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
    
    def _track_resources(self, op):
        """Track resources consumed by an operation."""
        # Extract media consumption from op
        if hasattr(op, 'items'):
            for item in op.items:
                if 'media' in item.resource_id.lower() or 'kit' in item.resource_id.lower():
                    self.media_consumed_ml += item.quantity * 1000  # Convert L to mL
        
        # Fallback: estimate from op name
        if 'feed' in op.name.lower():
            self.media_consumed_ml += 15.0  # 15mL per feed
        elif 'thaw' in op.name.lower():
            self.media_consumed_ml += 50.0  # 50mL for thaw
    
    def _calculate_daily_load(self):
        """Calculate labor and BSC hours for operations."""
        total_minutes = 0.0
        
        def get_labor_minutes(op):
            # If op has sub-steps, sum their labor
            if op.sub_steps:
                return sum(get_labor_minutes(sub) for sub in op.sub_steps)
            else:
                # Atomic op: count time if staff attention is required
                return op.time_score if op.staff_attention > 0 else 0.0
        
        for op in self.daily_ops:
            total_minutes += get_labor_minutes(op)
            
        staff_hours = total_minutes / 60.0
        bsc_hours = staff_hours  # Assume BSC is used for all labor steps
        
        return {'staff': staff_hours, 'bsc': bsc_hours}
    
    def _compile_results(self) -> SimulationResult:
        """Compile final simulation results."""
        success = self.frozen_vials > 0 and not self.terminal_failure
        
        summary = {
            "run_id": 1,
            "duration_days": self.day,
            "final_vials": self.frozen_vials,
            "waste_vials": self.waste_vials,
            "waste_cells": self.waste_cells,
            "waste_vials_equivalent": self.waste_cells / self.config.cells_per_vial if self.config.cells_per_vial > 0 else 0,
            "waste_fraction": self.waste_vials / (self.frozen_vials + self.waste_vials) if (self.frozen_vials + self.waste_vials) > 0 else 0,
            "terminal_failure": self.terminal_failure,
            "failed_reason": self.failed_reason or "",
            "total_media_l": self.media_consumed_ml / 1000.0,
            "failures": self.failures,
            "violations": self.violations,
            "daily_metrics": self.daily_metrics
        }
        
        return SimulationResult(
            success=success,
            vials_generated=self.frozen_vials,
            duration_days=self.day,
            daily_metrics=pd.DataFrame(self.daily_metrics),
            summary=summary,
            failures=self.failures,
            violations=self.violations
        )
