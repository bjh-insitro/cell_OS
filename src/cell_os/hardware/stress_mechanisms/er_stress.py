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

        if not vessel.compounds:
            # No compounds, but contact pressure can still induce ER stress
            for subpop in vessel.subpopulations.values():
                S = subpop['er_stress']
                dS_dt = -ER_STRESS_K_OFF * S + contact_stress_rate * (1.0 - S)
                subpop['er_stress'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

            vessel.er_stress = vessel.er_stress_mixture
            return

        # Update each subpopulation with shifted IC50
        for subpop in vessel.subpopulations.values():
            ic50_shift = subpop['ic50_shift']

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

                # Apply IC50 shift
                ic50_shifted = ic50_uM * ic50_shift
                f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
                induction_total += f_axis

            induction_total = float(min(1.0, induction_total))

            # Apply run context stress sensitivity
            bio_mods = self.vm.run_context.get_biology_modifiers()
            k_on_effective = ER_STRESS_K_ON * bio_mods['stress_sensitivity']

            # Dynamics: dS/dt = k_on * f * (1-S) - k_off * S + contact_stress * (1-S)
            S = subpop['er_stress']
            dS_dt = k_on_effective * induction_total * (1.0 - S) - ER_STRESS_K_OFF * S + contact_stress_rate * (1.0 - S)
            subpop['er_stress'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

        # Update scalar for backward compatibility
        vessel.er_stress = vessel.er_stress_mixture

        # Propose vessel-level death hazard from weighted per-subpop hazards
        hazard_er_total = 0.0

        for subpop in vessel.subpopulations.values():
            threshold_shift = subpop['stress_threshold_shift']
            S = subpop['er_stress']

            # Shifted threshold: sensitive (shift < 1.0) die at lower stress
            theta_shifted = ER_STRESS_DEATH_THETA * threshold_shift
            width_shifted = ER_STRESS_DEATH_WIDTH * threshold_shift

            if S > theta_shifted:
                x = (S - theta_shifted) / width_shifted
                sigmoid = float(1.0 / (1.0 + np.exp(-x)))
                hazard_subpop = ER_STRESS_H_MAX * sigmoid * subpop['fraction']
                hazard_er_total += hazard_subpop

        if hazard_er_total > 0:
            self._propose_hazard(vessel, hazard_er_total, "death_er_stress")
