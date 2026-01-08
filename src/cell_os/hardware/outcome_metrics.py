"""
Outcome-Aligned Metrics per Feala's Closed-Loop Manifesto.

"Sensors measuring objectives, not proxies - High-resolution, longitudinal
readouts tracking what actually matters (health outcomes rather than
biomarkers alone)"

This module defines metrics that are more aligned with actual experimental
outcomes than raw assay readouts:

1. Functional metrics (does the treatment work?)
2. Selectivity metrics (on-target vs off-target)
3. Therapeutic window (safe and effective range)
4. Recovery metrics (can cells recover?)

Design principle: Optimize for what we actually care about, not what's
easiest to measure.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import math


@dataclass
class FunctionalOutcome:
    """
    Measures whether the intervention achieved its functional goal.

    This is closer to "did the drug work?" than "did the biomarker change?"
    """
    # Primary outcomes
    viability_48h: float              # Cell survival at endpoint
    viability_delta: float            # Change from baseline

    # Functional readouts
    phenotype_rescued: bool = False   # Did intervention rescue disease phenotype?
    rescue_magnitude: float = 0.0     # How much rescue (0-1 scale)

    # Mechanism engagement
    target_engaged: bool = False      # Did we hit the intended target?
    engagement_confidence: float = 0.0  # Confidence in mechanism call

    # Stress resolution
    stress_resolved: bool = False     # Did cellular stress normalize?
    stress_at_baseline: float = 0.0
    stress_at_endpoint: float = 0.0

    @property
    def functional_score(self) -> float:
        """
        Composite functional outcome score.

        Combines survival, rescue, and mechanism engagement.
        """
        # Survival component (40% weight)
        survival_score = max(0, min(1, self.viability_48h))

        # Rescue component (30% weight)
        rescue_score = self.rescue_magnitude if self.phenotype_rescued else 0.0

        # Mechanism component (30% weight)
        mechanism_score = self.engagement_confidence if self.target_engaged else 0.0

        return 0.4 * survival_score + 0.3 * rescue_score + 0.3 * mechanism_score


@dataclass
class SelectivityMetrics:
    """
    Measures on-target vs off-target effects.

    Critical for drug discovery: a compound that kills everything
    is not a good drug, even if it kills the target cells.
    """
    # On-target effects
    target_effect_magnitude: float = 0.0   # Strength of intended effect
    target_specificity: float = 0.0        # How specific to target (0-1)

    # Off-target effects
    off_target_count: int = 0              # Number of off-target effects observed
    off_target_severity: float = 0.0       # Worst off-target effect (0-1)

    # Selectivity ratios
    on_off_ratio: float = 1.0              # On-target / off-target effect ratio

    # Healthy cell impact
    healthy_cell_toxicity: float = 0.0     # Toxicity to healthy cells (0-1)

    @property
    def selectivity_index(self) -> float:
        """
        Composite selectivity score.

        High selectivity = strong on-target, weak off-target.
        """
        if self.off_target_severity > 0:
            ratio = self.target_effect_magnitude / (self.off_target_severity + 0.01)
        else:
            ratio = self.target_effect_magnitude * 10  # High selectivity if no off-target

        # Normalize to 0-1 scale
        return min(1.0, ratio / 10.0)

    @property
    def is_selective(self) -> bool:
        """Is this compound sufficiently selective?"""
        return self.selectivity_index > 0.5 and self.healthy_cell_toxicity < 0.2


@dataclass
class TherapeuticWindow:
    """
    Measures the range of doses that are both effective and safe.

    A drug with a narrow therapeutic window is harder to use clinically.
    """
    # Dose-response curve parameters
    ec50_um: Optional[float] = None        # Half-maximal effective concentration
    ic50_um: Optional[float] = None        # Half-maximal inhibitory concentration
    ld50_um: Optional[float] = None        # Half-lethal dose

    # Window boundaries
    min_effective_dose: float = 0.0        # Lowest dose with significant effect
    max_safe_dose: float = float('inf')    # Highest dose without significant toxicity

    # Window metrics
    therapeutic_index: Optional[float] = None  # LD50/ED50 ratio

    @property
    def window_width(self) -> float:
        """
        Width of therapeutic window in log-dose units.

        Wider = better (more room for dosing error).
        """
        if self.min_effective_dose <= 0 or self.max_safe_dose <= 0:
            return 0.0
        if self.max_safe_dose <= self.min_effective_dose:
            return 0.0

        return math.log10(self.max_safe_dose / self.min_effective_dose)

    @property
    def has_window(self) -> bool:
        """Is there a therapeutic window at all?"""
        return self.window_width > 0.5  # At least 3-fold range

    def dose_in_window(self, dose_um: float) -> bool:
        """Check if a dose is within the therapeutic window."""
        return self.min_effective_dose <= dose_um <= self.max_safe_dose


@dataclass
class RecoveryMetrics:
    """
    Measures ability of cells to recover after treatment.

    Important for understanding reversibility of effects.
    """
    # Recovery trajectory
    viability_at_treatment: float = 1.0
    viability_24h_post: float = 0.0
    viability_48h_post: float = 0.0

    # Recovery rate
    recovery_half_time_h: Optional[float] = None  # Time to recover 50%

    # Full recovery assessment
    full_recovery_achieved: bool = False
    recovery_plateau: float = 0.0          # Final recovered state

    @property
    def recovery_fraction(self) -> float:
        """Fraction of initial viability recovered."""
        if self.viability_at_treatment <= 0:
            return 0.0

        damage = self.viability_at_treatment - min(
            self.viability_24h_post, self.viability_48h_post
        )
        if damage <= 0:
            return 1.0  # No damage to recover from

        recovered = self.recovery_plateau - min(
            self.viability_24h_post, self.viability_48h_post
        )
        return max(0, min(1, recovered / damage))

    @property
    def is_reversible(self) -> bool:
        """Is the treatment effect reversible?"""
        return self.recovery_fraction > 0.5


@dataclass
class OutcomeMetrics:
    """
    Comprehensive outcome metrics aligned with actual experimental goals.

    Combines functional, selectivity, therapeutic window, and recovery
    into a unified assessment.
    """
    functional: FunctionalOutcome = field(default_factory=FunctionalOutcome)
    selectivity: SelectivityMetrics = field(default_factory=SelectivityMetrics)
    therapeutic_window: TherapeuticWindow = field(default_factory=TherapeuticWindow)
    recovery: RecoveryMetrics = field(default_factory=RecoveryMetrics)

    # Proxy metrics (for comparison)
    morphology_distance: float = 0.0       # Cell painting distance from DMSO
    mechanism_confidence: float = 0.0      # Classifier confidence

    @property
    def outcome_score(self) -> float:
        """
        Composite outcome score combining all metrics.

        This is what we should optimize, not just morphology_distance.
        """
        # Weight the components
        functional_weight = 0.35
        selectivity_weight = 0.25
        window_weight = 0.20
        recovery_weight = 0.20

        scores = {
            'functional': self.functional.functional_score,
            'selectivity': self.selectivity.selectivity_index,
            'window': min(1.0, self.therapeutic_window.window_width / 2.0),  # Normalize
            'recovery': self.recovery.recovery_fraction,
        }

        return (
            functional_weight * scores['functional'] +
            selectivity_weight * scores['selectivity'] +
            window_weight * scores['window'] +
            recovery_weight * scores['recovery']
        )

    @property
    def proxy_vs_outcome_gap(self) -> float:
        """
        Measure discrepancy between proxy metrics and outcome metrics.

        High gap indicates proxy metrics are misleading.
        """
        proxy_score = (self.morphology_distance + self.mechanism_confidence) / 2
        return abs(proxy_score - self.outcome_score)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'outcome_score': self.outcome_score,
            'functional_score': self.functional.functional_score,
            'selectivity_index': self.selectivity.selectivity_index,
            'therapeutic_window_width': self.therapeutic_window.window_width,
            'recovery_fraction': self.recovery.recovery_fraction,
            'proxy_vs_outcome_gap': self.proxy_vs_outcome_gap,
            # Detailed metrics
            'viability_48h': self.functional.viability_48h,
            'target_engaged': self.functional.target_engaged,
            'is_selective': self.selectivity.is_selective,
            'has_window': self.therapeutic_window.has_window,
            'is_reversible': self.recovery.is_reversible,
        }


def compute_outcome_metrics(
    viability_trajectory: List[float],
    mechanism_posterior: Dict[str, float],
    true_mechanism: str,
    dose_response: Optional[Dict[float, float]] = None,
    healthy_cell_viability: float = 1.0
) -> OutcomeMetrics:
    """
    Compute outcome metrics from raw experimental data.

    Args:
        viability_trajectory: Viability at each timepoint [0h, 6h, 12h, ...]
        mechanism_posterior: Posterior probabilities over mechanisms
        true_mechanism: Ground truth mechanism (for evaluation)
        dose_response: Optional dose-response data {dose_um: effect}
        healthy_cell_viability: Viability of untreated healthy cells

    Returns:
        OutcomeMetrics with all components populated
    """
    # Functional outcomes
    viability_48h = viability_trajectory[-1] if viability_trajectory else 0.0
    viability_delta = viability_48h - (viability_trajectory[0] if viability_trajectory else 1.0)

    # Mechanism engagement
    top_mechanism = max(mechanism_posterior, key=mechanism_posterior.get) if mechanism_posterior else None
    target_engaged = (top_mechanism == true_mechanism)
    engagement_confidence = mechanism_posterior.get(true_mechanism, 0.0) if mechanism_posterior else 0.0

    functional = FunctionalOutcome(
        viability_48h=viability_48h,
        viability_delta=viability_delta,
        target_engaged=target_engaged,
        engagement_confidence=engagement_confidence,
    )

    # Selectivity (simplified - would need more data in practice)
    selectivity = SelectivityMetrics(
        target_effect_magnitude=engagement_confidence,
        healthy_cell_toxicity=max(0, 1.0 - healthy_cell_viability),
    )

    # Therapeutic window (from dose-response if available)
    therapeutic_window = TherapeuticWindow()
    if dose_response:
        # Find effective and toxic doses
        doses = sorted(dose_response.keys())
        for dose in doses:
            effect = dose_response[dose]
            if effect > 0.2 and therapeutic_window.min_effective_dose == 0:
                therapeutic_window.min_effective_dose = dose
            if effect > 0.8:  # Assume high effect = toxic
                therapeutic_window.max_safe_dose = dose
                break

    # Recovery (from trajectory)
    recovery = RecoveryMetrics(
        viability_at_treatment=viability_trajectory[0] if viability_trajectory else 1.0,
        viability_48h_post=viability_48h,
        recovery_plateau=viability_48h,
    )

    return OutcomeMetrics(
        functional=functional,
        selectivity=selectivity,
        therapeutic_window=therapeutic_window,
        recovery=recovery,
        mechanism_confidence=engagement_confidence,
    )
