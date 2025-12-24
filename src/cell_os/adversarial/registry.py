"""
Adversary registry and factory.

This module provides a registry of available adversaries and factory
functions for instantiating them from configuration.
"""

from typing import Dict, Type, Any
from .types import AdversarySpec, Adversary
from .adversaries import (
    SpatialGradientAdversary,
    EdgeEffectAdversary,
    BatchAlignedShiftAdversary,
    WashLossCorrelationAdversary,
)


# Registry mapping type strings to adversary classes
ADVERSARY_REGISTRY: Dict[str, Type[Any]] = {
    "SpatialGradient": SpatialGradientAdversary,
    "EdgeEffect": EdgeEffectAdversary,
    "BatchAlignedShift": BatchAlignedShiftAdversary,
    "WashLossCorrelation": WashLossCorrelationAdversary,
}


def get_adversary(spec: AdversarySpec) -> Adversary:
    """Instantiate an adversary from specification.

    Args:
        spec: Adversary specification with type and params

    Returns:
        Adversary instance

    Raises:
        ValueError: If adversary type not found in registry

    Example:
        >>> spec = AdversarySpec("SpatialGradient", {"strength": 0.15})
        >>> adv = get_adversary(spec)
        >>> isinstance(adv, SpatialGradientAdversary)
        True
    """
    if spec.type not in ADVERSARY_REGISTRY:
        raise ValueError(
            f"Unknown adversary type: {spec.type}. "
            f"Available types: {list(ADVERSARY_REGISTRY.keys())}"
        )

    adversary_class = ADVERSARY_REGISTRY[spec.type]

    # Instantiate with params (uses dataclass defaults for missing params)
    try:
        adversary = adversary_class(**spec.params)
    except TypeError as e:
        raise ValueError(
            f"Invalid parameters for adversary {spec.type}: {e}. "
            f"Provided params: {spec.params}"
        ) from e

    return adversary


def register_adversary(type_name: str, adversary_class: Type[Any]) -> None:
    """Register a custom adversary type.

    This allows external modules to extend the adversary system.

    Args:
        type_name: String identifier for adversary type
        adversary_class: Adversary class (must implement Adversary protocol)

    Example:
        >>> class CustomAdversary:
        ...     def apply(self, wells, rng, strength=1.0):
        ...         return wells
        >>> register_adversary("Custom", CustomAdversary)
    """
    ADVERSARY_REGISTRY[type_name] = adversary_class


def list_adversaries() -> Dict[str, Type[Any]]:
    """Get dict of all registered adversary types.

    Returns:
        Dict mapping type names to adversary classes
    """
    return dict(ADVERSARY_REGISTRY)
