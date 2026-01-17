"""
DNA damage mechanism simulator.

Handles DNA damage dynamics and death hazards for Phase 0 Thalamus.
DNA damage is induced by:
- Direct DNA-damaging agents (etoposide, cisplatin, doxorubicin)
- Secondary effect from oxidative stress (menadione → ROS → double-strand breaks)
- Compounds with dna_damage_coupling parameter

Readout: γ-H2AX phosphorylation (measured via SupplementalIFAssay)
"""

from typing import TYPE_CHECKING

import numpy as np

from ..constants import (
    DNA_DAMAGE_BOOST,
    DNA_DAMAGE_DEATH_THETA,
    DNA_DAMAGE_DEATH_WIDTH,
    DNA_DAMAGE_H_MAX,
    DNA_DAMAGE_K_ACCUM,
    DNA_DAMAGE_K_OFF,
    DNA_DAMAGE_K_ON,
    DNA_DAMAGE_K_REPAIR,
    DNA_DAMAGE_RECOVERY_SLOW,
    ENABLE_DNA_DAMAGE,
    ENABLE_OXIDATIVE_DNA_COUPLING,
    INTERNAL_STRESS_TIMESTEP_H,
    OXIDATIVE_DNA_COUPLING_RATE,
    OXIDATIVE_DNA_COUPLING_THRESHOLD,
)
from .base import StressMechanism

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


