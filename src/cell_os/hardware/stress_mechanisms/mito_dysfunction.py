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
    ENABLE_ER_MITO_COUPLING,
    ER_MITO_COUPLING_K,
    ER_MITO_COUPLING_D0,
    ER_MITO_COUPLING_SLOPE,
    MITO_DYSFUNCTION_K_ON,
    MITO_DYSFUNCTION_K_OFF,
    MITO_DYSFUNCTION_DEATH_THETA,
    MITO_DYSFUNCTION_DEATH_WIDTH,
    MITO_DYSFUNCTION_H_MAX,
    MITO_DAMAGE_K_ACCUM,
    MITO_DAMAGE_K_REPAIR,
    MITO_DAMAGE_BOOST,
    MITO_DAMAGE_RECOVERY_SLOW,
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
            # Phase 2: Use vessel-level transport dysfunction (not mixture)
            transport_stress = vessel.transport_dysfunction
            if transport_stress > TRANSPORT_MITO_COUPLING_THRESHOLD:
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

        # Phase 2: Vessel-level mito dysfunction (no subpops)
        S = vessel.mito_dysfunction

        # Phase: Scars - ALWAYS update damage accumulation (even without compounds)
        # Damage accumulates from current stress and repairs slowly
        D = vessel.mito_damage
        dD_dt = MITO_DAMAGE_K_ACCUM * S - MITO_DAMAGE_K_REPAIR * D
        vessel.mito_damage = float(np.clip(D + dD_dt * hours, 0.0, 1.0))

        if not vessel.compounds and coupling_induction <= 0:
            # No compounds, no coupling, but contact pressure can still induce dysfunction
            dS_dt = -MITO_DYSFUNCTION_K_OFF * S + contact_mito_rate * (1.0 - S)
            vessel.mito_dysfunction = float(np.clip(S + dS_dt * hours, 0.0, 1.0))
            return

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

            # Phase 3: Apply IC50 shift (continuous heterogeneity via bio_random_effects)
            bio_re = getattr(vessel, "bio_random_effects", None) or {}
            ic50_shift_mult = float(bio_re.get("ic50_shift_mult", 1.0))
            ic50_shifted = max(1e-12, float(ic50_uM) * ic50_shift_mult)

            f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar
            induction_total += f_axis

        # Add coupling induction
        induction_total += coupling_induction
        induction_total = float(min(1.0, induction_total))

        # Apply run context stress sensitivity
        bio_mods = self.vm.run_context.get_biology_modifiers()
        k_on_effective = MITO_DYSFUNCTION_K_ON * bio_mods['stress_sensitivity']

        # Phase 1: Apply intrinsic biology random effect (persistent per-vessel)
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        stress_sens_mult = float(bio_re.get('stress_sensitivity_mult', 1.0))
        k_on_effective *= stress_sens_mult

        # ER → Mito susceptibility coupling: ER damage amplifies mito induction
        if ENABLE_ER_MITO_COUPLING:
            er_damage = float(getattr(vessel, 'er_damage', 0.0))
            # Sigmoid: 1/(1+exp(-slope*(D-D0)))
            sigmoid = 1.0 / (1.0 + np.exp(-ER_MITO_COUPLING_SLOPE * (er_damage - ER_MITO_COUPLING_D0)))
            # Amplification: 1 + K*sigmoid, clamped at 1+K
            er_mito_amp = min(1.0 + ER_MITO_COUPLING_K * sigmoid, 1.0 + ER_MITO_COUPLING_K)
            k_on_effective *= er_mito_amp

        # Phase: Scars - Damage boosts induction (convex: D² makes damage compulsory)
        D_current = vessel.mito_damage
        k_on_boosted = k_on_effective * (1.0 + MITO_DAMAGE_BOOST * D_current * D_current)

        # Phase: Scars - Damage slows recovery (visible in trajectory slopes)
        k_off_effective = MITO_DYSFUNCTION_K_OFF / (1.0 + MITO_DAMAGE_RECOVERY_SLOW * D_current)

        # Dynamics (using damage-modified rates)
        dS_dt = k_on_boosted * induction_total * (1.0 - S) - k_off_effective * S + contact_mito_rate * (1.0 - S)
        vessel.mito_dysfunction = float(np.clip(S + dS_dt * hours, 0.0, 1.0))

        # Phase 2A.2: Check for stochastic death commitment event
        # Phase 2A.3: Refactored to use shared commitment helper
        self.vm.stochastic_biology.maybe_trigger_commitment(
            vessel=vessel,
            mechanism="mito",
            stress_S=vessel.mito_dysfunction,
            sim_time_h=self.vm.simulated_time,
            dt_h=hours
        )

        # Phase 2: Vessel-level death hazard (no subpop aggregation)
        S = vessel.mito_dysfunction

        # Phase 3.1: Apply death threshold shift (correlated with IC50 sensitivity)
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        theta_shift_mult = float(bio_re.get("death_threshold_shift_mult", 1.0))
        theta = MITO_DYSFUNCTION_DEATH_THETA * theta_shift_mult
        width = MITO_DYSFUNCTION_DEATH_WIDTH

        if S > theta:
            x = (S - theta) / width
            sigmoid = float(1.0 / (1.0 + np.exp(-x)))
            hazard_mito = MITO_DYSFUNCTION_H_MAX * sigmoid

            # Note: hazard_scale_mult is applied in _commit_step_death, not here
            self._propose_hazard(vessel, hazard_mito, "death_mito_dysfunction")

        # Phase 2A.2: Add committed death hazard (separate channel for provenance)
        # Phase 2A.3: Check for committed hazard using shared helper
        if vessel.death_committed and vessel.death_commitment_mechanism == "mito":
            committed_hazard = self.vm.stochastic_biology.mito_committed_death_hazard_per_h
            self._propose_hazard(vessel, committed_hazard, "death_committed_mito")
