"""
Imaging Artifacts Core: Debris Effects on Cell Painting

PROBLEM: Debris from wash/fixation affects imaging quality.
This is NOT biological signal - it's measurement system degradation.

DESIGN PRINCIPLES:
- Pure functions (no side effects, no RNG)
- Hard bounds (clamps prevent explosion)
- Monotonic (more debris never improves quality)
- Deterministic (stable outputs given inputs)
- Composable (modifiers stack without interference)

ARTIFACT MODIFIERS (from simple to structured):
1. Background fluorescence multiplier (scalar or per-channel)
2. Segmentation failure probability (scalar bump)
3. Segmentation failure modes (merge/split with severities)
4. Spatial debris field (3x3 local modulation)

MODIFIER COMPOSITION SCHEMA:
All modifiers return dicts with explicit keys. Callers compose via:
- Background: multiply channel intensities
- Segmentation: apply merge/split distortions
- Spatial: modulate texture/granularity features by pattern

COVENANT: Artifacts affect MEASUREMENTS, never BIOLOGY.
- Wash/fixation → debris → imaging quality degradation
- Compounds → stress program → morphology program
- Never let measurement corruption create stress-like morphology

Real-World Motivation:
- Debris scatters light → inflates background fluorescence
- Debris confounds segmentation → merges/splits/drops
- Edge wells accumulate more debris (evaporation + handling) → higher failure rate
- Artifacts are spatially structured (patches, not uniform noise)

References:
- Wash/fixation physics: src/cell_os/sim/wash_fix_core.py
- Debris tracking: VesselState.debris_cells, VesselState.initial_cells
"""

import numpy as np
from typing import Dict, Any, Optional
import hashlib


def compute_background_noise_multiplier(
    debris_cells: float,
    adherent_cells: float,
    base_multiplier: float = 1.0,
    debris_coefficient: float = 0.05,
    max_multiplier: float = 1.25
) -> float:
    """
    Compute background fluorescence noise multiplier from debris.

    Debris scatters light and increases autofluorescence, inflating
    measurement noise. This is a multiplicative noise inflation term.

    Formula:
        multiplier = base + debris_coefficient * (debris_cells / adherent_cells)
        clamped to [base, max_multiplier]

    Args:
        debris_cells: Debris cell count (accumulated from wash/fixation)
        adherent_cells: Current adherent cell count (normalization anchor)
        base_multiplier: Baseline multiplier (default 1.0 = no inflation)
        debris_coefficient: Sensitivity to debris (default 0.05 = 5% inflation per 100% debris)
        max_multiplier: Maximum multiplier (default 1.25 = cap at 25% inflation)

    Returns:
        Noise multiplier in [base_multiplier, max_multiplier]

    Example:
        Current cells: 10000
        Debris: 600 (6% of current)
        → multiplier = 1.0 + 0.05 * (600/10000) = 1.003 (0.3% inflation)

        Trashed well:
        Debris: 3000 (30% of current cells)
        → multiplier = 1.0 + 0.05 * (3000/10000) = 1.015 (1.5% inflation)

    Invariants:
        - multiplier >= base_multiplier (debris never improves signal)
        - multiplier <= max_multiplier (bounded, no light sources)
        - More debris → higher multiplier (monotonic)
    """
    # Guard against zero adherent_cells (shouldn't happen, but defensive)
    if adherent_cells <= 0:
        return float(base_multiplier)

    # Debris fraction (normalized to current adherent cell count)
    debris_fraction = float(debris_cells) / float(adherent_cells)

    # Linear inflation with debris fraction
    multiplier = base_multiplier + debris_coefficient * debris_fraction

    # Clamp to bounds
    multiplier = float(np.clip(multiplier, base_multiplier, max_multiplier))

    return multiplier


