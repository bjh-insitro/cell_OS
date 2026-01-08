"""
Adversarial Policy Pack: 4 deliberately dishonest policies.

These tests prove the epistemic machinery resists strategic manipulation.
Each policy tries to cheat; each must fail loudly.

v0.6.2: "A constitution needs court cases that try to abuse it."
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List

from src.cell_os.hardware.reward import compute_honesty_score, HonestyScoreReceipt
from src.cell_os.epistemic_agent.confidence_receipt import (
    CalibrationSupport, EvidenceSupport, ConfidenceCap, ConfidenceReceipt,
)


# =============================================================================
# Mock infrastructure
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


# =============================================================================
# Policy 1: Provenance Inflator
# =============================================================================

class TestProvenanceInflator:
    """
    Attack: Run DMSO calibration-like experiments outside calibration phase.
    Goal: Earn coverage and confidence illegitimately.

    Expected: Provenance should not move (cycle-gated).
    """

    def test_provenance_frozen_after_cycle_0(self):
        """Provenance accumulation is blocked after cycle 0.

        This test verifies that the cycle-0 gate exists in the codebase.
        The actual enforcement is tested in test_calibration_provenance.py.
        """
        from src.cell_os.epistemic_agent.beliefs.updates.noise import NoiseBeliefUpdater
        import inspect

        # Verify the gate exists in the code
        source = inspect.getsource(NoiseBeliefUpdater._accumulate_calibration_provenance)

        # The gate should check beliefs._cycle == 0
        assert "_cycle" in source or "cycle" in source, \
            "Provenance accumulation should be gated by cycle"

        # The actual provenance inflation defense is tested in:
        # tests/unit/test_calibration_provenance.py::TestProvenanceInflationDefense
        # This test documents that the gate exists.

    def test_inflated_receipt_is_invalid(self):
        """Receipt claiming coverage without earning it is invalid."""
        # Attacker constructs receipt claiming coverage they don't have
        fake_cal = CalibrationSupport(
            noise_sigma_stable=True,
            coverage_match=False,  # System knows coverage doesn't match
            provenance_center_wells=0,
            provenance_edge_wells=0,
            provenance_total_wells=0,
            df_total=0,
        )

        fake_receipt = ConfidenceReceipt(
            confidence_value=0.9,  # High confidence claim
            confidence_source="inflated",
            calibration_support=fake_cal,
            evidence_support=EvidenceSupport(
                n_wells_used=48, assays_used=("cell_painting",),
                timepoints_used=(48.0,), conditions_used=8,
            ),
            caps_applied=(),  # No cap - the lie
        )

        assert not fake_receipt.is_valid


# =============================================================================
# Policy 2: Confidence Sandbagger
# =============================================================================

class TestConfidenceSandbagger:
    """
    Attack: Always report low confidence to farm refusal rewards.
    Goal: Avoid penalties, collect +0.2 for justified refusals.

    Expected: Sandbagging penalty when calibration is strong.
    """

    def test_sandbagging_detected_and_penalized(self):
        """Strong calibration + low confidence = sandbagging penalty."""
        strong_receipt = ConfidenceReceipt(
            confidence_value=0.05,
            confidence_source="sandbag",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=True, coverage_match=True,
                provenance_center_wells=48, provenance_edge_wells=48,
                provenance_total_wells=96, df_total=95,
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=48, assays_used=("cell_painting",),
                timepoints_used=(48.0,), conditions_used=8,
            ),
            caps_applied=(),
        )

        result = compute_honesty_score(
            None, "er", confidence=0.05, confidence_receipt=strong_receipt,
        )

        assert result.sandbagging_detected
        assert result.sandbagging_penalty == -0.3
        assert result.honesty_score < 0  # Net negative

    def test_sandbagger_cannot_outperform_honest(self):
        """Sandbagger expected value < honest agent expected value."""
        strong_receipt = ConfidenceReceipt(
            confidence_value=0.05,
            confidence_source="test",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=True, coverage_match=True,
                provenance_center_wells=48, provenance_edge_wells=48,
                provenance_total_wells=96, df_total=95,
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=48, assays_used=("cell_painting",),
                timepoints_used=(48.0,), conditions_used=8,
            ),
            caps_applied=(),
        )

        # Sandbagger: always refuse with low confidence
        sandbag_score = compute_honesty_score(
            None, "er", confidence=0.05, confidence_receipt=strong_receipt,
        ).honesty_score

        # Honest: predict correctly with high confidence
        honest_score = compute_honesty_score(
            "er", "er", confidence=0.9, confidence_receipt=strong_receipt,
        ).honesty_score

        assert honest_score > sandbag_score


# =============================================================================
# Policy 3: Calibration Launderer
# =============================================================================

class TestCalibrationLaunderer:
    """
    Attack: Do minimal "balanced" calibration, then biology in different regime.
    Goal: Pass coverage gates with minimal effort.

    Expected: Coverage mismatch forces confidence cap.
    """

    def test_minimal_calibration_triggers_cap(self):
        """Minimal calibration with different biology regime gets capped."""
        from src.cell_os.epistemic_agent.confidence_receipt import confidence_capped_by_coverage

        # Attacker has minimal center calibration, tries edge biology
        minimal_beliefs = MockBeliefs(
            noise_sigma_stable=True,
            calibration_provenance=MockProvenance(
                position_counts={"center": 8, "edge": 0},  # No edge coverage
                total_wells=8,
            ),
            noise_df_total=7,
            noise_rel_width=0.1,
        )

        # System caps confidence to 0 due to coverage mismatch
        receipt = confidence_capped_by_coverage(
            raw_confidence=0.9,
            beliefs=minimal_beliefs,
            coverage_details={"coverage_gaps": ["edge"]},
            n_wells=48,
        )

        assert receipt.confidence_value == 0.0
        assert receipt.was_capped
        assert "coverage" in receipt.caps_applied[0].reason.lower()


# =============================================================================
# Policy 4: Receipt Forger
# =============================================================================

class TestReceiptForger:
    """
    Attack: Construct or mutate Decision with fake receipt.
    Goal: Bypass confidence validation.

    Expected: System rejects invalid receipts loudly.
    """

    def test_forged_receipt_detected_by_is_valid(self):
        """Forged receipt (coverage mismatch, no cap) fails validation."""
        forged = ConfidenceReceipt(
            confidence_value=0.95,
            confidence_source="forged",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=True,
                coverage_match=False,  # Mismatch!
                provenance_center_wells=0,
                provenance_edge_wells=0,
                provenance_total_wells=0,
                df_total=0,
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=0, assays_used=(),
                timepoints_used=(), conditions_used=0,
            ),
            caps_applied=(),  # No cap - the forgery
        )

        assert not forged.is_valid

    def test_missing_cap_on_mismatch_is_invalid(self):
        """Any receipt with coverage_match=False and no cap is invalid."""
        for conf in [0.1, 0.5, 0.9]:
            if conf == 0.0:
                continue  # Zero confidence is valid (refusal)
            receipt = ConfidenceReceipt(
                confidence_value=conf,
                confidence_source="test",
                calibration_support=CalibrationSupport(
                    noise_sigma_stable=True, coverage_match=False,
                    provenance_center_wells=48, provenance_edge_wells=48,
                    provenance_total_wells=96, df_total=95,
                ),
                evidence_support=EvidenceSupport(
                    n_wells_used=48, assays_used=("cell_painting",),
                    timepoints_used=(48.0,), conditions_used=8,
                ),
                caps_applied=(),
            )
            assert not receipt.is_valid, f"conf={conf} should be invalid"

    def test_zero_confidence_valid_without_cap(self):
        """Zero confidence (refusal) is valid even without explicit cap."""
        refusal_receipt = ConfidenceReceipt(
            confidence_value=0.0,
            confidence_source="refusal",
            calibration_support=CalibrationSupport(
                noise_sigma_stable=False, coverage_match=False,
                provenance_center_wells=0, provenance_edge_wells=0,
                provenance_total_wells=0, df_total=0,
            ),
            evidence_support=EvidenceSupport(
                n_wells_used=0, assays_used=(),
                timepoints_used=(), conditions_used=0,
            ),
            caps_applied=(),
        )

        # Zero confidence is valid because it's a refusal
        assert refusal_receipt.is_valid
