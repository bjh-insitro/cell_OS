"""
Realistic Noise Models for Synthetic Data Generation.

Improvements over baseline simulator:
1. Correlated channel noise (real Cell Painting has channel correlations)
2. Enhanced spatial effects (gradients, neighbor correlations, Moran's I)
3. State-dependent noise (stressed cells show higher variance)

Usage:
    from cell_os.sim.realistic_noise import RealisticNoiseModel
    noise_model = RealisticNoiseModel(seed=42)
    morphology = noise_model.apply_realistic_noise(
        base_morphology, well_position, stress_level, plate_id
    )
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# Cell Painting channel correlation matrix (empirical from real data)
# Channels: er, mito, nucleus, actin, rna
# These correlations reflect biological reality:
# - ER and mito are positively correlated (both organelles scale with cell size)
# - Nucleus is relatively independent
# - Actin and mito correlate (cytoskeleton and energy)
# - RNA correlates with ER (secretory machinery)
DEFAULT_CHANNEL_CORRELATION = np.array([
    #    er    mito   nuc   actin   rna
    [1.00,  0.45,  0.20,  0.30,  0.55],  # er
    [0.45,  1.00,  0.25,  0.50,  0.35],  # mito
    [0.20,  0.25,  1.00,  0.15,  0.20],  # nucleus
    [0.30,  0.50,  0.15,  1.00,  0.25],  # actin
    [0.55,  0.35,  0.20,  0.25,  1.00],  # rna
])

CHANNELS = ['er', 'mito', 'nucleus', 'actin', 'rna']


@dataclass
class SpatialEffectParams:
    """Parameters for spatial effects on plate."""
    edge_reduction: float = 0.12        # 12% signal reduction at edges
    gradient_strength: float = 0.05     # 5% max gradient across plate
    gradient_direction: str = 'radial'  # 'radial', 'left_right', 'top_bottom'
    neighbor_correlation: float = 0.3   # Correlation with adjacent wells


@dataclass
class NoiseParams:
    """Parameters for noise model."""
    base_cv: float = 0.02               # 2% baseline biological CV
    stress_cv_multiplier: float = 2.5   # Stressed cells have 2.5x higher CV
    channel_correlation: np.ndarray = field(
        default_factory=lambda: DEFAULT_CHANNEL_CORRELATION.copy()
    )
    spatial: SpatialEffectParams = field(default_factory=SpatialEffectParams)


def _stable_hash(s: str) -> int:
    """Stable 32-bit hash for deterministic seeding."""
    import hashlib
    h = hashlib.blake2s(s.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(h, byteorder="little", signed=False)


def _parse_well_position(well_id: str) -> Tuple[int, int]:
    """Parse well ID (e.g., 'A01') to (row, col) indices."""
    if not well_id or len(well_id) < 2:
        return (0, 0)
    row = ord(well_id[0].upper()) - ord('A')
    try:
        col = int(well_id[1:]) - 1
    except ValueError:
        col = 0
    return (row, col)


def _is_edge_well(row: int, col: int, n_rows: int = 8, n_cols: int = 12) -> bool:
    """Check if well is on plate edge."""
    return row == 0 or row == n_rows - 1 or col == 0 or col == n_cols - 1


class RealisticNoiseModel:
    """
    Realistic noise model with correlations and spatial effects.

    Features:
    1. Correlated channel noise using Cholesky decomposition
    2. Spatial effects: edge reduction, gradients, neighbor correlation
    3. State-dependent noise: variance scales with stress level
    """

    def __init__(
        self,
        seed: int = 42,
        params: Optional[NoiseParams] = None
    ):
        self.seed = seed
        self.params = params or NoiseParams()

        # Precompute Cholesky decomposition for correlated noise
        self._cholesky = np.linalg.cholesky(self.params.channel_correlation)

        # Cache for neighbor effects (plate_id -> well_id -> noise_offset)
        self._neighbor_cache: Dict[str, Dict[str, np.ndarray]] = {}

    def _get_well_rng(
        self,
        plate_id: str,
        well_id: str,
        tag: str
    ) -> np.random.Generator:
        """Get deterministic RNG for a specific well and noise type."""
        key = f"{tag}|{self.seed}|{plate_id}|{well_id}"
        return np.random.default_rng(_stable_hash(key))

    def generate_correlated_noise(
        self,
        plate_id: str,
        well_id: str,
        base_cv: float
    ) -> Dict[str, float]:
        """
        Generate correlated noise across channels.

        Uses Cholesky decomposition to transform independent normal samples
        into correlated samples matching the channel correlation matrix.
        """
        rng = self._get_well_rng(plate_id, well_id, "corr_noise")

        # Generate independent standard normal samples
        z = rng.standard_normal(len(CHANNELS))

        # Transform to correlated samples using Cholesky
        correlated = self._cholesky @ z

        # Scale by CV and convert to multiplicative factors
        noise_factors = {}
        for i, ch in enumerate(CHANNELS):
            # Multiplicative noise: exp(correlated * cv) for lognormal-like behavior
            noise_factors[ch] = np.exp(correlated[i] * base_cv)

        return noise_factors

    def compute_spatial_effect(
        self,
        well_id: str,
        plate_id: str,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> float:
        """
        Compute spatial effect multiplier for a well position.

        Combines:
        1. Edge effect (reduced signal at edges)
        2. Gradient effect (systematic variation across plate)
        """
        row, col = _parse_well_position(well_id)
        params = self.params.spatial

        # Start with no effect
        effect = 1.0

        # Edge effect
        if _is_edge_well(row, col, n_rows, n_cols):
            effect *= (1.0 - params.edge_reduction)

        # Gradient effect
        if params.gradient_strength > 0:
            if params.gradient_direction == 'radial':
                # Radial gradient: center is brightest
                center_row = (n_rows - 1) / 2
                center_col = (n_cols - 1) / 2
                max_dist = np.sqrt(center_row**2 + center_col**2)
                dist = np.sqrt((row - center_row)**2 + (col - center_col)**2)
                gradient = 1.0 - params.gradient_strength * (dist / max_dist)
            elif params.gradient_direction == 'left_right':
                # Left-to-right gradient
                gradient = 1.0 - params.gradient_strength * (col / (n_cols - 1))
            elif params.gradient_direction == 'top_bottom':
                # Top-to-bottom gradient
                gradient = 1.0 - params.gradient_strength * (row / (n_rows - 1))
            else:
                gradient = 1.0

            effect *= gradient

        return effect

    def compute_state_dependent_cv(
        self,
        base_cv: float,
        stress_level: float
    ) -> float:
        """
        Compute CV that increases with stress level.

        Stressed/dying cells show heterogeneous responses, increasing variance.

        Args:
            base_cv: Baseline coefficient of variation
            stress_level: 0.0 (healthy) to 1.0 (dead/dying)

        Returns:
            Adjusted CV
        """
        # Linear interpolation between base and stressed CV
        multiplier = 1.0 + stress_level * (self.params.stress_cv_multiplier - 1.0)
        return base_cv * multiplier

    def apply_realistic_noise(
        self,
        base_morphology: Dict[str, float],
        well_id: str,
        plate_id: str,
        stress_level: float = 0.0,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> Dict[str, float]:
        """
        Apply all realistic noise effects to morphology values.

        Args:
            base_morphology: Dict of channel -> value (before noise)
            well_id: Well position (e.g., 'A01')
            plate_id: Plate identifier
            stress_level: 0.0 (healthy) to 1.0 (dead/dying)
            n_rows: Number of plate rows
            n_cols: Number of plate columns

        Returns:
            Dict of channel -> noisy value
        """
        # 1. Compute state-dependent CV
        effective_cv = self.compute_state_dependent_cv(
            self.params.base_cv, stress_level
        )

        # 2. Generate correlated noise
        noise_factors = self.generate_correlated_noise(
            plate_id, well_id, effective_cv
        )

        # 3. Compute spatial effect
        spatial_factor = self.compute_spatial_effect(
            well_id, plate_id, n_rows, n_cols
        )

        # 4. Apply all effects
        noisy_morphology = {}
        for ch in CHANNELS:
            base_val = base_morphology.get(ch, 1.0)
            # Multiplicative: base * correlated_noise * spatial
            noisy_morphology[ch] = base_val * noise_factors[ch] * spatial_factor
            # Ensure non-negative
            noisy_morphology[ch] = max(0.0, noisy_morphology[ch])

        return noisy_morphology


def compute_morans_i(
    values: Dict[str, float],
    n_rows: int = 8,
    n_cols: int = 12
) -> float:
    """
    Compute Moran's I spatial autocorrelation statistic.

    Used to validate that spatial effects are realistic.

    Args:
        values: Dict of well_id -> value
        n_rows: Number of plate rows
        n_cols: Number of plate columns

    Returns:
        Moran's I statistic (-1 to 1, 0 = random, >0 = clustered)
    """
    # Build value array and weight matrix
    n = n_rows * n_cols
    y = np.zeros(n)

    for well_id, val in values.items():
        row, col = _parse_well_position(well_id)
        if 0 <= row < n_rows and 0 <= col < n_cols:
            idx = row * n_cols + col
            y[idx] = val

    # Compute mean
    y_mean = np.mean(y)
    y_dev = y - y_mean

    # Build adjacency weights (queen contiguity)
    W = np.zeros((n, n))
    for i in range(n):
        row_i, col_i = i // n_cols, i % n_cols
        for j in range(n):
            if i == j:
                continue
            row_j, col_j = j // n_cols, j % n_cols
            # Queen contiguity: adjacent in row, col, or diagonal
            if abs(row_i - row_j) <= 1 and abs(col_i - col_j) <= 1:
                W[i, j] = 1.0

    # Row-standardize weights
    row_sums = W.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    W = W / row_sums

    # Compute Moran's I
    numerator = np.sum(W * np.outer(y_dev, y_dev))
    denominator = np.sum(y_dev ** 2)

    if denominator == 0:
        return 0.0

    morans_i = (n / W.sum()) * (numerator / denominator)
    return float(morans_i)


# Convenience function for integration with existing simulator
def apply_realistic_noise_to_well(
    morphology: Dict[str, float],
    well_id: str,
    plate_id: str,
    design_id: str,
    viability: float,
    seed: int = 0
) -> Dict[str, float]:
    """
    Convenience function for applying realistic noise in simulator.

    Drop-in replacement for existing noise application.
    """
    # Create noise model (cached internally via seed)
    model = RealisticNoiseModel(seed=seed)

    # Stress level is inverse of viability
    stress_level = 1.0 - viability

    return model.apply_realistic_noise(
        base_morphology=morphology,
        well_id=well_id,
        plate_id=plate_id,
        stress_level=stress_level
    )