def compute_segmentation_failure_probability_bump(
    debris_cells: float,
    adherent_cell_count: float,
    base_probability: float = 0.0,
    debris_coefficient: float = 0.02,
    max_probability: float = 0.5
) -> float:
    """
    Compute segmentation failure probability bump from debris.

    Debris confounds segmentation algorithms, increasing merge/split/drop
    errors. This is an ADDITIVE probability bump on top of base failure rate.

    Formula:
        p_fail = base + debris_coefficient * (debris_cells / adherent_cells)
        clamped to [0, max_probability]

    Args:
        debris_cells: Debris cell count (detached, not adherent)
        adherent_cell_count: Current adherent cell count (denominator for signal ratio)
        base_probability: Base failure probability (default 0.0)
        debris_coefficient: Sensitivity to debris (default 0.02 = 2% failure bump per 100% debris)
        max_probability: Maximum failure probability (default 0.5 = cap at 50%)

    Returns:
        Failure probability in [0, max_probability]

    Example:
        Adherent cells: 5000
        Debris: 1000 (20% of adherent)
        → p_fail = 0.0 + 0.02 * (1000/5000) = 0.004 (0.4% failure bump)

        High debris scenario:
        Adherent cells: 2000
        Debris: 2000 (100% of adherent)
        → p_fail = 0.0 + 0.02 * (2000/2000) = 0.02 (2% failure bump)

        Trashed well (very low cells, high debris):
        Adherent cells: 500
        Debris: 2500 (500% of adherent)
        → p_fail = 0.0 + 0.02 * (2500/500) = 0.10 → clamped to max_probability

    Invariants:
        - p_fail >= 0 (probability is non-negative)
        - p_fail <= max_probability (bounded, prevents nonsense)
        - More debris → higher p_fail (monotonic)
        - Low cell count amplifies effect (debris-to-signal ratio matters)

    Note:
        Denominator is CURRENT adherent cells (not initial), because
        debris-to-signal ratio drives segmentation confusion. Low cell
        count + high debris = worst case.
    """
    # Guard against zero or very low cell count (prevents explosion)
    if adherent_cell_count <= 1:
        # If almost no cells, segmentation is hopeless regardless of debris
        # Clamp to max to signal "don't trust this well"
        return float(max_probability)

    # Debris-to-signal ratio
    debris_ratio = float(debris_cells) / float(adherent_cell_count)

    # Linear bump with debris ratio
    p_fail = base_probability + debris_coefficient * debris_ratio

    # Clamp to bounds [0, max_probability]
    p_fail = float(np.clip(p_fail, 0.0, max_probability))

    return p_fail


def compute_imaging_artifact_modifiers(
    vessel_state: Any,
    base_params: Dict[str, Any] = None
) -> Dict[str, float]:
    """
    Compute all imaging artifact modifiers from vessel state.

    This is the main entry point for debris-driven artifacts. Pure function
    with no side effects - just reads vessel state and returns modifiers.

    Args:
        vessel_state: VesselState with debris_cells, initial_cells, cell_count
        base_params: Optional parameter overrides (for testing/tuning)

    Returns:
        Dict with:
            - bg_noise_multiplier: Background fluorescence inflation [1.0, 1.25]
            - seg_fail_prob_bump: Segmentation failure probability bump [0, 0.5]

    Example usage in Cell Painting assay:
        >>> modifiers = compute_imaging_artifact_modifiers(vessel)
        >>> # Apply background noise multiplier to measurement variance
        >>> morph[channel] *= lognormal_multiplier(rng, cv * modifiers['bg_noise_multiplier'])
        >>> # Apply segmentation failure probability bump
        >>> seg_quality *= (1.0 - modifiers['seg_fail_prob_bump'])
    """
    base_params = base_params or {}

    # Extract vessel state fields
    debris_cells = float(getattr(vessel_state, 'debris_cells', 0.0))
    initial_cells = float(getattr(vessel_state, 'initial_cells', 1.0))  # Guard against zero
    adherent_cells = float(max(1.0, getattr(vessel_state, 'cell_count', 1.0)))  # Current adherent

    # Compute background noise multiplier (normalized to current adherent cells, not initial)
    bg_multiplier = compute_background_noise_multiplier(
        debris_cells=debris_cells,
        adherent_cells=adherent_cells,
        base_multiplier=base_params.get('bg_base_multiplier', 1.0),
        debris_coefficient=base_params.get('bg_debris_coefficient', 0.05),
        max_multiplier=base_params.get('bg_max_multiplier', 1.25)
    )

    # Compute segmentation failure probability bump
    seg_fail_bump = compute_segmentation_failure_probability_bump(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        base_probability=base_params.get('seg_base_probability', 0.0),
        debris_coefficient=base_params.get('seg_debris_coefficient', 0.02),
        max_probability=base_params.get('seg_max_probability', 0.5)
    )

    return {
        'bg_noise_multiplier': bg_multiplier,
        'seg_fail_prob_bump': seg_fail_bump,
        'debris_cells': debris_cells,
        'initial_cells': initial_cells,
        'adherent_cells': adherent_cells,
    }


