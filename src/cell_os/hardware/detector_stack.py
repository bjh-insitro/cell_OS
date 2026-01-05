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
from typing import Dict, Any, TYPE_CHECKING, Tuple, Optional

from ._impl import additive_floor_noise, apply_saturation, quantize_adc

if TYPE_CHECKING:
    from .biological_virtual import BiologicalVirtualMachine


def _parse_well_position(well_position: str) -> Tuple[int, int]:
    """
    Parse well position string (e.g., 'A1', 'H12') to (row, col) indices.

    Args:
        well_position: Well ID like 'A1', 'H12'

    Returns:
        (row, col) as 0-indexed integers, or (7, 7) for non-standard positions
    """
    # Handle non-standard positions (e.g., "test", "ctrl", numeric IDs)
    if not well_position or len(well_position) < 2:
        return 7, 7  # Default to center-ish position

    first_char = well_position[0].upper()
    if not first_char.isalpha() or first_char < 'A' or first_char > 'P':
        return 7, 7  # Not a valid row letter

    col_str = well_position[1:]
    if not col_str.isdigit():
        return 7, 7  # Not a valid column number

    row = ord(first_char) - ord('A')
    col = int(col_str) - 1
    return row, col


def _compute_edge_distance(row: int, col: int, plate_format: int) -> float:
    """
    Compute continuous distance from plate center (0.0 = center, 1.0 = edge).

    Pure geometric function - no RNG, fully deterministic from position.

    Args:
        row: Row index (0-indexed)
        col: Col index (0-indexed)
        plate_format: 96 or 384

    Returns:
        edge_distance: 0.0 at center, 1.0 at furthest edge
    """
    # Plate dimensions
    if plate_format == 384:
        n_rows, n_cols = 16, 24
    elif plate_format == 96:
        n_rows, n_cols = 8, 12
    else:
        raise ValueError(f"Unsupported plate format: {plate_format}")

    # Normalized position (0.0 = first row/col, 1.0 = last row/col)
    row_frac = row / (n_rows - 1) if n_rows > 1 else 0.5
    col_frac = col / (n_cols - 1) if n_cols > 1 else 0.5

    # Distance from center (Euclidean)
    center_row, center_col = 0.5, 0.5
    dist = np.sqrt((row_frac - center_row)**2 + (col_frac - center_col)**2)

    # Normalize to [0, 1] (max distance is corner to center)
    max_dist = np.sqrt(0.5**2 + 0.5**2)
    edge_distance = float(dist / max_dist)

    return edge_distance


def _apply_position_effects(
    signal: Dict[str, float],
    row: int,
    col: int,
    plate_format: int,
    realism_config: Dict[str, float]
) -> Tuple[Dict[str, float], float]:
    """
    Apply position-dependent effects (row/col gradients + edge effects).

    Pure geometric function - no RNG, fully deterministic from position.
    Effects model illumination gradients, evaporation, temperature drift.

    Args:
        signal: Per-channel signal dict
        row: Row index (0-indexed)
        col: Col index (0-indexed)
        plate_format: 96 or 384
        realism_config: Config dict with position_row_bias_pct, position_col_bias_pct, edge_mean_shift_pct

    Returns:
        (modified_signal, edge_distance)
    """
    # Extract config params (default to no effect)
    row_bias_pct = realism_config.get('position_row_bias_pct', 0.0)
    col_bias_pct = realism_config.get('position_col_bias_pct', 0.0)
    edge_shift_pct = realism_config.get('edge_mean_shift_pct', 0.0)

    # Early exit if all effects disabled
    if row_bias_pct == 0.0 and col_bias_pct == 0.0 and edge_shift_pct == 0.0:
        edge_distance = _compute_edge_distance(row, col, plate_format)
        return signal, edge_distance

    # Plate dimensions
    if plate_format == 384:
        n_rows, n_cols = 16, 24
    elif plate_format == 96:
        n_rows, n_cols = 8, 12
    else:
        n_rows, n_cols = 8, 12  # Fallback

    # Normalized position fractions
    row_frac = row / (n_rows - 1) if n_rows > 1 else 0.5
    col_frac = col / (n_cols - 1) if n_cols > 1 else 0.5

    # Row gradient: sinusoidal from top to bottom (±bias at extremes)
    # sin(π * x) gives 0 at edges, 1 at center → shift to ±1 at edges
    row_gradient = np.sin(np.pi * row_frac) * (row_bias_pct / 100.0)

    # Col gradient: sinusoidal from left to right
    col_gradient = np.sin(np.pi * col_frac) * (col_bias_pct / 100.0)

    # Edge distance (continuous)
    edge_distance = _compute_edge_distance(row, col, plate_format)

    # Edge mean shift (linear with distance, e.g., -5% at edge)
    edge_shift = edge_distance * (edge_shift_pct / 100.0)

    # Combined multiplicative factor
    total_shift = 1.0 + row_gradient + col_gradient + edge_shift

    # Apply to all channels
    modified_signal = {ch: val * total_shift for ch, val in signal.items()}

    return modified_signal, edge_distance


