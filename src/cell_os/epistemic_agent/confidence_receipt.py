"""
ConfidenceReceipt: Structured justification for every confidence value.

v0.6.1: Implements "confidence must be auditable, not just punishable."

Every time the agent emits a confidence, it must attach a structured
justification derived from calibration and evidence, not vibes.

Hard rule: If coverage_match is false, receipt must show a cap or refusal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Mapping, Any
import json


@dataclass(frozen=True)
class CalibrationSupport:
    """Calibration state at confidence computation time.

    Captures whether calibration gates are satisfied and the
    provenance distribution that supports the confidence.
    """
    noise_sigma_stable: bool
    """Is noise sigma within tolerance (gate earned)?"""

    coverage_match: bool
    """Does calibration coverage match experiment positions?"""

    provenance_center_wells: int
    """Center wells used for calibration."""

    provenance_edge_wells: int
    """Edge wells used for calibration."""

    provenance_total_wells: int
    """Total wells used for calibration."""

    df_total: int
    """Degrees of freedom for noise estimate (n_wells - 1)."""

    rel_width: Optional[float] = None
    """Relative width of confidence interval (lower = more stable)."""

    def to_dict(self) -> dict:
        return {
            "noise_sigma_stable": self.noise_sigma_stable,
            "coverage_match": self.coverage_match,
            "provenance_center_wells": self.provenance_center_wells,
            "provenance_edge_wells": self.provenance_edge_wells,
            "provenance_total_wells": self.provenance_total_wells,
            "df_total": self.df_total,
            "rel_width": self.rel_width,
        }

    @classmethod
    def from_beliefs(cls, beliefs, coverage_match: bool) -> "CalibrationSupport":
        """Extract calibration support from BeliefState."""
        prov = beliefs.calibration_provenance
        return cls(
            noise_sigma_stable=beliefs.noise_sigma_stable,
            coverage_match=coverage_match,
            provenance_center_wells=prov.position_counts.get("center", 0),
            provenance_edge_wells=prov.position_counts.get("edge", 0),
            provenance_total_wells=prov.total_wells,
            df_total=beliefs.noise_df_total,
            rel_width=beliefs.noise_rel_width,
        )


@dataclass(frozen=True)
class EvidenceSupport:
    """Evidence basis for confidence.

    Captures what experimental evidence was used to compute confidence.
    """
    n_wells_used: int
    """Total wells contributing to this confidence."""

    assays_used: Tuple[str, ...]
    """Assays that contributed evidence (e.g., "cell_painting", "scrna_seq")."""

    timepoints_used: Tuple[float, ...]
    """Timepoints observed (hours)."""

    conditions_used: int
    """Number of distinct experimental conditions."""

    def to_dict(self) -> dict:
        return {
            "n_wells_used": self.n_wells_used,
            "assays_used": list(self.assays_used),
            "timepoints_used": list(self.timepoints_used),
            "conditions_used": self.conditions_used,
        }

    @classmethod
    def empty(cls) -> "EvidenceSupport":
        """Create empty evidence support (for caps without evidence)."""
        return cls(
            n_wells_used=0,
            assays_used=(),
            timepoints_used=(),
            conditions_used=0,
        )


@dataclass(frozen=True)
class ConfidenceCap:
    """A cap applied to confidence.

    Records when and why confidence was forced lower than the
    raw estimate would suggest.
    """
    reason: str
    """Why the cap was applied (e.g., "coverage_mismatch", "gate_not_earned")."""

    original_value: float
    """Confidence before cap."""

    capped_value: float
    """Confidence after cap."""

    cap_source: str
    """What applied the cap (e.g., "coverage_check", "noise_gate", "manual")."""

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "original_value": self.original_value,
            "capped_value": self.capped_value,
            "cap_source": self.cap_source,
        }


@dataclass(frozen=True)
class ConfidenceReceipt:
    """Full justification for a confidence value.

    Every confidence emission must produce one of these. The receipt
    answers: "Why was confidence X allowed to be X?"

    Hard rule: If coverage_match is false, receipt must show a cap.
    This is enforced by is_valid property.
    """
    confidence_value: float
    """The final confidence value (after any caps)."""

    confidence_source: str
    """How confidence was computed.

    Examples:
    - "posterior_margin": Margin between top two mechanism posteriors
    - "classifier_entropy": 1 - normalized entropy
    - "gate_based_cap": Capped due to gate state
    - "coverage_cap": Capped due to coverage mismatch
    - "refusal": Confidence 0.0 due to refusal
    """

    calibration_support: CalibrationSupport
    """Calibration state at decision time."""

    evidence_support: EvidenceSupport
    """Evidence basis for this confidence."""

    caps_applied: Tuple[ConfidenceCap, ...] = field(default_factory=tuple)
    """Any caps that reduced confidence from raw estimate."""

    raw_confidence: Optional[float] = None
    """Raw confidence before any caps (for audit)."""

    decision_id: Optional[str] = None
    """Link to Decision artifact if applicable."""

    @property
    def is_valid(self) -> bool:
        """Check if confidence is justified by calibration.

        Hard rule: If coverage_match is false, must have a cap.
        """
        if not self.calibration_support.coverage_match:
            # Coverage mismatch: must have cap or be zero (refusal)
            has_cap = len(self.caps_applied) > 0
            is_refused = self.confidence_value == 0.0
            return has_cap or is_refused
        return True

    @property
    def was_capped(self) -> bool:
        """Whether any caps were applied."""
        return len(self.caps_applied) > 0

    @property
    def total_cap_reduction(self) -> float:
        """Total confidence reduction from caps."""
        if not self.caps_applied or self.raw_confidence is None:
            return 0.0
        return self.raw_confidence - self.confidence_value

    def to_dict(self) -> dict:
        return {
            "confidence_value": self.confidence_value,
            "confidence_source": self.confidence_source,
            "calibration_support": self.calibration_support.to_dict(),
            "evidence_support": self.evidence_support.to_dict(),
            "caps_applied": [c.to_dict() for c in self.caps_applied],
            "raw_confidence": self.raw_confidence,
            "decision_id": self.decision_id,
            "is_valid": self.is_valid,
            "was_capped": self.was_capped,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        """Human-readable summary."""
        cap_str = f", caps={len(self.caps_applied)}" if self.was_capped else ""
        valid_str = "" if self.is_valid else " [INVALID]"
        return (
            f"ConfidenceReceipt(value={self.confidence_value:.3f}, "
            f"source={self.confidence_source}, "
            f"coverage={self.calibration_support.coverage_match}"
            f"{cap_str}){valid_str}"
        )

    def __str__(self) -> str:
        return self.summary()


# =============================================================================
# Factory functions for common confidence receipt patterns
# =============================================================================

def confidence_from_posterior(
    confidence_value: float,
    beliefs,
    coverage_match: bool,
    n_wells: int,
    assays: Tuple[str, ...],
    timepoints: Tuple[float, ...],
    conditions: int,
    decision_id: Optional[str] = None,
) -> ConfidenceReceipt:
    """Create receipt for confidence derived from posterior margin.

    This is the standard case: confidence from Bayesian posterior.
    """
    cal_support = CalibrationSupport.from_beliefs(beliefs, coverage_match)
    ev_support = EvidenceSupport(
        n_wells_used=n_wells,
        assays_used=assays,
        timepoints_used=timepoints,
        conditions_used=conditions,
    )

    caps = []

    # Apply coverage cap if needed
    if not coverage_match:
        # Coverage mismatch: cap confidence to 0.0
        caps.append(ConfidenceCap(
            reason="coverage_mismatch",
            original_value=confidence_value,
            capped_value=0.0,
            cap_source="coverage_check",
        ))
        confidence_value = 0.0

    # Apply noise gate cap if needed
    if not beliefs.noise_sigma_stable and confidence_value > 0.5:
        caps.append(ConfidenceCap(
            reason="noise_gate_not_earned",
            original_value=confidence_value,
            capped_value=0.5,
            cap_source="noise_gate",
        ))
        confidence_value = 0.5

    return ConfidenceReceipt(
        confidence_value=confidence_value,
        confidence_source="posterior_margin",
        calibration_support=cal_support,
        evidence_support=ev_support,
        caps_applied=tuple(caps),
        raw_confidence=confidence_value if not caps else caps[0].original_value,
        decision_id=decision_id,
    )


def confidence_from_refusal(
    beliefs,
    refusal_reason: str,
    decision_id: Optional[str] = None,
) -> ConfidenceReceipt:
    """Create receipt for refusal (confidence = 0.0)."""
    cal_support = CalibrationSupport.from_beliefs(beliefs, coverage_match=False)

    return ConfidenceReceipt(
        confidence_value=0.0,
        confidence_source="refusal",
        calibration_support=cal_support,
        evidence_support=EvidenceSupport.empty(),
        caps_applied=(ConfidenceCap(
            reason=refusal_reason,
            original_value=0.0,
            capped_value=0.0,
            cap_source="refusal",
        ),),
        raw_confidence=0.0,
        decision_id=decision_id,
    )


def confidence_capped_by_coverage(
    raw_confidence: float,
    beliefs,
    coverage_details: Mapping[str, Any],
    n_wells: int,
    decision_id: Optional[str] = None,
) -> ConfidenceReceipt:
    """Create receipt when confidence is capped due to coverage mismatch.

    This is the key enforcement point: coverage mismatch MUST produce a cap.
    """
    cal_support = CalibrationSupport.from_beliefs(beliefs, coverage_match=False)
    ev_support = EvidenceSupport(
        n_wells_used=n_wells,
        assays_used=("cell_painting",),
        timepoints_used=(),
        conditions_used=0,
    )

    gap_reason = coverage_details.get("coverage_gaps", ["unknown"])

    return ConfidenceReceipt(
        confidence_value=0.0,  # Coverage mismatch forces zero confidence
        confidence_source="coverage_cap",
        calibration_support=cal_support,
        evidence_support=ev_support,
        caps_applied=(ConfidenceCap(
            reason=f"coverage_mismatch: {gap_reason}",
            original_value=raw_confidence,
            capped_value=0.0,
            cap_source="coverage_check",
        ),),
        raw_confidence=raw_confidence,
        decision_id=decision_id,
    )