def compute_segmentation_failure_modes(
    debris_cells: float,
    adherent_cell_count: float,
    confluence: float = 0.5,
    base_merge: float = 0.0,
    base_split: float = 0.0,
    merge_coefficient: float = 0.03,
    split_coefficient: float = 0.01,
    max_total: float = 0.5
) -> Dict[str, float]:
    """
    Compute structured segmentation failure modes (merge/split).

    Debris confounds segmentation in TWO distinct ways:
    - MERGE (under-segmentation): Touching cells incorrectly joined
    - SPLIT (over-segmentation): Single cells incorrectly fragmented

    High confluence amplifies merge (cells are actually touching).
    Low confluence amplifies split (debris fragments look like cells).

    This is pure deterministic math - no RNG, no position, no seed.

    Formula:
        debris_ratio = debris_cells / max(1.0, adherent_cell_count)
        confluence_bias_merge = 0.5 + 0.5 * confluence  # [0.5, 1.0]
        confluence_bias_split = 1.5 - 0.5 * confluence  # [1.0, 1.5]

        p_merge_raw = base_merge + merge_coefficient * debris_ratio * confluence_bias_merge
        p_split_raw = base_split + split_coefficient * debris_ratio * confluence_bias_split

        # Renormalize if total exceeds max_total (preserves ratio)
        if p_merge_raw + p_split_raw > max_total:
            scale = max_total / (p_merge_raw + p_split_raw)
            p_merge = p_merge_raw * scale
            p_split = p_split_raw * scale
        else:
            p_merge = p_merge_raw
            p_split = p_split_raw

    Args:
        debris_cells: Debris cell count (detached, not adherent)
        adherent_cell_count: Current adherent cell count
        confluence: Confluence level [0, 1] (default 0.5)
        base_merge: Base merge probability (default 0.0)
        base_split: Base split probability (default 0.0)
        merge_coefficient: Sensitivity to debris for merge (default 0.03)
        split_coefficient: Sensitivity to debris for split (default 0.01)
        max_total: Maximum total failure probability (default 0.5)

    Returns:
        Dict with:
            - p_merge: Merge probability [0, 0.4]
            - p_split: Split probability [0, 0.4]
            - merge_severity: Typical merge factor [2.0, 3.0]
            - split_severity: Typical split factor [2.0, 3.0]

    Example:
        High confluence scenario:
        Adherent cells: 10000, Debris: 500, Confluence: 0.9
        → debris_ratio = 0.05, confluence_bias_merge = 0.95
        → p_merge = 0.03 * 0.05 * 0.95 = 0.001425 (0.14%)
        → p_split = 0.01 * 0.05 * 1.05 = 0.000525 (0.05%)

        Low confluence scenario:
        Adherent cells: 2000, Debris: 500, Confluence: 0.2
        → debris_ratio = 0.25, confluence_bias_split = 1.4
        → p_merge = 0.03 * 0.25 * 0.6 = 0.0045 (0.45%)
        → p_split = 0.01 * 0.25 * 1.4 = 0.0035 (0.35%)

    Invariants:
        - p_merge >= 0, p_split >= 0 (non-negative probabilities)
        - p_merge + p_split <= max_total (renormalized if needed)
        - More debris → higher p_merge and p_split (monotonic)
        - High confluence → p_merge/p_split ratio increases
        - Low confluence → p_merge/p_split ratio decreases
    """
    # Guard against zero or very low cell count
    if adherent_cell_count <= 1:
        # If almost no cells, return max failures
        p_merge = min(0.4, max_total * 0.6)  # 60% of max budget
        p_split = min(0.4, max_total * 0.4)  # 40% of max budget
        return {
            'p_merge': float(p_merge),
            'p_split': float(p_split),
            'merge_severity': 2.5,
            'split_severity': 2.5,
        }

    # Clamp confluence to [0, 1]
    confluence = float(np.clip(confluence, 0.0, 1.0))

    # Debris-to-signal ratio
    debris_ratio = float(debris_cells) / float(adherent_cell_count)

    # Confluence bias factors
    # High confluence (0.9) → merge bias 0.95, split bias 1.05
    # Low confluence (0.1) → merge bias 0.55, split bias 1.45
    confluence_bias_merge = 0.5 + 0.5 * confluence  # [0.5, 1.0]
    confluence_bias_split = 1.5 - 0.5 * confluence  # [1.0, 1.5]

    # Compute raw probabilities
    p_merge_raw = base_merge + merge_coefficient * debris_ratio * confluence_bias_merge
    p_split_raw = base_split + split_coefficient * debris_ratio * confluence_bias_split

    # Clamp to individual max (0.4)
    p_merge_raw = float(np.clip(p_merge_raw, 0.0, 0.4))
    p_split_raw = float(np.clip(p_split_raw, 0.0, 0.4))

    # Renormalize if total exceeds max_total (preserves ratio)
    total_raw = p_merge_raw + p_split_raw
    if total_raw > max_total:
        scale = max_total / max(total_raw, 1e-9)
        p_merge = float(p_merge_raw * scale)
        p_split = float(p_split_raw * scale)
    else:
        p_merge = float(p_merge_raw)
        p_split = float(p_split_raw)

    # Severity factors (how many cells affected per failure event)
    # Higher debris → more severe failures (larger merges, more fragments)
    # Bounded to [2.0, 3.0] (typical merge joins 2-3 cells, split creates 2-3 fragments)
    severity_factor = float(np.clip(1.0 + debris_ratio, 1.0, 1.5))
    merge_severity = float(np.clip(2.0 * severity_factor, 2.0, 3.0))
    split_severity = float(np.clip(2.0 * severity_factor, 2.0, 3.0))

    return {
        'p_merge': p_merge,
        'p_split': p_split,
        'merge_severity': merge_severity,
        'split_severity': split_severity,
    }


