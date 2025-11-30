"""
Integration tests for WCB Wrapper.
"""

import pytest
from cell_os.simulation.wcb_wrapper import simulate_wcb_generation, MCBVialSpec

def test_simulate_wcb_generation_success():
    """Test that WCB generation simulation returns a successful result bundle."""
    spec = MCBVialSpec(
        cell_line="U2OS",
        vial_id="MCB-U2OS-001",
        passage_number=3
    )
    
    result = simulate_wcb_generation(
        spec=spec,
        target_vials=50,
        cells_per_vial=1e6
    )
    
    assert result.success
    assert result.cell_line == "U2OS"
    assert len(result.vials) == 50
    assert result.vials[0].source_mcb_vial_id == "MCB-U2OS-001"
    assert result.vials[0].passage_number == 5 # 3 + 2
    assert not result.daily_metrics.empty

def test_simulate_wcb_generation_large_scale():
    """Test larger scale WCB generation."""
    spec = MCBVialSpec(
        cell_line="HepG2",
        vial_id="MCB-HepG2-005",
        passage_number=4
    )
    
    result = simulate_wcb_generation(
        spec=spec,
        target_vials=200,
        cells_per_vial=1e6
    )
    
    assert result.success
    assert len(result.vials) == 200
    assert result.vials[0].passage_number == 6 # 4 + 2
