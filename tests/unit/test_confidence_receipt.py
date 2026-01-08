"""
Adversarial tests for ConfidenceReceipt.

v0.6.1: "Confidence must be auditable, not just punishable."

These tests prove the system cannot lie about confidence justification.
"""

import pytest
from dataclasses import dataclass
from typing import Optional

from src.cell_os.epistemic_agent.confidence_receipt import (
    CalibrationSupport,
    EvidenceSupport,
    ConfidenceCap,
    ConfidenceReceipt,
    confidence_from_posterior,
    confidence_from_refusal,
    confidence_capped_by_coverage,
)


# =============================================================================
# Mock beliefs for testing
# =============================================================================

@dataclass
class MockCalibrationProvenance:
    position_counts: dict
    total_wells: int


@dataclass
class MockBeliefs:
    noise_sigma_stable: bool
    calibration_provenance: MockCalibrationProvenance
    noise_df_total: int
    noise_rel_width: Optional[float]
    _cycle: int = 1


def make_strong_beliefs() -> MockBeliefs:
    """Beliefs with strong calibration (gates earned)."""
    return MockBeliefs(
        noise_sigma_stable=True,
        calibration_provenance=MockCalibrationProvenance(
            position_counts={"center": 48, "edge": 48},
            total_wells=96,
        ),
        noise_df_total=95,
        noise_rel_width=0.05,
    )


def make_weak_beliefs() -> MockBeliefs:
    """Beliefs with weak calibration (gates not earned)."""
    return MockBeliefs(
        noise_sigma_stable=False,
        calibration_provenance=MockCalibrationProvenance(
            position_counts={"center": 4, "edge": 4},
            total_wells=8,
        ),
        noise_df_total=7,
        noise_rel_width=0.5,
    )


# =============================================================================
# Test 1: Confidence requires support
# =============================================================================

class TestConfidenceRequiresSupport:
    """
    In a regime where calibration is strong and evidence is rich,
    confidence must be allowed to rise above a threshold.

    This tests the POSITIVE case: good behavior is not punished.
    """

    def test_strong_calibration_allows_high_confidence(self):
        """Strong calibration + rich evidence → confidence allowed to rise."""
        beliefs = make_strong_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(24.0, 48.0),
            conditions=8,
        )

        # High confidence should be allowed
        assert receipt.confidence_value == 0.85
        assert receipt.is_valid
        assert not receipt.was_capped
        assert receipt.confidence_source == "posterior_margin"

    def test_receipt_captures_calibration_support(self):
        """Receipt must show the calibration that justifies confidence."""
        beliefs = make_strong_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.9,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=96,
            assays=("cell_painting", "scrna_seq"),
            timepoints=(24.0, 48.0, 72.0),
            conditions=12,
        )

        # Calibration support must be captured
        cal = receipt.calibration_support
        assert cal.noise_sigma_stable is True
        assert cal.coverage_match is True
        assert cal.provenance_total_wells == 96
        assert cal.df_total == 95

        # Evidence support must be captured
        ev = receipt.evidence_support
        assert ev.n_wells_used == 96
        assert "cell_painting" in ev.assays_used
        assert ev.conditions_used == 12

    def test_no_cap_means_no_cap_record(self):
        """When confidence is earned, no caps should be recorded."""
        beliefs = make_strong_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.95,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=96,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=16,
        )

        assert receipt.caps_applied == ()
        assert receipt.total_cap_reduction == 0.0


# =============================================================================
# Test 2: Confidence is capped on mismatch
# =============================================================================

class TestConfidenceIsCappedOnMismatch:
    """
    Coverage mismatch present, classifier tries to be confident,
    system caps it and records cap reason.

    This is the ENFORCEMENT case: lies are caught.
    """

    def test_coverage_mismatch_forces_zero_confidence(self):
        """Coverage mismatch → confidence capped to 0.0."""
        beliefs = make_strong_beliefs()

        # Agent tries to claim 0.9 confidence but coverage doesn't match
        receipt = confidence_from_posterior(
            confidence_value=0.9,
            beliefs=beliefs,
            coverage_match=False,  # MISMATCH
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # System must cap to 0.0
        assert receipt.confidence_value == 0.0
        assert receipt.is_valid  # Valid because cap was applied
        assert receipt.was_capped

    def test_cap_records_original_value(self):
        """Cap must record what the agent tried to claim."""
        beliefs = make_strong_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=False,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        assert receipt.raw_confidence == 0.85
        assert len(receipt.caps_applied) >= 1

        cap = receipt.caps_applied[0]
        assert cap.original_value == 0.85
        assert cap.capped_value == 0.0
        assert "coverage" in cap.reason.lower()

    def test_invalid_receipt_if_mismatch_without_cap(self):
        """Receipt is INVALID if coverage mismatch but no cap recorded."""
        # Manually construct an invalid receipt (bypassing factories)
        cal_support = CalibrationSupport(
            noise_sigma_stable=True,
            coverage_match=False,  # MISMATCH
            provenance_center_wells=48,
            provenance_edge_wells=48,
            provenance_total_wells=96,
            df_total=95,
        )
        ev_support = EvidenceSupport(
            n_wells_used=48,
            assays_used=("cell_painting",),
            timepoints_used=(48.0,),
            conditions_used=8,
        )

        # Try to sneak through high confidence without cap
        invalid_receipt = ConfidenceReceipt(
            confidence_value=0.9,  # High confidence
            confidence_source="posterior_margin",
            calibration_support=cal_support,
            evidence_support=ev_support,
            caps_applied=(),  # NO CAP - this is the lie
        )

        # System catches the lie
        assert not invalid_receipt.is_valid

    def test_noise_gate_caps_confidence(self):
        """Unstable noise gate → confidence capped to 0.5."""
        beliefs = make_weak_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.8,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=8,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=2,
        )

        # Noise gate not earned → capped to 0.5
        assert receipt.confidence_value == 0.5
        assert receipt.was_capped

        # Find the noise gate cap
        noise_caps = [c for c in receipt.caps_applied if "noise" in c.reason.lower()]
        assert len(noise_caps) == 1
        assert noise_caps[0].cap_source == "noise_gate"


