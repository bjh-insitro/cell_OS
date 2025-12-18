#!/usr/bin/env python3
"""
Visualize Mechanism Recovery: Why All Doses Fail and Mid-Dose Succeeds

Creates side-by-side PCA plots showing:
1. All doses mixed → classes overlap (death signature dominates)
2. Mid-dose 12h only → classes separate cleanly (adaptive responses visible)
3. High-dose 48h only → universal death signature (terminal attractor)
"""

import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from collections import defaultdict

DESIGN_ID = '204a9d65-d240-4123-bf65-99405b86a5b8'
DB_PATH = '/Users/bjh/cell_OS/data/cell_thalamus.db'

# Stress axis mapping and colors
STRESS_AXES = {
    'tBHQ': 'oxidative',
    'H2O2': 'oxidative',
    'tunicamycin': 'er_stress',
    'thapsigargin': 'er_stress',
    'CCCP': 'mitochondrial',
    'oligomycin': 'mitochondrial',
    'etoposide': 'dna_damage',
    'MG132': 'proteasome',
    'nocodazole': 'microtubule',
    'paclitaxel': 'microtubule',
}

STRESS_COLORS = {
    'er_stress': '#E74C3C',      # Red
    'mitochondrial': '#3498DB',   # Blue
    'oxidative': '#F39C12',       # Orange
    'proteasome': '#9B59B6',      # Purple
    'dna_damage': '#2ECC71',      # Green
    'microtubule': '#E67E22',     # Dark orange
}

EC50_MAP = {
    'tBHQ': 30.0, 'H2O2': 100.0, 'tunicamycin': 1.0, 'thapsigargin': 0.5,
    'CCCP': 5.0, 'oligomycin': 1.0, 'etoposide': 10.0, 'MG132': 1.0,
    'nocodazole': 0.5, 'paclitaxel': 0.01,
}

def load_and_filter(dose_filter='all', timepoint_filter=None):
    """Load morphology data with optional dose/timepoint filtering."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT compound, cell_line, timepoint_h, dose_uM,
               morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna
        FROM thalamus_results
        WHERE design_id = ? AND is_sentinel = 0 AND compound != 'DMSO' AND dose_uM > 0
    """, (DESIGN_ID,))

    rows = cursor.fetchall()
    conn.close()

    data = []
    metadata = []

    for row in rows:
        compound, cell_line, timepoint, dose, er, mito, nucleus, actin, rna = row

        # Timepoint filter
        if timepoint_filter is not None and timepoint != timepoint_filter:
            continue

        # Dose filter
        ec50 = EC50_MAP.get(compound)
        if ec50 is None:
            continue

        dose_ratio = dose / ec50

        if dose_filter == 'mid' and not (0.5 <= dose_ratio <= 2.0):
            continue
        elif dose_filter == 'high' and dose_ratio < 5.0:
            continue

        stress_axis = STRESS_AXES.get(compound, 'unknown')
        morph_vector = np.array([er, mito, nucleus, actin, rna])

        data.append(morph_vector)
        metadata.append({
            'compound': compound,
            'stress_axis': stress_axis,
            'cell_line': cell_line,
            'timepoint': timepoint,
            'dose_ratio': dose_ratio
        })

    return np.array(data), metadata

