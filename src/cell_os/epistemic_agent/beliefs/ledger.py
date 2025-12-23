"""
Evidence ledger: accountability mechanisms for belief updates.

Every belief change gets a receipt with:
- What changed (prev → new)
- Why it changed (evidence)
- What data supported it (condition keys)

Agent C Phase 1: Schema versioning and event type envelope.
- All events now have event_type and schema_version fields
- Increment SCHEMA_VERSION when adding required fields or changing semantics
"""

import json
import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

# Schema versioning for JSONL events
# Version 1: Added event_type and schema_version envelope (Agent C Phase 1)
SCHEMA_VERSION = 1


def _json_dumps_safe(obj: Any, **kwargs) -> str:
    """JSON serializer that handles infinity and NaN values.

    Converts:
    - float('inf') → null
    - float('-inf') → null
    - float('nan') → null

    This ensures valid JSON output for JSONL files.
    """
    def _convert(o):
        if isinstance(o, float):
            if math.isinf(o) or math.isnan(o):
                return None
        elif isinstance(o, dict):
            return {k: _convert(v) for k, v in o.items()}
        elif isinstance(o, (list, tuple)):
            return [_convert(item) for item in o]
        return o

    return json.dumps(_convert(obj), **kwargs)


@dataclass(frozen=True)
class EvidenceEvent:
    """A single belief update with evidence.

    Temporal provenance (Agent 1 - Temporal Causality Enforcement):
    - evidence_time_h: When the observation was made (hours since t=0)
    - claim_time_h: What timepoint the belief is about (hours since t=0, or None if atemporal)

    Temporal admissibility rule: evidence_time_h >= claim_time_h
    (You may only update beliefs about a timepoint using evidence from that timepoint or later)

    Schema envelope (Agent C Phase 1):
    - event_type: "evidence" for routing
    - schema_version: integer version for compatibility
    """
    cycle: int
    belief: str
    prev: Any
    new: Any
    evidence: Dict[str, Any]
    supporting_conditions: List[str]
    note: Optional[str] = None
    evidence_time_h: Optional[float] = None  # When observation was made
    claim_time_h: Optional[float] = None  # What timepoint belief is about (None = atemporal)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict with schema envelope."""
        d = asdict(self)
        # Inject envelope fields for downstream parsing
        d["event_type"] = "evidence"
        d["schema_version"] = SCHEMA_VERSION
        return d

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return _json_dumps_safe(self.to_dict(), sort_keys=True)


def cond_key(cond) -> str:
    """Stable, human-readable key for a ConditionSummary."""
    return (f"{cond.cell_line}/{cond.compound}@{cond.dose_uM}uM/"
            f"{cond.time_h}h/{cond.assay}/{cond.position_tag}")


def format_event(ev: EvidenceEvent) -> str:
    """Format event for human-readable logs."""
    # Extract key evidence (keep it short)
    important_keys = {
        'cv_mean', 'range_over_mean', 'threshold',
        'effect_size', 'n_tests', 'n_channels',
        'max_diff_ratio', 'rel_range'
    }

    evidence_bits = [
        f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in ev.evidence.items()
        if k in important_keys
    ]

    evidence_str = ", ".join(evidence_bits) if evidence_bits else "no details"
    note_str = f" — {ev.note}" if ev.note else ""

    return f"🧾 {ev.belief}: {ev.prev} → {ev.new} ({evidence_str}){note_str}"


def append_events_jsonl(path, events: List[EvidenceEvent]):
    """Append events to JSONL file.

    Agent 1.5: Temporal Provenance Enforcement.
    Refuses to write belief_update events without evidence_time_h.
    """
    from ..exceptions import TemporalProvenanceError

    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            # Agent 1.5: Check for belief updates (not gate events) with null evidence_time_h
            # Gate events have belief like "gate_event:*" or "gate_loss:*"
            # Belief updates have belief like "dose_curvature_seen", "noise_sigma_stable", etc.
            is_gate_event = (
                ev.belief.startswith("gate_event:") or
                ev.belief.startswith("gate_loss:") or
                ev.belief.startswith("gate_shadow:")
            )

            # For non-gate belief updates, evidence_time_h should not be None
            # (Atemporal beliefs are allowed with evidence_time_h set, just claim_time_h=None)
            if not is_gate_event and ev.evidence_time_h is None:
                # Allow special cases: insolvency tracking, gate attainment
                special_beliefs = {"epistemic_insolvent"}
                if ev.belief not in special_beliefs:
                    raise TemporalProvenanceError(
                        message=(
                            f"Ledger refused to write belief_update for '{ev.belief}' "
                            f"with evidence_time_h=None; temporal provenance would be lost"
                        ),
                        missing_field="evidence_time_h",
                        context="ledger.append_events_jsonl()",
                        cycle=ev.cycle,
                        details={"belief": ev.belief, "prev": ev.prev, "new": ev.new}
                    )

            f.write(ev.to_json_line() + "\n")


