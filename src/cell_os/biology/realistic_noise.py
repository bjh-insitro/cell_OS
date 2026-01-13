"""
Realistic Noise Models for Synthetic Data Generation.

Improvements over baseline simulator:
1. Correlated channel noise (real Cell Painting has channel correlations)
2. Enhanced spatial effects (gradients, neighbor correlations, Moran's I)
3. State-dependent noise (stressed cells show higher variance)
4. Row/column systematic effects (real plates have row and column biases)
5. Batch drift over time (instrument calibration drifts during long runs)
6. Well failure clustering (failures cluster due to pipette tip issues)
7. Assay-specific noise (LDH and Cell Painting have different characteristics)

Design Note - Why No Discrete Subpopulations:
    Discrete subpopulation modeling (e.g., sensitive/typical/resistant buckets)
    was intentionally removed after Phase 5/6 design review. Reasons:

    1. "Privileged Structure": Hardcoded categories (25%/50%/25% splits) create
       assumptions that may not match reality and can be exploited by agents.

    2. Implementation Issues: The original _sync_subpopulation_viabilities()
       function was forcing synchronization after every step, defeating the
       purpose entirely (a "lie injector").

    3. Unfalsifiable: Without specific flow cytometry data showing distinct
       subpopulation death curves, the feature cannot be validated.

    The replacement approach (used in BiologicalVirtualMachine) is continuous
    heterogeneity via per-vessel random effects (bio_random_effects), which
    provides variation without assuming specific structure.

    See: docs/designs/REALISM_PRIORITY_ORDER.md
         docs/milestones/PHASE_5_HETEROGENEITY.md
         tests/contracts/test_no_subpop_structure.py

Usage:
    from cell_os.biology.realistic_noise import RealisticNoiseModel
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
    # Row/column systematic effects
    row_effect_cv: float = 0.03         # 3% CV for row-to-row variation
    col_effect_cv: float = 0.025        # 2.5% CV for column-to-column variation


@dataclass
class BatchDriftParams:
    """Parameters for batch drift over time."""
    drift_rate_per_hour: float = 0.002  # 0.2% drift per hour
    drift_type: str = 'linear'          # 'linear', 'sinusoidal', 'random_walk'
    recalibration_interval_h: float = 8.0  # Hours between recalibrations (resets drift)


@dataclass
class WellFailureParams:
    """Parameters for well failure clustering."""
    base_failure_rate: float = 0.02     # 2% base failure rate
    cluster_probability: float = 0.4    # 40% chance failure spreads to adjacent
    cluster_decay: float = 0.5          # Probability decays by 50% each step
    failure_modes: Dict[str, float] = field(default_factory=lambda: {
        'bubble': 0.40,           # Near-zero signal
        'contamination': 0.25,    # 5-20x higher signal
        'pipetting_error': 0.20,  # 5-30% of normal
        'focus_issue': 0.15,      # Blurred, 50-80% signal with high variance
    })


@dataclass
class AssayNoiseParams:
    """Assay-specific noise parameters."""
    # Cell Painting (morphology)
    cell_painting_cv: float = 0.02      # 2% baseline CV
    cell_painting_channel_specific: bool = True  # Use channel-specific CVs
    # LDH cytotoxicity
    ldh_cv: float = 0.15                # 15% baseline CV (higher than morphology)
    ldh_dead_cell_cv: float = 0.25      # 25% CV for dying cells (more heterogeneous)
    # ATP viability
    atp_cv: float = 0.10                # 10% baseline CV


# PopulationParams removed - see module docstring "Design Note - Why No Discrete Subpopulations"


@dataclass
class NoiseParams:
    """Parameters for noise model."""
    base_cv: float = 0.02               # 2% baseline biological CV
    stress_cv_multiplier: float = 2.5   # Stressed cells have 2.5x higher CV
    channel_correlation: np.ndarray = field(
        default_factory=lambda: DEFAULT_CHANNEL_CORRELATION.copy()
    )
    spatial: SpatialEffectParams = field(default_factory=SpatialEffectParams)
    batch_drift: BatchDriftParams = field(default_factory=BatchDriftParams)
    well_failure: WellFailureParams = field(default_factory=WellFailureParams)
    assay_noise: AssayNoiseParams = field(default_factory=AssayNoiseParams)
    # population field removed - see module docstring "Design Note - Why No Discrete Subpopulations"


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

    def compute_row_column_effects(
        self,
        well_id: str,
        plate_id: str,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> float:
        """
        Compute row and column systematic effects.

        Real plates have row-to-row and column-to-column biases from:
        - Temperature gradients (rows near incubator door)
        - Pipetting patterns (multi-channel pipette effects)
        - Plate manufacturing variability

        Returns multiplicative factor.
        """
        row, col = _parse_well_position(well_id)
        params = self.params.spatial

        # Row effect (consistent within plate)
        row_rng = np.random.default_rng(_stable_hash(f"row_{plate_id}_{row}"))
        row_effect = row_rng.lognormal(0, params.row_effect_cv)

        # Column effect (consistent within plate)
        col_rng = np.random.default_rng(_stable_hash(f"col_{plate_id}_{col}"))
        col_effect = col_rng.lognormal(0, params.col_effect_cv)

        return row_effect * col_effect

    def compute_batch_drift(
        self,
        plate_id: str,
        well_index: int,
        total_wells: int = 96,
        run_duration_h: float = 4.0
    ) -> float:
        """
        Compute batch drift effect based on temporal position.

        Instrument calibration drifts during long runs due to:
        - Temperature changes
        - Reagent degradation
        - Focus drift
        - Light source intensity changes

        Args:
            plate_id: Plate identifier
            well_index: Index of well in processing order (0 to total_wells-1)
            total_wells: Total wells in the plate
            run_duration_h: Total run duration in hours

        Returns:
            Multiplicative drift factor
        """
        params = self.params.batch_drift

        # Time position (0 to 1 within run)
        t = well_index / max(total_wells - 1, 1)

        # Hours elapsed
        hours_elapsed = t * run_duration_h

        # Apply recalibration reset
        hours_since_cal = hours_elapsed % params.recalibration_interval_h

        if params.drift_type == 'linear':
            # Linear drift
            drift = 1.0 + params.drift_rate_per_hour * hours_since_cal
        elif params.drift_type == 'sinusoidal':
            # Sinusoidal drift (thermal cycles)
            drift = 1.0 + params.drift_rate_per_hour * np.sin(2 * np.pi * hours_since_cal / 4.0)
        elif params.drift_type == 'random_walk':
            # Random walk (deterministic per plate)
            rng = np.random.default_rng(_stable_hash(f"drift_{plate_id}_{well_index}"))
            steps = int(hours_since_cal * 10)  # 10 steps per hour
            walk = rng.normal(0, params.drift_rate_per_hour / 3, steps).sum()
            drift = 1.0 + walk
        else:
            drift = 1.0

        return max(0.8, min(1.2, drift))  # Clamp to reasonable range

    def check_well_failure(
        self,
        well_id: str,
        plate_id: str,
        failed_wells: Optional[set] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if well has failed and determine failure mode.

        Failures cluster due to:
        - Pipette tip issues affecting consecutive wells
        - Contamination spreading to neighbors
        - Systematic focus problems in regions

        Args:
            well_id: Well position
            plate_id: Plate identifier
            failed_wells: Set of already-failed wells (for clustering)

        Returns:
            (is_failed, failure_mode, signal_multiplier)
        """
        params = self.params.well_failure
        rng = np.random.default_rng(_stable_hash(f"failure_{plate_id}_{well_id}"))

        # Base failure probability
        failure_prob = params.base_failure_rate

        # Increase probability if neighbors have failed (clustering)
        if failed_wells:
            row, col = _parse_well_position(well_id)
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    neighbor_row = row + dr
                    neighbor_col = col + dc
                    neighbor_id = f"{chr(65 + neighbor_row)}{neighbor_col + 1:02d}"
                    if neighbor_id in failed_wells:
                        # Increase failure probability
                        distance = abs(dr) + abs(dc)
                        cluster_boost = params.cluster_probability * (params.cluster_decay ** (distance - 1))
                        failure_prob = min(0.5, failure_prob + cluster_boost)

        # Check if failed
        if rng.random() > failure_prob:
            return (False, None, 1.0)

        # Determine failure mode
        modes = list(params.failure_modes.keys())
        probs = list(params.failure_modes.values())
        probs = np.array(probs) / sum(probs)  # Normalize
        mode = rng.choice(modes, p=probs)

        # Compute signal multiplier for this failure mode
        if mode == 'bubble':
            multiplier = rng.uniform(0.01, 0.1)
        elif mode == 'contamination':
            multiplier = rng.uniform(5.0, 20.0)
        elif mode == 'pipetting_error':
            multiplier = rng.uniform(0.05, 0.3)
        elif mode == 'focus_issue':
            multiplier = rng.uniform(0.5, 0.8)
        else:
            multiplier = 1.0

        return (True, mode, multiplier)

    def apply_assay_specific_noise(
        self,
        value: float,
        assay_type: str,
        well_id: str,
        plate_id: str,
        stress_level: float = 0.0
    ) -> float:
        """
        Apply assay-specific noise characteristics.

        Different assays have different noise profiles:
        - Cell Painting: Low CV, channel-correlated
        - LDH: Higher CV, especially for dying cells
        - ATP: Medium CV

        Args:
            value: Base measurement value
            assay_type: 'cell_painting', 'ldh', or 'atp'
            well_id: Well position
            plate_id: Plate identifier
            stress_level: 0.0 (healthy) to 1.0 (dead/dying)

        Returns:
            Noisy value
        """
        params = self.params.assay_noise
        rng = np.random.default_rng(_stable_hash(f"assay_{assay_type}_{plate_id}_{well_id}"))

        if assay_type == 'ldh':
            # LDH has higher CV, especially for dying cells
            base_cv = params.ldh_cv
            # Dead cells release LDH heterogeneously
            effective_cv = base_cv + stress_level * (params.ldh_dead_cell_cv - base_cv)
        elif assay_type == 'atp':
            base_cv = params.atp_cv
            # ATP also increases variance with stress
            effective_cv = base_cv * (1.0 + 0.5 * stress_level)
        else:  # cell_painting
            base_cv = params.cell_painting_cv
            effective_cv = self.compute_state_dependent_cv(base_cv, stress_level)

        # Apply lognormal noise
        noisy_value = value * rng.lognormal(0, effective_cv)
        return max(0.0, noisy_value)

    # compute_population_heterogeneity() removed - see module docstring
    # "Design Note - Why No Discrete Subpopulations"

    def apply_realistic_noise(
        self,
        base_morphology: Dict[str, float],
        well_id: str,
        plate_id: str,
        stress_level: float = 0.0,
        n_rows: int = 8,
        n_cols: int = 12,
        well_index: int = 0,
        failed_wells: Optional[set] = None
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
            well_index: Index of well in processing order (for batch drift)
            failed_wells: Set of already-failed wells (for failure clustering)

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

        # 3. Compute spatial effect (edges + gradients)
        spatial_factor = self.compute_spatial_effect(
            well_id, plate_id, n_rows, n_cols
        )

        # 4. Compute row/column systematic effects
        row_col_factor = self.compute_row_column_effects(
            well_id, plate_id, n_rows, n_cols
        )

        # 5. Compute batch drift
        drift_factor = self.compute_batch_drift(
            plate_id, well_index, n_rows * n_cols
        )

        # 6. Combine all multiplicative effects
        total_factor = spatial_factor * row_col_factor * drift_factor

        # 7. Apply all effects to morphology
        noisy_morphology = {}
        for ch in CHANNELS:
            base_val = base_morphology.get(ch, 1.0)
            # Multiplicative: base * correlated_noise * spatial * row_col * drift
            noisy_morphology[ch] = base_val * noise_factors[ch] * total_factor
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