def compute_pca_and_separation(X, metadata):
    """Compute PCA and separation ratio."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)

    # Compute separation ratio
    centroids = defaultdict(lambda: {'pc1': [], 'pc2': []})
    for i, meta in enumerate(metadata):
        stress_axis = meta['stress_axis']
        centroids[stress_axis]['pc1'].append(X_pca[i, 0])
        centroids[stress_axis]['pc2'].append(X_pca[i, 1])

    within_var = 0
    between_var = 0
    global_centroid = X_pca.mean(axis=0)

    for stress_axis, data in centroids.items():
        class_centroid = np.array([np.mean(data['pc1']), np.mean(data['pc2'])])
        between_var += len(data['pc1']) * np.sum((class_centroid - global_centroid)**2)

        for i, meta in enumerate(metadata):
            if meta['stress_axis'] == stress_axis:
                point = X_pca[i]
                within_var += np.sum((point - class_centroid)**2)

    separation_ratio = between_var / (within_var + 1e-9)

    return X_pca, pca, centroids, separation_ratio

def plot_pca_panel(ax, X_pca, metadata, centroids, separation_ratio, title):
    """Plot a single PCA panel with class coloring."""
    # Plot points
    for stress_axis, color in STRESS_COLORS.items():
        mask = [meta['stress_axis'] == stress_axis for meta in metadata]
        if any(mask):
            indices = [i for i, m in enumerate(mask) if m]
            ax.scatter(X_pca[indices, 0], X_pca[indices, 1],
                      c=color, alpha=0.4, s=20, label=stress_axis)

    # Plot centroids
    for stress_axis, data in centroids.items():
        if stress_axis in STRESS_COLORS:
            centroid = np.array([np.mean(data['pc1']), np.mean(data['pc2'])])
            ax.scatter(centroid[0], centroid[1],
                      c=STRESS_COLORS[stress_axis],
                      marker='X', s=200, edgecolors='black', linewidths=2,
                      zorder=10)

    ax.set_xlabel('PC1', fontsize=11)
    ax.set_ylabel('PC2', fontsize=11)
    ax.set_title(f'{title}\nSeparation Ratio: {separation_ratio:.3f}',
                fontsize=12, fontweight='bold')
    ax.grid(alpha=0.3)
    ax.legend(loc='best', fontsize=8, framealpha=0.9)

# Create figure with 3 panels
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Panel 1: All doses (collapse)
print("Computing: All doses mixed...")
X_all, meta_all = load_and_filter(dose_filter='all')
X_pca_all, pca_all, centroids_all, sep_all = compute_pca_and_separation(X_all, meta_all)
plot_pca_panel(axes[0], X_pca_all, meta_all, centroids_all, sep_all,
              f'All Doses Mixed (n={len(X_all)})')

# Panel 2: Mid-dose 12h (separation)
print("Computing: Mid-dose 12h...")
X_mid, meta_mid = load_and_filter(dose_filter='mid', timepoint_filter=12.0)
X_pca_mid, pca_mid, centroids_mid, sep_mid = compute_pca_and_separation(X_mid, meta_mid)
plot_pca_panel(axes[1], X_pca_mid, meta_mid, centroids_mid, sep_mid,
              f'Mid-Dose 12h Only (n={len(X_mid)})')

# Panel 3: High-dose 48h (universal death)
print("Computing: High-dose 48h...")
X_high, meta_high = load_and_filter(dose_filter='high', timepoint_filter=48.0)
X_pca_high, pca_high, centroids_high, sep_high = compute_pca_and_separation(X_high, meta_high)
plot_pca_panel(axes[2], X_pca_high, meta_high, centroids_high, sep_high,
              f'High-Dose 48h Only (n={len(X_high)})')

plt.tight_layout()
plt.savefig('mechanism_separation_comparison.png', dpi=300, bbox_inches='tight')
print("\n✓ Saved: mechanism_separation_comparison.png")

# Print statistics
print("\n" + "="*80)
print("SEPARATION RATIO BREAKDOWN")
print("="*80)
print(f"All doses mixed:      {sep_all:.3f}  (classes overlap - death dominates)")
print(f"Mid-dose 12h only:    {sep_mid:.3f}  (classes separate - adaptive responses)")
print(f"High-dose 48h only:   {sep_high:.3f}  (universal death signature)")
print(f"\nImprovement: {sep_mid/sep_all:.1f}× better separation at mid-dose")
print("="*80)

# Print centroid distances
print("\n" + "="*80)
print("CENTROID DISTANCES (Euclidean in PC1-PC2 space)")
print("="*80)

def compute_pairwise_distances(centroids):
    """Compute average pairwise distance between class centroids."""
    axes = list(centroids.keys())
    distances = []
    for i, ax1 in enumerate(axes):
        for ax2 in axes[i+1:]:
            c1 = np.array([np.mean(centroids[ax1]['pc1']), np.mean(centroids[ax1]['pc2'])])
            c2 = np.array([np.mean(centroids[ax2]['pc1']), np.mean(centroids[ax2]['pc2'])])
            dist = np.linalg.norm(c1 - c2)
            distances.append(dist)
    return np.mean(distances)

print(f"All doses:    {compute_pairwise_distances(centroids_all):.2f} (avg pairwise)")
print(f"Mid-dose 12h: {compute_pairwise_distances(centroids_mid):.2f} (avg pairwise)")
print(f"High-dose 48h: {compute_pairwise_distances(centroids_high):.2f} (avg pairwise)")
print("="*80)
