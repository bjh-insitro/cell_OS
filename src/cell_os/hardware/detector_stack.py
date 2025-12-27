"""
Detector Stack Simulator

Shared detector simulation for Cell Painting and calibration materials.
Applies realistic detector artifacts in correct order:

1. Exposure multiplier (agent-controlled photon collection)
2. Additive floor (detector read noise)
3. Saturation (dynamic range limits)
4. Quantization (ADC digitization)

This module is detector-only (no biology). Inputs are already-scaled signals
(viability-attenuated biology OR material intensities).
"""

import numpy as np
from typing import Dict, Any, TYPE_CHECKING

from ._impl import additive_floor_noise, apply_saturation, quantize_adc

if TYPE_CHECKING:
    from .biological_virtual import BiologicalVirtualMachine


def apply_detector_stack(
    signal: Dict[str, float],
    detector_params: Dict[str, Any],
    rng_detector: np.random.Generator,
    exposure_multiplier: float = 1.0,
    well_position: str = "H12",
    plate_format: int = 384,
    enable_vignette: bool = True,
    enable_pipeline: bool = True,
    enable_detector_bias: bool = False
) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    Apply detector stack to signal (works for both cells and materials).

    Pipeline:
    0. Detector baseline offset (bias + dark current, if enabled)
    1. Exposure multiplier (agent-controlled photon collection)
    2. Additive floor (detector read noise, stochastic)
    3. Saturation (analog dynamic range limits, deterministic)
    4. Quantization (ADC digitization, deterministic)
    5. Pipeline drift (digital post-processing, if enabled)

    NO VM COUPLING: Takes explicit detector params + dedicated RNG.
    NO KWARGS: All parameters explicit (prevents coupling creep).

    Args:
        signal: Per-channel signal dict {er: float, mito: float, ...}
        detector_params: Detector configuration dict (technical_noise params)
        rng_detector: Dedicated RNG for detector noise (NOT shared with biology)
        exposure_multiplier: Photon collection time multiplier (default 1.0)
        well_position: Well ID for spatial effects (default "H12")
        plate_format: Plate format for vignette (default 384)
        enable_vignette: Apply spatial vignette (default True)
        enable_pipeline: Apply digital pipeline transform (default True)
        enable_detector_bias: Add detector baseline offset (default False, optical_material only)

    Returns:
        tuple: (measured_signal, detector_metadata)
            measured_signal: signal after detector stack
            detector_metadata: {
                'is_saturated': {ch: bool},
                'is_quantized': {ch: bool},
                'quant_step': {ch: float},
                'snr_floor_proxy': {ch: float or None},
                'exposure_multiplier': float
            }
    """
    # Make a copy to avoid mutating input
    morph = signal.copy()

    tech_noise = detector_params  # Explicit params, not VM state
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    # 0. Detector baseline offset (bias + dark current)
    # Applied BEFORE exposure (bias is independent of photon collection time)
    # Only enabled for optical_material mode (enable_detector_bias=True)
    # This fixes DARK floor observability by giving DARK wells a positive baseline
    if enable_detector_bias:
        # Compute quant_step_param per channel (same logic as _apply_quantization_step)
        bits_default = int(tech_noise.get('adc_quant_bits_default', 0))
        step_default = float(tech_noise.get('adc_quant_step_default', 0.0))

        for ch in channels:
            # Get per-channel quant params (fall back to defaults)
            bits = int(tech_noise.get(f'adc_quant_bits_{ch}', bits_default))
            step = float(tech_noise.get(f'adc_quant_step_{ch}', step_default))
            ceiling = float(tech_noise.get(f'saturation_ceiling_{ch}', 0.0))

            # Compute effective quant step (same logic as quantize_adc)
            quant_step_param = 0.0
            if bits > 0:
                if ceiling > 0:
                    num_codes = (1 << bits) - 1
                    quant_step_param = ceiling / max(num_codes, 1)
            elif step > 0:
                quant_step_param = step

            # Compute bias: prefer explicit bias, else LSB-scaled, else fallback
            bias = tech_noise.get(f'detector_bias_{ch}', None)
            if bias is None:
                # Use dark_bias_lsbs (default 20) scaled by quant step
                dark_bias_lsbs = float(tech_noise.get('dark_bias_lsbs', 20.0))
                if quant_step_param > 0:
                    bias = dark_bias_lsbs * quant_step_param
                else:
                    # Quantization disabled, use AU fallback
                    bias = 0.3  # 0.3 AU fallback when quant disabled

            # Apply bias
            morph[ch] += bias

    # 1. Exposure multiplier (scales signal strength before detector)
    # Agent-controlled: trade-off between SNR (floor-limited) and saturation
    if exposure_multiplier != 1.0:
        for channel in morph:
            morph[channel] *= exposure_multiplier

    # 2. Additive floor (detector read noise)
    # Applied BEFORE saturation and quantization
    # Uses dedicated detector RNG (NOT shared with biology)
    sigmas = {ch: tech_noise.get(f'additive_floor_sigma_{ch}', 0.0) for ch in channels}

    if any(s > 0 for s in sigmas.values()):
        for ch in channels:
            sigma = sigmas[ch]
            if sigma > 0:
                noise = additive_floor_noise(rng_detector, sigma)
                morph[ch] = max(0.0, morph[ch] + noise)

    # Compute SNR floor proxy (signal / sigma_floor) after additive floor
    # This is the signal level relative to detector noise floor
    snr_floor_proxy = {}
    for ch in channels:
        sigma = tech_noise.get(f'additive_floor_sigma_{ch}', 0.0)
        if sigma > 0:
            snr_floor_proxy[ch] = morph[ch] / sigma
        else:
            snr_floor_proxy[ch] = None  # No floor, SNR undefined

    # 3. Saturation (detector dynamic range limits)
    # Applied AFTER additive floor (noise can push into saturation),
    # BEFORE quantization (analog compression before digitization)
    morph, is_saturated = _apply_saturation_step(morph, tech_noise)

    # 4. ADC quantization (analog-to-digital conversion)
    # Applied AFTER saturation (analog → digital),
    # deterministic (no RNG)
    morph, quant_step, is_quantized = _apply_quantization_step(morph, tech_noise)

    # Assemble detector metadata
    detector_metadata = {
        'is_saturated': is_saturated,
        'is_quantized': is_quantized,
        'quant_step': quant_step,
        'snr_floor_proxy': snr_floor_proxy,
        'exposure_multiplier': exposure_multiplier,
    }

    return morph, detector_metadata


def _apply_saturation_step(
    morph: Dict[str, float],
    tech_noise: Dict[str, Any]
) -> tuple[Dict[str, float], Dict[str, bool]]:
    """
    Apply detector saturation (dynamic range limits).

    Deterministic (no RNG): Detector physics, not randomness.
    Golden-preserving: Dormant when all ceilings <= 0.
    """
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    # Shared soft-knee parameters (apply to all channels)
    knee_start_frac = tech_noise.get('saturation_knee_start_fraction', 0.85)
    tau_frac = tech_noise.get('saturation_tau_fraction', 0.08)

    # Apply per-channel saturation (independent ceilings)
    is_saturated = {}
    for ch in channels:
        ceiling = tech_noise.get(f'saturation_ceiling_{ch}', 0.0)
        if ceiling > 0:  # Only apply if enabled for this channel
            y_pre = morph[ch]
            y_sat = apply_saturation(
                y=y_pre,
                ceiling=ceiling,
                knee_start_frac=knee_start_frac,
                tau_frac=tau_frac
            )
            morph[ch] = y_sat
            # Mark as saturated if within epsilon of ceiling
            is_saturated[ch] = (y_sat >= ceiling - 0.001)
        else:
            is_saturated[ch] = False

    return morph, is_saturated


def _apply_quantization_step(
    morph: Dict[str, float],
    tech_noise: Dict[str, Any]
) -> tuple[Dict[str, float], Dict[str, float], Dict[str, bool]]:
    """
    Apply ADC quantization (analog-to-digital conversion).

    Deterministic (no RNG): ADC conversion is electronics, not randomness.
    Golden-preserving: Dormant when all bits=0 and step=0.0.
    """
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    # Shared defaults
    bits_default = int(tech_noise.get('adc_quant_bits_default', 0))
    step_default = float(tech_noise.get('adc_quant_step_default', 0.0))
    mode = tech_noise.get('adc_quant_rounding_mode', 'round_half_up')

    # Apply per-channel quantization
    quant_step = {}
    is_quantized = {}

    for ch in channels:
        # Per-channel overrides (fall back to defaults)
        bits = int(tech_noise.get(f'adc_quant_bits_{ch}', bits_default))
        step = float(tech_noise.get(f'adc_quant_step_{ch}', step_default))

        # Get ceiling from saturation config (needed for bits-mode)
        ceiling = float(tech_noise.get(f'saturation_ceiling_{ch}', 0.0))

        # Determine effective step (same logic as quantize_adc)
        effective_step = 0.0
        if bits > 0:
            if ceiling > 0:
                num_codes = (1 << bits) - 1
                effective_step = ceiling / max(num_codes, 1)
        elif step > 0:
            effective_step = step

        # Apply quantization (dormant if bits=0 and step=0.0)
        if bits > 0 or step > 0:
            morph[ch] = quantize_adc(
                y=morph[ch],
                step=step,
                bits=bits,
                ceiling=ceiling,
                mode=mode
            )
            is_quantized[ch] = True
            quant_step[ch] = effective_step
        else:
            is_quantized[ch] = False
            quant_step[ch] = 0.0

    return morph, quant_step, is_quantized
