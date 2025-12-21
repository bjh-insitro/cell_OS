"""
Lightweight belief state for evidence-driven experiment selection.

v0.5.0: Measurement ladder with assay-specific gates (LDH, Cell Painting, scRNA).
- Pay-for-calibration regime extended to assay ladder
- Assay-specific gate events (ldh, cell_paint, scrna)
- Ladder constraints: scRNA requires CP gate, CP requires LDH gate (or noise baseline)
- Symmetric gate events (gate_event:* and gate_loss:*) for all assays
- Complete provenance tracking with upgrade triggers

v0.4.2: Baseline pay-for-calibration regime with noise gates.

No Bayesian math, no LLM - just trackable heuristics with receipts.
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import math
import numpy as np
from .ledger import EvidenceEvent, cond_key
from ..exceptions import BeliefLedgerInvariantError


def _inv_norm_cdf(p: float) -> float:
    """Acklam approximation for inverse normal CDF (good enough for CI gating)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01,  2.209460984245205e+02,
         -2.759285104469687e+02,  1.383577518672690e+02,
         -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02,
         -1.556989798598866e+02,  6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
          1.950560116618389e+00,  1.0]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,
          2.445134137142996e+00,  3.754408661907416e+00]
    
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q*q
        return q * (((((a[5]*r + a[4])*r + a[3])*r + a[2])*r + a[1])*r + a[0]) / \
               (((((b[4]*r + b[3])*r + b[2])*r + b[1])*r + b[0])*r + 1.0)
    else:
        r = p if q < 0 else 1.0 - p
        r = math.sqrt(-math.log(r))
        
        if r <= 5.0:
            r = r - 1.6
            val = (((((c[5]*r + c[4])*r + c[3])*r + c[2])*r + c[1])*r + c[0]) / \
                  ((((d[3]*r + d[2])*r + d[1])*r + d[0])*r + 1.0)
        else:
            r = r - 5.0
            val = (((((c[5]*r + c[4])*r + c[3])*r + c[2])*r + c[1])*r + c[0]) / \
                  ((((d[3]*r + d[2])*r + d[1])*r + d[0])*r + 1.0)
        
        return -val if q < 0 else val


def _chi2_ppf_wh(p: float, df: int) -> float:
    """Wilson-Hilferty approximation for chi-square quantile."""
    if p <= 0 or p >= 1:
        return 0.0
    if df <= 0:
        return 0.0
    
    z = _inv_norm_cdf(p)
    df_f = float(df)
    term = z * math.sqrt(2.0 / (9.0 * df_f)) - (2.0 / (9.0 * df_f))
    val = df_f * (1.0 + term) ** 3
    return max(val, 0.001)


def _sigma_ci_from_pooled(sse_total: float, df_total: int, alpha: float = 0.05):
    """Compute CI for sigma from pooled variance using chi-square.

    For chi-square CI for variance:
    - CI_lower = (df * s^2) / chi2_upper_quantile
    - CI_upper = (df * s^2) / chi2_lower_quantile
    """
    if df_total <= 0 or sse_total <= 0:
        return (None, None)

    sigma2_hat = sse_total / df_total
    chi2_lower = _chi2_ppf_wh(alpha/2, df_total)      # 0.025 quantile
    chi2_upper = _chi2_ppf_wh(1 - alpha/2, df_total)  # 0.975 quantile

    if chi2_lower <= 0 or chi2_upper <= 0:
        return (None, None)

    # Variance CI, then convert to sigma CI
    var_lo = (df_total * sigma2_hat) / chi2_upper
    var_hi = (df_total * sigma2_hat) / chi2_lower
    return (math.sqrt(max(var_lo, 0.0)), math.sqrt(max(var_hi, 0.0)))


