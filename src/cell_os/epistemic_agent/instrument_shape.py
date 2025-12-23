"""
Instrument shape learning from calibration plate results.

This module converts raw calibration data into InstrumentShapeSummary.
This is the ONLY way the agent learns about instrument characteristics.

No god mode. Only observables.
"""

import numpy as np
from datetime import datetime
from typing import Tuple, List, Dict, Optional
from scipy import stats
from collections import defaultdict

from .schemas import InstrumentShapeSummary, Observation, ConditionSummary
from .calibration_constants import (
    NOISE_SIGMA_THRESHOLD,
    EDGE_EFFECT_THRESHOLD,
    SPATIAL_RESIDUAL_THRESHOLD,
    REPLICATE_PRECISION_THRESHOLD,
    CHANNEL_COUPLING_THRESHOLD,
)


def _parse_well_position(well_pos: str) -> Tuple[int, int]:
    """Parse well position like 'A01' or 'P24' to (row, col) indices.

    Returns:
        (row_idx, col_idx) where row_idx=0 is 'A', col_idx=0 is column 1
    """
    row_letter = well_pos[0].upper()
    col_str = well_pos[1:]

    row_idx = ord(row_letter) - ord('A')
    col_idx = int(col_str) - 1

    return (row_idx, col_idx)


def _build_queen_adjacency(positions: List[Tuple[int, int]]) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
    """Build queen adjacency (8-neighbors) for plate positions.

    Args:
        positions: List of (row, col) tuples

    Returns:
        Dict mapping position -> list of neighbor positions
    """
    pos_set = set(positions)
    adjacency = {}

    for pos in positions:
        row, col = pos
        neighbors = []

        # Queen moves: all 8 directions
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue  # Skip self

                neighbor = (row + dr, col + dc)
                if neighbor in pos_set:
                    neighbors.append(neighbor)

        adjacency[pos] = neighbors

    return adjacency


def _compute_morans_i(
    residuals: Dict[Tuple[int, int], float],
    adjacency: Dict[Tuple[int, int], List[Tuple[int, int]]]
) -> float:
    """Compute Moran's I spatial autocorrelation statistic.

    Moran's I = (N / W) * Σ_i Σ_j w_ij (x_i - x̄)(x_j - x̄) / Σ_i (x_i - x̄)²

    Where:
        N = number of positions
        W = sum of all weights (for binary adjacency, W = number of edges)
        w_ij = 1 if i and j are neighbors, 0 otherwise
        x_i = residual at position i
        x̄ = mean residual (should be ~0 by construction)

    Returns:
        Moran's I in range [-1, 1]
            +1 = perfect positive autocorrelation (clustering)
             0 = random
            -1 = perfect negative autocorrelation (dispersion)
    """
    positions = list(residuals.keys())
    N = len(positions)

    if N < 3:
        return 0.0  # Not enough data

    # Mean residual (should be near 0)
    values = np.array([residuals[pos] for pos in positions])
    mean_val = np.mean(values)

    # Centered values
    centered = {pos: residuals[pos] - mean_val for pos in positions}

    # Compute numerator: sum of cross-products for neighbors
    numerator = 0.0
    W = 0  # Total weight (number of edges)

    for pos in positions:
        neighbors = adjacency.get(pos, [])
        for neighbor in neighbors:
            numerator += centered[pos] * centered[neighbor]
            W += 1

    # Compute denominator: sum of squared deviations
    denominator = sum(centered[pos]**2 for pos in positions)

    if denominator == 0 or W == 0:
        return 0.0

    # Moran's I formula
    morans_i = (N / W) * (numerator / denominator)

    return morans_i


