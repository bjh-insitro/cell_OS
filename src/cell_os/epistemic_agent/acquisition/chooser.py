"""
Template chooser with pay-for-calibration regime and measurement ladder.

v0.5.0: Assay-specific gates with ladder constraints.
- LDH, Cell Painting, scRNA gates enforced independently
- Ladder rule: scRNA requires CP gate earned first
- Fail-fast affordability checks per assay
- Complete decision provenance for upgrades

v0.4.2: Baseline noise gate implementation.
"""

from typing import Tuple, Optional, Any, Dict, List
from ..beliefs.state import BeliefState
from ..beliefs.ledger import DecisionEvent
from ..exceptions import DecisionReceiptInvariantError
from cell_os.core import Decision, DecisionRationale
import hashlib


class TemplateChooser:
    """Chooses next experiment template with hard calibration constraints."""

    def __init__(self):
        self.last_decision_event: Optional[DecisionEvent] = None
        self.last_decision: Optional[Decision] = None

    # Required fields for all decision receipts (Covenant 6)
    REQUIRED_DECISION_FIELDS = {"template", "forced", "trigger", "regime", "gate_state"}

    def _assert_decision_receipt(self) -> None:
        """Enforce Covenant 6: Every Decision Must Have a Receipt.

        This invariant check ensures no code path can return from choose_next()
        without writing a complete decision receipt with provenance.

        Raises:
            DecisionReceiptInvariantError: If receipt is missing or incomplete
        """
        ev = self.last_decision_event
        if ev is None:
            raise DecisionReceiptInvariantError(
                "choose_next() returned without writing last_decision_event. "
                "This is a Covenant 6 violation."
            )

        cand = getattr(ev, "selected_candidate", None)
        if not isinstance(cand, dict):
            raise DecisionReceiptInvariantError(
                f"last_decision_event.selected_candidate must be dict, got {type(cand)}"
            )

        # Check required fields
        missing = self.REQUIRED_DECISION_FIELDS - set(cand.keys())
        if missing:
            raise DecisionReceiptInvariantError(
                f"Decision receipt missing required fields: {sorted(missing)}. "
                f"Present: {sorted(cand.keys())}"
            )

        # If forced calibration or abort, enforcement_layer should be present
        if cand.get("forced") is True:
            if "enforcement_layer" not in cand:
                raise DecisionReceiptInvariantError(
                    f"Forced decision (template={cand.get('template')}) missing enforcement_layer field. "
                    "This makes it impossible to distinguish which policy layer enforced the decision."
                )

        # enforcement_layer semantic consistency
        enforcement = cand.get("enforcement_layer")
        trigger = cand.get("trigger")

        allowed_layers = {"global_pre_biology", "template_safety_net", "policy_boundary"}
        if enforcement is not None and enforcement not in allowed_layers:
            raise DecisionReceiptInvariantError(
                f"Invalid enforcement_layer={enforcement}. Allowed: {sorted(allowed_layers)}"
            )

        # If trigger is policy boundary, enforcement layer must be policy boundary
        if trigger == "policy_boundary":
            if enforcement != "policy_boundary":
                raise DecisionReceiptInvariantError(
                    f"trigger=policy_boundary requires enforcement_layer=policy_boundary, got {enforcement}"
                )

        # If we have an explicit blocked/override story, require template_safety_net semantics
        has_override_provenance = any(k in cand for k in ("blocked_template", "missing_gates"))
        if has_override_provenance:
            if enforcement not in ("global_pre_biology", "template_safety_net"):
                raise DecisionReceiptInvariantError(
                    "Decision includes override provenance (blocked_template/missing_gates) "
                    "but enforcement_layer is missing or not an enforcement layer."
                )
            # If missing_gates exists, it must be a non-empty list
            if "missing_gates" in cand:
                mg = cand.get("missing_gates")
                if not isinstance(mg, list) or len(mg) == 0:
                    raise DecisionReceiptInvariantError(
                        f"missing_gates must be a non-empty list when present, got {mg}"
                    )

        # Non-forced scoring decisions should not claim enforcement_layer
        if cand.get("forced") is not True and trigger == "scoring":
            if enforcement is not None:
                raise DecisionReceiptInvariantError(
                    f"Non-forced scoring decision must not set enforcement_layer, got {enforcement}"
                )

        # If abort, must have provenance showing what was attempted
        selected = getattr(ev, "selected", "")
        if "abort" in selected.lower():
            if "attempted_template" not in cand and "calibration_plan" not in cand:
                raise DecisionReceiptInvariantError(
                    f"Abort decision (selected={selected}) missing attempted_template or calibration_plan. "
                    "Refusals must explain what was refused and why."
                )

    def _set_last_decision(
        self,
        cycle: int,
        selected: str,
        selected_score: float,
        reason: str,
        selected_candidate: Dict[str, Any],
        beliefs: BeliefState,
        kwargs: Optional[dict] = None,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Decision:
        """Record decision event for provenance.

        Creates both legacy DecisionEvent (for backward compatibility) and
        canonical Decision (for new code).

        Returns:
            Canonical Decision object
        """
        # Create legacy DecisionEvent for backward compatibility
        self.last_decision_event = DecisionEvent(
            cycle=int(cycle),
            candidates=candidates or [],
            selected=str(selected),
            selected_score=float(selected_score),
            selected_candidate=selected_candidate or {},
            reason=str(reason),
        )

        # Create and store canonical Decision
        self.last_decision = self._build_decision(
            cycle=cycle,
            template=selected,
            kwargs=kwargs or {},
            reason=reason,
            selected_candidate=selected_candidate,
            beliefs=beliefs,
        )

        return self.last_decision

    def _get_gate_state(self, beliefs: BeliefState) -> Dict[str, str]:
        """Get current gate state for all assays (for decision provenance)."""
        return {
            "noise_sigma": "earned" if beliefs.noise_sigma_stable else "lost",
            "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown",
            "ldh": "earned" if beliefs.ldh_sigma_stable else "lost",
            "cell_paint": "earned" if beliefs.cell_paint_sigma_stable else "lost",
            "scrna": "earned" if beliefs.scrna_sigma_stable else "lost",
        }

    def _build_decision(
        self,
        cycle: int,
        template: str,
        kwargs: dict,
        reason: str,
        selected_candidate: Dict[str, Any],
        beliefs: BeliefState,
    ) -> Decision:
        """Build canonical Decision from parameters.

        Args:
            cycle: Current cycle number
            template: Template name chosen
            kwargs: Template parameters
            reason: Human-readable decision reason
            selected_candidate: Decision metadata (regime, forced, trigger, etc.)
            beliefs: Current belief state

        Returns:
            Canonical Decision with proper provenance
        """
        # Generate decision_id from cycle + template + hash of candidate
        cand_str = str(selected_candidate)
        cand_hash = hashlib.md5(cand_str.encode()).hexdigest()[:8]
        decision_id = f"cycle-{cycle}-{cand_hash}"

        # Determine kind from template and metadata
        if template.startswith("abort"):
            kind = "abort"
        elif template in ["baseline_replicates", "edge_center_test"] or \
             template.startswith("calibrate_"):
            kind = "calibration"
        elif selected_candidate.get("forced") and \
             selected_candidate.get("trigger") in ("must_calibrate", "gate_lock", "must_calibrate_for_template"):
            kind = "calibration"
        elif selected_candidate.get("trigger") == "abort":
            kind = "refusal"
        else:
            kind = "proposal"

        # Extract metrics from selected_candidate and beliefs
        metrics = {}
        if beliefs.noise_rel_width is not None:
            metrics["noise_rel_width"] = float(beliefs.noise_rel_width)
        if beliefs.ldh_rel_width is not None:
            metrics["ldh_rel_width"] = float(beliefs.ldh_rel_width)
        if beliefs.cell_paint_rel_width is not None:
            metrics["cell_paint_rel_width"] = float(beliefs.cell_paint_rel_width)
        if beliefs.scrna_rel_width is not None:
            metrics["scrna_rel_width"] = float(beliefs.scrna_rel_width)
        if "calibration_plan" in selected_candidate:
            plan = selected_candidate["calibration_plan"]
            if isinstance(plan, dict):
                if "wells_needed" in plan:
                    metrics["wells_needed"] = float(plan["wells_needed"])
                if "df_needed" in plan:
                    metrics["df_needed"] = float(plan["df_needed"])

        # Extract thresholds (standard calibration thresholds)
        thresholds = {
            "gate_enter": 0.25,
            "gate_exit": 0.40,
            "drift_threshold": 0.20,
        }

        # Extract rules fired from selected_candidate
        rules_fired = []
        if "regime" in selected_candidate:
            rules_fired.append(f"regime_{selected_candidate['regime']}")
        if "enforcement_layer" in selected_candidate:
            rules_fired.append(f"enforcement_{selected_candidate['enforcement_layer']}")
        if selected_candidate.get("forced"):
            rules_fired.append("forced_by_policy")
        if "trigger" in selected_candidate:
            rules_fired.append(f"trigger_{selected_candidate['trigger']}")

        # Create rationale (with legacy metadata fields for backward compatibility)
        rationale = DecisionRationale(
            summary=reason,
            rules_fired=tuple(rules_fired),
            warnings=tuple(),  # Not yet tracked in current system
            metrics=metrics,
            thresholds=thresholds,
            counterfactuals={},  # Not yet tracked in current system
            # Legacy metadata (v0.4.x compatibility)
            regime=selected_candidate.get("regime"),
            forced=selected_candidate.get("forced"),
            trigger=selected_candidate.get("trigger"),
            enforcement_layer=selected_candidate.get("enforcement_layer"),
            blocked_template=selected_candidate.get("blocked_template"),
            gate_state=selected_candidate.get("gate_state"),
            calibration_plan=selected_candidate.get("calibration_plan"),
        )

        # Generate inputs fingerprint from belief state + budget + cycle
        # Use key belief fields for stability
        fingerprint_data = f"{cycle}_{beliefs.noise_df_total}_{beliefs.ldh_df_total}_{beliefs.cell_paint_df_total}"
        fingerprint = hashlib.md5(fingerprint_data.encode()).hexdigest()[:16]

        # Extract chosen_kwargs (filter out meta fields)
        meta_fields = {
            "template", "forced", "trigger", "regime", "enforcement_layer",
            "gate_state", "calibration_plan", "blocked_template", "missing_gates",
            "attempted_template", "assay", "block_reason",
            "debt_bits", "last_refusal_reason", "consecutive_refusals"  # Epistemic debt provenance
        }
        chosen_kwargs = {k: v for k, v in selected_candidate.items() if k not in meta_fields}
        # Also include kwargs passed in (e.g., reason, n_reps)
        chosen_kwargs.update(kwargs)

        return Decision(
            decision_id=decision_id,
            cycle=cycle,
            timestamp_utc=Decision.now_utc(),
            kind=kind,
            chosen_template=template if kind != "refusal" else None,
            chosen_kwargs=chosen_kwargs,
            rationale=rationale,
            inputs_fingerprint=fingerprint,
        )

    def _check_assay_gate(
        self,
        beliefs: BeliefState,
        assay: str,
        require_ladder: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Check if assay gate is earned (with optional ladder check).

        Args:
            beliefs: Current belief state
            assay: One of 'ldh', 'cell_paint', 'scrna'
            require_ladder: If True, enforce ladder constraints

        Returns:
            (gate_ok, block_reason): gate_ok is True if gate earned and ladder satisfied
        """
        if assay == "ldh":
            gate_earned = beliefs.ldh_sigma_stable
            if not gate_earned:
                rw = f"{beliefs.ldh_rel_width:.3f}" if beliefs.ldh_rel_width is not None else "N/A"
                return (False, f"LDH gate not earned (rel_width={rw})")
        elif assay == "cell_paint":
            gate_earned = beliefs.cell_paint_sigma_stable
            if not gate_earned:
                rw = f"{beliefs.cell_paint_rel_width:.3f}" if beliefs.cell_paint_rel_width is not None else "N/A"
                return (False, f"Cell Painting gate not earned (rel_width={rw})")
        elif assay == "scrna":
            gate_earned = beliefs.scrna_sigma_stable
            if not gate_earned:
                rw = f"{beliefs.scrna_rel_width:.3f}" if beliefs.scrna_rel_width is not None else "N/A"
                return (False, f"scRNA gate not earned (rel_width={rw})")

            # Ladder constraint: scRNA requires CP gate first
            if require_ladder and not beliefs.cell_paint_sigma_stable:
                return (False, "scRNA requires Cell Painting gate earned first (ladder constraint)")
        else:
            return (False, f"Unknown assay: {assay}")

        return (True, None)

    def _compute_assay_calibration_plan(
        self,
        beliefs: BeliefState,
        assay: str
    ) -> Dict[str, Any]:
        """Compute calibration plan for an assay gate (wells needed, df needed)."""
        if assay == "ldh":
            df_total = beliefs.ldh_df_total
            rel_width = beliefs.ldh_rel_width
        elif assay == "cell_paint":
            df_total = beliefs.cell_paint_df_total
            rel_width = beliefs.cell_paint_rel_width
        elif assay == "scrna":
            df_total = beliefs.scrna_df_total
            rel_width = beliefs.scrna_rel_width
        else:
            return {}

        enter_threshold = 0.25
        if rel_width and rel_width > 0:
            c = rel_width * (df_total ** 0.5)
            df_needed = int((c / enter_threshold) ** 2 * 1.25)  # safety factor
        else:
            df_needed = 140  # conservative floor

        df_delta = max(0, df_needed - df_total)
        wells_needed = ((df_delta + 11) // 11) * 12  # cycles of 12 wells

        return {
            "assay": assay,
            "df_current": df_total,
            "df_needed": df_needed,
            "wells_needed": wells_needed,
            "rel_width": rel_width,
        }

    def _required_gates_for_template(self, template_name: str) -> set:
        """Return which assay gates are required before running this template.

        v0.5.0: Template-aware gate enforcement.
        - Calibration templates require nothing (they establish gates)
        - Biology templates require LDH + CP gates (cheap calibration first)
        - scRNA templates require CP gate (ladder prereq) but NOT scrna gate
        """
        # Calibration templates: no prerequisites (they establish the gates)
        if template_name in ["calibrate_ldh_baseline", "calibrate_cell_paint_baseline",
                              "calibrate_scrna_baseline", "baseline_replicates", "edge_center_test"]:
            return set()

        # scRNA templates: require CP gate (ladder), but NOT scrna gate
        # (scrna gate is optional, earned by explicit calibration or after upgrade)
        if template_name in ["scrna_upgrade_probe"]:
            return {"cell_paint"}  # Ladder prerequisite

        # All other biology templates: require LDH + CP gates
        # (cheap calibration before expensive biology)
        return {"ldh", "cell_paint"}

    def _validate_template_selection(
        self,
        template_name: str,
        allow_expensive_calibration: bool,
        cycle: int,
        beliefs: BeliefState
    ) -> Tuple[bool, Optional[str]]:
        """Validate template selection against policy boundaries.

        Returns:
            (is_valid, abort_reason): is_valid=False if policy violated
        """
        # Policy: calibrate_scrna_baseline requires explicit authorization
        # (expensive, manual-only template)
        if template_name == "calibrate_scrna_baseline" and not allow_expensive_calibration:
            reason = (
                "ABORT: calibrate_scrna_baseline requires explicit authorization "
                "(set allow_expensive_calibration=True). This is an expensive, manual-only "
                "template not eligible for autonomous selection."
            )
            return (False, reason)

        return (True, None)

    def _enforce_template_gates(
        self,
        beliefs: BeliefState,
        template_name: str,
        template_kwargs: dict,
        remaining_wells: int,
        cycle: int,
        allow_expensive_calibration: bool = False
    ) -> Tuple[str, dict]:
        """Enforce gate requirements before returning a template.

        v0.5.0: Authoritative gate enforcement at decision point.
        If template requires gates that are missing, override to calibration.

        Args:
            allow_expensive_calibration: Passed through to policy validation

        Returns:
            (actual_template_name, actual_template_kwargs): May override if gates missing
        """
        required_gates = self._required_gates_for_template(template_name)
        missing_gates = []

        # Check which gates are missing
        for gate in required_gates:
            gate_ok, block_reason = self._check_assay_gate(beliefs, gate, require_ladder=False)
            if not gate_ok:
                missing_gates.append(gate)

        # If no gates missing, return original template
        if not missing_gates:
            return (template_name, template_kwargs)

        # Gates missing: force calibration for first missing gate
        first_missing = missing_gates[0]  # LDH before CP (priority order)
        calib_plan = self._compute_assay_calibration_plan(beliefs, first_missing)
        wells_needed = calib_plan.get("wells_needed", 0)

        # Check affordability
        if remaining_wells < wells_needed:
            reason = f"ABORT: Cannot afford {first_missing} gate (required for {template_name}, need {wells_needed} wells, have {remaining_wells})"
            self._set_last_decision(
                cycle=cycle,
                selected="abort_insufficient_assay_gate_budget",
                selected_score=0.0,
                reason=reason,
                selected_candidate={
                    "template": "abort_insufficient_assay_gate_budget",
                    "forced": True,
                    "trigger": "abort",
                    "regime": "pre_gate",
                    "enforcement_layer": "template_safety_net",
                    "gate_state": self._get_gate_state(beliefs),
                    "calibration_plan": calib_plan,
                    "assay": first_missing,
                    "blocked_template": template_name,
                    "missing_gates": missing_gates,
                },
                beliefs=beliefs,
                kwargs={"reason": reason}
            )
            return ("abort", {"reason": reason})

        # Override to calibration
        calibration_template = f"calibrate_{first_missing}_baseline"

        # Policy check: validate template selection
        is_valid, abort_reason = self._validate_template_selection(
            calibration_template, allow_expensive_calibration, cycle, beliefs
        )
        if not is_valid:
            self._set_last_decision(
                cycle=cycle,
                selected="abort_policy_violation",
                selected_score=0.0,
                reason=abort_reason,
                selected_candidate={
                    "template": "abort_policy_violation",
                    "forced": True,
                    "trigger": "policy_boundary",
                    "regime": "pre_gate",
                    "enforcement_layer": "template_safety_net",
                    "gate_state": self._get_gate_state(beliefs),
                    "attempted_template": calibration_template,
                    "blocked_template": template_name,
                },
                beliefs=beliefs,
                kwargs={"reason": abort_reason}
            )
            return ("abort", {"reason": abort_reason})

        reason = f"Earn {first_missing} gate (required for {template_name})"
        self._set_last_decision(
            cycle=cycle,
            selected=calibration_template,
            selected_score=1.0,
            reason=reason,
            selected_candidate={
                "template": calibration_template,
                "forced": True,
                "trigger": "must_calibrate_for_template",
                "regime": "pre_gate",
                "enforcement_layer": "template_safety_net",
                "gate_state": self._get_gate_state(beliefs),
                "calibration_plan": calib_plan,
                "assay": first_missing,
                "blocked_template": template_name,
                "missing_gates": missing_gates,
                "n_reps": 12
            },
            beliefs=beliefs,
            kwargs={"reason": reason, "assay": first_missing, "n_reps": 12}
        )
        return (calibration_template, {
            "reason": reason,
            "assay": first_missing,
            "n_reps": 12
        })

    def _finalize_selection(
        self,
        beliefs: BeliefState,
        template_name: str,
        template_kwargs: dict,
        remaining_wells: int,
        cycle: int,
        allow_expensive_calibration: bool,
        selected_score: float,
        reason: str,
        forced: bool,
        trigger: str,
        regime: str,
        additional_candidate_fields: Optional[dict] = None
    ) -> Decision:
        """Single choke point for all template selection returns.

        Enforces:
        1. Policy validation (_validate_template_selection)
        2. Gate enforcement (_enforce_template_gates)
        3. Decision recording (_set_last_decision)

        This prevents any template from "sneaking through" without validation.

        Returns:
            Decision: Canonical decision object with template, kwargs, and provenance
        """
        # Step 1: Policy validation (expensive templates, etc.)
        is_valid, abort_reason = self._validate_template_selection(
            template_name, allow_expensive_calibration, cycle, beliefs
        )
        if not is_valid:
            return self._set_last_decision(
                cycle=cycle,
                selected="abort_policy_violation",
                selected_score=0.0,
                reason=abort_reason,
                selected_candidate={
                    "template": "abort_policy_violation",
                    "forced": True,
                    "trigger": "policy_boundary",
                    "regime": regime,
                    "gate_state": self._get_gate_state(beliefs),
                    "attempted_template": template_name,
                },
                beliefs=beliefs,
                kwargs={"reason": abort_reason}
            )

        # Step 2: Gate enforcement (may override to calibration)
        actual_template, actual_kwargs = self._enforce_template_gates(
            beliefs, template_name, template_kwargs, remaining_wells, cycle,
            allow_expensive_calibration
        )

        # If gates forced an override, enforcement already set decision
        if actual_template != template_name:
            # Invariant: enforcement must have written the decision receipt
            if self.last_decision_event is None:
                raise AssertionError(
                    f"INTERNAL ERROR: Gate enforcement overrode {template_name} → {actual_template}, "
                    f"but did not set last_decision_event. This is a contract violation."
                )
            if "enforcement_layer" not in self.last_decision_event.selected_candidate:
                raise AssertionError(
                    f"INTERNAL ERROR: Gate enforcement overrode {template_name} → {actual_template}, "
                    f"but decision receipt missing 'enforcement_layer' field. "
                    f"Receipt: {self.last_decision_event.selected_candidate.keys()}"
                )
            # Return the canonical Decision that was already created by enforcement
            return self.last_decision

        # Step 3: Record successful selection decision
        candidate_fields = {
            "template": template_name,
            "forced": forced,
            "trigger": trigger,
            "regime": regime,
            "gate_state": self._get_gate_state(beliefs),
            **(additional_candidate_fields or {})
        }
        decision = self._set_last_decision(
            cycle=cycle,
            selected=template_name,
            selected_score=selected_score,
            reason=reason,
            selected_candidate=candidate_fields,
            beliefs=beliefs,
            kwargs=template_kwargs
        )

        # Covenant 6 invariant: Ensure receipt was written correctly
        self._assert_decision_receipt()

        return decision

    def choose_next(
        self,
        beliefs: BeliefState,
        budget_remaining_wells: int = 384,
        cycle: int = 0,
        allow_expensive_calibration: bool = False
    ) -> Decision:
        """Choose next experiment template.

        v0.4.2: PAY-FOR-CALIBRATION REGIME with gate lock invariant.

        Args:
            beliefs: Current belief state
            budget_remaining_wells: Remaining well budget
            cycle: Current cycle number
            allow_expensive_calibration: If False (default), block autonomous selection of
                expensive calibration templates like calibrate_scrna_baseline. Requires
                explicit user intent to enable.

        Returns:
            Decision: Canonical decision object with template, kwargs, and provenance
        """
        remaining_wells = int(max(budget_remaining_wells, 0))

        # INSOLVENCY-FIRST RULE: If epistemically insolvent, force calibration
        # This is policy adaptation, not enforcement weakening
        # The agent learns: "I am insolvent, I must calibrate to restore solvency"
        if beliefs.epistemic_insolvent:
            # Backoff: if refused 3+ times, agent must declare bankruptcy
            MAX_CONSECUTIVE_REFUSALS = 3
            if beliefs.consecutive_refusals >= MAX_CONSECUTIVE_REFUSALS:
                reason = (
                    f"ABORT: Epistemic bankruptcy (debt={beliefs.epistemic_debt_bits:.2f} bits, "
                    f"{beliefs.consecutive_refusals} consecutive refusals). "
                    "Agent cannot restore solvency within budget constraints."
                )
                return self._set_last_decision(
                    cycle=cycle,
                    selected="abort_epistemic_bankruptcy",
                    selected_score=0.0,
                    reason=reason,
                    selected_candidate={
                        "template": "abort_epistemic_bankruptcy",
                        "forced": True,
                        "trigger": "insolvency_unrecoverable",
                        "regime": "epistemic_bankruptcy",
                        "enforcement_layer": "policy_boundary",
                        "gate_state": self._get_gate_state(beliefs),
                        "debt_bits": beliefs.epistemic_debt_bits,
                        "consecutive_refusals": beliefs.consecutive_refusals
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason}
                )

            # Force calibration to reduce debt
            reason = (
                f"Restore solvency: debt={beliefs.epistemic_debt_bits:.2f} bits "
                f"(refusals: {beliefs.consecutive_refusals})"
            )
            return self._set_last_decision(
                cycle=cycle,
                selected="baseline_replicates",
                selected_score=1.0,
                reason=reason,
                selected_candidate={
                    "template": "baseline_replicates",
                    "forced": True,
                    "trigger": "epistemic_insolvency",
                    "regime": "debt_recovery",
                    "enforcement_layer": "policy_boundary",
                    "gate_state": self._get_gate_state(beliefs),
                    "n_reps": 12,
                    "debt_bits": beliefs.epistemic_debt_bits,  # provenance only
                    "last_refusal_reason": beliefs.last_refusal_reason  # provenance only
                },
                beliefs=beliefs,
                kwargs={"n_reps": 12}  # Only pass template parameters, not provenance
            )

        # Check gate lock invariant
        stable = beliefs.noise_sigma_stable
        rel_width = beliefs.noise_rel_width
        drift_metric = beliefs.noise_drift_metric

        enter_threshold = 0.25
        exit_threshold = 0.40
        drift_threshold = 0.20
        df_min_sanity = 40

        # Gate lock check: if stable=True, verify still valid
        if stable:
            # Integrity check
            if rel_width is None:
                reason = "ABORT: Gate integrity error (stable=True but rel_width=None)"
                return self._set_last_decision(
                    cycle=cycle,
                    selected="abort_gate_integrity_error",
                    selected_score=0.0,
                    reason=reason,
                    selected_candidate={
                        "template": "abort_gate_integrity_error",
                        "forced": True,
                        "trigger": "abort",
                        "regime": "integrity_error",
                        "enforcement_layer": "global_pre_biology",
                        "gate_state": self._get_gate_state(beliefs)
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason}
                )
            
            # Check if gate lost
            drift_bad = (drift_metric is not None and drift_metric >= drift_threshold)
            gate_revoked = (rel_width >= exit_threshold) or drift_bad

            if gate_revoked:
                # Force recalibration
                reason = f"Gate lost: rel_width={rel_width:.4f} or drift={drift_metric}. Force recalibration."
                return self._set_last_decision(
                    cycle=cycle,
                    selected="baseline_replicates",
                    selected_score=1.0,
                    reason=reason,
                    selected_candidate={
                        "template": "baseline_replicates",
                        "forced": True,
                        "trigger": "gate_lock",
                        "regime": "gate_revoked",
                        "enforcement_layer": "global_pre_biology",
                        "gate_state": self._get_gate_state(beliefs),
                        "n_reps": 12
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason, "n_reps": 12}
                )
        
        # If gate not earned, force calibration
        df_total = beliefs.noise_df_total
        if not stable or (rel_width is not None and rel_width > enter_threshold):
            # Estimate cost to earn gate
            if rel_width and rel_width > 0:
                c = rel_width * (df_total ** 0.5)
                df_needed = int((c / enter_threshold) ** 2 * 1.25)  # safety factor
            else:
                df_needed = 140  # conservative floor

            df_delta = max(0, df_needed - df_total)
            wells_needed = ((df_delta + 11) // 11) * 12  # cycles of 12 wells

            calibration_plan = {
                "df_current": df_total,
                "df_needed": df_needed,
                "wells_needed": wells_needed,
                "rel_width": rel_width
            }

            # Fail-fast if can't afford
            if remaining_wells < wells_needed:
                reason = f"ABORT: Cannot afford gate (need {wells_needed} wells, have {remaining_wells})"
                return self._set_last_decision(
                    cycle=cycle,
                    selected="abort_insufficient_calibration_budget",
                    selected_score=0.0,
                    reason=reason,
                    selected_candidate={
                        "template": "abort_insufficient_calibration_budget",
                        "forced": True,
                        "trigger": "abort",
                        "regime": "pre_gate",
                        "enforcement_layer": "global_pre_biology",
                        "gate_state": self._get_gate_state(beliefs),
                        "calibration_plan": calibration_plan
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason}
                )

            # Prioritize: baseline reps first, then edge if df >= 40
            if not beliefs.edge_effect_confident and df_total >= 40:
                reason = "Resolve edge confound before biology"
                return self._set_last_decision(
                    cycle=cycle,
                    selected="edge_center_test",
                    selected_score=1.0,
                    reason=reason,
                    selected_candidate={
                        "template": "edge_center_test",
                        "forced": True,
                        "trigger": "must_calibrate",
                        "regime": "pre_gate",
                        "enforcement_layer": "global_pre_biology",
                        "gate_state": self._get_gate_state(beliefs),
                        "calibration_plan": calibration_plan
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason}
                )

            reason = f"Earn noise gate (df={df_total}, need~{df_needed})"
            return self._set_last_decision(
                cycle=cycle,
                selected="baseline_replicates",
                selected_score=1.0,
                reason=reason,
                selected_candidate={
                    "template": "baseline_replicates",
                    "forced": True,
                    "trigger": "must_calibrate",
                    "regime": "pre_gate",
                    "enforcement_layer": "global_pre_biology",
                    "gate_state": self._get_gate_state(beliefs),
                    "calibration_plan": calibration_plan,
                    "n_reps": 12
                },
                beliefs=beliefs,
                kwargs={"reason": reason, "n_reps": 12}
            )

        # Noise gate earned - now check cheap assay gates (LDH, CP) before biology
        # v0.5.0: Force LDH + CP calibration (never force scRNA unless explicitly requested)
        for assay in ["ldh", "cell_paint"]:  # Priority order: cheap gates first
            gate_ok, block_reason = self._check_assay_gate(beliefs, assay, require_ladder=False)
            if not gate_ok:
                # Compute calibration plan
                calib_plan = self._compute_assay_calibration_plan(beliefs, assay)
                wells_needed = calib_plan.get("wells_needed", 0)

                # Fail-fast if can't afford
                if remaining_wells < wells_needed:
                    reason = f"ABORT: Cannot afford {assay} gate ({block_reason}, need {wells_needed} wells, have {remaining_wells})"
                    return self._set_last_decision(
                        cycle=cycle,
                        selected="abort_insufficient_assay_gate_budget",
                        selected_score=0.0,
                        reason=reason,
                        selected_candidate={
                            "template": "abort_insufficient_assay_gate_budget",
                            "forced": True,
                            "trigger": "abort",
                            "regime": "pre_gate",
                            "enforcement_layer": "global_pre_biology",
                            "gate_state": self._get_gate_state(beliefs),
                            "calibration_plan": calib_plan,
                            "assay": assay,
                            "block_reason": block_reason,
                        },
                        beliefs=beliefs,
                        kwargs={"reason": reason}
                    )

                # Force calibration for this assay
                template_name = f"calibrate_{assay}_baseline"

                # Policy check: validate template selection
                is_valid, abort_reason = self._validate_template_selection(
                    template_name, allow_expensive_calibration, cycle, beliefs
                )
                if not is_valid:
                    return self._set_last_decision(
                        cycle=cycle,
                        selected="abort_policy_violation",
                        selected_score=0.0,
                        reason=abort_reason,
                        selected_candidate={
                            "template": "abort_policy_violation",
                            "forced": True,
                            "trigger": "policy_boundary",
                            "regime": "pre_gate",
                            "enforcement_layer": "global_pre_biology",
                            "gate_state": self._get_gate_state(beliefs),
                            "attempted_template": template_name,
                        },
                        beliefs=beliefs,
                        kwargs={"reason": abort_reason}
                    )

                reason = f"Earn {assay} gate ({block_reason})"
                return self._set_last_decision(
                    cycle=cycle,
                    selected=template_name,
                    selected_score=1.0,
                    reason=reason,
                    selected_candidate={
                        "template": template_name,
                        "forced": True,
                        "trigger": "must_calibrate",
                        "regime": "pre_gate",
                        "enforcement_layer": "global_pre_biology",
                        "gate_state": self._get_gate_state(beliefs),
                        "calibration_plan": calib_plan,
                        "assay": assay,
                        "n_reps": 12
                    },
                    beliefs=beliefs,
                    kwargs={"reason": reason, "assay": assay, "n_reps": 12}
                )

        # Gate earned - allow biology
        # v0.5.0: CP → scRNA upgrade trigger (DISABLED until real novelty metric exists)
        # Currently disabled: novelty_score computation requires real CP feature extraction
        # When enabled, this should check:
        #   - novelty_score from CP morphology embeddings (e.g., Mahalanobis distance)
        #   - ldh_viable from real LDH assay (viability > threshold)
        #   - budget affordability for scRNA probe
        # TODO: Enable when CP feature extraction is implemented
        # if beliefs.cell_paint_sigma_stable and not beliefs.scrna_sigma_stable:
        #     novelty_score = compute_morphology_novelty(latest_observation)
        #     ldh_viable = check_ldh_viability(latest_observation)
        #     if novelty_score >= 0.8 and ldh_viable and remaining_wells >= scrna_cost:
        #         return ("scrna_upgrade_probe", {...})

        # Simple fallback: test compounds with dose ladder
        tested = beliefs.tested_compounds - {'DMSO'}
        if not tested or len(tested) < 5:
            reason = "Explore compounds with dose-response"
            return self._finalize_selection(
                beliefs=beliefs,
                template_name="dose_ladder_coarse",
                template_kwargs={"reason": reason},
                remaining_wells=remaining_wells,
                cycle=cycle,
                allow_expensive_calibration=allow_expensive_calibration,
                selected_score=1.0,
                reason=reason,
                forced=False,
                trigger="scoring",
                regime="in_gate"
            )

        # Final fallback: calibration maintenance
        reason = "Continue calibration maintenance"
        return self._finalize_selection(
            beliefs=beliefs,
            template_name="baseline_replicates",
            template_kwargs={"reason": reason, "n_reps": 12},
            remaining_wells=remaining_wells,
            cycle=cycle,
            allow_expensive_calibration=allow_expensive_calibration,
            selected_score=1.0,
            reason=reason,
            forced=False,
            trigger="scoring",
            regime="in_gate",
            additional_candidate_fields={"n_reps": 12}
        )
