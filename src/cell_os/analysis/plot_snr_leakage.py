"""
Visualization tools for SNR second-order leakage analysis.

Generates before/after plots showing:
1. QC-only separability (AUC per attack type)
2. QC feature embeddings (PCA/UMAP)
3. Mask pattern entropy
"""

import logging
from typing import Dict, List, Any, Tuple
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


def plot_leakage_auc_comparison(
    results_before: Dict[str, float],
    results_after: Dict[str, float],
    output_path: str = "snr_leakage_auc_comparison.png"
):
    """
    Plot before/after AUC comparison for all attack types.

    Args:
        results_before: Dict mapping attack type to AUC (before fix)
        results_after: Dict mapping attack type to AUC (after fix)
        output_path: Where to save the plot
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping plot")
        return

    attack_types = ["hover", "missingness", "qc_proxy", "spatial"]
    x = np.arange(len(attack_types))
    width = 0.35

    before_aucs = [results_before.get(att, 0.5) for att in attack_types]
    after_aucs = [results_after.get(att, 0.5) for att in attack_types]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars1 = ax.bar(x - width/2, before_aucs, width, label='Before (QC exposed)', color='#e74c3c', alpha=0.8)
    bars2 = ax.bar(x + width/2, after_aucs, width, label='After (QC stripped)', color='#27ae60', alpha=0.8)

    # Add threshold lines
    ax.axhline(y=0.6, color='black', linestyle='--', linewidth=1, label='Strict threshold (0.6)')
    ax.axhline(y=0.75, color='gray', linestyle='--', linewidth=1, label='Spatial threshold (0.75)')
    ax.axhline(y=0.5, color='blue', linestyle=':', linewidth=1, label='Random (0.5)')

    ax.set_xlabel('Attack Type', fontsize=12)
    ax.set_ylabel('AUC (QC-only features)', fontsize=12)
    ax.set_title('SNR Second-Order Leakage: Before vs After QC Stripping', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([att.replace('_', ' ').title() for att in attack_types])
    ax.legend(loc='upper right')
    ax.set_ylim([0.4, 1.05])
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.3f}',
                   ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    logger.info(f"Saved AUC comparison plot to {output_path}")
    plt.close()


def plot_qc_feature_embedding(
    conditions: List[Dict[str, Any]],
    qc_features_only: bool = True,
    output_path: str = "snr_leakage_qc_embedding.png"
):
    """
    Plot PCA embedding of QC features, colored by treatment.

    If features separate into clusters, there's leakage.

    Args:
        conditions: List of condition dicts with snr_policy metadata
        qc_features_only: If True, use only QC features (not morphology)
        output_path: Where to save the plot
    """
    try:
        import matplotlib.pyplot as plt
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        logger.warning("matplotlib or sklearn not available, skipping plot")
        return

    from src.cell_os.adversarial.snr_leakage_harness import extract_qc_features

    # Extract features and labels
    X = []
    y = []

    for cond in conditions:
        if qc_features_only:
            features = extract_qc_features(cond)
            X.append(list(features.values()))
        else:
            # Include morphology
            morphology = cond.get("feature_means", {})
            morphology_values = [v for v in morphology.values() if v is not None]
            qc_features = extract_qc_features(cond)
            X.append(morphology_values + list(qc_features.values()))

        y.append(cond.get("compound", "unknown"))

    X = np.array(X)

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # PCA to 2D
    if X.shape[1] > 2:
        pca = PCA(n_components=2)
        X_2d = pca.fit_transform(X)
        explained_var = pca.explained_variance_ratio_
    else:
        X_2d = X
        explained_var = [1.0, 0.0]

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))

    scatter = ax.scatter(X_2d[:, 0], X_2d[:, 1], c=y_encoded, cmap='tab10', s=100, alpha=0.7, edgecolors='black')

    ax.set_xlabel(f'PC1 ({explained_var[0]:.1%} variance)', fontsize=12)
    ax.set_ylabel(f'PC2 ({explained_var[1]:.1%} variance)', fontsize=12)
    title = "QC Features Only" if qc_features_only else "Morphology + QC Features"
    ax.set_title(f'SNR Leakage Embedding: {title}', fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)

    # Add legend with treatment names
    handles, labels = scatter.legend_elements()
    ax.legend(handles, le.classes_, title="Treatment", loc='best')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    logger.info(f"Saved QC embedding plot to {output_path}")
    plt.close()


def plot_mask_pattern_distribution(
    conditions: List[Dict[str, Any]],
    output_path: str = "snr_leakage_mask_patterns.png"
):
    """
    Plot distribution of channel masking patterns by treatment.

    Shows which channels are masked for each treatment.

    Args:
        conditions: List of condition dicts with snr_policy metadata
        output_path: Where to save the plot
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping plot")
        return

    channels = ["er", "mito", "nucleus", "actin", "rna"]

    # Extract mask patterns per treatment
    treatments = {}
    for cond in conditions:
        treatment = cond.get("compound", "unknown")
        if treatment not in treatments:
            treatments[treatment] = {ch: 0 for ch in channels}

        # Count how often each channel is masked
        snr = cond.get("snr_policy", {})
        masked = snr.get("masked_channels", [])
        for ch in masked:
            if ch in treatments[treatment]:
                treatments[treatment][ch] += 1

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(channels))
    width = 0.8 / len(treatments)

    for i, (treatment, mask_counts) in enumerate(treatments.items()):
        counts = [mask_counts[ch] for ch in channels]
        ax.bar(x + i * width, counts, width, label=treatment, alpha=0.8)

    ax.set_xlabel('Channel', fontsize=12)
    ax.set_ylabel('Number of times masked', fontsize=12)
    ax.set_title('Channel Masking Patterns by Treatment', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width * (len(treatments) - 1) / 2)
    ax.set_xticklabels(channels)
    ax.legend(title='Treatment', loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    logger.info(f"Saved mask pattern plot to {output_path}")
    plt.close()


def generate_leakage_report(
    results_before: Dict[str, float],
    results_after: Dict[str, float],
    conditions_before: Dict[str, List[Dict[str, Any]]],
    conditions_after: Dict[str, List[Dict[str, Any]]],
    output_dir: str = "."
):
    """
    Generate complete leakage analysis report with all plots.

    Args:
        results_before: AUC scores before fix (dict of attack -> AUC)
        results_after: AUC scores after fix
        conditions_before: Conditions with QC metadata (dict of attack -> conditions)
        conditions_after: Conditions with QC stripped
        output_dir: Directory to save plots
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Generating SNR leakage analysis report...")

    # Plot 1: AUC comparison
    plot_leakage_auc_comparison(
        results_before,
        results_after,
        str(output_path / "snr_leakage_auc_comparison.png")
    )

    # Plot 2: QC embeddings (before)
    for attack_type, conds in conditions_before.items():
        if len(conds) >= 2:  # Need at least 2 points for PCA
            plot_qc_feature_embedding(
                conds,
                qc_features_only=True,
                output_path=str(output_path / f"snr_leakage_qc_embedding_{attack_type}_before.png")
            )

    # Plot 3: Mask patterns (before)
    for attack_type, conds in conditions_before.items():
        if len(conds) >= 2:
            plot_mask_pattern_distribution(
                conds,
                output_path=str(output_path / f"snr_leakage_mask_patterns_{attack_type}.png")
            )

    logger.info(f"Leakage analysis report saved to {output_path}")

    # Print summary
    print("\n" + "="*80)
    print("SNR SECOND-ORDER LEAKAGE REPORT")
    print("="*80)
    print("\nAUC Scores (QC-only features):")
    print("-" * 80)
    print(f"{'Attack Type':<20} {'Before':<12} {'After':<12} {'Status':<12}")
    print("-" * 80)

    for attack_type in ["hover", "missingness", "qc_proxy", "spatial"]:
        before = results_before.get(attack_type, 0.5)
        after = results_after.get(attack_type, 0.5)
        threshold = 0.75 if attack_type == "spatial" else 0.6

        status = "✓ FIXED" if after < threshold else "✗ LEAKING"
        print(f"{attack_type.replace('_', ' ').title():<20} {before:<12.3f} {after:<12.3f} {status:<12}")

    print("-" * 80)
    print("\nPlots saved:")
    print(f"  - AUC comparison: {output_path / 'snr_leakage_auc_comparison.png'}")
    print(f"  - QC embeddings: {output_path / 'snr_leakage_qc_embedding_*_before.png'}")
    print(f"  - Mask patterns: {output_path / 'snr_leakage_mask_patterns_*.png'}")
    print("="*80 + "\n")
