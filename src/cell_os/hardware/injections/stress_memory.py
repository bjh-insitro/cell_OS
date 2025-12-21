"""
Injection G: Stress Memory (Wells Remember Insults)

PROBLEM: Cells don't reset to baseline after stress. They remember.

State Variables:
- stress_exposures: History of stress events (type, magnitude, time)
- adaptive_resistance: Resistance levels per stress type (0-1)
- hardening_factor: General stress tolerance (0-0.5)
- priming_active: Whether stress response is primed
- sensitization_factor: Over-stressing makes cells MORE sensitive (0-0.3)

Pathologies Introduced:
- Repeated stress X → increased resistance to X (adaptive resistance)
- Multiple stress types → general hardening (cross-resistance)
- Recent stress → primed response (faster, stronger)
- Excessive stress → sensitization (more fragile, not tougher)
- Memory decays over days-weeks (not instant reset)

Exploits Blocked:
- "Washout resets to baseline": Cells remember stress
- "Every dose-response is the same": Prior exposure shifts curves
- "Stress is stateless": Past insults matter
- "More stress always equals more damage": Hardening can occur

Real-World Motivation:
- Preconditioning: Low stress protects against high stress
- Heat shock response: Prior heat stress → chaperone upregulation
- Drug resistance: Sublethal exposure → tolerance
- Hormesis: Small stresses make organisms stronger
- Sensitization: Too much stress → vulnerability

Philosophy:
History matters. The past is written in the cells' state, not erased by washout.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
ADAPTIVE_RESISTANCE_RATE = 0.10  # 10% resistance per exposure (max 80%)
ADAPTIVE_RESISTANCE_MAX = 0.80  # Maximum resistance to any single stress
HARDENING_RATE = 0.03  # 3% general hardening per distinct stress type
HARDENING_MAX = 0.50  # Maximum general hardening (50%)
PRIMING_WINDOW_H = 48.0  # Priming lasts 48h
PRIMING_THRESHOLD = 0.15  # Stress >15% triggers priming
SENSITIZATION_THRESHOLD = 0.60  # Stress >60% triggers sensitization
SENSITIZATION_RATE = 0.05  # 5% sensitization per severe stress
SENSITIZATION_MAX = 0.30  # Maximum sensitization (30% more damage)
MEMORY_DECAY_TAU_H = 168.0  # Memory decays with 1 week (168h) time constant

# Stress types (categorized)
STRESS_TYPES = [
    'compound_toxicity',
    'osmotic',
    'oxidative',
    'mechanical',
    'thermal',
    'nutrient_deprivation',
    'pH',
]

# Cross-resistance: Some stresses confer resistance to others
CROSS_RESISTANCE = {
    'oxidative': ['compound_toxicity'],  # ROS stress helps with drug stress
    'thermal': ['compound_toxicity', 'oxidative'],  # Heat shock proteins help
    'osmotic': ['mechanical'],  # Osmotic stress strengthens membrane
}


@dataclass
class StressExposure:
    """Record of a single stress exposure."""
    stress_type: str
    magnitude: float  # 0-1 (severity)
    time_h: float  # When it occurred (simulated time)


@dataclass
class StressMemoryState(InjectionState):
    """
    Stress memory state per well.

    Tracks history of stress exposures and adaptive responses.
    """
    vessel_id: str

    # Stress history (list of exposures)
    stress_exposures: List[StressExposure] = field(default_factory=list)

    # Adaptive resistance per stress type (0-1)
    # Higher = more resistant to that specific stress
    adaptive_resistance: Dict[str, float] = field(default_factory=dict)

    # General hardening (0-0.5)
    # Multiple stress types → general toughness
    hardening_factor: float = 0.0

    # Priming state (stress response is activated)
    priming_active: bool = False
    priming_magnitude: float = 0.0  # How strong the priming is
    time_since_last_stress: float = 999.0  # Hours since last stress

    # Sensitization (over-stressing makes cells MORE sensitive)
    sensitization_factor: float = 0.0  # 0-0.3 (higher = more fragile)

    # Current stress load (total recent stress)
    current_stress_load: float = 0.0

    def __post_init__(self):
        """Initialize adaptive resistance dict."""
        if not self.adaptive_resistance:
            self.adaptive_resistance = {stype: 0.0 for stype in STRESS_TYPES}

    def record_stress(self, stress_type: str, magnitude: float, current_time: float) -> None:
        """
        Record a stress exposure.

        Args:
            stress_type: Type of stress (e.g., 'compound_toxicity')
            magnitude: Severity (0-1)
            current_time: Current simulated time (hours)
        """
        exposure = StressExposure(
            stress_type=stress_type,
            magnitude=magnitude,
            time_h=current_time
        )
        self.stress_exposures.append(exposure)

        # Update adaptive resistance for this stress type
        self._update_adaptive_resistance(stress_type, magnitude)

        # Update general hardening
        self._update_hardening()

        # Check for priming or sensitization
        if magnitude >= PRIMING_THRESHOLD:
            if magnitude < SENSITIZATION_THRESHOLD:
                # Moderate stress → priming
                self._activate_priming(magnitude)
            else:
                # Severe stress → sensitization (too much!)
                self._increase_sensitization()

        # Reset time since last stress
        self.time_since_last_stress = 0.0

    def _update_adaptive_resistance(self, stress_type: str, magnitude: float) -> None:
        """
        Update adaptive resistance to a specific stress type.

        Repeated exposure increases resistance (up to max).
        """
        if stress_type not in self.adaptive_resistance:
            self.adaptive_resistance[stress_type] = 0.0

        # Increase resistance proportional to exposure magnitude
        resistance_gain = ADAPTIVE_RESISTANCE_RATE * magnitude
        self.adaptive_resistance[stress_type] = min(
            self.adaptive_resistance[stress_type] + resistance_gain,
            ADAPTIVE_RESISTANCE_MAX
        )

        # Cross-resistance: This stress may help with others
        if stress_type in CROSS_RESISTANCE:
            for other_type in CROSS_RESISTANCE[stress_type]:
                if other_type in self.adaptive_resistance:
                    # Cross-resistance is weaker (50% effect)
                    cross_gain = resistance_gain * 0.5
                    self.adaptive_resistance[other_type] = min(
                        self.adaptive_resistance[other_type] + cross_gain,
                        ADAPTIVE_RESISTANCE_MAX * 0.6  # Max 60% from cross-resistance
                    )

    def _update_hardening(self) -> None:
        """
        Update general hardening from diverse stress exposures.

        Multiple distinct stress types → general toughness.
        """
        # Count unique stress types in recent history (last 168h)
        recent_types = set()
        for exp in self.stress_exposures[-20:]:  # Last 20 exposures
            recent_types.add(exp.stress_type)

        # Hardening increases with diversity
        target_hardening = len(recent_types) * HARDENING_RATE
        self.hardening_factor = min(target_hardening, HARDENING_MAX)

    def _activate_priming(self, magnitude: float) -> None:
        """
        Activate stress response priming.

        Recent moderate stress → faster/stronger response to next stress.
        """
        self.priming_active = True
        self.priming_magnitude = magnitude

    def _increase_sensitization(self) -> None:
        """
        Increase sensitization from severe stress.

        Too much stress → cells become MORE vulnerable.
        """
        self.sensitization_factor = min(
            self.sensitization_factor + SENSITIZATION_RATE,
            SENSITIZATION_MAX
        )

    def decay_memory(self, dt_hours: float) -> None:
        """
        Decay stress memory over time.

        Adaptive resistance and hardening fade over weeks.
        """
        self.time_since_last_stress += dt_hours

        # Decay factor (1 week time constant)
        decay_factor = np.exp(-dt_hours / MEMORY_DECAY_TAU_H)

        # Decay adaptive resistance
        for stress_type in self.adaptive_resistance:
            self.adaptive_resistance[stress_type] *= decay_factor

        # Decay hardening (slower)
        self.hardening_factor *= decay_factor ** 0.5  # Slower decay

        # Decay sensitization (faster - cells recover from damage)
        self.sensitization_factor *= decay_factor ** 2  # Faster decay

        # Deactivate priming if too much time passed
        if self.time_since_last_stress > PRIMING_WINDOW_H:
            self.priming_active = False
            self.priming_magnitude = 0.0

    def get_resistance_multiplier(self, stress_type: str) -> float:
        """
        Get damage reduction multiplier for a stress type.

        Returns:
            Multiplier (0-1): 0 = full resistance, 1 = no resistance
        """
        specific_resistance = self.adaptive_resistance.get(stress_type, 0.0)
        general_resistance = self.hardening_factor

        # Combined resistance (multiplicative)
        total_resistance = specific_resistance + general_resistance * (1 - specific_resistance)

        # Convert resistance to damage multiplier
        damage_multiplier = 1.0 - total_resistance

        # Apply sensitization (increases damage)
        damage_multiplier *= (1.0 + self.sensitization_factor)

        return float(np.clip(damage_multiplier, 0.1, 2.0))  # Min 10%, max 200%

    def get_priming_boost(self) -> float:
        """
        Get response speed boost from priming.

        Returns:
            Boost factor (1.0-2.0): How much faster stress response activates
        """
        if not self.priming_active:
            return 1.0

        # Priming accelerates response by up to 2×
        boost = 1.0 + self.priming_magnitude
        return float(np.clip(boost, 1.0, 2.0))

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of stress memory state."""
        return {
            'n_exposures': len(self.stress_exposures),
            'adaptive_resistance': dict(self.adaptive_resistance),
            'hardening_factor': self.hardening_factor,
            'priming_active': self.priming_active,
            'sensitization_factor': self.sensitization_factor,
            'time_since_last_stress_h': self.time_since_last_stress,
        }

    def check_invariants(self) -> None:
        """Check stress memory state is valid."""
        for stress_type, resistance in self.adaptive_resistance.items():
            if not (0.0 <= resistance <= 1.0):
                raise ValueError(f"Invalid resistance for {stress_type}: {resistance}")

        if not (0.0 <= self.hardening_factor <= 1.0):
            raise ValueError(f"Invalid hardening: {self.hardening_factor}")

        if not (0.0 <= self.sensitization_factor <= 1.0):
            raise ValueError(f"Invalid sensitization: {self.sensitization_factor}")


