"""
Epistemic Invariant Exceptions

These are not bugs. These are violations of the Seven Covenants.
They should never be caught and handled - they should crash the system
and force a fix.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


# Type aliases for execution integrity
IntegritySeverity = Literal["none", "warning", "halt", "fatal"]
IntegrityAction = Literal["none", "continue", "cautious", "soft_halt", "hard_halt", "diagnose"]


@dataclass
class IntegrityViolation:
    """
    A single execution integrity violation with evidence.

    This is a fact: a measurable signal that something went wrong.
    The violation does NOT encode what action to take - that's for policy.

    Examples:
    - "anchor_position_mismatch": Anchors appear in wrong wells
    - "replicate_clustering_failed": Replicates don't cluster as expected
    - "dose_monotonicity_broken": Dose-response is inverted or non-monotonic
    """
    code: str  # Machine-readable violation type
    severity: IntegritySeverity  # Local severity for this violation
    summary: str  # Human-readable one-liner
    evidence: Dict[str, Any] = field(default_factory=dict)
    supporting_conditions: List[str] = field(default_factory=list)


@dataclass
class ExecutionIntegrityState:
    """
    Current state of execution integrity tracking.

    This is the single source of truth for "do we trust the plate map?"

    Design principles:
    - Violations are facts (measurable signals)
    - Severity is aggregate judgment (based on violations)
    - Action is policy recommendation (not hardcoded)
    - Hysteresis prevents noise-triggered halts
    """
    suspect: bool = False
    severity: IntegritySeverity = "none"
    recommended_action: IntegrityAction = "none"
    violations: List[IntegrityViolation] = field(default_factory=list)

    # Hysteresis: prevent false alarms from noisy signals
    last_check_cycle: Optional[int] = None
    consecutive_bad_checks: int = 0
    consecutive_good_checks: int = 0

    # Recovery protocol tracking
    diagnosis_in_progress: bool = False
    last_diagnostic_template: Optional[str] = None
    last_diagnostic_result: Optional[str] = None  # "cleared" | "confirmed" | "inconclusive"


class EpistemicInvariantError(RuntimeError):
    """Base class for epistemic invariant failures.

    When you see this, something violated the EPISTEMIC_CHARTER.md.
    Do not catch and continue. Fix the violation.
    """
    covenant_id: str


@dataclass
class DecisionReceiptInvariantError(EpistemicInvariantError):
    """Raised when choose_next() returns without a valid decision receipt.

    Covenant 6: Every Decision Must Have a Receipt.

    All template selection paths must write a complete decision receipt with:
    - template, forced, trigger, regime, gate_state (always)
    - enforcement_layer (if forced or abort)
    - attempted_template, calibration_plan (if abort)

    This error means a code path bypassed _finalize_selection() or
    _set_last_decision() without proper provenance.
    """
    message: str
    receipt_path: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)
    covenant_id: str = "C6"
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (
                self.message,
                self.receipt_path,
                self.missing_fields,
                self.covenant_id,
                self.details,
            ),
        )


@dataclass
class BeliefLedgerInvariantError(EpistemicInvariantError):
    """Raised when beliefs mutate without corresponding evidence events.

    Covenant 7: We Optimize for Causal Discoverability, Not Throughput.

    All belief updates must call _set() to emit evidence events.
    Direct mutation (beliefs.field = value) loses provenance and makes
    causal reconstruction impossible.

    This error means code bypassed _set() and mutated beliefs directly.
    """
    message: str
    mutated_fields: List[str] = field(default_factory=list)
    evidence_event_ids: List[str] = field(default_factory=list)
    covenant_id: str = "C7"
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (
                self.message,
                self.mutated_fields,
                self.evidence_event_ids,
                self.covenant_id,
                self.details,
            ),
        )


@dataclass
class InvalidDesignError(EpistemicInvariantError):
    """Raised when agent proposes a design that violates lab constraints.

    Covenant 5: Agent Must Refuse What It Cannot Guarantee.

    The agent must refuse to execute designs that:
    - Violate physical constraints (invalid well positions, negative doses)
    - Violate safety constraints (toxic concentrations, dangerous combinations)
    - Cannot be expressed in the design schema (approximations lose information)

    This error triggers a refusal with a decision receipt pointing to:
    - The invalid design artifact
    - The specific constraint violation
    - Whether the agent should retry or needs human intervention

    Structured fields (no parsing needed):
    - violation_code: Machine-readable violation type
    - design_id: Design identifier from proposal
    - rejected_path: Path to _REJECTED artifact
    - reason_path: Path to _REASON artifact
    - validator_mode: "strict" or "lenient" or "placeholder"
    - audit_degraded: True if refusal artifacts failed to write
    - audit_error: Error message if audit_degraded=True
    """
    message: str
    violation_code: str
    design_id: Optional[str] = None
    rejected_path: Optional[str] = None
    reason_path: Optional[str] = None
    validator_mode: Optional[str] = None
    cycle: Optional[int] = None
    covenant_id: str = "C5"
    details: Optional[Dict[str, Any]] = None
    audit_degraded: bool = False
    audit_error: Optional[str] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (
                self.message,
                self.violation_code,
                self.design_id,
                self.rejected_path,
                self.reason_path,
                self.validator_mode,
                self.cycle,
                self.covenant_id,
                self.details,
                self.audit_degraded,
                self.audit_error,
            ),
        )


@dataclass
class TemporalCausalityViolation(EpistemicInvariantError):
    """Raised when belief update violates temporal causality.

    Agent 1: Temporal Causality & Epistemic Provenance Enforcement.

    Temporal admissibility rule: evidence_time_h >= claim_time_h

    Beliefs cannot travel backward in time. You may only update beliefs about
    a timepoint using evidence from that timepoint or later.

    This prevents retroactive inference: using 48h data to update 12h mechanism
    beliefs, then proposing 12h experiments and being confused by mismatch.

    Structured fields:
    - belief_name: Which belief was being updated
    - evidence_time_h: When the observation was made
    - claim_time_h: What timepoint the belief is about
    - violation_delta_h: How far backward in time (evidence_time_h - claim_time_h)
    """
    message: str
    belief_name: str
    evidence_time_h: float
    claim_time_h: float
    violation_delta_h: float
    cycle: Optional[int] = None
    covenant_id: str = "C8_TEMPORAL"  # New covenant for temporal causality
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (
                self.message,
                self.belief_name,
                self.evidence_time_h,
                self.claim_time_h,
                self.violation_delta_h,
                self.cycle,
                self.covenant_id,
                self.details,
            ),
        )


@dataclass
class TemporalProvenanceError(EpistemicInvariantError):
    """Raised when temporal metadata required for epistemic guarantees is missing.

    Agent 1.5: Temporal Provenance Enforcement.

    This error fires when:
    - Observation has no conditions
    - Conditions lack time_h
    - evidence_time_h is None when beliefs are updated
    - Ledger attempts to write belief_update without evidence_time_h

    This prevents silent bypass of temporal causality enforcement.
    Without evidence_time_h, the system cannot verify temporal admissibility.

    Structured fields:
    - message: Human-readable error description
    - missing_field: Which temporal field is missing
    - context: Where the error occurred
    """
    message: str
    missing_field: str = "evidence_time_h"
    context: str = "unknown"
    cycle: Optional[int] = None
    covenant_id: str = "C8_TEMPORAL"  # Same covenant as TemporalCausalityViolation
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (
                self.message,
                self.missing_field,
                self.context,
                self.cycle,
                self.covenant_id,
                self.details,
            ),
        )


class ExecutionIntegrityViolation(RuntimeError):
    """
    Raised when execution integrity checks detect plate map errors.

    This is NOT an epistemic invariant violation - it's a detected
    failure in the physical execution layer (robot errors, swapped reagents, etc.)

    The agent detected this, which is GOOD. The question is what to do about it.

    Usage:
    - In CI/deterministic tests: throw on "halt" or "fatal"
    - In interactive exploration: soft halt and propose diagnostic
    - In production: escalate to human intervention

    Structured fields:
    - integrity_state: Full execution integrity state with violations
    - message: Human-readable error description
    """

    def __init__(self, message: str, integrity_state: ExecutionIntegrityState):
        super().__init__(message)
        self.integrity_state = integrity_state

    def __reduce__(self):
        """Enable pickle serialization for multiprocessing and persistence."""
        return (
            self.__class__,
            (self.args[0], self.integrity_state),
        )


class ExecutionIntegrityFatal(ExecutionIntegrityViolation):
    """
    Raised when execution integrity failure is unrecoverable.

    This is the "stop everything, human required" state.

    Triggers:
    - Multiple simultaneous violations (e.g., anchors wrong + dose inverted)
    - Violations with high spatial consistency (rigid transforms like column shift)
    - Diagnostic confirms systematic error

    The agent cannot self-heal from this. Requires:
    - Manual plate inspection
    - Re-running experiments
    - Investigation of root cause (robot calibration, worklist error, etc.)
    """

    pass
