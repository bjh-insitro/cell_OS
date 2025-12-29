"""
Mitotic catastrophe mechanism simulator.

Handles mitotic failure in dividing cells exposed to microtubule-disrupting compounds.
"""

import numpy as np
from typing import TYPE_CHECKING

from .base import StressMechanism
from ..constants import DEFAULT_DOUBLING_TIME_H
from ...sim import biology_core

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class MitoticCatastropheMechanism(StressMechanism):
    """
    Mitotic catastrophe mechanism simulator.

    Only affects dividing cells exposed to microtubule-axis stress.
    Neurons (iPSC_NGN2) die from transport collapse, not mitotic failure.

    Hazard formulation:
    - Cells attempt mitosis at rate = ln(2) / doubling_time (per hour)
    - Each attempt fails with probability p_fail = dose / (dose + IC50)
    - Instantaneous mitotic death rate = mitosis_rate * p_fail

    Note: This mechanism is called per-compound (not per-step like other mechanisms),
    so update() is not used. Use apply() instead.
    """

    def update(self, vessel: "VesselState", hours: float):
        """Not used for mitotic catastrophe (called per-compound instead)."""
        pass

    def apply(self, vessel: "VesselState", stress_axis: str, dose_uM: float, ic50_uM: float, hours: float):
        """
        Apply mitotic catastrophe hazard for a specific compound.

        This is called during compound attrition, not during general stress updates.

        Args:
            vessel: Vessel state
            stress_axis: Compound stress axis
            dose_uM: Compound dose (µM)
            ic50_uM: Compound IC50 (µM)
            hours: Time interval (hours)
        """
        # Zero time = zero physics
        if hours <= 0:
            return

        # Only affects microtubule-disrupting compounds
        if stress_axis != "microtubule":
            return

        # Skip non-dividing cells (neurons, post-mitotic cells)
        prolif_index = biology_core.PROLIF_INDEX.get(vessel.cell_line, 1.0)
        if prolif_index < 0.3:  # Threshold: below 0.3 = post-mitotic
            return

        viable_cells = vessel.cell_count * vessel.viability
        if viable_cells <= 0:
            return

        # Mitosis attempt rate (per hour)
        dt = max(1e-6, float(getattr(vessel, "doubling_time_h", DEFAULT_DOUBLING_TIME_H)))
        mitosis_rate = float(np.log(2.0) / dt)

        # Failure probability per mitotic attempt [0-1]
        ic50 = max(1e-9, float(ic50_uM))
        p_fail = float(dose_uM / (dose_uM + ic50))

        # Instantaneous mitotic death hazard (deaths per hour)
        hazard_mitotic = mitosis_rate * p_fail

        # Phase 1: Apply intrinsic biology hazard scale multiplier (persistent per-vessel)
        if vessel.bio_random_effects:
            hazard_mitotic *= vessel.bio_random_effects['hazard_scale_mult']

        self._propose_hazard(vessel, hazard_mitotic, "death_mitotic_catastrophe")
