"""
ER stress mechanism simulator.

Handles endoplasmic reticulum stress dynamics and death hazards.
"""

import numpy as np
from typing import TYPE_CHECKING

from .base import StressMechanism
from ..constants import (
    ER_STRESS_K_ON,
    ER_STRESS_K_OFF,
    ER_STRESS_DEATH_THETA,
    ER_STRESS_DEATH_WIDTH,
    ER_STRESS_H_MAX,
)

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class ERStressMechanism(StressMechanism):
    """
    ER stress mechanism simulator.

    ER stress is a morphology-first, death-later mechanism:
    - Morphology shifts early (ER channel increases)
    - Death hazard kicks in only after sustained high stress

    Dynamics (per subpopulation):
    - dS/dt = k_on * f_axis(dose, ic50_shifted) * (1-S) - k_off * S
    - f_axis = dose/(dose + ic50_shifted) for ER-stress axis compounds
    - Death hazard = h_max * sigmoid((S - theta_shifted)/width)

    Phase 5: Operates on subpopulations with shifted IC50 and death thresholds.
    """

    def update(self, vessel: "VesselState", hours: float):
        """
        Update ER stress latent state and propose death hazard if stressed.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        # Contact pressure induces mild ER stress (crowding → ER load)
        contact_pressure = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        contact_stress_rate = 0.02 * contact_pressure

        # Phase 2: Vessel-level ER stress (no subpops)
        S = vessel.er_stress

        if not vessel.compounds:
            # No compounds, but contact pressure can still induce ER stress
            dS_dt = -ER_STRESS_K_OFF * S + contact_stress_rate * (1.0 - S)
            vessel.er_stress = float(np.clip(S + dS_dt * hours, 0.0, 1.0))
            return

        # Compute induction term from all ER-stress compounds
        induction_total = 0.0
        for compound, dose_uM in vessel.compounds.items():
            if dose_uM <= 0:
                continue

            meta = vessel.compound_meta.get(compound)
            if not meta:
                continue

            stress_axis = meta['stress_axis']
            ic50_uM = meta['ic50_uM']
            potency_scalar = meta.get('potency_scalar', 1.0)

            # Only ER-stress and proteostasis axes induce ER stress
            if stress_axis not in ["er_stress", "proteostasis"]:
                continue

            # Phase 3: Apply IC50 shift (continuous heterogeneity via bio_random_effects)
            bio_re = getattr(vessel, "bio_random_effects", None) or {}
            ic50_shift_mult = float(bio_re.get("ic50_shift_mult", 1.0))
            ic50_shifted = max(1e-12, float(ic50_uM) * ic50_shift_mult)

            f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
            induction_total += f_axis

        induction_total = float(min(1.0, induction_total))

        # Apply run context stress sensitivity
        bio_mods = self.vm.run_context.get_biology_modifiers()
        k_on_effective = ER_STRESS_K_ON * bio_mods['stress_sensitivity']

        # Phase 1: Apply intrinsic biology random effect (persistent per-vessel)
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        stress_sens_mult = float(bio_re.get('stress_sensitivity_mult', 1.0))
        k_on_effective *= stress_sens_mult

        # Dynamics: dS/dt = k_on * f * (1-S) - k_off * S + contact_stress * (1-S)
        dS_dt = k_on_effective * induction_total * (1.0 - S) - ER_STRESS_K_OFF * S + contact_stress_rate * (1.0 - S)
        vessel.er_stress = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

        # Phase 2A.1: Check for stochastic death commitment event
        # Phase 2A.3: Refactored to use shared commitment helper
        self.vm.stochastic_biology.maybe_trigger_commitment(
            vessel=vessel,
            mechanism="er_stress",
            stress_S=vessel.er_stress,
            sim_time_h=self.vm.simulated_time,
            dt_h=hours
        )

        # Phase 2: Vessel-level death hazard (no subpop aggregation)
        S = vessel.er_stress

        # Phase 2: No threshold shift (continuous heterogeneity via bio_random_effects)
        theta = ER_STRESS_DEATH_THETA
        width = ER_STRESS_DEATH_WIDTH

        if S > theta:
            x = (S - theta) / width
            sigmoid = float(1.0 / (1.0 + np.exp(-x)))
            hazard_er = ER_STRESS_H_MAX * sigmoid

            # Note: hazard_scale_mult is applied in _commit_step_death, not here
            # This keeps RAW hazard proposals separate from vessel-level scaling
            self._propose_hazard(vessel, hazard_er, "death_er_stress")

        # Phase 2A.1: Add committed death hazard (separate channel for provenance)
        # Phase 2A.3: Check for committed hazard using shared helper
        if vessel.death_committed and vessel.death_commitment_mechanism == "er_stress":
            committed_hazard = self.vm.stochastic_biology.er_committed_death_hazard_per_h
            self._propose_hazard(vessel, committed_hazard, "death_committed_er")