def _morans_i_permutation_test(
    residuals: Dict[Tuple[int, int], float],
    adjacency: Dict[Tuple[int, int], List[Tuple[int, int]]],
    n_permutations: int = 999,
    seed: int = 42
) -> Tuple[float, Dict[str, float]]:
    """Permutation test for Moran's I significance.

    Args:
        residuals: Position -> residual mapping
        adjacency: Position -> neighbors mapping
        n_permutations: Number of random permutations
        seed: Random seed for reproducibility

    Returns:
        (p_value, null_stats) where null_stats contains:
            - i_mean: mean I under null
            - i_sd: standard deviation under null
            - i_p95: 95th percentile under null
    """
    # Observed Moran's I
    i_observed = _compute_morans_i(residuals, adjacency)

    # Generate null distribution by permuting residual values
    rng = np.random.RandomState(seed)
    positions = list(residuals.keys())
    values = np.array([residuals[pos] for pos in positions])

    null_distribution = []

    for _ in range(n_permutations):
        # Permute values randomly across positions
        permuted_values = rng.permutation(values)
        permuted_residuals = {pos: val for pos, val in zip(positions, permuted_values)}

        # Compute Moran's I for permuted data
        i_permuted = _compute_morans_i(permuted_residuals, adjacency)
        null_distribution.append(i_permuted)

    null_distribution = np.array(null_distribution)

    # Compute p-value (two-tailed: testing for ANY spatial structure)
    # We care about abs(I) being large, so test if observed is more extreme than null
    p_value = np.mean(np.abs(null_distribution) >= np.abs(i_observed))

    # Null distribution statistics
    null_stats = {
        'i_mean': float(np.mean(null_distribution)),
        'i_sd': float(np.std(null_distribution)),
        'i_p95': float(np.percentile(null_distribution, 95)),
    }

    return (p_value, null_stats)


def _diagnose_spatial_pattern(
    residuals: Dict[Tuple[int, int], float]
) -> str:
    """Heuristic pattern diagnosis: row gradient, column gradient, or field.

    Args:
        residuals: Position -> residual mapping

    Returns:
        Pattern hint string: "row_gradient", "column_gradient", "diagonal", or "smooth_field"
    """
    positions = list(residuals.keys())
    values = np.array([residuals[pos] for pos in positions])
    rows = np.array([pos[0] for pos in positions])
    cols = np.array([pos[1] for pos in positions])

    # Correlate residuals with row index and column index
    corr_row = np.corrcoef(rows, values)[0, 1] if len(values) > 2 else 0.0
    corr_col = np.corrcoef(cols, values)[0, 1] if len(values) > 2 else 0.0

    # Strong row correlation
    if abs(corr_row) > 0.5 and abs(corr_row) > abs(corr_col):
        return "row_gradient"

    # Strong column correlation
    if abs(corr_col) > 0.5 and abs(corr_col) > abs(corr_row):
        return "column_gradient"

    # Both correlations moderate (diagonal or complex field)
    if abs(corr_row) > 0.3 and abs(corr_col) > 0.3:
        return "diagonal_or_quadrant"

    # Moran's I significant but no clear linear pattern
    return "smooth_field_or_local_clustering"