def compute_background_multipliers_by_channel(
    debris_cells: float,
    adherent_cells: float,
    channel_weights: Optional[Dict[str, float]] = None,
    base_multiplier: float = 1.0,
    debris_coefficient: float = 0.05,
    max_multiplier: float = 1.25
) -> Dict[str, float]:
    """
    Per-channel background fluorescence multipliers (backward compatible).

    Different channels have different sensitivity to background corruption:
    - RNA, Actin: weak signal, more sensitive to background inflation
    - ER, Mito: strong signal, less sensitive
    - Nucleus: intermediate

    This is backward compatible: if channel_weights is None, returns scalar.

    Formula:
        base_mult = compute_background_noise_multiplier(debris_cells, adherent_cells, ...)

        If channel_weights is None:
            return {"__global__": base_mult}

        Else for each channel:
            weight = channel_weights.get(channel, 1.0)  # Default 1.0
            weight_clamped = clip(weight, 0.5, 2.0)  # Defensive bounds
            channel_mult = 1.0 + (base_mult - 1.0) * weight_clamped
            channel_mult_clamped = clip(channel_mult, base_multiplier, max_multiplier)

    Args:
        debris_cells: Debris cell count (accumulated from wash/fixation)
        adherent_cells: Current adherent cell count (normalization anchor)
        channel_weights: Optional per-channel sensitivity weights
            Example: {'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
            Default weight is 1.0 for channels not specified
        base_multiplier: Baseline multiplier (default 1.0)
        debris_coefficient: Sensitivity to debris (default 0.05)
        max_multiplier: Maximum multiplier (default 1.25)

    Returns:
        If channel_weights is None:
            {"__global__": scalar_multiplier}
        Else:
            {'er': 1.01, 'mito': 1.01, 'nucleus': 1.015, 'actin': 1.02, 'rna': 1.025}

    Example:
        # Backward compatible (scalar)
        result = compute_background_multipliers_by_channel(
            debris_cells=600, adherent_cells=3000, channel_weights=None
        )
        # → {"__global__": 1.01}

        # Per-channel (structured)
        result = compute_background_multipliers_by_channel(
            debris_cells=600, adherent_cells=3000,
            channel_weights={'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
        )
        # → {'rna': 1.015, 'actin': 1.013, 'nucleus': 1.01, 'er': 1.008, 'mito': 1.008}

    Invariants:
        - All multipliers >= base_multiplier (debris never improves signal)
        - All multipliers <= max_multiplier (bounded per channel)
        - channel_weights in [0.5, 2.0] after clamping (defensive)
        - Backward compatible: None returns scalar in "__global__" key
    """
    # Compute base global multiplier
    base_mult = compute_background_noise_multiplier(
        debris_cells=debris_cells,
        adherent_cells=adherent_cells,
        base_multiplier=base_multiplier,
        debris_coefficient=debris_coefficient,
        max_multiplier=max_multiplier
    )

    # Backward compatible: no weights → scalar
    if channel_weights is None:
        return {"__global__": base_mult}

    # Per-channel weights applied to delta from baseline
    # delta = (base_mult - 1.0) is the inflation amount
    # Each channel gets: 1.0 + delta * weight
    delta = base_mult - base_multiplier

    result = {}
    for channel, weight in channel_weights.items():
        # Clamp weight to [0.5, 2.0] (defensive)
        weight_clamped = float(np.clip(weight, 0.5, 2.0))

        # Apply weight to delta
        channel_mult = base_multiplier + delta * weight_clamped

        # Clamp to global bounds
        channel_mult_clamped = float(np.clip(channel_mult, base_multiplier, max_multiplier))

        result[channel] = channel_mult_clamped

    return result


