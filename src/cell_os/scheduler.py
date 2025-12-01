"""
Scheduler for Cell OS.

Uses Constraint Programming (CP-SAT) to optimize workflow scheduling
under resource constraints.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
import collections

@dataclass
class Resource:
    id: str
    name: str
    capacity: int = 1  # Number of concurrent tasks

@dataclass
class Task:
    id: str
    name: str
    duration_min: int
    resources_required: List[str]  # List of Resource IDs
    predecessors: List[str] = None # List of Task IDs
    
    def __post_init__(self):
        if self.predecessors is None:
            self.predecessors = []

@dataclass
class ScheduleResult:
    task_id: str
    start_time: int
    end_time: int
    resource_assignments: Dict[str, str] # resource_id -> specific_unit (if applicable)

class Scheduler:
    """
    Optimizes task scheduling using Google OR-Tools CP-SAT solver.
    """
    
    def __init__(self, resources: List[Resource]):
        self.resources = {r.id: r for r in resources}
        
    def schedule(self, tasks: List[Task], horizon_min: int = 10080) -> List[ScheduleResult]:
        """
        Schedule tasks to minimize makespan (total duration).
        
        Args:
            tasks: List of tasks to schedule
            horizon_min: Max scheduling horizon in minutes (default 7 days)
            
        Returns:
            List of ScheduleResult objects
        """
        model = cp_model.CpModel()
        
        # --- Variables ---
        
        # Task intervals
        task_starts = {}
        task_ends = {}
        task_intervals = {}
        
        for task in tasks:
            start_var = model.NewIntVar(0, horizon_min, f'start_{task.id}')
            end_var = model.NewIntVar(0, horizon_min, f'end_{task.id}')
            interval_var = model.NewIntervalVar(
                start_var, task.duration_min, end_var, f'interval_{task.id}'
            )
            
            task_starts[task.id] = start_var
            task_ends[task.id] = end_var
            task_intervals[task.id] = interval_var
            
        # --- Constraints ---
        
        # 1. Precedence constraints
        for task in tasks:
            for pred_id in task.predecessors:
                if pred_id in task_ends:
                    # Start >= Predecessor End
                    model.Add(task_starts[task.id] >= task_ends[pred_id])
                    
        # 2. Resource constraints (Cumulative)
        # Group tasks by resource requirement
        resource_usage = collections.defaultdict(list)
        for task in tasks:
            for res_id in task.resources_required:
                resource_usage[res_id].append(task_intervals[task.id])
                
        for res_id, intervals in resource_usage.items():
            if res_id in self.resources:
                capacity = self.resources[res_id].capacity
                # If capacity is 1, use NoOverlap
                if capacity == 1:
                    model.AddNoOverlap(intervals)
                else:
                    # For capacity > 1, we need Cumulative constraint
                    # OR-Tools Cumulative requires demands. Assuming demand=1 for now.
                    demands = [1] * len(intervals)
                    model.AddCumulative(intervals, demands, capacity)
                    
        # --- Objective ---
        
        # Minimize makespan (end time of the last task)
        makespan = model.NewIntVar(0, horizon_min, 'makespan')
        model.AddMaxEquality(makespan, [task_ends[t.id] for t in tasks])
        model.Minimize(makespan)
        
        # --- Solve ---
        
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        results = []
        task_lookup = {task.id: task for task in tasks}
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Schedule found! Makespan: {solver.Value(makespan)} min")
            for task in tasks:
                start = solver.Value(task_starts[task.id])
                end = solver.Value(task_ends[task.id])
                results.append(ScheduleResult(
                    task_id=task.id,
                    start_time=start,
                    end_time=end,
                    resource_assignments={}
                ))

            self._assign_resource_units(results, task_lookup)
        else:
            print("No solution found.")
            
        return results

    def visualize_schedule(self, results: List[ScheduleResult]):
        """Print a simple Gantt chart."""
        if not results:
            print("No schedule to visualize.")
            return
            
        # Sort by start time
        sorted_results = sorted(results, key=lambda x: x.start_time)
        
        print("\n--- Schedule Gantt ---")
        for r in sorted_results:
            assignment_str = ""
            if r.resource_assignments:
                formatted = ", ".join(
                    f"{res}:{unit}" for res, unit in r.resource_assignments.items()
                )
                assignment_str = f" [{formatted}]"
            print(f"[{r.start_time:4d} - {r.end_time:4d}] {r.task_id}{assignment_str}")

    def _assign_resource_units(self, results: List[ScheduleResult], tasks: Dict[str, Task]):
        """Assign specific resource units post-solve."""
        result_lookup = {r.task_id: r for r in results}

        for res_id, resource in self.resources.items():
            relevant = [
                result_lookup[task_id]
                for task_id, task in tasks.items()
                if res_id in task.resources_required and task_id in result_lookup
            ]
            if not relevant:
                continue

            capacity = resource.capacity
            if capacity == 1:
                for r in relevant:
                    r.resource_assignments[res_id] = res_id
                continue

            relevant.sort(key=lambda x: x.start_time)
            unit_available = [0] * capacity

            for sched in relevant:
                assigned_unit = None
                for idx in range(capacity):
                    if unit_available[idx] <= sched.start_time:
                        assigned_unit = idx
                        break

                if assigned_unit is None:
                    assigned_unit = min(range(capacity), key=lambda i: unit_available[i])

                unit_available[assigned_unit] = max(unit_available[assigned_unit], sched.end_time)
                sched.resource_assignments[res_id] = f"{res_id}_{assigned_unit}"
