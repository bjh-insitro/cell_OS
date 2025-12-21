"""
Injection H: Lumpy Time (Commitment Points and Phase Transitions)

PROBLEM: Time is not smooth. Cells commit to trajectories. Transitions are discrete, not gradual.

State Variables:
- cell_state: Discrete state (proliferating, committed_apoptosis, committed_senescence, etc.)
- commitment_accumulator: Builds up to threshold before transition
- commitment_threshold: Point of no return (state-dependent)
- time_since_commitment: Hours since committed to current state
- latent_period_remaining: Time until observable change
- reversibility: Whether this state can be exited (0-1, 0=irreversible)

Pathologies Introduced:
- Commitment points: Once threshold crossed, no going back
- Latent periods: Stress accumulates silently, then sudden transition
- Phase transitions: Discrete jumps (healthy → apoptotic), not gradual
- Hysteresis: Hard to reverse (senescence, differentiation)
- State-dependent dynamics: Different rules in different states
- All-or-nothing: Once you start apoptosis, you finish

Exploits Blocked:
- "Stress is linear": Stress accumulates, then sudden phase transition
- "Everything is reversible": Apoptosis, senescence, differentiation are irreversible
- "No commitment": Cells can change their mind before commitment point
- "Smooth dynamics": Real biology has discrete state changes

Real-World Motivation:
- Apoptosis: Once caspase-3 activates → committed (no reversal)
- Senescence: p16/p21 upregulation → irreversible growth arrest
- Cell cycle checkpoints: G1/S, G2/M are discrete transitions
- Differentiation: Stem cell → committed progenitor (hard to reverse)
- Necroptosis: MLKL oligomerization → membrane rupture (point of no return)

Philosophy:
Cells are state machines, not differential equations. Transitions are jumps, not slopes.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Cell states (discrete)
class CellState(Enum):
    PROLIFERATING = "proliferating"              # Healthy, dividing
    QUIESCENT = "quiescent"                      # G0 arrest (reversible)
    STRESSED = "stressed"                        # Responding to stress
    COMMITTED_APOPTOSIS = "committed_apoptosis"  # Point of no return → death
    COMMITTED_SENESCENCE = "committed_senescence" # Irreversible growth arrest
    COMMITTED_NECROSIS = "committed_necrosis"    # Membrane rupture (instant)
    EXECUTING_APOPTOSIS = "executing_apoptosis"  # After latent period
    SENESCENT = "senescent"                      # Terminal state
    DEAD = "dead"                                # Terminal state


# Commitment thresholds (stress accumulator must exceed to transition)
COMMITMENT_THRESHOLDS = {
    CellState.PROLIFERATING: {
        CellState.STRESSED: 0.20,              # 20% stress → enter stressed state
        CellState.QUIESCENT: 0.15,             # 15% nutrient stress → quiescence
    },
    CellState.STRESSED: {
        CellState.COMMITTED_APOPTOSIS: 0.60,   # 60% stress → commit to apoptosis
        CellState.COMMITTED_SENESCENCE: 0.50,  # 50% chronic stress → senescence
        CellState.PROLIFERATING: -0.40,        # Recovery: stress drops below 40% of threshold
    },
    CellState.QUIESCENT: {
        CellState.PROLIFERATING: -0.30,        # Recovery: nutrient restored
        CellState.COMMITTED_SENESCENCE: 0.40,  # Chronic quiescence → senescence
    },
    CellState.COMMITTED_APOPTOSIS: {
        CellState.EXECUTING_APOPTOSIS: 1.00,   # Always transitions (latent period)
    },
    CellState.COMMITTED_SENESCENCE: {
        CellState.SENESCENT: 1.00,             # Always transitions
    },
    CellState.COMMITTED_NECROSIS: {
        CellState.DEAD: 1.00,                  # Instant (no latent period)
    },
    CellState.EXECUTING_APOPTOSIS: {
        CellState.DEAD: 1.00,                  # Execution completes
    },
}

# Latent periods (hours) - time between commitment and observable change
LATENT_PERIODS = {
    CellState.COMMITTED_APOPTOSIS: (6.0, 12.0),  # 6-12h before execution
    CellState.COMMITTED_SENESCENCE: (24.0, 48.0), # 1-2 days before terminal
    CellState.COMMITTED_NECROSIS: (0.0, 0.0),    # Instant
    CellState.EXECUTING_APOPTOSIS: (2.0, 4.0),   # 2-4h to complete
}

# Reversibility (0 = irreversible, 1 = fully reversible)
REVERSIBILITY = {
    CellState.PROLIFERATING: 1.0,
    CellState.QUIESCENT: 0.8,              # Mostly reversible
    CellState.STRESSED: 0.9,               # Very reversible
    CellState.COMMITTED_APOPTOSIS: 0.0,    # Irreversible
    CellState.COMMITTED_SENESCENCE: 0.0,   # Irreversible
    CellState.COMMITTED_NECROSIS: 0.0,     # Irreversible
    CellState.EXECUTING_APOPTOSIS: 0.0,    # Irreversible
    CellState.SENESCENT: 0.0,              # Terminal
    CellState.DEAD: 0.0,                   # Terminal
}


@dataclass
class LumpyTimeState(InjectionState):
    """
    Lumpy time state per cell population.

    Tracks discrete cell states and commitment dynamics.
    """
    vessel_id: str

    # Current cell state (discrete)
    cell_state: CellState = CellState.PROLIFERATING

    # Commitment accumulator (builds up until threshold)
    commitment_accumulator: float = 0.0

    # Time since committed to current state (hours)
    time_since_commitment: float = 0.0

    # Latent period (hours until observable change)
    latent_period_remaining: float = 0.0

    # State transition history
    state_history: list = field(default_factory=list)

    # Fraction of population in each state (for heterogeneity)
    state_distribution: Dict[CellState, float] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize state distribution."""
        if not self.state_distribution:
            # Start with 100% proliferating
            self.state_distribution = {state: 0.0 for state in CellState}
            self.state_distribution[CellState.PROLIFERATING] = 1.0

    def accumulate_stress(self, stress: float, stress_type: str = 'general') -> None:
        """
        Accumulate stress toward commitment threshold.

        Args:
            stress: Stress magnitude (0-1)
            stress_type: Type of stress (affects threshold)
        """
        # Different stress types have different accumulation rates
        accumulation_rate = 1.0
        if stress_type == 'acute':
            accumulation_rate = 2.0  # Acute stress accumulates faster
        elif stress_type == 'chronic':
            accumulation_rate = 0.5  # Chronic stress accumulates slower but persistent

        self.commitment_accumulator += stress * accumulation_rate

    def check_transition(self, rng: np.random.Generator) -> Optional[CellState]:
        """
        Check if cell should transition to new state.

        Returns:
            New state if transition occurs, None otherwise
        """
        current_state = self.cell_state
        possible_transitions = COMMITMENT_THRESHOLDS.get(current_state, {})

        for target_state, threshold in possible_transitions.items():
            # Negative threshold = recovery (accumulator must drop below)
            if threshold < 0:
                if self.commitment_accumulator < abs(threshold):
                    return target_state
            else:
                # Positive threshold = commitment (accumulator must exceed)
                if self.commitment_accumulator >= threshold:
                    return target_state

        return None

    def transition_to(self, new_state: CellState, rng: np.random.Generator) -> None:
        """
        Execute transition to new state.

        Args:
            new_state: Target state
            rng: Random number generator
        """
        # Record transition
        self.state_history.append((self.cell_state, new_state, self.time_since_commitment))

        # Reset commitment accumulator (transition occurred)
        self.commitment_accumulator = 0.0
        self.time_since_commitment = 0.0

        # Set latent period if applicable
        if new_state in LATENT_PERIODS:
            min_latent, max_latent = LATENT_PERIODS[new_state]
            self.latent_period_remaining = float(rng.uniform(min_latent, max_latent))
        else:
            self.latent_period_remaining = 0.0

        # Update state
        self.cell_state = new_state

    def advance_latent_period(self, dt_hours: float, rng: np.random.Generator) -> None:
        """
        Advance latent period timer.

        If latent period completes, auto-transition to next state.
        """
        if self.latent_period_remaining > 0:
            self.latent_period_remaining -= dt_hours

            # Latent period complete → auto-transition
            if self.latent_period_remaining <= 0:
                self.latent_period_remaining = 0.0

                # Auto-transitions after latent period
                auto_transitions = {
                    CellState.COMMITTED_APOPTOSIS: CellState.EXECUTING_APOPTOSIS,
                    CellState.COMMITTED_SENESCENCE: CellState.SENESCENT,
                    CellState.EXECUTING_APOPTOSIS: CellState.DEAD,
                }

                if self.cell_state in auto_transitions:
                    next_state = auto_transitions[self.cell_state]
                    self.transition_to(next_state, rng)

    def decay_accumulator(self, dt_hours: float, recovery_rate: float = 0.05) -> None:
        """
        Decay commitment accumulator over time (recovery).

        Only applies in reversible states.
        """
        reversibility = REVERSIBILITY.get(self.cell_state, 0.0)
        if reversibility > 0:
            decay = recovery_rate * dt_hours * reversibility
            self.commitment_accumulator = max(0.0, self.commitment_accumulator - decay)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current state."""
        return {
            'cell_state': self.cell_state.value,
            'commitment_accumulator': self.commitment_accumulator,
            'time_since_commitment': self.time_since_commitment,
            'latent_period_remaining': self.latent_period_remaining,
            'reversibility': REVERSIBILITY[self.cell_state],
            'is_committed': self.cell_state in [
                CellState.COMMITTED_APOPTOSIS,
                CellState.COMMITTED_SENESCENCE,
                CellState.COMMITTED_NECROSIS,
            ],
            'is_terminal': self.cell_state in [CellState.SENESCENT, CellState.DEAD],
        }

    def check_invariants(self) -> None:
        """Check state is valid."""
        if not (0.0 <= self.commitment_accumulator <= 2.0):
            raise ValueError(f"Invalid commitment accumulator: {self.commitment_accumulator}")

        if self.time_since_commitment < 0:
            raise ValueError(f"Invalid time since commitment: {self.time_since_commitment}")

        if self.latent_period_remaining < 0:
            raise ValueError(f"Invalid latent period: {self.latent_period_remaining}")


class LumpyTimeInjection(Injection):
    """
    Injection H: Lumpy Time (Commitment Points and Phase Transitions).

    Makes time discrete. Agents must:
    - Recognize that transitions are all-or-nothing
    - Understand commitment points (irreversible)
    - Account for latent periods (delay before observable change)
    - Know that stressed cells can recover (if not committed)
    - Realize that state matters more than rates
    """

    def __init__(self, seed: int = 0):
        """
        Initialize lumpy time injection.

        Args:
            seed: RNG seed for stochastic transitions
        """
        self.rng = np.random.default_rng(seed + 700)

    def create_state(self, vessel_id: str, context: InjectionContext) -> LumpyTimeState:
        """
        Create lumpy time state for a well.

        Initial state: All cells proliferating (healthy).
        """
        state = LumpyTimeState(
            vessel_id=vessel_id,
            cell_state=CellState.PROLIFERATING,
            commitment_accumulator=0.0,
            time_since_commitment=0.0,
            latent_period_remaining=0.0,
            state_history=[],
            state_distribution={s: 0.0 for s in CellState},
        )
        state.state_distribution[CellState.PROLIFERATING] = 1.0
        return state

    def apply_time_step(self, state: LumpyTimeState, dt: float, context: InjectionContext) -> None:
        """
        Advance discrete state machine.

        Check for transitions, advance latent periods, decay accumulators.
        """
        state.time_since_commitment += dt

        # Advance latent period (may trigger auto-transition)
        state.advance_latent_period(dt, self.rng)

        # Decay commitment accumulator (recovery in reversible states)
        state.decay_accumulator(dt)

        # Check for state transitions
        next_state = state.check_transition(self.rng)
        if next_state:
            state.transition_to(next_state, self.rng)

    def on_event(self, state: LumpyTimeState, context: InjectionContext) -> None:
        """
        Apply stress events that push cells toward commitment.

        Events:
        - 'acute_stress': High stress, rapid accumulation
        - 'chronic_stress': Low stress, slow accumulation
        - 'recovery': Reduce accumulator (if reversible)
        - 'severe_insult': Instant commitment (necrosis)
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'acute_stress':
            # Acute stress (drug, oxidative, etc.)
            magnitude = params.get('magnitude', 0.3)
            state.accumulate_stress(magnitude, stress_type='acute')

        elif event_type == 'chronic_stress':
            # Chronic stress (nutrient depletion, hypoxia)
            magnitude = params.get('magnitude', 0.2)
            state.accumulate_stress(magnitude, stress_type='chronic')

        elif event_type == 'recovery':
            # Recovery event (remove stress)
            recovery = params.get('magnitude', 0.1)
            state.commitment_accumulator = max(0.0, state.commitment_accumulator - recovery)

        elif event_type == 'severe_insult':
            # Instant commitment to necrosis (membrane rupture)
            state.transition_to(CellState.COMMITTED_NECROSIS, self.rng)

        # Implicit stress from other events
        elif event_type == 'dispense':
            compound_conc = params.get('compound_uM', 0.0)
            if compound_conc > 10.0:  # High concentration
                toxicity = min(compound_conc / 100.0, 0.5)
                state.accumulate_stress(toxicity, stress_type='acute')

        # Check for immediate transition after event
        next_state = state.check_transition(self.rng)
        if next_state:
            state.transition_to(next_state, self.rng)

    def get_biology_modifiers(self, state: LumpyTimeState, context: InjectionContext) -> Dict[str, Any]:
        """
        Cell state affects biology.

        Returns:
            Dict with:
            - growth_rate_multiplier: State-dependent growth
            - viability: Fraction of viable cells
            - metabolic_activity: State-dependent metabolism
        """
        cell_state = state.cell_state

        # State-dependent growth rates
        growth_multipliers = {
            CellState.PROLIFERATING: 1.0,
            CellState.QUIESCENT: 0.0,              # No growth
            CellState.STRESSED: 0.3,               # Slow growth
            CellState.COMMITTED_APOPTOSIS: 0.0,    # No growth
            CellState.COMMITTED_SENESCENCE: 0.0,   # No growth
            CellState.COMMITTED_NECROSIS: 0.0,
            CellState.EXECUTING_APOPTOSIS: 0.0,
            CellState.SENESCENT: 0.0,              # Terminal
            CellState.DEAD: 0.0,
        }

        # State-dependent viability
        viability = {
            CellState.PROLIFERATING: 1.0,
            CellState.QUIESCENT: 1.0,
            CellState.STRESSED: 0.95,
            CellState.COMMITTED_APOPTOSIS: 0.90,   # Still viable (latent period)
            CellState.COMMITTED_SENESCENCE: 0.95,
            CellState.COMMITTED_NECROSIS: 0.0,     # Instant death
            CellState.EXECUTING_APOPTOSIS: 0.5,    # Dying
            CellState.SENESCENT: 0.90,             # Alive but not dividing
            CellState.DEAD: 0.0,
        }

        # State-dependent metabolic activity
        metabolic_activity = {
            CellState.PROLIFERATING: 1.0,
            CellState.QUIESCENT: 0.3,              # Low metabolism
            CellState.STRESSED: 0.8,
            CellState.COMMITTED_APOPTOSIS: 0.6,    # Declining
            CellState.COMMITTED_SENESCENCE: 0.4,
            CellState.COMMITTED_NECROSIS: 0.0,
            CellState.EXECUTING_APOPTOSIS: 0.2,
            CellState.SENESCENT: 0.3,
            CellState.DEAD: 0.0,
        }

        return {
            'growth_rate_multiplier': growth_multipliers[cell_state],
            'viability': viability[cell_state],
            'metabolic_activity': metabolic_activity[cell_state],
        }

    def get_measurement_modifiers(self, state: LumpyTimeState, context: InjectionContext) -> Dict[str, Any]:
        """
        Cell state affects measurements.

        Returns:
            Dict with:
            - apoptotic_markers: Caspase activity, PS flip
            - senescence_markers: SA-β-gal, p16/p21
            - morphology_change: State-dependent appearance
        """
        cell_state = state.cell_state

        # Apoptotic markers
        apoptotic_markers = 0.0
        if cell_state == CellState.COMMITTED_APOPTOSIS:
            apoptotic_markers = 0.3  # Early markers (latent period)
        elif cell_state == CellState.EXECUTING_APOPTOSIS:
            apoptotic_markers = 1.0  # Full markers
        elif cell_state == CellState.DEAD:
            apoptotic_markers = 0.5  # Some markers fade

        # Senescence markers
        senescence_markers = 0.0
        if cell_state == CellState.COMMITTED_SENESCENCE:
            senescence_markers = 0.5  # Early markers
        elif cell_state == CellState.SENESCENT:
            senescence_markers = 1.0  # Full SASP

        # Morphology changes (0-1)
        morphology_change = {
            CellState.PROLIFERATING: 0.0,
            CellState.QUIESCENT: 0.1,
            CellState.STRESSED: 0.2,
            CellState.COMMITTED_APOPTOSIS: 0.3,
            CellState.COMMITTED_SENESCENCE: 0.4,
            CellState.COMMITTED_NECROSIS: 1.0,     # Instant rupture
            CellState.EXECUTING_APOPTOSIS: 0.8,
            CellState.SENESCENT: 0.6,              # Flattened, enlarged
            CellState.DEAD: 1.0,
        }

        return {
            'apoptotic_markers': apoptotic_markers,
            'senescence_markers': senescence_markers,
            'morphology_change': morphology_change[cell_state],
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: LumpyTimeState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add lumpy time metadata to observations.
        """
        state_summary = state.get_state_summary()

        observation['cell_state'] = state_summary['cell_state']
        observation['commitment_accumulator'] = state_summary['commitment_accumulator']
        observation['time_since_commitment_h'] = state_summary['time_since_commitment']
        observation['latent_period_remaining_h'] = state_summary['latent_period_remaining']
        observation['state_reversibility'] = state_summary['reversibility']
        observation['is_committed'] = state_summary['is_committed']

        # Warn if committed (irreversible)
        if state_summary['is_committed']:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f"cells_committed_{state_summary['cell_state']}"
            )

        # Note if in latent period
        if state_summary['latent_period_remaining'] > 0:
            observation['in_latent_period'] = True
            observation['latent_period_remaining_h'] = state_summary['latent_period_remaining']

        return observation
