"""
Injection M: Cursed Plate (Rare Tail Events)

PROBLEM: Some days the universe just hates you. Rare, high-impact failures.

State Variables:
- curse_active: Is this plate cursed?
- curse_type: What kind of curse (contamination, instrument failure, etc.)
- curse_severity: How bad is it (0-1)
- curse_discovered_at: When did we notice?
- curse_duration: How long does it last?

Pathologies Introduced:
- Contamination: Bacteria/fungi ruin the plate
- Instrument failure: Robot miscalibrated, pipettes wrong volumes
- Plate manufacturing defect: Wells have cracks, uneven coating
- Incubator malfunction: Temperature excursion kills cells
- Reagent degradation: Old media, expired compounds
- Cross-contamination: Sample mixup, well-to-well bleed
- Cosmic ray: Single-event upset (extremely rare)

Exploits Blocked:
- "Everything works perfectly": Failures happen
- "Failures are gradual": Sometimes catastrophic
- "Failures are detectable": Some cursed plates look fine
- "Probability doesn't have tails": Rare events happen
- "One bad well": Sometimes the whole plate is cursed

Real-World Motivation:
- Contamination: Happens despite sterile technique
- Instrument drift: Calibration fails, systematic errors
- Reagent batch effects: One bad lot ruins everything
- Environmental factors: HVAC failure, power outage
- Human error: Sample swap, protocol mistake
- Unknown unknowns: Things you didn't even consider

Philosophy:
The tails are not thin. Rare events dominate outcomes. Most experiments
fail not because of biology, but because something went wrong.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
import numpy as np
from .base import InjectionState, Injection, InjectionContext


class CurseType(Enum):
    """Types of plate curses (rare failures)."""
    CONTAMINATION = "contamination"                  # Bacterial/fungal
    INSTRUMENT_FAILURE = "instrument_failure"        # Robot malfunction
    PLATE_DEFECT = "plate_defect"                   # Manufacturing defect
    INCUBATOR_FAILURE = "incubator_failure"         # Temperature excursion
    REAGENT_DEGRADATION = "reagent_degradation"     # Expired reagents
    CROSS_CONTAMINATION = "cross_contamination"     # Sample mixup
    COSMIC_RAY = "cosmic_ray"                       # Single-event upset (ultra-rare)
    UNKNOWN_UNKNOWN = "unknown_unknown"             # Something unexpected


# Curse probabilities (per experiment)
CURSE_PROBABILITIES = {
    CurseType.CONTAMINATION: 0.02,              # 2% chance
    CurseType.INSTRUMENT_FAILURE: 0.01,         # 1% chance
    CurseType.PLATE_DEFECT: 0.005,              # 0.5% chance
    CurseType.INCUBATOR_FAILURE: 0.001,         # 0.1% chance
    CurseType.REAGENT_DEGRADATION: 0.01,        # 1% chance
    CurseType.CROSS_CONTAMINATION: 0.005,       # 0.5% chance
    CurseType.COSMIC_RAY: 0.0001,               # 0.01% chance (ultra-rare)
    CurseType.UNKNOWN_UNKNOWN: 0.001,           # 0.1% chance
}

# Curse severity distributions (min, max)
CURSE_SEVERITY = {
    CurseType.CONTAMINATION: (0.5, 1.0),        # Moderate to total loss
    CurseType.INSTRUMENT_FAILURE: (0.3, 0.9),   # Partial to severe
    CurseType.PLATE_DEFECT: (0.2, 0.6),         # Mild to moderate
    CurseType.INCUBATOR_FAILURE: (0.7, 1.0),    # Severe to total loss
    CurseType.REAGENT_DEGRADATION: (0.2, 0.7),  # Mild to moderate
    CurseType.CROSS_CONTAMINATION: (0.4, 1.0),  # Moderate to total loss
    CurseType.COSMIC_RAY: (0.1, 0.3),           # Mild (single bit flip)
    CurseType.UNKNOWN_UNKNOWN: (0.3, 1.0),      # Variable
}


@dataclass
class CursedPlateState(InjectionState):
    """
    Cursed plate state per well (really per plate, but tracked per well).

    Rare, high-impact failures that ruin experiments.
    """
    vessel_id: str

    # Curse status
    curse_active: bool = False
    curse_type: Optional[CurseType] = None
    curse_severity: float = 0.0          # 0-1 (0=no effect, 1=total loss)
    curse_discovered: bool = False       # Has agent noticed?
    curse_discovery_time: float = 0.0    # When was it detected?

    # Curse-specific effects
    contamination_overgrowth: float = 0.0     # Bacteria/fungi growing
    instrument_systematic_error: float = 0.0  # Systematic pipetting error
    temperature_excursion_damage: float = 0.0 # Heat/cold damage
    reagent_degradation_factor: float = 1.0   # Reagent potency (1=normal, 0=dead)

    # Time tracking
    time_since_curse_onset: float = 0.0

    def apply_curse(self, curse_type: CurseType, severity: float) -> None:
        """
        Apply a curse to this plate.

        Args:
            curse_type: Type of curse
            severity: Severity (0-1)
        """
        self.curse_active = True
        self.curse_type = curse_type
        self.curse_severity = severity

        # Apply curse-specific effects
        if curse_type == CurseType.CONTAMINATION:
            self.contamination_overgrowth = severity * 0.8

        elif curse_type == CurseType.INSTRUMENT_FAILURE:
            # Systematic error in pipetting (all volumes wrong)
            self.instrument_systematic_error = (severity - 0.5) * 0.4  # ±20% max

        elif curse_type == CurseType.INCUBATOR_FAILURE:
            # Temperature excursion kills cells
            self.temperature_excursion_damage = severity * 0.9

        elif curse_type == CurseType.REAGENT_DEGRADATION:
            # Reagents don't work properly
            self.reagent_degradation_factor = 1.0 - severity * 0.7

    def progress_curse(self, dt_hours: float) -> None:
        """
        Curse gets worse over time (contamination grows, damage accumulates).

        Args:
            dt_hours: Time step (hours)
        """
        if not self.curse_active:
            return

        self.time_since_curse_onset += dt_hours

        # Some curses get worse over time
        if self.curse_type == CurseType.CONTAMINATION:
            # Contamination grows exponentially
            growth_rate = 0.30  # 30% per hour (doubles every ~2.5h)
            self.contamination_overgrowth = min(1.0,
                self.contamination_overgrowth * (1 + growth_rate * dt_hours))

        elif self.curse_type == CurseType.REAGENT_DEGRADATION:
            # Reagents degrade over time
            decay_rate = 0.05  # 5% per hour
            self.reagent_degradation_factor *= (1.0 - decay_rate * dt_hours)
            self.reagent_degradation_factor = max(0.0, self.reagent_degradation_factor)

    def get_viability_impact(self) -> float:
        """
        Get impact on cell viability from curse.

        Returns:
            Viability multiplier (0-1, 0=all dead)
        """
        if not self.curse_active:
            return 1.0

        # Different curses affect viability differently
        if self.curse_type == CurseType.CONTAMINATION:
            # Contamination competes with cells (toxic metabolites)
            return 1.0 - self.contamination_overgrowth * 0.8

        elif self.curse_type == CurseType.INCUBATOR_FAILURE:
            # Temperature excursion kills cells directly
            return 1.0 - self.temperature_excursion_damage

        elif self.curse_type == CurseType.REAGENT_DEGRADATION:
            # Bad reagents stress cells
            return 0.7 + 0.3 * self.reagent_degradation_factor

        else:
            # Other curses have indirect effects
            return 1.0 - self.curse_severity * 0.3

    def get_measurement_corruption(self) -> float:
        """
        Get measurement corruption from curse.

        Returns:
            Corruption magnitude (0-1)
        """
        if not self.curse_active:
            return 0.0

        # Curses corrupt measurements
        if self.curse_type == CurseType.INSTRUMENT_FAILURE:
            return abs(self.instrument_systematic_error)

        elif self.curse_type == CurseType.CROSS_CONTAMINATION:
            return self.curse_severity * 0.7

        elif self.curse_type == CurseType.COSMIC_RAY:
            return self.curse_severity * 0.5  # Random bit flips

        else:
            return self.curse_severity * 0.2

    def check_invariants(self) -> None:
        """Check curse state is valid."""
        if not (0.0 <= self.curse_severity <= 1.0):
            raise ValueError(f"Invalid curse severity: {self.curse_severity}")


class CursedPlateInjection(Injection):
    """
    Injection M: Cursed Plate (Rare Tail Events).

    Makes rare failures happen. Agents must:
    - Recognize that plates can be fundamentally ruined
    - Understand that probability has fat tails
    - Detect contamination and other failures
    - Know when to abort experiments (sunk cost fallacy)
    - Realize that most variance comes from rare events
    """

    def __init__(self, seed: int = 0, enable_curses: bool = True):
        """
        Initialize cursed plate injection.

        Args:
            seed: RNG seed for curse occurrence
            enable_curses: If False, disables all curses (for testing)
        """
        self.rng = np.random.default_rng(seed + 1200)
        self.enable_curses = enable_curses

    def create_state(self, vessel_id: str, context: InjectionContext) -> CursedPlateState:
        """
        Create cursed plate state for a well.

        Initial state: Not cursed (but could become cursed).
        """
        state = CursedPlateState(
            vessel_id=vessel_id,
            curse_active=False,
            curse_type=None,
            curse_severity=0.0,
            curse_discovered=False,
            curse_discovery_time=0.0,
            contamination_overgrowth=0.0,
            instrument_systematic_error=0.0,
            temperature_excursion_damage=0.0,
            reagent_degradation_factor=1.0,
            time_since_curse_onset=0.0,
        )

        # Small chance of starting with a curse (rare!)
        if self.enable_curses:
            self._check_for_curse_onset(state)

        return state

    def _check_for_curse_onset(self, state: CursedPlateState) -> None:
        """
        Check if a curse begins (rare event).

        Args:
            state: State to potentially curse
        """
        if state.curse_active:
            return  # Already cursed

        # Roll for each curse type
        for curse_type, probability in CURSE_PROBABILITIES.items():
            if self.rng.random() < probability:
                # Curse occurs!
                min_severity, max_severity = CURSE_SEVERITY[curse_type]
                severity = float(self.rng.uniform(min_severity, max_severity))
                state.apply_curse(curse_type, severity)
                break  # Only one curse at a time

    def apply_time_step(self, state: CursedPlateState, dt: float, context: InjectionContext) -> None:
        """
        Progress curse over time (contamination grows, etc.).

        Args:
            dt: Time step (hours)
        """
        # Check for new curse onset (rare)
        if self.enable_curses and not state.curse_active:
            # Very small chance each time step
            if self.rng.random() < 0.0001 * dt:  # ~0.01% per hour
                self._check_for_curse_onset(state)

        # Progress existing curse
        if state.curse_active:
            state.progress_curse(dt)

    def on_event(self, state: CursedPlateState, context: InjectionContext) -> None:
        """
        Some events can trigger or reveal curses.

        Events:
        - 'trigger_contamination': Force contamination (for testing)
        - 'trigger_instrument_failure': Force instrument failure
        - 'discover_curse': Agent notices something is wrong
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'trigger_contamination':
            # Force contamination (for testing)
            severity = params.get('severity', 0.70)
            state.apply_curse(CurseType.CONTAMINATION, severity)

        elif event_type == 'trigger_instrument_failure':
            # Force instrument failure
            severity = params.get('severity', 0.50)
            state.apply_curse(CurseType.INSTRUMENT_FAILURE, severity)

        elif event_type == 'discover_curse':
            # Agent notices something is wrong
            if state.curse_active and not state.curse_discovered:
                state.curse_discovered = True
                state.curse_discovery_time = context.simulated_time

    def get_biology_modifiers(self, state: CursedPlateState, context: InjectionContext) -> Dict[str, Any]:
        """
        Curses affect biology (contamination, temperature, reagents).

        Returns:
            Dict with curse impacts on biology
        """
        viability_impact = state.get_viability_impact()

        return {
            'curse_viability_multiplier': viability_impact,
            'reagent_potency': state.reagent_degradation_factor,
            'contamination_present': state.contamination_overgrowth > 0.1,
        }

    def get_measurement_modifiers(self, state: CursedPlateState, context: InjectionContext) -> Dict[str, Any]:
        """
        Curses corrupt measurements (instrument failure, cross-contamination).

        Returns:
            Dict with measurement corruption
        """
        corruption = state.get_measurement_corruption()

        return {
            'measurement_corruption': corruption,
            'systematic_error': state.instrument_systematic_error,
            'curse_active_hidden': state.curse_active,  # Agent doesn't know unless detected
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: CursedPlateState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add curse metadata to observations (if detectable).
        """
        # Some curses are immediately obvious
        if state.curse_active:
            # Contamination is visible (cloudiness, unusual morphology)
            if state.curse_type == CurseType.CONTAMINATION:
                if state.contamination_overgrowth > 0.3:
                    observation['visible_contamination'] = True
                    observation['contamination_level'] = state.contamination_overgrowth

            # Instrument failure shows up as systematic errors
            if state.curse_type == CurseType.INSTRUMENT_FAILURE:
                observation['systematic_pipetting_error'] = state.instrument_systematic_error

            # Temperature excursion shows up as mass death
            if state.curse_type == CurseType.INCUBATOR_FAILURE:
                observation['temperature_excursion_detected'] = True

            # Add general curse warning (if detectable)
            if state.curse_severity > 0.5 or state.curse_discovered:
                if 'qc_warnings' not in observation:
                    observation['qc_warnings'] = []

                if state.curse_type:
                    observation['qc_warnings'].append(
                        f'plate_curse_{state.curse_type.value}_severity_{state.curse_severity:.2f}'
                    )
                else:
                    observation['qc_warnings'].append('plate_curse_unknown')

                # Flag as potentially ruined
                if state.curse_severity > 0.7:
                    observation['qc_warnings'].append('experiment_may_be_ruined')
                    observation['abort_recommended'] = True

        # Add subtle indicators (even if curse not discovered)
        if state.curse_active and not state.curse_discovered:
            # Add noise/anomalies that hint something is wrong
            observation['data_quality_score'] = max(0.0, 1.0 - state.curse_severity * 0.5)

        return observation
