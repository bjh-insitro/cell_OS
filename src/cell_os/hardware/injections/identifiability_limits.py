"""
Injection L: Identifiability Limits (Permanent Ambiguity)

PROBLEM: Some questions are fundamentally unanswerable. Different mechanisms produce identical outputs.

State Variables:
- confounding_mechanisms: Multiple explanations for same observation
- aliased_parameters: Parameters that cannot be separated
- structural_ambiguity: Fundamental non-identifiability
- observational_equivalence: Different causes, same effect

Pathologies Introduced:
- Mechanism aliasing: Cytostatic vs cytotoxic look identical early
- Parameter confounding: Growth rate × death rate = net rate (can't separate)
- Causal ambiguity: Does drug A cause B, or B cause A?
- Temporal confounding: Early vs late effects indistinguishable
- Compensatory mechanisms: Multiple paths to same phenotype

Exploits Blocked:
- "More data solves everything": Some questions are structurally unanswerable
- "Perfect measurements = perfect knowledge": Confounding is permanent
- "There's a unique explanation": Multiple mechanisms fit the data
- "Causality is observable": Correlation ≠ causation, even with infinite data

Real-World Motivation:
- Cytostatic vs cytotoxic: Both reduce cell count, mechanism unknown
- Growth inhibition: Slower growth or faster death? Can't tell.
- Drug synergy: Additive, synergistic, or just timing? Ambiguous.
- Pathway analysis: Upstream or downstream? Bidirectional causality.
- Resistance mechanisms: Many roads to resistance, assays don't distinguish

Philosophy:
Not all ignorance is curable. Some questions have no answer, not because we
lack data, but because the universe doesn't care about our categories.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple
from enum import Enum
import numpy as np
from .base import InjectionState, Injection, InjectionContext


class ConfoundingType(Enum):
    """Types of fundamental confounding."""
    CYTOSTATIC_VS_CYTOTOXIC = "cytostatic_vs_cytotoxic"
    GROWTH_VS_DEATH = "growth_vs_death"
    EARLY_VS_LATE = "early_vs_late"
    UPSTREAM_VS_DOWNSTREAM = "upstream_vs_downstream"
    ADDITIVE_VS_SYNERGISTIC = "additive_vs_synergistic"


@dataclass
class ConfoundedMechanism:
    """A pair of mechanisms that produce identical observations."""
    name: str
    mechanism_a: str              # First explanation
    mechanism_b: str              # Alternative explanation
    confounding_type: ConfoundingType
    observational_equivalence: float  # 0-1 (1=perfectly confounded)
    true_mechanism: str           # Ground truth (unknown to agent)


@dataclass
class IdentifiabilityLimitsState(InjectionState):
    """
    Identifiability limits state per well.

    Tracks structural ambiguities and confounding.
    """
    vessel_id: str

    # Active confounding scenarios
    confounded_mechanisms: List[ConfoundedMechanism] = field(default_factory=list)

    # Parameter confounding (growth rate × death rate = net rate)
    growth_rate_true: float = 0.10        # True growth rate (hidden)
    death_rate_true: float = 0.05         # True death rate (hidden)
    net_rate_observed: float = 0.05       # Observable net rate (growth - death)

    # Mechanism ambiguity
    cytostatic_fraction: float = 0.0      # True cytostatic effect (hidden)
    cytotoxic_fraction: float = 0.0       # True cytotoxic effect (hidden)
    cell_count_reduction: float = 0.0     # Observable (can't distinguish causes)

    # Causal ambiguity
    pathway_a_active: bool = False        # Pathway A activation
    pathway_b_active: bool = False        # Pathway B activation
    causal_direction: str = "unknown"     # A→B, B→A, or A⇄B (unknown to agent)

    # Temporal confounding
    early_effect_magnitude: float = 0.0   # Effect at t=0
    late_effect_magnitude: float = 0.0    # Effect at t=∞
    observed_at_time: float = 0.0         # When measured (determines what's seen)

    def add_confounding(self, mechanism_a: str, mechanism_b: str,
                       confounding_type: ConfoundingType,
                       true_mechanism: str) -> None:
        """
        Add a confounded mechanism pair.

        Args:
            mechanism_a: First explanation
            mechanism_b: Alternative explanation
            confounding_type: Type of confounding
            true_mechanism: Which is actually true (hidden from agent)
        """
        confounded = ConfoundedMechanism(
            name=f"{mechanism_a}_vs_{mechanism_b}",
            mechanism_a=mechanism_a,
            mechanism_b=mechanism_b,
            confounding_type=confounding_type,
            observational_equivalence=1.0,  # Perfectly confounded
            true_mechanism=true_mechanism,
        )
        self.confounded_mechanisms.append(confounded)

    def set_growth_death_confounding(self, growth: float, death: float) -> None:
        """
        Set growth and death rates (confounded - only net is observable).

        Args:
            growth: True growth rate (hidden)
            death: True death rate (hidden)
        """
        self.growth_rate_true = growth
        self.death_rate_true = death
        self.net_rate_observed = growth - death
        # Agent can only see net_rate, can't separate growth and death!

    def set_cytostatic_cytotoxic_confounding(self, cytostatic: float,
                                             cytotoxic: float) -> None:
        """
        Set cytostatic vs cytotoxic effects (confounded early on).

        Args:
            cytostatic: Fraction of cells growth-arrested
            cytotoxic: Fraction of cells killed
        """
        self.cytostatic_fraction = cytostatic
        self.cytotoxic_fraction = cytotoxic
        # Both reduce cell count - can't distinguish without long observation
        self.cell_count_reduction = cytostatic + cytotoxic

    def get_observable_net_rate(self) -> float:
        """
        Get observable net growth rate.

        Agent can measure this, but can't separate growth and death.

        Returns:
            Net rate (growth - death)
        """
        return self.net_rate_observed

    def get_observable_cell_count_change(self) -> float:
        """
        Get observable cell count reduction.

        Agent can measure this, but can't tell if cytostatic or cytotoxic.

        Returns:
            Cell count reduction (0-1)
        """
        return self.cell_count_reduction

    def check_identifiability(self, mechanism_type: str) -> bool:
        """
        Check if a mechanism is identifiable from observations.

        Args:
            mechanism_type: Type to check

        Returns:
            True if identifiable, False if confounded
        """
        for confounded in self.confounded_mechanisms:
            if mechanism_type in [confounded.mechanism_a, confounded.mechanism_b]:
                if confounded.observational_equivalence > 0.8:
                    return False  # Not identifiable
        return True  # Identifiable

    def get_confounding_report(self) -> Dict[str, Any]:
        """Get report of all active confounding."""
        return {
            'n_confounded_mechanisms': len(self.confounded_mechanisms),
            'growth_death_confounded': True,
            'cytostatic_cytotoxic_confounded': self.cell_count_reduction > 0,
            'confounding_scenarios': [
                {
                    'mechanism_a': c.mechanism_a,
                    'mechanism_b': c.mechanism_b,
                    'type': c.confounding_type.value,
                    'equivalence': c.observational_equivalence,
                }
                for c in self.confounded_mechanisms
            ],
        }

    def check_invariants(self) -> None:
        """Check state is valid."""
        if not (0.0 <= self.growth_rate_true <= 1.0):
            raise ValueError(f"Invalid growth rate: {self.growth_rate_true}")

        if not (0.0 <= self.death_rate_true <= 1.0):
            raise ValueError(f"Invalid death rate: {self.death_rate_true}")


class IdentifiabilityLimitsInjection(Injection):
    """
    Injection L: Identifiability Limits (Permanent Ambiguity).

    Makes some questions fundamentally unanswerable. Agents must:
    - Recognize that different mechanisms can produce identical observations
    - Understand that more data doesn't always help (structural confounding)
    - Accept that some parameters cannot be separated
    - Know that causal direction may be unknowable
    - Realize that perfect measurements ≠ perfect knowledge
    """

    def __init__(self, seed: int = 0):
        """
        Initialize identifiability limits injection.

        Args:
            seed: RNG seed (unused, confounding is deterministic)
        """
        self.rng = np.random.default_rng(seed + 1100)

    def create_state(self, vessel_id: str, context: InjectionContext) -> IdentifiabilityLimitsState:
        """
        Create identifiability limits state for a well.

        Initial state: No confounding (identifiable).
        """
        state = IdentifiabilityLimitsState(
            vessel_id=vessel_id,
            confounded_mechanisms=[],
            growth_rate_true=0.10,
            death_rate_true=0.05,
            net_rate_observed=0.05,
            cytostatic_fraction=0.0,
            cytotoxic_fraction=0.0,
            cell_count_reduction=0.0,
            pathway_a_active=False,
            pathway_b_active=False,
            causal_direction="unknown",
            early_effect_magnitude=0.0,
            late_effect_magnitude=0.0,
            observed_at_time=0.0,
        )
        return state

    def apply_time_step(self, state: IdentifiabilityLimitsState, dt: float, context: InjectionContext) -> None:
        """
        Time doesn't resolve confounding (it's structural).

        Args:
            dt: Time step (hours)
        """
        # Confounding is permanent - time doesn't help
        pass

    def on_event(self, state: IdentifiabilityLimitsState, context: InjectionContext) -> None:
        """
        Trigger confounding scenarios.

        Events:
        - 'introduce_growth_death_confounding': Growth vs death ambiguity
        - 'introduce_cytostatic_cytotoxic': Mechanism ambiguity
        - 'introduce_pathway_confounding': Causal direction ambiguity
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'introduce_growth_death_confounding':
            # Set growth and death rates (only net is observable)
            growth = params.get('growth_rate', 0.15)
            death = params.get('death_rate', 0.10)
            state.set_growth_death_confounding(growth, death)

            # Add to confounding list
            state.add_confounding(
                "growth_rate",
                "death_rate",
                ConfoundingType.GROWTH_VS_DEATH,
                "confounded"
            )

        elif event_type == 'introduce_cytostatic_cytotoxic':
            # Cytostatic vs cytotoxic confounding
            mechanism = params.get('true_mechanism', 'cytotoxic')
            fraction = params.get('fraction', 0.30)

            if mechanism == 'cytostatic':
                state.set_cytostatic_cytotoxic_confounding(fraction, 0.0)
            elif mechanism == 'cytotoxic':
                state.set_cytostatic_cytotoxic_confounding(0.0, fraction)
            else:  # Mixed
                state.set_cytostatic_cytotoxic_confounding(fraction * 0.5, fraction * 0.5)

            # Add to confounding list
            state.add_confounding(
                "cytostatic",
                "cytotoxic",
                ConfoundingType.CYTOSTATIC_VS_CYTOTOXIC,
                mechanism
            )

        elif event_type == 'introduce_pathway_confounding':
            # Pathway A and B both active, causal direction unknown
            state.pathway_a_active = True
            state.pathway_b_active = True
            state.causal_direction = params.get('causal_direction', 'bidirectional')

            state.add_confounding(
                "pathway_a_upstream",
                "pathway_b_upstream",
                ConfoundingType.UPSTREAM_VS_DOWNSTREAM,
                state.causal_direction
            )

    def get_biology_modifiers(self, state: IdentifiabilityLimitsState, context: InjectionContext) -> Dict[str, Any]:
        """
        Confounding affects biology (via true mechanisms).

        Returns:
            Dict with true values (hidden from measurements)
        """
        return {
            'growth_rate_true': state.growth_rate_true,
            'death_rate_true': state.death_rate_true,
            'cytostatic_fraction_true': state.cytostatic_fraction,
            'cytotoxic_fraction_true': state.cytotoxic_fraction,
        }

    def get_measurement_modifiers(self, state: IdentifiabilityLimitsState, context: InjectionContext) -> Dict[str, Any]:
        """
        Measurements can only see observable quantities (confounded).

        Returns:
            Dict with observable values (ambiguous)
        """
        # Agent can only observe net quantities
        return {
            'net_growth_rate_observable': state.get_observable_net_rate(),
            'cell_count_reduction_observable': state.get_observable_cell_count_change(),
            'growth_rate_identifiable': False,  # Confounded with death
            'death_rate_identifiable': False,   # Confounded with growth
            'mechanism_identifiable': not state.check_identifiability('cytostatic'),
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: IdentifiabilityLimitsState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add identifiability metadata to observations.

        IMPORTANT: Observations show ONLY observable quantities, not ground truth.
        """
        # Add observable quantities (what agent can measure)
        observation['net_growth_rate'] = state.get_observable_net_rate()
        observation['cell_count_reduction'] = state.get_observable_cell_count_change()

        # Add confounding metadata (agent knows they're confounded)
        confounding_report = state.get_confounding_report()
        observation['n_confounded_mechanisms'] = confounding_report['n_confounded_mechanisms']
        observation['growth_death_confounded'] = confounding_report['growth_death_confounded']

        # Warn about identifiability limits
        if confounding_report['n_confounded_mechanisms'] > 0:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'identifiability_limit_{confounding_report["n_confounded_mechanisms"]}_confounded'
            )

        # Note specific confounding scenarios
        for scenario in confounding_report['confounding_scenarios']:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'confounded_{scenario["type"]}'
            )

        # Add ambiguity flag
        if confounding_report['n_confounded_mechanisms'] > 0:
            observation['permanent_ambiguity_present'] = True
            observation['more_data_helps'] = False  # More data won't resolve confounding

        return observation
