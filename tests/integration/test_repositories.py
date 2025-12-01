"""
Test all database repositories.
"""
import pandas as pd
from cell_os.database import (
    CellLineRepository, CellLine, CellLineCharacteristic, ProtocolParameters,
    SimulationParamsRepository, CellLineSimParams, CompoundSensitivity,
    ExperimentalRepository
)


# CellLineRepository Tests

def test_cell_line_repository_create_and_get(tmp_path):
    """Test creating and retrieving a cell line."""
    db_path = str(tmp_path / "test_cell_lines.db")
    repo = CellLineRepository(db_path)
    
    cell_line = CellLine(
        cell_line_id="HEK293T",
        display_name="HEK293T",
        cell_type="adherent",
        growth_media="DMEM",
        coating_required=False
    )
    
    repo.add_cell_line(cell_line)
    retrieved = repo.get_cell_line("HEK293T")
    
    assert retrieved is not None
    assert retrieved.cell_line_id == "HEK293T"
    assert retrieved.growth_media == "DMEM"


def test_cell_line_characteristics(tmp_path):
    """Test adding and retrieving characteristics."""
    db_path = str(tmp_path / "test_cell_lines.db")
    repo = CellLineRepository(db_path)
    
    cell_line = CellLine(
        cell_line_id="CHO-K1",
        display_name="CHO-K1",
        cell_type="adherent",
        growth_media="F12K"
    )
    repo.add_cell_line(cell_line)
    
    char = CellLineCharacteristic(
        cell_line_id="CHO-K1",
        characteristic="dissociation_method",
        value="trypsin"
    )
    repo.add_characteristic(char)
    
    chars = repo.get_characteristics("CHO-K1")
    assert len(chars) == 1
    assert chars[0].value == "trypsin"


def test_protocol_parameters(tmp_path):
    """Test adding and retrieving protocol parameters."""
    db_path = str(tmp_path / "test_cell_lines.db")
    repo = CellLineRepository(db_path)
    
    cell_line = CellLine(
        cell_line_id="iPSC",
        display_name="iPSC",
        cell_type="adherent",
        growth_media="mTeSR"
    )
    repo.add_cell_line(cell_line)
    
    protocol = ProtocolParameters(
        cell_line_id="iPSC",
        protocol_type="passage",
        vessel_type="6well",
        parameters={"split_ratio": 1, "incubation_time": 5}
    )
    repo.add_protocol(protocol)
    
    retrieved = repo.get_protocol("iPSC", "passage", "6well")
    assert retrieved is not None
    assert retrieved.parameters["split_ratio"] == 1


def test_vial_inventory(tmp_path):
    """Test vial inventory management."""
    db_path = str(tmp_path / "test_cell_lines.db")
    repo = CellLineRepository(db_path)
    
    cell_line = CellLine(
        cell_line_id="HeLa",
        display_name="HeLa",
        cell_type="adherent",
        growth_media="DMEM"
    )
    repo.add_cell_line(cell_line)
    
    repo.add_vial("HeLa", "vial_001", passage_number=5, location="LN2_tank_1")
    repo.add_vial("HeLa", "vial_002", passage_number=6, location="LN2_tank_1")
    
    vials = repo.get_available_vials("HeLa")
    assert len(vials) == 2
    
    repo.use_vial("vial_001", purpose="experiment")
    vials = repo.get_available_vials("HeLa")
    assert len(vials) == 1


# SimulationParamsRepository Tests

def test_simulation_params_repository(tmp_path):
    """Test creating and retrieving simulation parameters."""
    db_path = str(tmp_path / "test_sim_params.db")
    repo = SimulationParamsRepository(db_path)
    
    params = CellLineSimParams(
        cell_line_id="HEK293T",
        doubling_time_h=24.0,
        max_confluence=0.9,
        max_passage=30,
        senescence_rate=0.01,
        seeding_efficiency=0.8,
        passage_stress=0.05,
        cell_count_cv=0.1,
        viability_cv=0.05,
        biological_cv=0.15
    )
    
    repo.add_cell_line_params(params)
    retrieved = repo.get_cell_line_params("HEK293T")
    
    assert retrieved is not None
    assert retrieved.doubling_time_h == 24.0
    assert retrieved.max_passage == 30


def test_simulation_params_versioning(tmp_path):
    """Test parameter versioning."""
    db_path = str(tmp_path / "test_sim_params.db")
    repo = SimulationParamsRepository(db_path)
    
    # Add version 1
    params_v1 = CellLineSimParams(
        cell_line_id="CHO",
        doubling_time_h=20.0,
        max_confluence=0.9,
        max_passage=40,
        senescence_rate=0.01,
        seeding_efficiency=0.85,
        passage_stress=0.04,
        cell_count_cv=0.1,
        viability_cv=0.05,
        biological_cv=0.12,
        version=1
    )
    repo.add_cell_line_params(params_v1)
    
    # Add version 2
    params_v2 = CellLineSimParams(
        cell_line_id="CHO",
        doubling_time_h=18.0,  # Updated
        max_confluence=0.9,
        max_passage=40,
        senescence_rate=0.01,
        seeding_efficiency=0.85,
        passage_stress=0.04,
        cell_count_cv=0.1,
        viability_cv=0.05,
        biological_cv=0.12,
        version=2
    )
    repo.add_cell_line_params(params_v2)
    
    # Latest should be version 2
    latest = repo.get_cell_line_params("CHO")
    assert latest.doubling_time_h == 18.0
    assert latest.version == 2
    
    # Can still retrieve version 1
    v1 = repo.get_cell_line_params("CHO", version=1)
    assert v1.doubling_time_h == 20.0


