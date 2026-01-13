#!/usr/bin/env python3
"""
Manifold Analysis: Raw vs Calibrated Comparison

Generates side-by-side comparison of raw vs calibrated morphology in PCA and UMAP space.

Output: 2×3 grid plot
- Top row: Raw morphology
- Bottom row: Calibrated morphology
- Columns: PCA (cell line colored), UMAP (compound colored), UMAP (dose trajectories)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_plate_data(plate_path: str, use_calibrated: bool = False):
    """Load morphology data from plate JSON."""
    with open(plate_path, 'r') as f:
        plate_data = json.load(f)

    wells = plate_data['parsed_wells']

    # Extract features
    morph_key = 'morphology_corrected' if use_calibrated else 'morphology'
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    features = []
    metadata = []

    for well in wells:
        morph = well.get(morph_key, well.get('morphology', {}))
        if not morph or any(morph.get(ch) is None for ch in channels):
            continue  # Skip wells with missing data

        # Extract feature vector
        feat = [morph[ch] for ch in channels]
        features.append(feat)

        # Extract metadata
        metadata.append({
            'well_id': well['well_id'],
            'cell_line': well.get('cell_line', 'Unknown'),
            'treatment': well.get('treatment', 'Unknown'),
            'reagent': well.get('reagent', 'Unknown'),
            'dose_uM': well.get('dose_uM', 0),
        })

    return np.array(features), metadata


def compute_embeddings(features, random_state=42):
    """Compute PCA embeddings (2D and 3D for different views)."""
    # Standardize
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # PCA (2D)
    pca_2d = PCA(n_components=2, random_state=random_state)
    pca_coords_2d = pca_2d.fit_transform(features_scaled)
    var_2d = pca_2d.explained_variance_ratio_

    # PCA (3D for PC2 vs PC3 view)
    pca_3d = PCA(n_components=3, random_state=random_state)
    pca_coords_3d = pca_3d.fit_transform(features_scaled)
    var_3d = pca_3d.explained_variance_ratio_

    return pca_coords_2d, pca_coords_3d, var_2d, var_3d


def plot_comparison(raw_data, calibrated_data, output_path):
    """
    Create 2×3 comparison plot: raw vs calibrated.

    Columns:
    1. PCA PC1 vs PC2 (colored by cell line)
    2. PCA PC1 vs PC2 (colored by compound)
    3. PCA PC1 vs PC2 with dose trajectories (centroids + lines)
    """
    raw_features, raw_metadata = raw_data
    cal_features, cal_metadata = calibrated_data

    # Compute embeddings
    raw_pca_2d, raw_pca_3d, raw_var_2d, raw_var_3d = compute_embeddings(raw_features)
    cal_pca_2d, cal_pca_3d, cal_var_2d, cal_var_3d = compute_embeddings(cal_features)

    # Create figure
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Color schemes
    cell_line_colors = {'A549': '#e41a1c', 'HepG2': '#377eb8'}
    compound_colors = {
        'DMSO': '#888888',
        'nocodazole': '#4daf4a',
        'thapsigargin': '#984ea3',
        'tunicamycin': '#ff7f00',
    }

    # ===== ROW 1: RAW =====
    row_title = "RAW"

    # Column 1: PCA (cell line colored)
    ax = axes[0, 0]
    for cell_line in ['A549', 'HepG2']:
        mask = np.array([m['cell_line'] == cell_line for m in raw_metadata])
        if np.sum(mask) > 0:
            ax.scatter(raw_pca[mask, 0], raw_pca[mask, 1],
                      c=cell_line_colors[cell_line], label=cell_line, alpha=0.6, s=20)
    ax.set_xlabel(f'PC1 ({raw_pca_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({raw_pca_var[1]*100:.1f}%)')
    ax.set_title(f'{row_title}: PCA (Cell Line)')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    # Column 2: UMAP (compound colored)
    ax = axes[0, 1]
    for compound in ['DMSO', 'nocodazole', 'thapsigargin', 'tunicamycin']:
        compound_lower = compound.lower()
        mask = np.array([m['reagent'].lower() == compound_lower for m in raw_metadata])
        if np.sum(mask) > 0:
            ax.scatter(raw_umap[mask, 0], raw_umap[mask, 1],
                      c=compound_colors[compound], label=compound, alpha=0.6, s=20)
    ax.set_xlabel('UMAP 1')
    ax.set_ylabel('UMAP 2')
    ax.set_title(f'{row_title}: UMAP (Compound)')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    # Column 3: UMAP with dose trajectories
    ax = axes[0, 2]
    # Plot all points in gray
    ax.scatter(raw_umap[:, 0], raw_umap[:, 1], c='lightgray', alpha=0.3, s=10)

    # For each compound, compute centroids at each dose and draw trajectories
    for compound in ['nocodazole', 'thapsigargin', 'tunicamycin']:
        compound_lower = compound.lower()
        compound_mask = np.array([m['reagent'].lower() == compound_lower for m in raw_metadata])

        if np.sum(compound_mask) == 0:
            continue

        # Get unique doses
        doses = sorted(set(m['dose_uM'] for i, m in enumerate(raw_metadata) if compound_mask[i]))

        # Compute centroids for each dose
        centroids = []
        for dose in doses:
            dose_mask = compound_mask & np.array([m['dose_uM'] == dose for m in raw_metadata])
            if np.sum(dose_mask) > 0:
                centroid = np.mean(raw_umap[dose_mask], axis=0)
                centroids.append(centroid)

        if len(centroids) > 1:
            centroids = np.array(centroids)
            ax.plot(centroids[:, 0], centroids[:, 1], 'o-',
                   color=compound_colors[compound], linewidth=2, markersize=8,
                   label=compound, alpha=0.8)

    ax.set_xlabel('UMAP 1')
    ax.set_ylabel('UMAP 2')
    ax.set_title(f'{row_title}: Dose Trajectories')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    # ===== ROW 2: CALIBRATED =====
    row_title = "CALIBRATED"

    # Column 1: PCA (cell line colored)
    ax = axes[1, 0]
    for cell_line in ['A549', 'HepG2']:
        mask = np.array([m['cell_line'] == cell_line for m in cal_metadata])
        if np.sum(mask) > 0:
            ax.scatter(cal_pca[mask, 0], cal_pca[mask, 1],
                      c=cell_line_colors[cell_line], label=cell_line, alpha=0.6, s=20)
    ax.set_xlabel(f'PC1 ({cal_pca_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({cal_pca_var[1]*100:.1f}%)')
    ax.set_title(f'{row_title}: PCA (Cell Line)')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    # Column 2: UMAP (compound colored)
    ax = axes[1, 1]
    for compound in ['DMSO', 'nocodazole', 'thapsigargin', 'tunicamycin']:
        compound_lower = compound.lower()
        mask = np.array([m['reagent'].lower() == compound_lower for m in cal_metadata])
        if np.sum(mask) > 0:
            ax.scatter(cal_umap[mask, 0], cal_umap[mask, 1],
                      c=compound_colors[compound], label=compound, alpha=0.6, s=20)
    ax.set_xlabel('UMAP 1')
    ax.set_ylabel('UMAP 2')
    ax.set_title(f'{row_title}: UMAP (Compound)')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    # Column 3: UMAP with dose trajectories
    ax = axes[1, 2]
    # Plot all points in gray
    ax.scatter(cal_umap[:, 0], cal_umap[:, 1], c='lightgray', alpha=0.3, s=10)

    # For each compound, compute centroids at each dose and draw trajectories
    for compound in ['nocodazole', 'thapsigargin', 'tunicamycin']:
        compound_lower = compound.lower()
        compound_mask = np.array([m['reagent'].lower() == compound_lower for m in cal_metadata])

        if np.sum(compound_mask) == 0:
            continue

        # Get unique doses
        doses = sorted(set(m['dose_uM'] for i, m in enumerate(cal_metadata) if compound_mask[i]))

        # Compute centroids for each dose
        centroids = []
        for dose in doses:
            dose_mask = compound_mask & np.array([m['dose_uM'] == dose for m in cal_metadata])
            if np.sum(dose_mask) > 0:
                centroid = np.mean(cal_umap[dose_mask], axis=0)
                centroids.append(centroid)

        if len(centroids) > 1:
            centroids = np.array(centroids)
            ax.plot(centroids[:, 0], centroids[:, 1], 'o-',
                   color=compound_colors[compound], linewidth=2, markersize=8,
                   label=compound, alpha=0.8)

    ax.set_xlabel('UMAP 1')
    ax.set_ylabel('UMAP 2')
    ax.set_title(f'{row_title}: Dose Trajectories')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved comparison plot: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Manifold comparison: raw vs calibrated")
    parser.add_argument('--plate', required=True, help='Plate JSON (with calibrated morphology)')
    parser.add_argument('--output', required=True, help='Output PNG path')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')

    args = parser.parse_args()

    print("Loading raw morphology...")
    raw_features, raw_metadata = load_plate_data(args.plate, use_calibrated=False)
    print(f"  {len(raw_features)} wells loaded")

    print("Loading calibrated morphology...")
    cal_features, cal_metadata = load_plate_data(args.plate, use_calibrated=True)
    print(f"  {len(cal_features)} wells loaded")

    print("Computing embeddings and generating comparison plot...")
    plot_comparison(
        (raw_features, raw_metadata),
        (cal_features, cal_metadata),
        args.output
    )


if __name__ == '__main__':
    main()
