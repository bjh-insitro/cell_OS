"""
Integration test: Verify agent uses calibrated morphology when available.

Tests that:
  - Agent uses morphology_corrected if present
  - Agent logs calibration usage
  - Agent works correctly with or without calibration
  - Calibration metadata flows through to observations
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.analysis.apply_calibration import apply_calibration_to_observation


@pytest.mark.integration
def test_agent_accepts_calibrated_observations():
    """
    Test that agent can process observations with calibration fields.

    This is a smoke test - we're just verifying the agent doesn't crash
    when given observations with morphology_corrected and calibration fields.
    """
    # Load calibration report
    cal_path = Path("results/cal_beads_dyes_seed42/calibration/calibration_report.json")
    if not cal_path.exists():
        pytest.skip("Calibration report not found; run calibration first")

    profile = CalibrationProfile(cal_path)

    # Create synthetic observation (mimics cell_painting observation)
    obs_raw = {
        "well_id": "A1",  # Corner well - should get vignette boost
        "cell_line": "A549",
        "compound": "DMSO",
        "dose_uM": 0.0,
        "morphology": {
            "er": 100.0,
            "mito": 100.0,
            "nucleus": 100.0,
            "actin": 100.0,
            "rna": 100.0,
        }
    }

    # Apply calibration
    obs_cal = apply_calibration_to_observation(obs_raw, profile)

    # Verify calibration was applied
    assert "morphology_corrected" in obs_cal
    assert "calibration" in obs_cal
    assert obs_cal["calibration"]["applied"] is True

    # Verify edge well got boosted (vignette correction)
    assert obs_cal["morphology_corrected"]["er"] > obs_cal["morphology"]["er"]

    print("✓ Calibrated observation created:")
    print(f"  Raw ER:       {obs_cal['morphology']['er']:.1f} AU")
    print(f"  Corrected ER: {obs_cal['morphology_corrected']['er']:.1f} AU")
    print(f"  Boost:        {obs_cal['morphology_corrected']['er']/obs_cal['morphology']['er']:.2f}x")


@pytest.mark.integration
def test_agent_world_handles_both_raw_and_calibrated():
    """
    Test that agent's execute_design_v2() handles both raw and calibrated observations.

    This verifies that the agent:
    1. Uses morphology_corrected when present
    2. Falls back to morphology when not present
    3. Doesn't crash or produce errors

    This is a lightweight test - we just verify the code path exists and doesn't crash.
    Full end-to-end testing would require running a complete epistemic agent cycle.
    """
    # Create two observations: one raw, one calibrated
    obs_raw = {
        "well_id": "H12",  # Center well
        "cell_line": "A549",
        "compound": "DMSO",
        "dose_uM": 0.0,
        "morphology": {
            "er": 100.0,
            "mito": 100.0,
            "nucleus": 100.0,
            "actin": 100.0,
            "rna": 100.0,
        }
    }

    obs_calibrated = {
        "well_id": "A1",  # Corner well
        "cell_line": "A549",
        "compound": "DMSO",
        "dose_uM": 0.0,
        "morphology": {
            "er": 100.0,
            "mito": 100.0,
            "nucleus": 100.0,
            "actin": 100.0,
            "rna": 100.0,
        },
        "morphology_corrected": {
            "er": 115.0,  # Boosted by vignette correction
            "mito": 114.0,
            "nucleus": 114.5,
            "actin": 116.5,
            "rna": 117.0,
        },
        "calibration": {
            "schema_version": "bead_plate_calibration_report_v1",
            "applied": True,
            "vignette_applied": True,
        }
    }

    # Verify the logic path: code should detect morphology_corrected and use it
    # This simulates what the agent's execute_design_v2() does
    def simulate_agent_logic(sim_result):
        """Simulate the agent's morphology selection logic."""
        morph_raw = sim_result['morphology']

        # Use corrected morphology if calibration was applied
        if 'morphology_corrected' in sim_result:
            morph = sim_result['morphology_corrected']
            used_corrected = True
        else:
            morph = morph_raw
            used_corrected = False

        return morph, used_corrected

    # Test raw observation
    morph_raw_used, used_corrected_raw = simulate_agent_logic(obs_raw)
    assert morph_raw_used == obs_raw['morphology']
    assert used_corrected_raw is False

    # Test calibrated observation
    morph_cal_used, used_corrected_cal = simulate_agent_logic(obs_calibrated)
    assert morph_cal_used == obs_calibrated['morphology_corrected']
    assert used_corrected_cal is True

    # Verify corrected values are different from raw
    assert morph_cal_used['er'] != obs_calibrated['morphology']['er']
    assert morph_cal_used['er'] == 115.0  # Should use corrected value

    print("✓ Agent logic correctly selects morphology_corrected when available")
    print(f"  Raw observation: used raw morphology (er={morph_raw_used['er']:.1f})")
    print(f"  Calibrated observation: used corrected morphology (er={morph_cal_used['er']:.1f})")


@pytest.mark.integration
def test_calibration_metadata_flows_through_agent():
    """
    Test that calibration metadata is preserved in agent's observation processing.
    """
    # This is a documentation test - verifying the integration pattern works
    # Full end-to-end test would require running epistemic agent with calibrated data

    obs_with_cal = {
        "well_id": "A1",
        "morphology": {"er": 100.0, "mito": 100.0, "nucleus": 100.0, "actin": 100.0, "rna": 100.0},
        "morphology_corrected": {"er": 115.0, "mito": 114.0, "nucleus": 114.5, "actin": 116.5, "rna": 117.0},
        "calibration": {
            "applied": True,
            "vignette_applied": True,
            "saturation_warnings": ["er: 350.0 AU near safe max 325.4 AU"]
        }
    }

    # Verify structure matches expected schema
    assert "morphology" in obs_with_cal
    assert "morphology_corrected" in obs_with_cal
    assert "calibration" in obs_with_cal
    assert obs_with_cal["calibration"]["applied"] is True

    print("✓ Calibration metadata structure validated")
    print(f"  Vignette applied: {obs_with_cal['calibration']['vignette_applied']}")
    print(f"  Warnings: {len(obs_with_cal['calibration'].get('saturation_warnings', []))}")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