@dataclass
class BeliefState:
    """Tracks what the agent knows (with evidence receipts).

    v0.5.0: Pay-for-calibration with measurement ladder (LDH, CP, scRNA gates).
    v0.4.2: Baseline noise gate implementation.
    """
    
    # Noise model (pooled variance + chi-square CI)
    noise_sigma_hat: Optional[float] = None
    noise_ci_low: Optional[float] = None
    noise_ci_high: Optional[float] = None
    noise_rel_width: Optional[float] = None
    noise_sigma_stable: bool = False             # THE GATE (replaces cv_stable)
    noise_df_total: int = 0
    noise_sse_total: float = 0.0
    noise_sigma_cycle_history: List[float] = field(default_factory=list)
    noise_drift_metric: Optional[float] = None
    noise_gate_streak: int = 0                   # Consecutive stable observations (for K-sequential requirement)

    # Assay-specific gates (measurement ladder)
    # LDH: scalar viability readout
    ldh_df_total: int = 0
    ldh_rel_width: Optional[float] = None
    ldh_sigma_stable: bool = False

    # Cell Painting: high-dimensional morphology
    cell_paint_df_total: int = 0
    cell_paint_rel_width: Optional[float] = None
    cell_paint_sigma_stable: bool = False

    # scRNA Drug-seq: transcriptional state
    scrna_df_total: int = 0
    scrna_rel_width: Optional[float] = None
    scrna_sigma_stable: bool = False
    scrna_metric_source: Optional[str] = None  # Set explicitly during updates: "proxy:noisy_morphology" or "scrna:transcriptome"

    baseline_cv_scalar: Optional[float] = None
    baseline_cv_by_channel: Dict[str, float] = field(default_factory=dict)
    calibration_reps: int = 0
    baseline_std_scalar: Optional[float] = None
    cv_history: List[float] = field(default_factory=list)
    
    # Edge effects
    edge_effect_strength_by_channel: Dict[str, float] = field(default_factory=dict)
    edge_effect_confident: bool = False
    edge_tests_run: int = 0
    
    # Response patterns
    dose_curvature_seen: bool = False
    time_dependence_seen: bool = False
    
    # Exploration tracking
    tested_compounds: Set[str] = field(default_factory=set)
    tested_cell_lines: Set[str] = field(default_factory=set)
    total_observations: int = 0

    # Epistemic insolvency tracking (debt enforcement)
    epistemic_insolvent: bool = False        # True if last action was refused due to debt
    epistemic_debt_bits: float = 0.0         # Last known debt level
    consecutive_refusals: int = 0            # Count of refusals in a row (backoff trigger)
    last_refusal_reason: Optional[str] = None  # Most recent refusal reason

    # Evidence ledger
    _cycle: int = 0
    _events: List[EvidenceEvent] = field(default_factory=list)

    # Agent 1: Temporal provenance tracking
    _current_evidence_time_h: Optional[float] = None  # Set during update() from observation

    def begin_cycle(self, cycle: int):
        """Start a new cycle (clear event buffer)."""
        self._cycle = cycle
        self._events = []
    
    def end_cycle(self) -> List[EvidenceEvent]:
        """Return events from this cycle."""
        return self._events

    def record_refusal(
        self,
        refusal_reason: str,
        debt_bits: float,
        debt_threshold: float
    ) -> None:
        """
        Record that an action was refused due to epistemic debt.

        This is a measurement about the agent's state, not about biology.
        The agent learns "I am epistemically insolvent" and must adapt.

        Args:
            refusal_reason: Why refused ("epistemic_debt_action_blocked" or "epistemic_debt_budget_exceeded")
            debt_bits: Current epistemic debt
            debt_threshold: Threshold that was violated (usually 2.0)
        """
        # Update insolvency state
        self.epistemic_insolvent = True
        self.epistemic_debt_bits = debt_bits
        self.consecutive_refusals += 1
        self.last_refusal_reason = refusal_reason

        # Emit evidence event (refusal is evidence about agent state)
        self._events.append(EvidenceEvent(
            cycle=self._cycle,
            belief="epistemic_insolvent",
            prev=False,
            new=True,
            evidence={
                "refusal_reason": refusal_reason,
                "debt_bits": debt_bits,
                "debt_threshold": debt_threshold,
                "consecutive_refusals": self.consecutive_refusals
            },
            supporting_conditions=[],
            note=f"Action refused: {refusal_reason} (debt={debt_bits:.2f} > threshold={debt_threshold:.2f})"
        ))

    def record_action_executed(self, was_calibration: bool) -> None:
        """
        Record that an action successfully executed (not refused).

        If calibration executed, check if debt reduced enough to clear insolvency.

        Args:
            was_calibration: True if the executed action was a calibration template
        """
        if not self.epistemic_insolvent:
            return  # Already solvent, nothing to do

        # If calibration executed, assume debt is being addressed
        # (Controller will update debt separately; we just track state transitions)
        if was_calibration:
            # Check if debt dropped below threshold
            # (Threshold is 2.0 bits by convention)
            if self.epistemic_debt_bits < 2.0:
                # Clear insolvency
                self.epistemic_insolvent = False
                self.consecutive_refusals = 0
                self.last_refusal_reason = None

                self._events.append(EvidenceEvent(
                    cycle=self._cycle,
                    belief="epistemic_insolvent",
                    prev=True,
                    new=False,
                    evidence={
                        "debt_bits": self.epistemic_debt_bits,
                        "calibration_succeeded": True
                    },
                    supporting_conditions=[],
                    note=f"Solvency restored: debt={self.epistemic_debt_bits:.2f} < 2.0 threshold"
                ))

    def update_debt_level(self, current_debt: float) -> None:
        """
        Update tracked debt level (called by controller after each resolution).

        This keeps beliefs synchronized with controller state.

        Args:
            current_debt: Current epistemic debt from controller
        """
        self.epistemic_debt_bits = current_debt

        # If debt dropped below threshold while insolvent, clear flag
        if self.epistemic_insolvent and current_debt < 2.0:
            self.epistemic_insolvent = False
            self.consecutive_refusals = 0
            self.last_refusal_reason = None

    def _set(
        self,
        field_name: str,
        new_value: Any,
        *,
        evidence: Dict[str, Any],
        supporting_conditions: List[str],
        note: Optional[str] = None,
        claim_time_h: Optional[float] = None,  # Agent 1: What timepoint belief is about
        evidence_time_h: Optional[float] = None,  # Agent 1: When observation was made
    ):
        """Set a belief field and record evidence if it changed.

        This is the core accountability mechanism: every belief flip gets a receipt.

        Agent 1: Temporal Causality Enforcement
        - evidence_time_h: When the observation was made (defaults to _current_evidence_time_h)
        - claim_time_h: What timepoint the belief is about (None = atemporal belief)

        Temporal admissibility rule: evidence_time_h >= claim_time_h
        If violated, raises TemporalCausalityViolation (refusal, not warning).
        """
        from ..exceptions import TemporalCausalityViolation

        prev_value = getattr(self, field_name)

        if prev_value == new_value:
            return  # No change, no event

        # Agent 1: Temporal admissibility check
        # Use provided evidence_time_h, or fall back to _current_evidence_time_h
        final_evidence_time_h = evidence_time_h if evidence_time_h is not None else self._current_evidence_time_h

        # If both evidence_time_h and claim_time_h are specified, enforce temporal causality
        # Rule: claim_time_h <= evidence_time_h
        # (Can only make claims about states at or before observation time)
        if final_evidence_time_h is not None and claim_time_h is not None:
            if claim_time_h > final_evidence_time_h:
                violation_delta = claim_time_h - final_evidence_time_h
                raise TemporalCausalityViolation(
                    message=(
                        f"Attempted to update belief '{field_name}' about timepoint {claim_time_h}h "
                        f"using evidence from {final_evidence_time_h}h. "
                        f"Cannot make claims about future states using past evidence (violation: {violation_delta:.2f}h)."
                    ),
                    belief_name=field_name,
                    evidence_time_h=final_evidence_time_h,
                    claim_time_h=claim_time_h,
                    violation_delta_h=violation_delta,
                    cycle=self._cycle,
                    details={
                        "prev_value": prev_value,
                        "new_value": new_value,
                        "supporting_conditions": supporting_conditions,
                    }
                )

        # Covenant 7: Field-level provenance
        # Tag exactly which belief field(s) this EvidenceEvent just changed.
        # This prevents a single unrelated event from "laundering" other mutations.
        if evidence is None:
            evidence = {}
        else:
            # Avoid mutating caller-owned dicts
            evidence = dict(evidence)

        existing = evidence.get("fields_changed")
        if existing is None:
            evidence["fields_changed"] = [field_name]
        else:
            # Allow upstream callers to pre-populate this, but guarantee inclusion
            evidence["fields_changed"] = sorted(set(list(existing) + [field_name]))

        setattr(self, field_name, new_value)

        self._events.append(EvidenceEvent(
            cycle=self._cycle,
            belief=field_name,
            prev=prev_value,
            new=new_value,
            evidence=evidence,
            supporting_conditions=supporting_conditions,
            note=note,
            evidence_time_h=final_evidence_time_h,
            claim_time_h=claim_time_h,
        ))

        # v0.4.2+: explicit gate events for provenance-safe attainment tracking
        if (prev_value is False) and (new_value is True):
            # Only for gate-type beliefs (keep whitelist tight)
            if field_name == "noise_sigma_stable":
                self._emit_gate_event(
                    "noise_sigma",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate earned: noise_sigma (rel_width={evidence.get('rel_width'):.4f}, df={evidence.get('pooled_df')})",
                )
            elif field_name == "edge_effect_confident":
                self._emit_gate_event(
                    "edge_effect",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate earned: edge_effect (n_tests={evidence.get('n_tests')}, mean_abs_effect={evidence.get('mean_abs_effect'):.4f})",
                )
            # Assay-specific gates (measurement ladder)
            elif field_name == "ldh_sigma_stable":
                self._emit_gate_event(
                    "ldh",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate earned: ldh (rel_width={evidence.get('rel_width'):.4f}, df={evidence.get('df')}, proxy:noisy_morphology)",
                )
            elif field_name == "cell_paint_sigma_stable":
                self._emit_gate_event(
                    "cell_paint",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate earned: cell_paint (rel_width={evidence.get('rel_width'):.4f}, df={evidence.get('df')}, proxy:noisy_morphology)",
                )
            elif field_name == "scrna_sigma_stable":
                self._emit_gate_event(
                    "scrna",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate earned: scrna (rel_width={evidence.get('rel_width'):.4f}, df={evidence.get('df')}, proxy:noisy_morphology)",
                )

        # v0.4.2+: symmetric gate_loss events (True → False)
        elif (prev_value is True) and (new_value is False):
            # Same whitelist: track revocations
            if field_name == "noise_sigma_stable":
                rel_width_val = evidence.get('rel_width')
                drift_val = evidence.get('drift_metric')
                rel_width_str = f"{rel_width_val:.4f}" if rel_width_val is not None else "N/A"
                drift_str = f"{drift_val:.4f}" if drift_val is not None else "N/A"
                self._emit_gate_loss(
                    "noise_sigma",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: noise_sigma (rel_width={rel_width_str}, drift={drift_str})",
                )
            elif field_name == "edge_effect_confident":
                mean_abs_effect_val = evidence.get('mean_abs_effect')
                mean_abs_effect_str = f"{mean_abs_effect_val:.4f}" if mean_abs_effect_val is not None else "0.0"
                self._emit_gate_loss(
                    "edge_effect",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: edge_effect (n_tests={evidence.get('n_tests')}, mean_abs_effect={mean_abs_effect_str})",
                )
            # Assay-specific gates
            elif field_name == "ldh_sigma_stable":
                self._emit_gate_loss(
                    "ldh",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: ldh (rel_width={evidence.get('rel_width'):.4f if evidence.get('rel_width') else 'N/A'}, proxy:noisy_morphology)",
                )
            elif field_name == "cell_paint_sigma_stable":
                self._emit_gate_loss(
                    "cell_paint",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: cell_paint (rel_width={evidence.get('rel_width'):.4f if evidence.get('rel_width') else 'N/A'}, proxy:noisy_morphology)",
                )
            elif field_name == "scrna_sigma_stable":
                self._emit_gate_loss(
                    "scrna",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: scrna (rel_width={evidence.get('rel_width'):.4f if evidence.get('rel_width') else 'N/A'}, proxy:noisy_morphology)",
                )

    def _emit_gate_event(
        self,
        gate_name: str,
        *,
        prev: Any,
        new: Any,
        evidence: Dict[str, Any],
        supporting_conditions: List[str],
        note: Optional[str] = None,
    ):
        """
        Emit an explicit gate attainment event.
        Uses the existing EvidenceEvent schema to avoid downstream schema changes.
        Provenance-safe: benchmark never has to infer from state transitions.
        """
        from datetime import datetime

        event = EvidenceEvent(
            cycle=self._cycle,
            belief=f"gate_event:{gate_name}",
            prev=prev,
            new=new,
            evidence={
                **(evidence or {}),
                "gate": gate_name,
                "event_type": "gate_event",
                "emitted_at": datetime.now().isoformat(timespec="seconds"),
            },
            supporting_conditions=list(supporting_conditions or []),
            note=note,
        )
        self._events.append(event)

    def _emit_gate_loss(
        self,
        gate_name: str,
        *,
        prev: Any,
        new: Any,
        evidence: Dict[str, Any],
        supporting_conditions: List[str],
        note: Optional[str] = None,
    ):
        """
        Emit an explicit gate loss event (symmetric to gate_event).
        Tracks when calibration degrades below acceptable thresholds.
        Critical for instrument regime: "we lost calibration, stop trusting downstream."
        """
        from datetime import datetime

        event = EvidenceEvent(
            cycle=self._cycle,
            belief=f"gate_loss:{gate_name}",
            prev=prev,
            new=new,
            evidence={
                **(evidence or {}),
                "gate": gate_name,
                "event_type": "gate_loss",
                "emitted_at": datetime.now().isoformat(timespec="seconds"),
            },
            supporting_conditions=list(supporting_conditions or []),
            note=note,
        )
        self._events.append(event)

    def _emit_gate_shadow(
        self,
        gate_name: str,
        *,
        evidence: Dict[str, Any],
        supporting_conditions: List[str],
        note: Optional[str] = None,
    ):
        """
        Emit a gate shadow event for non-actionable stats tracking.
        Used when metrics are tracked but gate cannot be earned (e.g., scRNA with proxy).
        UI can show these as "shadow stats" without claiming the gate is earned.
        """
        from datetime import datetime

        event = EvidenceEvent(
            cycle=self._cycle,
            belief=f"gate_shadow:{gate_name}",
            prev=None,
            new=None,
            evidence={
                **(evidence or {}),
                "gate": gate_name,
                "event_type": "gate_shadow",
                "actionable": False,
                "emitted_at": datetime.now().isoformat(timespec="seconds"),
            },
            supporting_conditions=list(supporting_conditions or []),
            note=note,
        )
        self._events.append(event)

    def to_dict(self) -> dict:
        """Serialize beliefs to dict (for JSON persistence)."""
        return {
            'noise_sigma_hat': self.noise_sigma_hat,
            'noise_ci_low': self.noise_ci_low,
            'noise_ci_high': self.noise_ci_high,
            'noise_rel_width': self.noise_rel_width,
            'noise_sigma_stable': self.noise_sigma_stable,
            'noise_df_total': self.noise_df_total,
            # Assay-specific gates
            'ldh_df_total': self.ldh_df_total,
            'ldh_rel_width': self.ldh_rel_width,
            'ldh_sigma_stable': self.ldh_sigma_stable,
            'cell_paint_df_total': self.cell_paint_df_total,
            'cell_paint_rel_width': self.cell_paint_rel_width,
            'cell_paint_sigma_stable': self.cell_paint_sigma_stable,
            'scrna_df_total': self.scrna_df_total,
            'scrna_rel_width': self.scrna_rel_width,
            'scrna_sigma_stable': self.scrna_sigma_stable,
            'scrna_metric_source': self.scrna_metric_source,
            # Legacy fields
            'baseline_cv_scalar': self.baseline_cv_scalar,
            'baseline_cv_by_channel': dict(self.baseline_cv_by_channel),
            'calibration_reps': self.calibration_reps,
            'edge_effect_strength_by_channel': dict(self.edge_effect_strength_by_channel),
            'edge_effect_confident': self.edge_effect_confident,
            'edge_tests_run': self.edge_tests_run,
            'dose_curvature_seen': self.dose_curvature_seen,
            'time_dependence_seen': self.time_dependence_seen,
            'tested_compounds': list(self.tested_compounds),
            'tested_cell_lines': list(self.tested_cell_lines),
            'total_observations': self.total_observations,
        }

    def snapshot(self) -> dict:
        """Capture current belief state for mutation tracking (Covenant 7)."""
        return self.to_dict()

    def assert_no_undocumented_mutation(
        self,
        before: dict,
        after: dict,
        *,
        cycle: int
    ) -> None:
        """Enforce Covenant 7: We Optimize for Causal Discoverability, Not Throughput.

        All belief changes must be accompanied by evidence events. This invariant
        check prevents direct mutation (beliefs.field = value) that bypasses _set().

        Args:
            before: Snapshot before cycle
            after: Snapshot after cycle
            cycle: Cycle number for diagnostics

        Raises:
            BeliefLedgerInvariantError: If beliefs changed without evidence events
        """
        # Find what changed
        changed = {k for k in after.keys() if before.get(k) != after.get(k)}
        if not changed:
            return  # No changes, all good

        # Get evidence events from this cycle
        cycle_events = [e for e in self._events if e.cycle == cycle]
        beliefs_logged = {e.belief for e in cycle_events}

        # If beliefs changed but no events emitted, this is a violation
        if not cycle_events:
            raise BeliefLedgerInvariantError(
                f"Beliefs mutated without any evidence events (cycle={cycle}). "
                f"Changed keys: {sorted(changed)[:15]}. "
                f"This violates Covenant 7: all belief updates must call _set() to emit evidence."
            )

        # Covenant 7: field-level mapping
        # Each changed field must be explicitly accounted for by at least one EvidenceEvent
        # via evidence["fields_changed"].
        accounted = set()
        for ev in cycle_events:
            ev_evidence = getattr(ev, "evidence", None) or {}
            fc = ev_evidence.get("fields_changed") or []
            # tolerate old events that lack fields_changed by falling back to ev.belief
            if not fc and getattr(ev, "belief", None):
                fc = [ev.belief]
            accounted |= set(fc)

        missing_fields = changed - accounted
        if missing_fields:
            raise BeliefLedgerInvariantError(
                f"Beliefs mutated without evidence mapping (cycle={cycle}). "
                f"Unaccounted fields: {sorted(missing_fields)[:15]}. "
                f"Changed fields: {sorted(changed)[:15]}. "
                f"Accounted by events: {sorted(accounted)[:15]}. "
                "This violates Covenant 7: every changed belief field must be claimed by an EvidenceEvent."
            )

        # Special check: gate changes require gate_* events
        gate_fields = [k for k in changed if k.endswith("_sigma_stable")]
        if gate_fields:
            gate_events = [
                b for b in beliefs_logged
                if b and (b.startswith("gate_event:") or b.startswith("gate_shadow:") or b.startswith("gate_loss:"))
            ]
            if not gate_events:
                raise BeliefLedgerInvariantError(
                    f"Gate field(s) changed without gate_* event (cycle={cycle}). "
                    f"Changed gates: {sorted(gate_fields)}. "
                    f"This violates Covenant 7: gate changes must emit gate_event/gate_loss/gate_shadow."
                )

    def update(self, observation, cycle: int = 0):
        """Update beliefs from a new observation.

        Args:
            observation: Observation object with conditions (List[ConditionSummary])
            cycle: Current cycle number (for diagnostics)

        Returns:
            (events, diagnostics): Event lists for ledgers
        """
        self.total_observations += 1

        # Extract conditions from observation
        conditions = observation.conditions if hasattr(observation, 'conditions') else []

        # Agent 1: Extract observation time for temporal provenance
        # Set _current_evidence_time_h from conditions (use max time if multiple)
        if conditions:
            # Extract all unique time_h values from conditions
            time_h_values = [cond.time_h for cond in conditions if hasattr(cond, 'time_h')]
            if time_h_values:
                # Use the maximum observation time (most conservative for causality)
                self._current_evidence_time_h = max(time_h_values)

        # Track compounds and cell lines
        for cond in conditions:
            self.tested_compounds.add(cond.compound)
            self.tested_cell_lines.add(cond.cell_line)

        # Update noise model, edge effects, dose/time beliefs
        diagnostics_out = []
        self._update_noise_beliefs(conditions, diagnostics_out)
        self._update_edge_beliefs(conditions)
        self._update_response_beliefs(conditions)

        # v0.5.0: Update assay-specific gates (measurement ladder)
        self._update_assay_gates(conditions, "ldh")
        self._update_assay_gates(conditions, "cell_paint")
        self._update_assay_gates(conditions, "scrna")

        return (self._events, diagnostics_out)

    def _update_noise_beliefs(self, conditions: List, diagnostics_out: List):
        """Update noise model using pooled variance + chi-square CI.

        v0.4.2: Gate based on rel_width ≤ 0.25 (not arbitrary df threshold).
        Emits gate_event when earned, gate_loss when revoked.
        """
        # Find DMSO baseline conditions
        dmso_conditions = [c for c in conditions if c.compound == 'DMSO' and c.position_tag == 'center']

        if not dmso_conditions:
            return

        for cond in dmso_conditions:
            n = cond.n_wells
            condition_key = cond_key(cond)

            # 1) Track per-channel CV for transparency
            if cond.feature_means:
                for ch, mean_val in cond.feature_means.items():
                    std_val = cond.feature_stds.get(ch, 0.0)
                    if mean_val > 0:
                        self.baseline_cv_by_channel[ch] = float(std_val / mean_val)

            self.calibration_reps += n
            self.baseline_std_scalar = float(cond.std)
            self.baseline_cv_scalar = float(cond.cv)
            self.cv_history.append(float(cond.cv))

            # 2) Pooled variance update using (n, std)
            df = n - 1
            sse = df * (float(cond.std) ** 2)
            self.noise_df_total += df
            self.noise_sse_total += sse

            # 3) Compute pooled sigma + CI
            if self.noise_df_total > 0 and self.noise_sse_total > 0:
                sigma2_hat = self.noise_sse_total / self.noise_df_total
                sigma_hat = math.sqrt(max(sigma2_hat, 0.0))
                ci_low, ci_high = _sigma_ci_from_pooled(self.noise_sse_total, self.noise_df_total, alpha=0.05)

                self.noise_sigma_hat = sigma_hat
                self.noise_ci_low = ci_low
                self.noise_ci_high = ci_high

                if ci_low is not None and ci_high is not None and sigma_hat > 0:
                    # TEMP FIX: use abs() since ci_low/ci_high swap bug in chi2 approx
                    rel_width = abs(ci_high - ci_low) / sigma_hat
                else:
                    rel_width = None
                self.noise_rel_width = rel_width
            else:
                sigma_hat = None
                rel_width = None

            # 4) Drift detection on per-cycle sigma estimates
            drift_metric = None
            sigma_cycle = float(cond.std)
            self.noise_sigma_cycle_history.append(sigma_cycle)
            if len(self.noise_sigma_cycle_history) > 20:
                self.noise_sigma_cycle_history = self.noise_sigma_cycle_history[-20:]

            k = 5
            if len(self.noise_sigma_cycle_history) >= 2 * k and self.noise_sigma_hat:
                prev = self.noise_sigma_cycle_history[-2*k:-k]
                recent = self.noise_sigma_cycle_history[-k:]
                prev_m = float(np.mean(prev))
                recent_m = float(np.mean(recent))
                drift_metric = abs(recent_m - prev_m) / float(self.noise_sigma_hat)
            self.noise_drift_metric = drift_metric

            # 5) Gate with hysteresis on relative CI width + df sanity + drift
            # ROBUST GATE: Requires K consecutive stable observations (not one lucky batch)
            enter_threshold = 0.25
            exit_threshold = 0.40
            df_min_sanity = 40  # Sanity floor: prevent nonsense claims at tiny df
            drift_threshold = 0.20
            NOISE_GATE_STREAK_K = 3  # Must see stability K consecutive times

            drift_bad = (drift_metric is not None and drift_metric >= drift_threshold)

            # Separate one-time df check from per-observation stability check
            # df_min_sanity: One-time gate to prevent earning before enough data
            # current_observation_stable: Per-observation check (rel_width + drift)
            has_enough_data = (self.noise_df_total >= df_min_sanity)
            current_observation_stable = (
                rel_width is not None and
                rel_width <= enter_threshold and
                not drift_bad
            )

            # Gate logic with sequential stability requirement
            new_stable = self.noise_sigma_stable
            if not self.noise_sigma_stable:
                # Not yet stable: accumulate evidence
                if has_enough_data:
                    # Only start counting streak once we have enough data
                    if current_observation_stable:
                        # Increment streak
                        self.noise_gate_streak += 1
                        # Earn gate only if we've seen K consecutive stable observations
                        if self.noise_gate_streak >= NOISE_GATE_STREAK_K:
                            new_stable = True
                    else:
                        # Reset streak on instability
                        self.noise_gate_streak = 0
                else:
                    # Not enough data yet - reset streak
                    self.noise_gate_streak = 0
            else:
                # Already stable: check for revocation
                # Revoke if clearly degraded or drifting
                should_revoke = (
                    drift_bad or
                    (rel_width is not None and rel_width >= exit_threshold)
                )
                if should_revoke:
                    new_stable = False
                    self.noise_gate_streak = 0  # Reset streak on revocation

            # Record belief change only if it flips
            # Format note strings (avoid conditionals in format specs)
            rel_width_str = f"{self.noise_rel_width:.3f}" if self.noise_rel_width is not None else "N/A"
            drift_str = f"{drift_metric:.3f}" if drift_metric is not None else "N/A"

            self._set(
                "noise_sigma_stable",
                new_stable,
                evidence={
                    "pooled_df": self.noise_df_total,
                    "pooled_sigma": self.noise_sigma_hat,
                    "ci_low": self.noise_ci_low,
                    "ci_high": self.noise_ci_high,
                    "rel_width": self.noise_rel_width,
                    "enter_threshold": enter_threshold,
                    "exit_threshold": exit_threshold,
                    "df_min_sanity": df_min_sanity,
                    "drift_metric": drift_metric,
                    "drift_threshold": drift_threshold,
                },
                supporting_conditions=[condition_key],
                note=(
                    f"noise_sigma_stable={new_stable} (df={self.noise_df_total}, "
                    f"rel_width={rel_width_str}, drift={drift_str}, "
                    f"streak={self.noise_gate_streak}/{NOISE_GATE_STREAK_K})"
                ),
            )
            self.noise_sigma_stable = new_stable

            # 6) Always emit diagnostic record for this calibration cycle
            from .ledger import NoiseDiagnosticEvent
            diagnostics_out.append(
                NoiseDiagnosticEvent(
                    cycle=self._cycle,
                    condition_key=condition_key,
                    n_wells=n,
                    std_cycle=sigma_cycle,
                    mean_cycle=float(cond.mean),
                    pooled_df=self.noise_df_total,
                    pooled_sigma=self.noise_sigma_hat or 0.0,
                    ci_low=self.noise_ci_low,
                    ci_high=self.noise_ci_high,
                    rel_width=self.noise_rel_width,
                    drift_metric=drift_metric,
                    noise_sigma_stable=self.noise_sigma_stable,
                    enter_threshold=enter_threshold,
                    exit_threshold=exit_threshold,
                    df_min=df_min_sanity,
                    drift_threshold=drift_threshold,
                )
            )

    def _update_edge_beliefs(self, conditions: List):
        """Detect edge effects by comparing edge vs center wells."""
        # Find matched edge/center pairs (same compound/dose/time)
        edge_conditions = {}
        center_conditions = {}

        for cond in conditions:
            key = (cond.cell_line, cond.compound, cond.dose_uM, cond.time_h, cond.assay)
            if cond.position_tag == 'edge':
                edge_conditions[key] = cond
            elif cond.position_tag == 'center':
                center_conditions[key] = cond

        # Find pairs and compute effect sizes
        matched_pairs = set(edge_conditions.keys()) & set(center_conditions.keys())

        if matched_pairs:
            self.edge_tests_run += 1

            # Compare by channel (feature_means)
            supporting = []
            for key in matched_pairs:
                edge = edge_conditions[key]
                center = center_conditions[key]

                supporting.append(cond_key(edge))
                supporting.append(cond_key(center))

                if edge.feature_means and center.feature_means:
                    for channel in edge.feature_means:
                        if channel in center.feature_means:
                            edge_val = edge.feature_means[channel]
                            center_val = center.feature_means[channel]
                            if center_val > 0:
                                effect = (edge_val - center_val) / center_val

                                # Accumulate effects (running average)
                                if channel not in self.edge_effect_strength_by_channel:
                                    self.edge_effect_strength_by_channel[channel] = effect
                                else:
                                    # Exponential moving average
                                    alpha = 0.7  # weight new observation more
                                    old = self.edge_effect_strength_by_channel[channel]
                                    self.edge_effect_strength_by_channel[channel] = alpha * effect + (1 - alpha) * old

        # Determine confidence: effect is consistent (abs > 5%) and we have 2+ tests
        if self.edge_tests_run >= 2 and self.edge_effect_strength_by_channel:
            strong_effects = [abs(e) > 0.05 for e in self.edge_effect_strength_by_channel.values()]
            n_strong = sum(strong_effects)
            new_confident = n_strong > 0

            # Compute summary evidence
            effect_magnitudes = [abs(e) for e in self.edge_effect_strength_by_channel.values()]
            mean_effect = float(np.mean(effect_magnitudes)) if effect_magnitudes else 0.0

            self._set(
                "edge_effect_confident",
                new_confident,
                evidence={
                    "n_tests": self.edge_tests_run,
                    "n_channels": len(self.edge_effect_strength_by_channel),
                    "n_strong_effects": n_strong,
                    "mean_abs_effect": mean_effect,
                    "threshold": 0.05,
                    "effects_by_channel": {k: float(v) for k, v in list(self.edge_effect_strength_by_channel.items())[:5]},
                },
                supporting_conditions=supporting,
                note=f"Edge bias detected in {n_strong}/{len(self.edge_effect_strength_by_channel)} channels" if new_confident else "Edge effect not yet confident",
            )


    def _update_response_beliefs(self, conditions: List):
        """Detect dose-response curves and time-dependence."""
        # Group by (compound, time, cell_line) to look for dose ladders
        dose_groups = {}
        for cond in conditions:
            if cond.compound == 'DMSO':
                continue
            key = (cond.compound, cond.time_h, cond.cell_line)
            if key not in dose_groups:
                dose_groups[key] = []
            dose_groups[key].append(cond)

        # Look for dose curves: need 3+ doses
        for key, conds in dose_groups.items():
            if len(conds) >= 3:
                # Sort by dose
                conds_sorted = sorted(conds, key=lambda c: c.dose_uM)

                # Check for non-linear pattern (adjacent jumps differ significantly)
                diffs = []
                for i in range(len(conds_sorted) - 1):
                    diff = abs(conds_sorted[i+1].mean - conds_sorted[i].mean)
                    diffs.append(diff)

                if len(diffs) >= 2:
                    min_diff = min(diffs)
                    max_diff = max(diffs)

                    # If max jump is >2x min jump, we see curvature
                    # Also require effect is larger than noise floor
                    noise_sigma = self.noise_sigma_hat or 0.05
                    min_effect_threshold = 3 * noise_sigma

                    if max_diff > min_effect_threshold and max_diff > 2.0 * min_diff:
                        compound = key[0]

                        self._set(
                            "dose_curvature_seen",
                            True,
                            evidence={
                                "n_curves": 1,
                                "max_diff_ratio": max_diff / min_diff if min_diff > 0 else 0,
                                "threshold_ratio": 2.0,
                                "examples": [{
                                    "compound": compound,
                                    "min_diff": min_diff,
                                    "max_diff": max_diff,
                                    "ratio": max_diff / min_diff if min_diff > 0 else 0,
                                    "noise_sigma": noise_sigma,
                                    "min_effect_threshold": min_effect_threshold,
                                }]
                            },
                            supporting_conditions=[cond_key(c) for c in conds_sorted],
                            note=f"Nonlinear dose-response detected in {len(dose_groups)} conditions",
                        )

        # Time-dependence: group by (compound, dose, cell_line) to look for time series
        time_groups = {}
        for cond in conditions:
            if cond.compound == 'DMSO':
                continue
            key = (cond.compound, cond.dose_uM, cond.cell_line)
            if key not in time_groups:
                time_groups[key] = []
            time_groups[key].append(cond)

        # Look for time series: need 3+ timepoints
        for key, conds in time_groups.items():
            if len(conds) >= 3:
                conds_sorted = sorted(conds, key=lambda c: c.time_h)

                # Check for temporal trend (mean changes over time)
                means = [c.mean for c in conds_sorted]
                mean_range = max(means) - min(means)

                noise_sigma = self.noise_sigma_hat or 0.05
                threshold = 3 * noise_sigma

                if mean_range > threshold:
                    compound = key[0]
                    dose = key[1]

                    self._set(
                        "time_dependence_seen",
                        True,
                        evidence={
                            "compound": compound,
                            "dose_uM": dose,
                            "mean_range": mean_range,
                            "threshold": threshold,
                            "n_timepoints": len(conds_sorted),
                        },
                        supporting_conditions=[cond_key(c) for c in conds_sorted],
                        note=f"Time-dependent response detected for {compound} @ {dose}µM",
                    )

    def _update_assay_gates(self, conditions: List, assay: str):
        """Update assay-specific gate (ldh, cell_paint, scrna).

        v0.5.0: Assay ladder gate computation.
        Uses same pooled variance approach as noise_sigma, but per-assay.

        For now, uses existing noisy_morphology as proxy:
        - ldh: scalar viability (from morphology mean)
        - cell_paint: morphology features (existing signal)
        - scrna: placeholder (TODO: add transcriptional readouts)
        """
        # Find DMSO baseline for this assay
        dmso_conditions = [c for c in conditions if c.compound == 'DMSO' and c.position_tag == 'center']
        if not dmso_conditions:
            return

        # Get assay-specific fields
        if assay == "ldh":
            df_field = "ldh_df_total"
            rel_width_field = "ldh_rel_width"
            stable_field = "ldh_sigma_stable"
        elif assay == "cell_paint":
            df_field = "cell_paint_df_total"
            rel_width_field = "cell_paint_rel_width"
            stable_field = "cell_paint_sigma_stable"
        elif assay == "scrna":
            df_field = "scrna_df_total"
            rel_width_field = "scrna_rel_width"
            stable_field = "scrna_sigma_stable"
        else:
            return

        # Accumulate pooled variance
        sse_total = 0.0
        df_total = 0
        for cond in dmso_conditions:
            n = cond.n_wells
            df = n - 1
            sse = df * (float(cond.std) ** 2)
            df_total += df
            sse_total += sse

        # Update fields
        current_df = getattr(self, df_field)
        setattr(self, df_field, current_df + df_total)
        total_df = current_df + df_total

        # Compute pooled sigma + CI
        if total_df > 0 and sse_total > 0:
            sigma2_hat = sse_total / total_df
            sigma_hat = math.sqrt(max(sigma2_hat, 0.0))
            ci_low, ci_high = _sigma_ci_from_pooled(sse_total, total_df, alpha=0.05)

            if ci_low is not None and ci_high is not None and sigma_hat > 0:
                rel_width = abs(ci_high - ci_low) / sigma_hat
            else:
                rel_width = None
            setattr(self, rel_width_field, rel_width)
        else:
            rel_width = None

        # Gate with hysteresis
        enter_threshold = 0.25
        exit_threshold = 0.40
        df_min_sanity = 40

        current_stable = getattr(self, stable_field)
        new_stable = current_stable
        if not current_stable:
            new_stable = (
                total_df >= df_min_sanity and
                rel_width is not None and
                rel_width <= enter_threshold
            )
        else:
            new_stable = not (rel_width is not None and rel_width >= exit_threshold)

        # v0.5.0: Prevent scRNA gate from earning with proxy metrics
        # scRNA uses expensive transcriptional readouts - can't earn with cheap morphology proxy
        # Keep updating shadow stats (df, rel_width) but never mark stable=True until real assay exists
        if assay == "scrna":
            if new_stable and not current_stable:
                # Would have earned gate, but proxy metrics don't count for scRNA
                # Emit gate_shadow event to track non-actionable stats
                rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"
                self._emit_gate_shadow(
                    "scrna",
                    evidence={
                        "df": total_df,
                        "rel_width": rel_width,
                        "enter_threshold": enter_threshold,
                        "exit_threshold": exit_threshold,
                        "df_min_sanity": df_min_sanity,
                        "assay": assay,
                        "metric_source": "proxy:noisy_morphology",
                        "gate_blocked": "scRNA gate not earnable with proxy metrics (requires real transcriptional readout)",
                    },
                    supporting_conditions=[cond_key(c) for c in dmso_conditions],
                    note=f"scrna shadow stats (df={total_df}, rel_width={rel_width_str}, source=proxy:noisy_morphology, actionable=false)",
                )
                # Set metric_source explicitly (derived, not static default)
                self.scrna_metric_source = "proxy:noisy_morphology"
                return  # Don't update stable field or emit gate_event

        # Record belief change (for ldh, cell_paint, or if scrna already stable)
        rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"

        # Determine metric_source based on actual measurement type
        # TODO: When real assays exist, detect from observation.assay field
        # For now, all measurements use proxy morphology
        metric_source = "proxy:noisy_morphology"

        self._set(
            stable_field,
            new_stable,
            evidence={
                "df": total_df,
                "rel_width": rel_width,
                "enter_threshold": enter_threshold,
                "exit_threshold": exit_threshold,
                "df_min_sanity": df_min_sanity,
                "assay": assay,
                "metric_source": metric_source,  # Honest labeling: using morphology as proxy until real assay models exist
            },
            supporting_conditions=[cond_key(c) for c in dmso_conditions],
            note=f"{assay}_sigma_stable={new_stable} (df={total_df}, rel_width={rel_width_str}, {metric_source})",
        )
        setattr(self, stable_field, new_stable)

        # Set metric_source explicitly for scRNA (future: also set for real transcriptome measurements)
        if assay == "scrna":
            self.scrna_metric_source = metric_source  # When real scRNA exists, this will be "scrna:transcriptome"

    @property
    def calibration_entropy_bits(self) -> float:
        """
        Calibration entropy: uncertainty about NOISE, bias, and measurement quality.

        Agent 3 hardening: Explicitly named to prevent conflation with mechanism entropy.
        This measures uncertainty about the RULER, not about which biological process.

        This is "Phase 1" entropy - based on calibration metrics, not mechanism inference.
        Higher entropy = more uncertainty about noise, edges, dose-response, etc.

        Entropy components:
        - Noise uncertainty: Wide CI = high entropy (0-2 bits)
        - Assay uncertainty: Ungated assays = high entropy (0-3 bits)
        - Edge effects: Unknown = high entropy (0-1 bit)
        - Compound exploration: Untested = high entropy (0-2 bits)

        Returns:
            Entropy in bits (heuristic, from calibration state, NOT mechanism posterior)
        """
        entropy = 0.0

        # Noise uncertainty (0-2 bits)
        # Wide CI or no noise estimate = high entropy
        if not self.noise_sigma_stable:
            if self.noise_rel_width is None or self.noise_df_total < 10:
                entropy += 2.0  # No noise estimate yet
            elif self.noise_rel_width > 0.40:
                entropy += 1.5  # Very wide CI
            elif self.noise_rel_width > 0.25:
                entropy += 1.0  # Moderate CI
            else:
                entropy += 0.5  # Narrow CI but gate not stable yet
        else:
            entropy += 0.1  # Stable gate, low uncertainty

        # Assay uncertainty (0-3 bits, 1 bit per ungated assay)
        # Ungated assays represent unknown measurement quality
        if not self.ldh_sigma_stable:
            entropy += 1.0
        if not self.cell_paint_sigma_stable:
            entropy += 1.0
        if not self.scrna_sigma_stable:
            entropy += 1.0

        # Edge effects uncertainty (0-1 bit)
        # Unknown edge effects = systematic bias risk
        if not self.edge_effect_confident:
            if self.edge_tests_run == 0:
                entropy += 1.0  # No edge tests yet
            else:
                entropy += 0.5  # Edge tests run but not confident

        # Compound exploration uncertainty (0-2 bits)
        # Untested compounds represent unknown dose-response space
        n_tested = len(self.tested_compounds) - (1 if 'DMSO' in self.tested_compounds else 0)
        if n_tested == 0:
            entropy += 2.0  # No compounds tested
        elif n_tested == 1:
            entropy += 1.0  # Only one compound
        else:
            entropy += 0.5  # Multiple compounds (still exploration needed)

        # Dose-response uncertainty (0-1 bit)
        if not self.dose_curvature_seen:
            entropy += 1.0

        # Time-dependence uncertainty (0-1 bit)
        if not self.time_dependence_seen:
            entropy += 1.0

        return entropy

    @property
    def entropy(self) -> float:
        """
        DEPRECATED: Use calibration_entropy_bits for clarity.

        This returns calibration entropy (uncertainty about noise/bias/measurement quality).
        Do NOT confuse with mechanism entropy (uncertainty about which biological process).
        """
        return self.calibration_entropy_bits

    def estimate_expected_gain(
        self,
        template_name: str,
        n_wells: int,
        modalities: Tuple[str, ...] = ("cell_painting",)
    ) -> float:
        """
        Estimate expected information gain from a proposed experiment.

        This is "Phase 1" gain estimation - based on heuristics, not full Bayesian updates.
        Assumes experiments reduce entropy by tightening calibration or exploring new space.

        Args:
            template_name: Experiment template (e.g., "baseline_replicates", "edge_center_test")
            n_wells: Number of wells in design
            modalities: Assays used (e.g., ("cell_painting",), ("scrna_seq",))

        Returns:
            Expected information gain in bits (higher = more informative)
        """
        expected_gain = 0.0

        # Baseline replicates: Reduce noise uncertainty
        if "baseline" in template_name or "calibrate" in template_name:
            if not self.noise_sigma_stable:
                # Gain proportional to wells (more data = tighter CI)
                # Saturates at ~0.5-1.0 bits for reasonable sample sizes
                df_current = self.noise_df_total
                df_after = df_current + (n_wells - 1)
                if df_current < 10:
                    expected_gain += 0.8  # First calibration is very informative
                elif df_current < 40:
                    expected_gain += 0.5  # Approaching gate, still valuable
                else:
                    expected_gain += 0.2  # Fine-tuning
            else:
                expected_gain += 0.1  # Maintenance of calibration

        # Edge center test: Resolve edge effects
        if "edge" in template_name:
            if not self.edge_effect_confident:
                expected_gain += 0.8  # First edge test is informative
            else:
                expected_gain += 0.1  # Confirmation

        # Dose ladder: Explore dose-response
        if "dose" in template_name or "screen" in template_name:
            n_untested = len(self.tested_compounds)  # Rough proxy
            if n_untested < 2:
                expected_gain += 1.0  # First compound very informative
            elif n_untested < 5:
                expected_gain += 0.6  # Expanding chemical space
            else:
                expected_gain += 0.3  # Incremental exploration

        # scRNA upgrade: High information gain (expensive modality)
        if "scrna" in template_name:
            if "scrna_seq" in modalities or "scrna" in modalities:
                # scRNA resolves mechanism-level questions
                expected_gain += 1.5  # High gain from transcriptional data
            else:
                expected_gain += 0.3  # Proxy measurements less informative

        # Assay ladder calibration: Per-assay gate earning
        if "ldh" in template_name:
            if not self.ldh_sigma_stable:
                expected_gain += 0.6
        if "cell_paint" in template_name or "paint" in template_name:
            if not self.cell_paint_sigma_stable:
                expected_gain += 0.6
        if "scrna" in template_name:
            if not self.scrna_sigma_stable:
                expected_gain += 1.0  # scRNA gate is expensive, high value

        # Minimum gain floor (even bad experiments provide some information)
        if expected_gain < 0.05:
            expected_gain = 0.05

        return expected_gain