def _create_qc_rng(run_seed: int, well_position: str) -> np.random.Generator:
    """
    Create dedicated RNG for QC pathologies.

    Seeded from (run_seed, "qc_pathology", well_position) for determinism.
    NEVER reuse biology or detector RNG streams.

    Args:
        run_seed: Run seed for reproducibility
        well_position: Well ID (e.g., 'A1', 'H12')

    Returns:
        Dedicated RNG for QC pathology sampling
    """
    import hashlib

    # Stable hash from (run_seed, "qc_pathology", well_position)
    hash_input = f"{run_seed}_qc_pathology_{well_position}".encode()
    hash_bytes = hashlib.blake2s(hash_input, digest_size=4).digest()
    qc_seed = int.from_bytes(hash_bytes, byteorder='little')

    return np.random.default_rng(qc_seed)


def _apply_qc_pathologies(
    signal: Dict[str, float],
    well_position: str,
    run_seed: int,
    realism_config: Dict[str, float]
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Apply QC pathologies (outliers, instrument failures).

    Dedicated RNG ensures determinism + isolation from biology/detector noise.
    Pathologies model: channel dropout, focus miss, noise spike.

    Applied BEFORE quantization (hardware-realistic, not post-processing fake).

    Args:
        signal: Per-channel signal dict (after saturation, before quantization)
        well_position: Well ID for RNG seeding
        run_seed: Run seed for reproducibility
        realism_config: Config dict with outlier_rate

    Returns:
        (modified_signal, qc_flags)
        qc_flags: {'is_outlier': bool, 'pathology_type': str, 'affected_channel': str}
    """
    outlier_rate = realism_config.get('outlier_rate', 0.0)

    # Early exit if outliers disabled
    if outlier_rate <= 0.0:
        return signal, {'is_outlier': False, 'pathology_type': None, 'affected_channel': None}

    # Create dedicated RNG
    rng_qc = _create_qc_rng(run_seed, well_position)

    # Sample whether this well is an outlier
    is_outlier = rng_qc.random() < outlier_rate

    if not is_outlier:
        return signal, {'is_outlier': False, 'pathology_type': None, 'affected_channel': None}

    # Pick pathology type (equal probability)
    pathology_type = rng_qc.choice(['channel_dropout', 'focus_miss', 'noise_spike'])

    modified_signal = signal.copy()
    affected_channel = None

    if pathology_type == 'channel_dropout':
        # One channel fails (laser off, filter stuck, PMT dead)
        affected_channel = rng_qc.choice(['er', 'mito', 'nucleus', 'actin', 'rna'])
        modified_signal[affected_channel] *= 0.1  # 90% signal loss

    elif pathology_type == 'focus_miss':
        # All channels attenuated (focus drifted, z-height wrong)
        focus_attenuation = 0.7
        for ch in modified_signal:
            modified_signal[ch] *= focus_attenuation
        affected_channel = 'all'

    elif pathology_type == 'noise_spike':
        # One channel gets noise spike (electrical transient, stray light)
        affected_channel = rng_qc.choice(['er', 'mito', 'nucleus', 'actin', 'rna'])
        # Add +15% spike (additive, not multiplicative, to model transient)
        baseline = signal[affected_channel]
        spike_magnitude = 0.15 * baseline
        modified_signal[affected_channel] += spike_magnitude

    qc_flags = {
        'is_outlier': True,
        'pathology_type': pathology_type,
        'affected_channel': affected_channel
    }

    return modified_signal, qc_flags


def apply_detector_stack(
    signal: Dict[str, float],
    detector_params: Dict[str, Any],
    rng_detector: np.random.Generator,
    exposure_multiplier: float = 1.0,
    well_position: str = "H12",
    plate_format: int = 384,
    enable_vignette: bool = True,
    enable_pipeline: bool = True,
    enable_detector_bias: bool = False,
    run_seed: int = 0,
    realism_config: Optional[Dict[str, float]] = None
) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    Apply detector stack to signal (works for both cells and materials).

    Pipeline (v7: realism layers added):
    0. Position effects (row/col gradients, edge mean shift) [v7, Cell Painting only]
    1. Detector baseline offset (bias + dark current, if enabled)
    2. Exposure multiplier (agent-controlled photon collection)
    3. Additive floor (detector read noise, stochastic, edge-inflated) [v7]
    4. Saturation (analog dynamic range limits, deterministic)
    5. QC pathologies (channel dropout, focus miss, noise spike) [v7, before quantization]
    6. Quantization (ADC digitization, deterministic)
    7. Pipeline drift (digital post-processing, if enabled)

    NO VM COUPLING: Takes explicit detector params + dedicated RNG.
    NO KWARGS: All parameters explicit (prevents coupling creep).

    v7 Realism layers (gated by realism_config):
    - Position effects: pure geometric (no RNG), row/col gradients + edge dimming
    - Edge noise inflation: detector noise scales with edge_distance
    - QC pathologies: dedicated RNG (run_seed + well_position), applied pre-quantization

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
        run_seed: Run seed for QC pathology RNG (v7, default 0)
        realism_config: Realism layer config (v7, default None = clean profile)

    Returns:
        tuple: (measured_signal, detector_metadata)
            measured_signal: signal after detector stack
            detector_metadata: {
                'is_saturated': {ch: bool},
                'is_quantized': {ch: bool},
                'quant_step': {ch: float},
                'snr_floor_proxy': {ch: float or None},
                'exposure_multiplier': float,
                'edge_distance': float [v7],
                'qc_flags': dict [v7]
            }
    """
    # Make a copy to avoid mutating input
    morph = signal.copy()

    tech_noise = detector_params  # Explicit params, not VM state
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    # v7: Initialize realism config (default to clean profile)
    if realism_config is None:
        realism_config = {
            'position_row_bias_pct': 0.0,
            'position_col_bias_pct': 0.0,
            'edge_mean_shift_pct': 0.0,
            'edge_noise_multiplier': 1.0,
            'outlier_rate': 0.0,
        }

    # 0. Position effects (v7: row/col gradients, edge mean shift)
    # Pure geometric, no RNG, fully deterministic from position
    # Applied first to model illumination gradients and evaporation
    # ONLY for Cell Painting (calibration materials should skip this)
    row, col = _parse_well_position(well_position)
    morph, edge_distance = _apply_position_effects(
        morph, row, col, plate_format, realism_config
    )

    # 1. Detector baseline offset (bias + dark current)
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

    # 2. Exposure multiplier (scales signal strength before detector)
    # Agent-controlled: trade-off between SNR (floor-limited) and saturation
    if exposure_multiplier != 1.0:
        for channel in morph:
            morph[channel] *= exposure_multiplier

    # 3. Additive floor (detector read noise, v7: edge-inflated)
    # Applied BEFORE saturation and quantization
    # Uses dedicated detector RNG (NOT shared with biology)
    # v7: Noise sigma inflated at edges (heteroscedastic noise)
    edge_noise_mult = realism_config.get('edge_noise_multiplier', 1.0)
    edge_noise_factor = 1.0 + (edge_noise_mult - 1.0) * edge_distance

    sigmas = {ch: tech_noise.get(f'additive_floor_sigma_{ch}', 0.0) for ch in channels}

    if any(s > 0 for s in sigmas.values()):
        for ch in channels:
            sigma = sigmas[ch] * edge_noise_factor  # v7: Edge inflation
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

    # 4. Saturation (detector dynamic range limits)
    # Applied AFTER additive floor (noise can push into saturation),
    # BEFORE quantization (analog compression before digitization)
    morph, is_saturated = _apply_saturation_step(morph, tech_noise)

    # 5. QC pathologies (v7: channel dropout, focus miss, noise spike)
    # Applied AFTER saturation, BEFORE quantization (hardware-realistic)
    # Dedicated RNG from (run_seed, well_position) - NEVER reuse biology/detector RNG
    morph, qc_flags = _apply_qc_pathologies(
        morph, well_position, run_seed, realism_config
    )

    # 6. ADC quantization (analog-to-digital conversion)
    # Applied AFTER saturation (analog → digital),
    # deterministic (no RNG)
    morph, quant_step, is_quantized = _apply_quantization_step(morph, tech_noise)

    # Assemble detector metadata (v7: includes edge_distance, qc_flags)
    detector_metadata = {
        'is_saturated': is_saturated,
        'is_quantized': is_quantized,
        'quant_step': quant_step,
        'snr_floor_proxy': snr_floor_proxy,
        'exposure_multiplier': exposure_multiplier,
        'edge_distance': edge_distance,  # v7
        'qc_flags': qc_flags,  # v7
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
