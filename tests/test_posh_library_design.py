
import pytest
import pandas as pd
from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import design_posh_library, POSHLibrary, LibraryDesignError

def test_design_posh_library_basic():
    # Setup Scenario
    scenario = POSHScenario(
        name="Test Scenario",
        cell_lines=["HeLa"],
        genes=10,
        guides_per_gene=3,
        coverage_cells_per_gene_per_bank=100,
        banks_per_line=1,
        moi_target=0.3,
        moi_tolerance=0.1,
        viability_min=0.8,
        segmentation_min=0.9,
        stress_signal_min=2.0,
        budget_max=10000.0
    )
    
    # Setup World
    world = LabWorldModel.empty()
    
    # Run Design
    library = design_posh_library(world, scenario)
    
    # Assertions
    assert isinstance(library, POSHLibrary)
    assert library.num_genes == 10
    assert library.guides_per_gene_actual == 3
    assert not library.df.empty
    assert "gene" in library.df.columns
    assert "guide_id" in library.df.columns
    assert "sequence" in library.df.columns
    assert "ot_score" in library.df.columns
    
    # Check no duplicates
    assert not library.df.duplicated(subset=["gene", "sequence"]).any()
    
    # Check deterministic output
    library2 = design_posh_library(world, scenario)
    pd.testing.assert_frame_equal(library.df, library2.df)
    assert library.vendor_payload == library2.vendor_payload

def test_design_posh_library_with_gene_list():
    # Setup Scenario with genes_list
    scenario = POSHScenario(
        name="Test Scenario List",
        cell_lines=["HeLa"],
        genes=2,
        guides_per_gene=2,
        coverage_cells_per_gene_per_bank=100,
        banks_per_line=1,
        moi_target=0.3,
        moi_tolerance=0.1,
        viability_min=0.8,
        segmentation_min=0.9,
        stress_signal_min=2.0,
        budget_max=10000.0,
        genes_list=["TP53", "BRCA1"]
    )
    
    world = LabWorldModel.empty()
    
    library = design_posh_library(world, scenario)
    
    assert library.num_genes == 2
    assert set(library.df['gene'].unique()) == {"TP53", "BRCA1"}

def test_vendor_format_twist():
    scenario = POSHScenario(
        name="Test Twist",
        cell_lines=["HeLa"],
        genes=5,
        guides_per_gene=2,
        coverage_cells_per_gene_per_bank=100,
        banks_per_line=1,
        moi_target=0.3,
        moi_tolerance=0.1,
        viability_min=0.8,
        segmentation_min=0.9,
        stress_signal_min=2.0,
        budget_max=10000.0,
        vendor_format="twist"
    )
    
    world = LabWorldModel.empty()
    library = design_posh_library(world, scenario)
    
    assert "name,sequence" in library.vendor_payload
    assert "," in library.vendor_payload

def test_gene_list_mismatch_error():
    scenario = POSHScenario(
        name="Test Mismatch",
        cell_lines=["HeLa"],
        genes=5, # Mismatch with list length
        guides_per_gene=2,
        coverage_cells_per_gene_per_bank=100,
        banks_per_line=1,
        moi_target=0.3,
        moi_tolerance=0.1,
        viability_min=0.8,
        segmentation_min=0.9,
        stress_signal_min=2.0,
        budget_max=10000.0,
        genes_list=["TP53", "BRCA1"]
    )
    world = LabWorldModel.empty()
    
    with pytest.raises(LibraryDesignError, match="genes_list length"):
        design_posh_library(world, scenario)
