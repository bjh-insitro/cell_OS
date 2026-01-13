"""
Cell Cycle Dynamics Model.

A biologically realistic model of the eukaryotic cell cycle with:
- Phase distribution tracking (G0, G1, S, G2, M)
- Checkpoint mechanisms (G1/S, G2/M, spindle assembly)
- Phase-specific drug sensitivity
- Synchronization protocols
- Observable markers (DNA content, phospho-H3)

References:
- Tyson & Novak (2001) - Mathematical model of cell cycle
- Domingo-Sananes et al. (2011) - Quantitative cell cycle analysis
- Bartek & Lukas (2001) - Checkpoint mechanisms
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class CellCyclePhase(str, Enum):
    """Cell cycle phases."""
    G0 = "G0"   # Quiescent (reversible exit from cycle)
    G1 = "G1"   # Gap 1 (growth, preparation for S)
    S = "S"     # Synthesis (DNA replication)
    G2 = "G2"   # Gap 2 (preparation for mitosis)
    M = "M"     # Mitosis (cell division)


# Typical phase durations (hours) - varies by cell line
DEFAULT_PHASE_DURATIONS = {
    CellCyclePhase.G1: 10.0,  # 10 hours
    CellCyclePhase.S: 8.0,    # 8 hours
    CellCyclePhase.G2: 4.0,   # 4 hours
    CellCyclePhase.M: 1.0,    # 1 hour
}


@dataclass
class CellLineProfile:
    """Cell-line-specific cell cycle parameters."""
    name: str
    doubling_time_h: float
    g1_fraction: float  # Fraction of cycle in G1
    s_fraction: float   # Fraction of cycle in S
    g2_fraction: float  # Fraction of cycle in G2
    m_fraction: float   # Fraction of cycle in M

    # Checkpoint sensitivity
    p53_functional: bool = True      # p53 status (G1/S checkpoint)
    rb_functional: bool = True       # Rb status (G1/S checkpoint)
    atm_atr_functional: bool = True  # ATM/ATR (DNA damage response)

    # Growth factor dependency
    serum_dependency: float = 0.8    # 0-1, how much serum affects G1→S
    contact_inhibition: float = 0.7  # 0-1, how much confluence arrests G1

    # Fraction that can enter G0 (quiescence)
    quiescence_capacity: float = 0.3


# Cell line profiles based on literature
CELL_LINE_PROFILES = {
    'A549': CellLineProfile(
        name='A549',
        doubling_time_h=22.0,
        g1_fraction=0.45,
        s_fraction=0.35,
        g2_fraction=0.15,
        m_fraction=0.05,
        p53_functional=True,  # Wild-type p53
        contact_inhibition=0.5,  # Cancer cells have reduced contact inhibition
        quiescence_capacity=0.2,
    ),
    'HepG2': CellLineProfile(
        name='HepG2',
        doubling_time_h=30.0,
        g1_fraction=0.50,
        s_fraction=0.30,
        g2_fraction=0.15,
        m_fraction=0.05,
        p53_functional=True,
        contact_inhibition=0.6,
        quiescence_capacity=0.3,
    ),
    'iPSC_NGN2': CellLineProfile(
        name='iPSC_NGN2',
        doubling_time_h=200.0,  # Essentially post-mitotic
        g1_fraction=0.90,  # Mostly in G0/G1
        s_fraction=0.05,
        g2_fraction=0.03,
        m_fraction=0.02,
        contact_inhibition=0.9,  # Strong contact inhibition
        quiescence_capacity=0.95,  # Can readily enter G0
    ),
    'iPSC_Microglia': CellLineProfile(
        name='iPSC_Microglia',
        doubling_time_h=48.0,
        g1_fraction=0.55,
        s_fraction=0.25,
        g2_fraction=0.15,
        m_fraction=0.05,
        contact_inhibition=0.7,
        quiescence_capacity=0.5,
    ),
    'HeLa': CellLineProfile(
        name='HeLa',
        doubling_time_h=18.0,  # Fast growing
        g1_fraction=0.35,
        s_fraction=0.40,
        g2_fraction=0.20,
        m_fraction=0.05,
        p53_functional=False,  # p53 degraded by HPV E6
        rb_functional=False,   # Rb degraded by HPV E7
        contact_inhibition=0.3,  # Weak contact inhibition
        quiescence_capacity=0.1,
    ),
}


@dataclass
class CheckpointState:
    """State of cell cycle checkpoints."""
    # G1/S checkpoint (restriction point)
    g1s_arrested: bool = False
    g1s_arrest_strength: float = 0.0  # 0-1

    # G2/M checkpoint (DNA damage)
    g2m_arrested: bool = False
    g2m_arrest_strength: float = 0.0

    # Spindle assembly checkpoint (SAC)
    sac_arrested: bool = False
    sac_arrest_strength: float = 0.0

    # DNA damage level (triggers checkpoints)
    dna_damage: float = 0.0  # 0-1


@dataclass
class DrugCycleEffect:
    """How a drug affects the cell cycle."""
    name: str
    target_phase: CellCyclePhase  # Primary phase affected
    mechanism: str  # Description of mechanism

    # Arrest parameters
    causes_arrest: bool = True
    arrest_strength: float = 1.0     # 0-1, how strongly it arrests
    arrest_ec50_uM: float = 1.0      # EC50 for arrest

    # Death parameters (from prolonged arrest)
    death_from_arrest: bool = True
    arrest_tolerance_h: float = 24.0  # Hours in arrest before death starts
    death_rate_arrested: float = 0.1  # Death rate per hour when arrested

    # Slowing parameters (if not arresting)
    slowing_factor: float = 0.5       # How much it slows the phase


# Drug effects on cell cycle
DRUG_CYCLE_EFFECTS = {
    # Microtubule drugs - M phase arrest (spindle disruption)
    'paclitaxel': DrugCycleEffect(
        name='paclitaxel',
        target_phase=CellCyclePhase.M,
        mechanism='Microtubule stabilization prevents spindle dynamics',
        arrest_ec50_uM=0.01,
        arrest_tolerance_h=12.0,  # Mitotic arrest → death quickly
        death_rate_arrested=0.15,
    ),
    'nocodazole': DrugCycleEffect(
        name='nocodazole',
        target_phase=CellCyclePhase.M,
        mechanism='Microtubule depolymerization disrupts spindle',
        arrest_ec50_uM=0.1,
        arrest_tolerance_h=16.0,
        death_rate_arrested=0.12,
    ),
    'colchicine': DrugCycleEffect(
        name='colchicine',
        target_phase=CellCyclePhase.M,
        mechanism='Microtubule depolymerization',
        arrest_ec50_uM=0.05,
        arrest_tolerance_h=14.0,
        death_rate_arrested=0.12,
    ),

    # CDK4/6 inhibitors - G1 arrest
    'palbociclib': DrugCycleEffect(
        name='palbociclib',
        target_phase=CellCyclePhase.G1,
        mechanism='CDK4/6 inhibition prevents Rb phosphorylation',
        arrest_ec50_uM=0.1,
        arrest_tolerance_h=72.0,  # G1 arrest is well-tolerated
        death_rate_arrested=0.02,  # Cytostatic, not cytotoxic
    ),
    'ribociclib': DrugCycleEffect(
        name='ribociclib',
        target_phase=CellCyclePhase.G1,
        mechanism='CDK4/6 inhibition',
        arrest_ec50_uM=0.15,
        arrest_tolerance_h=72.0,
        death_rate_arrested=0.02,
    ),

    # DNA synthesis inhibitors - S phase arrest
    'hydroxyurea': DrugCycleEffect(
        name='hydroxyurea',
        target_phase=CellCyclePhase.S,
        mechanism='Ribonucleotide reductase inhibition depletes dNTPs',
        arrest_ec50_uM=100.0,  # High concentration needed
        arrest_tolerance_h=24.0,
        death_rate_arrested=0.08,
    ),
    'aphidicolin': DrugCycleEffect(
        name='aphidicolin',
        target_phase=CellCyclePhase.S,
        mechanism='DNA polymerase α/δ inhibition',
        arrest_ec50_uM=1.0,
        arrest_tolerance_h=20.0,
        death_rate_arrested=0.1,
    ),
    'thymidine': DrugCycleEffect(
        name='thymidine',
        target_phase=CellCyclePhase.S,
        mechanism='Nucleotide pool imbalance (excess thymidine)',
        arrest_ec50_uM=2000.0,  # 2mM for double thymidine block
        arrest_tolerance_h=48.0,  # Well tolerated
        death_rate_arrested=0.01,
    ),

    # Topoisomerase inhibitors - S/G2 arrest
    'etoposide': DrugCycleEffect(
        name='etoposide',
        target_phase=CellCyclePhase.S,  # Primarily S, also G2
        mechanism='Topoisomerase II inhibition causes DNA breaks',
        arrest_ec50_uM=1.0,
        arrest_tolerance_h=18.0,
        death_rate_arrested=0.12,
    ),
    'camptothecin': DrugCycleEffect(
        name='camptothecin',
        target_phase=CellCyclePhase.S,
        mechanism='Topoisomerase I inhibition',
        arrest_ec50_uM=0.1,
        arrest_tolerance_h=16.0,
        death_rate_arrested=0.15,
    ),

    # G2/M inhibitors
    'ro3306': DrugCycleEffect(
        name='ro3306',
        target_phase=CellCyclePhase.G2,
        mechanism='CDK1 inhibition prevents mitotic entry',
        arrest_ec50_uM=5.0,
        arrest_tolerance_h=48.0,
        death_rate_arrested=0.03,
    ),
}


@dataclass
class PhaseDistribution:
    """Distribution of cells across cycle phases."""
    g0: float = 0.0   # Quiescent fraction
    g1: float = 0.5   # G1 fraction
    s: float = 0.3    # S phase fraction
    g2: float = 0.15  # G2 fraction
    m: float = 0.05   # Mitotic fraction

    def __post_init__(self):
        """Normalize to sum to 1."""
        total = self.g0 + self.g1 + self.s + self.g2 + self.m
        if total > 0:
            self.g0 /= total
            self.g1 /= total
            self.s /= total
            self.g2 /= total
            self.m /= total

    def as_dict(self) -> Dict[CellCyclePhase, float]:
        return {
            CellCyclePhase.G0: self.g0,
            CellCyclePhase.G1: self.g1,
            CellCyclePhase.S: self.s,
            CellCyclePhase.G2: self.g2,
            CellCyclePhase.M: self.m,
        }

    def to_array(self) -> np.ndarray:
        return np.array([self.g0, self.g1, self.s, self.g2, self.m])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> 'PhaseDistribution':
        return cls(g0=arr[0], g1=arr[1], s=arr[2], g2=arr[3], m=arr[4])

    @classmethod
    def from_profile(cls, profile: CellLineProfile) -> 'PhaseDistribution':
        """Create distribution from cell line profile (asynchronous steady state)."""
        return cls(
            g0=0.0,  # Start with no quiescent cells
            g1=profile.g1_fraction,
            s=profile.s_fraction,
            g2=profile.g2_fraction,
            m=profile.m_fraction,
        )


class CellCycleModel:
    """
    Comprehensive cell cycle dynamics model.

    Models cell population as a distribution across phases with:
    - Phase transition kinetics (ODE-based)
    - Checkpoint activation and arrest
    - Phase-specific drug effects
    - Synchronization protocols
    - Observable markers
    """

    def __init__(
        self,
        cell_line: str = 'A549',
        seed: int = 42,
        initial_distribution: Optional[PhaseDistribution] = None
    ):
        self.profile = CELL_LINE_PROFILES.get(cell_line, CELL_LINE_PROFILES['A549'])
        self.rng = np.random.default_rng(seed)

        # Phase distribution
        if initial_distribution:
            self.distribution = initial_distribution
        else:
            self.distribution = PhaseDistribution.from_profile(self.profile)

        # Checkpoint state
        self.checkpoints = CheckpointState()

        # Tracking
        self.time_h = 0.0
        self.time_in_arrest = {phase: 0.0 for phase in CellCyclePhase}
        self.total_deaths = 0.0

        # Active drugs
        self.active_drugs: Dict[str, float] = {}  # drug_name -> dose_uM

        # Compute base transition rates
        self._compute_transition_rates()

    def _compute_transition_rates(self):
        """Compute phase transition rate constants from doubling time."""
        T = self.profile.doubling_time_h

        # Rate = 1 / phase_duration
        # Phase duration = fraction * doubling_time
        self.k_g1_to_s = 1.0 / max(0.1, self.profile.g1_fraction * T)
        self.k_s_to_g2 = 1.0 / max(0.1, self.profile.s_fraction * T)
        self.k_g2_to_m = 1.0 / max(0.1, self.profile.g2_fraction * T)
        self.k_m_to_g1 = 1.0 / max(0.1, self.profile.m_fraction * T)

        # G0 entry/exit rates
        self.k_g1_to_g0 = 0.01  # Slow entry into quiescence
        self.k_g0_to_g1 = 0.05  # Moderate exit from quiescence

    def add_drug(self, drug_name: str, dose_uM: float):
        """Add a drug that affects the cell cycle."""
        if drug_name in DRUG_CYCLE_EFFECTS:
            self.active_drugs[drug_name] = dose_uM

    def remove_drug(self, drug_name: str):
        """Remove a drug (washout)."""
        if drug_name in self.active_drugs:
            del self.active_drugs[drug_name]

    def _compute_effective_rates(
        self,
        confluence: float = 0.5,
        serum_fraction: float = 1.0,
        nutrients: float = 1.0
    ) -> Dict[str, float]:
        """
        Compute effective transition rates considering:
        - Confluence (contact inhibition)
        - Serum (growth factors)
        - Nutrients
        - Drug effects
        - Checkpoint status
        """
        rates = {
            'g1_to_s': self.k_g1_to_s,
            's_to_g2': self.k_s_to_g2,
            'g2_to_m': self.k_g2_to_m,
            'm_to_g1': self.k_m_to_g1,
            'g1_to_g0': self.k_g1_to_g0,
            'g0_to_g1': self.k_g0_to_g1,
        }

        # Contact inhibition (affects G1→S)
        contact_factor = 1.0 - self.profile.contact_inhibition * confluence
        rates['g1_to_s'] *= max(0.01, contact_factor)

        # Serum starvation (affects G1→S strongly, G0→G1 weakly)
        serum_factor = self.profile.serum_dependency * serum_fraction + (1 - self.profile.serum_dependency)
        rates['g1_to_s'] *= serum_factor
        rates['g0_to_g1'] *= (0.5 + 0.5 * serum_fraction)

        # Nutrient effects (affects S phase)
        rates['s_to_g2'] *= nutrients

        # Quiescence entry increases with confluence and low serum
        rates['g1_to_g0'] *= (1 + confluence) * (1 + (1 - serum_fraction))

        # Apply drug effects
        for drug_name, dose in self.active_drugs.items():
            if drug_name not in DRUG_CYCLE_EFFECTS:
                continue

            effect = DRUG_CYCLE_EFFECTS[drug_name]
            arrest_fraction = dose / (dose + effect.arrest_ec50_uM)

            # Map target phase to affected transition
            if effect.target_phase == CellCyclePhase.G1:
                rates['g1_to_s'] *= (1 - arrest_fraction * effect.arrest_strength)
            elif effect.target_phase == CellCyclePhase.S:
                rates['s_to_g2'] *= (1 - arrest_fraction * effect.arrest_strength)
            elif effect.target_phase == CellCyclePhase.G2:
                rates['g2_to_m'] *= (1 - arrest_fraction * effect.arrest_strength)
            elif effect.target_phase == CellCyclePhase.M:
                rates['m_to_g1'] *= (1 - arrest_fraction * effect.arrest_strength)

        # Apply checkpoint arrests
        if self.checkpoints.g1s_arrested:
            rates['g1_to_s'] *= (1 - self.checkpoints.g1s_arrest_strength)
        if self.checkpoints.g2m_arrested:
            rates['g2_to_m'] *= (1 - self.checkpoints.g2m_arrest_strength)
        if self.checkpoints.sac_arrested:
            rates['m_to_g1'] *= (1 - self.checkpoints.sac_arrest_strength)

        return rates

    def step(
        self,
        dt_h: float,
        confluence: float = 0.5,
        serum_fraction: float = 1.0,
        nutrients: float = 1.0
    ) -> Dict[str, float]:
        """
        Advance cell cycle by dt hours.

        Returns dict with phase distribution and events.
        """
        rates = self._compute_effective_rates(confluence, serum_fraction, nutrients)

        # Current distribution
        g0, g1, s, g2, m = (
            self.distribution.g0,
            self.distribution.g1,
            self.distribution.s,
            self.distribution.g2,
            self.distribution.m
        )

        # ODE: dX/dt = inflow - outflow
        # Using forward Euler (simple but stable for small dt)
        dg0 = rates['g1_to_g0'] * g1 - rates['g0_to_g1'] * g0
        dg1 = rates['g0_to_g1'] * g0 + 2 * rates['m_to_g1'] * m - rates['g1_to_s'] * g1 - rates['g1_to_g0'] * g1
        ds = rates['g1_to_s'] * g1 - rates['s_to_g2'] * s
        dg2 = rates['s_to_g2'] * s - rates['g2_to_m'] * g2
        dm = rates['g2_to_m'] * g2 - rates['m_to_g1'] * m

        # Update
        self.distribution.g0 = max(0, g0 + dg0 * dt_h)
        self.distribution.g1 = max(0, g1 + dg1 * dt_h)
        self.distribution.s = max(0, s + ds * dt_h)
        self.distribution.g2 = max(0, g2 + dg2 * dt_h)
        self.distribution.m = max(0, m + dm * dt_h)

        # Renormalize
        total = (self.distribution.g0 + self.distribution.g1 +
                 self.distribution.s + self.distribution.g2 + self.distribution.m)
        if total > 0:
            self.distribution.g0 /= total
            self.distribution.g1 /= total
            self.distribution.s /= total
            self.distribution.g2 /= total
            self.distribution.m /= total

        # Track arrest time and compute death
        deaths = self._compute_arrest_deaths(dt_h, rates)

        self.time_h += dt_h

        return {
            'distribution': self.distribution.as_dict(),
            'rates': rates,
            'deaths_from_arrest': deaths,
            'time_h': self.time_h,
        }

    def _compute_arrest_deaths(self, dt_h: float, rates: Dict[str, float]) -> float:
        """Compute deaths from prolonged cell cycle arrest."""
        deaths = 0.0

        for drug_name, dose in self.active_drugs.items():
            if drug_name not in DRUG_CYCLE_EFFECTS:
                continue

            effect = DRUG_CYCLE_EFFECTS[drug_name]
            if not effect.death_from_arrest:
                continue

            # Fraction arrested
            arrest_fraction = dose / (dose + effect.arrest_ec50_uM) * effect.arrest_strength

            # Get fraction in target phase
            phase = effect.target_phase
            phase_fraction = getattr(self.distribution, phase.value.lower(), 0)

            # Track time in arrest
            self.time_in_arrest[phase] += dt_h * arrest_fraction

            # Death after tolerance exceeded
            if self.time_in_arrest[phase] > effect.arrest_tolerance_h:
                excess_time = self.time_in_arrest[phase] - effect.arrest_tolerance_h
                death_rate = effect.death_rate_arrested * (1 - np.exp(-excess_time / 10))
                deaths += phase_fraction * arrest_fraction * death_rate * dt_h

        self.total_deaths += deaths
        return deaths

    def simulate(
        self,
        duration_h: float,
        dt_h: float = 0.1,
        confluence: float = 0.5,
        serum_fraction: float = 1.0,
        nutrients: float = 1.0
    ) -> Dict[str, np.ndarray]:
        """
        Simulate cell cycle for given duration.

        Returns time series of phase distributions.
        """
        n_steps = int(duration_h / dt_h)
        times = np.zeros(n_steps)
        g0 = np.zeros(n_steps)
        g1 = np.zeros(n_steps)
        s = np.zeros(n_steps)
        g2 = np.zeros(n_steps)
        m = np.zeros(n_steps)
        deaths = np.zeros(n_steps)

        for i in range(n_steps):
            result = self.step(dt_h, confluence, serum_fraction, nutrients)
            times[i] = self.time_h
            g0[i] = self.distribution.g0
            g1[i] = self.distribution.g1
            s[i] = self.distribution.s
            g2[i] = self.distribution.g2
            m[i] = self.distribution.m
            deaths[i] = result['deaths_from_arrest']

        return {
            'time_h': times,
            'G0': g0,
            'G1': g1,
            'S': s,
            'G2': g2,
            'M': m,
            'deaths': deaths,
            'cumulative_deaths': np.cumsum(deaths),
        }

    # =========================================================================
    # SYNCHRONIZATION PROTOCOLS
    # =========================================================================

    def serum_starve(self, duration_h: float = 24.0, dt_h: float = 0.1):
        """
        Serum starvation to arrest cells in G0/G1.

        Common protocol: 24-48h in 0.1% serum
        Results in G0/G1 accumulation (70-90%)
        """
        return self.simulate(
            duration_h=duration_h,
            dt_h=dt_h,
            serum_fraction=0.01,  # 0.1% serum
            confluence=0.5,
        )

    def release_from_starvation(self, duration_h: float = 24.0, dt_h: float = 0.1):
        """
        Release from serum starvation - synchronous S phase entry.

        After 4-8h: S phase peak
        After 12-16h: G2/M peak
        After 18-24h: second G1
        """
        return self.simulate(
            duration_h=duration_h,
            dt_h=dt_h,
            serum_fraction=1.0,
            confluence=0.5,
        )

    def double_thymidine_block(self, dt_h: float = 0.1) -> Dict[str, np.ndarray]:
        """
        Double thymidine block for G1/S synchronization.

        Protocol:
        1. 2mM thymidine for 18h (first block)
        2. Release for 9h (cells progress through S, G2, M, back to G1/early S)
        3. 2mM thymidine for 18h (second block - captures all at G1/S)
        4. Release - highly synchronized S phase entry

        Returns trajectory through entire protocol.
        """
        all_results = []

        # First thymidine block (18h)
        self.add_drug('thymidine', 2000.0)  # 2mM
        result1 = self.simulate(18.0, dt_h)
        all_results.append(('block1', result1))

        # Release (9h)
        self.remove_drug('thymidine')
        result2 = self.simulate(9.0, dt_h)
        all_results.append(('release1', result2))

        # Second thymidine block (18h)
        self.add_drug('thymidine', 2000.0)
        result3 = self.simulate(18.0, dt_h)
        all_results.append(('block2', result3))

        # Final release
        self.remove_drug('thymidine')

        return {
            'protocol': 'double_thymidine',
            'stages': all_results,
            'final_distribution': self.distribution.as_dict(),
            'expected_sync': 'G1/S boundary',
        }

    def nocodazole_arrest(self, dose_uM: float = 0.1, duration_h: float = 16.0, dt_h: float = 0.1):
        """
        Nocodazole arrest to synchronize in M phase.

        Cells accumulate in prometaphase with condensed chromosomes.
        Commonly used for mitotic shake-off.
        """
        self.add_drug('nocodazole', dose_uM)
        result = self.simulate(duration_h, dt_h)
        return {
            'protocol': 'nocodazole_arrest',
            'result': result,
            'final_distribution': self.distribution.as_dict(),
            'expected_sync': 'M phase (prometaphase)',
            'note': 'Use mitotic shake-off to collect arrested cells',
        }

    def ro3306_arrest(self, dose_uM: float = 10.0, duration_h: float = 20.0, dt_h: float = 0.1):
        """
        RO-3306 (CDK1 inhibitor) arrest at G2/M boundary.

        Cleaner than nocodazole - cells arrest before nuclear envelope breakdown.
        """
        self.add_drug('ro3306', dose_uM)
        result = self.simulate(duration_h, dt_h)
        return {
            'protocol': 'ro3306_arrest',
            'result': result,
            'final_distribution': self.distribution.as_dict(),
            'expected_sync': 'G2/M boundary',
        }

    # =========================================================================
    # OBSERVABLE MARKERS
    # =========================================================================

    def get_dna_content_distribution(self) -> Dict[str, float]:
        """
        Get DNA content distribution (for flow cytometry simulation).

        DNA content:
        - G0/G1: 2N (diploid)
        - S: 2N to 4N (continuous)
        - G2/M: 4N (tetraploid)

        Returns fractions in 2N, S-phase (2N-4N), and 4N peaks.
        """
        return {
            '2N': self.distribution.g0 + self.distribution.g1,  # G0/G1 peak
            '2N_4N': self.distribution.s,  # S phase (broad)
            '4N': self.distribution.g2 + self.distribution.m,  # G2/M peak
        }

    def get_mitotic_index(self) -> float:
        """
        Get mitotic index (phospho-histone H3 positive fraction).

        In practice, this is measured by phospho-H3 (Ser10) staining.
        Only M phase cells are positive.
        """
        return self.distribution.m

    def get_s_phase_fraction(self) -> float:
        """
        Get S phase fraction (BrdU/EdU incorporation).

        Measured by pulse-labeling with nucleotide analogs.
        """
        return self.distribution.s

    def get_ki67_positive(self) -> float:
        """
        Get Ki-67 positive fraction (proliferating cells).

        Ki-67 is expressed in all phases except G0.
        """
        return 1.0 - self.distribution.g0

    def get_flow_cytometry_histogram(self, n_cells: int = 10000, cv: float = 0.05) -> Dict[str, np.ndarray]:
        """
        Simulate flow cytometry DNA content histogram.

        Args:
            n_cells: Number of cells to simulate
            cv: Coefficient of variation for DNA content measurement

        Returns:
            Dict with 'dna_content' array and 'histogram' counts
        """
        dna_content = []

        # G0/G1 cells: 2N
        n_g0g1 = int(n_cells * (self.distribution.g0 + self.distribution.g1))
        dna_content.extend(self.rng.normal(2.0, 2.0 * cv, n_g0g1))

        # S phase cells: uniform 2N-4N
        n_s = int(n_cells * self.distribution.s)
        dna_content.extend(self.rng.uniform(2.0, 4.0, n_s))

        # G2/M cells: 4N
        n_g2m = int(n_cells * (self.distribution.g2 + self.distribution.m))
        dna_content.extend(self.rng.normal(4.0, 4.0 * cv, n_g2m))

        dna_array = np.array(dna_content)

        # Create histogram
        bins = np.linspace(1.5, 4.5, 100)
        hist, bin_edges = np.histogram(dna_array, bins=bins)

        return {
            'dna_content': dna_array,
            'histogram': hist,
            'bin_edges': bin_edges,
            'bin_centers': (bin_edges[:-1] + bin_edges[1:]) / 2,
        }

    # =========================================================================
    # CHECKPOINT ACTIVATION
    # =========================================================================

    def activate_dna_damage_checkpoint(self, damage_level: float = 0.5):
        """
        Activate DNA damage checkpoints (G1/S and G2/M).

        Simulates DNA damage (e.g., from radiation, genotoxic drugs).

        Args:
            damage_level: 0-1, severity of damage
        """
        self.checkpoints.dna_damage = damage_level

        # G1/S checkpoint (p53-dependent)
        if self.profile.p53_functional:
            self.checkpoints.g1s_arrested = damage_level > 0.2
            self.checkpoints.g1s_arrest_strength = min(1.0, damage_level * 1.5)
        else:
            # p53-deficient cells have weak G1/S checkpoint
            self.checkpoints.g1s_arrested = damage_level > 0.6
            self.checkpoints.g1s_arrest_strength = min(0.5, damage_level * 0.5)

        # G2/M checkpoint (ATM/ATR-dependent)
        if self.profile.atm_atr_functional:
            self.checkpoints.g2m_arrested = damage_level > 0.3
            self.checkpoints.g2m_arrest_strength = min(1.0, damage_level * 1.2)

    def deactivate_checkpoints(self):
        """Clear all checkpoint arrests (damage repair complete)."""
        self.checkpoints = CheckpointState()

    # =========================================================================
    # INTEGRATION WITH EXISTING SIMULATION
    # =========================================================================

    def get_proliferation_modifier(self) -> float:
        """
        Get modifier for cell proliferation rate.

        Can be used to modulate growth in existing simulation.
        """
        # Arrested cells don't proliferate
        cycling_fraction = 1.0 - self.distribution.g0

        # Checkpoints slow proliferation
        checkpoint_factor = 1.0
        if self.checkpoints.g1s_arrested:
            checkpoint_factor *= (1 - self.checkpoints.g1s_arrest_strength * 0.5)
        if self.checkpoints.g2m_arrested:
            checkpoint_factor *= (1 - self.checkpoints.g2m_arrest_strength * 0.5)

        return cycling_fraction * checkpoint_factor

    def get_drug_sensitivity_modifier(self, drug_name: str) -> float:
        """
        Get drug sensitivity modifier based on cell cycle phase.

        Phase-specific drugs are more effective when more cells are in target phase.
        """
        if drug_name not in DRUG_CYCLE_EFFECTS:
            return 1.0

        effect = DRUG_CYCLE_EFFECTS[drug_name]
        target_phase = effect.target_phase

        # Get fraction in target phase
        phase_fraction = getattr(self.distribution, target_phase.value.lower(), 0)

        # Sensitivity scales with phase fraction
        # More cells in target phase = higher sensitivity
        return 0.5 + phase_fraction * 1.5  # Range: 0.5 to 2.0


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def simulate_drug_treatment_cycle(
    cell_line: str,
    drug_name: str,
    dose_uM: float,
    duration_h: float = 48.0,
    seed: int = 42
) -> Dict[str, any]:
    """
    Simulate drug treatment with cell cycle dynamics.

    Returns comprehensive results including phase distribution changes.
    """
    model = CellCycleModel(cell_line=cell_line, seed=seed)

    # Simulate without drug (baseline)
    baseline = model.simulate(duration_h=12.0)

    # Add drug
    model.add_drug(drug_name, dose_uM)

    # Simulate with drug
    treatment = model.simulate(duration_h=duration_h)

    return {
        'cell_line': cell_line,
        'drug': drug_name,
        'dose_uM': dose_uM,
        'baseline': baseline,
        'treatment': treatment,
        'final_distribution': model.distribution.as_dict(),
        'total_deaths': model.total_deaths,
        'dna_content': model.get_dna_content_distribution(),
        'mitotic_index': model.get_mitotic_index(),
    }


def compare_cell_lines_response(
    drug_name: str,
    dose_uM: float,
    duration_h: float = 48.0,
    cell_lines: Optional[List[str]] = None
) -> Dict[str, Dict]:
    """Compare drug response across cell lines."""
    if cell_lines is None:
        cell_lines = list(CELL_LINE_PROFILES.keys())

    results = {}
    for cl in cell_lines:
        results[cl] = simulate_drug_treatment_cycle(cl, drug_name, dose_uM, duration_h)

    return results