class StressMemoryInjection(Injection):
    """
    Injection G: Stress memory (Wells Remember Insults).

    Makes stress history matter. Agents must:
    - Recognize that past stress affects future responses
    - Understand adaptive resistance develops
    - Account for hardening and sensitization
    - Know that washout doesn't erase memory
    """

    def __init__(self, seed: int = 0):
        """
        Initialize stress memory injection.

        Args:
            seed: RNG seed (reserved for stochastic effects)
        """
        self.rng = np.random.default_rng(seed + 600)

    def create_state(self, vessel_id: str, context: InjectionContext) -> StressMemoryState:
        """
        Create stress memory state for a well.

        Initial state: No stress history (naive cells).
        """
        state = StressMemoryState(
            vessel_id=vessel_id,
            stress_exposures=[],
            adaptive_resistance={stype: 0.0 for stype in STRESS_TYPES},
            hardening_factor=0.0,
            priming_active=False,
            priming_magnitude=0.0,
            time_since_last_stress=999.0,
            sensitization_factor=0.0,
            current_stress_load=0.0,
        )
        return state

    def apply_time_step(self, state: StressMemoryState, dt: float, context: InjectionContext) -> None:
        """
        Decay stress memory over time.

        Adaptive resistance and hardening fade over weeks.
        """
        state.decay_memory(dt)

    def on_event(self, state: StressMemoryState, context: InjectionContext) -> None:
        """
        Record stress events and update adaptive state.

        Events:
        - 'compound_exposure': Drug toxicity stress
        - 'osmotic_stress': Volume/concentration changes
        - 'oxidative_stress': ROS, peroxide, etc.
        - 'mechanical_stress': Shear, pipetting
        - 'thermal_stress': Temperature excursions
        - 'nutrient_stress': Starvation, depletion
        """
        event_type = context.event_type
        params = context.event_params or {}
        current_time = context.simulated_time

        # Map events to stress types
        stress_mapping = {
            'compound_exposure': ('compound_toxicity', params.get('toxicity', 0.3)),
            'osmotic_stress': ('osmotic', params.get('magnitude', 0.2)),
            'oxidative_stress': ('oxidative', params.get('magnitude', 0.25)),
            'mechanical_stress': ('mechanical', params.get('magnitude', 0.15)),
            'thermal_stress': ('thermal', params.get('magnitude', 0.3)),
            'nutrient_stress': ('nutrient_deprivation', params.get('magnitude', 0.2)),
        }

        if event_type in stress_mapping:
            stress_type, magnitude = stress_mapping[event_type]
            state.record_stress(stress_type, magnitude, current_time)

        # Also detect implicit stress from other events
        elif event_type == 'dispense':
            # Compound dispense may cause toxicity stress
            compound_conc = params.get('compound_uM', 0.0)
            if compound_conc > 1.0:  # >1µM considered stressful
                toxicity = min(compound_conc / 100.0, 0.8)  # Scale to 0-0.8
                state.record_stress('compound_toxicity', toxicity, current_time)

        elif event_type in ['aspirate', 'washout']:
            # Liquid handling causes mechanical stress
            magnitude = 0.10 if event_type == 'aspirate' else 0.15
            state.record_stress('mechanical', magnitude, current_time)

    def get_biology_modifiers(self, state: StressMemoryState, context: InjectionContext) -> Dict[str, Any]:
        """
        Stress memory affects biology.

        Returns:
            Dict with:
            - stress_resistance_compound: Damage reduction for compound toxicity
            - stress_resistance_general: General hardening factor
            - stress_priming_boost: Response speed multiplier
            - stress_sensitization: Damage amplification
        """
        # Resistance to compound toxicity (most relevant)
        compound_resistance = state.get_resistance_multiplier('compound_toxicity')

        # General resistance from hardening
        general_resistance = 1.0 - state.hardening_factor

        # Priming boost (faster response)
        priming_boost = state.get_priming_boost()

        # Sensitization (more damage)
        sensitization = state.sensitization_factor

        return {
            'stress_resistance_compound': compound_resistance,
            'stress_resistance_general': general_resistance,
            'stress_priming_boost': priming_boost,
            'stress_sensitization': sensitization,
        }

    def get_measurement_modifiers(self, state: StressMemoryState, context: InjectionContext) -> Dict[str, Any]:
        """
        Stress memory affects measurements.

        Returns:
            Dict with:
            - baseline_stress_markers: Chronic stress markers elevated
        """
        # Cells with stress history show elevated baseline stress markers
        baseline_markers = state.hardening_factor * 0.5 + state.sensitization_factor * 0.3

        return {
            'baseline_stress_markers': baseline_markers,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: StressMemoryState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add stress memory metadata to observations.
        """
        memory_summary = state.get_memory_summary()

        observation['stress_memory_exposures'] = memory_summary['n_exposures']
        observation['stress_memory_hardening'] = memory_summary['hardening_factor']
        observation['stress_memory_priming'] = memory_summary['priming_active']
        observation['stress_memory_sensitization'] = memory_summary['sensitization_factor']

        # Add resistance levels for key stress types
        observation['stress_resistance_compound'] = state.adaptive_resistance.get('compound_toxicity', 0.0)
        observation['stress_resistance_oxidative'] = state.adaptive_resistance.get('oxidative', 0.0)

        # Warn if sensitization is high (cells are fragile)
        if state.sensitization_factor > 0.15:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'high_sensitization_{state.sensitization_factor:.2f}'
            )

        # Note if cells are primed
        if state.priming_active:
            observation['stress_primed'] = True

        return observation
