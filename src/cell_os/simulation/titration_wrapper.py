"""
LV Titration Simulation Wrapper.

Provides a clean API for simulating Lentivirus titration experiments for the dashboard.
Wraps the underlying posh_lv_moi logic to generate synthetic data and fit models.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from cell_os.posh.lv_moi import (
    LVTransductionModel, 
    LVTitrationPlan, 
    LVTitrationResult,
    _poisson_curve,
    fit_lv_transduction_model,
    LVDesignError
)
from cell_os.workflows import Workflow, WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.utils import MockInventory

@dataclass
class TitrationResultBundle:
    """Result of a single titration simulation run."""
    cell_line: str
    true_titer_tu_ml: float
    fitted_titer_tu_ml: float
    r_squared: float
    data: pd.DataFrame
    model: Optional[LVTransductionModel]
    recommended_vol_ul: float
    target_moi: float
    success: bool
    error_message: str = ""
    workflow: Optional[Workflow] = None

def simulate_titration(
    cell_line: str,
    true_titer_tu_ml: float = 1.0e8,
    target_transduction_efficiency: float = 0.30,
    cells_per_well: int = 100000,
    vol_range_ul: List[float] = None,
    replicates: int = 2,
    random_seed: int = 42
) -> TitrationResultBundle:
    """
    Simulate an LV titration experiment.
    
    Args:
        cell_line: Name of the cell line
        true_titer_tu_ml: The "ground truth" titer (TU/mL) to simulate
        target_transduction_efficiency: Target %BFP (e.g., 0.30 for 30%)
        cells_per_well: Number of cells plated per well
        vol_range_ul: List of viral volumes to test (in uL)
        replicates: Number of replicates per volume condition
        random_seed: Seed for reproducibility
        
    Returns:
        TitrationResultBundle with synthetic data and fitted model
    """
    rng = np.random.default_rng(random_seed)
    
    # 1. Define the Plan
    if vol_range_ul is None:
        # Auto-scale volumes based on expected titer to ensure we get data in the linear range
        # Target MOI ~ 0.3. MOI = (Vol * Titer) / Cells
        # Vol = (MOI * Cells) / Titer
        # Titer is in TU/mL, so TU/uL = Titer / 1000
        
        titer_tu_ul = true_titer_tu_ml / 1000.0
        if titer_tu_ul > 0:
            optimal_vol = (0.3 * cells_per_well) / titer_tu_ul
            # Create a range around the optimal volume (0.1x to 10x)
            # Ensure min volume is reasonable (e.g. 0.05 uL)
            min_vol = max(0.05, optimal_vol * 0.1)
            max_vol = optimal_vol * 10.0
            vol_range_ul = list(np.geomspace(min_vol, max_vol, 8))
            # Round to reasonable pipetting precision
            vol_range_ul = [round(v, 2) for v in vol_range_ul]
        else:
            # Fallback if titer is 0 or unknown
            vol_range_ul = [0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
        
    # 2. Generate Synthetic Data
    # True physics parameters
    true_titer_tu_ul = true_titer_tu_ml / 1000.0
    max_infectivity = 0.98 # Assumes high quality virus/cells
    
    data_rows = []
    
    for vol in vol_range_ul:
        # Calculate theoretical BFP
        # Poisson: P(k>0) = 1 - e^(-MOI)
        # MOI = (Vol * Titer) / Cells
        moi = (vol * true_titer_tu_ul) / cells_per_well
        theoretical_bfp = max_infectivity * (1.0 - np.exp(-moi))
        
        for r in range(replicates):
            # Add noise
            # Pipetting error (CV ~5%) + Cell counting error (CV ~10%) -> Combined noise
            # We'll approximate with normal noise on the observed BFP
            noise = rng.normal(0, 0.02) # 2% absolute noise
            observed_bfp = np.clip(theoretical_bfp + noise, 0.001, 0.999)
            
            data_rows.append({
                "cell_line": cell_line,
                "volume_ul": vol,
                "replicate": r + 1,
                "fraction_bfp": observed_bfp,
                "moi_theoretical": moi
            })
            
    df_data = pd.DataFrame(data_rows)
    
    # 3. Fit Model
    titration_result = LVTitrationResult(cell_line=cell_line, data=df_data)
    
    # Mock scenario/batch objects needed for the fit function signature
    # In a real app these would come from the database, but here we just need placeholders
    class MockObj: pass
    scenario = MockObj()
    scenario.name = "Simulated"
    batch = MockObj()
    
    try:
        model = fit_lv_transduction_model(
            scenario, 
            batch, 
            titration_result, 
            n_cells_override=cells_per_well
        )
        
        # 4. Calculate Recommendations
        # Volume for target MOI/Efficiency
        # BFP = A * (1 - e^(-MOI))
        # BFP/A = 1 - e^(-MOI)
        # e^(-MOI) = 1 - BFP/A
        # -MOI = ln(1 - BFP/A)
        # MOI = -ln(1 - BFP/A)
        # (Vol * Titer)/Cells = -ln(1 - BFP/A)
        # Vol = (-ln(1 - BFP/A) * Cells) / Titer
        
        if target_transduction_efficiency >= model.max_infectivity:
             # Target too high, cap it slightly below max to avoid log(neg)
             target_eff = model.max_infectivity * 0.95
        else:
             target_eff = target_transduction_efficiency
             
        target_moi = -np.log(1.0 - (target_eff / model.max_infectivity))
        recommended_vol_ul = (target_moi * cells_per_well) / model.titer_tu_ul
        
        # 5. Build Workflow for Resource Tracking
        inv = MockInventory()
        vessels = VesselLibrary()
        ops = ParametricOps(vessels, inv)
        builder = WorkflowBuilder(ops)
        
        num_conditions = len(vol_range_ul)
        workflow = builder.build_titration_workflow(
            cell_line=cell_line,
            num_conditions=num_conditions,
            replicates=replicates
        )
        
        return TitrationResultBundle(
            cell_line=cell_line,
            true_titer_tu_ml=true_titer_tu_ml,
            fitted_titer_tu_ml=model.titer_tu_ul * 1000.0,
            r_squared=model.r_squared,
            data=df_data,
            model=model,
            recommended_vol_ul=recommended_vol_ul,
            target_moi=target_moi,
            success=True,
            workflow=workflow
        )
        
    except Exception as e:
        return TitrationResultBundle(
            cell_line=cell_line,
            true_titer_tu_ml=true_titer_tu_ml,
            fitted_titer_tu_ml=0.0,
            r_squared=0.0,
            data=df_data,
            model=None,
            recommended_vol_ul=0.0,
            target_moi=0.0,
            success=False,
            error_message=str(e)
        )
