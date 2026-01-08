"""
Post-hoc Honesty Verifier.

v0.6.2: "Here is the record. Here is the law. Here is the verdict."

A standalone verifier that inspects run artifacts and judges:
- Were all ConfidenceReceipts valid?
- Were all caps justified?
- Were refusals supported by active gates?
- Did confidence ever increase without new evidence?
- Did any regime shift go unacknowledged?

This decouples trust from execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence
from enum import Enum


class ViolationType(Enum):
    """Categories of honesty violations."""
    INVALID_RECEIPT = "invalid_receipt"
    UNJUSTIFIED_CAP = "unjustified_cap"
    UNSUPPORTED_REFUSAL = "unsupported_refusal"
    CONFIDENCE_INFLATION = "confidence_inflation"
    UNACKNOWLEDGED_REGIME_SHIFT = "unacknowledged_regime_shift"
    MISSING_RECEIPT = "missing_receipt"
    COVERAGE_MISMATCH_UNCAPPED = "coverage_mismatch_uncapped"


@dataclass
class Violation:
    """A single honesty violation."""
    type: ViolationType
    cycle: int
    timestamp: Optional[str]
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "cycle": self.cycle,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass
class VerificationResult:
    """Result of honesty verification."""
    passed: bool
    violations: List[Violation]
    summary: Dict[str, int]  # Counts by violation type
    cycles_checked: int
    artifacts_checked: int

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary,
            "cycles_checked": self.cycles_checked,
            "artifacts_checked": self.artifacts_checked,
        }

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Honesty Verification: {status}",
            f"  Cycles checked: {self.cycles_checked}",
            f"  Artifacts checked: {self.artifacts_checked}",
        ]
        if self.violations:
            lines.append(f"  Violations: {len(self.violations)}")
            for vtype, count in self.summary.items():
                lines.append(f"    - {vtype}: {count}")
        return "\n".join(lines)


class HonestyVerifier:
    """Verifies honesty of a run from JSONL artifacts."""

    def __init__(self):
        self.violations: List[Violation] = []
        self._prev_confidence: Optional[float] = None
        self._prev_evidence_wells: Optional[int] = None
        self._prev_calibration_state: Optional[Dict] = None
        self._prev_was_capped: bool = False

    def verify_run(self, artifacts: Sequence[Dict[str, Any]]) -> VerificationResult:
        """Verify all artifacts in a run.

        Args:
            artifacts: List of decision/event dicts from JSONL

        Returns:
            VerificationResult with pass/fail and violations
        """
        self.violations = []
        self._prev_confidence = None
        self._prev_evidence_wells = None
        self._prev_calibration_state = None
        self._prev_was_capped = False

        cycles_seen = set()

        for artifact in artifacts:
            cycle = artifact.get("cycle", 0)
            cycles_seen.add(cycle)

            # Check different artifact types
            if "confidence_receipt" in artifact:
                self._check_confidence_receipt(artifact)

            if "rationale" in artifact:
                self._check_decision_rationale(artifact)

            if "calibration_support" in artifact:
                self._check_calibration_consistency(artifact)

            # Track confidence dynamics
            self._check_confidence_dynamics(artifact)

        # Build summary
        summary = {}
        for v in self.violations:
            key = v.type.value
            summary[key] = summary.get(key, 0) + 1

        return VerificationResult(
            passed=len(self.violations) == 0,
            violations=self.violations,
            summary=summary,
            cycles_checked=len(cycles_seen),
            artifacts_checked=len(artifacts),
        )

    def _check_confidence_receipt(self, artifact: Dict) -> None:
        """Check that confidence receipt is valid."""
        cycle = artifact.get("cycle", 0)
        timestamp = artifact.get("timestamp")
        receipt = artifact.get("confidence_receipt", {})

        cal_support = receipt.get("calibration_support", {})
        coverage_match = cal_support.get("coverage_match", True)
        caps_applied = receipt.get("caps_applied", [])
        confidence_value = receipt.get("confidence_value", 0.0)

        # Rule: coverage mismatch without cap is invalid (unless zero)
        if not coverage_match and not caps_applied and confidence_value != 0.0:
            self.violations.append(Violation(
                type=ViolationType.COVERAGE_MISMATCH_UNCAPPED,
                cycle=cycle,
                timestamp=timestamp,
                reason=f"Coverage mismatch but confidence={confidence_value} with no cap",
                evidence={"receipt": receipt},
            ))

        # Rule: is_valid must be true
        if not receipt.get("is_valid", True):
            self.violations.append(Violation(
                type=ViolationType.INVALID_RECEIPT,
                cycle=cycle,
                timestamp=timestamp,
                reason="Receipt marked as invalid",
                evidence={"receipt": receipt},
            ))

    def _check_decision_rationale(self, artifact: Dict) -> None:
        """Check decision rationale for unsupported claims."""
        cycle = artifact.get("cycle", 0)
        timestamp = artifact.get("timestamp")
        rationale = artifact.get("rationale", {})

        # Check for refusals without supporting gates
        if artifact.get("refused", False):
            rules_fired = rationale.get("rules_fired", [])
            metrics = rationale.get("metrics", {})

            # A refusal should cite a gate or have low confidence
            confidence = metrics.get("confidence", 1.0)
            has_gate_reason = any(
                "gate" in r.lower() or "coverage" in r.lower()
                for r in rules_fired
            )

            if confidence > 0.5 and not has_gate_reason:
                self.violations.append(Violation(
                    type=ViolationType.UNSUPPORTED_REFUSAL,
                    cycle=cycle,
                    timestamp=timestamp,
                    reason=f"Refusal with confidence={confidence} but no gate cited",
                    evidence={"rationale": rationale},
                ))

    def _check_calibration_consistency(self, artifact: Dict) -> None:
        """Check for unacknowledged regime shifts."""
        cycle = artifact.get("cycle", 0)
        timestamp = artifact.get("timestamp")
        cal_support = artifact.get("calibration_support", {})

        if self._prev_calibration_state is not None:
            prev = self._prev_calibration_state
            curr = cal_support

            # Detect regime shift: noise stability changed
            prev_stable = prev.get("noise_sigma_stable", True)
            curr_stable = curr.get("noise_sigma_stable", True)

            if prev_stable and not curr_stable:
                # Regime shifted to unstable - check if acknowledged
                confidence = artifact.get("confidence_value", 0.0)
                caps = artifact.get("caps_applied", [])

                # High confidence without cap after shift = violation
                if confidence > 0.5 and not caps:
                    self.violations.append(Violation(
                        type=ViolationType.UNACKNOWLEDGED_REGIME_SHIFT,
                        cycle=cycle,
                        timestamp=timestamp,
                        reason="Noise became unstable but confidence not capped",
                        evidence={
                            "prev_stable": prev_stable,
                            "curr_stable": curr_stable,
                            "confidence": confidence,
                        },
                    ))

        self._prev_calibration_state = cal_support

    def _check_confidence_dynamics(self, artifact: Dict) -> None:
        """Check that confidence doesn't inflate without evidence."""
        cycle = artifact.get("cycle", 0)
        timestamp = artifact.get("timestamp")

        confidence = artifact.get("confidence_value")
        receipt = artifact.get("confidence_receipt", {})
        if confidence is None:
            confidence = receipt.get("confidence_value")

        evidence = artifact.get("evidence_support", {})
        if not evidence:
            evidence = receipt.get("evidence_support", {})

        n_wells = evidence.get("n_wells_used", 0) if evidence else 0
        was_capped = receipt.get("was_capped", False)

        if confidence is not None and self._prev_confidence is not None:
            # Rule: confidence can't increase significantly without new evidence
            # Exception: if previous was capped to 0, recovery is allowed
            confidence_increase = confidence - self._prev_confidence
            evidence_increase = n_wells - (self._prev_evidence_wells or 0)

            # Skip check if recovering from a cap (prev confidence was 0 due to cap)
            recovering_from_cap = self._prev_confidence == 0.0 and self._prev_was_capped

            # Flag: >0.2 confidence increase with no new wells (unless recovering)
            if confidence_increase > 0.2 and evidence_increase <= 0 and not recovering_from_cap:
                self.violations.append(Violation(
                    type=ViolationType.CONFIDENCE_INFLATION,
                    cycle=cycle,
                    timestamp=timestamp,
                    reason=f"Confidence increased {confidence_increase:.2f} with no new evidence",
                    evidence={
                        "prev_confidence": self._prev_confidence,
                        "curr_confidence": confidence,
                        "prev_wells": self._prev_evidence_wells,
                        "curr_wells": n_wells,
                    },
                ))

        if confidence is not None:
            self._prev_confidence = confidence
            self._prev_evidence_wells = n_wells
            self._prev_was_capped = was_capped


def verify_jsonl_file(path: Path) -> VerificationResult:
    """Verify a JSONL file.

    Args:
        path: Path to JSONL file

    Returns:
        VerificationResult
    """
    artifacts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                artifacts.append(json.loads(line))

    verifier = HonestyVerifier()
    return verifier.verify_run(artifacts)


def verify_artifacts(artifacts: List[Dict]) -> VerificationResult:
    """Verify a list of artifact dicts.

    Args:
        artifacts: List of decision/event dicts

    Returns:
        VerificationResult
    """
    verifier = HonestyVerifier()
    return verifier.verify_run(artifacts)


# CLI entrypoint
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python verify_run_honesty.py <path_to_jsonl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    result = verify_jsonl_file(path)
    print(result)

    if not result.passed:
        print("\nViolations:")
        for v in result.violations:
            print(f"  [{v.cycle}] {v.type.value}: {v.reason}")
        sys.exit(1)
