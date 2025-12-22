"""
Noise Belief Updater

Updates noise model beliefs using pooled variance + chi-square CI.
Tracks calibration quality and gate status with drift detection.
"""

from typing import List, Optional
import math
import numpy as np

from .base import BaseBeliefUpdater
from ..ledger import cond_key, NoiseDiagnosticEvent


# Gate thresholds (shared constants)
ENTER_THRESHOLD = 0.25
EXIT_THRESHOLD = 0.40
DF_MIN_SANITY = 40
DRIFT_THRESHOLD = 0.20
NOISE_GATE_STREAK_K = 3


def _sigma_ci_from_pooled(sse_total: float, df_total: int, alpha: float = 0.05):
    """Compute CI for sigma from pooled variance using chi-square.

    Note: Imported from state.py module-level function.
    """
    from .. import state
    return state._sigma_ci_from_pooled(sse_total, df_total, alpha)


class NoiseBeliefUpdater(BaseBeliefUpdater):
    """
    Updates noise model beliefs from DMSO baseline observations.

    Tracks:
    - Pooled variance estimate (chi-square CI)
    - Per-channel CVs
    - Drift detection (rolling window)
    - Gate status (enter/exit with hysteresis)
    """

    def update(self, conditions: List, diagnostics_out: List) -> None:
        """
        Update noise beliefs from DMSO baseline conditions.

        Args:
            conditions: List of ConditionSummary objects
            diagnostics_out: List to append NoiseDiagnosticEvent objects
        """
        dmso_conditions = self._find_dmso_baselines(conditions)
        if not dmso_conditions:
            return

        for cond in dmso_conditions:
            condition_key = cond_key(cond)

            # Update calibration tracking
            self._update_channel_cvs(cond, condition_key)

            # Update pooled variance and compute sigma + CI
            rel_width = self._update_pooled_variance(cond, condition_key)

            # Detect drift in sigma estimates
            drift_metric = self._update_drift_metric(cond)

            # Evaluate gate status with hysteresis
            self._update_noise_gate_status(rel_width, drift_metric, condition_key)

            # Emit diagnostic event
            self._emit_noise_diagnostic(cond, condition_key, diagnostics_out)

    def _find_dmso_baselines(self, conditions: List) -> List:
        """Extract DMSO baseline conditions from center wells."""
        return [c for c in conditions if c.compound == 'DMSO' and c.position_tag == 'center']

    def _update_channel_cvs(self, cond, condition_key: str):
        """Update per-channel CV tracking and calibration counters."""
        n = cond.n_wells

        # Track per-channel CV for transparency
        if cond.feature_means:
            new_cv_by_channel = dict(self.beliefs.baseline_cv_by_channel)
            for ch, mean_val in cond.feature_means.items():
                std_val = cond.feature_stds.get(ch, 0.0)
                if mean_val > 0:
                    new_cv_by_channel[ch] = float(std_val / mean_val)

            self.beliefs._set(
                "baseline_cv_by_channel",
                new_cv_by_channel,
                evidence={"n_wells": n, "condition": condition_key},
                supporting_conditions=[condition_key],
                note=f"Updated baseline CV from {n} DMSO wells"
            )

        self.beliefs._set(
            "calibration_reps",
            self.beliefs.calibration_reps + n,
            evidence={"n_wells": n, "condition": condition_key},
            supporting_conditions=[condition_key],
            note=f"Added {n} calibration replicates"
        )

        self.beliefs._set(
            "baseline_std_scalar",
            float(cond.std),
            evidence={"value": float(cond.std), "condition": condition_key},
            supporting_conditions=[condition_key],
            note="Updated baseline std"
        )

        self.beliefs._set(
            "baseline_cv_scalar",
            float(cond.cv),
            evidence={"value": float(cond.cv), "condition": condition_key},
            supporting_conditions=[condition_key],
            note="Updated baseline CV"
        )

        new_cv_history = list(self.beliefs.cv_history)
        new_cv_history.append(float(cond.cv))
        self.beliefs._set(
            "cv_history",
            new_cv_history,
            evidence={"cv": float(cond.cv), "condition": condition_key},
            supporting_conditions=[condition_key],
            note="Added CV to history"
        )

    def _update_pooled_variance(self, cond, condition_key: str) -> Optional[float]:
        """Update pooled variance and compute sigma + CI.

        Returns:
            Relative width of CI (rel_width), or None if not computable
        """
        n = cond.n_wells
        df = n - 1
        sse = df * (float(cond.std) ** 2)

        self.beliefs._set(
            "noise_df_total",
            self.beliefs.noise_df_total + df,
            evidence={"df": df, "sse": sse, "condition": condition_key},
            supporting_conditions=[condition_key],
            note=f"Added {df} df from calibration"
        )

        self.beliefs._set(
            "noise_sse_total",
            self.beliefs.noise_sse_total + sse,
            evidence={"df": df, "sse": sse, "condition": condition_key},
            supporting_conditions=[condition_key],
            note=f"Added {sse:.4f} SSE from calibration"
        )

        # Compute pooled sigma + CI
        if self.beliefs.noise_df_total > 0 and self.beliefs.noise_sse_total > 0:
            sigma2_hat = self.beliefs.noise_sse_total / self.beliefs.noise_df_total
            sigma_hat = math.sqrt(max(sigma2_hat, 0.0))
            ci_low, ci_high = _sigma_ci_from_pooled(self.beliefs.noise_sse_total, self.beliefs.noise_df_total, alpha=0.05)

            self.beliefs._set(
                "noise_sigma_hat",
                sigma_hat,
                evidence={"sigma": sigma_hat, "df": self.beliefs.noise_df_total},
                supporting_conditions=[condition_key],
                note="Updated pooled noise estimate"
            )

            self.beliefs._set(
                "noise_ci_low",
                ci_low,
                evidence={"ci_low": ci_low, "ci_high": ci_high, "df": self.beliefs.noise_df_total},
                supporting_conditions=[condition_key],
                note="Updated noise CI lower bound"
            )

            self.beliefs._set(
                "noise_ci_high",
                ci_high,
                evidence={"ci_low": ci_low, "ci_high": ci_high, "df": self.beliefs.noise_df_total},
                supporting_conditions=[condition_key],
                note="Updated noise CI upper bound"
            )

            if ci_low is not None and ci_high is not None and sigma_hat > 0:
                # TEMP FIX: use abs() since ci_low/ci_high swap bug in chi2 approx
                rel_width = abs(ci_high - ci_low) / sigma_hat
            else:
                rel_width = None

            rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "unknown"
            self.beliefs._set(
                "noise_rel_width",
                rel_width,
                evidence={"rel_width": rel_width, "df": self.beliefs.noise_df_total},
                supporting_conditions=[condition_key],
                note=f"Noise CI width: {rel_width_str}"
            )
            return rel_width
        else:
            return None

    def _update_drift_metric(self, cond) -> Optional[float]:
        """Detect drift in sigma estimates using rolling window comparison.

        Returns:
            Drift metric (normalized change in sigma), or None if insufficient data
        """
        sigma_cycle = float(cond.std)
        self.beliefs.noise_sigma_cycle_history.append(sigma_cycle)
        if len(self.beliefs.noise_sigma_cycle_history) > 20:
            self.beliefs.noise_sigma_cycle_history = self.beliefs.noise_sigma_cycle_history[-20:]

        k = 5
        if len(self.beliefs.noise_sigma_cycle_history) >= 2 * k and self.beliefs.noise_sigma_hat:
            prev = self.beliefs.noise_sigma_cycle_history[-2*k:-k]
            recent = self.beliefs.noise_sigma_cycle_history[-k:]
            prev_m = float(np.mean(prev))
            recent_m = float(np.mean(recent))
            drift_metric = abs(recent_m - prev_m) / float(self.beliefs.noise_sigma_hat)
            self.beliefs.noise_drift_metric = drift_metric
            return drift_metric

        self.beliefs.noise_drift_metric = None
        return None

    def _update_noise_gate_status(self, rel_width: Optional[float], drift_metric: Optional[float], condition_key: str):
        """Evaluate gate status with hysteresis and sequential stability requirement."""
        drift_bad = (drift_metric is not None and drift_metric >= DRIFT_THRESHOLD)
        has_enough_data = (self.beliefs.noise_df_total >= DF_MIN_SANITY)
        current_observation_stable = (
            rel_width is not None and
            rel_width <= ENTER_THRESHOLD and
            not drift_bad
        )

        # Gate logic with sequential stability requirement
        new_stable = self.beliefs.noise_sigma_stable
        if not self.beliefs.noise_sigma_stable:
            # Not yet stable: accumulate evidence
            if has_enough_data:
                if current_observation_stable:
                    self.beliefs.noise_gate_streak += 1
                    if self.beliefs.noise_gate_streak >= NOISE_GATE_STREAK_K:
                        new_stable = True
                else:
                    self.beliefs.noise_gate_streak = 0
            else:
                self.beliefs.noise_gate_streak = 0
        else:
            # Already stable: check for revocation
            should_revoke = (
                drift_bad or
                (rel_width is not None and rel_width >= EXIT_THRESHOLD)
            )
            if should_revoke:
                new_stable = False
                self.beliefs.noise_gate_streak = 0

        # Format note strings
        rel_width_str = f"{self.beliefs.noise_rel_width:.3f}" if self.beliefs.noise_rel_width is not None else "N/A"
        drift_str = f"{drift_metric:.3f}" if drift_metric is not None else "N/A"

        self.beliefs._set(
            "noise_sigma_stable",
            new_stable,
            evidence={
                "pooled_df": self.beliefs.noise_df_total,
                "pooled_sigma": self.beliefs.noise_sigma_hat,
                "ci_low": self.beliefs.noise_ci_low,
                "ci_high": self.beliefs.noise_ci_high,
                "rel_width": self.beliefs.noise_rel_width,
                "enter_threshold": ENTER_THRESHOLD,
                "exit_threshold": EXIT_THRESHOLD,
                "df_min_sanity": DF_MIN_SANITY,
                "drift_metric": drift_metric,
                "drift_threshold": DRIFT_THRESHOLD,
            },
            supporting_conditions=[condition_key],
            note=(
                f"noise_sigma_stable={new_stable} (df={self.beliefs.noise_df_total}, "
                f"rel_width={rel_width_str}, drift={drift_str}, "
                f"streak={self.beliefs.noise_gate_streak}/{NOISE_GATE_STREAK_K})"
            ),
        )
        self.beliefs.noise_sigma_stable = new_stable

    def _emit_noise_diagnostic(self, cond, condition_key: str, diagnostics_out: List):
        """Emit diagnostic event for this calibration cycle."""
        n = cond.n_wells
        sigma_cycle = float(cond.std)

        diagnostics_out.append(
            NoiseDiagnosticEvent(
                cycle=self.beliefs._cycle,
                condition_key=condition_key,
                n_wells=n,
                std_cycle=sigma_cycle,
                mean_cycle=float(cond.mean),
                pooled_df=self.beliefs.noise_df_total,
                pooled_sigma=self.beliefs.noise_sigma_hat or 0.0,
                ci_low=self.beliefs.noise_ci_low,
                ci_high=self.beliefs.noise_ci_high,
                rel_width=self.beliefs.noise_rel_width,
                drift_metric=self.beliefs.noise_drift_metric,
                noise_sigma_stable=self.beliefs.noise_sigma_stable,
                enter_threshold=ENTER_THRESHOLD,
                exit_threshold=EXIT_THRESHOLD,
                df_min=DF_MIN_SANITY,
                drift_threshold=DRIFT_THRESHOLD,
            )
        )
