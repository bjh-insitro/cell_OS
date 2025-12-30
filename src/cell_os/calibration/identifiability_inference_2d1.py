"""
Phase 2D.1: Contamination Identifiability - Inference

Label-free contamination detector and parameter recovery.

Detector signatures:
1. Growth arrest (change-point on log-growth rate)
2. Morphology anomaly (Mahalanobis distance from clean baseline)
3. Viability trajectory (plateau → drop)

Parameter recovery:
- Event rate per regime
- Onset time distribution
- Contamination type classification (on flagged events)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.spatial.distance import mahalanobis
from scipy import stats


# Feature indices (must match runner)
FEATURE_CELL_COUNT = 0
FEATURE_VIABILITY = 1
FEATURE_ER = 2
FEATURE_MITO = 3
FEATURE_NUCLEUS = 4
FEATURE_ACTIN = 5
FEATURE_RNA = 6

MORPH_FEATURES = [FEATURE_ER, FEATURE_MITO, FEATURE_NUCLEUS, FEATURE_ACTIN, FEATURE_RNA]


def compute_log_growth_rate(counts: np.ndarray, times: np.ndarray) -> np.ndarray:
    """
    Compute log-growth rate increments.

    Args:
        counts: Cell counts over time (shape: n_times)
        times: Sampling times (hours)

    Returns:
        Log-growth rate per interval (shape: n_times - 1)
    """
    # Avoid log(0) by flooring at 1.0
    counts = np.maximum(counts, 1.0)
    log_counts = np.log(counts)

    # Finite differences
    dt = np.diff(times)
    dlog = np.diff(log_counts)

    # Growth rate per hour
    growth_rate = dlog / np.maximum(dt, 1e-6)

    return growth_rate


def detect_growth_arrest(
    counts: np.ndarray,
    times: np.ndarray,
    window_size: int = 3,
    threshold_factor: float = 0.5,
) -> Tuple[bool, Optional[float], float]:
    """
    Detect growth arrest via change-point on log-growth rate.

    Args:
        counts: Cell counts over time
        times: Sampling times (hours)
        window_size: Rolling window size for smoothing
        threshold_factor: Drop threshold relative to baseline (0.5 → 50% drop)

    Returns:
        (is_arrested, arrest_time_h, arrest_score)
    """
    if len(counts) < window_size + 2:
        return False, None, 0.0

    growth_rate = compute_log_growth_rate(counts, times)

    # Baseline: mean of first half
    baseline_window = len(growth_rate) // 3
    baseline_mean = np.mean(growth_rate[:baseline_window])

    if baseline_mean <= 0:
        # Already not growing at start (weird, but not arrest)
        return False, None, 0.0

    # Rolling mean for smoothing
    if len(growth_rate) >= window_size:
        smooth_rate = np.convolve(growth_rate, np.ones(window_size) / window_size, mode='valid')
    else:
        smooth_rate = growth_rate

    # Find first sustained drop below threshold
    threshold = baseline_mean * threshold_factor
    arrest_candidates = np.where(smooth_rate < threshold)[0]

    if len(arrest_candidates) == 0:
        return False, None, 0.0

    # First arrest point (in smooth_rate indexing)
    arrest_idx_smooth = arrest_candidates[0]

    # Map back to original time array (accounting for convolution offset)
    offset = (window_size - 1) // 2
    arrest_idx_time = arrest_idx_smooth + offset

    # Ensure within bounds
    if arrest_idx_time >= len(times) - 1:
        return False, None, 0.0

    arrest_time = times[arrest_idx_time + 1]  # +1 because growth_rate is len(times)-1

    # Score: magnitude of drop relative to baseline
    arrest_score = max(0.0, 1.0 - smooth_rate[arrest_idx_smooth] / baseline_mean)

    return True, arrest_time, arrest_score


def compute_morphology_anomaly_score(
    morph_features: np.ndarray,
    clean_mean: np.ndarray,
    clean_cov_inv: np.ndarray,
) -> float:
    """
    Compute Mahalanobis distance from clean baseline distribution.

    Args:
        morph_features: Morphology vector (5 channels)
        clean_mean: Clean baseline mean vector
        clean_cov_inv: Inverse covariance matrix

    Returns:
        Mahalanobis distance (anomaly score)
    """
    try:
        dist = mahalanobis(morph_features, clean_mean, clean_cov_inv)
    except (ValueError, np.linalg.LinAlgError):
        # Covariance singular or other numerical issue
        # Fall back to normalized Euclidean
        diff = morph_features - clean_mean
        dist = np.linalg.norm(diff) / max(np.linalg.norm(clean_mean), 1e-6)

    return float(dist)


def detect_viability_drop(
    viability: np.ndarray,
    times: np.ndarray,
    plateau_threshold: float = 0.9,
    drop_threshold: float = 0.2,
) -> Tuple[bool, Optional[float], float]:
    """
    Detect plateau → sudden drop in viability.

    Args:
        viability: Viability over time
        times: Sampling times (hours)
        plateau_threshold: Min viability to count as plateau (0.9)
        drop_threshold: Min drop magnitude to count as event (0.2)

    Returns:
        (has_drop, drop_time_h, drop_score)
    """
    if len(viability) < 3:
        return False, None, 0.0

    # Find plateau region (viability > threshold)
    plateau_mask = viability >= plateau_threshold

    if not np.any(plateau_mask):
        # Never plateaued (died early or never healthy)
        return False, None, 0.0

    # Find first drop after plateau
    plateau_end = np.where(plateau_mask)[0][-1]

    if plateau_end >= len(viability) - 1:
        # Still in plateau (no drop)
        return False, None, 0.0

    # Compute drop magnitude after plateau
    post_plateau_viability = viability[plateau_end + 1:]
    drop_magnitude = viability[plateau_end] - np.min(post_plateau_viability)

    if drop_magnitude < drop_threshold:
        return False, None, 0.0

    # Drop time: first point after plateau
    drop_time = times[plateau_end + 1]
    drop_score = drop_magnitude

    return True, drop_time, drop_score


def fit_clean_baseline(observations: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Fit clean baseline distribution from Regime A (clean).

    Args:
        observations: Regime A observations (n_vessels × n_times × n_features)

    Returns:
        Dict with:
            - morph_mean: Mean morphology vector (5 channels)
            - morph_cov: Covariance matrix
            - morph_cov_inv: Inverse covariance (for Mahalanobis)
    """
    # Extract morphology features from all vessels/times in Regime A
    morph_data = observations[:, :, MORPH_FEATURES]  # (n_vessels, n_times, 5)
    morph_flat = morph_data.reshape(-1, len(MORPH_FEATURES))  # (n_vessels * n_times, 5)

    # Remove any invalid data (zeros, NaNs)
    valid_mask = np.all(np.isfinite(morph_flat) & (morph_flat > 0), axis=1)
    morph_clean = morph_flat[valid_mask]

    # Fit distribution
    morph_mean = np.mean(morph_clean, axis=0)
    morph_cov = np.cov(morph_clean, rowvar=False)

    # Regularize covariance for numerical stability
    morph_cov += np.eye(len(MORPH_FEATURES)) * 1e-6

    try:
        morph_cov_inv = np.linalg.inv(morph_cov)
    except np.linalg.LinAlgError:
        # Singular matrix - use pseudo-inverse
        morph_cov_inv = np.linalg.pinv(morph_cov)

    return {
        'morph_mean': morph_mean,
        'morph_cov': morph_cov,
        'morph_cov_inv': morph_cov_inv,
    }


