"""
InjectionManager: Authoritative source of truth for vessel exposure state.

Manages:
- Compound concentrations (uM) in each vessel
- Nutrient concentrations (mM) in each vessel
- Evaporation drift (volume shrink → concentration increase)

Design: Event-driven with strict schema validation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Literal, List, Callable
import logging

logger = logging.getLogger(__name__)

# Type aliases
EventType = Literal[
    "SEED_VESSEL",
    "TREAT_COMPOUND",
    "FEED_VESSEL",
    "WASHOUT_COMPOUND",
]

NutrientName = Literal["glucose", "glutamine"]


class InjectionSchemaError(ValueError):
    """Raised when event schema is invalid."""
    pass


@dataclass
class VesselExposureState:
    """
    Per-vessel exposure state tracking concentrations and drift.

    Authoritative for what is currently in the vessel.
    """
    vessel_id: str

    # Current concentrations
    compounds_uM: Dict[str, float] = field(default_factory=dict)
    nutrients_mM: Dict[NutrientName, float] = field(default_factory=dict)

    # Evaporation tracking
    volume_mult: float = 1.0  # 1.0 = baseline, <1.0 = concentrated

    # Timestamps
    last_event_time: float = 0.0
    last_step_time: float = 0.0

    # Debug forensics
    last_feed_time: Optional[float] = None
    last_washout_time: Optional[float] = None


class InjectionManager:
    """
    Authoritative source of truth for vessel exposure concentrations.

    Manages compound and nutrient concentrations with evaporation drift.
    All biology and assays must query this manager for current concentrations.
    """

    def __init__(
        self,
        *,
        is_edge_well_fn: Callable[[str], bool],
        base_evap_rate_per_h: float = 0.0005,   # 0.05% volume per hour interior
        edge_evap_rate_per_h: float = 0.0020,   # 0.2% volume per hour edge
        min_volume_mult: float = 0.70,          # cap at 30% lost volume
    ):
        """
        Initialize InjectionManager.

        Args:
            is_edge_well_fn: Callable(well_position) -> bool for edge detection
            base_evap_rate_per_h: Fractional volume loss per hour (interior wells)
            edge_evap_rate_per_h: Fractional volume loss per hour (edge wells)
            min_volume_mult: Minimum volume multiplier (caps concentration increase)
        """
        self._is_edge_well_fn = is_edge_well_fn
        self._base_evap_rate_per_h = float(base_evap_rate_per_h)
        self._edge_evap_rate_per_h = float(edge_evap_rate_per_h)
        self._min_volume_mult = float(min_volume_mult)

        self._vessels: Dict[str, VesselExposureState] = {}
        self._seq: int = 0
        self._event_log: List[Dict[str, Any]] = []

    # ========== Core getters ==========

    def has_vessel(self, vessel_id: str) -> bool:
        """Check if vessel is tracked."""
        return vessel_id in self._vessels

    def get_state(self, vessel_id: str) -> VesselExposureState:
        """Get exposure state for vessel."""
        if vessel_id not in self._vessels:
            raise KeyError(f"Vessel {vessel_id} not found in InjectionManager")
        return self._vessels[vessel_id]

    def get_compound_concentration_uM(self, vessel_id: str, compound: str) -> float:
        """Get current concentration of compound in vessel (uM)."""
        state = self.get_state(vessel_id)
        return state.compounds_uM.get(compound, 0.0)

    def get_all_compounds_uM(self, vessel_id: str) -> Dict[str, float]:
        """Get all current compound concentrations in vessel."""
        state = self.get_state(vessel_id)
        return state.compounds_uM.copy()

    def get_nutrient_conc_mM(self, vessel_id: str, nutrient: NutrientName) -> float:
        """Get current concentration of nutrient in vessel (mM)."""
        state = self.get_state(vessel_id)
        return state.nutrients_mM.get(nutrient, 0.0)

    def get_all_nutrients_mM(self, vessel_id: str) -> Dict[NutrientName, float]:
        """Get all current nutrient concentrations in vessel."""
        state = self.get_state(vessel_id)
        return state.nutrients_mM.copy()

    def get_volume_mult(self, vessel_id: str) -> float:
        """Get current volume multiplier (1.0 = baseline, <1.0 = concentrated)."""
        state = self.get_state(vessel_id)
        return state.volume_mult

    # ========== Event ingestion ==========

    def add_event(self, event: Dict[str, Any]) -> None:
        """
        Add and apply event with strict schema validation.

        Event is validated, logged, and applied immediately to vessel state.

        Args:
            event: Event dict with required keys: event_type, time_h, vessel_id, payload

        Raises:
            InjectionSchemaError: If event schema is invalid
        """
        # Validate schema
        self.validate_event(event)

        # Log event
        event_copy = event.copy()
        event_copy['_seq'] = self._seq
        self._event_log.append(event_copy)
        self._seq += 1

        # Apply event
        self._apply_event(event)

    def _apply_event(self, event: Dict[str, Any]) -> None:
        """Apply validated event to vessel state."""
        event_type = event['event_type']
        vessel_id = event['vessel_id']
        time_h = event['time_h']
        payload = event['payload']

        if event_type == 'SEED_VESSEL':
            # Create new vessel exposure state
            state = VesselExposureState(
                vessel_id=vessel_id,
                last_event_time=time_h,
                last_step_time=time_h,
            )

            # Initialize nutrients from payload
            initial_nutrients = payload['initial_nutrients_mM']
            state.nutrients_mM = {
                'glucose': float(initial_nutrients.get('glucose', 0.0)),
                'glutamine': float(initial_nutrients.get('glutamine', 0.0)),
            }

            self._vessels[vessel_id] = state
            logger.debug(f"InjectionManager: seeded {vessel_id} with nutrients={state.nutrients_mM}")

        elif event_type == 'TREAT_COMPOUND':
            # Set compound concentration (overwrites if exists)
            state = self.get_state(vessel_id)
            compound = payload['compound']
            dose_uM = float(payload['dose_uM'])

            state.compounds_uM[compound] = dose_uM
            state.last_event_time = time_h
            logger.debug(f"InjectionManager: treated {vessel_id} with {compound} @ {dose_uM} uM")

        elif event_type == 'FEED_VESSEL':
            # Update nutrient concentrations
            state = self.get_state(vessel_id)
            nutrients = payload['nutrients_mM']

            state.nutrients_mM['glucose'] = float(nutrients.get('glucose', 0.0))
            state.nutrients_mM['glutamine'] = float(nutrients.get('glutamine', 0.0))
            state.last_event_time = time_h
            state.last_feed_time = time_h
            logger.debug(f"InjectionManager: fed {vessel_id} with nutrients={state.nutrients_mM}")

        elif event_type == 'WASHOUT_COMPOUND':
            # Remove compound(s)
            state = self.get_state(vessel_id)
            compound = payload.get('compound')

            if compound is None:
                # Remove all compounds
                removed = list(state.compounds_uM.keys())
                state.compounds_uM.clear()
                logger.debug(f"InjectionManager: washed out all compounds from {vessel_id}: {removed}")
            else:
                # Remove specific compound
                if compound in state.compounds_uM:
                    del state.compounds_uM[compound]
                    logger.debug(f"InjectionManager: washed out {compound} from {vessel_id}")

            state.last_event_time = time_h
            state.last_washout_time = time_h

    # ========== Time evolution ==========

    def step(self, *, dt_h: float, now_h: float) -> None:
        """
        Apply evaporation drift over time interval to all vessels.

        Updates volume_mult which concentrates all compounds and nutrients.

        Args:
            dt_h: Time interval (hours)
            now_h: Current simulated time (hours)
        """
        for vessel_id, state in self._vessels.items():
            # Determine evaporation rate based on well position
            # Extract well position from vessel_id (assumes format like "Plate1_A01")
            well_position = vessel_id.split('_')[-1] if '_' in vessel_id else vessel_id
            is_edge = self._is_edge_well_fn(well_position)

            evap_rate = self._edge_evap_rate_per_h if is_edge else self._base_evap_rate_per_h

            # Update volume multiplier (capped at minimum)
            prev_volume_mult = state.volume_mult
            state.volume_mult = max(
                self._min_volume_mult,
                state.volume_mult * (1.0 - evap_rate * dt_h)
            )

            # Concentrate all compounds and nutrients
            # concentration_new = concentration_old * (volume_old / volume_new)
            #                    = concentration_old * (prev_mult / new_mult)
            if state.volume_mult > 0 and prev_volume_mult > 0:
                conc_mult = prev_volume_mult / state.volume_mult

                # Concentrate compounds
                for compound in state.compounds_uM:
                    state.compounds_uM[compound] *= conc_mult

                # Concentrate nutrients
                for nutrient in state.nutrients_mM:
                    state.nutrients_mM[nutrient] *= conc_mult

            state.last_step_time = now_h

            if is_edge and conc_mult > 1.01:  # Log significant concentration
                logger.debug(
                    f"InjectionManager: {vessel_id} (edge) concentrated {conc_mult:.3f}× "
                    f"(volume_mult={state.volume_mult:.3f})"
                )

    # ========== Internal sync hook ==========

    def set_nutrients_mM(
        self,
        vessel_id: str,
        nutrients_mM: Dict[NutrientName, float],
        *,
        now_h: float
    ) -> None:
        """
        Internal sync hook for nutrient depletion.

        Not an event - used by simulator's _update_nutrient_depletion to sync
        depleted nutrients back into authoritative state.

        Args:
            vessel_id: Vessel identifier
            nutrients_mM: Updated nutrient concentrations
            now_h: Current simulated time
        """
        state = self.get_state(vessel_id)
        state.nutrients_mM.update(nutrients_mM)
        logger.debug(f"InjectionManager: synced nutrients for {vessel_id}: {nutrients_mM}")

    # ========== Validation ==========

    def validate_event(self, event: Dict[str, Any]) -> None:
        """
        Validate event schema strictly.

        Raises:
            InjectionSchemaError: If schema is invalid
        """
        # Required top-level keys
        required = ['event_type', 'time_h', 'vessel_id', 'payload']
        for key in required:
            if key not in event:
                raise InjectionSchemaError(f"Missing required key: {key}")

        event_type = event['event_type']
        payload = event['payload']

        # Validate payload shape per event type
        if event_type == 'SEED_VESSEL':
            if 'initial_nutrients_mM' not in payload:
                raise InjectionSchemaError("SEED_VESSEL requires payload.initial_nutrients_mM")
            nutrients = payload['initial_nutrients_mM']
            if not isinstance(nutrients, dict):
                raise InjectionSchemaError("initial_nutrients_mM must be dict")

        elif event_type == 'TREAT_COMPOUND':
            if 'compound' not in payload or 'dose_uM' not in payload:
                raise InjectionSchemaError("TREAT_COMPOUND requires payload.compound and payload.dose_uM")
            # Reject if payload has nutrient fields (common mistake)
            if 'nutrients_mM' in payload or 'initial_nutrients_mM' in payload:
                raise InjectionSchemaError("TREAT_COMPOUND payload cannot contain nutrient fields")

        elif event_type == 'FEED_VESSEL':
            if 'nutrients_mM' not in payload:
                raise InjectionSchemaError("FEED_VESSEL requires payload.nutrients_mM")
            # Reject if payload has compound fields (common mistake)
            if 'compound' in payload or 'dose_uM' in payload:
                raise InjectionSchemaError("FEED_VESSEL payload cannot contain compound fields")

        elif event_type == 'WASHOUT_COMPOUND':
            if 'compound' not in payload:
                raise InjectionSchemaError("WASHOUT_COMPOUND requires payload.compound (can be None)")

        else:
            raise InjectionSchemaError(f"Unknown event_type: {event_type}")

    # ========== Forensics ==========

    def get_event_log(self) -> List[Dict[str, Any]]:
        """Get full event log for debugging."""
        return self._event_log.copy()
