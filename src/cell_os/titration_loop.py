"""
Titration Loop Module.
The Autonomous Agent orchestrating the titration campaign.
"""
from typing import List, Dict, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

# --- CORRECT IMPORTS ---
from cell_os.posh_lv_moi import (
    fit_lv_transduction_model, 
    LVTitrationResult, 
    LVBatch, 
    POSHScenario, 
    ScreenSimulator, 
    ScreenConfig, 
    LVAutoExplorer,
    LVDesignError,
    TitrationReport # <-- Imported from posh_lv_moi.py to break the cycle
)
# In cell_os/titration_loop.py, near the top

# Import only for type checking to avoid circular dependency at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cell_os.budget_manager import BudgetConfig # <-- Imported for pricing data

# --- Agent Implementation ---

def _mock_lab_step(cell_line: str, volumes: List[float], true_params: Dict) -> pd.DataFrame:
    """Mocks the physical lab step to generate data."""
    rows = []
    titer = true_params['titer']
    alpha = true_params['alpha']
    
    for v in volumes:
        moi = (v * titer) / 100000
        p_bfp = alpha * (1.0 - np.exp(-moi))
        noise = np.random.normal(0, 0.03)
        if cell_line == "HepG2" and v < 1.0: noise += np.random.normal(0, 0.02)
        obs = np.clip(p_bfp + noise, 0.001, 0.999)
        rows.append({"volume_ul": v, "fraction_bfp": obs})
        
    return pd.DataFrame(rows)


from core.state_manager import StateManager

class AutonomousTitrationAgent:
    def __init__(self, config: ScreenConfig, prices: "BudgetConfig", experiment_id: str = None):
        self.prices = prices
        self.config = config
        self.dummy_batch = LVBatch("Batch", 500, 0, None)
        self.dummy_scen = POSHScenario("Auto", ["Demo"], 1, 1, 100, 1, 0.3, 0.05, 0.8, 0.9, 2.0, 1000)
        self.logs = []
        self.max_rounds = config.max_titration_rounds
        self.max_budget = config.max_titration_budget_usd
        
        # Persistence
        self.state_manager = StateManager(experiment_id)
        self.agent_id = "TitrationAgent_v1"
        
    def _log(self, msg: str):
        print(msg)
        self.logs.append(msg)

    def _calculate_round_cost(self, df_round: pd.DataFrame) -> float:
        """Calculates the sunk cost for the wells used in the current round."""
        wells = len(df_round)
        virus_used = df_round['volume_ul'].sum()
        
        # Uses unit costs from BudgetConfig (derived from Parametric Ops)
        cost_reagents_flow = (wells * self.prices.reagent_cost_per_well) + \
                             ((wells * self.prices.mins_per_sample_flow) / 60.0 * self.prices.flow_rate_per_hour)
        
        cost_virus = virus_used * self.prices.virus_price
        
        return cost_reagents_flow + cost_virus
        
    def run_campaign(self, cell_lines: List[Dict]) -> List[TitrationReport]:
        reports = []
        self._log(f"🚀 LAUNCHING AUTONOMOUS TITRATION CAMPAIGN (Exp ID: {self.state_manager.experiment_id})")
        self._log("="*60)
        
        # Load previous state if available
        saved_state = self.state_manager.load_state(self.agent_id)
        completed_lines = set(saved_state.get('completed_lines', [])) if saved_state else set()
        
        if completed_lines:
            self._log(f"🔄 Resuming campaign. Skipping {len(completed_lines)} completed lines: {completed_lines}")

        for line in cell_lines:
            name = line['name']
            if name in completed_lines:
                continue
                
            self._log(f"\n🧪 Starting Campaign for {name}...")
            report = self._run_single_line_loop(name, line['true_params'])
            reports.append(report)
            
            # Checkpoint
            completed_lines.add(name)
            self.state_manager.save_state(self.agent_id, {'completed_lines': list(completed_lines)})
            
        return reports


    def _run_single_line_loop(self, name: str, true_params: Dict) -> TitrationReport:
        
        # Initial State
        df_cumulative = pd.DataFrame()
        rounds_run = 0
        total_cost_incurred = 0.0
        pos = 0.0
        model = None
        
        # --- INITIAL PILOT ROUND (ROUND 1) ---
        initial_vols = [0.1, 0.3, 0.5, 1.0, 3.0, 5.0, 10.0]
        
        df_r1 = _mock_lab_step(name, initial_vols, true_params)
        df_cumulative = df_r1.copy()
        
        rounds_run = 1
        cost_r1 = self._calculate_round_cost(df_r1)
        total_cost_incurred += cost_r1
        
        self._log(f"   Round 1: Testing {len(initial_vols)} standard points.")
        
        # Log data points to DB
        for _, row in df_r1.iterrows():
            self.state_manager.log_result(name, 1, row['volume_ul'], row['fraction_bfp'], cost_r1/len(df_r1))
        
        # --- DYNAMIC LOOP ---
        while pos < 0.90 and rounds_run <= self.max_rounds and total_cost_incurred < self.max_budget:
            
            # 1. Assess Current Status
            result = LVTitrationResult(name, df_cumulative)
            try:
                model = fit_lv_transduction_model(self.dummy_scen, self.dummy_batch, result)
                sim = ScreenSimulator(model, self.config)
                pos = sim.get_probability_of_success()
            except LVDesignError:
                pos = 0.0
                model = None
            
            self._log(f"   Assessment R{rounds_run}: PoS={pos:.1%} | Cost=${total_cost_incurred:.2f}")

            if pos >= 0.90: break # SUCCESS: PoS target met.
            
            # 2. Check Stopping Conditions
            if total_cost_incurred >= self.max_budget:
                 self._log(f"🛑 Budget limit (${self.max_budget:.2f}) exceeded. Stopping.")
                 break
            if rounds_run >= self.max_rounds:
                 self._log(f"🛑 Max rounds ({self.max_rounds}) reached. Stopping.")
                 break
            
            # 3. Request Repair Points & Simulate Lab Step (Round N + 1)
            explorer = LVAutoExplorer(self.dummy_scen, self.dummy_batch)
            suggestions = explorer.suggest_next_volumes(result, n_suggestions=3)
            
            rounds_run += 1
            self._log(f"   🤖 R{rounds_run} Request: {suggestions} µL")
            
            df_new = _mock_lab_step(name, suggestions, true_params)
            df_cumulative = pd.concat([df_cumulative, df_new], ignore_index=True)
            
            # 4. Update Costs & Log
            cost_new = self._calculate_round_cost(df_new)
            total_cost_incurred += cost_new
            
            for _, row in df_new.iterrows():
                self.state_manager.log_result(name, rounds_run, row['volume_ul'], row['fraction_bfp'], cost_new/len(df_new))
        
        # --- FINAL ASSESSMENT ---
        status_final = "GO" if pos >= 0.90 else "NO GO"
        vol = sim.target_vol_ul if model else 0.0
        
        self._log(f"   🏁 Final Status: {status_final} after {rounds_run} rounds.")
        
        return TitrationReport(
            cell_line=name,
            status=status_final,
            rounds_run=rounds_run,
            final_pos=pos,
            final_vol=vol,
            final_cost=total_cost_incurred,
            history_dfs=[df_cumulative], # Pass cumulative data for plotting
            model=model
        )