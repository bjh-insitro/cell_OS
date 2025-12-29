"""
Transport dysfunction mechanism simulator.

Handles cytoskeletal transport dysfunction dynamics.
"""

import numpy as np
from typing import TYPE_CHECKING

from .base import StressMechanism
from ..constants import (
    TRANSPORT_DYSFUNCTION_K_ON,
    TRANSPORT_DYSFUNCTION_K_OFF,
)

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class TransportDysfunctionMechanism(StressMechanism):
    """
    Transport dysfunction mechanism simulator.

    Transport dysfunction is triggered by microtubule disruption:
    - Morphology shifts early (actin channel increases)
    - NO death hazard in v1 (already have mitotic catastrophe for microtubules)

    Dynamics:
    - dS/dt = k_on * f_axis(dose, ic50_shifted) * (1-S) - k_off * S
    - Faster onset/recovery than ER/mito (k_on=0.35, k_off=0.08)
    """

    def update(self, vessel: "VesselState", hours: float):
        """
        Update transport dysfunction latent state (morphology-first, no death in v1).

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        # Contact pressure induces mild transport dysfunction
        contact_pressure = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        contact_transport_rate = 0.01 * contact_pressure

        if not vessel.compounds:
            # No compounds, but contact pressure can still induce dysfunction
            for subpop in vessel.subpopulations.values():
                S = subpop['transport_dysfunction']
                dS_dt = -TRANSPORT_DYSFUNCTION_K_OFF * S + contact_transport_rate * (1.0 - S)
                subpop['transport_dysfunction'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

            vessel.transport_dysfunction = vessel.transport_dysfunction_mixture
            return

        # Update each subpopulation with shifted IC50
        for subpop in vessel.subpopulations.values():
            ic50_shift = subpop['ic50_shift']

            # Compute induction term from all microtubule compounds
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

                # Only microtubule axis induces transport dysfunction
                if stress_axis != "microtubule":
                    continue

                # Apply IC50 shift
                ic50_shifted = ic50_uM * ic50_shift
                f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
                induction_total += f_axis

            induction_total = float(min(1.0, induction_total))

            # Apply run context stress sensitivity
            bio_mods = self.vm.run_context.get_biology_modifiers()
            k_on_effective = TRANSPORT_DYSFUNCTION_K_ON * bio_mods['stress_sensitivity']

            # Phase 1: Apply intrinsic biology random effect (persistent per-vessel)
            if vessel.bio_random_effects:
                k_on_effective *= vessel.bio_random_effects['stress_sensitivity_mult']

            # Dynamics
            S = subpop['transport_dysfunction']
            dS_dt = k_on_effective * induction_total * (1.0 - S) - TRANSPORT_DYSFUNCTION_K_OFF * S + contact_transport_rate * (1.0 - S)
            subpop['transport_dysfunction'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

            # NO death hazard in v1

        # Update scalar for backward compatibility
        vessel.transport_dysfunction = vessel.transport_dysfunction_mixture
