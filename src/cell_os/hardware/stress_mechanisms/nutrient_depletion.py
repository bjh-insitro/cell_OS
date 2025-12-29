"""
Nutrient depletion mechanism simulator.

Handles nutrient consumption and starvation death hazards.
"""

import numpy as np
from typing import TYPE_CHECKING

from .base import StressMechanism
from ..constants import (
    DEFAULT_MEDIA_GLUCOSE_mM,
    DEFAULT_MEDIA_GLUTAMINE_mM,
    GLUCOSE_STRESS_THRESHOLD_mM,
    GLUTAMINE_STRESS_THRESHOLD_mM,
    MAX_STARVATION_RATE_PER_H,
)

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class NutrientDepletionMechanism(StressMechanism):
    """
    Nutrient depletion mechanism simulator.

    Handles:
    - Glucose and glutamine consumption (driven by viable cell load)
    - Starvation death hazard (when nutrients drop below thresholds)

    Uses interval-average viable cells (trapezoid rule) to avoid dt-sensitivity.
    """

    def update(self, vessel: "VesselState", hours: float):
        """
        Update nutrient levels and propose starvation death hazard.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        # Zero time → zero consumption
        if hours <= 0:
            return

        # Read authoritative nutrients from InjectionManager if present
        if self.vm.injection_mgr is not None and self.vm.injection_mgr.has_vessel(vessel.vessel_id):
            vessel.media_glucose_mM = self.vm.injection_mgr.get_nutrient_conc_mM(vessel.vessel_id, "glucose")
            vessel.media_glutamine_mM = self.vm.injection_mgr.get_nutrient_conc_mM(vessel.vessel_id, "glutamine")

        # Media buffer (scales with vessel capacity)
        media_buffer = max(1.0, float(vessel.vessel_capacity) / 1e7)

        # Interval-average viable cells using trapezoid rule
        # CRITICAL FIX: Nutrient depletion runs AFTER growth, so vessel.cell_count
        # is the END-OF-INTERVAL population (t1), not start (t0).
        # Back-calculate t0 from t1 to get the correct interval average.
        viable_cells_t1 = float(vessel.cell_count * vessel.viability)

        # Get growth rate to back-calculate start-of-interval population
        cell_line_params = self.vm.cell_line_params.get(vessel.cell_line, self.vm.defaults)
        baseline_doubling_h = cell_line_params.get("doubling_time_h", 24.0)
        growth_rate = np.log(2.0) / baseline_doubling_h

        # Back-calculate start-of-interval from end-of-interval
        viable_cells_t0 = viable_cells_t1 / np.exp(growth_rate * hours)

        # Interval-average (trapezoid rule)
        viable_cells_mean = 0.5 * (viable_cells_t0 + viable_cells_t1)
        viable_cells_mean = float(max(0.0, viable_cells_mean))

        # Consumption rates (mM per hour)
        glucose_drop = (viable_cells_mean / 1e7) * (0.8 / media_buffer) * hours
        glutamine_drop = (viable_cells_mean / 1e7) * (0.12 / media_buffer) * hours

        vessel.media_glucose_mM = max(0.0, vessel.media_glucose_mM - glucose_drop)
        vessel.media_glutamine_mM = max(0.0, vessel.media_glutamine_mM - glutamine_drop)

        # Sync depleted nutrients back into InjectionManager spine
        if self.vm.injection_mgr is not None and self.vm.injection_mgr.has_vessel(vessel.vessel_id):
            t_end = float(self.vm.simulated_time + hours)
            self.vm.injection_mgr.set_nutrients_mM(
                vessel.vessel_id,
                {"glucose": float(vessel.media_glucose_mM), "glutamine": float(vessel.media_glutamine_mM)},
                now_h=t_end,
            )

        # Compute starvation stress
        glucose_stress = max(0.0, (GLUCOSE_STRESS_THRESHOLD_mM - vessel.media_glucose_mM) / GLUCOSE_STRESS_THRESHOLD_mM)
        glutamine_stress = max(0.0, (GLUTAMINE_STRESS_THRESHOLD_mM - vessel.media_glutamine_mM) / GLUTAMINE_STRESS_THRESHOLD_mM)
        nutrient_stress = max(glucose_stress, glutamine_stress)

        if nutrient_stress <= 0.0:
            return

        # Propose starvation death hazard
        starvation_rate = MAX_STARVATION_RATE_PER_H * nutrient_stress

        # Phase 1: Apply intrinsic biology hazard scale multiplier (persistent per-vessel)
        if vessel.bio_random_effects:
            starvation_rate *= vessel.bio_random_effects['hazard_scale_mult']

        self._propose_hazard(vessel, starvation_rate, "death_starvation")