@dataclass(frozen=True)
class DecisionEvent:
    """A single decision with all candidate scores.

    LEGACY/DEAD CODE: This event type is defined but NOT USED.
    loop.py uses core/decision.py::Decision instead.
    Kept for backward compatibility but not maintained.
    """
    cycle: int
    candidates: List[Dict[str, Any]]  # List of {template, base_ev, cost, score, multiplier, ...}
    selected: str  # template name
    selected_score: float
    selected_candidate: Dict[str, Any]
    reason: str

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return _json_dumps_safe(self.to_dict(), sort_keys=True)


def append_decisions_jsonl(path, decisions: List[DecisionEvent]):
    """Append decisions to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for dec in decisions:
            f.write(dec.to_json_line() + "\n")


@dataclass(frozen=True)
class RefusalEvent:
    """
    A single refusal with full context.

    This is NOT a warning. This is a permanent record that the system
    refused to execute an action because epistemic debt made it unaffordable.

    Refusals are asymmetric: they only trigger when overclaiming has accumulated.
    Underclaiming never causes refusal.

    Schema envelope (Agent C Phase 1):
    - event_type: "refusal" for routing
    - schema_version: integer version for compatibility
    """
    cycle: int
    timestamp: str
    refusal_reason: str  # "epistemic_debt_budget_exceeded" or "epistemic_debt_action_blocked"

    # Action that was refused
    proposed_template: str
    proposed_hypothesis: str
    proposed_wells: int

    # Epistemic state at refusal
    debt_bits: float
    base_cost_wells: int
    inflated_cost_wells: float
    budget_remaining: int
    debt_threshold: float  # What threshold was violated

    # Context
    blocked_by_cost: bool  # True if inflated cost exceeded budget
    blocked_by_threshold: bool  # True if debt exceeded hard threshold

    # Optional design ID (if proposal existed)
    design_id: Optional[str] = None

    # Agent 3: Deadlock prevention diagnostics
    budget_after_action: Optional[int] = None  # Budget remaining after action would execute
    required_reserve: Optional[int] = None  # Minimum wells required for recovery
    blocked_by_reserve: Optional[bool] = None  # True if budget reserve violation
    is_calibration: Optional[bool] = None  # True if action is calibration
    is_deadlocked: Optional[bool] = None  # True if epistemic deadlock detected

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict with schema envelope."""
        d = asdict(self)
        d["event_type"] = "refusal"
        d["schema_version"] = SCHEMA_VERSION
        return d

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return _json_dumps_safe(self.to_dict(), sort_keys=True)


def append_refusals_jsonl(path, refusals: List[RefusalEvent]):
    """Append refusals to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for refusal in refusals:
            f.write(refusal.to_json_line() + "\n")


@dataclass(frozen=True)
class NoiseDiagnosticEvent:
    """Per-cycle instrument noise diagnostics (always emitted).

    Schema envelope (Agent C Phase 1):
    - event_type: "noise_diagnostic" for routing
    - schema_version: integer version for compatibility
    """
    cycle: int
    condition_key: str
    n_wells: int
    std_cycle: float
    mean_cycle: float
    pooled_df: int
    pooled_sigma: float
    ci_low: Optional[float]
    ci_high: Optional[float]
    rel_width: Optional[float]
    drift_metric: Optional[float]
    noise_sigma_stable: bool
    enter_threshold: float
    exit_threshold: float
    df_min: int
    drift_threshold: float

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict with schema envelope."""
        d = asdict(self)
        d["event_type"] = "noise_diagnostic"
        d["schema_version"] = SCHEMA_VERSION
        return d

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return _json_dumps_safe(self.to_dict(), sort_keys=True)


def append_noise_diagnostics_jsonl(path, diagnostics: List[NoiseDiagnosticEvent]):
    """Append noise diagnostics to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for diag in diagnostics:
            f.write(diag.to_json_line() + "\n")
