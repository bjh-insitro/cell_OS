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


class TemplateChooser:
    """Chooses next experiment template with hard calibration constraints."""

    def __init__(self):
        self.last_decision_event: Optional[DecisionEvent] = None

    def _set_last_decision(
        self,
        cycle: int,
        selected: str,
        selected_score: float,
        reason: str,
        selected_candidate: Dict[str, Any],
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Record decision event for provenance."""
        self.last_decision_event = DecisionEvent(
            cycle=int(cycle),
            candidates=candidates or [],
            selected=str(selected),
            selected_score=float(selected_score),
            selected_candidate=selected_candidate or {},
            reason=str(reason),
        )

    def _get_gate_state(self, beliefs: BeliefState) -> Dict[str, str]:
        """Get current gate state for all assays (for decision provenance)."""
        return {
            "noise_sigma": "earned" if beliefs.noise_sigma_stable else "lost",
            "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown",
            "ldh": "earned" if beliefs.ldh_sigma_stable else "lost",
            "cell_paint": "earned" if beliefs.cell_paint_sigma_stable else "lost",
            "scrna": "earned" if beliefs.scrna_sigma_stable else "lost",
        }

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

    def choose_next(
        self,
        beliefs: BeliefState,
        budget_remaining_wells: int = 384,
        cycle: int = 0
    ) -> Tuple[str, dict]:
        """Choose next experiment template.

        v0.4.2: PAY-FOR-CALIBRATION REGIME with gate lock invariant.

        Returns:
            (template_name, template_kwargs): What to run next
        """
        remaining_wells = int(max(budget_remaining_wells, 0))

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
                self._set_last_decision(
                    cycle=cycle,
                    selected="abort_gate_integrity_error",
                    selected_score=0.0,
                    reason=reason,
                    selected_candidate={
                        "template": "abort_gate_integrity_error",
                        "forced": True,
                        "trigger": "abort",
                        "regime": "integrity_error",
                        "gate_state": self._get_gate_state(beliefs)
                    }
                )
                return ("abort", {
                    "reason": reason
                })
            
            # Check if gate lost
            drift_bad = (drift_metric is not None and drift_metric >= drift_threshold)
            gate_revoked = (rel_width >= exit_threshold) or drift_bad

            if gate_revoked:
                # Force recalibration
                reason = f"Gate lost: rel_width={rel_width:.4f} or drift={drift_metric}. Force recalibration."
                self._set_last_decision(
                    cycle=cycle,
                    selected="baseline_replicates",
                    selected_score=1.0,
                    reason=reason,
                    selected_candidate={
                        "template": "baseline_replicates",
                        "forced": True,
                        "trigger": "gate_lock",
                        "regime": "gate_revoked",
                        "gate_state": self._get_gate_state(beliefs),
                        "n_reps": 12
                    }
                )
                return ("baseline_replicates", {
                    "reason": reason,
                    "n_reps": 12
                })
        
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
                self._set_last_decision(
                    cycle=cycle,
                    selected="abort_insufficient_calibration_budget",
                    selected_score=0.0,
                    reason=reason,
                    selected_candidate={
                        "template": "abort_insufficient_calibration_budget",
                        "forced": True,
                        "trigger": "abort",
                        "regime": "pre_gate",
                        "gate_state": self._get_gate_state(beliefs),
                        "calibration_plan": calibration_plan
                    }
                )
                return ("abort", {
                    "reason": reason
                })

            # Prioritize: baseline reps first, then edge if df >= 40
            if not beliefs.edge_effect_confident and df_total >= 40:
                reason = "Resolve edge confound before biology"
                self._set_last_decision(
                    cycle=cycle,
                    selected="edge_center_test",
                    selected_score=1.0,
                    reason=reason,
                    selected_candidate={
                        "template": "edge_center_test",
                        "forced": True,
                        "trigger": "must_calibrate",
                        "regime": "pre_gate",
                        "gate_state": self._get_gate_state(beliefs),
                        "calibration_plan": calibration_plan
                    }
                )
                return ("edge_center_test", {
                    "reason": reason
                })

            reason = f"Earn noise gate (df={df_total}, need~{df_needed})"
            self._set_last_decision(
                cycle=cycle,
                selected="baseline_replicates",
                selected_score=1.0,
                reason=reason,
                selected_candidate={
                    "template": "baseline_replicates",
                    "forced": True,
                    "trigger": "must_calibrate",
                    "regime": "pre_gate",
                    "gate_state": self._get_gate_state(beliefs),
                    "calibration_plan": calibration_plan,
                    "n_reps": 12
                }
            )
            return ("baseline_replicates", {
                "reason": reason,
                "n_reps": 12
            })
        
        # Gate earned - allow biology
        # v0.5.0: Check for CP → scRNA upgrade opportunity first
        if beliefs.cell_paint_sigma_stable and not beliefs.scrna_sigma_stable:
            # Placeholder novelty score (proxy from observation variance)
            # TODO: Replace with real CP feature novelty when available
            novelty_score = 0.0  # Will be populated by observation context
            ldh_viable = True  # Placeholder: assume viable unless LDH says otherwise

            # For now, don't trigger upgrade in every cycle (placeholder threshold)
            novelty_threshold = 0.8
            if novelty_score >= novelty_threshold and ldh_viable:
                # Check affordability for scRNA calibration
                scrna_plan = self._compute_assay_calibration_plan(beliefs, "scrna")
                wells_needed = scrna_plan.get("wells_needed", 0)

                if remaining_wells >= wells_needed:
                    reason = f"Upgrade to scRNA: novelty={novelty_score:.3f}, ldh_viable={ldh_viable}"
                    self._set_last_decision(
                        cycle=cycle,
                        selected="scrna_upgrade_probe",
                        selected_score=1.0,
                        reason=reason,
                        selected_candidate={
                            "template": "scrna_upgrade_probe",
                            "forced": False,
                            "trigger": "upgrade",
                            "regime": "in_gate",
                            "gate_state": self._get_gate_state(beliefs),
                            "novelty_score": novelty_score,
                            "novelty_threshold": novelty_threshold,
                            "ldh_viable": ldh_viable,
                            "budget_remaining": remaining_wells,
                        }
                    )
                    return ("scrna_upgrade_probe", {
                        "reason": reason,
                        "novelty_score": novelty_score,
                        "ldh_viable": ldh_viable,
                    })

        # Simple fallback: test compounds with dose ladder
        tested = beliefs.tested_compounds - {'DMSO'}
        if not tested or len(tested) < 5:
            reason = "Explore compounds with dose-response"
            self._set_last_decision(
                cycle=cycle,
                selected="dose_ladder_coarse",
                selected_score=1.0,
                reason=reason,
                selected_candidate={
                    "template": "dose_ladder_coarse",
                    "forced": False,
                    "trigger": "scoring",
                    "regime": "in_gate",
                    "gate_state": self._get_gate_state(beliefs)
                }
            )
            return ("dose_ladder_coarse", {
                "reason": reason,
            })

        reason = "Continue calibration maintenance"
        self._set_last_decision(
            cycle=cycle,
            selected="baseline_replicates",
            selected_score=1.0,
            reason=reason,
            selected_candidate={
                "template": "baseline_replicates",
                "forced": False,
                "trigger": "scoring",
                "regime": "in_gate",
                "gate_state": self._get_gate_state(beliefs),
                "n_reps": 12
            }
        )
        return ("baseline_replicates", {
            "reason": reason,
            "n_reps": 12
        })
