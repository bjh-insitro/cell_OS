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
    TRANSPORT_DAMAGE_K_ACCUM,
    TRANSPORT_DAMAGE_K_REPAIR,
    TRANSPORT_DAMAGE_BOOST,
    TRANSPORT_DAMAGE_RECOVERY_SLOW,
    INTERNAL_STRESS_TIMESTEP_H,
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

        Uses internal substepping to avoid dt-dependence in forward Euler integration.
        This prevents "coarse actions change physics" exploits.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        if hours <= 0:
            return  # Zero time → zero update

        # Contact pressure induces mild transport dysfunction
        contact_pressure = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        contact_transport_rate = 0.01 * contact_pressure

        # --- Compute "static" parameters (computed once, used in all substeps) ---

        # Compute induction term from all microtubule compounds
        induction_total = 0.0
        if vessel.compounds:
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

                # Phase 3: Apply IC50 shift (continuous heterogeneity via bio_random_effects)
                bio_re = getattr(vessel, "bio_random_effects", None) or {}
                ic50_shift_mult = float(bio_re.get("ic50_shift_mult", 1.0))
                ic50_shifted = max(1e-12, float(ic50_uM) * ic50_shift_mult)

                f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
                induction_total += f_axis

        induction_total = float(min(1.0, induction_total))

        # Apply run context stress sensitivity
        bio_mods = self.vm.run_context.get_biology_modifiers()
        k_on_effective = TRANSPORT_DYSFUNCTION_K_ON * bio_mods['stress_sensitivity']

        # Phase 1: Apply intrinsic biology random effect (persistent per-vessel)
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        stress_sens_mult = float(bio_re.get('stress_sensitivity_mult', 1.0))
        k_on_effective *= stress_sens_mult

        # --- Internal substepping to avoid dt-dependence ---
        # Dynamics:
        #   dD/dt = k_accum * S - k_repair * D  (damage accumulates from stress, repairs slowly)
        #   dS/dt = k_on * (1 + boost*D²) * f * (1-S) - k_off/(1+slow*D) * S + contact * (1-S)

        # Calculate number of substeps
        dt_internal = INTERNAL_STRESS_TIMESTEP_H
        n_substeps = max(1, int(np.ceil(hours / dt_internal)))
        dt = hours / n_substeps  # Actual substep size (ensures total time matches exactly)

        # Substep the coupled ODE integration (damage first, then stress)
        for _ in range(n_substeps):
            S = vessel.transport_dysfunction
            D = vessel.transport_damage

            # Update damage first (accumulates from current stress level)
            dD_dt = TRANSPORT_DAMAGE_K_ACCUM * S - TRANSPORT_DAMAGE_K_REPAIR * D
            vessel.transport_damage = float(np.clip(D + dD_dt * dt, 0.0, 1.0))

            # Phase: Scars - CONVEX damage boost (D² makes damage mechanistically compulsory)
            D_current = vessel.transport_damage
            k_on_boosted = k_on_effective * (1.0 + TRANSPORT_DAMAGE_BOOST * D_current * D_current)

            # Phase: Scars - Recovery slowdown (damage visible in trajectory slopes)
            k_off_effective = TRANSPORT_DYSFUNCTION_K_OFF / (1.0 + TRANSPORT_DAMAGE_RECOVERY_SLOW * D_current)

            # Update stress (using boosted induction and slowed recovery)
            dS_dt = k_on_boosted * induction_total * (1.0 - S) - k_off_effective * S + contact_transport_rate * (1.0 - S)
            vessel.transport_dysfunction = float(np.clip(S + dS_dt * dt, 0.0, 1.0))

        # NO death hazard in v1 (chronic damage hazard handled in biological_virtual)
