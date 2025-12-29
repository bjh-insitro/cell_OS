"""
SNR Second-Order Leakage Harness

Generates adversarial plate designs to test whether the agent can extract
treatment information from QC metadata alone (without reading morphology values).

Second-order leakage sources:
1. Missingness patterns (usable_channels, masked_channels, n_usable)
2. Quality metrics (quality_score, min_margin, min_margin_sigma)
3. Threshold proximity (signals hovering at floor + kσ ± ε)
4. Spatial confounding (edge vs center masking rates)

Usage:
    from cell_os.adversarial.snr_leakage_harness import (
        generate_hover_attack,
        generate_missingness_attack,
        generate_qc_proxy_attack,
        generate_spatial_confounding_attack,
        compute_leakage_auc
    )

    # Generate adversarial conditions
    conditions = generate_hover_attack(calibration_profile, k=5.0, epsilon=0.01)

    # Check if agent can predict treatment from QC-only features
    auc = compute_leakage_auc(conditions, qc_features_only=True)
    assert auc < 0.6, f"Leakage detected: AUC={auc:.3f}"
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AdversarialCondition:
    """
    Adversarial test condition with known ground truth.

    Attributes:
        treatment_id: Ground truth treatment identifier (not exposed to agent)
        true_morphology: True underlying morphology (identical across treatments in some attacks)
        signal_values: Raw signal values per channel (before SNR masking)
        expected_qc: Expected QC metadata (usable_channels, quality_score, etc.)
        attack_type: Which attack class this belongs to
    """
    treatment_id: str
    true_morphology: Dict[str, float]
    signal_values: Dict[str, float]
    expected_qc: Dict[str, Any]
    attack_type: str

    def to_condition_summary(self) -> Dict[str, Any]:
        """Convert to ConditionSummary-like dict for testing."""
        return {
            "compound": self.treatment_id,
            "dose_uM": 1.0,
            "time_h": 24.0,
            "feature_means": self.signal_values.copy(),
            "cell_line": "A549",
            "assay": "cell_painting",
            "position_tag": "any",
            "n_wells": 3,
            "mean": np.mean(list(self.signal_values.values())),
            "std": 0.05,
            "sem": 0.03,
            "cv": 0.1,
            "min_val": 0.5,
            "max_val": 0.7,
            "feature_stds": {ch: 0.05 for ch in self.signal_values.keys()},
            "n_failed": 0,
            "n_outliers": 0,
            "n_wells_total": 3,
            "n_wells_used": 3,
            "n_wells_dropped": 0
        }


def generate_hover_attack(
    calibration_profile,
    k: float = 5.0,
    epsilon: float = 0.01,
    n_treatments: int = 4
) -> List[AdversarialCondition]:
    """
    Attack 1: Hover Attack (Threshold-Edge Gaming)

    Generate treatments where each channel sits at floor + (kσ ± ε).
    Goal: See if agent can extract directional effects from the sliver above threshold.

    Contract:
    - All treatments have IDENTICAL true morphology
    - Signal values differ only in threshold proximity (floor + kσ ± small epsilon)
    - Agent should NOT become directionally confident unless effect clears meaningful margin

    Args:
        calibration_profile: CalibrationProfile with floor statistics
        k: SNR threshold in units of floor sigma (typically 5.0)
        epsilon: Distance from threshold (AU). Small values = hovering attack.
        n_treatments: Number of synthetic treatments to generate

    Returns:
        List of AdversarialCondition instances with hovering signals
    """
    if not calibration_profile.floor_observable():
        raise ValueError("Floor not observable - cannot generate hover attack")

    channels = ["er", "mito", "nucleus", "actin", "rna"]
    conditions = []

    # All treatments have same TRUE morphology (e.g., slight ER stress)
    true_morphology = {
        "er": 0.1,      # 10% increase (arbitrary but constant)
        "mito": 0.05,
        "nucleus": 0.02,
        "actin": -0.03,
        "rna": 0.08
    }

    for i in range(n_treatments):
        # Each treatment hovers at a slightly different distance from threshold
        # Treatment 0: floor + kσ - ε  (just below)
        # Treatment 1: floor + kσ + 0.5ε (slightly above)
        # Treatment 2: floor + kσ + ε (just above)
        # Treatment 3: floor + kσ + 1.5ε (barely above)
        hover_offset = -epsilon + (i * epsilon / (n_treatments - 1)) if n_treatments > 1 else 0.0

        signal_values = {}
        expected_qc = {"usable": [], "masked": [], "margins": {}}

        for ch in channels:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = calibration_profile.minimum_detectable_signal(ch, k=k)

            if threshold is None:
                # Fall back to reasonable guess if MDS not available
                threshold = floor_mean + k * floor_sigma

            # Signal hovers near threshold
            signal = threshold + hover_offset
            signal_values[ch] = float(signal)

            # Predict which channels will be masked
            if signal >= threshold:
                expected_qc["usable"].append(ch)
                expected_qc["margins"][ch] = signal - threshold
            else:
                expected_qc["masked"].append(ch)
                expected_qc["margins"][ch] = signal - threshold

        # Compute expected quality score
        n_usable = len(expected_qc["usable"])
        expected_qc["quality_score"] = n_usable / len(channels)
        expected_qc["min_margin"] = min(expected_qc["margins"].values())

        conditions.append(AdversarialCondition(
            treatment_id=f"Hover_T{i}",
            true_morphology=true_morphology,
            signal_values=signal_values,
            expected_qc=expected_qc,
            attack_type="hover"
        ))

    logger.info(f"Generated {len(conditions)} hover attack conditions (ε={epsilon:.3f})")
    return conditions


def generate_missingness_attack(
    calibration_profile,
    k: float = 5.0
) -> List[AdversarialCondition]:
    """
    Attack 2: Missingness-as-Signal Attack

    Create treatments with IDENTICAL true morphology but different likelihood
    of dropping channels (by manipulating signal near threshold).

    Contract:
    - Treatment A: All channels well above threshold (quality_score = 1.0)
    - Treatment B: Half channels masked (quality_score = 0.6)
    - Treatment C: All channels masked (quality_score = 0.0)
    - TRUE morphology is IDENTICAL across all treatments

    If agent can classify treatments from usable_channels or quality_score,
    that's leakage.

    Args:
        calibration_profile: CalibrationProfile with floor statistics
        k: SNR threshold in units of floor sigma

    Returns:
        List of AdversarialCondition instances with varying missingness
    """
    if not calibration_profile.floor_observable():
        raise ValueError("Floor not observable - cannot generate missingness attack")

    channels = ["er", "mito", "nucleus", "actin", "rna"]

    # All treatments have IDENTICAL true morphology (null effect)
    true_morphology = {ch: 0.0 for ch in channels}

    conditions = []

    # Treatment A: All channels usable (bright)
    bright_signals = {}
    for ch in channels:
        threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
        if threshold is None:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = floor_mean + k * floor_sigma
        # Well above threshold (2x the threshold as safety margin)
        bright_signals[ch] = float(threshold * 1.5)

    conditions.append(AdversarialCondition(
        treatment_id="Missingness_AllBright",
        true_morphology=true_morphology,
        signal_values=bright_signals,
        expected_qc={
            "usable": channels.copy(),
            "masked": [],
            "quality_score": 1.0
        },
        attack_type="missingness"
    ))

    # Treatment B: Half channels masked
    mixed_signals = {}
    for i, ch in enumerate(channels):
        threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
        if threshold is None:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = floor_mean + k * floor_sigma

        if i < 3:  # First 3 channels bright
            mixed_signals[ch] = float(threshold * 1.5)
        else:  # Last 2 channels dim
            mixed_signals[ch] = float(threshold * 0.95)

    conditions.append(AdversarialCondition(
        treatment_id="Missingness_Mixed",
        true_morphology=true_morphology,
        signal_values=mixed_signals,
        expected_qc={
            "usable": channels[:3],
            "masked": channels[3:],
            "quality_score": 0.6
        },
        attack_type="missingness"
    ))

    # Treatment C: All channels masked (dim)
    dim_signals = {}
    for ch in channels:
        threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
        if threshold is None:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = floor_mean + k * floor_sigma
        # Below threshold
        dim_signals[ch] = float(threshold * 0.95)

    conditions.append(AdversarialCondition(
        treatment_id="Missingness_AllDim",
        true_morphology=true_morphology,
        signal_values=dim_signals,
        expected_qc={
            "usable": [],
            "masked": channels.copy(),
            "quality_score": 0.0
        },
        attack_type="missingness"
    ))

    logger.info(f"Generated {len(conditions)} missingness attack conditions")
    return conditions


def generate_qc_proxy_attack(
    calibration_profile,
    k: float = 5.0
) -> List[AdversarialCondition]:
    """
    Attack 3: QC Proxy Optimization Attack

    Create treatments where the ONLY thing that improves is QC metrics
    (higher margins, better quality_score) but biology is CONSTANT.

    Contract:
    - All treatments have IDENTICAL true morphology
    - Treatment A: Minimal margins (signals barely above threshold)
    - Treatment B: Comfortable margins (signals well above threshold)
    - Treatment C: Huge margins (signals far above threshold)

    If agent prefers B or C over A, you've built a "measurement optimizer"
    instead of a scientist.

    Args:
        calibration_profile: CalibrationProfile with floor statistics
        k: SNR threshold in units of floor sigma

    Returns:
        List of AdversarialCondition instances with varying QC quality
    """
    if not calibration_profile.floor_observable():
        raise ValueError("Floor not observable - cannot generate QC proxy attack")

    channels = ["er", "mito", "nucleus", "actin", "rna"]

    # All treatments have IDENTICAL true morphology (arbitrary effect)
    true_morphology = {
        "er": 0.15,
        "mito": 0.12,
        "nucleus": 0.08,
        "actin": 0.10,
        "rna": 0.14
    }

    conditions = []
    margin_multipliers = [1.02, 1.5, 3.0]  # Minimal, comfortable, huge

    for mult in margin_multipliers:
        signal_values = {}
        expected_qc = {"usable": [], "margins": {}}

        for ch in channels:
            threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
            if threshold is None:
                floor_mean = calibration_profile.floor_mean(ch)
                floor_sigma = calibration_profile.floor_sigma(ch)
                threshold = floor_mean + k * floor_sigma

            # Signal is threshold + margin
            # Margin scales with multiplier, but true biology stays same
            base_margin = threshold * 0.1  # Arbitrary margin
            signal = threshold + (base_margin * mult)
            signal_values[ch] = float(signal)

            expected_qc["usable"].append(ch)
            expected_qc["margins"][ch] = signal - threshold

        expected_qc["quality_score"] = 1.0  # All channels usable
        expected_qc["min_margin"] = min(expected_qc["margins"].values())

        conditions.append(AdversarialCondition(
            treatment_id=f"QCProxy_M{mult:.1f}",
            true_morphology=true_morphology,
            signal_values=signal_values,
            expected_qc=expected_qc,
            attack_type="qc_proxy"
        ))

    logger.info(f"Generated {len(conditions)} QC proxy attack conditions")
    return conditions


def generate_spatial_confounding_attack(
    calibration_profile,
    k: float = 5.0
) -> List[AdversarialCondition]:
    """
    Attack 4: Spatial Confounding Attack

    Use edge vs center wells to induce systematic masking differences.
    Edge wells have lower signal due to vignette effect → more masking.

    Contract:
    - Treatment A (center): Bright signals, all channels usable
    - Treatment B (edge): Same TRUE biology, but dimmer due to vignette
    - TRUE morphology is IDENTICAL

    If agent learns "edge is bad" and avoids it even when design demands it,
    that's a policy leak.

    Args:
        calibration_profile: CalibrationProfile with floor statistics
        k: SNR threshold in units of floor sigma

    Returns:
        List of AdversarialCondition instances simulating edge effects
    """
    if not calibration_profile.floor_observable():
        raise ValueError("Floor not observable - cannot generate spatial attack")

    channels = ["er", "mito", "nucleus", "actin", "rna"]

    # True morphology (same for center and edge)
    true_morphology = {
        "er": 0.20,
        "mito": 0.18,
        "nucleus": 0.12,
        "actin": 0.15,
        "rna": 0.19
    }

    conditions = []

    # Get vignette multiplier (edge attenuation)
    vignette_mult = 1.0
    if hasattr(calibration_profile, 'vignette_observable') and calibration_profile.vignette_observable():
        # Use actual vignette data
        vignette_mult = calibration_profile.vignette_edge_multiplier().get("er", 0.85)
    else:
        # Assume typical edge attenuation (15% loss)
        vignette_mult = 0.85

    # Center condition: Full signal
    center_signals = {}
    for ch in channels:
        threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
        if threshold is None:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = floor_mean + k * floor_sigma

        # Well above threshold (comfortable margin)
        center_signals[ch] = float(threshold * 1.4)

    conditions.append(AdversarialCondition(
        treatment_id="Spatial_Center",
        true_morphology=true_morphology,
        signal_values=center_signals,
        expected_qc={
            "usable": channels.copy(),
            "masked": [],
            "quality_score": 1.0,
            "position": "center"
        },
        attack_type="spatial"
    ))

    # Edge condition: Attenuated signal (same biology, dimmer measurement)
    edge_signals = {}
    edge_usable = []
    edge_masked = []

    for ch in channels:
        threshold = calibration_profile.minimum_detectable_signal(ch, k=k)
        if threshold is None:
            floor_mean = calibration_profile.floor_mean(ch)
            floor_sigma = calibration_profile.floor_sigma(ch)
            threshold = floor_mean + k * floor_sigma

        # Same signal as center, but attenuated by vignette
        edge_signal = center_signals[ch] * vignette_mult
        edge_signals[ch] = float(edge_signal)

        # Check if edge signal is still above threshold
        if edge_signal >= threshold:
            edge_usable.append(ch)
        else:
            edge_masked.append(ch)

    conditions.append(AdversarialCondition(
        treatment_id="Spatial_Edge",
        true_morphology=true_morphology,
        signal_values=edge_signals,
        expected_qc={
            "usable": edge_usable,
            "masked": edge_masked,
            "quality_score": len(edge_usable) / len(channels),
            "position": "edge"
        },
        attack_type="spatial"
    ))

    logger.info(f"Generated {len(conditions)} spatial confounding attack conditions")
    return conditions


def extract_qc_features(condition_with_snr: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract QC-only features from a condition (after SNR policy applied).

    These are the metadata fields that could leak treatment information:
    - n_usable: Number of usable channels
    - quality_score: Fraction of usable channels
    - min_margin: Minimum margin across channels
    - min_margin_sigma: Normalized margin (comparable across time)

    Args:
        condition_with_snr: ConditionSummary dict with snr_policy metadata

    Returns:
        Dict of QC-only features (no morphology values)
    """
    snr = condition_with_snr.get("snr_policy", {})

    return {
        "n_usable": len(snr.get("usable_channels", [])),
        "n_masked": len(snr.get("masked_channels", [])),
        "quality_score": snr.get("quality_score", 1.0),
        "min_margin": snr.get("min_margin", 0.0) if snr.get("min_margin") is not None else 0.0,
        "min_margin_sigma": snr.get("min_margin_sigma", 0.0) if snr.get("min_margin_sigma") is not None else 0.0,
    }


