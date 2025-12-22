"""
Base classes for assay simulators.

Assays are pure measurement functions that read vessel state and return
synthetic data with realistic noise characteristics. They must not mutate
vessel state (observer independence).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


class AssaySimulator(ABC):
    """
    Base class for assay simulators.

    Contract:
    - Assays are READ-ONLY: They observe vessel state but never mutate it
    - Assays use rng_assay for all noise (observer independence)
    - Assays return Dict[str, Any] with "status" and "action" keys
    - Assays should check vessel state before measurement
    """

    def __init__(self, vm):
        """
        Initialize assay simulator.

        Args:
            vm: BiologicalVirtualMachine instance (provides RNGs, params, run context)
        """
        self.vm = vm

    @abstractmethod
    def measure(self, vessel: "VesselState", **kwargs) -> Dict[str, Any]:
        """
        Perform measurement on vessel.

        Args:
            vessel: Vessel state to measure
            **kwargs: Additional parameters (plate_id, well_position, etc.)

        Returns:
            Dict with measurement results and metadata
        """
        pass

    def _assert_measurement_purity(self, vessel: "VesselState", state_before: tuple):
        """
        Assert that measurement did not perturb vessel state.

        Args:
            vessel: Vessel state after measurement
            state_before: Tuple of (cell_count, viability, confluence) before measurement

        Raises:
            AssertionError if state changed
        """
        state_after = (vessel.cell_count, vessel.viability, vessel.confluence)
        assert state_before == state_after, (
            f"MEASUREMENT PURITY VIOLATION: {self.__class__.__name__} mutated vessel state!\n"
            f"  Before: count={state_before[0]:.2f}, via={state_before[1]:.6f}, conf={state_before[2]:.4f}\n"
            f"  After:  count={state_after[0]:.2f}, via={state_after[1]:.6f}, conf={state_after[2]:.4f}\n"
            f"Measurement functions must be read-only. Observer independence violated."
        )
