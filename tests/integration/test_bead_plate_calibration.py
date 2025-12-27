from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cell_os.calibration.bead_plate_calibration import calibrate_from_observations, SCHEMA_VERSION


@pytest.mark.integration
def test_bead_plate_calibration_report_schema(tmp_path: Path) -> None:
    """
    Integration skeleton:
      - Runs calibration on a real observations.jsonl if present.
      - Asserts schema keys exist.
      - Asserts vignette block is at least structurally sane.

    You can wire this to your repo fixture paths later.
    """
    # Adjust to your real output path or use a fixture generator.
    obs = Path("results/cal_beads_dyes_seed42/observations.jsonl")
    if not obs.exists():
        pytest.skip("No bead plate observations.jsonl found; generate it before running this integration test.")

    outdir = tmp_path / "calibration"
    report = calibrate_from_observations(
        observations_jsonl=str(obs),
        design_json=None,
        outdir=str(outdir),
    )

    # Required top-level keys
    assert report["schema_version"] == SCHEMA_VERSION
    for k in [
        "created_utc",
        "inputs",
        "channels",
        "floor",
        "vignette",
        "saturation",
        "quantization",
        "exposure_recommendations",
        "notes",
    ]:
        assert k in report

    # Observable contract fields exist in each block
    for block_name in ["floor", "vignette", "saturation", "quantization", "exposure_recommendations"]:
        blk = report[block_name]
        assert "observable" in blk
        if blk["observable"] is False:
            assert isinstance(blk.get("reason"), str)

    # Vignette sanity: if observable, edge_multiplier dict exists with valid values
    vig = report["vignette"]
    if vig["observable"]:
        assert isinstance(vig.get("edge_multiplier"), dict)
        # Edge multipliers should be in reasonable range (typical vignette is 0.7-1.0)
        edge_mults = vig["edge_multiplier"]
        non_null_channels = sum(1 for v in edge_mults.values() if v is not None)
        assert non_null_channels >= 3, f"Expected at least 3 channels with vignette estimates, got {non_null_channels}"

        for ch, v in edge_mults.items():
            if v is not None:
                assert 0.5 <= v <= 1.0, f"Edge multiplier for {ch} out of range: {v}"

        # R² should be reasonable
        fit_qual = vig.get("fit_quality", {})
        if fit_qual.get("r_squared"):
            rsq_vals = [v for v in fit_qual["r_squared"].values() if v is not None]
            if rsq_vals:
                assert all(0 <= r <= 1 for r in rsq_vals), "R² values out of [0,1] range"

    # Saturation: if observable, check per-channel data exists
    sat = report["saturation"]
    if sat["observable"]:
        assert isinstance(sat.get("per_channel"), dict)
        per_ch = sat["per_channel"]
        # At least some channels should have data
        channels_with_data = sum(1 for v in per_ch.values() if isinstance(v, dict) and v.get("p99") is not None)
        assert channels_with_data >= 3, f"Expected at least 3 channels with saturation data, got {channels_with_data}"

    # Quantization: check if detected (may or may not be observable depending on detector config)
    quant = report["quantization"]
    # Don't assert observable (depends on detector config), but check structure
    if quant.get("per_channel"):
        per_ch = quant["per_channel"]
        for ch, data in per_ch.items():
            assert "quantization_detected" in data
            if data["quantization_detected"]:
                assert data.get("quant_step_estimate") is not None

    # Exposure recommendations: if observable, check structure
    expo = report["exposure_recommendations"]
    if expo["observable"]:
        assert expo.get("policy") is not None
        assert "target_fraction_of_saturation" in expo["policy"]
        per_ch = expo.get("per_channel", {})
        if per_ch:
            # At least check that some channels have recommendations
            recs = [v.get("recommended_exposure_multiplier") for v in per_ch.values()]
            non_null_recs = sum(1 for r in recs if r is not None)
            assert non_null_recs >= 3, f"Expected at least 3 channels with exposure recommendations"

    # Output written
    report_path = outdir / "calibration_report.json"
    assert report_path.exists()
    loaded = json.loads(report_path.read_text())
    assert loaded["schema_version"] == SCHEMA_VERSION
