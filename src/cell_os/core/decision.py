"""
Canonical decision types.

A Decision is an immutable, serializable object that bundles:
1. What was chosen
2. Why it was chosen
3. What it was based on
4. What it refused and why
5. The exact inputs and thresholds that mattered

This eliminates the "side-channel provenance" pattern where decisions
are stored in mutable state (e.g., `chooser.last_decision_event`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence
from datetime import datetime, timezone
import json
import math


def _json_dumps_safe(obj: Any, **kwargs: Any) -> str:
    """JSON serializer that handles infinity and NaN values.

    Converts:
    - float('inf') → null
    - float('-inf') → null
    - float('nan') → null

    This ensures valid JSON output for JSONL files.
    """
    def _convert(o: Any) -> Any:
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
class DecisionRationale:
    """Why a decision was made.

    This captures the logic that led to the choice:
    - Which rules fired (stable identifiers, not prose)
    - Which warnings were considered (references to QualityWarning categories)
    - Which metrics mattered (e.g., rel_width, top_prob, ece)
    - Which thresholds were applied (e.g., gate_enter=0.25, commit=0.75)
    - What would have happened under different conditions (counterfactuals)
    """
    summary: str
    """Human-readable one-liner explaining the decision."""

    rules_fired: tuple[str, ...] = field(default_factory=tuple)
    """Stable identifiers for rules that triggered (not prose)."""

    warnings: tuple[str, ...] = field(default_factory=tuple)
    """References to QualityWarning categories that were considered."""

    metrics: Mapping[str, float] = field(default_factory=dict)
    """Relevant metrics at decision time (e.g., rel_width=0.3, top_prob=0.8)."""

    thresholds: Mapping[str, float] = field(default_factory=dict)
    """Thresholds applied (e.g., gate_enter=0.25, commit=0.75)."""

    counterfactuals: Mapping[str, str] = field(default_factory=dict)
    """What would have happened under different conditions.

    Example:
        {"if_rel_width_below_0.25": "biology_would_be_allowed"}
    """

    # Legacy metadata fields (for backward compatibility with v0.4.x tests)
    # These will be deprecated in favor of rules_fired tuples
    regime: Optional[str] = None
    """Decision regime (e.g., "pre_gate", "in_gate", "gate_revoked")."""

    forced: Optional[bool] = None
    """Whether this decision was forced by policy (not autonomous choice)."""

    trigger: Optional[str] = None
    """What triggered this decision (e.g., "must_calibrate", "gate_lock", "abort")."""

    enforcement_layer: Optional[str] = None
    """Which enforcement layer made this decision (e.g., "global_pre_biology", "template_safety_net")."""

    blocked_template: Optional[str] = None
    """Template that was blocked (for enforcement overrides)."""

    gate_state: Optional[Mapping[str, str]] = None
    """Gate status for all assays at decision time."""

    calibration_plan: Optional[Mapping[str, Any]] = None
    """Calibration plan details (wells_needed, df_needed, assays, etc.)."""


@dataclass(frozen=True)
class Decision:
    """An immutable, serializable decision artifact.

    A Decision bundles everything needed to understand, replay, or audit
    a single decision point in the agent's execution.

    Key properties:
    - Immutable (frozen=True)
    - Serializable (all fields JSON-compatible)
    - Self-contained (no references to mutable state)
    - Hashable (can be used as dict key or in sets)
    """

    decision_id: str
    """Unique identifier for this decision (deterministic or UUID)."""

    cycle: int
    """Which cycle this decision was made in."""

    timestamp_utc: str
    """When this decision was made (ISO 8601 format)."""

    kind: str
    """Type of decision: "proposal" | "refusal" | "commit" | "calibration" | "abort"."""

    chosen_template: Optional[str]
    """Template name chosen (None for refusals)."""

    chosen_kwargs: Mapping[str, Any]
    """Parameters for the chosen template."""

    rationale: DecisionRationale
    """Why this decision was made."""

    inputs_fingerprint: str
    """Hash of belief snapshot + budget + run_context.

    This fingerprint should be stable across runs with same inputs.
    It should NOT include timestamps or file paths.

    Should include:
    - Belief state hash (or key fields + values)
    - Budget remaining
    - Cycle number
    - Run context ID (if relevant)
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        rationale_dict: dict[str, Any] = {
            "summary": self.rationale.summary,
            "rules_fired": list(self.rationale.rules_fired),
            "warnings": list(self.rationale.warnings),
            "metrics": dict(self.rationale.metrics),
            "thresholds": dict(self.rationale.thresholds),
            "counterfactuals": dict(self.rationale.counterfactuals),
        }

        # Include legacy fields if present (backward compatibility)
        if self.rationale.regime is not None:
            rationale_dict["regime"] = self.rationale.regime
        if self.rationale.forced is not None:
            rationale_dict["forced"] = self.rationale.forced
        if self.rationale.trigger is not None:
            rationale_dict["trigger"] = self.rationale.trigger
        if self.rationale.enforcement_layer is not None:
            rationale_dict["enforcement_layer"] = self.rationale.enforcement_layer
        if self.rationale.blocked_template is not None:
            rationale_dict["blocked_template"] = self.rationale.blocked_template
        if self.rationale.gate_state is not None:
            rationale_dict["gate_state"] = dict(self.rationale.gate_state)
        if self.rationale.calibration_plan is not None:
            rationale_dict["calibration_plan"] = dict(self.rationale.calibration_plan)

        return {
            "decision_id": self.decision_id,
            "cycle": self.cycle,
            "timestamp_utc": self.timestamp_utc,
            "kind": self.kind,
            "chosen_template": self.chosen_template,
            "chosen_kwargs": dict(self.chosen_kwargs),
            "rationale": rationale_dict,
            "inputs_fingerprint": self.inputs_fingerprint,
        }

    def to_json_line(self) -> str:
        """Serialize as single JSON line for JSONL."""
        return _json_dumps_safe(self.to_dict(), sort_keys=True)

    @classmethod
    def now_utc(cls) -> str:
        """Generate UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        """Deserialize from dict (e.g., loaded from JSON)."""
        rationale_data = data.get("rationale", {})
        rationale = DecisionRationale(
            summary=rationale_data.get("summary", ""),
            rules_fired=tuple(rationale_data.get("rules_fired", [])),
            warnings=tuple(rationale_data.get("warnings", [])),
            metrics=rationale_data.get("metrics", {}),
            thresholds=rationale_data.get("thresholds", {}),
            counterfactuals=rationale_data.get("counterfactuals", {}),
            # Legacy fields (backward compatibility)
            regime=rationale_data.get("regime"),
            forced=rationale_data.get("forced"),
            trigger=rationale_data.get("trigger"),
            enforcement_layer=rationale_data.get("enforcement_layer"),
            blocked_template=rationale_data.get("blocked_template"),
            gate_state=rationale_data.get("gate_state"),
            calibration_plan=rationale_data.get("calibration_plan"),
        )

        return cls(
            decision_id=data["decision_id"],
            cycle=data["cycle"],
            timestamp_utc=data["timestamp_utc"],
            kind=data["kind"],
            chosen_template=data.get("chosen_template"),
            chosen_kwargs=data.get("chosen_kwargs", {}),
            rationale=rationale,
            inputs_fingerprint=data["inputs_fingerprint"],
        )