def detect_contamination_vessel(
    vessel_obs: np.ndarray,
    times: np.ndarray,
    clean_baseline: Dict[str, np.ndarray],
    growth_arrest_threshold: float = 0.3,
    morphology_anomaly_threshold: float = 3.0,
    viability_drop_threshold: float = 0.2,
) -> Dict[str, any]:
    """
    Run contamination detector on a single vessel.

    Args:
        vessel_obs: Observations for one vessel (n_times × n_features)
        times: Sampling times (hours)
        clean_baseline: Clean baseline distribution from fit_clean_baseline()
        growth_arrest_threshold: Min arrest score to flag (0.3)
        morphology_anomaly_threshold: Min Mahalanobis distance to flag (3.0)
        viability_drop_threshold: Min viability drop to flag (0.2)

    Returns:
        Dict with:
            - flagged: bool (contamination detected)
            - onset_h: float or None (predicted onset time)
            - signatures: dict of individual signature scores
    """
    counts = vessel_obs[:, FEATURE_CELL_COUNT]
    viability = vessel_obs[:, FEATURE_VIABILITY]
    morph = vessel_obs[:, MORPH_FEATURES]

    # Signature 1: Growth arrest
    arrest_detected, arrest_time, arrest_score = detect_growth_arrest(counts, times)

    # Signature 2: Morphology anomaly (max over time after arrest)
    if arrest_detected and arrest_time is not None:
        # Only check morphology after arrest
        arrest_idx = np.searchsorted(times, arrest_time)
        post_arrest_morph = morph[arrest_idx:, :]
    else:
        # Check all timepoints
        post_arrest_morph = morph

    morph_scores = []
    for morph_vec in post_arrest_morph:
        if np.all(np.isfinite(morph_vec)) and np.all(morph_vec > 0):
            score = compute_morphology_anomaly_score(
                morph_vec,
                clean_baseline['morph_mean'],
                clean_baseline['morph_cov_inv']
            )
            morph_scores.append(score)

    max_morph_anomaly = max(morph_scores) if morph_scores else 0.0

    # Signature 3: Viability drop
    drop_detected, drop_time, drop_score = detect_viability_drop(viability, times)

    # Combined flagging logic (AND/OR gates)
    # Flag if: (arrest AND morphology) OR (viability_drop AND morphology)
    arrest_flag = arrest_detected and (arrest_score >= growth_arrest_threshold)
    morph_flag = max_morph_anomaly >= morphology_anomaly_threshold
    drop_flag = drop_detected and (drop_score >= viability_drop_threshold)

    flagged = (arrest_flag and morph_flag) or (drop_flag and morph_flag)

    # Predicted onset: earliest of arrest or drop time
    onset_candidates = []
    if arrest_detected and arrest_time is not None:
        onset_candidates.append(arrest_time)
    if drop_detected and drop_time is not None:
        onset_candidates.append(drop_time)

    predicted_onset = min(onset_candidates) if onset_candidates else None

    return {
        'flagged': flagged,
        'onset_h': predicted_onset,
        'signatures': {
            'growth_arrest_detected': arrest_detected,
            'growth_arrest_score': arrest_score,
            'growth_arrest_time_h': arrest_time,
            'morphology_anomaly_max': max_morph_anomaly,
            'viability_drop_detected': drop_detected,
            'viability_drop_score': drop_score,
            'viability_drop_time_h': drop_time,
        }
    }


