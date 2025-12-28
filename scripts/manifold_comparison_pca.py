#!/usr/bin/env python3
"""
PCA Comparison: Raw vs Calibrated

Simple 2×3 grid showing PCA before and after calibration.
"""

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


def load_plate_data(plate_path: str, use_calibrated: bool = False):
    """Load morphology data from plate JSON (from raw_results)."""
    with open(plate_path, 'r') as f:
        plate_data = json.load(f)

    wells = plate_data.get('raw_results', [])
    morph_key = 'morphology_corrected' if use_calibrated else 'morphology'
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    features, metadata = [], []
    for well in wells:
        morph = well.get(morph_key, {})
        if not morph or any(morph.get(ch) is None for ch in channels):
            continue

        features.append([morph[ch] for ch in channels])
        metadata.append({
            'well_id': well['well_id'],
            'cell_line': well.get('cell_line', 'Unknown'),
            'reagent': well.get('compound', well.get('reagent', 'Unknown')).lower(),
            'dose_uM': well.get('dose_uM', 0),
        })

    return np.array(features), metadata


def compute_pca(features):
    """Compute PCA (2D)."""
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    pca = PCA(n_components=2)
    coords = pca.fit_transform(features_scaled)
    var_ratio = pca.explained_variance_ratio_

    return coords, var_ratio


def plot_comparison(raw_data, cal_data, output_path):
    """Create 2×3 comparison: raw (top) vs calibrated (bottom)."""
    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Compute PCA
    raw_pca, raw_var = compute_pca(raw_features)
    cal_pca, cal_var = compute_pca(cal_features)

    # Colors
    cell_line_colors = {'a549': '#e41a1c', 'hepg2': '#377eb8'}
    compound_colors = {'dmso': '#888888', 'nocodazole': '#4daf4a',
                      'thapsigargin': '#984ea3', 'tunicamycin': '#ff7f00'}

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # ===== ROW 1: RAW =====
    # Col 1: Cell line colored
    ax = axes[0, 0]
    for cell_line in ['a549', 'hepg2']:
        mask = np.array([m['cell_line'].lower() == cell_line for m in raw_meta])
        if np.sum(mask) > 0:
            ax.scatter(raw_pca[mask, 0], raw_pca[mask, 1],
                      c=cell_line_colors[cell_line], label=cell_line.upper(),
                      alpha=0.6, s=30)
    ax.set_xlabel(f'PC1 ({raw_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({raw_var[1]*100:.1f}%)')
    ax.set_title('RAW: Cell Line')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Col 2: Compound colored
    ax = axes[0, 1]
    for compound in ['dmso', 'nocodazole', 'thapsigargin', 'tunicamycin']:
        mask = np.array([m['reagent'] == compound for m in raw_meta])
        if np.sum(mask) > 0:
            ax.scatter(raw_pca[mask, 0], raw_pca[mask, 1],
                      c=compound_colors[compound], label=compound.capitalize(),
                      alpha=0.6, s=30)
    ax.set_xlabel(f'PC1 ({raw_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({raw_var[1]*100:.1f}%)')
    ax.set_title('RAW: Compound')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Col 3: Dose trajectories
    ax = axes[0, 2]
    ax.scatter(raw_pca[:, 0], raw_pca[:, 1], c='lightgray', alpha=0.3, s=10)
    for compound in ['nocodazole', 'thapsigargin', 'tunicamycin']:
        mask = np.array([m['reagent'] == compound for m in raw_meta])
        if np.sum(mask) == 0:
            continue

        doses = sorted(set(m['dose_uM'] for i, m in enumerate(raw_meta) if mask[i]))
        centroids = []
        for dose in doses:
            dose_mask = mask & np.array([m['dose_uM'] == dose for m in raw_meta])
            if np.sum(dose_mask) > 0:
                centroids.append(np.mean(raw_pca[dose_mask], axis=0))

        if len(centroids) > 1:
            centroids = np.array(centroids)
            ax.plot(centroids[:, 0], centroids[:, 1], 'o-',
                   color=compound_colors[compound], linewidth=2, markersize=8,
                   label=compound.capitalize())

    ax.set_xlabel(f'PC1 ({raw_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({raw_var[1]*100:.1f}%)')
    ax.set_title('RAW: Dose Trajectories')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # ===== ROW 2: CALIBRATED =====
    # Col 1: Cell line colored
    ax = axes[1, 0]
    for cell_line in ['a549', 'hepg2']:
        mask = np.array([m['cell_line'].lower() == cell_line for m in cal_meta])
        if np.sum(mask) > 0:
            ax.scatter(cal_pca[mask, 0], cal_pca[mask, 1],
                      c=cell_line_colors[cell_line], label=cell_line.upper(),
                      alpha=0.6, s=30)
    ax.set_xlabel(f'PC1 ({cal_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({cal_var[1]*100:.1f}%)')
    ax.set_title('CALIBRATED: Cell Line')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Col 2: Compound colored
    ax = axes[1, 1]
    for compound in ['dmso', 'nocodazole', 'thapsigargin', 'tunicamycin']:
        mask = np.array([m['reagent'] == compound for m in cal_meta])
        if np.sum(mask) > 0:
            ax.scatter(cal_pca[mask, 0], cal_pca[mask, 1],
                      c=compound_colors[compound], label=compound.capitalize(),
                      alpha=0.6, s=30)
    ax.set_xlabel(f'PC1 ({cal_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({cal_var[1]*100:.1f}%)')
    ax.set_title('CALIBRATED: Compound')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Col 3: Dose trajectories
    ax = axes[1, 2]
    ax.scatter(cal_pca[:, 0], cal_pca[:, 1], c='lightgray', alpha=0.3, s=10)
    for compound in ['nocodazole', 'thapsigargin', 'tunicamycin']:
        mask = np.array([m['reagent'] == compound for m in cal_meta])
        if np.sum(mask) == 0:
            continue

        doses = sorted(set(m['dose_uM'] for i, m in enumerate(cal_meta) if mask[i]))
        centroids = []
        for dose in doses:
            dose_mask = mask & np.array([m['dose_uM'] == dose for m in cal_meta])
            if np.sum(dose_mask) > 0:
                centroids.append(np.mean(cal_pca[dose_mask], axis=0))

        if len(centroids) > 1:
            centroids = np.array(centroids)
            ax.plot(centroids[:, 0], centroids[:, 1], 'o-',
                   color=compound_colors[compound], linewidth=2, markersize=8,
                   label=compound.capitalize())

    ax.set_xlabel(f'PC1 ({cal_var[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({cal_var[1]*100:.1f}%)')
    ax.set_title('CALIBRATED: Dose Trajectories')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--plate', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    print("Loading raw morphology...")
    raw_features, raw_meta = load_plate_data(args.plate, use_calibrated=False)
    print(f"  {len(raw_features)} wells")

    print("Loading calibrated morphology...")
    cal_features, cal_meta = load_plate_data(args.plate, use_calibrated=True)
    print(f"  {len(cal_features)} wells")

    print("Generating comparison plot...")
    plot_comparison((raw_features, raw_meta), (cal_features, cal_meta), args.output)


if __name__ == '__main__':
    main()
