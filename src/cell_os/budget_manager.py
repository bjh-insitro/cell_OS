from dataclasses import dataclass, field
from typing import List, Dict, Any
import pandas as pd
import yaml
import os
from pathlib import Path

# Import the Engine Stack
from cell_os.titration_loop import TitrationReport
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.recipe_optimizer import RecipeOptimizer
from cell_os.posh_lv_moi import ScreenConfig # Used for type hinting

# --- ADAPTERS ---

class YamlVesselLibrary:
    def __init__(self, path="data/raw/vessels.yaml"):
        full_path = Path(os.getcwd()) / path
        self.vessels: Dict[str, Any] = {}
        if full_path.exists():
            with open(full_path, 'r') as f: 
                data = yaml.safe_load(f)
                self.data = data.get('vessels', {}) or {}
        else:
            self.data = {}
            
    def get(self, vessel_id: str):
        info = self.data.get(vessel_id, {})
        class VesselSpec:
            def __init__(self, d):
                self.name = d.get('name', vessel_id)
                self.working_volume_ml = d.get('working_volume_ml', 0.0)
                self.coating_volume_ml = d.get('coating_volume_ml', 0.0)
        return VesselSpec(info)

class YamlPricingInventory:
    def __init__(self, path="data/raw/pricing.yaml"):
        full_path = Path(os.getcwd()) / path
        self.data = {}
        
        if full_path.exists():
            with open(full_path, 'r') as f: 
                raw_data = yaml.safe_load(f)
            
            # CRITICAL FIX: Handle nested 'items' structure
            if raw_data and 'items' in raw_data and isinstance(raw_data['items'], dict):
                self.data = raw_data['items']
            else:
                self.data = raw_data
        
        self._calculate_composite_costs()
        
    def _calculate_composite_costs(self):
        """Calculates prices for common composite items (like prepared media)."""
        p_dmem = self.get_price('dmem_high_glucose') or 0.05
        p_fbs = self.get_price('fbs_serum') or 0.40
        
        # Formula for DMEM Complete (10% FBS):
        cost_per_mL = (0.9 * p_dmem) + (0.1 * p_fbs) + 0.01 # + 0.01 for supplements
        
        self.data['media_dmem_complete'] = {
            'name': 'DMEM Complete (Calculated)',
            'category': 'reagent_composite',
            'unit_price_usd': cost_per_mL,
            'logical_unit': 'mL'
        }
        
    def get_price(self, item_id):
        return self.data.get(item_id, {}).get('unit_price_usd', 0.0)

# --- COST SUMMARY STRUCTURES ---
@dataclass
class LineItem:
    name: str
    category: str
    qty: float
    unit: str
    total_cost: float

@dataclass
class CostSummary:
    cell_line: str
    total_sunk_cost: float
    screen_cost_est: float
    total_virus_ul_consumed: float
    total_virus_ul_needed: float
    line_items: List[LineItem] = field(default_factory=list)

@dataclass
class BudgetConfig:
    currency: str = "$"
    optimizer: RecipeOptimizer = None
    inventory: YamlPricingInventory = None
    virus_price: float = 2.00
    max_titration_budget_usd: float = 5000.0
    
    # Unit costs are needed by titration_loop
    reagent_cost_per_well: float = 0.0
    reagent_cost_per_flask: float = 0.0
    flow_rate_per_hour: float = 80.00
    mins_per_sample_flow: float = 2.0
    
    @classmethod
    def from_optimizer(cls):
        vessels = YamlVesselLibrary()
        inv = YamlPricingInventory()
        virus_price = inv.get_price("lentivirus_stock") or 2.00
        
        ops_engine = ParametricOps(vessels, inv)
        optimizer = RecipeOptimizer(ops_engine)
        
        # Calculate unit costs based on a standard U2OS recipe for the loop
        baseline_titration_ops = optimizer.get_titration_recipe('U2OS')
        baseline_screen_ops = optimizer.get_screen_recipe('U2OS')
        
        cost_per_well = sum(op.material_cost_usd + op.instrument_cost_usd for op in baseline_titration_ops)
        cost_per_flask = sum(op.material_cost_usd + op.instrument_cost_usd for op in baseline_screen_ops)


        return cls(
            optimizer=optimizer, 
            inventory=inv, 
            virus_price=virus_price,
            reagent_cost_per_well=cost_per_well,
            reagent_cost_per_flask=cost_per_flask
        )

# --- CORE LOGIC (Exported Function) ---
def calculate_campaign_cost(reports: List[TitrationReport], prices: BudgetConfig) -> List[CostSummary]:
    """
    Calculates the detailed cost summary for all cell line campaigns.
    
    This function orchestrates the final cost summation and reports generation.
    """
    summaries = []
    
    for r in reports:
        # 1. Get Optimized Recipe & Stats
        titration_ops = prices.optimizer.get_titration_recipe(r.cell_line)
        screen_ops = prices.optimizer.get_screen_recipe(r.cell_line)
        all_data = pd.concat(r.history_dfs)
        total_wells = len(all_data)
        
        # 2. Build Itemized Sunk Cost List
        items = []
        
        # Sum costs based on the optimized workflow steps (simplified reconstruction for the report)
        for op in titration_ops:
            material_cost_unit = op.material_cost_usd 
            instrument_cost_unit = op.instrument_cost_usd
            
            # Simple Amortization
            items.append(LineItem(
                name=f"Op: {op.name} (Materials)", 
                category=f"Reagent/Consumable",
                qty=total_wells,
                unit="wells",
                total_cost=material_cost_unit * total_wells
            ))
            items.append(LineItem(
                name=f"Op: {op.name} (Overhead)", 
                category=f"Overhead/Inst",
                qty=total_wells * 2.0 / 60.0,
                unit="hours",
                total_cost=instrument_cost_unit * total_wells
            ))
        
        # 3. Virus (Variable)
        virus_consumed = all_data['volume_ul'].sum()
        virus_cost_sunk = virus_consumed * prices.virus_price
        items.append(LineItem("Lentivirus Stock (Consumed)", "Virus", virus_consumed, "µL", virus_cost_sunk))

        # 4. Final Summation
        total_sunk_cost = sum(i.total_cost for i in items)
        
        # 5. Project Final Screen Cost
        projected_material_cost = sum(op.material_cost_usd + op.instrument_cost_usd for op in screen_ops)
        
        is_diluted = (r.status != "GO" and r.final_vol > 0)
        virus_needed = r.final_vol / 10.0 if is_diluted else r.final_vol
        
        screen_cost_est = projected_material_cost + (virus_needed * prices.virus_price)

        summaries.append(CostSummary(
            cell_line=r.cell_line,
            total_sunk_cost=total_sunk_cost,
            screen_cost_est=screen_cost_est,
            total_virus_ul_consumed=virus_consumed,
            total_virus_ul_needed=virus_needed,
            line_items=items
        ))

    return summaries

def _get_note(r): 
    return "Ready" if r.status == "GO" else ("Rescued" if r.final_vol > 0 else "Reject")