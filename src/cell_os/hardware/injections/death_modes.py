"""
Injection I: Death Modes (Death Has Shape)

PROBLEM: Not all death is the same. Different death modes have different signatures.

State Variables:
- death_mode_counts: Number of cells dying via each mode
- apoptotic_bodies: Fragmented cells (visible in imaging)
- necrotic_debris: Ruptured cells (inflammatory)
- silent_dropouts: Detached cells (invisible to most assays)
- autophagy_flux: Cells dying via autophagy
- caspase_activity: Active caspase (apoptosis marker)
- membrane_permeability: Leaked LDH, PI+ (necrosis marker)

Pathologies Introduced:
- Apoptosis: Organized death (caspase+, PS flip, fragmentation)
  → Visible in: Caspase assay, Annexin-V, nuclear morphology
  → Invisible in: LDH release (membrane intact until late)
- Necrosis: Membrane rupture (LDH+, PI+, inflammatory)
  → Visible in: LDH release, PI staining, cell swelling
  → Invisible in: Caspase activity, PS flip (no apoptotic machinery)
- Silent dropout: Detachment (cells lost from well)
  → Invisible in: ALL assays (cells are gone)
  → Only detectable by: Cell count decrease, plate imaging
- Autophagy: Vacuolar death (LC3+, no caspase)
  → Visible in: LC3 puncta, autophagosome markers
  → Confounds: Viability assays (metabolically active until late)

Exploits Blocked:
- "All death looks the same": Different modes, different signatures
- "Viability = alive cells": Autophagic cells are "alive" but dying
- "Cell count = viability": Silent dropouts reduce count without death markers
- "ATP = viability": Necrotic cells lose ATP instantly, apoptotic cells retain ATP

Real-World Motivation:
- Apoptosis: Caspase-dependent, energy-dependent, "clean" death
- Necrosis: Accidental death, energy-independent, inflammatory
- Anoikis: Detachment-induced apoptosis (dropout)
- Necroptosis: Programmed necrosis (RIPK1/3, MLKL)
- Autophagy: Self-digestion, can be pro-survival or pro-death
- Pyroptosis: Inflammatory caspase-1 death

Philosophy:
Death is not a binary (alive/dead). It's a spectrum with distinct modes,
each visible to different assays in different ways.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum
import numpy as np
from .base import InjectionState, Injection, InjectionContext


class DeathMode(Enum):
    """Types of cell death."""
    APOPTOSIS = "apoptosis"              # Caspase-dependent, organized
    NECROSIS = "necrosis"                # Membrane rupture, accidental
    SILENT_DROPOUT = "silent_dropout"    # Detachment, lost from well
    AUTOPHAGY = "autophagy"              # Vacuolar death, LC3+
    NECROPTOSIS = "necroptosis"          # Programmed necrosis (RIPK/MLKL)
    PYROPTOSIS = "pyroptosis"            # Inflammatory caspase-1


# Death mode kinetics (hours to complete death)
DEATH_KINETICS = {
    DeathMode.APOPTOSIS: (4.0, 8.0),       # 4-8h execution phase
    DeathMode.NECROSIS: (0.5, 2.0),        # 0.5-2h rapid rupture
    DeathMode.SILENT_DROPOUT: (0.0, 0.0),  # Instant (detachment)
    DeathMode.AUTOPHAGY: (12.0, 24.0),     # 12-24h slow degradation
    DeathMode.NECROPTOSIS: (2.0, 4.0),     # 2-4h programmed rupture
    DeathMode.PYROPTOSIS: (1.0, 3.0),      # 1-3h inflammatory death
}

# Assay visibility (which assays detect which death modes)
ASSAY_VISIBILITY = {
    'caspase_activity': {
        DeathMode.APOPTOSIS: 1.0,          # Strongly positive
        DeathMode.PYROPTOSIS: 0.3,         # Caspase-1 (different)
        DeathMode.NECROSIS: 0.0,
        DeathMode.NECROPTOSIS: 0.0,
        DeathMode.AUTOPHAGY: 0.0,
        DeathMode.SILENT_DROPOUT: 0.0,
    },
    'ldh_release': {
        DeathMode.NECROSIS: 1.0,           # Immediate membrane rupture
        DeathMode.NECROPTOSIS: 0.9,        # Programmed rupture
        DeathMode.PYROPTOSIS: 0.8,         # Inflammatory rupture
        DeathMode.APOPTOSIS: 0.3,          # Late secondary necrosis
        DeathMode.AUTOPHAGY: 0.1,
        DeathMode.SILENT_DROPOUT: 0.0,     # Cells are gone
    },
    'annexin_v': {
        DeathMode.APOPTOSIS: 1.0,          # PS flip
        DeathMode.NECROSIS: 0.5,           # PS exposed after rupture
        DeathMode.NECROPTOSIS: 0.4,
        DeathMode.PYROPTOSIS: 0.3,
        DeathMode.AUTOPHAGY: 0.2,
        DeathMode.SILENT_DROPOUT: 0.0,
    },
    'pi_staining': {
        DeathMode.NECROSIS: 1.0,           # Immediate permeability
        DeathMode.NECROPTOSIS: 0.9,
        DeathMode.PYROPTOSIS: 0.9,
        DeathMode.APOPTOSIS: 0.4,          # Late stage
        DeathMode.AUTOPHAGY: 0.3,
        DeathMode.SILENT_DROPOUT: 0.0,
    },
    'atp_content': {
        # Higher = more ATP retained (inverse of death)
        DeathMode.AUTOPHAGY: 0.6,          # Metabolically active
        DeathMode.APOPTOSIS: 0.4,          # Some ATP retained
        DeathMode.NECROSIS: 0.0,           # Instant ATP loss
        DeathMode.NECROPTOSIS: 0.1,
        DeathMode.PYROPTOSIS: 0.1,
        DeathMode.SILENT_DROPOUT: 0.0,
    },
    'cell_count': {
        # Affects direct cell counting
        DeathMode.SILENT_DROPOUT: 0.0,     # Cells gone (not counted)
        DeathMode.APOPTOSIS: 0.8,          # Bodies remain (fragmented)
        DeathMode.NECROSIS: 0.6,           # Debris remains
        DeathMode.NECROPTOSIS: 0.5,
        DeathMode.AUTOPHAGY: 0.9,          # Cell remains intact
        DeathMode.PYROPTOSIS: 0.4,
    },
}


@dataclass
class DeathModeState(InjectionState):
    """
    Death mode state per well.

    Tracks how cells die and their assay signatures.
    """
    vessel_id: str

    # Death mode counts (fraction of population)
    death_mode_fractions: Dict[DeathMode, float] = field(default_factory=dict)

    # Active death markers
    caspase_activity: float = 0.0        # 0-1 (apoptosis marker)
    membrane_permeability: float = 0.0   # 0-1 (necrosis marker)
    ps_externalization: float = 0.0      # 0-1 (early apoptosis)
    autophagosome_count: float = 0.0     # 0-1 (autophagy)

    # Debris and bodies
    apoptotic_bodies_fraction: float = 0.0  # Fragmented cells
    necrotic_debris_fraction: float = 0.0   # Ruptured cells
    silent_dropouts_fraction: float = 0.0   # Lost cells (undetectable)

    # Total death fraction (sum of all modes)
    total_death_fraction: float = 0.0

    def __post_init__(self):
        """Initialize death mode fractions."""
        if not self.death_mode_fractions:
            self.death_mode_fractions = {mode: 0.0 for mode in DeathMode}

    def record_death(self, death_mode: DeathMode, fraction: float) -> None:
        """
        Record cells dying via specific mode.

        Args:
            death_mode: Type of death
            fraction: Fraction of population dying (0-1)
        """
        self.death_mode_fractions[death_mode] += fraction
        self.total_death_fraction += fraction

        # Update mode-specific markers
        if death_mode == DeathMode.APOPTOSIS:
            self.caspase_activity = min(1.0, self.caspase_activity + fraction)
            self.ps_externalization = min(1.0, self.ps_externalization + fraction)
            self.apoptotic_bodies_fraction += fraction

        elif death_mode == DeathMode.NECROSIS:
            self.membrane_permeability = min(1.0, self.membrane_permeability + fraction)
            self.necrotic_debris_fraction += fraction

        elif death_mode == DeathMode.SILENT_DROPOUT:
            self.silent_dropouts_fraction += fraction
            # No markers (cells are gone!)

        elif death_mode == DeathMode.AUTOPHAGY:
            self.autophagosome_count = min(1.0, self.autophagosome_count + fraction * 2.0)

        elif death_mode == DeathMode.NECROPTOSIS:
            self.membrane_permeability = min(1.0, self.membrane_permeability + fraction * 0.9)
            self.necrotic_debris_fraction += fraction * 0.9

        elif death_mode == DeathMode.PYROPTOSIS:
            self.membrane_permeability = min(1.0, self.membrane_permeability + fraction * 0.8)
            self.caspase_activity = min(1.0, self.caspase_activity + fraction * 0.3)  # Caspase-1

    def get_assay_readout(self, assay_type: str) -> float:
        """
        Get assay-specific readout based on death mode distribution.

        Args:
            assay_type: Assay name (e.g., 'caspase_activity', 'ldh_release')

        Returns:
            Assay signal (0-1)
        """
        if assay_type not in ASSAY_VISIBILITY:
            return 0.0

        visibility = ASSAY_VISIBILITY[assay_type]

        # Weighted sum across death modes
        signal = 0.0
        for death_mode, fraction in self.death_mode_fractions.items():
            mode_visibility = visibility[death_mode]
            signal += fraction * mode_visibility

        return float(np.clip(signal, 0.0, 1.0))

    def get_apparent_viability(self, assay_type: str) -> float:
        """
        Get apparent viability for an assay (1 - death signal).

        Different assays see different death modes differently.

        Args:
            assay_type: Assay name

        Returns:
            Apparent viability (0-1)
        """
        death_signal = self.get_assay_readout(assay_type)
        return 1.0 - death_signal

    def get_true_viability(self) -> float:
        """
        Get true viability (ground truth).

        Returns:
            Fraction of truly viable cells (0-1)
        """
        return 1.0 - self.total_death_fraction

    def check_invariants(self) -> None:
        """Check death fractions are valid."""
        if not (0.0 <= self.total_death_fraction <= 1.0):
            raise ValueError(f"Invalid total death: {self.total_death_fraction}")

        for mode, fraction in self.death_mode_fractions.items():
            if not (0.0 <= fraction <= 1.0):
                raise ValueError(f"Invalid {mode.value} fraction: {fraction}")


class DeathModesInjection(Injection):
    """
    Injection I: Death Modes (Death Has Shape).

    Makes death heterogeneous. Agents must:
    - Recognize that different assays see different death modes
    - Understand viability is assay-dependent
    - Account for silent dropouts (invisible death)
    - Know that ATP ≠ LDH ≠ caspase ≠ true viability
    """

    def __init__(self, seed: int = 0):
        """
        Initialize death modes injection.

        Args:
            seed: RNG seed for stochastic death mode selection
        """
        self.rng = np.random.default_rng(seed + 800)

    def create_state(self, vessel_id: str, context: InjectionContext) -> DeathModeState:
        """
        Create death mode state for a well.

        Initial state: No death (all cells viable).
        """
        state = DeathModeState(
            vessel_id=vessel_id,
            death_mode_fractions={mode: 0.0 for mode in DeathMode},
            caspase_activity=0.0,
            membrane_permeability=0.0,
            ps_externalization=0.0,
            autophagosome_count=0.0,
            apoptotic_bodies_fraction=0.0,
            necrotic_debris_fraction=0.0,
            silent_dropouts_fraction=0.0,
            total_death_fraction=0.0,
        )
        return state

    def apply_time_step(self, state: DeathModeState, dt: float, context: InjectionContext) -> None:
        """
        Death markers decay over time (bodies cleared, debris removed).

        Args:
            dt: Time step (hours)
        """
        # Apoptotic bodies cleared by phagocytosis (slow)
        decay_rate_apoptotic = 0.01  # 1% per hour
        state.apoptotic_bodies_fraction *= (1.0 - decay_rate_apoptotic * dt)

        # Necrotic debris cleared faster (inflammatory response)
        decay_rate_necrotic = 0.03  # 3% per hour
        state.necrotic_debris_fraction *= (1.0 - decay_rate_necrotic * dt)

        # Caspase activity decays (enzymatic degradation)
        state.caspase_activity *= np.exp(-dt / 12.0)  # 12h half-life

        # Membrane permeability persists (debris remains)
        state.membrane_permeability *= np.exp(-dt / 24.0)  # 24h half-life

    def on_event(self, state: DeathModeState, context: InjectionContext) -> None:
        """
        Trigger death modes based on stress events.

        Events:
        - 'trigger_apoptosis': Caspase-dependent death
        - 'trigger_necrosis': Membrane rupture
        - 'trigger_dropout': Detachment
        - 'trigger_autophagy': Vacuolar death
        - 'stress_induced_death': Mixed modes based on stress type
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'trigger_apoptosis':
            fraction = params.get('fraction', 0.10)
            state.record_death(DeathMode.APOPTOSIS, fraction)

        elif event_type == 'trigger_necrosis':
            fraction = params.get('fraction', 0.10)
            state.record_death(DeathMode.NECROSIS, fraction)

        elif event_type == 'trigger_dropout':
            fraction = params.get('fraction', 0.05)
            state.record_death(DeathMode.SILENT_DROPOUT, fraction)

        elif event_type == 'trigger_autophagy':
            fraction = params.get('fraction', 0.10)
            state.record_death(DeathMode.AUTOPHAGY, fraction)

        elif event_type == 'stress_induced_death':
            # Mixed death modes based on stress type
            stress_type = params.get('stress_type', 'general')
            total_fraction = params.get('fraction', 0.10)

            # Different stresses favor different death modes
            if stress_type == 'oxidative':
                # Oxidative stress → mostly apoptosis
                state.record_death(DeathMode.APOPTOSIS, total_fraction * 0.7)
                state.record_death(DeathMode.NECROSIS, total_fraction * 0.2)
                state.record_death(DeathMode.AUTOPHAGY, total_fraction * 0.1)

            elif stress_type == 'toxic':
                # Toxic compounds → mixed (dose-dependent)
                state.record_death(DeathMode.APOPTOSIS, total_fraction * 0.5)
                state.record_death(DeathMode.NECROSIS, total_fraction * 0.3)
                state.record_death(DeathMode.AUTOPHAGY, total_fraction * 0.2)

            elif stress_type == 'mechanical':
                # Mechanical stress → necrosis + dropout
                state.record_death(DeathMode.NECROSIS, total_fraction * 0.4)
                state.record_death(DeathMode.SILENT_DROPOUT, total_fraction * 0.4)
                state.record_death(DeathMode.APOPTOSIS, total_fraction * 0.2)

            elif stress_type == 'detachment':
                # Detachment stress → anoikis (dropout + apoptosis)
                state.record_death(DeathMode.SILENT_DROPOUT, total_fraction * 0.6)
                state.record_death(DeathMode.APOPTOSIS, total_fraction * 0.4)

    def get_biology_modifiers(self, state: DeathModeState, context: InjectionContext) -> Dict[str, Any]:
        """
        Death affects biology.

        Returns:
            Dict with:
            - true_viability: Ground truth viability
            - population_multiplier: Reduce population by dead cells
        """
        true_viability = state.get_true_viability()
        population_mult = true_viability  # Dead cells reduce population

        return {
            'true_viability': true_viability,
            'population_multiplier': population_mult,
        }

    def get_measurement_modifiers(self, state: DeathModeState, context: InjectionContext) -> Dict[str, Any]:
        """
        Death modes affect measurements differently.

        Returns:
            Dict with assay-specific viability estimates
        """
        # Different assays see different things
        return {
            'viability_atp': state.get_apparent_viability('atp_content'),
            'viability_ldh': state.get_apparent_viability('ldh_release'),
            'viability_caspase': state.get_apparent_viability('caspase_activity'),
            'viability_pi': state.get_apparent_viability('pi_staining'),
            'viability_count': state.get_apparent_viability('cell_count'),
            'true_viability': state.get_true_viability(),
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: DeathModeState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add death mode metadata to observations.
        """
        # Add assay readouts
        observation['caspase_activity'] = state.get_assay_readout('caspase_activity')
        observation['ldh_release'] = state.get_assay_readout('ldh_release')
        observation['annexin_v_positive'] = state.get_assay_readout('annexin_v')
        observation['pi_positive'] = state.get_assay_readout('pi_staining')

        # Add death mode distribution
        observation['death_apoptosis_fraction'] = state.death_mode_fractions[DeathMode.APOPTOSIS]
        observation['death_necrosis_fraction'] = state.death_mode_fractions[DeathMode.NECROSIS]
        observation['death_dropout_fraction'] = state.death_mode_fractions[DeathMode.SILENT_DROPOUT]
        observation['death_total_fraction'] = state.total_death_fraction

        # Add viability estimates (assay-dependent)
        observation['viability_atp'] = state.get_apparent_viability('atp_content')
        observation['viability_ldh'] = state.get_apparent_viability('ldh_release')
        observation['viability_true'] = state.get_true_viability()

        # Warn if assays disagree (death mode confounding)
        viability_atp = state.get_apparent_viability('atp_content')
        viability_ldh = state.get_apparent_viability('ldh_release')
        viability_discrepancy = abs(viability_atp - viability_ldh)

        if viability_discrepancy > 0.2:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'viability_assay_discrepancy_{viability_discrepancy:.2f}'
            )

        # Warn if silent dropouts are significant
        if state.silent_dropouts_fraction > 0.10:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'silent_dropouts_{state.silent_dropouts_fraction:.2f}'
            )

        return observation
