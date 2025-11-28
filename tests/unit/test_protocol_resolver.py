"""
Tests for Protocol Resolver.

Tests the resolution of abstract protocol templates to concrete unit operations
with cell-line-specific parameters.
"""

import pytest
from cell_os.protocol_resolver import ProtocolResolver
from cell_os.unit_ops.base import UnitOp
from cell_os.lab_world_model import LabWorldModel


class TestProtocolResolver:
    """Test protocol resolver functionality."""
    
    def test_resolve_ipsc_t75_protocol(self):
        """Test iPSC T75 protocol resolution."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("iPSC")
        
        # Should return a list of UnitOps
        assert isinstance(ops, list)
        assert len(ops) > 0
        assert all(isinstance(op, UnitOp) for op in ops)
        
        # Should include accutase (detach reagent for iPSC)
        op_names = [op.name.lower() for op in ops]
        assert any("accutase" in name for name in op_names), \
            "iPSC protocol should include accutase"
        
        # Should include mtesr (growth media for iPSC)
        assert any("mtesr" in name for name in op_names), \
            "iPSC protocol should include mTeSR media"
    
    def test_resolve_ipsc_t75_volume_keys(self):
        """Test that iPSC T75 protocol resolves all required volume keys."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("iPSC")
        
        op_names = [op.name.lower() for op in ops]
        
        # Check for multi-collect workflow steps
        # wash_1: Should have wash step
        assert any("wash" in name or "dpbs" in name for name in op_names), \
            "Protocol should include wash step"
        
        # collect_1 and collect_2: Should have multiple aspirate steps
        aspirate_ops = [op for op in ops if "aspirate" in op.name.lower()]
        assert len(aspirate_ops) >= 3, \
            "Protocol should have multiple aspirate steps (collect_1, collect_2, supernatant)"
        
        # resuspend: Should have resuspend step with media
        assert any("resuspend" in name or ("dispense" in name and "mtesr" in name) 
                   for name in op_names), \
            "Protocol should include resuspend step"
        
        # count_sample: Should have count step
        assert any("count" in name for name in op_names), \
            "Protocol should include cell count step"
    
    def test_resolve_ipsc_t75_cost_calculation(self):
        """Test that iPSC T75 protocol has valid cost calculations."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("iPSC")
        
        # Calculate total cost
        total_material_cost = sum(op.material_cost_usd for op in ops)
        total_instrument_cost = sum(op.instrument_cost_usd for op in ops)
        total_cost = total_material_cost + total_instrument_cost
        
        # Should have non-zero costs
        assert total_material_cost > 0, \
            "Total material cost should be greater than 0"
        assert total_cost > 0, \
            "Total protocol cost should be greater than 0"
    
    def test_resolve_hek293_t75_protocol(self):
        """Test HEK293 T75 protocol resolution."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("HEK293")
        
        # Should return a list of UnitOps
        assert isinstance(ops, list)
        assert len(ops) > 0
        
        # Should include trypsin (detach reagent for HEK293)
        op_names = [op.name.lower() for op in ops]
        assert any("trypsin" in name for name in op_names), \
            "HEK293 protocol should include trypsin"
        
        # Should include DMEM (growth media for HEK293)
        assert any("dmem" in name for name in op_names), \
            "HEK293 protocol should include DMEM media"
    
    def test_unknown_cell_line_raises_error(self):
        """Test that unknown cell line raises ValueError."""
        resolver = ProtocolResolver()
        
        with pytest.raises(ValueError, match="Unknown cell line"):
            resolver.resolve_passage_protocol_t75("UNKNOWN_CELL_LINE")
    
    def test_protocol_includes_incubation(self):
        """Test that protocol includes incubation step."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("iPSC")
        
        # Should have incubation step
        incubate_ops = [op for op in ops if "incubate" in op.name.lower()]
        assert len(incubate_ops) > 0, \
            "Protocol should include incubation step"
        
        # Incubation should have time score > 0
        assert any(op.time_score > 0 for op in incubate_ops), \
            "Incubation should have non-zero time score"
    
    def test_protocol_includes_centrifuge(self):
        """Test that protocol includes centrifuge step."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t75("iPSC")
        
        # Should have centrifuge step
        centrifuge_ops = [op for op in ops if "centrifuge" in op.name.lower()]
        assert len(centrifuge_ops) > 0, \
            "Protocol should include centrifuge step"

    # --- T25 Tests ---

    def test_resolve_ipsc_t25_protocol(self):
        """Test iPSC T25 protocol resolution."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t25("iPSC")
        
        assert isinstance(ops, list)
        assert len(ops) > 0
        
        # Check for T25 specific volumes (e.g. wash_1 is 3.0mL)
        # We can check the name or the cost (cost depends on volume)
        # Let's check the name of the dispense ops
        dispense_ops = [op for op in ops if "dispense" in op.name.lower()]
        
        # There should be a dispense op with 3.0mL (wash_1)
        assert any("3.0ml" in op.name.lower() for op in dispense_ops), \
            "Should have 3.0mL dispense step for T25 wash"
            
        # Should include accutase
        assert any("accutase" in op.name.lower() for op in dispense_ops)

    def test_resolve_hek293_t25_protocol(self):
        """Test HEK293 T25 protocol resolution."""
        resolver = ProtocolResolver()
        ops = resolver.resolve_passage_protocol_t25("HEK293")
        
        assert isinstance(ops, list)
        assert len(ops) > 0
        
        # Should include trypsin
        assert any("trypsin" in op.name.lower() for op in ops)

    # --- Wrapper Tests ---

    def test_wrapper_resolved(self):
        """Test unified wrapper with cell_line provided."""
        lwm = LabWorldModel.empty()
        ops = lwm.get_passage_protocol("iPSC", "T75")
        
        assert isinstance(ops, list)
        assert len(ops) > 0
        assert any("accutase" in op.name.lower() for op in ops)

    def test_wrapper_legacy_fallback(self):
        """Test unified wrapper with cell_line=None (legacy fallback)."""
        lwm = LabWorldModel.empty()
        ops = lwm.get_passage_protocol(None, "T75")
        
        # Should return a list with one composite UnitOp
        assert isinstance(ops, list)
        assert len(ops) == 1
        op = ops[0]
        
        # Legacy op_passage returns a composite op with sub_steps
        assert len(op.sub_steps) > 0
        # Legacy defaults to accutase
        # Check sub-steps for accutase
        sub_names = [sub.name.lower() for sub in op.sub_steps]
        assert any("accutase" in name for name in sub_names)

    def test_resolve_ipsc_t175_autoscale(self):
        """Test iPSC T175 protocol resolution with auto-scaling."""
        resolver = ProtocolResolver()
        # T175 is not in cell_lines.yaml, so it should fallback to T75 reference and scale.
        # T75 wash_1 = 10.0 mL.
        # T175 working_vol = 30.0 mL. T75 working_vol = 15.0 mL. Scale = 2.0.
        # Expected wash_1 = 20.0 mL.
        
        ops = resolver.resolve_passage_protocol("iPSC", "T175")
        
        assert isinstance(ops, list)
        assert len(ops) > 0
        
        dispense_ops = [op for op in ops if "dispense" in op.name.lower()]
        
        # Check for 20.0mL wash
        assert any("20.0ml" in op.name.lower() for op in dispense_ops), \
            "Should have 20.0mL dispense step for T175 wash (scaled from T75)"

    def test_get_cell_line_profile(self):
        """Test retrieving cell line profile from YAML."""
        resolver = ProtocolResolver()
        profile = resolver.get_cell_line_profile("iPSC")
        
        assert profile is not None
        assert profile.cell_type == "iPSC"
        assert profile.coating_required is True
        assert profile.coating_reagent == "laminin_521"
        
        profile_hek = resolver.get_cell_line_profile("HEK293")
        assert profile_hek is not None
        assert profile_hek.coating_required is False

    def test_get_thaw_config_ipsc_t75(self):
        """Test thaw config for iPSC T75."""
        resolver = ProtocolResolver()
        config = resolver.get_thaw_config("iPSC", "flask_t75")
        
        assert config["coating_required"] is True
        assert config["coating_reagent"] == "laminin_521"
        assert config["media"] == "mtesr_plus_kit"
        assert config["volumes_mL"]["media_aliquot"] == 40.0
        assert config["volumes_mL"]["pre_warm"] == 15.0
        assert config["volumes_mL"]["wash_aliquot"] == 5.0
    
    def test_get_thaw_config_hek293_t75(self):
        """Test thaw config for HEK293 T75."""
        resolver = ProtocolResolver()
        config = resolver.get_thaw_config("HEK293", "flask_t75")
        
        assert config["coating_required"] is False
        assert config["media"] == "dmem_high_glucose"
        assert config["volumes_mL"]["media_aliquot"] == 40.0
        assert config["volumes_mL"]["pre_warm"] == 15.0
    
    def test_get_feed_config_ipsc_t75(self):
        """Test feed config for iPSC T75."""
        resolver = ProtocolResolver()
        config = resolver.get_feed_config("iPSC", "flask_t75")
        
        assert config["media"] == "mtesr_plus_kit"
        assert config["volume_ml"] == 15.0
        assert config["schedule"]["interval_days"] == 1
    
    def test_get_feed_config_hek293_t75(self):
        """Test feed config for HEK293 T75."""
        resolver = ProtocolResolver()
        config = resolver.get_feed_config("HEK293", "flask_t75")
        
        assert config["media"] == "dmem_high_glucose"
        assert config["volume_ml"] == 15.0
        assert config["schedule"]["interval_days"] == 2