def classify_contamination_type(
    vessel_obs: np.ndarray,
    times: np.ndarray,
    predicted_onset_h: float,
    type_prototypes: Dict[str, np.ndarray],
    window_h: float = 12.0,
) -> Tuple[str, Dict[str, float]]:
    """
    Classify contamination type from morphology signature.

    Args:
        vessel_obs: Observations for one vessel (n_times × n_features)
        times: Sampling times (hours)
        predicted_onset_h: Predicted onset time
        type_prototypes: Dict mapping type → mean morphology vector
        window_h: Time window after onset to average morphology (12h)

    Returns:
        (predicted_type, type_scores)
    """
    # Extract morphology in window [onset, onset + window_h]
    onset_idx = np.searchsorted(times, predicted_onset_h)
    end_time = predicted_onset_h + window_h
    end_idx = np.searchsorted(times, end_time)

    if end_idx <= onset_idx:
        end_idx = min(onset_idx + 2, len(times))  # At least 2 samples

    morph_window = vessel_obs[onset_idx:end_idx, MORPH_FEATURES]

    # Average morphology in window (robust to outliers)
    valid_mask = np.all(np.isfinite(morph_window) & (morph_window > 0), axis=1)
    if not np.any(valid_mask):
        # No valid data - return unknown
        return 'unknown', {}

    morph_mean = np.median(morph_window[valid_mask], axis=0)

    # Nearest prototype classifier
    type_scores = {}
    for ctype, prototype in type_prototypes.items():
        dist = np.linalg.norm(morph_mean - prototype)
        type_scores[ctype] = float(dist)

    # Predict type with minimum distance
    predicted_type = min(type_scores, key=type_scores.get)

    return predicted_type, type_scores


def learn_type_prototypes(
    observations: np.ndarray,
    times: np.ndarray,
    ground_truth: List[Dict],
) -> Dict[str, np.ndarray]:
    """
    Learn type prototypes from Regime B ground truth (training data).

    Args:
        observations: Regime B observations (n_vessels × n_times × n_features)
        times: Sampling times
        ground_truth: List of true event dicts with 'vessel_index' and 'contamination_type'

    Returns:
        Dict mapping type → mean morphology vector
    """
    type_morphs = {'bacterial': [], 'fungal': [], 'mycoplasma': []}

    for event in ground_truth:
        v_idx = event['vessel_index']
        ctype = event['contamination_type']
        onset_h = event['contamination_onset_h']

        # Extract morphology after onset
        onset_idx = np.searchsorted(times, onset_h)
        morph_post = observations[v_idx, onset_idx:, MORPH_FEATURES]

        # Average valid samples
        valid_mask = np.all(np.isfinite(morph_post) & (morph_post > 0), axis=1)
        if np.any(valid_mask):
            morph_mean = np.mean(morph_post[valid_mask], axis=0)
            type_morphs[ctype].append(morph_mean)

    # Compute prototype per type
    prototypes = {}
    for ctype, morphs in type_morphs.items():
        if len(morphs) > 0:
            prototypes[ctype] = np.mean(morphs, axis=0)
        else:
            # No examples - use zeros (will fail gracefully)
            prototypes[ctype] = np.zeros(len(MORPH_FEATURES))

    return prototypes


