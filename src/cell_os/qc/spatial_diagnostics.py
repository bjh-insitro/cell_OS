"""
Spatial diagnostics for plate QC.

This module provides spatial autocorrelation measures to detect
technical artifacts like gradients, edge effects, and batch patterns.

Extracted from scripts/analyze_spatial_autocorrelation.py and made
production-ready with channel-agnostic interface.
"""

from typing import Dict, List, Tuple
import numpy as np

from ..core.observation import RawWellResult


def parse_well_id(well_id: str) -> Tuple[int, int]:
    """Parse well_id to (row_index, col_index).

    Args:
        well_id: Well identifier like "A1", "B12", "P24"

    Returns:
        Tuple of (row_index, col_index) zero-indexed

    Example:
        >>> parse_well_id("A1")
        (0, 0)
        >>> parse_well_id("P24")
        (15, 23)
    """
    if not well_id or len(well_id) < 2:
        raise ValueError(f"Invalid well_id: {well_id}")

    row_letter = well_id[0].upper()
    try:
        col_num = int(well_id[1:])
    except ValueError:
        raise ValueError(f"Invalid well_id column: {well_id}")

    # Convert row letter to index (A=0, B=1, ..., P=15)
    row_idx = ord(row_letter) - ord('A')
    col_idx = col_num - 1  # Columns are 1-indexed

    return row_idx, col_idx


def extract_channel_values(
    wells: List[RawWellResult],
    channel_key: str
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract channel values and positions from wells.

    Args:
        wells: List of raw well results
        channel_key: Dot-notation channel key (e.g., "morphology.nucleus")

    Returns:
        Tuple of (values, positions) where:
        - values: np.ndarray of shape (N,) with channel values
        - positions: np.ndarray of shape (N, 2) with (row, col) indices

    Raises:
        ValueError: If channel key invalid or wells empty
    """
    if not wells:
        raise ValueError("Cannot extract values from empty wells")

    # Parse channel key
    parts = channel_key.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid channel key: {channel_key}. Expected format: 'category.channel'")
    category, channel = parts

    values = []
    positions = []

    for well in wells:
        # Extract value
        if category not in well.readouts:
            raise ValueError(f"Category '{category}' not found in well readouts")
        if channel not in well.readouts[category]:
            raise ValueError(f"Channel '{channel}' not found in category '{category}'")

        value = well.readouts[category][channel]
        values.append(value)

        # Extract position
        row_idx, col_idx = parse_well_id(well.location.well_id)
        positions.append([row_idx, col_idx])

    return np.array(values), np.array(positions)


def compute_morans_i(
    wells: List[RawWellResult],
    channel_key: str
) -> Dict[str, float]:
    """
    Compute Moran's I spatial autocorrelation statistic.

    Moran's I measures spatial autocorrelation:
    I = (N/W) * Σ_i Σ_j w_ij (x_i - x̄)(x_j - x̄) / Σ_i (x_i - x̄)²

    where w_ij = 1 if wells i and j are adjacent (rook contiguity), 0 otherwise.

    Interpretation:
    - I > 0: Positive spatial autocorrelation (similar values cluster)
    - I ≈ 0: No spatial autocorrelation (random spatial pattern)
    - I < 0: Negative spatial autocorrelation (dissimilar values cluster)

    Statistical significance:
    - Z-score > 1.96: Significant at p < 0.05 (two-tailed)
    - Z-score > 2.58: Significant at p < 0.01

    Args:
        wells: List of raw well results
        channel_key: Dot-notation channel key (e.g., "morphology.nucleus")

    Returns:
        Dict with keys:
        - morans_i: Moran's I statistic
        - expected: Expected value under null hypothesis (random)
        - variance: Variance under null hypothesis
        - z_score: Standardized Z-score
        - n_wells: Number of wells analyzed
        - total_weight: Sum of spatial weights

    References:
        Moran, P.A. (1950). "Notes on continuous stochastic phenomena".
        Biometrika 37 (1-2): 17-23.
    """
    if len(wells) == 0:
        return {
            'morans_i': 0.0,
            'expected': 0.0,
            'variance': 0.0,
            'z_score': 0.0,
            'n_wells': 0,
            'total_weight': 0.0
        }

    # Extract values and positions
    values, positions = extract_channel_values(wells, channel_key)

    N = len(values)
    mean_val = np.mean(values)

    # Build spatial weight matrix (rook contiguity: adjacent wells only, no diagonals)
    W_matrix = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            if i != j:
                # Manhattan distance (row diff + col diff)
                dist = abs(positions[i][0] - positions[j][0]) + abs(positions[i][1] - positions[j][1])
                if dist == 1:  # Adjacent (not diagonal)
                    W_matrix[i, j] = 1.0

    W = np.sum(W_matrix)

    if W == 0:
        # No adjacencies (single well or disconnected)
        return {
            'morans_i': 0.0,
            'expected': -1 / (N - 1) if N > 1 else 0.0,
            'variance': 0.0,
            'z_score': 0.0,
            'n_wells': N,
            'total_weight': 0.0
        }

    # Compute Moran's I
    numerator = 0.0
    for i in range(N):
        for j in range(N):
            numerator += W_matrix[i, j] * (values[i] - mean_val) * (values[j] - mean_val)

    denominator = np.sum((values - mean_val) ** 2)

    if denominator == 0:
        # No variance (all values identical)
        morans_i = 0.0
    else:
        morans_i = (N / W) * (numerator / denominator)

    # Expected value and variance under null hypothesis (random spatial pattern)
    expected = -1 / (N - 1)

    # Compute variance (simplified formula)
    S1 = 0.0
    for i in range(N):
        for j in range(N):
            S1 += (W_matrix[i, j] + W_matrix[j, i]) ** 2
    S1 /= 2

    S2 = 0.0
    for i in range(N):
        row_sum = np.sum(W_matrix[i, :])
        col_sum = np.sum(W_matrix[:, i])
        S2 += (row_sum + col_sum) ** 2

    # Variance formula (under normality assumption)
    variance = ((N * S1 - N * S2 + 3 * W**2) / ((N**2 - 1) * W**2)) - expected**2

    # Z-score for significance testing
    if variance > 0:
        z_score = (morans_i - expected) / np.sqrt(variance)
    else:
        z_score = 0.0

    return {
        'morans_i': float(morans_i),
        'expected': float(expected),
        'variance': float(variance),
        'z_score': float(z_score),
        'n_wells': N,
        'total_weight': float(W)
    }


def check_spatial_autocorrelation(
    wells: List[RawWellResult],
    channel_key: str = "morphology.nucleus",
    significance_threshold: float = 1.96
) -> Tuple[bool, Dict[str, float]]:
    """Check if spatial autocorrelation is significant.

    This is a convenience wrapper around compute_morans_i for QC purposes.

    Args:
        wells: List of raw well results
        channel_key: Dot-notation channel key (default: morphology.nucleus)
        significance_threshold: Z-score threshold for flagging (default: 1.96 = p<0.05)

    Returns:
        Tuple of (flagged, diagnostics) where:
        - flagged: True if |Z-score| > threshold
        - diagnostics: Dict with Moran's I statistics

    Example:
        >>> flagged, diag = check_spatial_autocorrelation(wells)
        >>> if flagged:
        ...     print(f"Spatial autocorrelation detected: I={diag['morans_i']:.3f}")
    """
    diagnostics = compute_morans_i(wells, channel_key)
    flagged = abs(diagnostics['z_score']) > significance_threshold
    return flagged, diagnostics