# =============================================================================
# Test 3: Confidence cannot increase without new evidence
# =============================================================================

class TestConfidenceCannotIncreaseWithoutNewEvidence:
    """
    Epistemic monotonicity: Run identical experiment twice,
    confidence shouldn't rise unless evidence changes.

    This prevents "confidence inflation" attacks.
    """

    def test_same_evidence_same_confidence(self):
        """Identical evidence → identical confidence bounds."""
        beliefs = make_strong_beliefs()

        # First receipt
        receipt1 = confidence_from_posterior(
            confidence_value=0.7,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # Second receipt with same evidence
        receipt2 = confidence_from_posterior(
            confidence_value=0.7,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=8,
        )

        # Same evidence → same confidence
        assert receipt1.confidence_value == receipt2.confidence_value
        assert receipt1.evidence_support.n_wells_used == receipt2.evidence_support.n_wells_used

    def test_more_evidence_allows_higher_confidence(self):
        """More evidence → higher confidence is justified."""
        beliefs = make_strong_beliefs()

        # Receipt with sparse evidence
        receipt_sparse = confidence_from_posterior(
            confidence_value=0.6,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=16,
            assays=("cell_painting",),
            timepoints=(48.0,),
            conditions=4,
        )

        # Receipt with rich evidence
        receipt_rich = confidence_from_posterior(
            confidence_value=0.85,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=96,
            assays=("cell_painting", "scrna_seq"),
            timepoints=(24.0, 48.0, 72.0),
            conditions=16,
        )

        # More evidence justifies higher confidence
        assert receipt_rich.evidence_support.n_wells_used > receipt_sparse.evidence_support.n_wells_used
        assert receipt_rich.evidence_support.conditions_used > receipt_sparse.evidence_support.conditions_used
        # Both are valid because evidence supports claimed confidence
        assert receipt_sparse.is_valid
        assert receipt_rich.is_valid

    def test_evidence_audit_trail_preserved(self):
        """Receipt serialization preserves full audit trail."""
        beliefs = make_strong_beliefs()

        receipt = confidence_from_posterior(
            confidence_value=0.75,
            beliefs=beliefs,
            coverage_match=True,
            n_wells=48,
            assays=("cell_painting", "scrna_seq"),
            timepoints=(24.0, 48.0),
            conditions=8,
            decision_id="decision_001",
        )

        # Serialize and check
        d = receipt.to_dict()

        assert d["confidence_value"] == 0.75
        assert d["decision_id"] == "decision_001"
        assert d["calibration_support"]["noise_sigma_stable"] is True
        assert d["evidence_support"]["n_wells_used"] == 48
        assert "cell_painting" in d["evidence_support"]["assays_used"]
        assert d["is_valid"] is True


# =============================================================================
# Refusal receipt tests
# =============================================================================

class TestRefusalReceipts:
    """Tests for refusal receipts (confidence = 0.0)."""

    def test_refusal_is_always_valid(self):
        """Refusal (confidence 0.0) is always a valid choice."""
        beliefs = make_weak_beliefs()

        receipt = confidence_from_refusal(
            beliefs=beliefs,
            refusal_reason="insufficient_calibration",
            decision_id="decision_002",
        )

        assert receipt.confidence_value == 0.0
        assert receipt.confidence_source == "refusal"
        assert receipt.is_valid
        assert receipt.was_capped  # Refusal is recorded as a cap

    def test_refusal_records_reason(self):
        """Refusal must record why it was refused."""
        beliefs = make_weak_beliefs()

        receipt = confidence_from_refusal(
            beliefs=beliefs,
            refusal_reason="coverage_gap_edge_wells",
        )

        assert len(receipt.caps_applied) == 1
        cap = receipt.caps_applied[0]
        assert cap.reason == "coverage_gap_edge_wells"
        assert cap.cap_source == "refusal"
