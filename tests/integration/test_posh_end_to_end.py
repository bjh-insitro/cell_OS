import pytest

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_screen_design import run_posh_screen_design, ScreenDesignResult
from cell_os.posh_library_design import POSHLibrary
from cell_os.posh_lv_moi import LVDesignBundle, LVBatch, LVTitrationPlan

def test_end_to_end_3lines_stress_screen_library_and_lv():
    scenario = POSHScenario.from_yaml("data/scenarios/3lines_stress_screen.yaml")
    world = LabWorldModel.empty()

    result = run_posh_screen_design(world, scenario)

    # Basic shape
    assert isinstance(result, ScreenDesignResult)
    assert result.scenario.name == "3lines_stress_screen"
    assert isinstance(result.library, POSHLibrary)
    assert isinstance(result.lv_design, LVDesignBundle)

    # Library invariants
    lib = result.library
    assert lib.num_genes == scenario.genes
    assert lib.guides_per_gene_actual == scenario.guides_per_gene
    assert not lib.df.empty
    
    # LV invariants
    lv = result.lv_design
    assert isinstance(lv.batch, LVBatch)
    assert lv.batch.library is lib
    assert len(lv.titration_plans) == len(scenario.cell_lines)
    
    for cell_line in scenario.cell_lines:
        assert cell_line in lv.titration_plans
        plan = lv.titration_plans[cell_line]
        assert isinstance(plan, LVTitrationPlan)
        assert plan.cell_line == cell_line
        assert len(plan.lv_volumes_ul) > 0
