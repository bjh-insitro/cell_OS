
import pytest
import pandas as pd
import numpy as np
from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary
from cell_os.posh_lv_moi import (
    design_lv_batch, 
    design_lv_titration_plan, 
    fit_lv_transduction_model,
    LVAutoExplorer,
    ScreenSimulator,
    ScreenConfig,
    LVTitrationResult
)

# --- Helpers ---

def _dummy_library() -> POSHLibrary:
    return POSHLibrary(
        df=pd.DataFrame({'gene': ['G1'], 'guide_id': ['G1_1'], 'sequence': ['ATCG']}),
        num_genes=1,
        guides_per_gene_actual=1,
        vendor_payload="mock"
    )

def _dummy_scenario() -> POSHScenario:
    return POSHScenario(
        name="IntegrationScenario",
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

def _simulate_data(volumes, titer, n_cells, alpha=0.98, noise=0.01):
    rows = []
    for vol in volumes:
        moi = (vol * titer) / n_cells
        bfp = alpha * (1.0 - np.exp(-moi)) + np.random.normal(0, noise)
        bfp = max(0.001, min(0.999, bfp))
        rows.append({'volume_ul': vol, 'fraction_bfp': bfp})
    return pd.DataFrame(rows)

# --- Tests ---

def test_auto_explorer_suggestions():
    """Test that LVAutoExplorer suggests reasonable next volumes."""
    scenario = _dummy_scenario()
    library = _dummy_library()
    world = LabWorldModel.empty()
    batch = design_lv_batch(world, scenario, library)
    
    # Initial data: very low volumes, low signal
    # Titer ~ 1e5, N=1e5. 0.1uL -> MOI 0.1 -> BFP ~9.5%
    initial_vols = [0.01, 0.05] 
    df = _simulate_data(initial_vols, titer=100000, n_cells=100000)
    result = LVTitrationResult(cell_line="U2OS", data=df)
    
    explorer = LVAutoExplorer(scenario, batch)
    suggestions = explorer.suggest_next_volumes(result, n_suggestions=2)
    
    assert len(suggestions) == 2
    # Should suggest higher volumes because signal is low (<5% likely for 0.01/0.05)
    # Actually 0.05 * 1e5 / 1e5 = 0.05 MOI => ~5% BFP. 
    # If noise pushes it below 5%, heuristic kicks in.
    # If it fits a model, it should suggest volumes near target BFP (0.3).
    # Target MOI 0.35 => Vol 0.35 uL.
    # So suggestions should be around 0.3 - 0.5 range.
    
    for vol in suggestions:
        assert vol > 0
        assert vol not in initial_vols

def test_screen_simulator_risk_assessment():
    """Test that ScreenSimulator produces a probability of success."""
    scenario = _dummy_scenario()
    library = _dummy_library()
    world = LabWorldModel.empty()
    batch = design_lv_batch(world, scenario, library)
    
    # Fit a good model first
    volumes = [0.1, 0.3, 0.5, 1.0, 3.0]
    df = _simulate_data(volumes, titer=100000, n_cells=100000)
    result = LVTitrationResult(cell_line="U2OS", data=df)
    
    model = fit_lv_transduction_model(scenario, batch, result, n_cells_override=100000)
    
    # Config with wide tolerance to ensure high success
    config = ScreenConfig(
        num_guides=1000,
        coverage_target=500,
        target_bfp=0.30,
        bfp_tolerance=(0.20, 0.40), # Wide
        cell_counting_error=0.01,   # Low error
        pipetting_error=0.01
    )
    
    sim = ScreenSimulator(model, config)
    pos = sim.get_probability_of_success()
    
    assert 0.0 <= pos <= 1.0
    # With good data and low error, PoS should be high
    assert pos > 0.8
    
    # Test with tight tolerance and high error
    config_tight = ScreenConfig(
        num_guides=1000,
        coverage_target=500,
        target_bfp=0.30,
        bfp_tolerance=(0.29, 0.31), # Impossible
        cell_counting_error=0.20,
        pipetting_error=0.20
    )
    sim_tight = ScreenSimulator(model, config_tight)
    pos_tight = sim_tight.get_probability_of_success()
    
    assert pos_tight < pos # Should be much lower
