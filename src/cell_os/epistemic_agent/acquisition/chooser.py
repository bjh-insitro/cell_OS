"""
Template chooser with pay-for-calibration regime and gate lock invariant.

v0.4.2: Hard constraints - biology forbidden until gate earned.
Gate lock invariant prevents lying once earned.
"""

from typing import Tuple
from ..beliefs.state import BeliefState


class TemplateChooser:
    """Chooses next experiment template with hard calibration constraints."""

    def __init__(self):
        pass

    def choose_next(
        self,
        beliefs: BeliefState,
        budget_remaining_wells: int = 384
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
                return ("abort", {
                    "reason": "Gate integrity error: stable=True but rel_width=None"
                })
            
            # Check if gate lost
            drift_bad = (drift_metric is not None and drift_metric >= drift_threshold)
            gate_revoked = (rel_width >= exit_threshold) or drift_bad
            
            if gate_revoked:
                # Force recalibration
                return ("baseline_replicates", {
                    "reason": f"Gate lost: rel_width={rel_width:.4f} or drift={drift_metric}",
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
            
            # Fail-fast if can't afford
            if remaining_wells < wells_needed:
                return ("abort", {
                    "reason": f"Cannot afford gate: need {wells_needed} wells, have {remaining_wells}"
                })
            
            # Prioritize: baseline reps first, then edge if df >= 40
            if not beliefs.edge_effect_confident and df_total >= 40:
                return ("edge_center_test", {
                    "reason": "Resolve edge confound before biology"
                })
            
            return ("baseline_replicates", {
                "reason": f"Earn noise gate (df={df_total}, need~{df_needed})",
                "n_reps": 12
            })
        
        # Gate earned - allow biology
        # Simple fallback: test compounds with dose ladder
        tested = beliefs.tested_compounds - {'DMSO'}
        if not tested or len(tested) < 5:
            return ("dose_ladder_coarse", {
                "reason": "Explore compounds with dose-response",
            })
        
        return ("baseline_replicates", {
            "reason": "Continue calibration maintenance",
            "n_reps": 12
        })
