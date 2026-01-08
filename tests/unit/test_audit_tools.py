"""
Tests for audit tools: HonestyVerifier and NarrativeGenerator.

v0.6.2: "Here is the record. Here is the law. Here is the verdict."
"""

import pytest
from src.cell_os.audit import (
    HonestyVerifier,
    verify_artifacts,
    ViolationType,
    generate_narrative,
)


# =============================================================================
# Test fixtures: sample artifacts
# =============================================================================

def make_clean_artifact(cycle: int, confidence: float = 0.8) -> dict:
    """Create a clean artifact with valid receipt."""
    return {
        "cycle": cycle,
        "timestamp": f"2024-01-01T00:{cycle:02d}:00Z",
        "confidence_receipt": {
            "confidence_value": confidence,
            "confidence_source": "posterior_margin",
            "is_valid": True,
            "was_capped": False,
            "caps_applied": [],
            "calibration_support": {
                "noise_sigma_stable": True,
                "coverage_match": True,
                "provenance_center_wells": 48,
                "provenance_edge_wells": 48,
                "provenance_total_wells": 96,
            },
            "evidence_support": {
                "n_wells_used": 48,
                "assays_used": ["cell_painting"],
                "conditions_used": 8,
            },
        },
    }


def make_capped_artifact(cycle: int, raw_conf: float = 0.9) -> dict:
    """Create artifact with legitimately capped confidence."""
    return {
        "cycle": cycle,
        "confidence_receipt": {
            "confidence_value": 0.0,
            "confidence_source": "coverage_cap",
            "is_valid": True,
            "was_capped": True,
            "caps_applied": [
                {"reason": "coverage_mismatch", "original_value": raw_conf, "capped_value": 0.0}
            ],
            "calibration_support": {
                "noise_sigma_stable": True,
                "coverage_match": False,
                "provenance_center_wells": 48,
                "provenance_edge_wells": 0,
                "provenance_total_wells": 48,
            },
            "evidence_support": {"n_wells_used": 48},
        },
    }


def make_invalid_artifact(cycle: int) -> dict:
    """Create artifact with invalid receipt (coverage mismatch, no cap)."""
    return {
        "cycle": cycle,
        "confidence_receipt": {
            "confidence_value": 0.9,
            "confidence_source": "forged",
            "is_valid": False,
            "was_capped": False,
            "caps_applied": [],
            "calibration_support": {
                "noise_sigma_stable": True,
                "coverage_match": False,  # Mismatch!
                "provenance_total_wells": 96,
            },
            "evidence_support": {"n_wells_used": 48},
        },
    }


# =============================================================================
# HonestyVerifier tests
# =============================================================================

