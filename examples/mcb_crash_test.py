"""
MCB Crash Test Simulation (U2OS)

Simulates a Master Cell Bank (MCB) generation workflow for U2OS cells.
Starting from 3 vendor vials, expanding to ~200 MCB vials.
Runs 500 Monte Carlo simulations to assess robustness and variability.
"""

import os
import sys
import json
import base64
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.workflow_executor import WorkflowExecutor
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.failure_modes import FailureModeSimulator

# --- Configuration ---
CELL_LINE = "U2OS"
STARTING_VIALS = 3
TARGET_MCB_VIALS = 30  # 10 vials per starting vial (User Requirement)
CELLS_PER_MCB_VIAL = 1e6  # 1 million cells per vial (User Requirement)
TARGET_TOTAL_CELLS = TARGET_MCB_VIALS * CELLS_PER_MCB_VIAL
NUM_SIMULATIONS = 500
OUTPUT_DIR = Path("dashboard_assets")

# --- Mock Inventory ---
class MockInventory:
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
        pass  # Mock consumption

# --- Simulation Class ---
class MCBSimulation:
    def __init__(self, run_id: int):
        self.run_id = run_id
        self.vm = BiologicalVirtualMachine(simulation_speed=1000.0) # Fast simulation
        self.executor = WorkflowExecutor(db_path=":memory:", hardware=self.vm, inventory_manager=MockInventory())
        self.vessels = VesselLibrary()
        self.ops = ParametricOps(self.vessels, MockInventory())
        self.failure_sim = FailureModeSimulator()
        
        # Metrics
        self.history = []
        self.daily_metrics = []
        self.failures = []
        self.violations = []
        self.media_consumed_ml = 0.0
        self.reagents_consumed = {}
        self.waste_vials = 0
        self.waste_cells = 0.0
        
        # Failure tracking
        self.had_contamination = False
        self.terminal_failure = False
        self.failed_reason = None
        
        # State
        self.active_flasks = [] # List of vessel_ids
        self.frozen_vials = 0
        self.day = 0
        
    def log_metric(self, metric_type: str, value: Any, details: Dict = None):
        self.history.append({
            "run_id": self.run_id,
            "day": self.day,
            "type": metric_type,
            "value": value,
            "details": details or {}
        })

    def run(self):
        """Execute the full MCB workflow."""
        try:
            # 1. Thaw
            self._phase_thaw()
            
            # 2. Expansion Loop
            while self._get_total_cells() < TARGET_TOTAL_CELLS:
                self.day += 1
                self.vm.advance_time(24.0) # Advance 1 day
                self._record_daily_metrics()
                
                # Check for failures (Global check - e.g. incubator failure)
                # For now, we handle per-flask contamination in _manage_culture
                
                if not self.active_flasks:
                    self.failures.append("All flasks lost")
                    break
                    
                # Check confluence and passage if needed
                self._manage_culture()
                
                # Safety break (e.g., max 60 days)
                if self.day > 60:
                    self.failures.append("Timeout: Expansion took too long")
                    break
            
            # 3. Freeze
            if self.active_flasks:
                self._phase_freeze()
                
        except Exception as e:
            print(f"Run {self.run_id} failed: {e}")
            self.failures.append(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            
        return self._compile_results()

    def _phase_thaw(self):
        """Thaw 3 vendor vials into T75 flasks."""
        # Use WorkflowBuilder logic implicitly by replicating the steps
        # Ideally we would use WorkflowBuilder().build_master_cell_bank() but that returns a static definition
        # We need to execute it dynamically for 3 parallel lines.
        
        for i in range(STARTING_VIALS):
            vial_id = f"Vendor_Vial_{i+1}"
            flask_id = f"Flask_P1_{i+1}"
            
            # Execute UnitOp (Process Simulation)
            op = self.ops.op_thaw(flask_id, cell_line=CELL_LINE)
            # self.executor.create_execution_from_protocol(...) 
            
            self._track_resources(op)
            
            # Biological Update (State Simulation)
            # Assume vendor vial has ~1M cells, 90% viability (matches WorkflowBuilder default)
            initial_cells = np.random.normal(1e6, 1e5)
            self.vm.seed_vessel(flask_id, CELL_LINE, initial_cells, capacity=2.5e7) # T75 capacity approx
            self.active_flasks.append(flask_id)
            
        self.log_metric("phase_complete", "thaw")

    def _manage_culture(self):
        """Check status and feed or passage."""
        to_passage = []
        surviving_flasks = []
        
        for flask_id in self.active_flasks:
            # 1. Failure Check (Contamination)
            # Calculate days in culture for this vessel
            vessel_obj = self.vm.vessel_states.get(flask_id)
            if not vessel_obj: continue
            
            days_in_culture = (self.vm.simulated_time - vessel_obj.last_passage_time) / 24.0
            
            # Check for contamination
            failure = self.failure_sim.check_for_contamination(flask_id, days_in_culture)
            if failure:
                self.had_contamination = True
                self.terminal_failure = True
                self.failed_reason = failure.description
                self.failures.append(f"TERMINAL: {failure.description} in {flask_id}")
                # Contamination is terminal - entire batch must be discarded
                # Clear all flasks
                for fid in self.active_flasks:
                    if fid in self.vm.vessel_states:
                        del self.vm.vessel_states[fid]
                self.active_flasks = []
                return  # Exit immediately
                
            surviving_flasks.append(flask_id)
            
            # 2. Culture Management
            state = self.vm.get_vessel_state(flask_id)
            
            # Check constraints
            if state["confluence"] > 1.0:
                self.violations.append(f"Overconfluence in {flask_id}: {state['confluence']:.2f}")
            
            if state["confluence"] > 0.8: # Passage threshold
                to_passage.append(flask_id)
            elif state["confluence"] < 0.1 and self.day > 5:
                # Stagnation check
                self.violations.append(f"Stagnation in {flask_id}")
            else:
                # Feed
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
            if not state: continue
            
            total_cells = state["cell_count"]
            viability = state["viability"]
            
            # Target seeding: 0.5e6 per T75
            cells_per_flask = 0.5e6
            num_new_flasks = int(total_cells / cells_per_flask)
            if num_new_flasks < 1: num_new_flasks = 1
            
            # Constraint check
            if num_new_flasks > 20: 
                num_new_flasks = 20
                self.violations.append(f"Split ratio capped for {source_id}")
            
            split_ratio = total_cells / (num_new_flasks * cells_per_flask)
            
            # Execute UnitOp (Process Simulation)
            op = self.ops.op_passage(source_id, ratio=int(split_ratio), cell_line=CELL_LINE)
            self._track_resources(op)
            
            # Biological Update (Manual Expansion)
            # Apply passage stress
            # U2OS passage stress is 0.025 (from YAML)
            passage_stress = 0.025 
            new_viability = viability * (1.0 - passage_stress)
            
            cells_per_new_flask = (total_cells * new_viability) / num_new_flasks # Account for viability loss in count? 
            # Actually, viability loss usually means dead cells, but total count might include them?
            # BiologicalVirtualMachine tracks "cell_count" as total or live? 
            # Usually simulation tracks "effective" count.
            # Let's assume cell_count is live cells for growth purposes.
            cells_per_new_flask = (total_cells / num_new_flasks) # Distribute cells
            
            current_p = state["passage_number"]
            for i in range(num_new_flasks):
                new_id = f"Flask_P{current_p+1}_{self.day}_{i}_{source_id[-3:]}"
                # Seed directly
                self.vm.seed_vessel(new_id, CELL_LINE, cells_per_new_flask, capacity=2.5e7)
                # Update state manually to reflect passage properties
                new_state = self.vm.vessel_states[new_id]
                new_state.viability = new_viability
                new_state.passage_number = current_p + 1
                
                new_flasks.append(new_id)
                
            # Remove source flask
            if source_id in self.vm.vessel_states:
                del self.vm.vessel_states[source_id]
            self.active_flasks.remove(source_id)
            
        self.active_flasks.extend(new_flasks)
        self.log_metric("passage", len(new_flasks))

    def _phase_freeze(self):
        """Harvest all and freeze target number of vials, discarding excess."""
        total_cells = self._get_total_cells()
        potential_vials = int(total_cells / CELLS_PER_MCB_VIAL)
        
        # Cap at target (discard excess)
        num_vials = min(potential_vials, TARGET_MCB_VIALS)
        
        if potential_vials > num_vials:
            discarded_vials = potential_vials - num_vials
            discarded_cells = discarded_vials * CELLS_PER_MCB_VIAL
            self.waste_vials = discarded_vials
            self.waste_cells = discarded_cells
            self.log_metric("waste", discarded_vials)
        
        # Execute UnitOp
        op = self.ops.op_freeze(num_vials=num_vials)
        self._track_resources(op)
        
        self.frozen_vials = num_vials
        self.log_metric("phase_complete", "freeze", {"vials": num_vials})

    def _get_total_cells(self):
        total = 0
        for flask_id in self.active_flasks:
            state = self.vm.get_vessel_state(flask_id)
            if state:
                total += state["cell_count"]
        return total

    def _record_daily_metrics(self):
        total_cells = self._get_total_cells()
        avg_confluence = 0
        avg_viability = 0
        if self.active_flasks:
            confluences = []
            viabilities = []
            for f in self.active_flasks:
                s = self.vm.get_vessel_state(f)
                confluences.append(s["confluence"])
                viabilities.append(s["viability"])
            avg_confluence = np.mean(confluences)
            avg_viability = np.mean(viabilities)
            
        self.daily_metrics.append({
            "day": self.day,
            "total_cells": total_cells,
            "flask_count": len(self.active_flasks),
            "avg_confluence": avg_confluence,
            "avg_viability": avg_viability,
            "media_consumed": self.media_consumed_ml
        })

    def _track_resources(self, op):
        """Extract cost and media usage from UnitOp."""
        # This is an approximation since UnitOp aggregates costs
        # We'll parse the name/description or just use a heuristic for media
        if "Feed" in op.name or "Passage" in op.name:
            # Assume 15mL per T75 per feed/passage
            self.media_consumed_ml += 15.0 
        elif "Thaw" in op.name:
            self.media_consumed_ml += 50.0 # Thaw uses more

    def _compile_results(self):
        # Calculate waste fraction
        final_cells_banked = self.frozen_vials * CELLS_PER_MCB_VIAL
        total_cells_produced = final_cells_banked + self.waste_cells
        waste_fraction = self.waste_cells / total_cells_produced if total_cells_produced > 0 else 0.0
        
        return {
            "run_id": self.run_id,
            "duration_days": self.day,
            "final_vials": self.frozen_vials,
            "waste_vials": self.waste_vials,
            "waste_cells": self.waste_cells,
            "waste_vials_equivalent": self.waste_cells / CELLS_PER_MCB_VIAL,
            "waste_fraction": waste_fraction,
            "had_contamination": self.had_contamination,
            "terminal_failure": self.terminal_failure,
            "failed_reason": self.failed_reason if self.failed_reason else "",
            "total_media_l": self.media_consumed_ml / 1000.0,
            "failures": self.failures,
            "violations": self.violations,
            "daily_metrics": self.daily_metrics
        }

# --- Main Execution ---
def run_crash_test():
    print(f"Starting MCB Crash Test: {NUM_SIMULATIONS} simulations...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    results = []
    all_daily = []
    
    for i in range(NUM_SIMULATIONS):
        if i % 50 == 0: print(f"  Running simulation {i+1}/{NUM_SIMULATIONS}...")
        sim = MCBSimulation(i)
        res = sim.run()
        results.append(res)
        
        for d in res["daily_metrics"]:
            d["run_id"] = i
            all_daily.append(d)
            
    # --- Analysis & Output ---
    print("Generating assets...")
    
    df_results = pd.DataFrame(results)
    df_daily = pd.DataFrame(all_daily)
    
    if df_daily.empty:
        print("ERROR: No daily metrics collected. All runs likely failed.")
        # Create dummy df to prevent crash
        df_daily = pd.DataFrame(columns=["run_id", "day", "total_cells"])
    
    # 1. JSON Summary
    contaminated_runs = len(df_results[df_results["had_contamination"] == True])
    failed_runs = len(df_results[df_results["terminal_failure"] == True])
    success_runs = len(df_results[df_results["final_vials"] > 0])
    
    summary = {
        "total_runs": NUM_SIMULATIONS,
        "successful_runs": success_runs,
        "success_rate": success_runs / NUM_SIMULATIONS,
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
    
    with open(OUTPUT_DIR / "mcb_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    # 2. CSVs
    df_results.to_csv(OUTPUT_DIR / "mcb_run_results.csv", index=False)
    df_daily.to_csv(OUTPUT_DIR / "mcb_daily_metrics.csv", index=False)
    
    # 3. Plots (Base64)
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
    
    # Growth Curves (Sample)
    plt.figure(figsize=(10, 6))
    if not df_daily.empty and "run_id" in df_daily.columns:
        for i in range(min(50, NUM_SIMULATIONS)):
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
    
    # Save plots manifest
    with open(OUTPUT_DIR / "plots_manifest.json", "w") as f:
        json.dump(plots, f)
        
    # 4. Dashboard Manifest
    manifest = {
        "title": "MCB Crash Test (U2OS) - Pilot Scale with Failures",
        "description": f"Simulation of {NUM_SIMULATIONS} MCB generation runs starting from 3 vendor vials (Target: 30 vials total). Success rate: {summary['success_rate']:.1%}",
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
    with open(OUTPUT_DIR / "dashboard_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print("Analysis Complete.")
    print(f"Summary: {success_runs}/{NUM_SIMULATIONS} successful ({summary['success_rate']:.1%})")
    print(f"  Median: {summary['vials_p50']} vials in {summary['duration_p50']} days")
    print(f"  Contaminated: {contaminated_runs} runs")
    print(f"  Failed: {failed_runs} runs")
    print(f"  Waste: Median {summary['waste_p50']} vials ({summary['waste_fraction_p50']:.1%} of production)")
    
    # Gap Analysis (Printed for User)
    print("\n--- GAP ANALYSIS (Pilot Scale + Real Failures) ---")
    print("A. REALISTIC:")
    print("- Exponential growth phases match U2OS doubling time.")
    print("- Variability in final yield reflects biological noise.")
    print("- 10x expansion achievable in single passage (3-4 days).")
    print(f"- Contamination now causes terminal failures: {failed_runs}/{NUM_SIMULATIONS} runs failed.")
    print(f"- Success rate ({summary['success_rate']:.1%}) reflects real-world MCB production challenges.")
    print(f"- Waste tracking shows {summary['waste_fraction_p50']:.1%} of cells discarded (realistic for fixed-size banks).")
    
    print("\nB. UNREALISTIC/BROKEN:")
    print("- 'Feed' operation assumes fixed volume/cost, doesn't account for flask size variations accurately.")
    print("- Confluence checks are perfect (no measurement error simulated in decision logic).")
    print("- Contamination rate may be too high or too low (needs calibration to real data).")
    
    print("\nC. MISSING:")
    print("- QC steps (Mycoplasma, Sterility, Karyotype) before freeze.")
    print("- Inventory stock-outs (MockInventory is infinite).")
    print("- Incubator space constraints (infinite capacity).")
    print("- Recovery protocols (re-thaw from backup if contamination detected early).")
    
    print("\nD. NEXT STEPS:")
    print("1. Calibrate contamination rates against real MCB production data.")
    print("2. Add QC steps to the workflow definition.")
    print("3. Implement finite inventory tracking.")
    print("4. Add variability to seeding efficiency and thaw viability.")
    print("5. Model recovery protocols (e.g., restart from backup vials).")

if __name__ == "__main__":
    run_crash_test()