class DNADamageMechanism(StressMechanism):
    """
    DNA damage mechanism simulator.

    DNA damage is a morphology-first, death-later mechanism:
    - γ-H2AX phosphorylation appears early (nuclear foci)
    - Death hazard (apoptosis) kicks in after sustained high damage

    Sources of DNA damage:
    1. Direct DNA-damaging compounds (dna_damage stress axis)
    2. Secondary effect from oxidative stress (ROS → double-strand breaks)
    3. Compounds with explicit dna_damage_coupling parameter
    """

    def update(self, vessel: "VesselState", hours: float):
        """
        Update DNA damage latent state and propose death hazard if damaged.

        Uses internal substepping to avoid dt-dependence in forward Euler integration.

        Args:
            vessel: Vessel state to update
            hours: Time interval (hours)
        """
        if hours <= 0 or not ENABLE_DNA_DAMAGE:
            return  # Zero time or disabled → no update

        # Initialize dna_damage if not present (backward compatibility)
        if not hasattr(vessel, "dna_damage"):
            vessel.dna_damage = 0.0
        if not hasattr(vessel, "dna_damage_memory"):
            vessel.dna_damage_memory = 0.0

        # --- Compute induction from all sources ---

        # Source 1: Direct DNA-damaging compounds (dna_damage stress axis)
        induction_direct = 0.0
        oxidative_coupling_induction = 0.0

        if vessel.compounds:
            for compound, dose_uM in vessel.compounds.items():
                if dose_uM <= 0:
                    continue

                meta = vessel.compound_meta.get(compound)
                if not meta:
                    continue

                stress_axis = meta["stress_axis"]
                ic50_uM = meta["ic50_uM"]
                potency_scalar = meta.get("potency_scalar", 1.0)

                # Apply IC50 shift from random effects
                bio_re = getattr(vessel, "bio_random_effects", None) or {}
                ic50_shift_mult = float(bio_re.get("ic50_shift_mult", 1.0))
                ic50_shifted = max(1e-12, float(ic50_uM) * ic50_shift_mult)

                f_axis = float(dose_uM / (dose_uM + ic50_shifted)) * potency_scalar

                # Direct DNA damage induction
                if stress_axis == "dna_damage":
                    induction_direct += f_axis

                # Oxidative compounds with dna_damage_coupling parameter
                # (e.g., menadione has dna_damage_coupling: 0.6)
                if stress_axis == "oxidative":
                    coupling_factor = meta.get("dna_damage_coupling", 0.0)
                    if coupling_factor > 0:
                        oxidative_coupling_induction += f_axis * coupling_factor

        # Source 2: Secondary induction from mito dysfunction (ROS → DSBs)
        mito_coupling_induction = 0.0
        if ENABLE_OXIDATIVE_DNA_COUPLING:
            mito_stress = getattr(vessel, "mito_dysfunction", 0.0)
            if mito_stress > OXIDATIVE_DNA_COUPLING_THRESHOLD:
                # Excess mito dysfunction above threshold induces DNA damage
                excess = mito_stress - OXIDATIVE_DNA_COUPLING_THRESHOLD
                mito_coupling_induction = OXIDATIVE_DNA_COUPLING_RATE * excess

        # Total induction (capped at 1.0)
        induction_total = float(
            min(1.0, induction_direct + oxidative_coupling_induction + mito_coupling_induction)
        )

        # Apply run context stress sensitivity
        bio_mods = self.vm.run_context.get_biology_modifiers()
        k_on_effective = DNA_DAMAGE_K_ON * bio_mods["stress_sensitivity"]

        # Apply intrinsic biology random effect
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        stress_sens_mult = float(bio_re.get("stress_sensitivity_mult", 1.0))
        k_on_effective *= stress_sens_mult

        # --- Internal substepping for ODE integration ---
        # Dynamics:
        #   dD_mem/dt = k_accum * S - k_repair * D_mem  (memory accumulates, repairs slowly)
        #   dS/dt = k_on * (1 + boost*D_mem²) * f * (1-S) - k_off/(1+slow*D_mem) * S

        dt_internal = INTERNAL_STRESS_TIMESTEP_H
        n_substeps = max(1, int(np.ceil(hours / dt_internal)))
        dt = hours / n_substeps

        for _ in range(n_substeps):
            S = vessel.dna_damage
            D_mem = vessel.dna_damage_memory

            # Update damage memory first (accumulates from current damage level)
            dD_dt = DNA_DAMAGE_K_ACCUM * S - DNA_DAMAGE_K_REPAIR * D_mem
            vessel.dna_damage_memory = float(np.clip(D_mem + dD_dt * dt, 0.0, 1.0))

            # Convex damage boost (D² makes history mechanistically compulsory)
            D_current = vessel.dna_damage_memory
            k_on_boosted = k_on_effective * (1.0 + DNA_DAMAGE_BOOST * D_current * D_current)

            # Recovery slowdown (damage visible in trajectory slopes)
            k_off_effective = DNA_DAMAGE_K_OFF / (1.0 + DNA_DAMAGE_RECOVERY_SLOW * D_current)

            # Update DNA damage state
            dS_dt = k_on_boosted * induction_total * (1.0 - S) - k_off_effective * S
            vessel.dna_damage = float(np.clip(S + dS_dt * dt, 0.0, 1.0))

        # --- Stochastic death commitment ---
        self.vm.stochastic_biology.maybe_trigger_commitment(
            vessel=vessel,
            mechanism="dna",
            stress_S=vessel.dna_damage,
            sim_time_h=self.vm.simulated_time,
            dt_h=hours,
        )

        # --- Death hazard (apoptosis from DNA damage) ---
        S = vessel.dna_damage

        # Apply death threshold shift from random effects
        bio_re = getattr(vessel, "bio_random_effects", None) or {}
        theta_shift_mult = float(bio_re.get("death_threshold_shift_mult", 1.0))
        theta = DNA_DAMAGE_DEATH_THETA * theta_shift_mult
        width = DNA_DAMAGE_DEATH_WIDTH

        if S > theta:
            x = (S - theta) / width
            sigmoid = float(1.0 / (1.0 + np.exp(-x)))
            hazard_dna = DNA_DAMAGE_H_MAX * sigmoid
            self._propose_hazard(vessel, hazard_dna, "death_dna_damage")

        # Committed death hazard (if previously committed)
        if vessel.death_committed and vessel.death_commitment_mechanism == "dna":
            committed_hazard = self.vm.stochastic_biology.dna_committed_death_hazard_per_h
            self._propose_hazard(vessel, committed_hazard, "death_committed_dna")