def compute_instrument_shape_summary(
    observation: Observation,
    plate_id: str
) -> InstrumentShapeSummary:
    """Compute instrument shape summary from calibration plate results.

    This is the ONLY interface between raw calibration data and trust updates.

    Args:
        observation: Aggregated results from calibration plate execution
        plate_id: ID of the calibration plate that was run

    Returns:
        InstrumentShapeSummary with all metrics and pass/fail status

    Raises:
        ValueError: If observation lacks required structure for shape learning
    """

    # Extract vehicle (DMSO) conditions for noise estimation
    dmso_conditions = [c for c in observation.conditions if c.compound == 'DMSO']
    if not dmso_conditions:
        raise ValueError("Calibration plate must contain vehicle (DMSO) controls")

    # 1. Noise sigma (primary gate criterion)
    noise_sigma, noise_ci_width, noise_df = _estimate_noise_from_dmso(dmso_conditions)

    # 2. Edge effect (spatial bias)
    edge_strength, edge_confident = _estimate_edge_effect(dmso_conditions)

    # 3. Spatial residual metric (local structure via Moran's I)
    spatial_metric, spatial_detected, spatial_diagnostic = _estimate_spatial_residuals(
        observation, return_diagnostic=True
    )

    # 4. Replicate precision (from CV islands or replicates)
    precision_score, n_pairs = _estimate_replicate_precision(dmso_conditions)

    # 5. Channel coupling (spurious correlation)
    coupling_score, channels_ok = _estimate_channel_coupling(dmso_conditions)

    # Pass/fail checks
    failed_checks = []

    if noise_sigma > NOISE_SIGMA_THRESHOLD:
        failed_checks.append("noise_sigma")

    if edge_strength > EDGE_EFFECT_THRESHOLD:
        failed_checks.append("edge_effect")

    # Spatial residual check: uses BOTH metric threshold AND detection flag
    # Detection flag includes p-value significance test
    if spatial_detected:
        failed_checks.append("spatial_residual")

    if precision_score < REPLICATE_PRECISION_THRESHOLD:
        failed_checks.append("replicate_precision")

    if coupling_score > CHANNEL_COUPLING_THRESHOLD:
        failed_checks.append("channel_coupling")

    noise_gate_pass = len(failed_checks) == 0

    return InstrumentShapeSummary(
        noise_sigma=noise_sigma,
        noise_sigma_ci_width=noise_ci_width,
        noise_sigma_df=noise_df,
        edge_effect_strength=edge_strength,
        edge_effect_confident=edge_confident,
        spatial_residual_metric=spatial_metric,
        spatial_structure_detected=spatial_detected,
        spatial_diagnostic=spatial_diagnostic,  # Trust audit breadcrumb for heatmap
        replicate_precision_score=precision_score,
        replicate_n_pairs=n_pairs,
        channel_coupling_score=coupling_score,
        channel_independence_ok=channels_ok,
        noise_gate_pass=noise_gate_pass,
        failed_checks=failed_checks,
        plate_id=plate_id,
        n_wells_analyzed=observation.wells_spent,
        calibration_timestamp=datetime.now().isoformat()
    )


def _estimate_noise_from_dmso(dmso_conditions: List[ConditionSummary]) -> Tuple[float, float, int]:
    """Estimate instrument noise from DMSO replicate variability.

    Returns:
        (noise_sigma, ci_width, df): noise estimate, CI width (relative), degrees of freedom
    """
    if not dmso_conditions:
        return (1.0, 1.0, 0)  # Fail-safe: high noise, no confidence

    # Pool all DMSO CVs (coefficient of variation = std/mean)
    cvs = [c.cv for c in dmso_conditions if c.n_wells_used >= 3]

    if not cvs:
        # Fallback: use mean of std/mean from conditions with fewer replicates
        cvs = [c.std / max(abs(c.mean), 0.01) for c in dmso_conditions]

    if not cvs:
        return (1.0, 1.0, 0)

    # Noise estimate: median CV (robust to outliers)
    noise_sigma = float(np.median(cvs))

    # Confidence: IQR / median (relative spread)
    if len(cvs) >= 3:
        q25, q75 = np.percentile(cvs, [25, 75])
        ci_width = (q75 - q25) / max(noise_sigma, 0.01)
    else:
        ci_width = 1.0  # Wide CI for small samples

    # Degrees of freedom: total wells - number of conditions
    total_wells = sum(c.n_wells_used for c in dmso_conditions)
    df = max(total_wells - len(dmso_conditions), 1)

    return (noise_sigma, ci_width, df)


def _estimate_edge_effect(dmso_conditions: List[ConditionSummary]) -> Tuple[float, bool]:
    """Estimate edge vs center bias from DMSO controls.

    Returns:
        (edge_strength, confident): relative difference, statistical confidence
    """
    # Separate edge vs center DMSO conditions
    edge_conds = [c for c in dmso_conditions if c.position_tag == 'edge']
    center_conds = [c for c in dmso_conditions if c.position_tag == 'center']

    if not edge_conds or not center_conds:
        # No spatial structure in design - can't assess edge effects
        return (0.0, False)

    # Compute mean response for edge and center
    edge_mean = np.mean([c.mean for c in edge_conds])
    center_mean = np.mean([c.mean for c in center_conds])

    # Relative difference
    edge_strength = abs(edge_mean - center_mean) / max(abs(center_mean), 0.01)

    # Statistical confidence: t-test
    if len(edge_conds) >= 3 and len(center_conds) >= 3:
        edge_vals = [c.mean for c in edge_conds]
        center_vals = [c.mean for c in center_conds]
        _, p_value = stats.ttest_ind(edge_vals, center_vals)
        confident = p_value < 0.05
    else:
        confident = False

    return (float(edge_strength), confident)


