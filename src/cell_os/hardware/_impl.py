"""
Shared implementation utilities for hardware module.

Contains utility functions used by both BiologicalVirtualMachine and assay simulators.
"""

import hashlib
import numpy as np


def stable_u32(s: str) -> int:
    """
    Stable deterministic hash for RNG seeding (32-bit).

    Unlike Python's hash(), this is NOT salted per process, so it gives
    consistent seeds across runs and machines. Critical for reproducibility.

    WARNING: 32-bit space has collision risk in large-scale calibrations.
    For high-volume seeding (e.g., calibration plates), use stable_u64() instead.

    Args:
        s: String to hash

    Returns:
        Unsigned 32-bit integer suitable for RNG seeding
    """
    return int.from_bytes(hashlib.blake2s(s.encode(), digest_size=4).digest(), "little")


def stable_u64(s: str) -> int:
    """
    Stable deterministic hash for RNG seeding (64-bit).

    Provides larger seed space than stable_u32, reducing collision risk
    in high-volume scenarios (calibration plates, large experiments).

    Args:
        s: String to hash

    Returns:
        Unsigned 64-bit integer suitable for RNG seeding
    """
    return int.from_bytes(hashlib.blake2s(s.encode(), digest_size=8).digest(), "little")


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

    Note:
        RNG draw-count invariance: This function ALWAYS consumes exactly one
        RNG draw, even when cv=0, to ensure that downstream randomness is
        independent of config parameters under the same seed.
    """
    sigma = max(cv, 1e-10)  # Avoid exactly zero to ensure draw occurs
    mu = -0.5 * sigma ** 2
    sample = float(rng.lognormal(mean=mu, sigma=sigma))

    # If cv was actually 0, return 1.0 but we already consumed the draw
    if cv <= 0:
        return 1.0
    return sample


def additive_floor_noise(rng: np.random.Generator, sigma: float) -> float:
    """
    Sample additive Gaussian read noise (detector floor).

    Returns sigma * N(0,1). If sigma=0, returns 0 without drawing from RNG.
    This is NOT draw-count invariant across configs, but preserves existing
    golden test trajectories when feature is dormant (sigma=0.0 default).

    Rationale: Real detectors (CCD/PMT) have dark current and read noise
    independent of signal magnitude. At low signal, this additive floor
    dominates SNR. At high signal, multiplicative noise dominates.

    Args:
        rng: RNG stream (must be rng_assay for observer independence)
        sigma: Read noise standard deviation (0.0 = disabled, no draw)

    Returns:
        Additive noise sample (0.0 if sigma <= 0)

    Example:
        >>> rng = np.random.default_rng(42)
        >>> noise = additive_floor_noise(rng, sigma=2.0)
        >>> # Returns ~N(0, 2.0)
    """
    if sigma <= 0:
        return 0.0
    return float(rng.normal(0.0, sigma))


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


def apply_saturation(
    y: float,
    ceiling: float,
    knee_start_frac: float,
    tau_frac: float
) -> float:
    """
    Apply detector saturation with soft knee (piecewise exponential compression).

    Models camera/PMT dynamic range limits: signal is linear at low intensities,
    compresses smoothly as it approaches the ceiling, and asymptotically saturates.
    This creates realistic plateaus in dose-response curves and reduces information
    gain at high signal.

    IMPORTANT - Detector physics (deterministic, no RNG):
    - This models photon well depth / digitizer max, NOT biological effects
    - Applied after additive floor (detector noise), before pipeline_transform (software)
    - Creates genuine dynamic range problem: agent must learn to operate instrument

    Function behavior:
    - If ceiling <= 0: disabled (returns y unchanged, golden-preserving)
    - If y <= knee_start: identity (no compression, y_sat = y exactly)
    - If y > knee_start: exponential compression toward ceiling
      - y_sat = knee_start + room * (1 - exp(-excess / tau))
      - As y → ∞, y_sat → ceiling asymptotically

    Epistemic implications:
    - High signal becomes less informative (compressed variance)
    - Dose-response plateaus at saturation (fake robustness)
    - Agent learns: "go bigger" is not always better
    - Forces calibration strategy: operate in linear regime

    Args:
        y: Input signal intensity (arbitrary units, typically 100-500 AU)
        ceiling: Maximum digitized output (0.0 = disabled/dormant)
        knee_start_frac: Fraction of ceiling where compression begins (e.g., 0.85)
        tau_frac: Compression rate as fraction of ceiling (e.g., 0.08)

    Returns:
        Saturated signal intensity in [0, ceiling]
        - y unchanged if ceiling <= 0 (dormant mode)
        - y unchanged if y <= knee_start (linear regime)
        - Compressed if y > knee_start (approaching saturation)

    Contract:
    - Monotone: y1 > y2 → y_sat(y1) >= y_sat(y2)
    - Bounded: 0 <= y_sat <= ceiling
    - Identity: y_sat(y) == y for y <= knee_start
    - Deterministic: same (y, params) → same y_sat

    Example:
        >>> apply_saturation(y=50.0, ceiling=600.0, knee_start_frac=0.85, tau_frac=0.08)
        50.0  # Below knee (0.85 * 600 = 510), identity

        >>> apply_saturation(y=800.0, ceiling=600.0, knee_start_frac=0.85, tau_frac=0.08)
        599.x  # Compressed toward ceiling

        >>> apply_saturation(y=100.0, ceiling=0.0, knee_start_frac=0.85, tau_frac=0.08)
        100.0  # Dormant mode (ceiling=0), no saturation
    """
    import math

    # Dormant mode: ceiling <= 0 means saturation disabled
    if ceiling <= 0:
        return y

    # Safety: signal should be non-negative (enforced elsewhere, but clamp here too)
    y = max(0.0, y)

    # Already at or above ceiling → hard clamp
    if y >= ceiling:
        return ceiling

    # Compute knee point (where compression begins)
    knee_start = knee_start_frac * ceiling

    # Linear regime: below knee, exact identity (no compression)
    if y <= knee_start:
        return y

    # Saturation regime: exponential compression toward ceiling
    # excess = how far above knee we are
    # room = headroom between knee and ceiling
    # tau = rate of approach (smaller = faster saturation)
    excess = y - knee_start
    room = ceiling - knee_start
    tau = max(1e-9, tau_frac * ceiling)  # Floor to avoid division by zero

    # Piecewise exponential knee: y_sat approaches ceiling asymptotically
    # As excess → ∞, exp(-excess/tau) → 0, so y_sat → knee_start + room = ceiling
    y_sat = knee_start + room * (1.0 - math.exp(-excess / tau))

    return float(y_sat)


def quantize_adc(
    y: float,
    step: float = 0.0,
    bits: int = 0,
    ceiling: float = 0.0,
    mode: str = "round_half_up"
) -> float:
    """
    Apply ADC quantization (deterministic digitization into discrete levels).

    Models analog-to-digital conversion: continuous signal → discrete codes.
    Creates visible banding at low signal and bin merging near saturation.
    Removes fake precision, forces agents to operate in information-rich regime.

    IMPORTANT - Detector electronics (deterministic, no RNG):
    - This models ADC bit depth / digitizer quantization, NOT biological effects
    - Applied after saturation (analog), before pipeline_transform (software)
    - Removes arbitrarily fine decimal precision that doesn't exist in real detectors
    - Creates dead zones where small signal changes don't change digitized output

    Quantization modes (priority order):
    1. If bits > 0 and ceiling > 0: Derive step = ceiling / (2^bits - 1)
       - Realistic: "12-bit ADC with 800 AU full scale"
       - If bits > 0 but ceiling <= 0: RAISES ValueError (explicit contract violation)
    2. If step > 0: Use explicit step size
       - Direct control: "quantize to 0.5 AU bins"
    3. Otherwise: No-op (dormant mode, golden-preserving)

    Rounding: "round_half_up" (default)
    - Uses floor(y/step + 0.5) * step (NOT Python round() banker's rounding)
    - Symmetric, predictable, matches most ADC behavior

    Epistemic implications:
    - Low signal shows visible banding (coarse steps)
    - Near saturation shows bin merging (many inputs → same code)
    - Plateaus where agent nudges signal but output unchanged
    - Forces recognition of digitization limits

    Args:
        y: Input signal intensity (arbitrary units, after saturation)
        step: Explicit quantization step size (0.0 = dormant)
        bits: ADC bit depth (0 = dormant, requires ceiling > 0)
        ceiling: Analog full scale (needed for bits-mode, typically from saturation)
        mode: Rounding mode ("round_half_up" only supported currently)

    Returns:
        Quantized signal intensity
        - y unchanged if both step=0.0 and bits=0 (dormant mode)
        - Quantized to nearest step if step > 0
        - Quantized to 2^bits codes if bits > 0 and ceiling > 0

    Contract:
    - Monotone: y1 > y2 → y_q(y1) >= y_q(y2) (preserves order within float precision)
    - Idempotent: quantize(quantize(y)) == quantize(y)
    - Bounded: 0 <= y_q <= ceiling (if ceiling provided)
    - Deterministic: same (y, params) → same y_q

    Raises:
        ValueError: If bits > 0 but ceiling <= 0 (must provide analog full scale for bits-mode)
        ValueError: If mode is not "round_half_up"

    Example:
        >>> quantize_adc(y=10.3, step=0.5)
        10.5  # Nearest 0.5 AU step

        >>> quantize_adc(y=800.0, bits=8, ceiling=800.0)
        800.0  # 8-bit (255 codes), step=800/255=3.14, maps to ceiling

        >>> quantize_adc(y=100.0, step=0.0, bits=0)
        100.0  # Dormant mode, no quantization

        >>> quantize_adc(y=10.0, bits=12, ceiling=0.0)
        ValueError: bits-mode requires ceiling > 0
    """
    import math

    # Validate mode
    if mode != "round_half_up":
        raise ValueError(f"Unsupported quantization mode: {mode}. Only 'round_half_up' supported.")

    # Determine effective step (priority: bits-mode > explicit step > dormant)
    effective_step = 0.0

    if bits > 0:
        # Bits-mode: derive step from ceiling
        if ceiling <= 0:
            raise ValueError(
                f"ADC quantization with bits={bits} requires ceiling > 0 (analog full scale). "
                f"Got ceiling={ceiling}. Enable saturation on this channel or use explicit step instead."
            )
        # Derive step: ceiling / (2^bits - 1)
        # Example: 8-bit (255 codes), ceiling=800 → step = 800/255 ≈ 3.14 AU
        num_codes = (1 << bits) - 1  # 2^bits - 1
        effective_step = ceiling / max(num_codes, 1)

    elif step > 0:
        # Explicit step mode
        effective_step = step
        # If ceiling provided, use it for clamping (even in step mode)
        # This ensures quantization doesn't create values > ceiling

    else:
        # Dormant mode: both bits=0 and step=0.0
        return y

    # Defensive clamp to [0, ceiling] before quantization
    if ceiling > 0:
        y = max(0.0, min(y, ceiling))
    else:
        y = max(0.0, y)  # At least ensure non-negative

    # Quantize using round_half_up: floor(y/step + 0.5) * step
    # This avoids Python round() banker's rounding (ties to even)
    k = math.floor(y / effective_step + 0.5)
    y_q = k * effective_step

    # Final clamp to ceiling (defensive, prevents float rounding from exceeding ceiling)
    if ceiling > 0:
        y_q = min(y_q, ceiling)

    return float(y_q)
