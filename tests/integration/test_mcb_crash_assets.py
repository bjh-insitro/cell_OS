"""
Integration tests for MCB crash test dashboard asset generation.

Tests that the MCB crash test correctly generates all required
dashboard assets with proper structure.
"""

import json
import pytest
from pathlib import Path
from cell_os.mcb_crash import MCBTestConfig, run_mcb_crash_test


def test_mcb_crash_generates_dashboard_assets(tmp_path):
    """Test that MCB crash test generates all expected dashboard assets."""
    outdir = tmp_path / "dashboard_assets"
    outdir.mkdir()

    config = MCBTestConfig(
        num_simulations=20,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=123,
        enable_failures=True,
        output_dir=str(outdir),
    )

    run_mcb_crash_test(config)

    # Assert files exist
    expected = [
        "mcb_summary.json",
        "mcb_run_results.csv",
        "mcb_daily_metrics.csv",
        "dashboard_manifest.json",
        "plots_manifest.json",
    ]
    for name in expected:
        assert (outdir / name).exists(), f"Missing file: {name}"

    # Sanity check mcb_summary.json contents
    summary = json.loads((outdir / "mcb_summary.json").read_text())
    assert "total_runs" in summary
    assert "vials_p50" in summary
    assert "waste_p50" in summary
    assert "success_rate" in summary
    assert summary["total_runs"] == 20


def test_mcb_summary_json_structure(tmp_path):
    """Test that mcb_summary.json has all expected fields."""
    outdir = tmp_path / "dashboard_assets"
    outdir.mkdir()

    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=456,
        enable_failures=True,
        output_dir=str(outdir),
    )

    run_mcb_crash_test(config)

    summary = json.loads((outdir / "mcb_summary.json").read_text())

    # Check all required fields
    required_fields = [
        "total_runs", "successful_runs", "success_rate",
        "contaminated_runs", "failed_runs",
        "vials_p5", "vials_p50", "vials_p95",
        "waste_p50", "waste_total", "waste_cells_p50",
        "waste_vials_eq_p50", "waste_fraction_p50",
        "duration_p50", "failures", "violations"
    ]
    for field in required_fields:
        assert field in summary, f"Missing field in summary: {field}"


def test_dashboard_manifest_structure(tmp_path):
    """Test that dashboard_manifest.json has correct structure."""
    outdir = tmp_path / "dashboard_assets"
    outdir.mkdir()

    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=789,
        enable_failures=True,
        output_dir=str(outdir),
    )

    run_mcb_crash_test(config)

    manifest = json.loads((outdir / "dashboard_manifest.json").read_text())

    # Check structure
    assert "title" in manifest
    assert "description" in manifest
    assert "components" in manifest
    assert isinstance(manifest["components"], list)

    # Check that we have expected component types
    component_types = [c["type"] for c in manifest["components"]]
    assert "metric" in component_types
    assert "plot" in component_types
    assert "table" in component_types


def test_plots_manifest_structure(tmp_path):
    """Test that plots_manifest.json contains base64 encoded plots."""
    outdir = tmp_path / "dashboard_assets"
    outdir.mkdir()

    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=999,
        enable_failures=True,
        output_dir=str(outdir),
    )

    run_mcb_crash_test(config)

    plots = json.loads((outdir / "plots_manifest.json").read_text())

    # Check expected plots exist
    expected_plots = ["dist_vials", "growth_curves", "dist_waste"]
    for plot_name in expected_plots:
        assert plot_name in plots, f"Missing plot: {plot_name}"
        # Check that it's a non-empty base64 string
        assert isinstance(plots[plot_name], str)
        assert len(plots[plot_name]) > 100  # Base64 encoded PNG should be substantial


def test_csv_files_not_empty(tmp_path):
    """Test that generated CSV files are not empty."""
    outdir = tmp_path / "dashboard_assets"
    outdir.mkdir()

    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=111,
        enable_failures=True,
        output_dir=str(outdir),
    )

    run_mcb_crash_test(config)

    # Check run results CSV
    run_results_path = outdir / "mcb_run_results.csv"
    assert run_results_path.exists()
    content = run_results_path.read_text()
    lines = content.strip().split('\n')
    assert len(lines) > 1  # Header + at least one data row
    assert len(lines) == 11  # Header + 10 runs

    # Check daily metrics CSV
    daily_metrics_path = outdir / "mcb_daily_metrics.csv"
    assert daily_metrics_path.exists()
    content = daily_metrics_path.read_text()
    lines = content.strip().split('\n')
    assert len(lines) > 1  # Header + at least one data row
