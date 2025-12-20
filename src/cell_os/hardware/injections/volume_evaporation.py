"""
Injection A: Volume + Evaporation Field

Spatial reality: plates are not well-independent.

State Variables:
- vol_uL: Liquid volume per well
- compound_mass, nutrient_mass, waste_mass: Solute amounts
- evap_field[x,y]: Position-dependent evaporation rate

Invariants:
- Non-negativity: volume and masses never negative
- Mass accounting: evaporation removes volume only, not solutes
- Concentration honesty: always derived from mass/volume

Exploits Blocked:
- "Ignore position effects": edge wells drift in dose and nutrients
- "Perfect concentration control": dose changes over time without intervention
- "Infinite micro-operations": dilution and volume chaos from over-intervention

New Pathologies:
- Edge wells systematically weird
- Late timepoints drift without ops
- Accidental dilution from over-washing
- Osmolality stress masquerades as mechanism signals
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Evaporation model constants
DEFAULT_EVAP_RATE_CENTER_uL_per_h = 0.2  # ~2.4% volume loss per 24h at center (200 uL well)
EVAP_EDGE_MULTIPLIER = 3.0  # Edge wells lose 3× more
MIN_VOLUME_uL = 10.0  # Below this, well is "dry" (failure mode)
OSMOLALITY_BASELINE = 300.0  # mOsm (typical cell culture media)
OSMOLALITY_STRESS_THRESHOLD = 450.0  # Above this, stress kicks in


class VolumeEvaporationError(Exception):
    """Raised when volume/mass invariants are violated."""
    pass


@dataclass
class VolumeEvaporationState(InjectionState):
    """
    Per-well state for volume and evaporation tracking.

    Manages liquid volume and solute masses to compute derived concentrations.
    """
    vessel_id: str

    # Volume
    vol_uL: float = 200.0  # Typical well volume (96-well plate)

    # Solute masses (arbitrary units, normalized to baseline concentrations)
    compound_mass: float = 0.0  # Compound amount
    nutrient_mass: float = 1.0  # Nutrient amount (1.0 = baseline)
    waste_mass: float = 0.0  # Metabolic waste accumulation

    # Baseline masses for concentration computation
    baseline_compound_mass: float = field(default=0.0, init=False, repr=False)

    # Spatial position (for evaporation field)
    well_position: Optional[str] = None  # 'A01', 'H12', etc.

    # Derived state (computed on demand)
    _evap_rate_cache: float = field(default=0.0, init=False, repr=False)

    def get_compound_concentration_multiplier(self) -> float:
        """
        Concentration multiplier due to volume and mass changes.

        Concentration = mass / volume.
        Multiplier = (mass / volume) / (baseline_mass / baseline_volume)
                   = (mass / baseline_mass) * (baseline_volume / volume)

        If volume drops by 20% → 1/0.8 = 1.25× concentration
        If mass drops by 50% → 0.5× concentration
        Combined: 0.5 * 1.25 = 0.625× concentration
        """
        baseline_vol = 200.0

        # If no baseline mass set, return volume-only effect
        if self.baseline_compound_mass == 0.0:
            return baseline_vol / max(MIN_VOLUME_uL, self.vol_uL)

        # Combined mass and volume effect
        mass_ratio = self.compound_mass / max(1e-9, self.baseline_compound_mass)
        vol_ratio = baseline_vol / max(MIN_VOLUME_uL, self.vol_uL)

        return mass_ratio * vol_ratio

    def get_nutrient_concentration_multiplier(self) -> float:
        """
        Nutrient concentration multiplier.

        Combines volume effect and nutrient depletion/addition.
        """
        baseline_vol = 200.0
        vol_multiplier = baseline_vol / max(MIN_VOLUME_uL, self.vol_uL)

        # Nutrient mass relative to baseline (1.0 = baseline)
        # If mass drops to 0.5 and volume to 0.8, concentration = 0.5/0.8 = 0.625
        mass_multiplier = self.nutrient_mass

        return vol_multiplier * mass_multiplier

    def get_osmolality_stress(self) -> float:
        """
        Osmolality stress (0-1) due to volume loss.

        Simplified model: total solute concentration increases with volume loss,
        creating hyperosmotic stress.
        """
        baseline_vol = 200.0
        vol_multiplier = baseline_vol / max(MIN_VOLUME_uL, self.vol_uL)

        # Total solute proxy: compound + nutrient + waste
        total_solute = self.compound_mass + self.nutrient_mass + self.waste_mass

        # Osmolality proxy (mOsm)
        osmolality = OSMOLALITY_BASELINE * vol_multiplier * (1.0 + total_solute)

        # Stress kicks in above threshold
        if osmolality < OSMOLALITY_STRESS_THRESHOLD:
            return 0.0

        # Sigmoid-like stress: 0 at threshold, 1.0 at 2× threshold
        excess = osmolality - OSMOLALITY_STRESS_THRESHOLD
        return float(np.clip(excess / OSMOLALITY_STRESS_THRESHOLD, 0.0, 1.0))

    def check_invariants(self) -> None:
        """Check volume and mass conservation invariants."""
        # Non-negativity
        if self.vol_uL < 0:
            raise VolumeEvaporationError(
                f"Negative volume: {self.vol_uL:.2f} uL (vessel_id={self.vessel_id})"
            )

        if self.compound_mass < 0:
            raise VolumeEvaporationError(
                f"Negative compound mass: {self.compound_mass:.6f} (vessel_id={self.vessel_id})"
            )

        if self.nutrient_mass < 0:
            raise VolumeEvaporationError(
                f"Negative nutrient mass: {self.nutrient_mass:.6f} (vessel_id={self.vessel_id})"
            )

        if self.waste_mass < 0:
            raise VolumeEvaporationError(
                f"Negative waste mass: {self.waste_mass:.6f} (vessel_id={self.vessel_id})"
            )

        # Dry well check (warn, don't fail - this is a valid failure mode)
        if self.vol_uL < MIN_VOLUME_uL:
            # TODO: Set a flag for "well failed due to desiccation"
            pass


@dataclass
class PlateEvaporationField:
    """
    Plate-level evaporation field.

    Position-dependent evaporation rates based on:
    - Edge distance (edge wells evaporate faster)
    - Incubator humidity (from RunContext)
    - Plate seal quality (optional)
    """
    plate_id: str
    evap_rates: Dict[str, float] = field(default_factory=dict)  # well_position -> rate_uL_per_h

    def get_rate(self, well_position: str, context: InjectionContext) -> float:
        """
        Get evaporation rate for a well.

        Factors:
        - Edge position (3× multiplier for edge wells)
        - Incubator humidity (from RunContext)
        """
        # Cache if already computed
        if well_position in self.evap_rates:
            return self.evap_rates[well_position]

        # Base rate
        base_rate = DEFAULT_EVAP_RATE_CENTER_uL_per_h

        # Edge multiplier
        is_edge = self._is_edge_well(well_position)
        edge_mult = EVAP_EDGE_MULTIPLIER if is_edge else 1.0

        # Humidity modifier from RunContext (if available)
        humidity_mult = 1.0
        if context.run_context is not None:
            # RunContext should have incubator_humidity latent (0.8-1.2 range)
            # Lower humidity → higher evaporation
            humidity = getattr(context.run_context, 'incubator_humidity', 1.0)
            humidity_mult = 2.0 - humidity  # humidity=0.8 → mult=1.2, humidity=1.2 → mult=0.8

        rate = base_rate * edge_mult * humidity_mult
        self.evap_rates[well_position] = rate
        return rate

    @staticmethod
    def _is_edge_well(well_position: str, plate_format: int = 96) -> bool:
        """Detect if well is on plate edge."""
        import re
        match = re.search(r'([A-P])(\d{1,2})$', well_position)
        if not match:
            return False

        row = match.group(1)
        col = int(match.group(2))

        if plate_format == 96:
            edge_rows = ['A', 'H']
            edge_cols = [1, 12]
            return row in edge_rows or col in edge_cols
        elif plate_format == 384:
            edge_rows = ['A', 'P']
            edge_cols = [1, 24]
            return row in edge_rows or col in edge_cols

        return False


class VolumeEvaporationInjection(Injection):
    """
    Injection A: Volume + Evaporation Field

    Makes spatial position, time, and operations matter for effective concentrations.
    """

    def __init__(self):
        # Plate-level evaporation fields (one per plate)
        self.plate_fields: Dict[str, PlateEvaporationField] = {}

    def create_state(self, vessel_id: str, context: InjectionContext) -> VolumeEvaporationState:
        """Create initial volume state for a vessel."""
        state = VolumeEvaporationState(
            vessel_id=vessel_id,
            vol_uL=200.0,  # Standard starting volume
            compound_mass=0.0,  # No compound initially
            nutrient_mass=1.0,  # Baseline nutrients
            waste_mass=0.0,  # No waste initially
            well_position=context.well_position
        )

        # Initialize plate field if needed
        if context.plate_id and context.plate_id not in self.plate_fields:
            self.plate_fields[context.plate_id] = PlateEvaporationField(plate_id=context.plate_id)

        return state

    def apply_time_step(self, state: VolumeEvaporationState, dt: float, context: InjectionContext) -> None:
        """
        Apply evaporation over time interval.

        Volume decreases, concentrations increase, osmolality stress builds.
        """
        if state.well_position is None or context.plate_id is None:
            return  # Can't compute evaporation without position

        # Get evaporation rate for this well
        plate_field = self.plate_fields.get(context.plate_id)
        if plate_field is None:
            return

        evap_rate = plate_field.get_rate(state.well_position, context)

        # Apply evaporation
        vol_loss = evap_rate * dt
        state.vol_uL = max(MIN_VOLUME_uL, state.vol_uL - vol_loss)

        # Masses unchanged (evaporation removes water, not solutes)
        # Concentrations automatically increase via derived properties

    def on_event(self, state: VolumeEvaporationState, context: InjectionContext) -> None:
        """
        Handle liquid handling events (aspirate, dispense, feed, washout).

        Updates both volume and solute masses according to operation.
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'aspirate':
            # Remove fraction of volume and proportional solutes
            fraction = params.get('fraction', 0.5)  # Default 50% removal

            state.vol_uL *= (1.0 - fraction)
            state.compound_mass *= (1.0 - fraction)
            state.nutrient_mass *= (1.0 - fraction)
            state.waste_mass *= (1.0 - fraction)

        elif event_type == 'dispense':
            # Add volume and solutes from source
            vol_added = params.get('volume_uL', 100.0)
            compound_added = params.get('compound_mass', 0.0)
            nutrient_added = params.get('nutrient_mass', 0.0)

            state.vol_uL += vol_added
            state.compound_mass += compound_added
            state.nutrient_mass += nutrient_added
            # Waste not added (fresh media has no waste)

        elif event_type == 'feed':
            # Media change: exchange volume, reset nutrients, dilute everything else
            exchange_fraction = params.get('exchange_fraction', 0.8)  # Typical 80% exchange

            # Remove old media (volume + solutes)
            state.vol_uL *= (1.0 - exchange_fraction)
            state.compound_mass *= (1.0 - exchange_fraction)
            state.nutrient_mass *= (1.0 - exchange_fraction)
            state.waste_mass *= (1.0 - exchange_fraction)

            # Add fresh media (volume + nutrients, no compound or waste)
            vol_added = 200.0 * exchange_fraction  # Return to baseline
            nutrient_added = 1.0 * exchange_fraction  # Baseline nutrients

            state.vol_uL += vol_added
            state.nutrient_mass += nutrient_added

        elif event_type == 'washout':
            # Similar to feed, but more aggressive exchange
            exchange_fraction = params.get('exchange_fraction', 0.95)  # 95% removal

            # Remove old media
            state.vol_uL *= (1.0 - exchange_fraction)
            state.compound_mass *= (1.0 - exchange_fraction)
            state.nutrient_mass *= (1.0 - exchange_fraction)
            state.waste_mass *= (1.0 - exchange_fraction)

            # Add fresh media
            vol_added = 200.0 * exchange_fraction
            nutrient_added = 1.0 * exchange_fraction

            state.vol_uL += vol_added
            state.nutrient_mass += nutrient_added

        # Check invariants after every operation
        state.check_invariants()

    def get_biology_modifiers(self, state: VolumeEvaporationState, context: InjectionContext) -> Dict[str, Any]:
        """
        Return concentration and stress modifiers for biology.

        Evaporation increases effective concentrations and creates osmolality stress.
        """
        return {
            'compound_concentration_multiplier': state.get_compound_concentration_multiplier(),
            'nutrient_concentration_multiplier': state.get_nutrient_concentration_multiplier(),
            'osmolality_stress': state.get_osmolality_stress(),
        }

    def get_measurement_modifiers(self, state: VolumeEvaporationState, context: InjectionContext) -> Dict[str, Any]:
        """
        Volume changes can affect measurement quality.

        Very low volume → poor imaging quality (cells detached, debris).
        """
        # Segmentation quality degrades below 50 uL
        if state.vol_uL < 50.0:
            quality_mult = state.vol_uL / 50.0
        else:
            quality_mult = 1.0

        return {
            'segmentation_quality': quality_mult,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: VolumeEvaporationState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        No pipeline transform for this injection (yet).

        Future: could add "well failed" flags for dry wells.
        """
        # Add volume metadata to observation
        observation['volume_uL'] = state.vol_uL
        observation['osmolality_stress'] = state.get_osmolality_stress()

        # Flag dry wells
        if state.vol_uL < MIN_VOLUME_uL:
            observation['well_failure'] = 'desiccation'
            observation['qc_flag'] = 'FAIL'

        return observation
