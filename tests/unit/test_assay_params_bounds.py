"""
Test AssayParams validation bounds.

These tests enforce functional forms and bounds, not exact values.
The goal: prevent nonsense parameters that would create oracles or break measurements.
"""

import pytest
from src.cell_os.hardware.assays.assay_params import AssayParams


def test_default_assay_params_valid():
    """Default AssayParams must pass validation."""
    params = AssayParams()  # Should not raise
    assert params.CP_DEAD_SIGNAL_FLOOR == 0.3
    assert params.LDH_DEATH_AMPLIFICATION_CAP == 10.0
    assert params.ATP_SIGNAL_FLOOR == 0.3
    assert params.SEGMENTATION_C_BASE == 0.8


def test_cp_dead_signal_floor_bounds():
    """CP_DEAD_SIGNAL_FLOOR must be in (0, 1) exclusive."""
    # Valid: within bounds
    AssayParams(CP_DEAD_SIGNAL_FLOOR=0.2)
    AssayParams(CP_DEAD_SIGNAL_FLOOR=0.5)

    # Invalid: zero creates viability oracle
    with pytest.raises(ValueError, match="CP_DEAD_SIGNAL_FLOOR must be in \\(0, 1\\)"):
        AssayParams(CP_DEAD_SIGNAL_FLOOR=0.0)

    # Invalid: one creates no-signal regime
    with pytest.raises(ValueError, match="CP_DEAD_SIGNAL_FLOOR must be in \\(0, 1\\)"):
        AssayParams(CP_DEAD_SIGNAL_FLOOR=1.0)

    # Invalid: negative
    with pytest.raises(ValueError, match="CP_DEAD_SIGNAL_FLOOR must be in \\(0, 1\\)"):
        AssayParams(CP_DEAD_SIGNAL_FLOOR=-0.1)


def test_ldh_death_amplification_cap_bounds():
    """LDH_DEATH_AMPLIFICATION_CAP must be in (1, 100)."""
    # Valid
    AssayParams(LDH_DEATH_AMPLIFICATION_CAP=5.0)
    AssayParams(LDH_DEATH_AMPLIFICATION_CAP=20.0)

    # Invalid: must be > 1 to actually cap
    with pytest.raises(ValueError, match="LDH_DEATH_AMPLIFICATION_CAP must be in \\(1, 100\\)"):
        AssayParams(LDH_DEATH_AMPLIFICATION_CAP=1.0)

    # Invalid: unrealistic high value
    with pytest.raises(ValueError, match="LDH_DEATH_AMPLIFICATION_CAP must be in \\(1, 100\\)"):
        AssayParams(LDH_DEATH_AMPLIFICATION_CAP=150.0)


def test_atp_signal_floor_bounds():
    """ATP_SIGNAL_FLOOR must be in (0, 1) exclusive."""
    # Valid
    AssayParams(ATP_SIGNAL_FLOOR=0.2)
    AssayParams(ATP_SIGNAL_FLOOR=0.5)

    # Invalid: zero creates mito dysfunction oracle
    with pytest.raises(ValueError, match="ATP_SIGNAL_FLOOR must be in \\(0, 1\\)"):
        AssayParams(ATP_SIGNAL_FLOOR=0.0)

    # Invalid: one saturates signal
    with pytest.raises(ValueError, match="ATP_SIGNAL_FLOOR must be in \\(0, 1\\)"):
        AssayParams(ATP_SIGNAL_FLOOR=1.0)


def test_segmentation_c_base_bounds():
    """SEGMENTATION_C_BASE must be in [0, 2]."""
    # Valid
    AssayParams(SEGMENTATION_C_BASE=0.0)  # No debris effect
    AssayParams(SEGMENTATION_C_BASE=0.5)
    AssayParams(SEGMENTATION_C_BASE=1.0)
    AssayParams(SEGMENTATION_C_BASE=2.0)  # Max plausible

    # Invalid: negative makes no sense
    with pytest.raises(ValueError, match="SEGMENTATION_C_BASE must be in \\[0, 2\\]"):
        AssayParams(SEGMENTATION_C_BASE=-0.1)

    # Invalid: >2 would mean yield increases with debris
    with pytest.raises(ValueError, match="SEGMENTATION_C_BASE must be in \\[0, 2\\]"):
        AssayParams(SEGMENTATION_C_BASE=3.0)
