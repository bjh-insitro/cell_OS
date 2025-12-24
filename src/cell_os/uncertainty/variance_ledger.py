"""
Variance ledger: Decompose measurement uncertainty into named contributions.

Tracks three kinds of variance:
- modeled: Deterministic effects that happened in this run
- aleatoric: Irreducible randomness (well-to-well noise)
- epistemic: Uncertainty from unknown calibration parameters

Each contribution records:
- What term (e.g., VAR_CALIBRATION_ASPIRATION_RIDGE)
- What metric (e.g., segmentation_yield)
- How it contributes (delta, multiplier, cv, var)
- Scope (per-well, per-plate, per-run, per-instrument)
- Correlation group (for proper quadrature)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import numpy as np


class VarianceKind(Enum):
    """Kind of variance contribution."""
    MODELED = "modeled"      # Deterministic effect in this run
    ALEATORIC = "aleatoric"  # Irreducible randomness
    EPISTEMIC = "epistemic"  # Calibration uncertainty


class EffectType(Enum):
    """How the contribution affects the metric."""
    DELTA = "delta"          # Additive shift (e.g., -0.05)
    MULTIPLIER = "multiplier"  # Multiplicative factor (e.g., 1.3×)
    CV = "cv"                # Coefficient of variation (e.g., 0.10 = 10%)
    VAR = "var"              # Variance (e.g., 0.01)


@dataclass
class VarianceContribution:
    """
    Single variance contribution to a metric.

    Example:
        VarianceContribution(
            term="VAR_CALIBRATION_ASPIRATION_RIDGE",
            metric="segmentation_yield",
            kind=VarianceKind.EPISTEMIC,
            effect_type=EffectType.CV,
            value=0.10,  # 10% CV
            scope="per_instrument",
            correlation_group="aspiration_ridge",
            context={"sampled_gamma": 1.23, "prior_cv": 0.35}
        )
    """
    term: str                     # Variance term name (e.g., VAR_CALIBRATION_ASPIRATION_RIDGE)
    metric: str                   # Affected metric (e.g., segmentation_yield)
    kind: VarianceKind            # modeled, aleatoric, epistemic
    effect_type: EffectType       # delta, multiplier, cv, var
    value: float                  # Magnitude of contribution
    scope: str                    # per_well, per_plate, per_run, per_instrument
    correlation_group: str = "independent"  # Correlation group for quadrature assumptions
    context: Dict = field(default_factory=dict)  # Optional metadata


class VarianceLedger:
    """
    Append-only log of variance contributions.

    Per-run (ephemeral). Persisted later if needed.
    """

    def __init__(self):
        self.contributions: List[VarianceContribution] = []

    def record(self, contribution: VarianceContribution):
        """Record a variance contribution."""
        self.contributions.append(contribution)

    def query(self, well_id: str = None, metric: str = None) -> List[VarianceContribution]:
        """
        Query contributions by well_id and/or metric.

        Args:
            well_id: Filter by well (if None, all wells)
            metric: Filter by metric (if None, all metrics)

        Returns:
            List of matching contributions
        """
        results = self.contributions

        if well_id is not None:
            results = [c for c in results if c.context.get('well_id') == well_id]

        if metric is not None:
            results = [c for c in results if c.metric == metric]

        return results

    def summarize(self, well_id: str, metric: str) -> Dict:
        """
        Summarize variance for a single well + metric.

        Returns dict with:
        - modeled_effects: List of modeled contributions
        - aleatoric_cv: Combined aleatoric CV
        - epistemic_cv: Combined epistemic CV
        - correlation_groups: List of groups present (for warning)
        """
        contribs = self.query(well_id=well_id, metric=metric)

        modeled = [c for c in contribs if c.kind == VarianceKind.MODELED]
        aleatoric = [c for c in contribs if c.kind == VarianceKind.ALEATORIC]
        epistemic = [c for c in contribs if c.kind == VarianceKind.EPISTEMIC]

        # Combine CVs in quadrature (assumes independence within kind)
        aleatoric_cv = np.sqrt(sum(c.value ** 2 for c in aleatoric if c.effect_type == EffectType.CV))
        epistemic_cv = np.sqrt(sum(c.value ** 2 for c in epistemic if c.effect_type == EffectType.CV))

        # Check correlation groups
        correlation_groups = set(c.correlation_group for c in contribs if c.effect_type == EffectType.CV)

        return {
            'modeled_effects': modeled,
            'aleatoric_cv': float(aleatoric_cv),
            'epistemic_cv': float(epistemic_cv),
            'correlation_groups': list(correlation_groups)
        }


def explain_difference(
    ledger: VarianceLedger,
    well_a: str,
    well_b: str,
    metric: str,
    baseline_value: Optional[float] = None,  # For percent change
    expected_aleatoric_sd: Optional[float] = None  # For z-score
) -> Dict:
    """
    Explain difference in a metric between two wells.

    Decomposes into:
    - Modeled delta (deterministic effects)
    - Aleatoric uncertainty (randomness)
    - Epistemic uncertainty (calibration)
    - Top contributing terms

    NEW: Reporting scale layer for human-meaningful units:
    - Percent change (if baseline_value provided)
    - Z-score relative to expected aleatoric noise (if expected_aleatoric_sd provided)

    Args:
        ledger: Variance ledger with recorded contributions
        well_a: First well ID (e.g., "A1")
        well_b: Second well ID (e.g., "A24")
        metric: Metric to compare (e.g., "noise_mult")
        baseline_value: Baseline value for percent change (optional)
        expected_aleatoric_sd: Expected aleatoric SD for z-score (optional)

    Returns:
        Dict with:
        - delta_modeled: Predicted difference in metric
        - uncertainty_aleatoric_cv: Aleatoric CV
        - uncertainty_epistemic_cv: Epistemic CV
        - top_terms: Ranked list of contributing terms
        - summary: Human-readable report
        - percent_change: (optional) % change relative to baseline
        - z_score: (optional) z-score relative to expected aleatoric
        - correlation_warnings: List of warnings about correlated terms
    """
    # Query contributions for each well
    contribs_a = ledger.query(well_id=well_a, metric=metric)
    contribs_b = ledger.query(well_id=well_b, metric=metric)

    # Partition by kind
    modeled_a = [c for c in contribs_a if c.kind == VarianceKind.MODELED]
    modeled_b = [c for c in contribs_b if c.kind == VarianceKind.MODELED]

    aleatoric_a = [c for c in contribs_a if c.kind == VarianceKind.ALEATORIC]
    aleatoric_b = [c for c in contribs_b if c.kind == VarianceKind.ALEATORIC]

    epistemic_a = [c for c in contribs_a if c.kind == VarianceKind.EPISTEMIC]
    epistemic_b = [c for c in contribs_b if c.kind == VarianceKind.EPISTEMIC]

    # Check correlation groups
    correlation_groups_a = set(c.correlation_group for c in contribs_a if c.effect_type == EffectType.CV)
    correlation_groups_b = set(c.correlation_group for c in contribs_b if c.effect_type == EffectType.CV)
    all_groups = correlation_groups_a | correlation_groups_b

    correlation_warnings = []
    if len(all_groups) > 1 and "independent" not in all_groups:
        correlation_warnings.append(
            f"WARNING: Multiple correlation groups detected: {all_groups}. "
            f"Quadrature combination assumes independence. "
            f"If terms are correlated, total uncertainty may be underestimated."
        )

    # Compute modeled delta
    term_deltas = {}

    # Collect all unique terms
    all_terms = set(c.term for c in modeled_a + modeled_b)

    for term in all_terms:
        # Get contributions from each well
        contrib_a = [c for c in modeled_a if c.term == term]
        contrib_b = [c for c in modeled_b if c.term == term]

        # Compute term-specific delta
        # (Simplified: assume additive deltas for now)
        value_a = sum(c.value for c in contrib_a if c.effect_type == EffectType.DELTA)
        value_b = sum(c.value for c in contrib_b if c.effect_type == EffectType.DELTA)

        # Also handle multipliers (convert to log space for stability)
        mult_a = np.prod([c.value for c in contrib_a if c.effect_type == EffectType.MULTIPLIER] or [1.0])
        mult_b = np.prod([c.value for c in contrib_b if c.effect_type == EffectType.MULTIPLIER] or [1.0])

        # Approximate delta from multipliers (multiplicative difference)
        mult_delta = mult_a - mult_b

        # Combine (simplified: add delta + mult_delta)
        total_delta = (value_a - value_b) + (mult_delta if mult_delta != 0 else 0)

        if total_delta != 0:
            term_deltas[term] = total_delta

    # Total modeled delta
    delta_modeled = sum(term_deltas.values())

    # Combine aleatoric CVs in quadrature
    aleatoric_cv_a = np.sqrt(sum(c.value ** 2 for c in aleatoric_a if c.effect_type == EffectType.CV))
    aleatoric_cv_b = np.sqrt(sum(c.value ** 2 for c in aleatoric_b if c.effect_type == EffectType.CV))
    # Difference between wells: combine as sqrt(cv_a^2 + cv_b^2)
    uncertainty_aleatoric_cv = float(np.sqrt(aleatoric_cv_a ** 2 + aleatoric_cv_b ** 2))

    # Combine epistemic CVs in quadrature
    epistemic_cv_a = np.sqrt(sum(c.value ** 2 for c in epistemic_a if c.effect_type == EffectType.CV))
    epistemic_cv_b = np.sqrt(sum(c.value ** 2 for c in epistemic_b if c.effect_type == EffectType.CV))
    uncertainty_epistemic_cv = float(np.sqrt(epistemic_cv_a ** 2 + epistemic_cv_b ** 2))

    # Rank terms by absolute contribution
    top_terms = sorted(term_deltas.items(), key=lambda x: abs(x[1]), reverse=True)

    # Compute percentages
    total_abs_delta = sum(abs(d) for d in term_deltas.values())
    top_terms_pct = [(term, delta, 100 * abs(delta) / total_abs_delta if total_abs_delta > 0 else 0)
                     for term, delta in top_terms]

    # Total uncertainty (quadrature of aleatoric + epistemic)
    uncertainty_total_cv = float(np.sqrt(uncertainty_aleatoric_cv ** 2 + uncertainty_epistemic_cv ** 2))

    # Uncertainty contribution percentages
    if uncertainty_total_cv > 0:
        aleatoric_pct = 100 * (uncertainty_aleatoric_cv ** 2) / (uncertainty_total_cv ** 2)
        epistemic_pct = 100 * (uncertainty_epistemic_cv ** 2) / (uncertainty_total_cv ** 2)
    else:
        aleatoric_pct = 0.0
        epistemic_pct = 0.0

    # NEW: Reporting scale layer
    percent_change = None
    if baseline_value is not None and baseline_value != 0:
        percent_change = 100 * delta_modeled / baseline_value

    z_score = None
    if expected_aleatoric_sd is not None and expected_aleatoric_sd > 0:
        z_score = delta_modeled / expected_aleatoric_sd

    # Generate human-readable summary
    lines = []
    lines.append(f"Difference in {metric}: {well_a} vs {well_b}")
    lines.append(f"")
    lines.append(f"Modeled difference: {delta_modeled:+.4f}")

    # Add reporting scale if available
    if percent_change is not None:
        lines.append(f"  That's {percent_change:+.2f}% relative to baseline")
    if z_score is not None:
        lines.append(f"  That's {z_score:+.2f}× the expected aleatoric SD")

    lines.append(f"Uncertainty: aleatoric ±{uncertainty_aleatoric_cv:.4f} (CV {uncertainty_aleatoric_cv:.1%}), "
                 f"epistemic ±{uncertainty_epistemic_cv:.4f} (CV {uncertainty_epistemic_cv:.1%})")
    lines.append(f"")

    if top_terms_pct:
        lines.append(f"Primary drivers:")
        for term, delta, pct in top_terms_pct[:5]:  # Top 5
            lines.append(f"  - {term}: {delta:+.4f} ({pct:.0f}% of modeled delta)")

    if uncertainty_total_cv > 0.001:
        lines.append(f"")
        lines.append(f"Uncertainty breakdown:")
        lines.append(f"  - Aleatoric (randomness): {aleatoric_pct:.0f}% of total uncertainty")
        lines.append(f"  - Epistemic (calibration): {epistemic_pct:.0f}% of total uncertainty")

    if correlation_warnings:
        lines.append(f"")
        for warning in correlation_warnings:
            lines.append(f"⚠️  {warning}")

    summary = "\n".join(lines)

    result = {
        'well_a': well_a,
        'well_b': well_b,
        'metric': metric,
        'delta_modeled': float(delta_modeled),
        'uncertainty_aleatoric_cv': uncertainty_aleatoric_cv,
        'uncertainty_epistemic_cv': uncertainty_epistemic_cv,
        'uncertainty_total_cv': uncertainty_total_cv,
        'top_terms': top_terms_pct,
        'aleatoric_pct': aleatoric_pct,
        'epistemic_pct': epistemic_pct,
        'summary': summary,
        'correlation_warnings': correlation_warnings
    }

    # Add reporting scale fields if computed
    if percent_change is not None:
        result['percent_change'] = float(percent_change)
    if z_score is not None:
        result['z_score'] = float(z_score)

    return result
