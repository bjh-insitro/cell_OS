"""
Unit tests for database classes.

Tests SimulationParamsDatabase, CellLineDatabase, and CampaignDatabase.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from cell_os.simulation_params_db import (
    SimulationParamsDatabase,
    CellLineSimParams,
    CompoundSensitivity
)
from cell_os.cell_line_db import (
    CellLineDatabase,
    CellLine,
    CellLineCharacteristic,
    ProtocolParameters
)
from cell_os.campaign_db import (
    CampaignDatabase,
    Campaign,
    CampaignIteration
)


class TestSimulationParamsDatabase:
    """Tests for SimulationParamsDatabase."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_sim_params.db"
        db = SimulationParamsDatabase(str(db_path))
        yield db
        shutil.rmtree(temp_dir)
    
    def test_add_cell_line_params(self, temp_db):
        """Test adding cell line parameters."""
        params = CellLineSimParams(
            cell_line_id="HEK293T",
            doubling_time_h=24.0,
            max_confluence=0.9,
            max_passage=30,
            senescence_rate=0.01,
            seeding_efficiency=0.85,
            passage_stress=0.02,
            cell_count_cv=0.10,
            viability_cv=0.02,
            biological_cv=0.05
        )
        
        param_id = temp_db.add_cell_line_params(params)
        assert param_id > 0
        
        # Retrieve and verify
        retrieved = temp_db.get_cell_line_params("HEK293T")
        assert retrieved is not None
        assert retrieved.doubling_time_h == 24.0
        assert retrieved.max_confluence == 0.9
    
    def test_add_compound_sensitivity(self, temp_db):
        """Test adding compound sensitivity."""
        sensitivity = CompoundSensitivity(
            compound_name="staurosporine",
            cell_line_id="HEK293T",
            ic50_um=0.05,
            hill_slope=1.2,
            source="literature"
        )
        
        sensitivity_id = temp_db.add_compound_sensitivity(sensitivity)
        assert sensitivity_id > 0
        
        # Retrieve and verify
        retrieved = temp_db.get_compound_sensitivity("staurosporine", "HEK293T")
        assert retrieved is not None
        assert retrieved.ic50_um == 0.05
        assert retrieved.hill_slope == 1.2
    
    def test_find_sensitive_compounds(self, temp_db):
        """Test finding sensitive compounds."""
        # Add multiple compounds
        for compound, ic50 in [("compound_a", 0.1), ("compound_b", 0.5), ("compound_c", 2.0)]:
            temp_db.add_compound_sensitivity(CompoundSensitivity(
                compound_name=compound,
                cell_line_id="U2OS",
                ic50_um=ic50,
                hill_slope=1.0
            ))
        
        # Find compounds with IC50 < 1.0
        sensitive = temp_db.find_sensitive_compounds("U2OS", max_ic50=1.0)
        assert len(sensitive) == 2
        assert all(s.ic50_um < 1.0 for s in sensitive)
    
    def test_default_params(self, temp_db):
        """Test default parameters."""
        temp_db.set_default_param("doubling_time_h", 24.0, "Default doubling time")
        
        value = temp_db.get_default_param("doubling_time_h")
        assert value == 24.0


