"""
Adversary application orchestration.

This module coordinates the application of multiple adversaries to a plate,
ensuring deterministic RNG streams and proper composition.
"""

from typing import Tuple, Optional
import numpy as np
import hashlib

from ..core.observation import RawWellResult
from .types import AdversarialPlateConfig
from .registry import get_adversary


def derive_rng_seed(base_seed: int, plate_id: str, adversary_index: int, seed_offset: int) -> int:
    """Derive deterministic RNG seed for an adversary.

    Args:
        base_seed: World's base RNG seed
        plate_id: Plate identifier
        adversary_index: Index of adversary in config list
        seed_offset: Additional offset from adversary spec

    Returns:
        Deterministic integer seed

    Design:
        Uses hash of (base_seed, plate_id, adversary_index, seed_offset) to
        create independent RNG streams for each adversary on each plate.
    """
    # Create deterministic hash
    combined = f"{base_seed}_{plate_id}_{adversary_index}_{seed_offset}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    # Convert first 8 bytes to int
    seed = int.from_bytes(hash_bytes[:8], byteorder='big') % (2**31)
    return seed


def apply_adversaries(
    wells: Tuple[RawWellResult, ...],
    config: Optional[AdversarialPlateConfig],
    base_seed: int,
    plate_id: Optional[str] = None
) -> Tuple[RawWellResult, ...]:
    """Apply adversarial perturbations to raw well results.

    This is the main entry point for adversarial plate injection.
    Called from world.py:run_experiment() after _simulate_wells().

    Args:
        wells: Tuple of raw well results (full plate)
        config: Adversarial plate configuration (None = disabled)
        base_seed: Base RNG seed for deterministic stream derivation
        plate_id: Plate identifier for RNG derivation (uses first well if None)

    Returns:
        Tuple of perturbed wells (same length as input, or unchanged if disabled)

    Invariants:
        - If config is None or disabled, returns wells unchanged
        - Output tuple length == input tuple length
        - Deterministic given config and base_seed
        - No wells dropped, no wells added
    """
    # Fast path: disabled or empty
    if not config or not config.enabled or not wells:
        return wells

    # Derive plate_id if not provided
    if plate_id is None and wells:
        plate_id = wells[0].location.plate_id

    # Apply adversaries in sequence
    current_wells = wells
    for idx, adversary_spec in enumerate(config.adversaries):
        # Derive deterministic RNG for this adversary
        seed = derive_rng_seed(base_seed, plate_id or "unknown", idx, adversary_spec.seed_offset)
        rng = np.random.default_rng(seed)

        # Get adversary instance
        adversary = get_adversary(adversary_spec)

        # Apply with global strength multiplier
        current_wells = adversary.apply(current_wells, rng, strength=config.strength)

        # Sanity check: well count must not change
        if len(current_wells) != len(wells):
            raise RuntimeError(
                f"Adversary {adversary_spec.type} violated invariant: "
                f"changed well count from {len(wells)} to {len(current_wells)}"
            )

    return current_wells
