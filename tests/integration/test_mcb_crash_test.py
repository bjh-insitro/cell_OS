"""
Integration tests for MCB crash test behavior.

Tests that the MCB crash test simulation produces sane results
with deterministic seeds for regression testing.
"""

import pytest
from cell_os.mcb_crash import MCBTestConfig, run_mcb_crash_test


def test_u2os_mcb_pilot_scale_behaves_sanely():
    """Test that MCB crash test produces reasonable results."""
    config = MCBTestConfig(
        num_simulations=50,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=123,
        enable_failures=True,
        output_dir=None,
    )

    result = run_mcb_crash_test(config)
    summary = result.summary

    # Basic shape
    assert summary["total_runs"] == 50
    assert "successful_runs" in summary
    assert "vials_p5" in summary
    assert "vials_p50" in summary
    assert "vials_p95" in summary
    assert "duration_p50" in summary
    assert "waste_p50" in summary

    # Success rate not ridiculous
    success_rate = summary["successful_runs"] / summary["total_runs"]
    assert 0.7 <= success_rate <= 1.0, f"Success rate {success_rate:.1%} outside expected range"

    # Vials behavior
    assert summary["vials_p50"] == 30, f"Median vials {summary['vials_p50']} != 30"
    assert 0 <= summary["vials_p5"] <= 30, f"P5 vials {summary['vials_p5']} outside [0, 30]"
    assert summary["vials_p95"] <= 30, f"P95 vials {summary['vials_p95']} > 30"

    # Duration in a reasonable range for 10x expansion
    assert 2 <= summary["duration_p50"] <= 10, f"Median duration {summary['duration_p50']} outside [2, 10] days"

    # Waste present and non-negative
    assert summary["waste_p50"] >= 0, f"Median waste {summary['waste_p50']} is negative"

    # Failures array is a list
    failures = summary.get("failures", [])
    assert isinstance(failures, list), "Failures should be a list"


def test_u2os_mcb_without_failures():
    """Test MCB crash test with failures disabled."""
    config = MCBTestConfig(
        num_simulations=20,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=456,
        enable_failures=False,
        output_dir=None,
    )

    result = run_mcb_crash_test(config)
    summary = result.summary

    # With failures disabled, success rate should be 100%
    assert summary["successful_runs"] == 20
    assert summary["success_rate"] == 1.0
    assert summary["contaminated_runs"] == 0
    assert summary["failed_runs"] == 0

    # All runs should hit target
    assert summary["vials_p50"] == 30
    assert summary["vials_p5"] == 30
    assert summary["vials_p95"] == 30


def test_mcb_crash_test_deterministic():
    """Test that same seed produces same results."""
    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=789,
        enable_failures=True,
        output_dir=None,
    )

    result1 = run_mcb_crash_test(config)
    result2 = run_mcb_crash_test(config)

    # Should get identical results
    assert result1.summary["successful_runs"] == result2.summary["successful_runs"]
    assert result1.summary["vials_p50"] == result2.summary["vials_p50"]
    assert result1.summary["duration_p50"] == result2.summary["duration_p50"]
    assert result1.summary["waste_p50"] == result2.summary["waste_p50"]


def test_mcb_crash_test_dataframes():
    """Test that result DataFrames have expected structure."""
    config = MCBTestConfig(
        num_simulations=10,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=999,
        enable_failures=True,
        output_dir=None,
    )

    result = run_mcb_crash_test(config)

    # Check run_results DataFrame
    assert len(result.run_results) == 10
    expected_columns = [
        "run_id", "duration_days", "final_vials", "waste_vials",
        "waste_cells", "waste_vials_equivalent", "waste_fraction",
        "had_contamination", "terminal_failure", "failed_reason",
        "total_media_l", "failures", "violations", "daily_metrics"
    ]
    for col in expected_columns:
        assert col in result.run_results.columns, f"Missing column: {col}"

    # Check daily_metrics DataFrame
    if not result.daily_metrics.empty:
        expected_daily_columns = [
            "day", "total_cells", "flask_count", "avg_confluence",
            "avg_viability", "media_consumed", "run_id"
        ]
        for col in expected_daily_columns:
            assert col in result.daily_metrics.columns, f"Missing daily column: {col}"
