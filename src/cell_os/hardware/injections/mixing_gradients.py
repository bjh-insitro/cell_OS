"""
Injection E: Media Mixing Gradients

PROBLEM: Compound doesn't mix instantly when added to well.

State Variables:
- gradient_magnitude: Current Z-axis concentration gradient (0-0.3)
- time_since_dispense: Time since last liquid addition
- mixing_tau: Characteristic mixing time (depends on well, compound)

Pathologies Introduced:
- Immediate post-dispense: ±20% concentration variation with depth
- Cells at bottom see different dose than cells at top
- Creates false subpopulation heterogeneity
- Gradient decays exponentially (tau ~5-10 minutes)
- Poor mixing conditions → slower decay

Exploits Blocked:
- "Instant mixing": Mixing takes minutes, not seconds
- "Homogeneous dose": Cells experience local concentration
- "Ignore spatial structure": Z-position matters early

Real-World Motivation:
- Dense cells at bottom, media at top
- DMSO compounds sink (denser than water)
- Hydrophobic compounds aggregate at surface
- Insufficient mixing after dispense (no shaking step)
- Cell-secreted factors create local gradients

Temporal Dynamics:
- t=0: Dispense → gradient = 20% (large)
- t=5min: gradient = 7% (decaying)
- t=10min: gradient = 3% (nearly mixed)
- t=30min: gradient < 1% (fully mixed)
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
GRADIENT_INITIAL_MAGNITUDE = 0.20  # ±20% variation immediately after dispense
MIXING_TAU_MIN = 5.0  # Fast mixing (5 minutes) - well-mixed conditions
MIXING_TAU_MAX = 10.0  # Slow mixing (10 minutes) - poor mixing conditions
GRADIENT_THRESHOLD = 0.01  # Below 1%, consider fully mixed


@dataclass
class MixingGradientState(InjectionState):
    """
    Media mixing state for a well.

    Tracks concentration gradient after liquid dispenses.
    """
    vessel_id: str

    # Current gradient magnitude (0-0.3)
    gradient_magnitude: float = 0.0

    # Time since last dispense (for decay)
    time_since_dispense: float = 999.0  # Large value = fully mixed

    # Mixing characteristics
    mixing_tau: float = 7.0  # Characteristic mixing time (minutes)

    # Z-position of cells (for gradient application)
    # Most cells settle to bottom (z=0), some float (z=1)
    # We'll sample per-cell or use population average
    cell_z_position: float = 0.3  # Average: cells mostly at bottom, some mid

    def decay_gradient(self, dt_hours: float) -> None:
        """
        Decay gradient exponentially with mixing time constant.

        Args:
            dt_hours: Time elapsed (hours)
        """
        self.time_since_dispense += dt_hours

        # Convert to minutes for mixing tau
        dt_minutes = dt_hours * 60.0

        # Exponential decay: G(t) = G0 * exp(-t/tau)
        decay_factor = np.exp(-dt_minutes / self.mixing_tau)
        self.gradient_magnitude *= decay_factor

        # Clamp to zero if nearly mixed
        if self.gradient_magnitude < GRADIENT_THRESHOLD:
            self.gradient_magnitude = 0.0

    def trigger_gradient(self, mixing_tau: float = 7.0) -> None:
        """
        Trigger new gradient after dispense operation.

        Args:
            mixing_tau: Mixing time constant (minutes)
        """
        self.gradient_magnitude = GRADIENT_INITIAL_MAGNITUDE
        self.time_since_dispense = 0.0
        self.mixing_tau = mixing_tau

    def get_local_concentration_multiplier(self, z_position: float) -> float:
        """
        Get local concentration multiplier at given Z-position.

        Gradient creates variation: bottom sees less, top sees more (or vice versa).

        Args:
            z_position: Normalized Z-position (0=bottom, 1=top)

        Returns:
            Concentration multiplier (0.8-1.2 at max gradient)
        """
        if self.gradient_magnitude < GRADIENT_THRESHOLD:
            return 1.0  # Fully mixed

        # Linear gradient model: C(z) = C0 * (1 + alpha * (z - 0.5))
        # where alpha = gradient_magnitude * 2
        #
        # z=0 (bottom): multiplier = 1 - gradient_magnitude
        # z=0.5 (middle): multiplier = 1.0
        # z=1 (top): multiplier = 1 + gradient_magnitude

        deviation = (z_position - 0.5) * self.gradient_magnitude * 2.0
        multiplier = 1.0 + deviation

        return float(np.clip(multiplier, 0.5, 1.5))

    def check_invariants(self) -> None:
        """Check gradient magnitude is in valid range."""
        if not (0.0 <= self.gradient_magnitude <= 0.5):
            raise ValueError(
                f"Gradient magnitude out of range: {self.gradient_magnitude:.3f}"
            )


class MixingGradientsInjection(Injection):
    """
    Injection E: Media mixing gradients.

    Makes mixing time matter. Agents must:
    - Wait for mixing after dispense (or accept gradient)
    - Recognize subpopulation heterogeneity may be artifact
    - Account for Z-position effects in measurements
    """

    def __init__(self, seed: int = 0):
        """
        Initialize mixing gradients injection.

        Args:
            seed: RNG seed for reproducibility
        """
        self.rng = np.random.default_rng(seed + 400)  # Offset from other RNGs

    def create_state(self, vessel_id: str, context: InjectionContext) -> MixingGradientState:
        """
        Create mixing state for a well.

        Initial state: no gradient (wells start empty or pre-mixed).
        """
        # Sample mixing tau (well-dependent: shape, surface properties)
        mixing_tau = float(self.rng.uniform(MIXING_TAU_MIN, MIXING_TAU_MAX))

        # Sample average cell Z-position (most settle to bottom)
        # Normal distribution: mean=0.3 (mostly bottom), std=0.15
        cell_z = float(np.clip(self.rng.normal(0.3, 0.15), 0.0, 1.0))

        state = MixingGradientState(
            vessel_id=vessel_id,
            gradient_magnitude=0.0,  # No gradient initially
            time_since_dispense=999.0,  # Fully mixed
            mixing_tau=mixing_tau,
            cell_z_position=cell_z
        )

        return state

    def apply_time_step(self, state: MixingGradientState, dt: float, context: InjectionContext) -> None:
        """
        Decay mixing gradient over time.

        Gradient decays exponentially with mixing tau.
        """
        if state.gradient_magnitude > 0.0:
            state.decay_gradient(dt)

    def on_event(self, state: MixingGradientState, context: InjectionContext) -> None:
        """
        Trigger mixing gradient when liquid is added.

        Events that trigger gradients:
        - 'dispense': Add compound (creates gradient)
        - 'feed': Media change (creates gradient)
        - 'washout': Media exchange (creates gradient)

        'aspirate' doesn't create gradient (only removes liquid).
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type in ['dispense', 'feed', 'washout']:
            # Trigger new gradient
            # Mixing tau depends on operation type
            if event_type == 'washout':
                # Washout has more turbulence → faster mixing
                mixing_tau = state.mixing_tau * 0.7
            else:
                mixing_tau = state.mixing_tau

            state.trigger_gradient(mixing_tau=mixing_tau)

    def get_biology_modifiers(self, state: MixingGradientState, context: InjectionContext) -> Dict[str, Any]:
        """
        Mixing gradient affects effective compound concentration.

        Cells experience local concentration, not bulk average.
        """
        # Use population average Z-position
        local_multiplier = state.get_local_concentration_multiplier(state.cell_z_position)

        return {
            'compound_concentration_multiplier_gradient': local_multiplier,
        }

    def get_measurement_modifiers(self, state: MixingGradientState, context: InjectionContext) -> Dict[str, Any]:
        """
        Mixing gradient creates apparent subpopulation heterogeneity.

        scRNA sees "two populations" when really it's just Z-position gradient.
        """
        # If gradient is large, increase apparent heterogeneity
        heterogeneity_inflation = 1.0 + state.gradient_magnitude * 2.0

        return {
            'subpopulation_heterogeneity_multiplier': heterogeneity_inflation,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: MixingGradientState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add mixing gradient metadata to observations.
        """
        observation['mixing_gradient_magnitude'] = state.gradient_magnitude
        observation['mixing_time_since_dispense_h'] = state.time_since_dispense
        observation['mixing_is_mixed'] = state.gradient_magnitude < GRADIENT_THRESHOLD

        # Warn if gradient is large (measurement timing issue)
        if state.gradient_magnitude > 0.1:  # >10% gradient
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'mixing_gradient_{state.gradient_magnitude:.2f}'
            )

        return observation
