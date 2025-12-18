"""
Evidence ledger: accountability mechanisms for belief updates.

Every belief change gets a receipt with:
- What changed (prev → new)
- Why it changed (evidence)
- What data supported it (condition keys)
"""

import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class EvidenceEvent:
    """A single belief update with evidence."""
    cycle: int
    belief: str
    prev: Any
    new: Any
    evidence: Dict[str, Any]
    supporting_conditions: List[str]
    note: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return json.dumps(self.to_dict(), sort_keys=True)


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
    """Append events to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.to_json_line() + "\n")


@dataclass(frozen=True)
class DecisionEvent:
    """A single decision with all candidate scores."""
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
        return json.dumps(self.to_dict(), sort_keys=True)


def append_decisions_jsonl(path, decisions: List[DecisionEvent]):
    """Append decisions to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for dec in decisions:
            f.write(dec.to_json_line() + "\n")


@dataclass(frozen=True)
class NoiseDiagnosticEvent:
    """Per-cycle instrument noise diagnostics (always emitted)."""
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
        """Convert to JSON-serializable dict."""
        return asdict(self)

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return json.dumps(self.to_dict(), sort_keys=True)


def append_noise_diagnostics_jsonl(path, diagnostics: List[NoiseDiagnosticEvent]):
    """Append noise diagnostics to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for diag in diagnostics:
            f.write(diag.to_json_line() + "\n")
