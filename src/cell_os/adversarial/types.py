"""
Type definitions for adversarial plate configuration.

This module defines configuration structures and protocols for injecting
realistic technical artifacts into simulated measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Tuple
from numpy.random import Generator

from ..core.observation import RawWellResult


@dataclass
class AdversarySpec:
    """Specification for a single adversary to apply.

    Attributes:
        type: Adversary type identifier (e.g., "SpatialGradient")
        params: Adversary-specific parameters
        seed_offset: Offset added to base seed for deterministic stream derivation
    """
    type: str
    params: Dict[str, any] = field(default_factory=dict)
    seed_offset: int = 0


@dataclass
class AdversarialPlateConfig:
    """Configuration for adversarial plate feature.

    Opt-in system for injecting technical artifacts into measurements.

    Attributes:
        enabled: Whether adversarial mode is active (default: False)
        adversaries: List of adversary specifications to apply
        strength: Global multiplier for all adversary effects (default: 1.0)
        targets: Optional mapping of which measurement keys to target

    Example:
        >>> cfg = AdversarialPlateConfig(
        ...     enabled=True,
        ...     adversaries=[
        ...         AdversarySpec("SpatialGradient", {"target_channel": "morphology.nucleus"}),
        ...         AdversarySpec("EdgeEffect", {"edge_shift": -0.05}, seed_offset=1),
        ...     ],
        ...     strength=1.0
        ... )
    """
    enabled: bool = False
    adversaries: List[AdversarySpec] = field(default_factory=list)
    strength: float = 1.0
    targets: Optional[Dict[str, any]] = None


class Adversary(Protocol):
    """Protocol for adversary implementations.

    All adversaries must implement this interface to be composable.
    """

    def apply(
        self,
        wells: Tuple[RawWellResult, ...],
        rng: Generator,
        strength: float = 1.0
    ) -> Tuple[RawWellResult, ...]:
        """Apply adversarial perturbation to wells.

        Args:
            wells: Tuple of raw well results (full plate context)
            rng: Numpy random generator for deterministic sampling
            strength: Strength multiplier for this adversary

        Returns:
            Tuple of perturbed wells (same length as input)

        Invariants:
            - Output tuple length == input tuple length (no dropping wells)
            - Only readouts modified, never location/treatment/etc
            - Must be deterministic given rng state
        """
        ...


# Measurement key constants (dot notation for config, nested for storage)
MORPHOLOGY_CHANNELS = [
    "morphology.nucleus",
    "morphology.er",
    "morphology.mito",
    "morphology.actin",
    "morphology.rna",
]


def parse_measurement_key(key: str) -> Tuple[str, str]:
    """Parse dot-notation measurement key to nested path.

    Args:
        key: Dot-notation key (e.g., "morphology.nucleus")

    Returns:
        Tuple of (category, channel)

    Example:
        >>> parse_measurement_key("morphology.nucleus")
        ("morphology", "nucleus")
    """
    parts = key.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid measurement key: {key}. Expected format: 'category.channel'")
    return parts[0], parts[1]


def get_readout_value(well: RawWellResult, key: str) -> float:
    """Extract readout value using dot-notation key.

    Args:
        well: Raw well result
        key: Dot-notation key (e.g., "morphology.nucleus")

    Returns:
        Float value from readouts dict
    """
    category, channel = parse_measurement_key(key)
    return well.readouts[category][channel]


def set_readout_value(well: RawWellResult, key: str, value: float) -> RawWellResult:
    """Create new RawWellResult with modified readout value.

    Args:
        well: Original raw well result
        key: Dot-notation key (e.g., "morphology.nucleus")
        value: New value to set

    Returns:
        New RawWellResult with modified readouts (immutable update)
    """
    from dataclasses import replace

    category, channel = parse_measurement_key(key)

    # Deep copy readouts dict structure
    new_readouts = dict(well.readouts)
    new_readouts[category] = dict(new_readouts[category])
    new_readouts[category][channel] = value

    return replace(well, readouts=new_readouts)
