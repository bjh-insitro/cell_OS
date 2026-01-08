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


class TestPathologicalCycle0Layout:
    """Test that pathological cycle 0 calibration layouts are blocked (v0.6.1).

    Attack scenario:
    - Agent calibrates in cycle 0 with pathological layout (edge-only or center-only)
    - This earns provenance and sigma stability
    - Agent then attempts biology in opposite-position wells
    - System must BLOCK with coverage_gap trigger and auditable receipt

    This ensures cycle 0 gate doesn't become "anything goes as long as it's early."
    """

    def test_edge_only_cycle0_blocks_center_biology(self):
        """Edge-only calibration in cycle 0 should block center biology.

        Full scenario:
        1. Cycle 0: calibrate edge-only (96 wells, enough for sigma stability)
        2. Cycle 1: attempt center biology
        3. Must be blocked with coverage_gap trigger

        Note: We use direct provenance setup because the NoiseBeliefUpdater
        only accepts center wells for noise calibration. In a real system,
        edge-only calibration would be achieved through a different template.
        """
        # Phase 1: Simulate edge-only calibration (directly set provenance)
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"edge": 96},
            total_wells=96,
            last_update_cycle=0,  # Earned in cycle 0
        )

        # Phase 2: Attempt center biology in cycle 1
        beliefs.begin_cycle(1)
        chooser = TemplateChooser()

        # dose_ladder_coarse uses center by default
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )

        # MUST be blocked
        assert is_covered is False, "Edge-only calibration should NOT cover center biology"
        assert gap_reason is not None, "Must provide gap reason"
        assert "center" in gap_reason.lower(), f"Gap reason should mention center: {gap_reason}"

        # Verify auditable details
        assert "calibration_center_wells" in details
        assert details["calibration_center_wells"] == 0
        assert details["calibration_edge_wells"] == 96

    def test_center_only_cycle0_blocks_edge_biology(self):
        """Center-only calibration in cycle 0 should block edge biology.

        This is the most realistic pathological scenario: the default
        noise calibration (center DMSO) doesn't cover edge positions.
        """
        # Phase 1: Simulate center-only calibration (directly set provenance)
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
            last_update_cycle=0,  # Earned in cycle 0
        )

        # Verify provenance was earned
        assert beliefs.calibration_provenance.total_wells == 96
        assert beliefs.calibration_provenance.center_fraction() == 1.0

        # Phase 2: Attempt edge biology in cycle 1
        beliefs.begin_cycle(1)
        chooser = TemplateChooser()

        # edge_center_test requires edge coverage
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )

        # MUST be blocked
        assert is_covered is False, "Center-only calibration should NOT cover edge biology"
        assert "edge" in gap_reason.lower(), f"Gap reason should mention edge: {gap_reason}"

    def test_balanced_cycle0_allows_any_biology(self):
        """Balanced calibration in cycle 0 should allow any biology position.

        Note: We use direct provenance setup because the NoiseBeliefUpdater
        only accepts center wells for noise calibration. This test verifies
        the coverage check logic, not the updater's filtering.
        """
        # Phase 1: Simulate balanced calibration (directly set provenance)
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 48, "edge": 48},
            total_wells=96,
            last_update_cycle=0,  # Earned in cycle 0
        )

        # Verify balanced provenance
        assert beliefs.calibration_provenance.total_wells == 96
        assert abs(beliefs.calibration_provenance.center_fraction() - 0.5) < 0.01
        assert abs(beliefs.calibration_provenance.edge_fraction() - 0.5) < 0.01

        # Phase 2: Both center and edge biology should be allowed
        beliefs.begin_cycle(1)
        chooser = TemplateChooser()

        # Center biology
        is_covered_center, _, _ = chooser._check_calibration_coverage(
            beliefs, "dose_ladder_coarse", {}
        )
        assert is_covered_center is True, "Balanced calibration should cover center biology"

        # Edge biology
        is_covered_edge, _, _ = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )
        assert is_covered_edge is True, "Balanced calibration should cover edge biology"

    def test_coverage_gap_receipt_is_auditable(self):
        """Coverage gap must produce an auditable receipt with details."""
        beliefs = BeliefState()
        # Pathological: center-only calibration
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )

        chooser = TemplateChooser()

        # Attempt edge biology
        is_covered, gap_reason, details = chooser._check_calibration_coverage(
            beliefs, "edge_center_test", {}
        )

        # Receipt must be auditable
        assert is_covered is False
        assert gap_reason is not None

        # Required audit fields
        assert "calibration_center_fraction" in details
        assert "calibration_edge_fraction" in details
        assert "calibration_center_wells" in details
        assert "calibration_edge_wells" in details
        assert "coverage_gaps" in details

        # Coverage gaps should identify specific missing position
        gaps = details["coverage_gaps"]
        assert len(gaps) > 0, "Should identify coverage gaps"
        assert any("edge" in str(g).lower() for g in gaps), "Should identify edge gap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
