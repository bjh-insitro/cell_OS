"""
Expanded Action Space per Feala's Closed-Loop Manifesto.

"Expanded action space - Multiple 'knobs' (drugs, biomolecules, stimulation)
rather than single interventions"

This module extends the basic Action (dose, washout, feed) with:
1. Environmental controls (temperature, oxygen)
2. Combinatorial treatments (secondary compounds)
3. Temporal controls (pulse duration, recovery time)
4. Media modifications (serum, supplements)

Design principle: Actions should be composable and parametric.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class EnvironmentalStressor(str, Enum):
    """Environmental perturbations beyond compound treatment."""
    NONE = "none"
    HYPOXIA = "hypoxia"           # Low O2 (1-5%)
    HYPEROXIA = "hyperoxia"       # High O2 (>21%)
    HYPOTHERMIA = "hypothermia"   # Cold stress (30-35°C)
    HYPERTHERMIA = "hyperthermia" # Heat stress (39-42°C)
    SERUM_STARVATION = "serum_starvation"  # Growth factor withdrawal
    NUTRIENT_STRESS = "nutrient_stress"     # Glucose/glutamine depletion


@dataclass
class EnvironmentalControl:
    """Environmental parameters that can be modulated.

    Default values represent standard culture conditions.
    """
    temperature_c: float = 37.0       # Celsius (standard: 37°C)
    oxygen_pct: float = 21.0          # O2 percentage (standard: 21%, hypoxia: 1-5%)
    co2_pct: float = 5.0              # CO2 percentage (standard: 5%)
    serum_pct: float = 10.0           # FBS percentage (standard: 10%, starvation: 0-2%)
    glucose_mm: float = 25.0          # Glucose mM (standard DMEM: 25mM, low: 1-5mM)

    def is_standard(self) -> bool:
        """Check if conditions are standard (no environmental stress)."""
        return (
            abs(self.temperature_c - 37.0) < 0.5 and
            abs(self.oxygen_pct - 21.0) < 1.0 and
            abs(self.serum_pct - 10.0) < 0.5 and
            abs(self.glucose_mm - 25.0) < 1.0
        )

    def describe_stress(self) -> Optional[str]:
        """Describe any active environmental stressor."""
        stressors = []
        if self.temperature_c < 35:
            stressors.append(f"hypothermia({self.temperature_c}°C)")
        elif self.temperature_c > 38:
            stressors.append(f"hyperthermia({self.temperature_c}°C)")
        if self.oxygen_pct < 10:
            stressors.append(f"hypoxia({self.oxygen_pct}%O2)")
        elif self.oxygen_pct > 30:
            stressors.append(f"hyperoxia({self.oxygen_pct}%O2)")
        if self.serum_pct < 2:
            stressors.append(f"serum_starvation({self.serum_pct}%)")
        if self.glucose_mm < 5:
            stressors.append(f"glucose_restriction({self.glucose_mm}mM)")
        return ", ".join(stressors) if stressors else None


@dataclass
class CombinatorialTreatment:
    """Secondary compound for combination therapy.

    Enables testing drug combinations and synergy detection.
    """
    compound_id: Optional[str] = None
    dose_um: float = 0.0

    # Timing relative to primary compound
    delay_h: float = 0.0              # Hours after primary compound
    simultaneous: bool = True         # Apply at same time as primary

    def is_active(self) -> bool:
        return self.compound_id is not None and self.dose_um > 0


@dataclass
class TemporalControl:
    """Temporal parameters for treatment timing.

    Enables pulse treatments, pre-conditioning, and recovery periods.
    """
    pulse_duration_h: float = 6.0     # How long compound stays (default: full step)
    recovery_time_h: float = 0.0      # Time without compound before next step
    pre_condition_h: float = 0.0      # Environmental stress before compound

    def is_continuous(self) -> bool:
        """Check if treatment is continuous (default)."""
        return self.pulse_duration_h >= 6.0 and self.recovery_time_h == 0.0


@dataclass
class ExpandedAction:
    """
    Rich action representation per Feala's "expanded action space" principle.

    Combines:
    - Primary compound treatment (dose, washout, feed) - existing
    - Environmental controls (temp, O2, media) - NEW
    - Combinatorial treatments (secondary compound) - NEW
    - Temporal controls (pulse, recovery) - NEW

    This enables more sophisticated intervention strategies that better
    mirror real experimental possibilities.
    """
    # Primary treatment (from existing Action)
    dose_fraction: float = 0.0        # 0, 0.25, 0.5, 1.0
    washout: bool = False
    feed: bool = False

    # Environmental controls (NEW)
    environment: EnvironmentalControl = field(default_factory=EnvironmentalControl)

    # Combinatorial treatment (NEW)
    combination: CombinatorialTreatment = field(default_factory=CombinatorialTreatment)

    # Temporal control (NEW)
    timing: TemporalControl = field(default_factory=TemporalControl)

    def to_basic_action(self):
        """Convert to basic Action for backward compatibility."""
        from .episode import Action
        return Action(
            dose_fraction=self.dose_fraction,
            washout=self.washout,
            feed=self.feed
        )

    @classmethod
    def from_basic_action(cls, action) -> 'ExpandedAction':
        """Create ExpandedAction from basic Action."""
        return cls(
            dose_fraction=action.dose_fraction,
            washout=action.washout,
            feed=action.feed
        )

    def is_simple(self) -> bool:
        """Check if this is equivalent to a basic Action (no expanded features)."""
        return (
            self.environment.is_standard() and
            not self.combination.is_active() and
            self.timing.is_continuous()
        )

    def describe(self) -> str:
        """Human-readable description of the action."""
        parts = []

        # Primary treatment
        if self.dose_fraction > 0:
            parts.append(f"dose={self.dose_fraction:.2f}×")
        if self.washout:
            parts.append("washout")
        if self.feed:
            parts.append("feed")

        # Environmental
        env_stress = self.environment.describe_stress()
        if env_stress:
            parts.append(f"env[{env_stress}]")

        # Combination
        if self.combination.is_active():
            parts.append(f"+{self.combination.compound_id}@{self.combination.dose_um}µM")

        # Timing
        if not self.timing.is_continuous():
            parts.append(f"pulse={self.timing.pulse_duration_h}h")

        return f"ExpandedAction({', '.join(parts) if parts else 'noop'})"

    def __str__(self):
        return self.describe()


# Predefined action templates for common experimental patterns
class ActionTemplates:
    """Factory for common expanded actions."""

    @staticmethod
    def standard_dose(fraction: float = 1.0) -> ExpandedAction:
        """Standard compound treatment at given dose fraction."""
        return ExpandedAction(dose_fraction=fraction)

    @staticmethod
    def hypoxia_preconditioning(hours: float = 6.0) -> ExpandedAction:
        """Hypoxic preconditioning before treatment."""
        return ExpandedAction(
            environment=EnvironmentalControl(oxygen_pct=1.0),
            timing=TemporalControl(pre_condition_h=hours)
        )

    @staticmethod
    def pulse_treatment(dose_fraction: float, pulse_h: float = 2.0) -> ExpandedAction:
        """Short pulse of compound followed by washout."""
        return ExpandedAction(
            dose_fraction=dose_fraction,
            timing=TemporalControl(pulse_duration_h=pulse_h),
            washout=True
        )

    @staticmethod
    def combination_therapy(
        primary_dose: float,
        secondary_compound: str,
        secondary_dose: float
    ) -> ExpandedAction:
        """Simultaneous two-compound treatment."""
        return ExpandedAction(
            dose_fraction=primary_dose,
            combination=CombinatorialTreatment(
                compound_id=secondary_compound,
                dose_um=secondary_dose,
                simultaneous=True
            )
        )

    @staticmethod
    def serum_starvation_sensitization(starvation_h: float = 24.0) -> ExpandedAction:
        """Serum starvation to sensitize cells."""
        return ExpandedAction(
            environment=EnvironmentalControl(serum_pct=0.5),
            timing=TemporalControl(pre_condition_h=starvation_h)
        )


# Action space enumeration for beam search
def enumerate_expanded_actions(
    dose_levels: List[float] = None,
    include_environmental: bool = False,
    include_combinations: bool = False,
    available_combinations: List[str] = None
) -> List[ExpandedAction]:
    """
    Enumerate possible actions for search algorithms.

    Args:
        dose_levels: Dose fractions to consider (default: [0, 0.25, 0.5, 1.0])
        include_environmental: Include environmental stressors
        include_combinations: Include combination treatments
        available_combinations: List of secondary compound IDs

    Returns:
        List of possible ExpandedActions
    """
    if dose_levels is None:
        dose_levels = [0.0, 0.25, 0.5, 1.0]

    if available_combinations is None:
        available_combinations = []

    actions = []

    # Basic actions (dose × washout × feed)
    for dose in dose_levels:
        for washout in [False, True]:
            for feed in [False, True]:
                # Skip illegal: washout without prior dose
                if washout and dose == 0:
                    continue
                actions.append(ExpandedAction(
                    dose_fraction=dose,
                    washout=washout,
                    feed=feed
                ))

    # Environmental variations (if enabled)
    if include_environmental:
        for dose in [0.0, 1.0]:  # Only at no-dose or full-dose
            # Hypoxia
            actions.append(ExpandedAction(
                dose_fraction=dose,
                environment=EnvironmentalControl(oxygen_pct=1.0)
            ))
            # Heat stress
            actions.append(ExpandedAction(
                dose_fraction=dose,
                environment=EnvironmentalControl(temperature_c=42.0)
            ))
            # Serum starvation
            actions.append(ExpandedAction(
                dose_fraction=dose,
                environment=EnvironmentalControl(serum_pct=0.5)
            ))

    # Combinations (if enabled)
    if include_combinations and available_combinations:
        for primary_dose in [0.5, 1.0]:
            for combo_compound in available_combinations[:3]:  # Limit search space
                actions.append(ExpandedAction(
                    dose_fraction=primary_dose,
                    combination=CombinatorialTreatment(
                        compound_id=combo_compound,
                        dose_um=1.0,  # Standard dose
                        simultaneous=True
                    )
                ))

    return actions
