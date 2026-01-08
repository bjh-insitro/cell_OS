"""
Regime Shift Trials: Test honesty under shifting worlds.

v0.6.2: "Can the system stay honest when the ground moves?"

These trials test that the epistemic machinery forces recalibration
and confidence downgrades when the world changes.
"""

import pytest
from dataclasses import dataclass
from typing import List, Dict, Any

from src.cell_os.epistemic_agent.confidence_receipt import (
    CalibrationSupport, EvidenceSupport, ConfidenceCap, ConfidenceReceipt,
    confidence_from_posterior, confidence_capped_by_coverage,
)
from src.cell_os.hardware.reward import compute_honesty_score


# =============================================================================
# Mock infrastructure for regime shifts
# =============================================================================

@dataclass
class MockProvenance:
    position_counts: dict
    total_wells: int


@dataclass
class MockBeliefs:
    noise_sigma_stable: bool
    calibration_provenance: MockProvenance
    noise_df_total: int
    noise_rel_width: float
    _cycle: int = 1


def make_calibrated_beliefs(center: int = 48, edge: int = 48) -> MockBeliefs:
    """Create beliefs with calibration from specified position distribution."""
    return MockBeliefs(
        noise_sigma_stable=True,
        calibration_provenance=MockProvenance(
            position_counts={"center": center, "edge": edge},
            total_wells=center + edge,
        ),
        noise_df_total=center + edge - 1,
        noise_rel_width=0.05,
    )


# =============================================================================
# Trial 1: Drift after calibration
# =============================================================================