def run_inference_on_regime(
    observations: np.ndarray,
    times: np.ndarray,
    clean_baseline: Dict[str, np.ndarray],
    type_prototypes: Optional[Dict[str, np.ndarray]] = None,
) -> List[Dict]:
    """
    Run detector on all vessels in a regime.

    Args:
        observations: Observations (n_vessels × n_times × n_features)
        times: Sampling times
        clean_baseline: Clean baseline distribution
        type_prototypes: Type prototypes (optional, for classification)

    Returns:
        List of detection dicts (one per vessel)
    """
    n_vessels = observations.shape[0]
    detections = []

    for v_idx in range(n_vessels):
        vessel_obs = observations[v_idx, :, :]
        detection = detect_contamination_vessel(vessel_obs, times, clean_baseline)
        detection['vessel_index'] = v_idx

        # Type classification (if flagged and prototypes available)
        if detection['flagged'] and type_prototypes is not None and detection['onset_h'] is not None:
            predicted_type, type_scores = classify_contamination_type(
                vessel_obs,
                times,
                detection['onset_h'],
                type_prototypes
            )
            detection['predicted_type'] = predicted_type
            detection['type_scores'] = type_scores
        else:
            detection['predicted_type'] = None
            detection['type_scores'] = {}

        detections.append(detection)

    return detections


def compute_sensitivity_specificity(
    detections: List[Dict],
    ground_truth: List[Dict],
) -> Dict[str, any]:
    """
    Compute TP/FP/FN counts and sensitivity/specificity.

    Args:
        detections: List of detection dicts (from run_inference_on_regime)
        ground_truth: List of true event dicts

    Returns:
        Dict with TP, FP, FN, sensitivity, specificity, precision
    """
    # Build ground truth set (vessel indices with events)
    true_positive_vessels = set(event['vessel_index'] for event in ground_truth)
    n_vessels = len(detections)
    n_true_events = len(true_positive_vessels)
    n_true_negatives = n_vessels - n_true_events

    # Count detections
    detected_vessels = set(d['vessel_index'] for d in detections if d['flagged'])

    TP = len(detected_vessels & true_positive_vessels)
    FP = len(detected_vessels - true_positive_vessels)
    FN = len(true_positive_vessels - detected_vessels)
    TN = n_true_negatives - FP

    # Metrics
    sensitivity = TP / n_true_events if n_true_events > 0 else 0.0
    specificity = TN / n_true_negatives if n_true_negatives > 0 else 0.0
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    fpr = FP / n_true_negatives if n_true_negatives > 0 else 0.0

    return {
        'TP': TP,
        'FP': FP,
        'FN': FN,
        'TN': TN,
        'n_true_events': n_true_events,
        'n_detected': len(detected_vessels),
        'sensitivity': sensitivity,
        'specificity': specificity,
        'precision': precision,
        'fpr': fpr,
    }


def compute_onset_mae(
    detections: List[Dict],
    ground_truth: List[Dict],
) -> Tuple[float, List[float]]:
    """
    Compute MAE on onset time for correctly detected true events.

    Args:
        detections: List of detection dicts
        ground_truth: List of true event dicts

    Returns:
        (mae, list of errors)
    """
    # Build lookup: vessel_index → true onset
    true_onset_map = {event['vessel_index']: event['contamination_onset_h'] for event in ground_truth}

    # Compute errors for correctly detected true events
    errors = []
    for d in detections:
        if d['flagged'] and d['vessel_index'] in true_onset_map and d['onset_h'] is not None:
            true_onset = true_onset_map[d['vessel_index']]
            error = abs(d['onset_h'] - true_onset)
            errors.append(error)

    mae = np.mean(errors) if errors else np.nan

    return mae, errors


def compute_type_accuracy(
    detections: List[Dict],
    ground_truth: List[Dict],
) -> Tuple[float, Dict[str, int]]:
    """
    Compute type classification accuracy on correctly detected true events.

    Args:
        detections: List of detection dicts (with predicted_type)
        ground_truth: List of true event dicts (with contamination_type)

    Returns:
        (accuracy, confusion_counts)
    """
    # Build lookup: vessel_index → true type
    true_type_map = {event['vessel_index']: event['contamination_type'] for event in ground_truth}

    # Count correct classifications on flagged true events
    n_correct = 0
    n_total = 0
    confusion = {}

    for d in detections:
        if d['flagged'] and d['vessel_index'] in true_type_map and d['predicted_type'] is not None:
            true_type = true_type_map[d['vessel_index']]
            predicted_type = d['predicted_type']

            key = f"{true_type}_as_{predicted_type}"
            confusion[key] = confusion.get(key, 0) + 1

            if predicted_type == true_type:
                n_correct += 1
            n_total += 1

    accuracy = n_correct / n_total if n_total > 0 else np.nan

    return accuracy, confusion


if __name__ == "__main__":
    print("Phase 2D.1: Contamination Identifiability - Inference Module")
    print("This module provides detector and parameter recovery functions.")
    print("Use scripts/run_identifiability_2d1.py to run full suite.")
