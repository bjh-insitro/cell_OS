"""
RewardSpec: Epistemic governance layer for Phase 5B+6A

Makes refusal diagnostic and actionable:
- Decomposes uncertainty budget
- Proposes rescue plans
- Validates that uncertainty decays under correct action

Invariants:
A. Refusal must be specific (decompose variance sources)
B. Every refusal implies cheapest rescue (actionable guidance)
C. Uncertainty must decay under correct action (validated predictions)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum
import numpy as np


class UncertaintySource(Enum):
    """Sources of epistemic uncertainty in Phase 5B."""
    ARTIFACT = "plating_artifact"  # Post-dissociation stress (temporal decay)
    HETEROGENEITY = "biological_heterogeneity"  # Subpopulation mixture
    CONTEXT = "run_context"  # Batch/lot/instrument effects
    PIPELINE = "pipeline_drift"  # Feature extraction failures
    MEASUREMENT = "measurement_noise"  # Irreducible technical noise


@dataclass
class UncertaintyBudget:
    """
    Decomposed uncertainty budget at a timepoint.

    Invariant A: Refusal must be specific.
    When confidence is low, this tells you WHY.
    """
    # Absolute contributions (variance units)
    artifact_var: float  # Plating artifact contribution
    heterogeneity_var: float  # Biological mixture width²
    context_var: float  # RunContext channel biases
    pipeline_var: float  # Batch-dependent segmentation
    measurement_var: float  # Technical noise floor

    # Total and confidence
    total_var: float  # Sum of variances
    confidence: float  # 0-1, higher is better

    @property
    def artifact_fraction(self) -> float:
        """Fraction of total variance from plating artifacts."""
        return self.artifact_var / self.total_var if self.total_var > 0 else 0.0

    @property
    def heterogeneity_fraction(self) -> float:
        """Fraction of total variance from biological heterogeneity."""
        return self.heterogeneity_var / self.total_var if self.total_var > 0 else 0.0

    @property
    def context_fraction(self) -> float:
        """Fraction of total variance from context effects."""
        return self.context_var / self.total_var if self.total_var > 0 else 0.0

    @property
    def pipeline_fraction(self) -> float:
        """Fraction of total variance from pipeline drift."""
        return self.pipeline_var / self.total_var if self.total_var > 0 else 0.0

    @property
    def dominant_source(self) -> UncertaintySource:
        """Which uncertainty source dominates?"""
        fractions = {
            UncertaintySource.ARTIFACT: self.artifact_fraction,
            UncertaintySource.HETEROGENEITY: self.heterogeneity_fraction,
            UncertaintySource.CONTEXT: self.context_fraction,
            UncertaintySource.PIPELINE: self.pipeline_fraction,
            UncertaintySource.MEASUREMENT: self.measurement_var / self.total_var
        }
        return max(fractions.items(), key=lambda x: x[1])[0]

    def summary(self) -> str:
        """Human-readable summary of uncertainty budget."""
        return (
            f"UncertaintyBudget(confidence={self.confidence:.3f}, total_var={self.total_var:.4f}):\n"
            f"  Artifact: {self.artifact_fraction:.1%}\n"
            f"  Heterogeneity: {self.heterogeneity_fraction:.1%}\n"
            f"  Context: {self.context_fraction:.1%}\n"
            f"  Pipeline: {self.pipeline_fraction:.1%}\n"
            f"  Measurement: {self.measurement_var/self.total_var:.1%}\n"
            f"  Dominant: {self.dominant_source.value}"
        )


@dataclass
class RescueOption:
    """
    One way to rescue a low-confidence measurement.

    Invariant B: Every refusal implies cheapest rescue.
    """
    action: str  # "WAIT_TO_24H", "ADD_CALIBRATION", "COMMIT_NOW"
    confidence_delta: float  # Predicted change in confidence (-1 to +1)
    cost_h: float  # Time cost in hours
    cost_wells: int  # Additional well cost
    rationale: str  # Why this helps (or doesn't)

    @property
    def efficiency(self) -> float:
        """Confidence gain per unit cost (higher is better)."""
        total_cost = self.cost_h / 12.0 + self.cost_wells / 8.0  # Normalize to ~1
        if total_cost <= 0:
            return self.confidence_delta if self.confidence_delta > 0 else 0.0
        return self.confidence_delta / total_cost


@dataclass
class RescuePlan:
    """
    Ranked options for rescuing low-confidence measurement.

    Invariant B: Actionable guidance, not excuse-making.
    """
    current_confidence: float
    target_confidence: float  # Desired confidence threshold
    options: List[RescueOption]

    @property
    def recommended(self) -> Optional[RescueOption]:
        """Highest efficiency option with positive gain."""
        positive_options = [opt for opt in self.options if opt.confidence_delta > 0]
        if not positive_options:
            # No rescue available → commit now or abandon
            return RescueOption(
                action="COMMIT_NOW_OR_ABANDON",
                confidence_delta=0.0,
                cost_h=0,
                cost_wells=0,
                rationale="No rescue improves confidence; either commit or abandon"
            )
        return max(positive_options, key=lambda opt: opt.efficiency)

    def summary(self) -> str:
        """Human-readable rescue plan."""
        lines = [
            f"RescuePlan(current={self.current_confidence:.3f}, target={self.target_confidence:.3f}):"
        ]
        for i, opt in enumerate(sorted(self.options, key=lambda x: -x.efficiency)):
            marker = "→" if opt == self.recommended else " "
            lines.append(
                f"{marker} {opt.action}: Δconf={opt.confidence_delta:+.3f}, "
                f"cost={opt.cost_h:.0f}h+{opt.cost_wells}wells, "
                f"eff={opt.efficiency:.3f}"
            )
            lines.append(f"     {opt.rationale}")
        return "\n".join(lines)


@dataclass
class EpistemicState:
    """
    Complete epistemic state at a decision point.

    Combines:
    - What we know (mechanism signal, viability)
    - What we're uncertain about (UncertaintyBudget)
    - What we can do about it (RescuePlan)
    """
    time_h: float
    mechanism_signal: float  # Actin fold or similar
    mechanism_confidence: float  # 0-1
    viability: float  # 0-1

    uncertainty_budget: UncertaintyBudget
    rescue_plan: Optional[RescuePlan]

    def should_commit(self, confidence_threshold: float = 0.7) -> bool:
        """Should we commit to classification now?"""
        if self.mechanism_confidence >= confidence_threshold:
            return True

        # Check if waiting makes it worse
        if self.rescue_plan:
            best_option = self.rescue_plan.recommended
            if best_option and best_option.confidence_delta <= 0:
                # No rescue helps → commit now or abandon
                return True  # Commit now (or abandon if signal too weak)

        return False

    def summary(self) -> str:
        """Human-readable epistemic state."""
        commit = "COMMIT" if self.should_commit() else "DEFER"
        return (
            f"EpistemicState @ {self.time_h:.0f}h [{commit}]:\n"
            f"  Mechanism signal: {self.mechanism_signal:.2f}×\n"
            f"  Confidence: {self.mechanism_confidence:.3f}\n"
            f"  Viability: {self.viability:.3f}\n"
            f"  {self.uncertainty_budget.summary()}\n"
            f"  {self.rescue_plan.summary() if self.rescue_plan else 'No rescue plan'}"
        )


def compute_uncertainty_budget_from_vessel(
    vessel,
    simulated_time: float,
    field: str = 'transport_dysfunction'
) -> UncertaintyBudget:
    """
    Compute UncertaintyBudget from VesselState.

    Decomposes total variance into sources:
    - Artifact: plating context (time-dependent decay)
    - Heterogeneity: subpopulation mixture width
    - Context: RunContext channel biases (estimated)
    - Pipeline: batch-dependent segmentation (estimated)
    - Measurement: technical noise floor (estimated)
    """
    # Base biological heterogeneity (subpopulation mixture)
    base_width = vessel.get_mixture_width(field)
    heterogeneity_var = base_width ** 2

    # Artifact inflation (plating context)
    if vessel.plating_context is not None:
        time_since_seed = simulated_time - vessel.seed_time
        tau_recovery = vessel.plating_context['tau_recovery_h']
        post_dissoc = vessel.plating_context['post_dissociation_stress']
        clumpiness = vessel.plating_context['clumpiness']

        artifact_width = (post_dissoc + clumpiness) * float(
            np.exp(-time_since_seed / tau_recovery)
        )
        artifact_var = artifact_width ** 2
    else:
        artifact_var = 0.0

    # Context variance (RunContext channel biases)
    # Estimated as 15% channel bias → ~0.15² = 0.0225 variance
    context_var = 0.0225  # TODO: compute from actual run_context

    # Pipeline variance (batch-dependent segmentation)
    # Estimated as 10% segmentation bias → ~0.10² = 0.01 variance
    pipeline_var = 0.01  # TODO: compute from actual batch effects

    # Measurement noise floor (irreducible technical noise)
    # Estimated as 5% CV → ~0.05² = 0.0025 variance
    measurement_var = 0.0025

    # Total variance (sum, assuming independence)
    total_var = heterogeneity_var + artifact_var + context_var + pipeline_var + measurement_var

    # Confidence from total uncertainty
    # Base confidence 0.80, penalty from width
    base_confidence = 0.80
    total_width = float(np.sqrt(total_var))
    width_penalty = min(1.0, total_width / 0.3)
    confidence = base_confidence * (1.0 - width_penalty)

    return UncertaintyBudget(
        artifact_var=artifact_var,
        heterogeneity_var=heterogeneity_var,
        context_var=context_var,
        pipeline_var=pipeline_var,
        measurement_var=measurement_var,
        total_var=total_var,
        confidence=confidence
    )


def propose_rescue_plan(
    current_budget: UncertaintyBudget,
    current_time_h: float,
    viability: float,
    target_confidence: float = 0.75
) -> RescuePlan:
    """
    Propose rescue options based on uncertainty decomposition.

    Invariant B: Every refusal implies cheapest rescue.
    Invariant C: Uncertainty decays under correct action (or we predict it won't).
    """
    options = []

    # Option 1: Wait (reduces artifact, but may increase heterogeneity if dying)
    if current_budget.artifact_fraction > 0.2:  # Artifact substantial
        # Predict artifact decay
        artifact_reduction = current_budget.artifact_var * 0.5  # Assume 50% decay over 12h
        # Predict heterogeneity change (increases if dying)
        heterogeneity_increase = current_budget.heterogeneity_var * 0.2 if viability < 0.5 else 0.0

        predicted_var = (
            current_budget.artifact_var - artifact_reduction +
            current_budget.heterogeneity_var + heterogeneity_increase +
            current_budget.context_var +
            current_budget.pipeline_var +
            current_budget.measurement_var
        )
        predicted_width = float(np.sqrt(predicted_var))
        predicted_confidence = 0.80 * (1.0 - min(1.0, predicted_width / 0.3))

        confidence_delta = predicted_confidence - current_budget.confidence

        options.append(RescueOption(
            action="WAIT_TO_24H",
            confidence_delta=confidence_delta,
            cost_h=12.0,
            cost_wells=0,
            rationale=f"Reduces artifact by 50%, but heterogeneity {'increases' if heterogeneity_increase > 0 else 'stable'}"
        ))
    else:
        # Artifact minor → waiting doesn't help
        options.append(RescueOption(
            action="WAIT_TO_24H",
            confidence_delta=-0.05,  # Makes it worse (heterogeneity increases)
            cost_h=12.0,
            cost_wells=0,
            rationale="Artifact minor ({}%); waiting degrades signal as cells die".format(
                int(current_budget.artifact_fraction * 100)
            )
        ))

    # Option 2: Add calibration wells (reduces context/pipeline variance)
    if current_budget.context_fraction > 0.15 or current_budget.pipeline_fraction > 0.10:
        # Calibration can halve context + pipeline variance
        context_reduction = current_budget.context_var * 0.5
        pipeline_reduction = current_budget.pipeline_var * 0.5

        predicted_var = (
            current_budget.artifact_var +
            current_budget.heterogeneity_var +
            current_budget.context_var - context_reduction +
            current_budget.pipeline_var - pipeline_reduction +
            current_budget.measurement_var
        )
        predicted_width = float(np.sqrt(predicted_var))
        predicted_confidence = 0.80 * (1.0 - min(1.0, predicted_width / 0.3))

        confidence_delta = predicted_confidence - current_budget.confidence

        options.append(RescueOption(
            action="ADD_CALIBRATION_WELLS",
            confidence_delta=confidence_delta,
            cost_h=0,
            cost_wells=8,
            rationale="Separates context ({:.0%}) + pipeline ({:.0%}) from biology".format(
                current_budget.context_fraction, current_budget.pipeline_fraction
            )
        ))

    # Option 3: Commit now (no improvement, but no cost)
    options.append(RescueOption(
        action="COMMIT_NOW",
        confidence_delta=0.0,
        cost_h=0,
        cost_wells=0,
        rationale="Accept current confidence; no rescue available or waiting makes it worse"
    ))

    return RescuePlan(
        current_confidence=current_budget.confidence,
        target_confidence=target_confidence,
        options=options
    )
