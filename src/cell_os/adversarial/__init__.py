"""
Adversarial Plates: Inject realistic technical artifacts into simulated measurements.

This module provides a drop-in system for testing whether QC and detection systems
can identify structured technical artifacts that masquerade as biology.

Design principles:
- Opt-in and default-off
- Deterministic given seed
- Preserves measurement-purity (no mutation of biological state)
- Pluggable (stack multiple adversaries)

Usage:
    from cell_os.adversarial import AdversarialPlateConfig, AdversarySpec, apply_adversaries

    cfg = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {"target_channel": "morphology.nucleus", "strength": 0.1}),
            AdversarySpec("EdgeEffect", {"edge_shift": -0.05}, seed_offset=1),
        ],
        strength=1.0
    )

    # After producing raw_wells, apply adversaries:
    perturbed_wells = apply_adversaries(raw_wells, cfg, base_seed)
"""

from .types import AdversarialPlateConfig, AdversarySpec, Adversary
from .apply import apply_adversaries
from .adversaries import (
    SpatialGradientAdversary,
    EdgeEffectAdversary,
    BatchAlignedShiftAdversary,
    WashLossCorrelationAdversary,
)
from .registry import register_adversary, list_adversaries

__all__ = [
    "AdversarialPlateConfig",
    "AdversarySpec",
    "Adversary",
    "apply_adversaries",
    "SpatialGradientAdversary",
    "EdgeEffectAdversary",
    "BatchAlignedShiftAdversary",
    "WashLossCorrelationAdversary",
    "register_adversary",
    "list_adversaries",
]