class TestCellLineDatabase:
    """Tests for CellLineDatabase."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_cell_lines.db"
        db = CellLineDatabase(str(db_path))
        yield db
        shutil.rmtree(temp_dir)
    
    def test_add_cell_line(self, temp_db):
        """Test adding a cell line."""
        cell_line = CellLine(
            cell_line_id="HEK293T",
            display_name="HEK293T (with SV40 T antigen)",
            cell_type="immortalized",
            growth_media="dmem_high_glucose",
            coating_required=False,
            cost_tier="budget"
        )
        
        cell_line_id = temp_db.add_cell_line(cell_line)
        assert cell_line_id == "HEK293T"
        
        # Retrieve and verify
        retrieved = temp_db.get_cell_line("HEK293T")
        assert retrieved is not None
        assert retrieved.display_name == "HEK293T (with SV40 T antigen)"
        assert retrieved.cell_type == "immortalized"
    
    def test_find_cell_lines(self, temp_db):
        """Test finding cell lines by filter."""
        # Add multiple cell lines
        for cell_line_id, cell_type, coating in [
            ("iPSC", "iPSC", True),
            ("HEK293", "immortalized", False),
            ("hESC", "hESC", True)
        ]:
            temp_db.add_cell_line(CellLine(
                cell_line_id=cell_line_id,
                display_name=cell_line_id,
                cell_type=cell_type,
                growth_media="dmem",
                coating_required=coating
            ))
        
        # Find cell lines requiring coating
        coating_lines = temp_db.find_cell_lines(coating_required=True)
        assert len(coating_lines) == 2
        assert all(cl.coating_required for cl in coating_lines)
    
    def test_add_protocol(self, temp_db):
        """Test adding protocol parameters."""
        # First add cell line
        temp_db.add_cell_line(CellLine(
            cell_line_id="iPSC",
            display_name="iPSC",
            cell_type="iPSC",
            growth_media="mtesr"
        ))
        
        # Add protocol
        protocol = ProtocolParameters(
            cell_line_id="iPSC",
            protocol_type="passage",
            vessel_type="T75",
            parameters={"wash_1": 10.0, "detach": 5.0}
        )
        
        temp_db.add_protocol(protocol)
        
        # Retrieve and verify
        retrieved = temp_db.get_protocol("iPSC", "passage", "T75")
        assert retrieved is not None
        assert retrieved["wash_1"] == 10.0
        assert retrieved["detach"] == 5.0
    
    def test_inventory_management(self, temp_db):
        """Test vial inventory management."""
        # Add cell line
        temp_db.add_cell_line(CellLine(
            cell_line_id="U2OS",
            display_name="U2OS",
            cell_type="immortalized",
            growth_media="dmem"
        ))
        
        # Add vial
        vial_id = temp_db.add_vial(
            cell_line_id="U2OS",
            vial_id="U2OS_P5_001",
            passage_number=5,
            location="Freezer A, Box 1"
        )
        assert vial_id > 0
        
        # Get available vials
        vials = temp_db.get_available_vials("U2OS")
        assert len(vials) == 1
        assert vials[0]["vial_id"] == "U2OS_P5_001"
        assert vials[0]["passage_number"] == 5


class TestCampaignDatabase:
    """Tests for CampaignDatabase."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_campaigns.db"
        db = CampaignDatabase(str(db_path))
        yield db
        shutil.rmtree(temp_dir)
    
    def test_create_campaign(self, temp_db):
        """Test creating a campaign."""
        campaign = Campaign(
            campaign_id="test_campaign_001",
            campaign_type="autonomous",
            goal="optimization",
            status="running"
        )
        
        campaign_id = temp_db.create_campaign(campaign)
        assert campaign_id == "test_campaign_001"
        
        # Retrieve and verify
        retrieved = temp_db.get_campaign("test_campaign_001")
        assert retrieved is not None
        assert retrieved.campaign_type == "autonomous"
        assert retrieved.goal == "optimization"
    
    def test_add_iteration(self, temp_db):
        """Test adding campaign iterations."""
        # Create campaign first
        temp_db.create_campaign(Campaign(
            campaign_id="test_campaign",
            campaign_type="autonomous"
        ))
        
        # Add iteration
        iteration = CampaignIteration(
            campaign_id="test_campaign",
            iteration_number=1,
            results=[{"measurement": 0.5}],
            metrics={"experiments": 4}
        )
        
        iteration_id = temp_db.add_iteration(iteration)
        assert iteration_id > 0
        
        # Retrieve iterations
        iterations = temp_db.get_iterations("test_campaign")
        assert len(iterations) == 1
        assert iterations[0].iteration_number == 1
    
    def test_find_campaigns(self, temp_db):
        """Test finding campaigns by filter."""
        # Add multiple campaigns
        for i, campaign_type in enumerate(["autonomous", "manual", "autonomous"]):
            temp_db.create_campaign(Campaign(
                campaign_id=f"campaign_{i}",
                campaign_type=campaign_type
            ))
        
        # Find autonomous campaigns
        autonomous = temp_db.find_campaigns(campaign_type="autonomous")
        assert len(autonomous) == 2
        assert all(c.campaign_type == "autonomous" for c in autonomous)
    
    def test_campaign_stats(self, temp_db):
        """Test getting campaign statistics."""
        # Create campaign
        temp_db.create_campaign(Campaign(
            campaign_id="stats_test",
            campaign_type="autonomous"
        ))
        
        # Add iterations
        for i in range(3):
            temp_db.add_iteration(CampaignIteration(
                campaign_id="stats_test",
                iteration_number=i+1
            ))
        
        # Get stats
        stats = temp_db.get_campaign_stats("stats_test")
        assert stats["iterations"] == 3
        assert stats["campaign_id"] == "stats_test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
