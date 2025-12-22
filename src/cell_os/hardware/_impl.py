"""
Shared implementation utilities for hardware module.

Contains utility functions used by both BiologicalVirtualMachine and assay simulators.
"""

import hashlib
import numpy as np


def stable_u32(s: str) -> int:
    """
    Stable deterministic hash for RNG seeding.

    Unlike Python's hash(), this is NOT salted per process, so it gives
    consistent seeds across runs and machines. Critical for reproducibility.

    Args:
        s: String to hash

    Returns:
        Unsigned 32-bit integer suitable for RNG seeding
    """
    return int.from_bytes(hashlib.blake2s(s.encode(), digest_size=4).digest(), "little")


def lognormal_multiplier(rng: np.random.Generator, cv: float) -> float:
    """
    Sample a strictly-positive multiplicative noise factor with mean=1.

    Uses lognormal distribution to guarantee positivity, unlike normal(1.0, cv)
    which can go negative for large cv.

    If X ~ lognormal(μ, σ), then E[X] = exp(μ + σ²/2).
    Setting E[X] = 1 gives μ = -σ²/2.

    Args:
        rng: Random number generator
        cv: Coefficient of variation (σ in log-space)

    Returns:
        Positive multiplicative factor with E[factor] ≈ 1
    """
    if cv <= 0:
        return 1.0
    sigma = cv
    mu = -0.5 * sigma ** 2
    return float(rng.lognormal(mean=mu, sigma=sigma))
