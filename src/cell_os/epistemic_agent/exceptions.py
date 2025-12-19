"""
Epistemic Invariant Exceptions

These are not bugs. These are violations of the Seven Covenants.
They should never be caught and handled - they should crash the system
and force a fix.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
