"""
Template chooser with pay-for-calibration regime and gate lock invariant.

v0.4.2: Hard constraints - biology forbidden until gate earned.
Gate lock invariant prevents lying once earned.
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
                        "gate_state": {
                            "noise_sigma": "corrupted",
                            "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                        }
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
                        "gate_state": {
                            "noise_sigma": "lost",
                            "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                        },
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
                        "gate_state": {
                            "noise_sigma": "lost",
                            "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                        },
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
                        "gate_state": {
                            "noise_sigma": "lost",
                            "edge_effect": "lost"
                        },
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
                    "gate_state": {
                        "noise_sigma": "lost",
                        "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                    },
                    "calibration_plan": calibration_plan,
                    "n_reps": 12
                }
            )
            return ("baseline_replicates", {
                "reason": reason,
                "n_reps": 12
            })
        
        # Gate earned - allow biology
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
                    "gate_state": {
                        "noise_sigma": "earned",
                        "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                    }
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
                "gate_state": {
                    "noise_sigma": "earned",
                    "edge_effect": "earned" if beliefs.edge_effect_confident else "unknown"
                },
                "n_reps": 12
            }
        )
        return ("baseline_replicates", {
            "reason": reason,
            "n_reps": 12
        })