class TestHonestyVerifier:
    """Tests for the post-hoc honesty verifier."""

    def test_clean_run_passes(self):
        """Clean run with valid receipts passes verification."""
        artifacts = [make_clean_artifact(i, 0.5 + i * 0.1) for i in range(3)]

        result = verify_artifacts(artifacts)

        assert result.passed
        assert len(result.violations) == 0
        assert result.cycles_checked == 3

    def test_invalid_receipt_caught(self):
        """Invalid receipt triggers violation."""
        artifacts = [
            make_clean_artifact(0),
            make_invalid_artifact(1),
            make_clean_artifact(2),
        ]

        result = verify_artifacts(artifacts)

        assert not result.passed
        assert len(result.violations) >= 1
        assert any(v.type == ViolationType.INVALID_RECEIPT for v in result.violations)

    def test_coverage_mismatch_without_cap_caught(self):
        """Coverage mismatch without cap triggers violation."""
        artifacts = [{
            "cycle": 1,
            "confidence_receipt": {
                "confidence_value": 0.85,
                "is_valid": True,  # Even if marked valid, verifier checks
                "was_capped": False,
                "caps_applied": [],
                "calibration_support": {
                    "coverage_match": False,  # Mismatch!
                },
            },
        }]

        result = verify_artifacts(artifacts)

        assert not result.passed
        violations = [v for v in result.violations
                      if v.type == ViolationType.COVERAGE_MISMATCH_UNCAPPED]
        assert len(violations) >= 1

    def test_legitimate_cap_passes(self):
        """Legitimately capped confidence passes verification."""
        artifacts = [
            make_clean_artifact(0),
            make_capped_artifact(1),
            make_clean_artifact(2),
        ]

        result = verify_artifacts(artifacts)

        assert result.passed

    def test_confidence_inflation_caught(self):
        """Confidence increasing without new evidence is caught."""
        artifacts = [
            {
                "cycle": 0,
                "confidence_receipt": {
                    "confidence_value": 0.5,
                    "evidence_support": {"n_wells_used": 48},
                    "calibration_support": {"coverage_match": True},
                    "caps_applied": [],
                    "is_valid": True,
                },
            },
            {
                "cycle": 1,
                "confidence_receipt": {
                    "confidence_value": 0.9,  # +0.4 jump
                    "evidence_support": {"n_wells_used": 48},  # Same wells
                    "calibration_support": {"coverage_match": True},
                    "caps_applied": [],
                    "is_valid": True,
                },
            },
        ]

        result = verify_artifacts(artifacts)

        assert not result.passed
        inflation_violations = [v for v in result.violations
                                if v.type == ViolationType.CONFIDENCE_INFLATION]
        assert len(inflation_violations) >= 1

    def test_regime_shift_acknowledged_passes(self):
        """Regime shift with appropriate cap passes."""
        artifacts = [
            {
                "cycle": 0,
                "calibration_support": {"noise_sigma_stable": True},
                "confidence_value": 0.8,
                "caps_applied": [],
            },
            {
                "cycle": 1,
                "calibration_support": {"noise_sigma_stable": False},  # Shift!
                "confidence_value": 0.3,  # Appropriately low
                "caps_applied": [{"reason": "noise_unstable"}],
            },
        ]

        result = verify_artifacts(artifacts)

        # Should pass because confidence was capped
        assert result.passed


# =============================================================================
# NarrativeGenerator tests
# =============================================================================

class TestNarrativeGenerator:
    """Tests for the run narrative generator."""

    def test_generates_cycle_records(self):
        """Narrative includes all cycles."""
        artifacts = [make_clean_artifact(i) for i in range(5)]

        narrative = generate_narrative(artifacts)

        assert narrative.total_cycles == 5
        assert len(narrative.cycles) == 5

    def test_captures_caps(self):
        """Narrative captures cap events."""
        artifacts = [
            make_clean_artifact(0),
            make_capped_artifact(1),
            make_clean_artifact(2),
        ]

        narrative = generate_narrative(artifacts)

        assert narrative.total_caps == 1
        assert narrative.cycles[1].was_capped
        assert "coverage" in narrative.cycles[1].cap_reasons[0].lower()

    def test_captures_refusals(self):
        """Narrative captures refusal events."""
        artifacts = [
            make_clean_artifact(0),
            {
                "cycle": 1,
                "refused": True,
                "refusal_reason": "insufficient_calibration",
                "refusal_justified": True,
            },
        ]

        narrative = generate_narrative(artifacts)

        assert narrative.total_refusals == 1
        assert narrative.cycles[1].refused

    def test_tracks_calibration_state(self):
        """Narrative tracks calibration state per cycle."""
        artifacts = [make_clean_artifact(0)]

        narrative = generate_narrative(artifacts)

        record = narrative.cycles[0]
        assert record.noise_sigma_stable is True
        assert record.coverage_match is True
        assert record.calibration_wells == 96

    def test_to_yaml_includes_summary(self):
        """YAML output includes summary section."""
        artifacts = [make_clean_artifact(i) for i in range(3)]

        narrative = generate_narrative(artifacts)
        yaml_output = narrative.to_yaml()

        assert "summary:" in yaml_output
        assert "total_cycles:" in yaml_output
        assert "verdict:" in yaml_output

    def test_verdict_honest_with_constraints(self):
        """Verdict is HONEST_WITH_CONSTRAINTS when caps applied."""
        artifacts = [make_capped_artifact(0)]

        narrative = generate_narrative(artifacts)

        assert narrative.verdict == "HONEST_WITH_CONSTRAINTS"

    def test_verdict_clean(self):
        """Verdict is CLEAN when no caps or refusals."""
        artifacts = [make_clean_artifact(i) for i in range(3)]

        narrative = generate_narrative(artifacts)

        assert narrative.verdict == "CLEAN"
