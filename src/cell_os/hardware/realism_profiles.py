"""
Realism profiles for biological simulation (Issue #8).

Configurable coupling strengths and mechanism interactions.
These profiles allow tuning how realistic the simulation is, trading
off between identifiability and biological fidelity.

v0.6.0: Added ER-mito coupling profile
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ERMitoCouplingProfile:
    """Profile for ER stress → mitochondrial dysfunction coupling.

    In real biology, ER stress can induce mitochondrial dysfunction via:
    - Calcium release from ER → mito calcium overload
    - ROS generation from misfolded proteins → mito damage
    - PERK/eIF2α signaling → mito biogenesis disruption

    This makes mechanism classification harder because ER stressors
    can produce secondary mito signatures.

    Attributes:
        enabled: Whether coupling is active
        coupling_k: Max amplification factor at full ER damage (default: 3.0)
        coupling_d0: Sigmoid midpoint - ER damage level where coupling activates (default: 0.3)
        coupling_slope: Sigmoid steepness (default: 8.0)
        delay_h: Delay before coupling activates (default: 0.0, immediate)
    """
    enabled: bool = True
    coupling_k: float = 3.0
    coupling_d0: float = 0.3
    coupling_slope: float = 8.0
    delay_h: float = 0.0

    def coupling_factor(self, er_damage: float) -> float:
        """Compute coupling factor from ER damage level.

        Args:
            er_damage: ER damage level (0-1)

        Returns:
            Coupling factor (1.0 = no coupling, up to 1+k = full coupling)
        """
        if not self.enabled:
            return 1.0

        import numpy as np
        sigmoid = 1.0 / (1.0 + np.exp(-self.coupling_slope * (er_damage - self.coupling_d0)))
        return 1.0 + self.coupling_k * sigmoid

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "coupling_k": self.coupling_k,
            "coupling_d0": self.coupling_d0,
            "coupling_slope": self.coupling_slope,
            "delay_h": self.delay_h,
        }


# Preset profiles

# Default: moderate coupling (current simulation default)
DEFAULT_ER_MITO_COUPLING = ERMitoCouplingProfile()

# Realistic: strong coupling (matches wet-lab observations)
REALISTIC_ER_MITO_COUPLING = ERMitoCouplingProfile(
    enabled=True,
    coupling_k=5.0,  # Stronger amplification
    coupling_d0=0.2,  # Activates earlier
    coupling_slope=10.0,  # Sharper transition
)

# Identifiable: no coupling (mechanisms are independent)
IDENTIFIABLE_ER_MITO_COUPLING = ERMitoCouplingProfile(
    enabled=False,
    coupling_k=0.0,
)

# Weak: minimal coupling for testing
WEAK_ER_MITO_COUPLING = ERMitoCouplingProfile(
    enabled=True,
    coupling_k=1.0,
    coupling_d0=0.5,
    coupling_slope=4.0,
)


@dataclass(frozen=True)
class RealismProfile:
    """Complete realism profile combining all coupling mechanisms.

    This is the top-level configuration for simulation realism.
    Higher realism = more cross-talk between mechanisms = harder classification.

    Use cases:
    - IDENTIFIABLE_PROFILE: Easy mode for agent development (mechanisms independent)
    - DEFAULT_PROFILE: Moderate difficulty (some cross-talk)
    - REALISTIC_PROFILE: Hard mode (full biological cross-talk)
    """
    name: str
    er_mito_coupling: ERMitoCouplingProfile
    # Future: add transport_mito_coupling, confluence_stress_coupling, etc.

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "er_mito_coupling": self.er_mito_coupling.to_dict(),
        }


# Preset profiles
IDENTIFIABLE_PROFILE = RealismProfile(
    name="identifiable",
    er_mito_coupling=IDENTIFIABLE_ER_MITO_COUPLING,
)

DEFAULT_PROFILE = RealismProfile(
    name="default",
    er_mito_coupling=DEFAULT_ER_MITO_COUPLING,
)

REALISTIC_PROFILE = RealismProfile(
    name="realistic",
    er_mito_coupling=REALISTIC_ER_MITO_COUPLING,
)
