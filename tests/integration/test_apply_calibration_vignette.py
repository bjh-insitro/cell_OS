"""
Integration test for calibration application (vignette correction).

Verifies that:
  - Center wells remain approximately unchanged
  - Edge wells are corrected upward by ~1/0.85 factor
  - Calibration metadata is stamped
  - Original morphology remains unchanged (read-only)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.analysis.apply_calibration import apply_calibration_to_observation


@pytest.mark.integration
def test_vignette_correction_center_vs_edge():
    """
    Test that vignette correction:
      - Leaves center wells approximately unchanged
      - Boosts edge wells by ~1/edge_multiplier factor
    """
    # Load real calibration report
    cal_path = Path("results/cal_beads_dyes_seed42/calibration/calibration_report.json")
    if not cal_path.exists():
        pytest.skip("Calibration report not found; run calibration first")

    profile = CalibrationProfile(cal_path)

    # Check vignette is observable
    if not profile._vignette.get("observable"):
        pytest.skip("Vignette not observable in calibration report")

    # Get edge multiplier for ER channel (should be ~0.85-0.88)
    edge_mult_er = profile._vignette["edge_multiplier"]["er"]
    assert 0.7 <= edge_mult_er <= 1.0, f"Edge multiplier out of range: {edge_mult_er}"

    # Synthetic observations: center well vs corner well
    obs_center = {
        "well_id": "H12",  # Near center
        "morphology": {
            "er": 100.0,
            "mito": 100.0,
            "nucleus": 100.0,
            "actin": 100.0,
            "rna": 100.0,
        }
    }

    obs_corner = {
        "well_id": "A1",  # Corner
        "morphology": {
            "er": 100.0,
            "mito": 100.0,
            "nucleus": 100.0,
            "actin": 100.0,
            "rna": 100.0,
        }
    }

    # Apply calibration
    obs_center_cal = apply_calibration_to_observation(obs_center, profile)
    obs_corner_cal = apply_calibration_to_observation(obs_corner, profile)

    # Check that corrected fields exist
    assert "morphology_corrected" in obs_center_cal
    assert "calibration" in obs_center_cal
    assert obs_center_cal["calibration"]["applied"] is True

    # Check original morphology unchanged (read-only)
    assert obs_center["morphology"]["er"] == 100.0
    assert obs_corner["morphology"]["er"] == 100.0

    # Center well: corrected ~= raw (vignette multiplier ~1.0 at center)
    center_corrected_er = obs_center_cal["morphology_corrected"]["er"]
    assert 98.0 <= center_corrected_er <= 102.0, (
        f"Center well should remain ~unchanged: {center_corrected_er:.2f}"
    )

    # Corner well: corrected > raw (boosted by 1/edge_multiplier)
    corner_corrected_er = obs_corner_cal["morphology_corrected"]["er"]
    expected_boost = 100.0 / edge_mult_er  # e.g., 100 / 0.87 = 115

    # Allow 10% tolerance
    assert expected_boost * 0.9 <= corner_corrected_er <= expected_boost * 1.1, (
        f"Corner well not boosted correctly: "
        f"expected ~{expected_boost:.1f}, got {corner_corrected_er:.1f}"
    )

    print(f"✓ Center well: {100.0:.1f} → {center_corrected_er:.1f} (unchanged)")
    print(f"✓ Corner well: {100.0:.1f} → {corner_corrected_er:.1f} (boosted by {corner_corrected_er/100.0:.2f}x)")
    print(f"  Expected boost: {1.0/edge_mult_er:.2f}x (edge_mult={edge_mult_er:.3f})")


@pytest.mark.integration
def test_calibration_metadata_stamped():
    """Test that calibration metadata is correctly stamped."""
    cal_path = Path("results/cal_beads_dyes_seed42/calibration/calibration_report.json")
    if not cal_path.exists():
        pytest.skip("Calibration report not found")

    profile = CalibrationProfile(cal_path)

    obs = {
        "well_id": "A1",
        "morphology": {"er": 50.0, "mito": 60.0, "nucleus": 70.0, "actin": 40.0, "rna": 55.0}
    }

    obs_cal = apply_calibration_to_observation(obs, profile)

    # Check metadata stamped
    assert "calibration" in obs_cal
    cal_meta = obs_cal["calibration"]

    assert "schema_version" in cal_meta
    assert cal_meta["applied"] is True
    assert "vignette_applied" in cal_meta
    assert "report_created_utc" in cal_meta

    print(f"✓ Calibration metadata stamped: {list(cal_meta.keys())}")


@pytest.mark.integration
def test_saturation_warnings_triggered():
    """Test that saturation warnings are added for high-intensity wells."""
    cal_path = Path("results/cal_beads_dyes_seed42/calibration/calibration_report.json")
    if not cal_path.exists():
        pytest.skip("Calibration report not found")

    profile = CalibrationProfile(cal_path)

    # Get safe max for ER (should be ~330 AU based on report)
    safe_max_er = profile.safe_max("er")
    if safe_max_er is None:
        pytest.skip("Saturation not observable")

    # Create observation near safe max
    obs_high = {
        "well_id": "A1",
        "morphology": {
            "er": safe_max_er * 0.95,  # 95% of safe max → should warn
            "mito": 50.0,
            "nucleus": 60.0,
            "actin": 40.0,
            "rna": 45.0,
        }
    }

    obs_cal = apply_calibration_to_observation(obs_high, profile)

    # Check warning added
    assert "saturation_warnings" in obs_cal["calibration"], (
        "Expected saturation warning for high-intensity well"
    )

    warnings = obs_cal["calibration"]["saturation_warnings"]
    assert any("er" in w for w in warnings), (
        f"Expected ER warning in: {warnings}"
    )

    print(f"✓ Saturation warning triggered: {warnings[0]}")


@pytest.mark.integration
def test_quantization_awareness():
    """Test that quantization-aware significance checking works."""
    cal_path = Path("results/cal_beads_dyes_seed42/calibration/calibration_report.json")
    if not cal_path.exists():
        pytest.skip("Calibration report not found")

    profile = CalibrationProfile(cal_path)

    # Get quantization step for ER
    resolution_er = profile.effective_resolution("er")
    assert resolution_er > 0, "Expected positive resolution"

    # Test significance checking
    # Delta below 2*resolution should be noise
    small_delta = resolution_er * 1.5
    large_delta = resolution_er * 3.0

    assert not profile.is_significant_difference(small_delta, "er"), (
        f"Delta {small_delta:.4f} below 2*{resolution_er:.4f} should not be significant"
    )

    assert profile.is_significant_difference(large_delta, "er"), (
        f"Delta {large_delta:.4f} above 2*{resolution_er:.4f} should be significant"
    )

    print(f"✓ Quantization awareness: resolution={resolution_er:.4f} AU")
    print(f"  Small delta ({small_delta:.4f}): not significant")
    print(f"  Large delta ({large_delta:.4f}): significant")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
