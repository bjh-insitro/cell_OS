"""
Optical Calibration Materials - Pure Signal Generation

Pure functions for generating known optical signals from calibration materials.
NO VM, NO RNG coupling, NO biology. Just optics and determinism.

Design:
- Materials have fixed base intensities (known truth)
- Variance comes from two sources:
  a) Material variance (mixing, manufacturing, N-averaging)
  b) Detector variance (floor, quantization, drift) - added by detector_stack
- Spatial vignette (radial illumination falloff) is deterministic per well

Variance model:
    CV_total = sqrt(CV_material^2 + CV_detector^2)

For beads with N-averaging:
    CV_material = CV_per_bead / sqrt(N)

Where CV_detector comes from detector_stack (floor, quantization, etc.)
"""

import numpy as np
from typing import Dict, Optional
from .material_state import BEAD_COUNTS


def generate_material_base_signal(
    material_type: str,
    base_intensities: Dict[str, float],
    spatial_pattern: Optional[str] = None,
    bead_count: Optional[int] = None,
    well_position: str = "H12",  # Center well by default
    plate_format: int = 384,
    enable_vignette: bool = True,
    rng: Optional[np.random.Generator] = None
) -> Dict[str, float]:
    """
    Generate base signal for optical material (before detector stack).

    This is the "true" optical signal that would hit the detector if it were perfect.
    Detector artifacts (floor, saturation, quantization) are applied separately.

    Args:
        material_type: "buffer_only", "fluorescent_dye_solution", "fluorescent_beads"
        base_intensities: Per-channel nominal intensities {er: float, ...}
        spatial_pattern: Bead density ("sparse", "dense", "medium") or None
        bead_count: Number of beads (if None, use BEAD_COUNTS[spatial_pattern])
        well_position: Well ID like "A1" (for vignette)
        plate_format: Plate format (384, 96, etc.) for vignette radius
        enable_vignette: Apply radial illumination falloff (default True)
        rng: RNG for material variance (if None, no variance added)

    Returns:
        Per-channel signal dict {er: float, mito: float, ...}

    Variance sources:
    - buffer_only: no variance (true zero)
    - fluorescent_dye_solution: 3% CV (mixing/concentration)
    - fluorescent_beads: 10% per-bead CV / sqrt(N) (manufacturing + averaging)

    Spatial vignette (if enabled):
    - Radial illumination falloff: center=1.0, edge~0.85
    - Models real microscope illumination non-uniformity
    """
    signal = base_intensities.copy()

    # Apply spatial vignette (deterministic per well position)
    if enable_vignette:
        vignette = compute_radial_vignette(well_position, plate_format)
        for ch in signal:
            signal[ch] *= vignette

    # Add material-specific variance
    if material_type == "buffer_only":
        # True zero - no variance
        pass

    elif material_type == "fluorescent_dye_solution":
        # Dye mixing/concentration variance (~3% CV)
        if rng is not None:
            for ch in signal:
                signal[ch] *= rng.normal(1.0, 0.03)
                signal[ch] = max(0.0, signal[ch])

    elif material_type == "fluorescent_beads":
        # Per-bead variance + N-averaging
        # CV = CV_per_bead / sqrt(N)
        if bead_count is None:
            bead_count = BEAD_COUNTS.get(spatial_pattern, 10)

        per_bead_cv = 0.10  # 10% manufacturing variance
        averaging_cv = per_bead_cv / np.sqrt(bead_count)

        if rng is not None:
            for ch in signal:
                signal[ch] *= rng.normal(1.0, averaging_cv)
                signal[ch] = max(0.0, signal[ch])

    else:
        raise ValueError(f"Unknown material_type: {material_type}")

    return signal


def compute_radial_vignette(well_position: str, plate_format: int = 384) -> float:
    """
    Compute radial illumination falloff (vignette) for a well.

    Models real microscope illumination non-uniformity:
    - Center wells: ~1.0 (full intensity)
    - Edge wells: ~0.85 (15% falloff)
    - Smooth radial gradient (no hard boundaries)

    Deterministic (no RNG): vignette is a property of the optical path, not randomness.

    Args:
        well_position: Well ID like "A1", "H12", "P24"
        plate_format: Plate format (384, 96, 24, etc.)

    Returns:
        Vignette multiplier in [0.85, 1.0]
    """
    # Parse well position to row/col indices
    import re
    match = re.search(r'([A-P])(\d{1,2})$', well_position.upper())
    if not match:
        # Invalid format → assume center well
        return 1.0

    row_letter = match.group(1)
    col_number = int(match.group(2))

    # Convert to 0-indexed coordinates
    row_idx = ord(row_letter) - ord('A')
    col_idx = col_number - 1

    # Plate dimensions (rows × cols)
    if plate_format == 384:
        n_rows, n_cols = 16, 24
    elif plate_format == 96:
        n_rows, n_cols = 8, 12
    elif plate_format == 24:
        n_rows, n_cols = 4, 6
    elif plate_format == 6:
        n_rows, n_cols = 2, 3
    else:
        # Unknown format → no vignette
        return 1.0

    # Normalize to [-1, 1] coordinates (center = 0,0)
    x = (col_idx - (n_cols - 1) / 2.0) / ((n_cols - 1) / 2.0)
    y = (row_idx - (n_rows - 1) / 2.0) / ((n_rows - 1) / 2.0)

    # Radial distance from center
    r = np.sqrt(x**2 + y**2)

    # Vignette model: center=1.0, edge~0.85
    # Use smooth falloff (no hard boundaries)
    # f(r) = 1.0 - 0.15 * (r / r_max)^2
    # where r_max = sqrt(2) for corner wells
    r_max = np.sqrt(2.0)
    vignette = 1.0 - 0.15 * (r / r_max)**2

    # Clamp to [0.85, 1.0] (safety)
    return float(np.clip(vignette, 0.85, 1.0))
