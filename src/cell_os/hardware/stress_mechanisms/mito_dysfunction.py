"""
Mitochondrial dysfunction mechanism simulator.

Handles mitochondrial dysfunction dynamics and death hazards.
"""

import numpy as np
from typing import TYPE_CHECKING

from .base import StressMechanism
from ..constants import (
    ENABLE_TRANSPORT_MITO_COUPLING,
    TRANSPORT_MITO_COUPLING_DELAY_H,
    TRANSPORT_MITO_COUPLING_THRESHOLD,
    TRANSPORT_MITO_COUPLING_RATE,
    MITO_DYSFUNCTION_K_ON,
    MITO_DYSFUNCTION_K_OFF,
    MITO_DYSFUNCTION_DEATH_THETA,
    MITO_DYSFUNCTION_DEATH_WIDTH,
    MITO_DYSFUNCTION_H_MAX,
)

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class MitoDysfunctionMechanism(StressMechanism):
    """
    Mitochondrial dysfunction mechanism simulator.

    Mito dysfunction is a morphology-first, death-later mechanism:
    - Morphology shifts early (mito channel decreases)
    - Death hazard kicks in only after sustained high stress

    Phase 4 Option 3: Cross-talk from transport dysfunction
    - Prolonged transport dysfunction (>18h above threshold) induces mito dysfunction
    """

    def update(self, vessel: "VesselState", hours: float):
        """
        Update mito dysfunction latent state and propose death hazard if stressed.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        # Phase 4: Check for transport → mito coupling
        coupling_induction = 0.0
        if ENABLE_TRANSPORT_MITO_COUPLING:
            transport_mixture = vessel.transport_dysfunction_mixture
            if transport_mixture > TRANSPORT_MITO_COUPLING_THRESHOLD:
                if vessel.transport_high_since is None:
                    vessel.transport_high_since = self.vm.simulated_time
                time_above_threshold = self.vm.simulated_time - vessel.transport_high_since
                if time_above_threshold >= TRANSPORT_MITO_COUPLING_DELAY_H:
                    coupling_induction = TRANSPORT_MITO_COUPLING_RATE
            else:
                vessel.transport_high_since = None

        # Contact pressure induces mild mito dysfunction (crowding → metabolic stress)
        contact_pressure = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        contact_mito_rate = 0.015 * contact_pressure

        if not vessel.compounds and coupling_induction <= 0:
            # No compounds, no coupling, but contact pressure can still induce dysfunction
            for subpop in vessel.subpopulations.values():
                S = subpop['mito_dysfunction']
                dS_dt = -MITO_DYSFUNCTION_K_OFF * S + contact_mito_rate * (1.0 - S)
                subpop['mito_dysfunction'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

            vessel.mito_dysfunction = vessel.mito_dysfunction_mixture
            return

        # Update each subpopulation with shifted IC50
        for subpop in vessel.subpopulations.values():
            ic50_shift = subpop['ic50_shift']

            # Compute induction term from all mitochondrial compounds
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

                # Only mitochondrial axis induces mito dysfunction
                if stress_axis != "mitochondrial":
                    continue

                # Apply IC50 shift
                ic50_shifted = ic50_uM * ic50_shift
                f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
                induction_total += f_axis

            # Add coupling induction (same for all subpopulations)
            induction_total += coupling_induction
            induction_total = float(min(1.0, induction_total))

            # Apply run context stress sensitivity
            bio_mods = self.vm.run_context.get_biology_modifiers()
            k_on_effective = MITO_DYSFUNCTION_K_ON * bio_mods['stress_sensitivity']

            # Phase 1: Apply intrinsic biology random effect (persistent per-vessel)
            if vessel.bio_random_effects:
                k_on_effective *= vessel.bio_random_effects['stress_sensitivity_mult']

            # Dynamics
            S = subpop['mito_dysfunction']
            dS_dt = k_on_effective * induction_total * (1.0 - S) - MITO_DYSFUNCTION_K_OFF * S + contact_mito_rate * (1.0 - S)
            subpop['mito_dysfunction'] = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

        # Update scalar for backward compatibility
        vessel.mito_dysfunction = vessel.mito_dysfunction_mixture

        # Propose vessel-level death hazard from weighted per-subpop hazards
        hazard_mito_total = 0.0

        for subpop in vessel.subpopulations.values():
            threshold_shift = subpop['stress_threshold_shift']
            S = subpop['mito_dysfunction']

            # Shifted threshold
            theta_shifted = MITO_DYSFUNCTION_DEATH_THETA * threshold_shift
            width_shifted = MITO_DYSFUNCTION_DEATH_WIDTH * threshold_shift

            if S > theta_shifted:
                x = (S - theta_shifted) / width_shifted
                sigmoid = float(1.0 / (1.0 + np.exp(-x)))
                hazard_subpop = MITO_DYSFUNCTION_H_MAX * sigmoid * subpop['fraction']
                hazard_mito_total += hazard_subpop

        # Phase 1: Apply intrinsic biology hazard scale multiplier (persistent per-vessel)
        if vessel.bio_random_effects and hazard_mito_total > 0:
            hazard_mito_total *= vessel.bio_random_effects['hazard_scale_mult']

        if hazard_mito_total > 0:
            self._propose_hazard(vessel, hazard_mito_total, "death_mito_dysfunction")