def _estimate_spatial_residuals(
    observation: Observation,
    return_diagnostic: bool = False
) -> Tuple[float, bool, Optional[Dict]]:
    """Compute Moran's I on DMSO well residuals to detect spatial confounding.

    This is the real spatial structure detector that catches gradients,
    illumination fields, evaporation patterns, and local hot spots.

    Architecture note: This function needs well-level positions to compute
    spatial autocorrelation. For Cycle 0 calibration, we need this spatial
    information to properly characterize instrument shape. This is still
    an "aggregate" metric (Moran's I, not raw wells), but it requires
    well positions as input.

    Args:
        observation: Observation with DMSO conditions
        return_diagnostic: If True, return diagnostic dict with null distribution

    Returns:
        (morans_i, detected, diagnostic) where:
            - morans_i: Moran's I statistic (0.0 if insufficient data)
            - detected: True if spatial structure detected (I > threshold AND p < 0.01)
            - diagnostic: Optional dict with null stats and pattern hint
    """
    # Check if we have raw wells for Moran's I
    if hasattr(observation, 'raw_wells') and observation.raw_wells and len(observation.raw_wells) > 0:
        # Real well-level Moran's I (doesn't need dmso_conditions parameter)
        return _compute_morans_i_from_raw_wells(
            observation.raw_wells,
            None,  # dmso_conditions unused in this function
            return_diagnostic=return_diagnostic
        )

    # Fallback: condition-level approximation
    # Use position_tag to infer coarse spatial structure
    # This catches edge vs center differences but not fine gradients

    # Extract DMSO conditions for fallback
    dmso_conditions = [c for c in observation.conditions if c.compound == 'DMSO']

    if not dmso_conditions or len(dmso_conditions) < 3:
        return (0.0, False, None if not return_diagnostic else {})

    # Check if we have position diversity
    position_tags = set(c.position_tag for c in dmso_conditions)
    if len(position_tags) < 2:
        return (0.0, False, None if not return_diagnostic else {})

    # Simple metric: variance in means across positions
    # This is NOT Moran's I, but catches coarse spatial structure
    means_by_position = defaultdict(list)
    for c in dmso_conditions:
        means_by_position[c.position_tag].append(c.mean)

    # Compute between-position variance
    grand_mean = np.mean([c.mean for c in dmso_conditions])
    position_means = [np.mean(vals) for vals in means_by_position.values()]
    between_var = np.var(position_means) if len(position_means) > 1 else 0.0
    within_var = np.mean([np.var([c.mean for c in dmso_conditions])])

    # Approximate spatial metric: ratio of between/within variance
    spatial_metric = float(between_var / max(within_var, 0.01))

    # Conservative detection: only flag if large effect
    detected = spatial_metric > 0.20

    diagnostic = {
        'method': 'condition_level_approximation',
        'note': 'Well positions not available - using coarse spatial metric',
        'between_var': float(between_var),
        'within_var': float(within_var),
    } if return_diagnostic else None

    return (spatial_metric, detected, diagnostic)


