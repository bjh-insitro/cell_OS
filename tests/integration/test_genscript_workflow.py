
import pytest
import pandas as pd
import numpy as np
from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary
from cell_os.posh_lv_moi import (
    design_lv_batch, design_lv_titration_plan, fit_lv_transduction_model,
    LVTitrationResult
)

def _dummy_library() -> POSHLibrary:
    return POSHLibrary(
        df=pd.DataFrame({'gene': ['G1'], 'guide_id': ['G1_1'], 'sequence': ['ATCG']}),
        num_genes=1,
        guides_per_gene_actual=1,
        vendor_payload="mock"
    )

def _dummy_scenario() -> POSHScenario:
    return POSHScenario(
        name="GenScriptScenario",
        cell_lines=["U2OS"],
        genes=1,
        guides_per_gene=1,
        coverage_cells_per_gene_per_bank=100,
        banks_per_line=1,
        moi_target=0.3,
        moi_tolerance=0.05,
        viability_min=0.8,
        segmentation_min=0.9,
        stress_signal_min=2.0,
        budget_max=1000.0
    )

def test_genscript_workflow_simulation():
    """
    Simulate the user's specific GenScript workflow:
    - 10 x 50uL aliquots
    - Titration: 0.1, 0.3, 0.5, 1, 3, 5, 10 uL
    - 6-well plate, 100K cells
    - Observation: ~1uL gives 30% BFP
    """
    world = LabWorldModel.empty()
    scenario = _dummy_scenario()
    library = _dummy_library()
    
    # 1. Design Batch (10 x 50uL)
    batch = design_lv_batch(world, scenario, library, aliquot_count=10, aliquot_volume_ul=50.0)
    assert batch.aliquot_count == 10
    
    # 2. Design Titration Plan
    volumes = [0.1, 0.3, 0.5, 1.0, 3.0, 5.0, 10.0]
    plan = design_lv_titration_plan(
        world, scenario, batch, 
        cell_line="U2OS",
        plate_format="6",
        cells_per_well=100000,
        lv_volumes_ul=volumes
    )
    
    # 3. Simulate Data
    # User says 1uL -> 30% BFP.
    # MOI = -ln(1 - 0.3) = -ln(0.7) ≈ 0.3566
    # Titer = (MOI * Cells) / Vol = (0.3566 * 100000) / 1.0 = 35667 TU/uL
    true_titer = 35667.0
    n_cells = 100000
    alpha = 0.98
    
    rows = []
    for vol in plan.lv_volumes_ul:
        # Physics Model
        moi = (vol * true_titer) / n_cells
        bfp_true = alpha * (1.0 - np.exp(-moi))
        
        # Add some noise
        bfp_obs = bfp_true + np.random.normal(0, 0.01)
        bfp_obs = max(0.001, min(0.999, bfp_obs)) 
        
        rows.append({
            'volume_ul': vol,
            'fraction_bfp': bfp_obs
        })
        
    result = LVTitrationResult(
        cell_line="U2OS",
        data=pd.DataFrame(rows)
    )
    
    # 4. Fit Model
    model = fit_lv_transduction_model(scenario, batch, result, n_cells_override=n_cells)
    
    # 5. Predict Volume for MOI 0.3
    # Target MOI 0.3
    # Vol = (0.3 * 100000) / Titer
    # Vol ≈ 30000 / 35667 ≈ 0.84 uL
    vol_target = model.volume_for_moi(0.3)
    
    # Check it's reasonable
    assert 0.7 < vol_target < 1.0
    print(f"Predicted volume for MOI 0.3: {vol_target:.4f} uL")
    
    # Check BFP prediction for that volume
    bfp_pred = model.predict_bfp(vol_target)
    # MOI 0.3 => BFP = 0.98 * (1 - e^-0.3) = 0.98 * (1 - 0.7408) = 0.98 * 0.259 = 0.254
    assert abs(bfp_pred - 0.254) < 0.02
