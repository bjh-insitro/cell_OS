"""
Injection K: Coalition Dynamics (Wells are Coalitions)

PROBLEM: Wells are not homogeneous. Subpopulations interact and dominate.

State Variables:
- subpopulations: Distinct phenotypes with different properties
- paracrine_signals: Secreted factors (cytokines, growth factors)
- quorum_state: Density-dependent behavior
- bystander_effects: Dying cells affect neighbors
- leader_fraction: Minority that controls majority

Pathologies Introduced:
- Minority dominance: 5% resistant cells protect 95% sensitive (paracrine)
- Bystander killing: Dying cells release signals that kill neighbors
- Quorum sensing: High density → different phenotype
- Conditioned media: Secreted factors accumulate, change environment
- Leader-follower: Small fraction dictates population behavior
- Averaging fallacy: Mean response hides subpopulation structure

Exploits Blocked:
- "All cells are identical": Heterogeneity matters
- "Average = typical": Bulk measurements miss structure
- "1% resistant = 1% survival": Paracrine protection
- "Response scales linearly": Quorum effects are nonlinear
- "Cell-autonomous": Cells communicate and coordinate

Real-World Motivation:
- Cancer: Drug-resistant minority protects bulk via paracrine
- Stem cells: 1% stem cells maintain 99% differentiated
- Immune evasion: Minority PD-L1+ cells protect neighbors
- Bystander effect: Radiation kills neighbors via ROS
- Quorum sensing: Bacteria change behavior at high density
- Conditioned media: Cell secretions accumulate over time

Philosophy:
The population is not a bag of independent cells. It's a coalition with
internal politics, signaling, and coordination. The minority can rule.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
PARACRINE_PROTECTION_RANGE = 0.50   # 50% protection from paracrine signals
BYSTANDER_KILLING_RANGE = 0.30      # 30% bystander effect from dying cells
QUORUM_THRESHOLD = 0.70             # 70% confluence triggers quorum
LEADER_INFLUENCE = 0.40             # Leaders influence 40% of behavior
SIGNAL_DIFFUSION_RATE = 0.20        # 20% signal diffusion per hour
SIGNAL_DECAY_RATE = 0.10            # 10% signal decay per hour
CONDITIONED_MEDIA_ACCUMULATION = 0.05  # 5% accumulation per hour


@dataclass
class Subpopulation:
    """A distinct cell subpopulation with unique properties."""
    name: str
    fraction: float                  # Fraction of population (0-1)
    drug_resistance: float = 0.0     # 0-1 (0=sensitive, 1=resistant)
    paracrine_secretion: float = 0.0 # 0-1 (secretes protective signals)
    is_leader: bool = False          # Controls population behavior
    proliferation_rate: float = 1.0  # Relative growth rate
    apoptosis_rate: float = 0.0      # Baseline death rate


@dataclass
class CoalitionDynamicsState(InjectionState):
    """
    Coalition dynamics state per well.

    Tracks subpopulations, signaling, and interactions.
    """
    vessel_id: str

    # Subpopulations
    subpopulations: List[Subpopulation] = field(default_factory=list)

    # Paracrine signals (secreted factors)
    paracrine_protection_level: float = 0.0   # 0-1 (protective signals)
    paracrine_toxicity_level: float = 0.0     # 0-1 (toxic signals)
    conditioned_media_strength: float = 0.0   # 0-1 (accumulated factors)

    # Bystander effects
    bystander_killing_active: bool = False
    bystander_signal_level: float = 0.0       # 0-1 (from dying cells)

    # Quorum sensing
    cell_density: float = 0.5                 # 0-1 (confluence)
    quorum_activated: bool = False
    quorum_phenotype: str = "proliferative"   # Changes at high density

    # Leader-follower dynamics
    leader_fraction: float = 0.0              # Fraction of leaders
    leader_influence_active: bool = False

    def __post_init__(self):
        """Initialize default subpopulations if empty."""
        if not self.subpopulations:
            # Start with homogeneous population
            self.subpopulations = [
                Subpopulation(
                    name="bulk",
                    fraction=1.0,
                    drug_resistance=0.0,
                    paracrine_secretion=0.0,
                    is_leader=False,
                    proliferation_rate=1.0,
                    apoptosis_rate=0.0,
                )
            ]

    def add_resistant_minority(self, fraction: float, resistance: float,
                              paracrine: float = 0.0) -> None:
        """
        Add a drug-resistant minority subpopulation.

        Args:
            fraction: Fraction of population (0-1)
            resistance: Drug resistance level (0-1)
            paracrine: Paracrine secretion level (0-1)
        """
        # Reduce bulk fraction
        bulk = self.subpopulations[0]
        bulk.fraction -= fraction

        # Add resistant minority
        resistant = Subpopulation(
            name="resistant",
            fraction=fraction,
            drug_resistance=resistance,
            paracrine_secretion=paracrine,
            is_leader=False,
            proliferation_rate=0.8,  # Slightly slower (fitness cost)
            apoptosis_rate=0.0,
        )
        self.subpopulations.append(resistant)

    def add_leader_minority(self, fraction: float) -> None:
        """
        Add a leader subpopulation that influences others.

        Args:
            fraction: Fraction of leaders (0-1)
        """
        # Reduce bulk fraction
        bulk = self.subpopulations[0]
        bulk.fraction -= fraction

        # Add leaders
        leader = Subpopulation(
            name="leader",
            fraction=fraction,
            drug_resistance=0.3,
            paracrine_secretion=0.5,  # Leaders secrete signals
            is_leader=True,
            proliferation_rate=0.6,   # Slow proliferation (quiescent-like)
            apoptosis_rate=0.0,
        )
        self.subpopulations.append(leader)

        self.leader_fraction = fraction
        if fraction > 0.01:  # >1% leaders
            self.leader_influence_active = True

    def update_paracrine_signals(self, dt_hours: float) -> None:
        """
        Update paracrine signal levels from secreting subpopulations.

        Args:
            dt_hours: Time step (hours)
        """
        # Production from subpopulations
        total_secretion = 0.0
        for subpop in self.subpopulations:
            contribution = subpop.fraction * subpop.paracrine_secretion
            total_secretion += contribution

        # Signal production
        production = total_secretion * SIGNAL_DIFFUSION_RATE * dt_hours

        # Signal decay
        decay = self.paracrine_protection_level * SIGNAL_DECAY_RATE * dt_hours

        # Update signal level
        self.paracrine_protection_level += production - decay
        self.paracrine_protection_level = float(np.clip(
            self.paracrine_protection_level, 0.0, 1.0
        ))

    def update_bystander_effects(self, death_fraction: float) -> None:
        """
        Update bystander killing from dying cells.

        Dying cells release signals that kill neighbors (bystander effect).

        Args:
            death_fraction: Fraction of cells dying (0-1)
        """
        if death_fraction > 0.05:  # >5% death triggers bystander
            self.bystander_killing_active = True
            self.bystander_signal_level = min(1.0, death_fraction * 2.0)
        else:
            self.bystander_killing_active = False
            self.bystander_signal_level *= 0.5  # Decay

    def check_quorum(self) -> None:
        """
        Check if quorum threshold crossed (density-dependent behavior).

        High density → phenotype switch (e.g., contact inhibition).
        """
        if self.cell_density >= QUORUM_THRESHOLD and not self.quorum_activated:
            # Activate quorum response
            self.quorum_activated = True
            self.quorum_phenotype = "contact_inhibited"

        elif self.cell_density < QUORUM_THRESHOLD * 0.8 and self.quorum_activated:
            # Deactivate quorum (hysteresis)
            self.quorum_activated = False
            self.quorum_phenotype = "proliferative"

    def get_protection_multiplier(self) -> float:
        """
        Get protection multiplier from paracrine signals.

        Minority resistant cells can protect majority via paracrine.

        Returns:
            Protection multiplier (0-1, 0=no protection, 1=full protection)
        """
        # Paracrine protection
        protection = self.paracrine_protection_level * PARACRINE_PROTECTION_RANGE

        # Leader influence (if active)
        if self.leader_influence_active:
            leader_protection = self.leader_fraction * LEADER_INFLUENCE
            protection = max(protection, leader_protection)

        return float(np.clip(protection, 0.0, 1.0))

    def get_bystander_killing_multiplier(self) -> float:
        """
        Get bystander killing multiplier.

        Dying cells kill neighbors via released signals.

        Returns:
            Bystander killing (0-1)
        """
        if self.bystander_killing_active:
            return self.bystander_signal_level * BYSTANDER_KILLING_RANGE
        return 0.0

    def get_subpopulation_structure(self) -> Dict[str, float]:
        """Get fraction of each subpopulation."""
        return {subpop.name: subpop.fraction for subpop in self.subpopulations}

    def check_invariants(self) -> None:
        """Check subpopulation fractions sum to ~1.0."""
        total_fraction = sum(subpop.fraction for subpop in self.subpopulations)
        if not (0.95 <= total_fraction <= 1.05):
            raise ValueError(f"Subpopulation fractions sum to {total_fraction}, expected ~1.0")


class CoalitionDynamicsInjection(Injection):
    """
    Injection K: Coalition Dynamics (Wells are Coalitions).

    Makes heterogeneity matter. Agents must:
    - Recognize that minority subpopulations can dominate
    - Understand paracrine protection (5% resistant protects 95%)
    - Account for bystander effects (dying cells kill neighbors)
    - Know that quorum sensing creates density-dependent behavior
    - Realize that average response hides subpopulation structure
    """

    def __init__(self, seed: int = 0):
        """
        Initialize coalition dynamics injection.

        Args:
            seed: RNG seed for stochastic effects
        """
        self.rng = np.random.default_rng(seed + 1000)

    def create_state(self, vessel_id: str, context: InjectionContext) -> CoalitionDynamicsState:
        """
        Create coalition dynamics state for a well.

        Initial state: Homogeneous population, no signaling.
        """
        state = CoalitionDynamicsState(
            vessel_id=vessel_id,
            subpopulations=[],  # Will be initialized in __post_init__
            paracrine_protection_level=0.0,
            paracrine_toxicity_level=0.0,
            conditioned_media_strength=0.0,
            bystander_killing_active=False,
            bystander_signal_level=0.0,
            cell_density=0.5,
            quorum_activated=False,
            quorum_phenotype="proliferative",
            leader_fraction=0.0,
            leader_influence_active=False,
        )
        return state

    def apply_time_step(self, state: CoalitionDynamicsState, dt: float, context: InjectionContext) -> None:
        """
        Update paracrine signals, check quorum, update density.

        Args:
            dt: Time step (hours)
        """
        # Update paracrine signals
        state.update_paracrine_signals(dt)

        # Check quorum threshold
        state.check_quorum()

        # Accumulate conditioned media
        state.conditioned_media_strength += CONDITIONED_MEDIA_ACCUMULATION * dt
        state.conditioned_media_strength = min(1.0, state.conditioned_media_strength)

        # Update cell density (growth increases, death decreases)
        # This is a simplified model; real density depends on biology
        net_growth = 0.05 * dt  # Assume some growth
        state.cell_density = float(np.clip(state.cell_density + net_growth, 0.0, 1.0))

    def on_event(self, state: CoalitionDynamicsState, context: InjectionContext) -> None:
        """
        Trigger coalition effects from events.

        Events:
        - 'emerge_resistant': Resistant minority emerges
        - 'emerge_leader': Leader subpopulation emerges
        - 'cell_death': Update bystander effects
        - 'seed_heterogeneous': Start with heterogeneous population
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'emerge_resistant':
            # Resistant minority emerges (e.g., after drug pressure)
            fraction = params.get('fraction', 0.05)
            resistance = params.get('resistance', 0.80)
            paracrine = params.get('paracrine', 0.50)
            state.add_resistant_minority(fraction, resistance, paracrine)

        elif event_type == 'emerge_leader':
            # Leader subpopulation emerges
            fraction = params.get('fraction', 0.02)
            state.add_leader_minority(fraction)

        elif event_type == 'cell_death':
            # Update bystander effects based on death
            death_fraction = params.get('fraction', 0.10)
            state.update_bystander_effects(death_fraction)

        elif event_type == 'seed_heterogeneous':
            # Start with pre-existing heterogeneity
            resistant_fraction = params.get('resistant_fraction', 0.05)
            leader_fraction = params.get('leader_fraction', 0.01)

            if resistant_fraction > 0:
                state.add_resistant_minority(resistant_fraction, 0.70, 0.40)
            if leader_fraction > 0:
                state.add_leader_minority(leader_fraction)

    def get_biology_modifiers(self, state: CoalitionDynamicsState, context: InjectionContext) -> Dict[str, Any]:
        """
        Coalition effects modify biology.

        Returns:
            Dict with:
            - paracrine_protection: Damage reduction from signals
            - bystander_killing: Additional death from neighbors
            - quorum_growth_modulation: Density-dependent growth
        """
        # Paracrine protection (minority protects majority)
        protection = state.get_protection_multiplier()

        # Bystander killing (dying cells kill neighbors)
        bystander = state.get_bystander_killing_multiplier()

        # Quorum effects (density-dependent)
        if state.quorum_activated:
            growth_modulation = 0.3  # 70% reduced growth (contact inhibition)
        else:
            growth_modulation = 1.0

        return {
            'paracrine_protection': protection,
            'bystander_killing': bystander,
            'quorum_growth_modulation': growth_modulation,
        }

    def get_measurement_modifiers(self, state: CoalitionDynamicsState, context: InjectionContext) -> Dict[str, Any]:
        """
        Subpopulation structure affects measurements.

        Returns:
            Dict with subpopulation metrics
        """
        # Calculate weighted averages (what bulk measurements see)
        weighted_resistance = sum(
            subpop.fraction * subpop.drug_resistance
            for subpop in state.subpopulations
        )

        # But minority can have outsized effects (not just average)
        effective_resistance = weighted_resistance + state.get_protection_multiplier()

        return {
            'weighted_resistance': weighted_resistance,
            'effective_resistance': min(1.0, effective_resistance),
            'paracrine_protection_present': state.paracrine_protection_level > 0.1,
            'subpopulation_count': len(state.subpopulations),
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: CoalitionDynamicsState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add coalition dynamics metadata to observations.
        """
        # Add subpopulation structure
        subpop_structure = state.get_subpopulation_structure()
        for name, fraction in subpop_structure.items():
            observation[f'subpop_fraction_{name}'] = fraction

        # Add signaling state
        observation['paracrine_protection'] = state.paracrine_protection_level
        observation['bystander_killing'] = state.bystander_signal_level
        observation['conditioned_media'] = state.conditioned_media_strength

        # Add quorum state
        observation['cell_density'] = state.cell_density
        observation['quorum_activated'] = state.quorum_activated
        observation['quorum_phenotype'] = state.quorum_phenotype

        # Add leader-follower state
        observation['leader_fraction'] = state.leader_fraction
        observation['leader_influence_active'] = state.leader_influence_active

        # Warn if minority dominance is active
        protection = state.get_protection_multiplier()
        if protection > 0.20:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'minority_dominance_protection_{protection:.2f}'
            )

        # Warn if bystander killing is active
        if state.bystander_killing_active:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'bystander_killing_{state.bystander_signal_level:.2f}'
            )

        # Warn if quorum is active
        if state.quorum_activated:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append('quorum_sensing_active')

        # Warn if heterogeneous (averaging fallacy)
        if len(state.subpopulations) > 1:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'heterogeneous_{len(state.subpopulations)}_subpopulations'
            )

        return observation