def _compute_morans_i_from_raw_wells(
    raw_wells: List[Dict],
    dmso_conditions: List[ConditionSummary],
    return_diagnostic: bool = False
) -> Tuple[float, bool, Optional[Dict]]:
    """Compute Moran's I from raw well data.

    This is the real implementation for when well positions are available.

    Args:
        raw_wells: List of well dictionaries with 'position' and 'readout' fields
        dmso_conditions: DMSO condition summaries for computing residuals
        return_diagnostic: If True, return diagnostic info

    Returns:
        (morans_i, detected, diagnostic)
    """
    # Filter for DMSO wells
    dmso_wells = [w for w in raw_wells if w.get('compound') == 'DMSO']

    if len(dmso_wells) < 10:  # Need decent sample for Moran's I
        return (0.0, False, None if not return_diagnostic else {})

    # Compute global DMSO mean
    dmso_mean = np.mean([w['readout'] for w in dmso_wells])

    # Compute residuals: observed - mean
    residuals = {}
    positions = []

    for well in dmso_wells:
        pos_str = well.get('position', well.get('well_pos'))
        if not pos_str:
            continue

        try:
            pos_tuple = _parse_well_position(pos_str)
            residuals[pos_tuple] = well['readout'] - dmso_mean
            positions.append(pos_tuple)
        except (ValueError, IndexError, KeyError):
            continue  # Skip malformed positions

    if len(positions) < 10:
        return (0.0, False, None if not return_diagnostic else {})

    # Build queen adjacency
    adjacency = _build_queen_adjacency(positions)

    # Compute Moran's I
    morans_i = _compute_morans_i(residuals, adjacency)

    # Permutation test for significance
    p_value, null_stats = _morans_i_permutation_test(
        residuals, adjacency, n_permutations=999, seed=42
    )

    # Pattern diagnosis
    pattern_hint = _diagnose_spatial_pattern(residuals)

    # Detection criteria (strict for Cycle 0):
    # - p < 0.01 (not 0.05) for significance
    # - abs(Moran's I) > SPATIAL_RESIDUAL_THRESHOLD for effect size
    #   (catches BOTH positive clustering AND negative dispersion/stripes)
    detected = (p_value < 0.01 and abs(morans_i) > SPATIAL_RESIDUAL_THRESHOLD)

    diagnostic = {
        'morans_i': float(morans_i),
        'p_value': float(p_value),
        'wells_analyzed': len(positions),
        'adjacency': 'queen',
        'permutations': 999,
        'null': null_stats,
        'pattern_hint': pattern_hint,
    } if return_diagnostic else None

    return (morans_i, detected, diagnostic)


def _estimate_replicate_precision(dmso_conditions: List[ConditionSummary]) -> Tuple[float, int]:
    """Estimate replicate precision from CV islands or technical replicates.

    Returns:
        (precision_score, n_pairs): agreement metric (0-1), number of replicate pairs
    """
    # Use CV as inverse of precision: low CV = high precision
    # Precision score = 1 - mean(CV)

    cvs = [c.cv for c in dmso_conditions if c.n_wells_used >= 2]

    if not cvs:
        return (0.0, 0)

    mean_cv = float(np.mean(cvs))
    precision_score = max(0.0, min(1.0, 1.0 - mean_cv))

    # Number of "pairs": total wells / 2 (rough estimate)
    n_pairs = sum(c.n_wells_used for c in dmso_conditions) // 2

    return (precision_score, n_pairs)


def _estimate_channel_coupling(dmso_conditions: List[ConditionSummary]) -> Tuple[float, bool]:
    """Estimate spurious correlation between morphology channels.

    Returns:
        (coupling_score, ok): max pairwise correlation, True if channels independent
    """
    # Extract feature means from DMSO conditions
    all_features = {}

    for cond in dmso_conditions:
        if cond.feature_means:
            for feature, value in cond.feature_means.items():
                if feature not in all_features:
                    all_features[feature] = []
                all_features[feature].append(value)

    if len(all_features) < 2:
        # Can't assess coupling with <2 channels
        return (0.0, True)

    # Compute pairwise correlations
    max_corr = 0.0
    feature_names = list(all_features.keys())

    for i in range(len(feature_names)):
        for j in range(i + 1, len(feature_names)):
            f1 = all_features[feature_names[i]]
            f2 = all_features[feature_names[j]]

            if len(f1) >= 3 and len(f2) >= 3:
                corr = abs(np.corrcoef(f1, f2)[0, 1])
                max_corr = max(max_corr, corr)

    coupling_score = float(max_corr)
    channels_ok = coupling_score <= CHANNEL_COUPLING_THRESHOLD

    return (coupling_score, channels_ok)
