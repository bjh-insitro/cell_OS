"""
Unit tests for calibration-coverage match enforcement (Issue #2).

Tests that:
1. Coverage check detects position mismatches
2. Biology is blocked when calibration doesn't cover experiment positions
3. Coverage gaps force additional calibration
4. Balanced calibration passes coverage check
"""

import pytest
from cell_os.epistemic_agent.beliefs.state import BeliefState, CalibrationProvenance
from cell_os.epistemic_agent.acquisition.chooser import TemplateChooser


class TestCoverageCheck:
    """Test _check_calibration_coverage method."""

    def test_no_calibration_returns_ok(self):
        """No calibration data yet should pass (handled by gate checks)."""
        beliefs = BeliefState()
        chooser = TemplateChooser()

        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is True
        assert gap_reason is None
        assert details["status"] == "no_calibration_yet"

    def test_center_only_calibration_covers_center_biology(self):
        """Center-only calibration should cover center-only biology."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )
        chooser = TemplateChooser()

        # dose_ladder_coarse uses center by default
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is True
        assert gap_reason is None
        assert details["calibration_center_fraction"] == 1.0

    def test_center_only_calibration_fails_for_edge_biology(self):
        """Center-only calibration should fail for edge biology."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )
        chooser = TemplateChooser()

        # edge_center_test requires both positions
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )

        assert is_covered is False
        assert "edge" in gap_reason.lower()
        assert "coverage_gaps" in details
        assert len(details["coverage_gaps"]) > 0

    def test_edge_only_calibration_fails_for_center_biology(self):
        """Edge-only calibration should fail for center biology."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"edge": 96},
            total_wells=96,
        )
        chooser = TemplateChooser()

        # dose_ladder_coarse uses center by default
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is False
        assert "center" in gap_reason.lower()
        assert details["calibration_center_wells"] == 0

    def test_balanced_calibration_covers_all(self):
        """Balanced calibration should cover both center and edge."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 48, "edge": 48},
            total_wells=96,
        )
        chooser = TemplateChooser()

        # edge_center_test requires both positions
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )

        assert is_covered is True
        assert gap_reason is None
        assert details["calibration_center_fraction"] == 0.5
        assert details["calibration_edge_fraction"] == 0.5

    def test_min_wells_threshold(self):
        """Coverage requires minimum wells per position."""
        beliefs = BeliefState()
        # Only 4 center wells (below COVERAGE_MIN_WELLS=8)
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 4, "edge": 92},
            total_wells=96,
        )
        chooser = TemplateChooser()

        # dose_ladder_coarse uses center
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is False
        assert "center" in gap_reason.lower()
        assert "4" in gap_reason  # Shows actual count

    def test_min_fraction_threshold(self):
        """Coverage requires minimum fraction per position."""
        beliefs = BeliefState()
        # 8 center wells but only 5% of total (below COVERAGE_MIN_FRACTION=10%)
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 8, "edge": 152},
            total_wells=160,
        )
        chooser = TemplateChooser()

        # dose_ladder_coarse uses center
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is False
        assert "center" in gap_reason.lower()


class TestInferExperimentPositions:
    """Test _infer_experiment_positions method."""

    def test_edge_center_test_uses_both(self):
        """edge_center_test requires both positions."""
        chooser = TemplateChooser()
        positions = chooser._infer_experiment_positions("edge_center_test", {})
        assert positions == {"center", "edge"}

    def test_baseline_replicates_default_center(self):
        """baseline_replicates defaults to center."""
        chooser = TemplateChooser()
        positions = chooser._infer_experiment_positions("baseline_replicates", {})
        assert positions == {"center"}

    def test_baseline_replicates_full_spatial(self):
        """baseline_replicates with full_spatial uses both."""
        chooser = TemplateChooser()
        positions = chooser._infer_experiment_positions(
            "baseline_replicates",
            {"coverage_strategy": "full_spatial"}
        )
        assert positions == {"center", "edge"}

    def test_biology_template_defaults_center(self):
        """Unknown biology templates default to center."""
        chooser = TemplateChooser()
        positions = chooser._infer_experiment_positions("dose_ladder_coarse", {})
        assert positions == {"center"}

    def test_explicit_position_tags(self):
        """Explicit position_tags override default."""
        chooser = TemplateChooser()
        positions = chooser._infer_experiment_positions(
            "some_biology_template",
            {"position_tags": ["edge", "center"]}
        )
        assert positions == {"center", "edge"}


class TestCoverageEnforcement:
    """Test that coverage gaps force calibration before biology."""

    def test_coverage_gap_forces_calibration(self):
        """Coverage gap should force calibration instead of biology."""
        beliefs = BeliefState()
        # Center-only calibration
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )
        # Set up gates as earned (to reach biology selection)
        beliefs.noise_sigma_stable = True
        beliefs.noise_rel_width = 0.20
        beliefs.noise_df_total = 100
        beliefs.ldh_sigma_stable = True
        beliefs.cell_paint_sigma_stable = True
        beliefs.calibration_plate_run = True

        chooser = TemplateChooser()
        beliefs.begin_cycle(5)

        # Attempt biology with edge position requirement
        # First set a template that needs edge coverage
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )

        # Should detect coverage gap
        assert is_covered is False
        assert "edge" in gap_reason.lower()

    def test_balanced_calibration_allows_biology(self):
        """Balanced calibration should allow any biology."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 50, "edge": 46},
            total_wells=96,
        )

        chooser = TemplateChooser()

        # Check both center and edge biology
        for template in ["dose_ladder_coarse", "edge_center_test"]:
            is_covered, gap_reason, details = chooser._check_calibration_coverage(
                beliefs, template, {}
            )
            assert is_covered is True, f"Template {template} should be covered"


class TestAttackScenarios:
    """Test detection of position mismatch attack scenarios."""

    def test_edge_heavy_calibration_detected(self):
        """Detect edge-heavy calibration before center biology."""
        beliefs = BeliefState()
        # 95% edge calibration (potential attack) - only 5 center wells
        # This is below COVERAGE_MIN_WELLS (8) so should fail
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 5, "edge": 91},
            total_wells=96,
        )

        chooser = TemplateChooser()

        # Attempting center biology
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        # Should detect coverage gap (center has only 5 wells, below threshold)
        assert is_covered is False
        assert "center" in gap_reason.lower()
        assert details["calibration_center_wells"] == 5

    def test_honest_calibration_passes(self):
        """Honest calibration matching experiment positions passes."""
        beliefs = BeliefState()
        # Center-heavy calibration for center biology (honest)
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 80, "edge": 16},
            total_wells=96,
        )

        chooser = TemplateChooser()

        # Center biology should pass
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        assert is_covered is True
        assert gap_reason is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
