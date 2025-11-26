import pytest

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_screen_design import run_posh_screen_design, ScreenDesignResult
from cell_os.posh_library_design import POSHLibrary

def test_end_to_end_3lines_stress_screen_library_only():
    scenario = POSHScenario.from_yaml("data/scenarios/3lines_stress_screen.yaml")
    world = LabWorldModel.empty()

    result = run_posh_screen_design(world, scenario)

    # Basic shape
    assert isinstance(result, ScreenDesignResult)
    assert result.scenario.name == "3lines_stress_screen"
    assert isinstance(result.library, POSHLibrary)

    # Library invariants
    lib = result.library
    assert lib.num_genes == scenario.genes
    assert lib.guides_per_gene_actual == scenario.guides_per_gene
    assert not lib.df.empty