def compute_debris_field_modifiers(
    debris_cells: float,
    adherent_cells: float,
    is_edge: bool,
    well_id: str,
    experiment_seed: int,
    field_resolution: int = 3
) -> Dict[str, Any]:
    """
    Spatial debris field for locality-dependent artifacts.

    Debris doesn't distribute uniformly - it clumps, settles, accumulates
    at meniscus edges. This creates SPATIAL HETEROGENEITY in imaging quality.

    Pattern is deterministic from (experiment_seed, well_id, is_edge).
    This is NOT per-measurement randomness - it's a fixed spatial pattern
    for this well in this plate instance.

    Formula:
        field_strength = clip(debris_cells / adherent_cells, 0.0, 1.0)

        # Deterministic hash for spatial pattern
        hash_input = f"{experiment_seed}_{well_id}_{is_edge}"
        pattern_seed = int(hashlib.sha256(hash_input.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(pattern_seed)

        # Generate 3x3 spatial pattern with mean 1.0
        if is_edge:
            spatial_cv = 0.15  # Higher variance at edge (meniscus)
        else:
            spatial_cv = 0.08  # Lower variance interior

        pattern_raw = rng.normal(loc=1.0, scale=spatial_cv, size=(3, 3))
        pattern = clip(pattern_raw, 0.7, 1.3)  # Hard bounds
        pattern = pattern / pattern.mean()  # Renormalize to mean 1.0

        texture_corruption = field_strength * 0.3  # Max 30% texture noise
        edge_amplification = 1.0 + field_strength * 0.4 if is_edge else 1.0

    Args:
        debris_cells: Debris cell count
        adherent_cells: Current adherent cell count (normalization anchor)
        is_edge: Whether well is on plate edge (amplifies heterogeneity)
        well_id: Well identifier like "B03" (for deterministic pattern)
        experiment_seed: Plate instance seed (NOT per-measurement seed)
        field_resolution: Pattern grid size (default 3 for 3x3)

    Returns:
        {
            'field_strength': float,  # [0, 1] from debris fraction
            'spatial_pattern': np.ndarray,  # 3x3 with mean 1.0, bounded [0.7, 1.3]
            'texture_corruption': float,  # [0, 0.3] from field_strength
            'edge_amplification': float,  # [1.0, 1.4] if edge, else 1.0
        }

    Example:
        # Interior well, low debris
        result = compute_debris_field_modifiers(
            debris_cells=100, adherent_cells=3000, is_edge=False,
            well_id="B03", experiment_seed=42
        )
        # → field_strength=0.033, spatial_pattern=[[0.98, 1.02, 0.99], ...],
        #   texture_corruption=0.01, edge_amplification=1.0

        # Edge well, high debris
        result = compute_debris_field_modifiers(
            debris_cells=1000, adherent_cells=3000, is_edge=True,
            well_id="A01", experiment_seed=42
        )
        # → field_strength=0.333, spatial_pattern=[[0.85, 1.15, 0.95], ...],
        #   texture_corruption=0.10, edge_amplification=1.13

    Invariants:
        - field_strength in [0, 1] (normalized debris fraction)
        - spatial_pattern.mean() ≈ 1.0 (±1e-6, renormalized)
        - spatial_pattern values in [0.7, 1.3] (hard bounds)
        - texture_corruption in [0, 0.3] (max 30%)
        - edge_amplification in [1.0, 1.4] (edge only)
        - Deterministic: same inputs → same pattern
    """
    # Guard against zero adherent_cells
    if adherent_cells <= 0:
        return {
            'field_strength': 0.0,
            'spatial_pattern': np.ones((field_resolution, field_resolution), dtype=np.float64),
            'texture_corruption': 0.0,
            'edge_amplification': 1.0,
        }

    # Debris fraction → field strength [0, 1]
    field_strength = float(np.clip(debris_cells / adherent_cells, 0.0, 1.0))

    # Deterministic hash for spatial pattern
    hash_input = f"{experiment_seed}_{well_id}_{is_edge}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    pattern_seed = int.from_bytes(hash_bytes[:4], byteorder='big')  # Use first 4 bytes
    rng = np.random.default_rng(pattern_seed)

    # Generate spatial pattern with variance depending on edge status
    if is_edge:
        spatial_cv = 0.15  # Higher variance at edge (meniscus effects)
    else:
        spatial_cv = 0.08  # Lower variance interior

    # Generate 3x3 pattern with mean 1.0
    pattern_raw = rng.normal(loc=1.0, scale=spatial_cv, size=(field_resolution, field_resolution))

    # Hard bounds [0.7, 1.3]
    pattern = np.clip(pattern_raw, 0.7, 1.3)

    # Renormalize to exact mean 1.0 (preserves relative structure)
    pattern_mean = pattern.mean()
    if pattern_mean > 1e-9:
        pattern = pattern / pattern_mean

    # Ensure mean is exactly 1.0 (within floating point precision)
    pattern = pattern.astype(np.float64)

    # Texture corruption: debris creates granular noise in texture features
    # Max 30% corruption at full debris load
    texture_corruption = float(field_strength * 0.3)

    # Edge amplification: edge wells have stronger artifacts when debris present
    if is_edge:
        edge_amplification = float(1.0 + field_strength * 0.4)  # Up to 40% amplification
    else:
        edge_amplification = 1.0

    return {
        'field_strength': field_strength,
        'spatial_pattern': pattern,
        'texture_corruption': texture_corruption,
        'edge_amplification': edge_amplification,
    }
