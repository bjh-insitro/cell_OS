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


def heavy_tail_shock(
    rng: np.random.Generator,
    nu: float,
    log_scale: float,
    p_heavy: float,
    clip_min: float,
    clip_max: float
) -> float:
    """
    Sample a rare heavy-tail multiplicative shock with hard clipping.

    This models rare lab outliers (focus drift, contamination, bubbles) that
    create fat-tailed deviations beyond lognormal. Most calls return 1.0 (no shock).
    With probability p_heavy, returns exp(Student-t) clipped to [clip_min, clip_max].

    IMPORTANT: RNG draw-count invariance enforced. This function ALWAYS draws
    two random values (u, t) regardless of whether a shock occurs. This ensures
    deterministic RNG sequence even when p_heavy varies.

    Mathematical properties:
    - Student-t has power-law tails (heavier than lognormal)
    - Exponential moment E[exp(s*T)] may not exist for Student-t
    - Hard clipping prevents infinite/astronomic multipliers
    - Median ≈ 1.0 (pre-clip), mean not guaranteed to exist

    IMPORTANT - Tails are truncated by design:
    - Clipping is part of the simulator's statistical contract
    - Raw Student-t exp(t) can be infinite; clipping makes it finite and bounded
    - This creates "bounded heavy tails" - heavier than lognormal, but capped
    - Do NOT interpret capped outliers (at clip_max) as biological signal
    - They are artifacts of the truncation, not real data

    Args:
        rng: Random number generator (must be rng_assay for observer independence)
        nu: Student-t degrees of freedom (lower = heavier tails, recommend 4.0)
        log_scale: Scale parameter for Student-t on log-space (NOT cv, recommend 0.35)
        p_heavy: Frequency of heavy-tail shocks (0.0 = dormant, 0.01 = 1%)
        clip_min: Hard floor for multiplier (e.g., 0.2 = max 5× attenuation)
        clip_max: Hard ceiling for multiplier (e.g., 5.0 = max 5× amplification)

    Returns:
        Multiplicative shock factor:
        - 1.0 with probability (1 - p_heavy) [no shock]
        - clipped exp(Student-t) with probability p_heavy [outlier]

    Example:
        >>> rng = np.random.default_rng(42)
        >>> shock = heavy_tail_shock(rng, nu=4.0, log_scale=0.35, p_heavy=0.01,
        ...                          clip_min=0.2, clip_max=5.0)
        >>> # 99% of calls return 1.0, 1% return clipped exp(t_4)
    """
    # Draw-count invariance: ALWAYS draw both u and t from RNG
    # This ensures RNG sequence is constant regardless of whether shock occurs
    u = rng.random()  # Uniform [0, 1) for mixture selection
    t = rng.standard_t(nu) * log_scale  # Student-t scaled to log-space

    if p_heavy <= 0 or u >= p_heavy:
        # No shock (most common case)
        return 1.0
    else:
        # Heavy-tail shock: exp(Student-t), clipped for safety
        shock_raw = float(np.exp(t))
        shock_clipped = float(np.clip(shock_raw, clip_min, clip_max))
        return shock_clipped
