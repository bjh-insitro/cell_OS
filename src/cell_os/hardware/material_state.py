"""
Material State and Calibration Materials

Non-biological calibration materials for detector characterization:
- DARK wells (buffer only, camera baseline)
- Fluorescent dye solutions (uniform intensity, flat-field)
- Fluorescent beads (sparse/dense, registration/focus)

These materials have NO biology (no viability, no growth, no compounds).
They produce known optical signals for detector calibration.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MaterialState:
    """
    Non-biological calibration material (beads, dyes, buffer).

    Materials have fixed optical properties (no biology dynamics).
    Measurements include detector artifacts (floor, saturation, quantization)
    but no biological variance (viability, compound effects, growth).
    """
    material_id: str          # Unique identifier (e.g., "material_A1_FLATFIELD_DYE_LOW")
    material_type: str        # "buffer_only", "fluorescent_dye_solution", "fluorescent_beads"
    well_position: str        # Well ID (e.g., "A1")

    # Optical properties (per-channel intensities in arbitrary units)
    # These are the "true signal" before detector stack
    base_intensities: Dict[str, float]  # {er: 100.0, mito: 100.0, ...}

    # Spatial structure (for beads)
    spatial_pattern: Optional[str] = None  # "uniform", "sparse", "dense", None
    bead_count: Optional[int] = None       # Number of beads (for sparse/dense)

    # Metadata
    seed: int = 0                          # Deterministic RNG seed for this material


# Nominal intensities for standard calibration materials
# Units: arbitrary (matched to typical Cell Painting signal range ~100-500)
MATERIAL_NOMINAL_INTENSITIES = {
    'DARK': {
        # Buffer only: true zero signal (only detector floor will contribute)
        'er': 0.0,
        'mito': 0.0,
        'nucleus': 0.0,
        'actin': 0.0,
        'rna': 0.0
    },
    'BLANK': {
        # Empty well or minimal buffer: true zero signal
        'er': 0.0,
        'mito': 0.0,
        'nucleus': 0.0,
        'actin': 0.0,
        'rna': 0.0
    },
    'FLATFIELD_DYE_LOW': {
        # Low end of detector range (~20% of typical cell signal)
        # Goal: test floor-limited regime, linearity at low signal
        'er': 60.0,
        'mito': 70.0,
        'nucleus': 80.0,
        'actin': 55.0,
        'rna': 65.0
    },
    'FLATFIELD_DYE_HIGH': {
        # High end (~2× typical cell signal)
        # Goal: test saturation, dynamic range limits
        'er': 400.0,
        'mito': 500.0,
        'nucleus': 600.0,
        'actin': 450.0,
        'rna': 550.0
    },
    'MULTICOLOR_BEADS_SPARSE': {
        # Bright spots (per-bead intensity, not per-well average)
        # Goal: test registration, focus sensitivity
        'er': 200.0,
        'mito': 250.0,
        'nucleus': 300.0,
        'actin': 220.0,
        'rna': 270.0
    },
    'MULTICOLOR_BEADS_DENSE': {
        # Same per-bead intensity, more beads → higher well average
        # Goal: test repeatability, robust stats
        'er': 200.0,
        'mito': 250.0,
        'nucleus': 300.0,
        'actin': 220.0,
        'rna': 270.0
    },
    'FOCUS_BEADS': {
        # Very bright for autofocus
        # Goal: test autofocus performance, field curvature
        'er': 300.0,
        'mito': 350.0,
        'nucleus': 400.0,
        'actin': 320.0,
        'rna': 370.0
    }
}


# Bead counts per well (for averaging)
BEAD_COUNTS = {
    'sparse': 10,   # ~10 beads per well → high variance (1/sqrt(10) ≈ 32% CV)
    'dense': 100,   # ~100 beads per well → low variance (1/sqrt(100) = 10% CV)
    'medium': 30    # ~30 beads per well → moderate variance (1/sqrt(30) ≈ 18% CV)
}


# Map bead plate material names to material types
MATERIAL_TYPE_MAP = {
    'DARK': 'buffer_only',
    'BLANK': 'buffer_only',
    'FLATFIELD_DYE_LOW': 'fluorescent_dye_solution',
    'FLATFIELD_DYE_HIGH': 'fluorescent_dye_solution',
    'MULTICOLOR_BEADS_SPARSE': 'fluorescent_beads',
    'MULTICOLOR_BEADS_DENSE': 'fluorescent_beads',
    'FOCUS_BEADS': 'fluorescent_beads',
}


# Map bead plate material names to spatial patterns
MATERIAL_SPATIAL_PATTERNS = {
    'MULTICOLOR_BEADS_SPARSE': 'sparse',
    'MULTICOLOR_BEADS_DENSE': 'dense',
    'FOCUS_BEADS': 'medium',
}
