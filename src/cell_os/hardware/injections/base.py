"""
Base interfaces for injection modules.

All realism injections follow this protocol to ensure consistent integration
with the biological simulator.
"""

from typing import Dict, Any, Optional, Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod
import numpy as np


@dataclass
class InjectionContext:
    """
    Context for injection hooks.

    Provides access to run context, time, and operation metadata without
    giving injections write access to core biology state.
    """
    simulated_time: float
    run_context: Any  # RunContext (avoiding circular import)
    event_type: Optional[str] = None  # 'aspirate', 'dispense', 'feed', 'washout', etc.
    event_params: Optional[Dict[str, Any]] = None

    # Spatial context
    well_position: Optional[str] = None  # 'A01', 'H12', etc.
    plate_id: Optional[str] = None

    # Operation context
    operator: Optional[str] = None
    instrument_id: Optional[str] = None


class InjectionState(ABC):
    """
    Base class for injection state.

    Each injection module defines its own state dataclass inheriting from this.
    State is attached to vessels and persists across operations.
    """

    @abstractmethod
    def check_invariants(self) -> None:
        """
        Check conservation laws and invariants.

        Raises exception if state violates invariants (similar to ConservationViolationError).
        This is called after every state update to fail fast.
        """
        pass


class Injection(ABC):
    """
    Base class for injection modules.

    Each module implements these hooks to integrate with the simulator:
    - apply_time_step: Update state due to passive time evolution
    - on_event: Update state due to operations (aspirate, dispense, etc.)
    - get_modifiers: Return modifiers to biology/measurement (concentrations, stress, noise)
    - pipeline_transform: Transform observations (distortions, missingness)
    """

    @abstractmethod
    def create_state(self, vessel_id: str, context: InjectionContext) -> InjectionState:
        """
        Create initial injection state for a new vessel.

        Called when vessel is seeded or first encountered.
        """
        pass

    @abstractmethod
    def apply_time_step(self, state: InjectionState, dt: float, context: InjectionContext) -> None:
        """
        Update injection state due to passive time evolution.

        Called during each _step_vessel() before biology updates.

        Args:
            state: Injection state to update (mutated in-place)
            dt: Time interval (hours)
            context: Injection context with time, run context, etc.
        """
        pass

    @abstractmethod
    def on_event(self, state: InjectionState, context: InjectionContext) -> None:
        """
        Update injection state due to operation event.

        Called for liquid handling events (aspirate, dispense, feed, washout, etc.)

        Args:
            state: Injection state to update (mutated in-place)
            context: Injection context with event_type and event_params
        """
        pass

    @abstractmethod
    def get_biology_modifiers(self, state: InjectionState, context: InjectionContext) -> Dict[str, Any]:
        """
        Return modifiers to biology state.

        Called during biology updates to get injection-driven effects.

        Returns:
            Dict with modifiers like:
            - 'compound_concentration_multiplier': float
            - 'nutrient_concentration_multiplier': float
            - 'osmolality_stress': float (0-1)
            - 'handling_stress': float (0-1)
            etc.
        """
        pass

    @abstractmethod
    def get_measurement_modifiers(self, state: InjectionState, context: InjectionContext) -> Dict[str, Any]:
        """
        Return modifiers to measurement/assay readouts.

        Called during assays to get injection-driven measurement effects.

        Returns:
            Dict with modifiers like:
            - 'intensity_multiplier': float
            - 'segmentation_quality': float (0-1)
            - 'noise_multiplier': float
            etc.
        """
        pass

    @abstractmethod
    def pipeline_transform(self, observation: Dict[str, Any], state: InjectionState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Transform observation through injection-specific pipeline effects.

        Called after base pipeline_transform to add injection-specific distortions,
        missingness, etc.

        Args:
            observation: Base observation dict (morphology, scalars, etc.)
            state: Injection state
            context: Injection context

        Returns:
            Modified observation dict (may add 'missing' flags, distort features, etc.)
        """
        pass


class InjectionManager:
    """
    Manages multiple injections and composes their effects.

    Attached to BiologicalVirtualMachine to orchestrate all injections.
    """

    def __init__(self):
        self.injections: list[Injection] = []
        self.vessel_states: Dict[str, Dict[str, InjectionState]] = {}  # vessel_id -> injection_name -> state

    def register_injection(self, name: str, injection: Injection) -> None:
        """Register an injection module."""
        self.injections.append((name, injection))

    def initialize_vessel(self, vessel_id: str, context: InjectionContext) -> None:
        """Initialize injection states for a new vessel."""
        self.vessel_states[vessel_id] = {}
        for name, injection in self.injections:
            self.vessel_states[vessel_id][name] = injection.create_state(vessel_id, context)

    def apply_time_step(self, vessel_id: str, dt: float, context: InjectionContext) -> None:
        """Apply time step to all injections for a vessel."""
        if vessel_id not in self.vessel_states:
            return

        for name, injection in self.injections:
            state = self.vessel_states[vessel_id][name]
            injection.apply_time_step(state, dt, context)
            state.check_invariants()

    def on_event(self, vessel_id: str, context: InjectionContext) -> None:
        """Handle operation event for all injections."""
        if vessel_id not in self.vessel_states:
            return

        for name, injection in self.injections:
            state = self.vessel_states[vessel_id][name]
            injection.on_event(state, context)
            state.check_invariants()

    def get_biology_modifiers(self, vessel_id: str, context: InjectionContext) -> Dict[str, Any]:
        """Compose biology modifiers from all injections."""
        if vessel_id not in self.vessel_states:
            return {}

        # Start with neutral modifiers
        modifiers = {
            'compound_concentration_multiplier': 1.0,
            'nutrient_concentration_multiplier': 1.0,
            'osmolality_stress': 0.0,
            'handling_stress': 0.0,
        }

        # Compose from all injections
        for name, injection in self.injections:
            state = self.vessel_states[vessel_id][name]
            inj_mods = injection.get_biology_modifiers(state, context)

            # Multiplicative factors multiply
            for key in ['compound_concentration_multiplier', 'nutrient_concentration_multiplier']:
                if key in inj_mods:
                    modifiers[key] *= inj_mods[key]

            # Additive stressors add
            for key in ['osmolality_stress', 'handling_stress']:
                if key in inj_mods:
                    modifiers[key] += inj_mods[key]

        return modifiers

    def get_measurement_modifiers(self, vessel_id: str, context: InjectionContext) -> Dict[str, Any]:
        """Compose measurement modifiers from all injections."""
        if vessel_id not in self.vessel_states:
            return {}

        # Start with neutral modifiers
        modifiers = {
            'intensity_multiplier': 1.0,
            'segmentation_quality': 1.0,
            'noise_multiplier': 1.0,
        }

        # Compose from all injections
        for name, injection in self.injections:
            state = self.vessel_states[vessel_id][name]
            inj_mods = injection.get_measurement_modifiers(state, context)

            # All are multiplicative
            for key in modifiers:
                if key in inj_mods:
                    modifiers[key] *= inj_mods[key]

        return modifiers

    def pipeline_transform(self, observation: Dict[str, Any], vessel_id: str,
                          context: InjectionContext) -> Dict[str, Any]:
        """Apply all injection pipeline transforms in sequence."""
        if vessel_id not in self.vessel_states:
            return observation

        result = observation.copy()
        for name, injection in self.injections:
            state = self.vessel_states[vessel_id][name]
            result = injection.pipeline_transform(result, state, context)

        return result

    def get_state(self, vessel_id: str, injection_name: str) -> Optional[InjectionState]:
        """Get injection state for a specific vessel and injection."""
        if vessel_id not in self.vessel_states:
            return None
        return self.vessel_states[vessel_id].get(injection_name)