def test_compound_sensitivity(tmp_path):
    """Test compound sensitivity data."""
    db_path = str(tmp_path / "test_sim_params.db")
    repo = SimulationParamsRepository(db_path)
    
    sensitivity = CompoundSensitivity(
        compound_name="Doxorubicin",
        cell_line_id="HeLa",
        ic50_um=0.5,
        hill_slope=-1.0,
        source="experimental"
    )
    
    repo.add_compound_sensitivity(sensitivity)
    retrieved = repo.get_compound_sensitivity("Doxorubicin", "HeLa")
    
    assert retrieved is not None
    assert retrieved.ic50_um == 0.5
    assert retrieved.source == "experimental"


def test_find_sensitive_compounds(tmp_path):
    """Test finding sensitive compounds."""
    db_path = str(tmp_path / "test_sim_params.db")
    repo = SimulationParamsRepository(db_path)
    
    # Add multiple compounds
    for compound, ic50 in [("Drug_A", 0.1), ("Drug_B", 1.0), ("Drug_C", 10.0)]:
        sensitivity = CompoundSensitivity(
            compound_name=compound,
            cell_line_id="HEK293T",
            ic50_um=ic50,
            hill_slope=-1.0
        )
        repo.add_compound_sensitivity(sensitivity)
    
    # Find compounds with IC50 < 2.0
    sensitive = repo.find_sensitive_compounds("HEK293T", max_ic50=2.0)
    assert len(sensitive) == 2
    assert sensitive[0].compound_name == "Drug_A"  # Should be sorted by IC50


def test_default_params(tmp_path):
    """Test default parameter storage."""
    db_path = str(tmp_path / "test_sim_params.db")
    repo = SimulationParamsRepository(db_path)
    
    repo.set_default_param("default_doubling_time", 24.0, "Default doubling time in hours")
    value = repo.get_default_param("default_doubling_time")
    
    assert value == 24.0


# ExperimentalRepository Tests

def test_experimental_repository_measurements(tmp_path):
    """Test adding and retrieving measurements."""
    db_path = str(tmp_path / "test_experimental.db")
    repo = ExperimentalRepository(db_path)
    
    # Create test data
    df = pd.DataFrame({
        'plate_id': ['plate_001'] * 3,
        'well_id': ['A1', 'A2', 'A3'],
        'cell_line': ['HEK293T'] * 3,
        'compound': ['Drug_X'] * 3,
        'dose_uM': [0.1, 1.0, 10.0],
        'time_h': [24.0] * 3,
        'raw_signal': [1000, 800, 400],
        'is_control': [0, 0, 0],
        'date': ['2025-01-01'] * 3
    })
    
    repo.add_measurements(df)
    
    # Retrieve measurements
    retrieved = repo.get_measurements(cell_line="HEK293T")
    assert len(retrieved) == 3
    assert retrieved['dose_uM'].tolist() == [0.1, 1.0, 10.0]


def test_experimental_dose_response(tmp_path):
    """Test dose-response retrieval."""
    db_path = str(tmp_path / "test_experimental.db")
    repo = ExperimentalRepository(db_path)
    
    df = pd.DataFrame({
        'plate_id': ['plate_002'] * 4,
        'well_id': ['B1', 'B2', 'B3', 'B4'],
        'cell_line': ['HeLa'] * 4,
        'compound': ['Cisplatin'] * 4,
        'dose_uM': [0.01, 0.1, 1.0, 10.0],
        'time_h': [48.0] * 4,
        'raw_signal': [1000, 900, 600, 200],
        'is_control': [0, 0, 0, 0],
        'date': ['2025-01-02'] * 4
    })
    
    repo.add_measurements(df)
    
    dose_response = repo.get_dose_response("HeLa", "Cisplatin")
    assert len(dose_response) == 4
    assert dose_response['compound'].unique()[0] == "Cisplatin"


def test_experimental_summary_stats(tmp_path):
    """Test summary statistics."""
    db_path = str(tmp_path / "test_experimental.db")
    repo = ExperimentalRepository(db_path)
    
    df = pd.DataFrame({
        'plate_id': ['plate_003', 'plate_003', 'plate_004'],
        'well_id': ['C1', 'C2', 'C3'],
        'cell_line': ['HEK293T', 'HEK293T', 'CHO'],
        'compound': ['Drug_A', 'Drug_B', 'Drug_A'],
        'dose_uM': [1.0, 1.0, 1.0],
        'time_h': [24.0, 24.0, 24.0],
        'raw_signal': [800, 850, 900],
        'is_control': [0, 0, 0],
        'date': ['2025-01-03'] * 3
    })
    
    repo.add_measurements(df)
    
    stats = repo.get_summary_stats()
    assert stats['total_measurements'] == 3
    assert len(stats['cell_lines']) == 2
    assert len(stats['compounds']) == 2
    assert stats['plates'] == 2
