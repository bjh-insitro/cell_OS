"""
Base class for stress mechanism simulators.

Stress mechanisms update latent stress states and propose death hazards
based on compound exposure, nutrient levels, and confluence.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..biological_virtual import VesselState, BiologicalVirtualMachine


class StressMechanism(ABC):
    """
    Base class for stress mechanism simulators.

    Contract:
    - Mechanisms update VesselState in place (latent stress states)
    - Mechanisms propose death hazards via vm._propose_hazard()
    - Mechanisms should be stateless (all state in VesselState)
    """

    def __init__(self, vm: "BiologicalVirtualMachine"):
        """
        Initialize stress mechanism.

        Args:
            vm: BiologicalVirtualMachine instance (provides _propose_hazard, run_context)
        """
        self.vm = vm

    @abstractmethod
    def update(self, vessel: "VesselState", hours: float):
        """
        Update stress state and propose death hazards.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        pass

    def _propose_hazard(self, vessel: "VesselState", hazard_per_h: float, death_field: str):
        """
        Delegate to VM's _propose_hazard method.

        Args:
            vessel: Vessel state
            hazard_per_h: Hazard rate (deaths per hour, >= 0)
            death_field: Which cumulative death field to credit
        """
        self.vm._propose_hazard(vessel, hazard_per_h, death_field)