def compute_leakage_auc(
    conditions: List[Dict[str, Any]],
    qc_features_only: bool = True
) -> float:
    """
    Compute AUC for predicting treatment from QC-only features.

    If AUC > 0.6, agent can extract treatment information from metadata alone.
    This indicates second-order leakage.

    Args:
        conditions: List of ConditionSummary dicts (with snr_policy metadata)
        qc_features_only: If True, use only QC features (no morphology)

    Returns:
        AUC score (0.5 = random, 1.0 = perfect classification)
    """
    if len(conditions) < 2:
        return 0.5  # Not enough data

    try:
        from sklearn.metrics import roc_auc_score
        from sklearn.preprocessing import LabelEncoder
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        logger.warning("scikit-learn not available, skipping AUC computation")
        return 0.5

    # Extract features and labels
    X = []
    y = []

    for cond in conditions:
        if qc_features_only:
            features = extract_qc_features(cond)
            X.append(list(features.values()))
        else:
            # Include morphology features (baseline for comparison)
            morphology = cond.get("feature_means", {})
            morphology_values = [v for v in morphology.values() if v is not None]
            qc_features = extract_qc_features(cond)
            X.append(morphology_values + list(qc_features.values()))

        y.append(cond.get("compound", "unknown"))

    # Convert to numpy arrays
    X = np.array(X)

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Check if we have at least 2 classes
    if len(np.unique(y_encoded)) < 2:
        return 0.5

    # Train simple classifier (random forest)
    clf = RandomForestClassifier(n_estimators=10, random_state=42, max_depth=3)
    clf.fit(X, y_encoded)

    # Predict probabilities
    y_pred = clf.predict_proba(X)

    # Compute AUC (one-vs-rest for multiclass)
    try:
        if len(np.unique(y_encoded)) == 2:
            auc = roc_auc_score(y_encoded, y_pred[:, 1])
        else:
            auc = roc_auc_score(y_encoded, y_pred, multi_class='ovr')
    except Exception as e:
        logger.warning(f"Failed to compute AUC: {e}")
        return 0.5

    return auc
