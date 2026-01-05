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
from ..exceptions import (
    BeliefLedgerInvariantError,
    ExecutionIntegrityState,
    IntegrityViolation,
)


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

    # Cycle 0: Instrument shape learning (from calibration plate)
    instrument_shape: Optional[Any] = None  # InstrumentShapeSummary (use Any to avoid circular import)
    instrument_shape_learned: bool = False  # True after Cycle 0 calibration plate
    calibration_plate_run: bool = False     # True if canonical calibration plate executed

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

    # Execution integrity tracking (plate map error detection)
    execution_integrity: ExecutionIntegrityState = field(default_factory=ExecutionIntegrityState)

    # Health debt tracking (instrument quality degradation)
    # Debt accumulates from QC violations (Moran's I excess, nuclei CV excess)
    # Decays with mitigation actions or high-quality runs
    # Influences policy: high debt → prefer calibration over exploration
    health_debt: float = 0.0  # Accumulated quality debt (unitless, ~0-10 range)
    health_debt_history: List[float] = field(default_factory=list)  # Per-cycle tracking

    # Gain estimation aggressiveness (1.0 = conservative default, >1.0 = optimistic, <1.0 = pessimistic)
    # Higher values will overclaim expected gain, triggering debt enforcement
    # Useful for testing debt enforcement and simulating aggressive agents
    gain_estimate_multiplier: float = 1.0

    # Calibration uncertainty tracking (epistemic maintenance)
    # Measures ignorance about measurement quality (distinct from health debt = damage)
    # Increases with time since calibration and drift signals
    # Decreases after calibration proportional to QC cleanliness
    # Influences policy: high uncertainty → prefer calibration over exploration
    calibration_uncertainty: float = 0.5  # Uncertainty about measurement quality [0, 1]
    cycles_since_calibration: int = 0  # Time since last calibration
    last_calibration_cycle: Optional[int] = None  # Cycle when last calibrated
    last_action: Optional[str] = None  # Last epistemic action (for hysteresis)

    # Evidence ledger
    _cycle: int = 0
    _events: List[EvidenceEvent] = field(default_factory=list)

    # Agent 1: Temporal provenance tracking
    _current_evidence_time_h: Optional[float] = None  # Set during update() from observation

    # Belief updaters (initialized in __post_init__)
    _noise_updater: Any = field(default=None, init=False, repr=False)
    _edge_updater: Any = field(default=None, init=False, repr=False)
    _response_updater: Any = field(default=None, init=False, repr=False)
    _assay_gate_updater: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize belief updaters."""
        # Lazy import to avoid circular dependencies
        from .updates import (
            NoiseBeliefUpdater,
            EdgeBeliefUpdater,
            ResponseBeliefUpdater,
            AssayGateUpdater,
        )

        self._noise_updater = NoiseBeliefUpdater(self)
        self._edge_updater = EdgeBeliefUpdater(self)
        self._response_updater = ResponseBeliefUpdater(self)
        self._assay_gate_updater = AssayGateUpdater(self)

    def begin_cycle(self, cycle: int):
        """Start a new cycle (clear event buffer).

        GUARDRAIL: Enforces strict integer cycle type (temporal provenance).
        This is a TypeError (not assert) because temporal ordering is mission-critical
        and must not be disabled by -O flag.

        SEMANTIC CONTRACT:
        - Cycles are integers (no floats, no subcycles)
        - Cycles must be monotonically increasing
        - Mitigation consumes a whole integer cycle
        - Beliefs requires strict temporal ordering for causal attribution
        """
        if not isinstance(cycle, int):
            raise TypeError(f"Cycle must be int, got {type(cycle)}: {cycle}")

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

        # Agent 1.5: Strengthen temporal causality enforcement
        # If claim_time_h is specified, evidence_time_h MUST be present
        # (Can only make claims about states at or before observation time)
        if claim_time_h is not None:
            if final_evidence_time_h is None:
                from ..exceptions import TemporalProvenanceError
                raise TemporalProvenanceError(
                    message=(
                        f"Attempted to update belief '{field_name}' about timepoint {claim_time_h}h "
                        f"but evidence_time_h is None; cannot enforce temporal causality"
                    ),
                    missing_field="evidence_time_h",
                    context="BeliefState._set()",
                    cycle=self._cycle,
                    details={
                        "belief_name": field_name,
                        "claim_time_h": claim_time_h,
                        "prev_value": prev_value,
                        "new_value": new_value,
                    }
                )

            # Rule: claim_time_h <= evidence_time_h
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

        # Convert sets to sorted lists for JSON serialization
        prev_serializable = sorted(list(prev_value)) if isinstance(prev_value, set) else prev_value
        new_serializable = sorted(list(new_value)) if isinstance(new_value, set) else new_value

        self._events.append(EvidenceEvent(
            cycle=self._cycle,
            belief=field_name,
            prev=prev_serializable,
            new=new_serializable,
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
                rel_width_val = evidence.get('rel_width')
                rel_width_str = f"{rel_width_val:.4f}" if rel_width_val is not None else "N/A"
                self._emit_gate_loss(
                    "ldh",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: ldh (rel_width={rel_width_str}, proxy:noisy_morphology)",
                )
            elif field_name == "cell_paint_sigma_stable":
                rel_width_val = evidence.get('rel_width')
                rel_width_str = f"{rel_width_val:.4f}" if rel_width_val is not None else "N/A"
                self._emit_gate_loss(
                    "cell_paint",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: cell_paint (rel_width={rel_width_str}, proxy:noisy_morphology)",
                )
            elif field_name == "scrna_sigma_stable":
                rel_width_val = evidence.get('rel_width')
                rel_width_str = f"{rel_width_val:.4f}" if rel_width_val is not None else "N/A"
                self._emit_gate_loss(
                    "scrna",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: scrna (rel_width={rel_width_str}, proxy:noisy_morphology)",
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

    def _extract_evidence_time_h_from_conditions(self, conditions: List) -> float:
        """Extract evidence_time_h from conditions with strict validation.

        Agent 1.5: Temporal Provenance Enforcement.

        This method enforces that every observation has valid temporal metadata.
        If time is missing or malformed, temporal causality enforcement would be
        bypassed silently. This is not allowed.

        Args:
            conditions: List of ConditionSummary objects

        Returns:
            float: Maximum time_h from all conditions (most conservative for causality)

        Raises:
            TemporalProvenanceError: If conditions are empty or any lack time_h
        """
        from ..exceptions import TemporalProvenanceError

        if not conditions:
            raise TemporalProvenanceError(
                message="Observation has no conditions; cannot derive evidence_time_h",
                missing_field="time_h",
                context="BeliefState.update()",
                cycle=self._cycle,
                details={"observation": "empty conditions list"}
            )

        missing_indices = []
        times = []

        for i, cond in enumerate(conditions):
            if not hasattr(cond, "time_h"):
                missing_indices.append(i)
                continue

            t = getattr(cond, "time_h")
            if t is None:
                missing_indices.append(i)
                continue

            times.append(float(t))

        if missing_indices:
            raise TemporalProvenanceError(
                message=(
                    f"One or more conditions missing time_h (indices={missing_indices}); "
                    "temporal enforcement would be bypassed"
                ),
                missing_field="time_h",
                context="BeliefState.update()",
                cycle=self._cycle,
                details={"missing_indices": missing_indices, "n_conditions": len(conditions)}
            )

        if not times:
            raise TemporalProvenanceError(
                message="No valid time_h values found in conditions; cannot derive evidence_time_h",
                missing_field="time_h",
                context="BeliefState.update()",
                cycle=self._cycle,
                details={"n_conditions": len(conditions)}
            )

        return max(times)

    def update(self, observation, cycle: int = 0):
        """Update beliefs from a new observation.

        Args:
            observation: Observation object with conditions (List[ConditionSummary])
            cycle: Current cycle number (for diagnostics)

        Returns:
            (events, diagnostics): Event lists for ledgers

        Raises:
            TemporalProvenanceError: If observation lacks temporal metadata
        """
        # Extract conditions from observation
        conditions = observation.conditions if hasattr(observation, 'conditions') else []

        # Agent 1.5: Strict extraction of evidence_time_h (cannot be None)
        # This enforces temporal provenance and prevents silent bypass
        evidence_time_h = self._extract_evidence_time_h_from_conditions(conditions)
        self._current_evidence_time_h = evidence_time_h

        # Use condition keys for evidence tracking
        condition_keys = [cond_key(c) for c in conditions]

        # Track total observations
        self._set(
            "total_observations",
            self.total_observations + 1,
            evidence={"observation_count": len(conditions)},
            supporting_conditions=condition_keys,
            note=f"Observation #{self.total_observations + 1}"
        )

        # Track compounds and cell lines
        new_compounds = set(self.tested_compounds)
        new_cell_lines = set(self.tested_cell_lines)
        for cond in conditions:
            new_compounds.add(cond.compound)
            new_cell_lines.add(cond.cell_line)

        # Note: Store as sets internally but only update if changed
        # _set() will detect changes and emit events appropriately
        if new_compounds != self.tested_compounds:
            self._set(
                "tested_compounds",
                new_compounds,
                evidence={"n_compounds": len(new_compounds), "compounds": sorted(list(new_compounds))},
                supporting_conditions=condition_keys,
                note=f"Tested {len(new_compounds)} compounds"
            )

        if new_cell_lines != self.tested_cell_lines:
            self._set(
                "tested_cell_lines",
                new_cell_lines,
                evidence={"n_cell_lines": len(new_cell_lines), "cell_lines": sorted(list(new_cell_lines))},
                supporting_conditions=condition_keys,
                note=f"Tested {len(new_cell_lines)} cell lines"
            )

        # Update beliefs using modular updaters
        diagnostics_out = []
        self._noise_updater.update(conditions, diagnostics_out)
        self._edge_updater.update(conditions)
        self._response_updater.update(conditions)

        # v0.5.0: Update assay-specific gates (measurement ladder)
        self._assay_gate_updater.update(conditions, "ldh")
        self._assay_gate_updater.update(conditions, "cell_paint")
        self._assay_gate_updater.update(conditions, "scrna")

        # Execution integrity: consume from observation (computed at aggregation boundary)
        if hasattr(observation, 'execution_integrity') and observation.execution_integrity is not None:
            self._update_execution_integrity_from_observation(observation.execution_integrity, cycle)

        return (self._events, diagnostics_out)

    def update_from_instrument_shape(self, shape_summary, cycle: int = 0):
        """Update trust model from calibration plate instrument shape summary.

        This is the ONLY way noise gate can be earned from Cycle 0 calibration.

        Args:
            shape_summary: InstrumentShapeSummary from compute_instrument_shape_summary()
            cycle: Current cycle number

        Emits three events:
            1. calibration_plate_selected (from chooser, before execution)
            2. instrument_shape_summary (this method, after execution)
            3. noise_gate_updated (this method, based on pass/fail)
        """
        # Store instrument shape
        self.instrument_shape = shape_summary
        self.instrument_shape_learned = True
        self.calibration_plate_run = True

        # Event 2: instrument_shape_summary (trust audit breadcrumb)
        evidence_dict = {
            "plate_id": shape_summary.plate_id,
            "noise_sigma": shape_summary.noise_sigma,
            "edge_effect_strength": shape_summary.edge_effect_strength,
            "spatial_residual_metric": shape_summary.spatial_residual_metric,
            "replicate_precision_score": shape_summary.replicate_precision_score,
            "channel_coupling_score": shape_summary.channel_coupling_score,
            "pass": shape_summary.noise_gate_pass,
            "failed_checks": shape_summary.failed_checks,
        }

        # Include spatial diagnostic for heatmap rendering (if available)
        if shape_summary.spatial_diagnostic:
            evidence_dict["spatial_diagnostic"] = shape_summary.spatial_diagnostic

        self._set(
            "instrument_shape",
            shape_summary,
            evidence=evidence_dict,
            supporting_conditions=[],
            note=f"Instrument shape learned from {shape_summary.plate_id}"
        )

        # Event 3: noise_gate_updated
        previous_status = "earned" if self.noise_sigma_stable else "lost"
        new_status = "earned" if shape_summary.noise_gate_pass else "lost"

        # Update gate status
        if shape_summary.noise_gate_pass:
            self._set(
                "noise_sigma_stable",
                True,
                evidence={
                    "gate_event": "noise_sigma_stable",
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "shape_metrics": {
                        "noise_sigma": shape_summary.noise_sigma,
                        "edge_effect": shape_summary.edge_effect_strength,
                        "spatial_residual": shape_summary.spatial_residual_metric,
                        "replicate_precision": shape_summary.replicate_precision_score,
                    },
                    # Provide expected fields for _emit_gate_event formatting
                    "rel_width": shape_summary.noise_sigma_ci_width,
                    "pooled_df": shape_summary.noise_sigma_df,
                },
                supporting_conditions=[],
                note=f"Noise gate earned via instrument shape learning (Cycle 0)"
            )
        else:
            self._set(
                "noise_sigma_stable",
                False,
                evidence={
                    "gate_loss": "noise_sigma_stable",
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "failed_checks": shape_summary.failed_checks,
                },
                supporting_conditions=[],
                note=f"Noise gate NOT earned: {', '.join(shape_summary.failed_checks)}"
            )

    # Legacy update methods removed - now delegated to updater classes
    # See beliefs/updates/ for implementation

    def update_execution_integrity(self, conditions: List, cycle: int) -> None:
        """
        Check for execution integrity violations (plate map errors).

        This method computes a new ExecutionIntegrityState by running sanity checks:
        - Anchor position verification (are known compounds in expected wells?)
        - Replicate clustering (do replicates produce similar phenotypes?)
        - Dose monotonicity (is dose-response curve sensible?)

        Design principles:
        - Violations are facts (measurable signals)
        - Severity is aggregate judgment (based on violation count and consistency)
        - Action is policy recommendation (not hardcoded here)
        - Hysteresis prevents noise-triggered halts

        Args:
            conditions: List of conditions from current observation
            cycle: Current cycle number (for hysteresis tracking)
        """
        # Compute new integrity state by running all checks
        new_state = self._compute_execution_integrity_state(conditions, cycle)

        # Use _set() to record state change with evidence
        condition_keys = [cond_key(c) for c in conditions]

        self._set(
            "execution_integrity",
            new_state,
            evidence={
                "violations": [v.code for v in new_state.violations],
                "severity": new_state.severity,
                "recommended_action": new_state.recommended_action,
                "consecutive_bad_checks": new_state.consecutive_bad_checks,
                "consecutive_good_checks": new_state.consecutive_good_checks,
            },
            supporting_conditions=condition_keys,
            note=f"Integrity: {new_state.severity} ({len(new_state.violations)} violations: {[v.code for v in new_state.violations]})",
        )

    def _compute_execution_integrity_state(
        self,
        conditions: List,
        cycle: int
    ) -> ExecutionIntegrityState:
        """
        Compute new execution integrity state from observations.

        This is where the actual sanity checks run. Each check returns
        an IntegrityViolation or None.

        Returns:
            ExecutionIntegrityState with violations, severity, and recommended action
        """
        # Start with current state for hysteresis
        prev_state = self.execution_integrity

        # Run all sanity checks
        violations: List[IntegrityViolation] = []

        # TODO: Implement actual checkers (next phase)
        # violations.extend(self._check_anchor_positions(conditions) or [])
        # violations.extend(self._check_replicate_clustering(conditions) or [])
        # violations.extend(self._check_dose_monotonicity(conditions) or [])

        # Aggregate severity based on violations
        severity, recommended_action = self._compute_integrity_severity(
            violations=violations,
            prev_state=prev_state
        )

        # Update hysteresis counters
        consecutive_bad = prev_state.consecutive_bad_checks
        consecutive_good = prev_state.consecutive_good_checks

        if len(violations) > 0:
            consecutive_bad += 1
            consecutive_good = 0
        else:
            consecutive_bad = 0
            consecutive_good += 1

        return ExecutionIntegrityState(
            suspect=(len(violations) > 0),
            severity=severity,
            recommended_action=recommended_action,
            violations=violations,
            last_check_cycle=cycle,
            consecutive_bad_checks=consecutive_bad,
            consecutive_good_checks=consecutive_good,
            diagnosis_in_progress=prev_state.diagnosis_in_progress,
            last_diagnostic_template=prev_state.last_diagnostic_template,
            last_diagnostic_result=prev_state.last_diagnostic_result,
        )

    def _compute_integrity_severity(
        self,
        violations: List[IntegrityViolation],
        prev_state: ExecutionIntegrityState
    ) -> Tuple[str, str]:
        """
        Compute aggregate severity and recommended action from violations.

        Escalation rules:
        - 0 violations: "none", "continue"
        - 1 violation (first occurrence): "warning", "cautious"
        - 1 violation (2+ consecutive): "halt", "diagnose"
        - 2+ violations: "halt", "diagnose"
        - Any "fatal" violation: "fatal", "hard_halt"

        Args:
            violations: List of detected violations
            prev_state: Previous execution integrity state (for hysteresis)

        Returns:
            (severity, recommended_action) tuple
        """
        if not violations:
            # No violations: clear or stay clear
            if prev_state.consecutive_good_checks >= 2:
                return ("none", "continue")
            else:
                # Still in recovery period
                return (prev_state.severity, "continue")

        # Check for any fatal-level violations
        fatal_violations = [v for v in violations if v.severity == "fatal"]
        if fatal_violations:
            return ("fatal", "hard_halt")

        # Multiple violations or sustained single violation
        n_violations = len(violations)
        if n_violations >= 2:
            return ("halt", "diagnose")

        # Single violation: check hysteresis
        if prev_state.consecutive_bad_checks >= 1:
            # Sustained violation
            return ("halt", "diagnose")
        else:
            # First occurrence
            return ("warning", "cautious")

    def _update_execution_integrity_from_observation(
        self,
        integrity_state_from_obs: ExecutionIntegrityState,
        cycle: int
    ) -> None:
        """
        Update execution integrity from pre-computed state (from observation).

        This applies hysteresis to the state computed at the aggregation boundary
        and records it with full provenance via _set().

        Args:
            integrity_state_from_obs: Pre-computed state from observation_aggregator
            cycle: Current cycle number
        """
        prev_state = self.execution_integrity

        # Apply hysteresis: track consecutive good/bad checks
        if len(integrity_state_from_obs.violations) > 0:
            consecutive_bad = prev_state.consecutive_bad_checks + 1
            consecutive_good = 0
        else:
            consecutive_bad = 0
            consecutive_good = prev_state.consecutive_good_checks + 1

        # Re-compute severity with hysteresis
        # If we have consecutive bad checks, escalate severity
        violations = integrity_state_from_obs.violations
        if consecutive_bad >= 2 and len(violations) > 0:
            # Sustained violation → escalate to halt
            severity = "halt"
            recommended_action = "diagnose"
        elif consecutive_good >= 2 and not violations:
            # Sustained clean state → clear
            severity = "none"
            recommended_action = "continue"
        else:
            # Use the severity from observation (first occurrence or recovery)
            severity = integrity_state_from_obs.severity
            recommended_action = integrity_state_from_obs.recommended_action

        # Build final state with hysteresis applied
        final_state = ExecutionIntegrityState(
            suspect=(len(violations) > 0),
            severity=severity,
            recommended_action=recommended_action,
            violations=violations,
            last_check_cycle=cycle,
            consecutive_bad_checks=consecutive_bad,
            consecutive_good_checks=consecutive_good,
            diagnosis_in_progress=prev_state.diagnosis_in_progress,
            last_diagnostic_template=prev_state.last_diagnostic_template,
            last_diagnostic_result=prev_state.last_diagnostic_result,
        )

        # Record with provenance
        self._set(
            "execution_integrity",
            final_state,
            evidence={
                "violations": [v.code for v in final_state.violations],
                "severity": final_state.severity,
                "recommended_action": final_state.recommended_action,
                "consecutive_bad_checks": consecutive_bad,
                "consecutive_good_checks": consecutive_good,
            },
            supporting_conditions=[],  # Well-level QC, no condition keys
            note=f"Integrity: {final_state.severity} ({len(final_state.violations)} violations: {[v.code for v in final_state.violations]})"
        )

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

    def estimate_calibration_uncertainty(self) -> float:
        """
        Return current calibration uncertainty (bits).

        This measures uncertainty about MEASUREMENT QUALITY:
        - Noise (CI width on pooled sigma)
        - Edge effects (detection confidence)
        - Assay gates (LDH, Cell Painting, scRNA)
        - Dose-response patterns (curvature, time dependence)
        - Exploration coverage (untested compounds)

        This does NOT measure biological parameter uncertainty (IC50, mechanism).

        Uses existing calibration_entropy_bits property which aggregates:
        - Noise uncertainty (0-2 bits): wide CI → high entropy
        - Assay uncertainty (0-3 bits): ungated assays → high entropy
        - Edge effect uncertainty (0-1 bit): unknown edges → high entropy
        - Exploration uncertainty (0-2 bits): untested compounds → high entropy
        - Pattern uncertainty (0-2 bits): no dose curvature/time trends → high entropy

        Typical range: 0-10 bits
        - High (>6 bits): ruler uncertain, replicate to tighten
        - Medium (3-6 bits): transitional
        - Low (<3 bits): ruler confident, safe to expand

        Returns:
            Calibration uncertainty in bits
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

        # Apply aggressiveness multiplier (for testing debt enforcement)
        # 1.0 = default (conservative), >1.0 = overclaim (aggressive)
        return expected_gain * self.gain_estimate_multiplier

    def accumulate_health_debt(
        self,
        morans_i: Optional[float] = None,
        nuclei_cv: Optional[float] = None,
        segmentation_quality: Optional[float] = None
    ) -> float:
        """
        Accumulate health debt from QC violations.

        Health debt represents instrument quality degradation that must be paid down
        through mitigation (replating, recalibration) or high-quality runs.

        Design:
        - Debt grows from excess spatial autocorrelation (Moran's I > 0.15)
        - Debt grows from excess nuclei CV (> 0.20)
        - Debt grows from poor segmentation quality (< 0.80)
        - Debt is additive: multiple violations compound

        Args:
            morans_i: Spatial autocorrelation (0-1, flagged if > 0.15)
            nuclei_cv: Nuclei count CV (flagged if > 0.20)
            segmentation_quality: Segmentation quality score (flagged if < 0.80)

        Returns:
            Debt increment added this cycle
        """
        debt_increment = 0.0

        # Spatial QC: Moran's I excess
        if morans_i is not None and morans_i > 0.15:
            # Debt proportional to excess over threshold
            excess = morans_i - 0.15
            debt_increment += excess * 10.0  # Scale to ~1-2 units per violation

        # Nuclei CV excess
        if nuclei_cv is not None and nuclei_cv > 0.20:
            excess = nuclei_cv - 0.20
            debt_increment += excess * 5.0

        # Segmentation quality deficit
        if segmentation_quality is not None and segmentation_quality < 0.80:
            deficit = 0.80 - segmentation_quality
            debt_increment += deficit * 3.0

        if debt_increment > 0:
            self.health_debt += debt_increment
            self.health_debt_history.append(self.health_debt)

            # Emit evidence event
            self._set(
                "health_debt",
                self.health_debt,
                evidence={
                    "debt_increment": debt_increment,
                    "morans_i": morans_i,
                    "nuclei_cv": nuclei_cv,
                    "segmentation_quality": segmentation_quality,
                },
                supporting_conditions=[],
                note=f"Health debt accumulated: +{debt_increment:.2f} (total: {self.health_debt:.2f})"
            )

        return debt_increment

    def decay_health_debt(
        self,
        decay_rate: float = 0.2,
        reason: str = "high_quality_run"
    ) -> float:
        """
        Decay health debt after high-quality runs or mitigation.

        Design:
        - Natural decay: clean runs reduce debt by fixed percentage (default 20%)
        - Mitigation decay: replating/recalibration can apply larger decay
        - Debt floor: never goes below 0

        Args:
            decay_rate: Fraction of debt to remove (0-1, default 0.2)
            reason: Why debt is decaying ("high_quality_run", "mitigation_replate", etc.)

        Returns:
            Amount of debt repaid
        """
        if self.health_debt <= 0:
            return 0.0

        repayment = self.health_debt * decay_rate
        self.health_debt = max(0.0, self.health_debt - repayment)
        self.health_debt_history.append(self.health_debt)

        # Emit evidence event
        self._set(
            "health_debt",
            self.health_debt,
            evidence={
                "repayment": repayment,
                "decay_rate": decay_rate,
                "reason": reason,
            },
            supporting_conditions=[],
            note=f"Health debt repaid: -{repayment:.2f} ({reason}, remaining: {self.health_debt:.2f})"
        )

        return repayment

    def get_health_debt_pressure(self) -> str:
        """
        Return policy guidance based on current health debt.

        Returns:
            "low" (< 2.0): safe to explore
            "medium" (2.0-5.0): prefer calibration
            "high" (> 5.0): urgent mitigation needed
        """
        if self.health_debt < 2.0:
            return "low"
        elif self.health_debt < 5.0:
            return "medium"
        else:
            return "high"

    def advance_cycle_uncertainty(self):
        """
        Advance calibration uncertainty by one cycle (time-based drift).

        Uncertainty increases with time since calibration as a drift prior.
        This models the fact that instrument state changes over time.
        """
        self.cycles_since_calibration += 1

        # Drift prior: uncertainty grows slowly with time
        # Cap at 1.0 (full uncertainty)
        drift_rate = 0.05  # +5% uncertainty per cycle without calibration
        self.calibration_uncertainty = min(1.0, self.calibration_uncertainty + drift_rate)

    def update_calibration_uncertainty_from_signals(
        self,
        morans_i: Optional[float] = None,
        nuclei_cv: Optional[float] = None,
        segmentation_quality: Optional[float] = None
    ):
        """
        Update calibration uncertainty from QC signals (volatility indicators).

        Uncertainty increases when QC signals show instability or drift.
        This is distinct from health_debt (which tracks damage).

        Args:
            morans_i: Spatial autocorrelation (instability if high)
            nuclei_cv: Nuclei count CV (instability if high)
            segmentation_quality: Segmentation quality (instability if low)
        """
        uncertainty_increment = 0.0

        # Spatial instability
        if morans_i is not None and morans_i > 0.15:
            excess = morans_i - 0.15
            uncertainty_increment += excess * 0.5  # Scale to ~0-0.1 range

        # Nuclei CV instability
        if nuclei_cv is not None and nuclei_cv > 0.20:
            excess = nuclei_cv - 0.20
            uncertainty_increment += excess * 0.3

        # Segmentation instability
        if segmentation_quality is not None and segmentation_quality < 0.80:
            deficit = 0.80 - segmentation_quality
            uncertainty_increment += deficit * 0.2

        if uncertainty_increment > 0:
            self.calibration_uncertainty = min(1.0, self.calibration_uncertainty + uncertainty_increment)

            # Emit evidence event
            self._set(
                "calibration_uncertainty",
                self.calibration_uncertainty,
                evidence={
                    "uncertainty_increment": uncertainty_increment,
                    "morans_i": morans_i,
                    "nuclei_cv": nuclei_cv,
                    "segmentation_quality": segmentation_quality,
                },
                supporting_conditions=[],
                note=f"Calibration uncertainty increased: +{uncertainty_increment:.3f} (total: {self.calibration_uncertainty:.3f})"
            )

    def apply_calibration_result(
        self,
        calibration_metrics: dict,
        cycle: int
    ):
        """
        Apply calibration result to beliefs (reduce uncertainty, decay debt).

        Calibration reduces uncertainty proportional to QC cleanliness.
        Also decays health debt modestly if calibration was clean.

        Args:
            calibration_metrics: Dict with keys: morans_i, nuclei_cv, segmentation_quality, noise_rel_width
            cycle: Current cycle number
        """
        # Extract cleanliness metrics
        morans_i = calibration_metrics.get('morans_i', 0.1)
        nuclei_cv = calibration_metrics.get('nuclei_cv', 0.15)
        segmentation_quality = calibration_metrics.get('segmentation_quality', 0.85)
        noise_rel_width = calibration_metrics.get('noise_rel_width')

        # Compute cleanliness score [0, 1] (1 = perfect)
        # Perfect: Moran's I < 0.10, nuclei_cv < 0.15, segmentation > 0.85
        cleanliness = 1.0
        if morans_i > 0.10:
            cleanliness -= (morans_i - 0.10) * 2.0  # Penalty for spatial autocorrelation
        if nuclei_cv > 0.15:
            cleanliness -= (nuclei_cv - 0.15) * 1.5  # Penalty for variability
        if segmentation_quality < 0.85:
            cleanliness -= (0.85 - segmentation_quality) * 1.0  # Penalty for poor segmentation

        cleanliness = max(0.0, min(1.0, cleanliness))

        # Reduce uncertainty proportional to cleanliness
        # Perfect calibration reduces uncertainty to ~0.1
        # Poor calibration barely reduces uncertainty
        uncertainty_reduction = self.calibration_uncertainty * (0.5 + 0.4 * cleanliness)  # 50-90% reduction
        new_uncertainty = max(0.1, self.calibration_uncertainty - uncertainty_reduction)

        self._set(
            "calibration_uncertainty",
            new_uncertainty,
            evidence={
                "cleanliness_score": cleanliness,
                "uncertainty_reduction": uncertainty_reduction,
                "calibration_metrics": calibration_metrics,
            },
            supporting_conditions=[],
            note=f"Calibration applied: uncertainty {self.calibration_uncertainty:.3f} → {new_uncertainty:.3f} (cleanliness={cleanliness:.2f})"
        )

        # Reset cycles counter
        self.cycles_since_calibration = 0
        self.last_calibration_cycle = cycle

        # Decay health debt modestly if calibration was clean
        if cleanliness > 0.6:
            # Clean calibration suggests instrument is healthy, decay debt
            decay_rate = 0.3 * cleanliness  # Up to 30% decay for perfect calibration
            self.decay_health_debt(decay_rate=decay_rate, reason="calibration")