class TestDriftAfterCalibration:
    """
    Scenario:
    - Cycle 0: calibrate clean
    - Cycle 1-2: normal biology, build confidence
    - Cycle 3: world changes (noise increases, baseline shifts)

    Expected: High confidence after drift is penalized.
    """

    def test_pre_drift_confidence_allowed(self):
        """Before drift, high confidence with good calibration is allowed."""
        beliefs = make_calibrated_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        assert receipt.is_valid
        assert receipt.confidence_value == 0.85
        assert not receipt.was_capped

    def test_post_drift_requires_recalibration_signal(self):
        """After drift detected, confidence must be capped or refused."""
        beliefs = make_calibrated_beliefs()

        # Simulate drift detection: noise_sigma becomes unstable
        beliefs.noise_sigma_stable = False
        beliefs.noise_rel_width = 0.4  # Widened uncertainty

        receipt = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # Noise gate cap should trigger
        assert receipt.was_capped
        assert receipt.confidence_value <= 0.5  # Capped by noise gate

        # Cap reason should explain why
        noise_caps = [c for c in receipt.caps_applied if "noise" in c.reason.lower()]
        assert len(noise_caps) >= 1

    def test_high_confidence_after_drift_penalized(self):
        """Agent claiming high confidence after drift is penalized."""
        beliefs = make_calibrated_beliefs()
        beliefs.noise_sigma_stable = False  # Drift detected

        # Agent tries to claim high confidence anyway (ignoring drift)
        # In real system, factory would cap it. Here we test scoring.

        # Construct a receipt that SHOULD have been capped but wasn't
        # (simulating a bug or bypass)
        uncapped_receipt = ConfidenceReceipt(
            confidence_value=0.9,
            confidence_source="ignored_drift",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=False,  # Drift!
                coverage_match=True,
                provenance_center_wells=48,
                provenance_edge_wells=48,
                provenance_total_wells=96,
                df_total=95,
                rel_width=0.4,  # High uncertainty
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=48,
                assays_used=("cell_painting",),
                timepoints_used=(48.0,),
                conditions_used=8,
            ),
            caps_applied=(),  # No cap - the problem
        )

        # High confidence with unstable noise should score poorly
        result = compute_honesty_score(
            "er", "mito",  # Wrong prediction
            confidence=0.9,
            confidence_receipt=uncapped_receipt,
        )

        # Wrong + high confidence = -1.0
        assert result.honesty_score == -1.0

    def test_refusal_after_drift_justified(self):
        """Refusing after drift detection is justified and rewarded."""
        beliefs = make_calibrated_beliefs()
        beliefs.noise_sigma_stable = False  # Drift

        receipt = confidence_from_posterior(
            confidence_value=0.1,  # Low confidence due to drift
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        result = compute_honesty_score(
            None, "er",  # Refusal
            confidence=0.1,
            confidence_receipt=receipt,
        )

        assert result.refusal_justified
        # Weak calibration justifies low confidence, no sandbagging
        assert not result.sandbagging_detected


# =============================================================================
# Trial 2: Position regime flip
# =============================================================================

class TestPositionRegimeFlip:
    """
    Scenario:
    - Calibrate balanced (center + edge)
    - Run center-heavy biology
    - Flip to edge-heavy biology without re-calibration

    Expected: Coverage rules must block or cap.
    """

    def test_center_only_calibration_blocks_edge_biology(self):
        """Center-only calibration cannot support edge biology."""
        beliefs = make_calibrated_beliefs(center=48, edge=0)  # No edge

        # Agent tries edge biology
        receipt = confidence_capped_by_coverage(
            raw_confidence=0.9,
            beliefs=beliefs,
            coverage_details={"coverage_gaps": ["edge"]},
            n_wells=48,
        )

        assert receipt.confidence_value == 0.0
        assert receipt.was_capped
        assert "edge" in str(receipt.caps_applied[0].reason).lower()

    def test_edge_only_calibration_blocks_center_biology(self):
        """Edge-only calibration cannot support center biology."""
        beliefs = make_calibrated_beliefs(center=0, edge=48)  # No center

        receipt = confidence_capped_by_coverage(
            raw_confidence=0.85,
            beliefs=beliefs,
            coverage_details={"coverage_gaps": ["center"]},
            n_wells=48,
        )

        assert receipt.confidence_value == 0.0
        assert receipt.was_capped

    def test_balanced_calibration_allows_any_position(self):
        """Balanced calibration supports both center and edge biology."""
        beliefs = make_calibrated_beliefs(center=48, edge=48)

        # Center biology
        receipt_center = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        assert receipt_center.is_valid
        assert not receipt_center.was_capped

    def test_regime_flip_receipt_explains_gap(self):
        """Receipt must explain which positions are missing."""
        beliefs = make_calibrated_beliefs(center=48, edge=0)

        receipt = confidence_capped_by_coverage(
            raw_confidence=0.9,
            beliefs=beliefs,
            coverage_details={"coverage_gaps": ["edge"]},
            n_wells=48,
        )

        # Cap reason must mention the specific gap
        cap_reasons = " ".join(c.reason for c in receipt.caps_applied)
        assert "edge" in cap_reasons.lower()


# =============================================================================
# Trial 3: Calibration poisoning
# =============================================================================

class TestCalibrationPoisoning:
    """
    Scenario:
    - Cycle 0 calibration includes biased/corrupted wells
    - Noise estimates are wrong

    Expected: Agent must fail honesty (refuse/downgrade).
    """

    def test_unstable_noise_from_poisoning(self):
        """Poisoned calibration leads to unstable noise gate."""
        # Poisoning results in failed noise stability
        beliefs = MockBeliefs(
            noise_sigma_stable=False,  # Gate not earned
            calibration_provenance=MockProvenance(
                position_counts={"center": 48, "edge": 48},
                total_wells=96,
            ),
            noise_df_total=95,
            noise_rel_width=0.6,  # Very wide - unreliable
        )

        receipt = confidence_from_posterior(
            confidence_value=0.8,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # Must be capped due to noise gate failure
        assert receipt.was_capped
        assert receipt.confidence_value <= 0.5

    def test_high_rel_width_signals_poisoning(self):
        """High rel_width in receipt signals unreliable calibration."""
        beliefs = make_calibrated_beliefs()
        beliefs.noise_rel_width = 0.5  # Suspicious

        receipt = confidence_from_posterior(
            confidence_value=0.7,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # rel_width is captured in receipt for audit
        assert receipt.calibration_support.rel_width == 0.5

    def test_poisoning_makes_confident_prediction_costly(self):
        """Confident prediction with poisoned calibration costs more if wrong."""
        beliefs = MockBeliefs(
            noise_sigma_stable=False,  # Poisoned
            calibration_provenance=MockProvenance(
                position_counts={"center": 48, "edge": 48},
                total_wells=96,
            ),
            noise_df_total=95,
            noise_rel_width=0.5,
        )

        # Agent ignores poisoning, predicts confidently
        result = compute_honesty_score(
            "er", "mito",  # Wrong
            confidence=0.8,
        )

        # Wrong + high confidence = maximum penalty
        assert result.honesty_score == -1.0
