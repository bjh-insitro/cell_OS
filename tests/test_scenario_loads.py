from cell_os.posh_scenario import POSHScenario


def test_scenario_loads():
    scenario = POSHScenario.from_yaml("data/scenarios/3lines_stress_screen.yaml")
    assert scenario.name == "3lines_stress_screen"
    assert set(scenario.cell_lines) == {"U2OS", "A549", "HepG2"}
    assert scenario.genes == 300
    assert scenario.guides_per_gene == 4
    assert scenario.coverage_cells_per_gene_per_bank == 1000
    assert scenario.banks_per_line == 4
    assert scenario.moi_target == 0.3
