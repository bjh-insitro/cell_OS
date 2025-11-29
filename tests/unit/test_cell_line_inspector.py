"""
Tests for Cell Line Inspector functionality.
"""

import pytest
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.protocol_resolver import ProtocolResolver


class TestCellLineInspector:
    """Test protocol resolution for the Cell Line Inspector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.vessel_lib = VesselLibrary("data/raw/vessels.yaml")
        self.inv = Inventory("data/raw/pricing.yaml")
        self.ops = ParametricOps(self.vessel_lib, self.inv)
        self.resolver = ProtocolResolver()
        self.ops.resolver = self.resolver
        self.resolver.ops = self.ops
    
    def test_thaw_ipsc_t75_resolution(self):
        """Test that thaw protocol for iPSC in T75 resolves correctly."""
        thaw_op = self.ops.op_thaw("flask_t75", cell_line="iPSC")
        
        assert thaw_op is not None
        assert hasattr(thaw_op, 'sub_steps')
        assert len(thaw_op.sub_steps) > 0
        
        # Check that coating is included for iPSC
        step_names = [s.name for s in thaw_op.sub_steps]
        coating_steps = [s for s in step_names if 'coat' in s.lower() or 'laminin' in s.lower()]
        assert len(coating_steps) > 0, "iPSC thaw should include coating steps"
        
        # Check that media steps exist (aliquot, pre-warm, etc.)
        media_steps = [s for s in step_names if 'media' in s.lower() or 'aliquot' in s.lower() or 'mtesr' in s.lower() or 'dmem' in s.lower()]
        assert len(media_steps) > 0, "iPSC thaw should have media handling steps"
    
    def test_thaw_hek293_t75_resolution(self):
        """Test that thaw protocol for HEK293 in T75 resolves correctly."""
        thaw_op = self.ops.op_thaw("flask_t75", cell_line="HEK293")
        
        assert thaw_op is not None
        assert hasattr(thaw_op, 'sub_steps')
        assert len(thaw_op.sub_steps) > 0
        
        # Check that coating is NOT included for HEK293
        step_names = [s.name for s in thaw_op.sub_steps]
        coating_steps = [s for s in step_names if 'coat' in s.lower() and 'laminin' in s.lower()]
        assert len(coating_steps) == 0, "HEK293 thaw should not include coating steps"
    
    def test_feed_ipsc_t75_resolution(self):
        """Test that feed protocol for iPSC in T75 resolves correctly."""
        feed_op = self.ops.op_feed("flask_t75", cell_line="iPSC")
        
        assert feed_op is not None
        assert hasattr(feed_op, 'sub_steps')
        assert len(feed_op.sub_steps) > 0
        
        # Check that media is mTeSR
        step_names = [s.name for s in feed_op.sub_steps]
        media_steps = [s for s in step_names if 'mtesr' in s.lower()]
        assert len(media_steps) > 0, "iPSC feed should use mTeSR media"
    
    def test_feed_hek293_t75_resolution(self):
        """Test that feed protocol for HEK293 in T75 resolves correctly."""
        feed_op = self.ops.op_feed("flask_t75", cell_line="HEK293")
        
        assert feed_op is not None
        assert hasattr(feed_op, 'sub_steps')
        assert len(feed_op.sub_steps) > 0
        
        # Check that media is DMEM
        step_names = [s.name for s in feed_op.sub_steps]
        media_steps = [s for s in step_names if 'dmem' in s.lower()]
        assert len(media_steps) > 0, "HEK293 feed should use DMEM media"
    
    def test_passage_ipsc_t75_resolution(self):
        """Test that passage protocol for iPSC in T75 resolves correctly."""
        ops_list = self.resolver.resolve_passage_protocol("iPSC", "T75")
        
        assert ops_list is not None
        assert len(ops_list) > 0
        
        # Check that protocol includes expected steps
        step_names = [op.name for op in ops_list]
        
        # Should have aspirate, dispense, incubate steps
        assert any('aspirate' in s.lower() for s in step_names)
        assert any('dispense' in s.lower() for s in step_names)
    
    def test_passage_hek293_t75_resolution(self):
        """Test that passage protocol for HEK293 in T75 resolves correctly."""
        ops_list = self.resolver.resolve_passage_protocol("HEK293", "T75")
        
        assert ops_list is not None
        assert len(ops_list) > 0
        
        # Check that protocol includes expected steps
        step_names = [op.name for op in ops_list]
        
        # Should have aspirate, dispense, incubate steps
        assert any('aspirate' in s.lower() for s in step_names)
        assert any('dispense' in s.lower() for s in step_names)
    
    def test_thaw_config_volumes(self):
        """Test that thaw config returns correct volumes from YAML."""
        config = self.resolver.get_thaw_config("iPSC", "flask_t75")
        
        assert config is not None
        assert "volumes_mL" in config
        
        volumes = config["volumes_mL"]
        assert volumes["media_aliquot"] == 40.0
        assert volumes["pre_warm"] == 15.0
        assert volumes["wash_aliquot"] == 5.0
    
    def test_feed_config_volumes(self):
        """Test that feed config returns correct volumes from YAML."""
        config = self.resolver.get_feed_config("iPSC", "flask_t75")
        
        assert config is not None
        assert "volume_ml" in config
        assert config["volume_ml"] == 15.0
        assert config["media"] == "mtesr_plus_kit"
    
    def test_unknown_cell_line_handling(self):
        """Test that unknown cell line raises appropriate error."""
        with pytest.raises(ValueError, match="Unknown cell line"):
            self.resolver.get_thaw_config("UnknownCellLine", "flask_t75")
    
    def test_protocol_cost_calculation(self):
        """Test that protocols have cost information."""
        thaw_op = self.ops.op_thaw("flask_t75", cell_line="iPSC")
        
        assert hasattr(thaw_op, 'material_cost_usd')
        assert thaw_op.material_cost_usd > 0, "Thaw protocol should have material cost"
        
        # Check sub-steps also have costs
        if hasattr(thaw_op, 'sub_steps'):
            total_substep_cost = sum(
                s.material_cost_usd for s in thaw_op.sub_steps 
                if hasattr(s, 'material_cost_usd')
            )
            assert total_substep_cost > 0, "Sub-steps should have costs"
    
    def test_all_cell_lines_have_thaw_feed_configs(self):
        """Test that all cell lines in the database have thaw and feed configurations."""
        from cell_os.cell_line_database import list_cell_lines
        
        cell_lines = list_cell_lines()
        assert len(cell_lines) > 0, "Should have cell lines in database"
        
        for cell_line in cell_lines:
            # Test thaw config
            try:
                thaw_config = self.resolver.get_thaw_config(cell_line, "flask_t75")
                assert thaw_config is not None, f"{cell_line} should have thaw config"
                assert "volumes_mL" in thaw_config, f"{cell_line} thaw config should have volumes"
                assert "media" in thaw_config, f"{cell_line} thaw config should have media"
            except ValueError:
                pytest.fail(f"{cell_line} raised ValueError for thaw config")
            
            # Test feed config
            try:
                feed_config = self.resolver.get_feed_config(cell_line, "flask_t75")
                assert feed_config is not None, f"{cell_line} should have feed config"
                assert "volume_ml" in feed_config, f"{cell_line} feed config should have volume"
                assert "media" in feed_config, f"{cell_line} feed config should have media"
            except ValueError:
                pytest.fail(f"{cell_line} raised ValueError for feed config")
    
    def test_vessel_scaling_thaw_t25(self):
        """Test that thaw volumes scale correctly from T75 to T25."""
        # T25 working volume is 5.0 mL, T75 is 15.0 mL
        # Scale factor should be 5.0 / 15.0 = 0.333...
        
        config_t75 = self.resolver.get_thaw_config("iPSC", "flask_t75")
        config_t25 = self.resolver.get_thaw_config("iPSC", "flask_t25")
        
        # Check that T25 volumes are scaled down
        assert config_t25["volumes_mL"]["pre_warm"] < config_t75["volumes_mL"]["pre_warm"]
        assert config_t25["volumes_mL"]["pre_warm"] == 5.0  # T25 working volume
        
        # Media aliquot should be scaled
        expected_media = round(40.0 * (5.0 / 15.0), 1)
        assert config_t25["volumes_mL"]["media_aliquot"] == expected_media
    
    def test_vessel_scaling_thaw_t175(self):
        """Test that thaw volumes scale correctly from T75 to T175."""
        # T175 working volume is 30.0 mL, T75 is 15.0 mL
        # Scale factor should be 30.0 / 15.0 = 2.0
        
        config_t75 = self.resolver.get_thaw_config("HEK293", "flask_t75")
        config_t175 = self.resolver.get_thaw_config("HEK293", "flask_t175")
        
        # Check that T175 volumes are scaled up
        assert config_t175["volumes_mL"]["pre_warm"] > config_t75["volumes_mL"]["pre_warm"]
        assert config_t175["volumes_mL"]["pre_warm"] == 30.0  # T175 working volume
        
        # Media aliquot should be scaled 2x
        assert config_t175["volumes_mL"]["media_aliquot"] == 80.0  # 40.0 * 2
    
    def test_vessel_scaling_feed_t25(self):
        """Test that feed volumes scale correctly from T75 to T25."""
        config_t75 = self.resolver.get_feed_config("iPSC", "flask_t75")
        config_t25 = self.resolver.get_feed_config("iPSC", "flask_t25")
        
        # T25 should have 1/3 the volume of T75
        assert config_t25["volume_ml"] < config_t75["volume_ml"]
        assert config_t25["volume_ml"] == 5.0  # T25 working volume
        
        # Schedule should be the same
        assert config_t25["schedule"] == config_t75["schedule"]
    
    def test_vessel_scaling_feed_t175(self):
        """Test that feed volumes scale correctly from T75 to T175."""
        config_t75 = self.resolver.get_feed_config("HEK293", "flask_t75")
        config_t175 = self.resolver.get_feed_config("HEK293", "flask_t175")
        
        # T175 should have 2x the volume of T75
        assert config_t175["volume_ml"] > config_t75["volume_ml"]
        assert config_t175["volume_ml"] == 30.0  # T175 working volume
