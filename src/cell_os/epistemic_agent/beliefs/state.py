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

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
import math
import numpy as np
from .ledger import EvidenceEvent, cond_key


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
    
    # Evidence ledger
    _cycle: int = 0
    _events: List[EvidenceEvent] = field(default_factory=list)
    
    def begin_cycle(self, cycle: int):
        """Start a new cycle (clear event buffer)."""
        self._cycle = cycle
        self._events = []
    
    def end_cycle(self) -> List[EvidenceEvent]:
        """Return events from this cycle."""
        return self._events

    def _set(
        self,
        field_name: str,
        new_value: Any,
        *,
        evidence: Dict[str, Any],
        supporting_conditions: List[str],
        note: Optional[str] = None,
    ):
        """Set a belief field and record evidence if it changed.

        This is the core accountability mechanism: every belief flip gets a receipt.
        """
        prev_value = getattr(self, field_name)

        if prev_value == new_value:
            return  # No change, no event

        setattr(self, field_name, new_value)

        self._events.append(EvidenceEvent(
            cycle=self._cycle,
            belief=field_name,
            prev=prev_value,
            new=new_value,
            evidence=evidence,
            supporting_conditions=supporting_conditions,
            note=note,
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
                self._emit_gate_loss(
                    "noise_sigma",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: noise_sigma (rel_width={evidence.get('rel_width'):.4f if evidence.get('rel_width') else 'N/A'}, drift={evidence.get('drift_metric'):.4f if evidence.get('drift_metric') else 'N/A'})",
                )
            elif field_name == "edge_effect_confident":
                self._emit_gate_loss(
                    "edge_effect",
                    prev=prev_value,
                    new=new_value,
                    evidence=evidence,
                    supporting_conditions=supporting_conditions,
                    note=f"Gate lost: edge_effect (n_tests={evidence.get('n_tests')}, mean_abs_effect={evidence.get('mean_abs_effect'):.4f if evidence.get('mean_abs_effect') else 0.0})",
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
            enter_threshold = 0.25
            exit_threshold = 0.40
            df_min_sanity = 40  # Sanity floor: prevent nonsense claims at tiny df
            drift_threshold = 0.20

            drift_bad = (drift_metric is not None and drift_metric >= drift_threshold)

            # Gate: primary criterion is rel_width, df_min_sanity just prevents stupidity
            new_stable = self.noise_sigma_stable
            if not self.noise_sigma_stable:
                new_stable = (
                    self.noise_df_total >= df_min_sanity and
                    rel_width is not None and
                    rel_width <= enter_threshold and
                    not drift_bad
                )
            else:
                # only exit if clearly degraded or drifting
                new_stable = not (
                    drift_bad or
                    (rel_width is not None and rel_width >= exit_threshold)
                )

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
                    f"rel_width={rel_width_str}, drift={drift_str})"
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
                # Update shadow stats but keep stable=False
                rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"
                self._set(
                    stable_field,
                    False,  # Force False for proxy scRNA
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
                    note=f"scrna shadow stats updated (df={total_df}, rel_width={rel_width_str}, proxy:noisy_morphology, gate_blocked)",
                )
                setattr(self, stable_field, False)
                return  # Don't emit gate_event

        # Record belief change (for ldh, cell_paint, or if scrna already stable)
        rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"
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
                "metric_source": "proxy:noisy_morphology",  # Honest labeling: using morphology as proxy until real assay models exist
            },
            supporting_conditions=[cond_key(c) for c in dmso_conditions],
            note=f"{assay}_sigma_stable={new_stable} (df={total_df}, rel_width={rel_width_str}, proxy:noisy_morphology)",
        )
        setattr(self, stable_field, new_stable)
