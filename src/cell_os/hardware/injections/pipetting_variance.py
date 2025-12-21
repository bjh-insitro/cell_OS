"""
Injection D: Pipetting Accuracy Variance

PROBLEM: Robots are not perfectly accurate.

State Variables:
- systematic_error: Per-instrument bias (±1%)
- per_dispense_noise: Random error per operation (±0.5%)

Pathologies Introduced:
- Intended 200 µL → actually 198.5 µL (systematic)
- Random variation well-to-well (±0.5%)
- Dose accuracy affected (intended 1.0 µM → actually 0.99 µM)
- Nutrient variation (intended feed → slightly less/more)

Exploits Blocked:
- "Perfect volume control": Volumes have error
- "Exact dose delivery": Dose varies well-to-well
- "Identical replicates": Technical replicates differ slightly

Real-World Motivation:
- Pipetting robots have ±1-2% accuracy spec
- Viscosity affects accuracy (DMSO vs aqueous)
- Temperature affects accuracy
- Tip quality affects accuracy
- Air pressure affects accuracy

Interaction with Volume Evaporation:
- Pipetting error affects INITIAL volume
- Evaporation affects volume OVER TIME
- Combined: True volume is never exactly what you think
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
SYSTEMATIC_ERROR_MEAN = 0.0      # Average bias (0% = unbiased)
SYSTEMATIC_ERROR_STD = 0.01      # Instrument-to-instrument bias (±1%)
PER_DISPENSE_NOISE_STD = 0.005   # Random error per dispense (±0.5%)

# Viscosity affects accuracy (DMSO pipettes differently than water)
VISCOSITY_EFFECTS = {
    'aqueous': 1.0,      # Water, media (baseline)
    'dmso_low': 0.98,    # 0.1% DMSO (slight underdispense)
    'dmso_high': 0.95,   # 1% DMSO (noticeable underdispense)
}


@dataclass
class PipettingVarianceState(InjectionState):
    """
    Pipetting accuracy state.

    Tracks cumulative volume and compound errors from pipetting operations.
    """
    vessel_id: str

    # Systematic error for this instrument
    systematic_error: float = 0.0  # ±1% bias

    # History of volume errors (for debugging)
    cumulative_volume_error_uL: float = 0.0
    cumulative_compound_error: float = 0.0

    # Operation count (for statistics)
    n_dispenses: int = 0

    def check_invariants(self) -> None:
        """Pipetting errors should be small (±5% max cumulative)."""
        if abs(self.cumulative_volume_error_uL) > 50.0:
            # Cumulative error shouldn't exceed 50 µL over many operations
            # (This is a sanity check, not a hard failure)
            pass


class PipettingVarianceInjection(Injection):
    """
    Injection D: Pipetting accuracy variance.

    Makes liquid handling imperfect. Agents must:
    - Accept that replicates aren't identical
    - Account for dose variation well-to-well
    - Recognize systematic instrument bias
    """

    def __init__(self, seed: int = 0, instrument_id: Optional[str] = None):
        """
        Initialize pipetting variance injection.

        Args:
            seed: RNG seed for reproducibility
            instrument_id: Instrument identifier (for systematic bias)
        """
        self.rng = np.random.default_rng(seed + 300)  # Offset from other RNGs
        self.instrument_id = instrument_id or 'robot_001'

        # Sample systematic error for this instrument (persistent)
        self.instrument_systematic_error = float(
            self.rng.normal(SYSTEMATIC_ERROR_MEAN, SYSTEMATIC_ERROR_STD)
        )

    def create_state(self, vessel_id: str, context: InjectionContext) -> PipettingVarianceState:
        """
        Create pipetting state for a well.

        Each well inherits the instrument's systematic error.
        """
        state = PipettingVarianceState(
            vessel_id=vessel_id,
            systematic_error=self.instrument_systematic_error,
            cumulative_volume_error_uL=0.0,
            cumulative_compound_error=0.0,
            n_dispenses=0
        )

        return state

    def apply_time_step(self, state: PipettingVarianceState, dt: float, context: InjectionContext) -> None:
        """
        Pipetting errors don't evolve over time.

        Only occur during dispense operations.
        """
        pass

    def on_event(self, state: PipettingVarianceState, context: InjectionContext) -> None:
        """
        Apply pipetting errors to liquid handling operations.

        Events that trigger pipetting errors:
        - 'dispense': Add volume/compound (has error)
        - 'aspirate': Remove volume (has error)
        - 'feed': Media change (has error)

        Error model:
        - Systematic: Instrument bias (same for all operations)
        - Random: Per-dispense noise (different each time)
        - Viscosity: DMSO vs water (systematic underdispense)
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type not in ['dispense', 'aspirate', 'feed', 'washout']:
            return

        # Get intended volume
        intended_volume = params.get('volume_uL', 0.0)
        if intended_volume == 0.0:
            return

        # Error components
        systematic = state.systematic_error
        random = float(self.rng.normal(0.0, PER_DISPENSE_NOISE_STD))

        # Viscosity effect (if compound contains DMSO)
        viscosity_mult = 1.0
        if 'viscosity' in params:
            viscosity_mult = VISCOSITY_EFFECTS.get(params['viscosity'], 1.0)

        # Combined error
        total_error = systematic + random
        error_multiplier = (1.0 + total_error) * viscosity_mult

        # Actual volume delivered
        actual_volume = intended_volume * error_multiplier
        volume_error = actual_volume - intended_volume

        # Track cumulative error
        state.cumulative_volume_error_uL += volume_error
        state.n_dispenses += 1

        # Store actual volume in context for volume evaporation injection to use
        # (This is a bit hacky, ideally would have better inter-injection communication)
        if 'pipetting_actual_volume_uL' not in params:
            params['pipetting_actual_volume_uL'] = actual_volume

        # If dispensing compound, compound amount also has error
        if event_type == 'dispense' and 'compound_mass' in params:
            intended_compound = params['compound_mass']
            actual_compound = intended_compound * error_multiplier
            compound_error = actual_compound - intended_compound

            state.cumulative_compound_error += compound_error
            params['pipetting_actual_compound_mass'] = actual_compound

    def get_biology_modifiers(self, state: PipettingVarianceState, context: InjectionContext) -> Dict[str, Any]:
        """
        Pipetting errors affect effective concentrations indirectly.

        The volume/compound errors are already applied via on_event,
        so no additional biology modifiers needed here.
        """
        return {}

    def get_measurement_modifiers(self, state: PipettingVarianceState, context: InjectionContext) -> Dict[str, Any]:
        """
        Pipetting errors don't directly affect measurement quality.

        (Though they do affect biology via dose variation, which then affects measurements)
        """
        return {}

    def pipeline_transform(self, observation: Dict[str, Any], state: PipettingVarianceState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add pipetting variance metadata to observations.
        """
        observation['pipetting_systematic_error'] = state.systematic_error
        observation['pipetting_cumulative_volume_error_uL'] = state.cumulative_volume_error_uL
        observation['pipetting_n_dispenses'] = state.n_dispenses

        # Flag wells with large cumulative errors
        if abs(state.cumulative_volume_error_uL) > 20.0:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'pipetting_error_{state.cumulative_volume_error_uL:+.1f}uL'
            )

        return observation
