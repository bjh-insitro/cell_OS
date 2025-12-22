"""
Assay Gate Belief Updater

Updates assay-specific calibration gates (LDH, Cell Painting, scRNA).
Uses pooled variance approach similar to noise gate, but per-assay.
"""

from typing import List, Optional, Tuple
import math

from .base import BaseBeliefUpdater
from ..ledger import cond_key


# Gate thresholds
ENTER_THRESHOLD = 0.25
EXIT_THRESHOLD = 0.40
DF_MIN_SANITY = 40


def _sigma_ci_from_pooled(sse_total: float, df_total: int, alpha: float = 0.05):
    """Compute CI for sigma from pooled variance using chi-square.

    Note: Imported from state.py module-level function.
    """
    from .. import state
    return state._sigma_ci_from_pooled(sse_total, df_total, alpha)


class AssayGateUpdater(BaseBeliefUpdater):
    """
    Updates assay-specific calibration gates.

    Measurement ladder:
    - LDH: scalar viability readout
    - Cell Painting: high-dimensional morphology
    - scRNA: transcriptional state (requires real assay, not proxy)

    Each assay has its own gate with pooled variance tracking.
    """

    def update(self, conditions: List, assay: str) -> None:
        """
        Update assay-specific gate from DMSO baseline conditions.

        Args:
            conditions: List of ConditionSummary objects
            assay: Assay name ("ldh", "cell_paint", or "scrna")
        """
        dmso_conditions = [c for c in conditions if c.compound == 'DMSO' and c.position_tag == 'center']
        if not dmso_conditions:
            return

        # Get assay-specific field names
        field_names = self._get_field_names(assay)
        if not field_names:
            return

        df_field, rel_width_field, stable_field = field_names

        # Accumulate pooled variance
        sse_total, df_total = self._accumulate_pooled_variance(dmso_conditions)

        # Update df field
        current_df = getattr(self.beliefs, df_field)
        total_df = current_df + df_total

        condition_keys = [cond_key(c) for c in dmso_conditions]

        self.beliefs._set(
            df_field,
            total_df,
            evidence={"df_added": df_total, "sse_added": sse_total, "assay": assay},
            supporting_conditions=condition_keys,
            note=f"Added {df_total} df for {assay} assay"
        )

        # Compute pooled sigma + CI
        rel_width = self._compute_rel_width(sse_total, total_df, rel_width_field, assay, condition_keys)

        # Evaluate gate status
        self._evaluate_gate_status(
            assay, stable_field, total_df, rel_width, dmso_conditions, condition_keys
        )

    def _get_field_names(self, assay: str) -> Optional[Tuple[str, str, str]]:
        """Get field names for this assay."""
        if assay == "ldh":
            return ("ldh_df_total", "ldh_rel_width", "ldh_sigma_stable")
        elif assay == "cell_paint":
            return ("cell_paint_df_total", "cell_paint_rel_width", "cell_paint_sigma_stable")
        elif assay == "scrna":
            return ("scrna_df_total", "scrna_rel_width", "scrna_sigma_stable")
        else:
            return None

    def _accumulate_pooled_variance(self, dmso_conditions: List) -> Tuple[float, int]:
        """Accumulate pooled variance from DMSO conditions."""
        sse_total = 0.0
        df_total = 0
        for cond in dmso_conditions:
            n = cond.n_wells
            df = n - 1
            sse = df * (float(cond.std) ** 2)
            df_total += df
            sse_total += sse
        return sse_total, df_total

    def _compute_rel_width(
        self,
        sse_total: float,
        total_df: int,
        rel_width_field: str,
        assay: str,
        condition_keys: List[str]
    ) -> Optional[float]:
        """Compute relative CI width and update belief."""
        if total_df <= 0 or sse_total <= 0:
            return None

        sigma2_hat = sse_total / total_df
        sigma_hat = math.sqrt(max(sigma2_hat, 0.0))
        ci_low, ci_high = _sigma_ci_from_pooled(sse_total, total_df, alpha=0.05)

        if ci_low is not None and ci_high is not None and sigma_hat > 0:
            rel_width = abs(ci_high - ci_low) / sigma_hat
        else:
            rel_width = None

        rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "unknown"
        self.beliefs._set(
            rel_width_field,
            rel_width,
            evidence={"rel_width": rel_width, "df": total_df, "assay": assay},
            supporting_conditions=condition_keys,
            note=f"{assay} CI width: {rel_width_str}"
        )

        return rel_width

    def _evaluate_gate_status(
        self,
        assay: str,
        stable_field: str,
        total_df: int,
        rel_width: Optional[float],
        dmso_conditions: List,
        condition_keys: List[str]
    ):
        """Evaluate gate status with hysteresis."""
        current_stable = getattr(self.beliefs, stable_field)
        new_stable = current_stable

        if not current_stable:
            new_stable = (
                total_df >= DF_MIN_SANITY and
                rel_width is not None and
                rel_width <= ENTER_THRESHOLD
            )
        else:
            new_stable = not (rel_width is not None and rel_width >= EXIT_THRESHOLD)

        # Special handling for scRNA: cannot earn gate with proxy metrics
        if assay == "scrna" and new_stable and not current_stable:
            self._emit_scrna_shadow(total_df, rel_width, dmso_conditions)
            return  # Don't update stable field

        # Update gate status for other assays
        rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"
        metric_source = "proxy:noisy_morphology"  # TODO: detect real assay type

        self.beliefs._set(
            stable_field,
            new_stable,
            evidence={
                "df": total_df,
                "rel_width": rel_width,
                "enter_threshold": ENTER_THRESHOLD,
                "exit_threshold": EXIT_THRESHOLD,
                "df_min_sanity": DF_MIN_SANITY,
                "assay": assay,
                "metric_source": metric_source,
            },
            supporting_conditions=condition_keys,
            note=f"{assay}_sigma_stable={new_stable} (df={total_df}, rel_width={rel_width_str}, {metric_source})",
        )

        # Update metric_source for scRNA
        if assay == "scrna":
            self.beliefs._set(
                "scrna_metric_source",
                metric_source,
                evidence={"assay": "scrna", "source": metric_source},
                supporting_conditions=condition_keys,
                note=f"scRNA metric source: {metric_source}"
            )

    def _emit_scrna_shadow(self, total_df: int, rel_width: Optional[float], dmso_conditions: List):
        """Emit shadow gate event for scRNA (cannot earn with proxy metrics)."""
        rel_width_str = f"{rel_width:.3f}" if rel_width is not None else "N/A"

        self.beliefs._emit_gate_shadow(
            "scrna",
            evidence={
                "df": total_df,
                "rel_width": rel_width,
                "enter_threshold": ENTER_THRESHOLD,
                "exit_threshold": EXIT_THRESHOLD,
                "df_min_sanity": DF_MIN_SANITY,
                "assay": "scrna",
                "metric_source": "proxy:noisy_morphology",
                "gate_blocked": "scRNA gate not earnable with proxy metrics (requires real transcriptional readout)",
            },
            supporting_conditions=[cond_key(c) for c in dmso_conditions],
            note=f"scrna shadow stats (df={total_df}, rel_width={rel_width_str}, source=proxy:noisy_morphology, actionable=false)",
        )

        self.beliefs._set(
            "scrna_metric_source",
            "proxy:noisy_morphology",
            evidence={"assay": "scrna", "source": "proxy"},
            supporting_conditions=[cond_key(c) for c in dmso_conditions],
            note="scRNA using proxy morphology metrics"
        )
