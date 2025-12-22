"""
Measurement Overrides: Apply non-biological provocations to assay readouts

This module provides functions to apply measurement-level perturbations
(stain_scale, focus_offset, fixation_timing_offset) to morphology measurements.

These are applied AFTER biological effects but BEFORE final readout,
simulating real measurement artifacts that affect calibration plates.
"""

from typing import Dict, Optional
import numpy as np


def apply_stain_scale(morphology: Dict[str, float], stain_scale: float) -> Dict[str, float]:
    """
    Apply stain intensity scaling to morphology measurements.

    Args:
        morphology: Channel intensities
        stain_scale: Multiplicative factor (1.0 = nominal, >1.0 = brighter)

    Returns:
        Scaled morphology
    """
    return {ch: val * stain_scale for ch, val in morphology.items()}


def apply_focus_offset(
    morphology: Dict[str, float],
    focus_offset_um: float,
    rng: np.random.Generator
) -> Dict[str, float]:
    """
    Apply focus-dependent signal attenuation and noise.

    Out-of-focus imaging reduces signal and increases noise.

    Args:
        morphology: Channel intensities
        focus_offset_um: Defocus amount (positive or negative)
        rng: Random number generator

    Returns:
        Degraded morphology
    """
    if focus_offset_um == 0:
        return morphology

    # Attenuation: signal drops with |defocus|
    # Model: exp(-|offset| / characteristic_length)
    attenuation = np.exp(-abs(focus_offset_um) / 3.0)  # 3µm characteristic length

    # Blur increases noise (reduces SNR)
    noise_inflation = 1.0 + 0.15 * abs(focus_offset_um)  # 15% per µm

    result = {}
    for ch, val in morphology.items():
        # Apply attenuation
        attenuated = val * attenuation

        # Add extra noise
        noise = rng.normal(1.0, 0.02 * noise_inflation)
        result[ch] = max(0.0, attenuated * noise)

    return result


def apply_fixation_timing_offset(
    morphology: Dict[str, float],
    fixation_offset_min: float,
    rng: np.random.Generator
) -> Dict[str, float]:
    """
    Apply fixation timing artifacts to morphology.

    Early fixation: cells not fully equilibrated, higher variance
    Late fixation: some morphology changes, potential degradation

    Args:
        morphology: Channel intensities
        fixation_offset_min: Timing offset in minutes (±15 typical)
        rng: Random number generator

    Returns:
        Perturbed morphology
    """
    if fixation_offset_min == 0:
        return morphology

    # Timing offset introduces:
    # 1. Systematic shift (directional bias)
    # 2. Increased variance (timing uncertainty)

    # Systematic effects (channel-specific)
    # Early fixation (-): ER/nucleus higher (incomplete extraction)
    # Late fixation (+): RNA/mito lower (degradation)
    bias_factors = {
        'er': 1.0 + 0.01 * fixation_offset_min,      # +1% per minute late
        'mito': 1.0 - 0.008 * fixation_offset_min,   # -0.8% per minute late
        'nucleus': 1.0 + 0.005 * fixation_offset_min,
        'actin': 1.0 - 0.003 * fixation_offset_min,
        'rna': 1.0 - 0.015 * fixation_offset_min     # Most sensitive
    }

    # Variance inflation (timing jitter)
    variance_inflation = 1.0 + 0.02 * abs(fixation_offset_min)  # 2% per minute

    result = {}
    for ch, val in morphology.items():
        # Apply systematic bias
        biased = val * bias_factors.get(ch, 1.0)

        # Add timing noise
        noise = rng.normal(1.0, 0.02 * variance_inflation)
        result[ch] = max(0.0, biased * noise)

    return result


def apply_measurement_overrides(
    morphology: Dict[str, float],
    stain_scale: float = 1.0,
    focus_offset_um: float = 0.0,
    fixation_offset_min: float = 0.0,
    rng: Optional[np.random.Generator] = None
) -> Dict[str, float]:
    """
    Apply all measurement overrides in order.

    Order: stain → focus → fixation (matches physical causality)

    Args:
        morphology: Raw morphology from biological model
        stain_scale: Stain intensity multiplier
        focus_offset_um: Focus offset (µm)
        fixation_offset_min: Fixation timing offset (minutes)
        rng: Random number generator (required if focus or fixation offsets nonzero)

    Returns:
        Final observed morphology after measurement artifacts
    """
    if rng is None:
        rng = np.random.default_rng()

    # Apply in order
    result = apply_stain_scale(morphology, stain_scale)
    result = apply_focus_offset(result, focus_offset_um, rng)
    result = apply_fixation_timing_offset(result, fixation_offset_min, rng)

    return result
