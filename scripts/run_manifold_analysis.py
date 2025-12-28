#!/usr/bin/env python3
"""
Run manifold plate, apply calibration, and generate comprehensive geometry plots.

This script:
1. Executes the 384-well manifold plate
2. Applies calibration from bead plate
3. Generates PCA/UMAP raw vs calibrated
4. Generates dose trajectory plots
5. Generates direction cosine similarity heatmap
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

# Try to import UMAP, gracefully handle if not available
try:
    from umap import UMAP
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False
    print("Warning: UMAP not available. Install with: pip install umap-learn")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.plate_executor_v2 import execute_well, ParsedWell
from cell_os.hardware.run_context import RunContext
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.calibration.profile import CalibrationProfile
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# Worker process globals
_WORKER_VM = None
_WORKER_RUN_CONTEXT = None
_WORKER_BASE_SEED = None


def _init_worker(run_seed: int, base_seed: int):
    """Initialize worker process with VM and run context."""
    global _WORKER_VM, _WORKER_RUN_CONTEXT, _WORKER_BASE_SEED
    _WORKER_RUN_CONTEXT = RunContext.sample(seed=run_seed)
    _WORKER_BASE_SEED = base_seed
    _WORKER_VM = BiologicalVirtualMachine(seed=run_seed, run_context=_WORKER_RUN_CONTEXT)
    _WORKER_VM._load_cell_thalamus_params()


def execute_well_wrapper(well_dict):
    """Wrapper for multiprocessing - uses globals initialized in worker."""
    # Create ParsedWell from dict
    pw = ParsedWell(
        well_id=well_dict['well_id'],
        row=well_dict['well_pos'][0],
        col=int(well_dict['well_pos'][1:]),
        cell_line=well_dict['cell_line'],
        treatment=well_dict['compound'],
        reagent=well_dict['compound'],  # Same as treatment for simple case
        dose_uM=well_dict['dose_uM'],
        cell_density="NOMINAL",
        stain_scale=1.0,
        fixation_timing_offset_min=0.0,
        imaging_focus_offset_um=0.0,
        timepoint_hours=well_dict['timepoint_h'],
        exposure_multiplier=well_dict.get('exposure_multiplier', 1.0),
        mode="biological",
        material_assignment=None,
    )

    return execute_well(
        pw,
        _WORKER_VM,
        base_seed=_WORKER_BASE_SEED,
        run_context=_WORKER_RUN_CONTEXT,
        plate_id=well_dict.get('plate_id', 'ManifoldPlate_1')
    )


def execute_plate(design_path: str, output_dir: Path, seed: int):
    """Execute plate and return path to results."""
    print(f"\n=== Executing manifold plate ===")
    print(f"  Design: {design_path}")
    print(f"  Seed: {seed}")

    # Load design
    with open(design_path, 'r') as f:
        design = json.load(f)

    wells = design['wells']
    plate_id = wells[0]['plate_id'] if wells else "ManifoldPlate_1"

    # Execute wells in parallel
    n_workers = cpu_count()
    print(f"  Executing {len(wells)} wells with {n_workers} workers...")

    with Pool(n_workers, initializer=_init_worker, initargs=(seed, seed)) as pool:
        results = list(tqdm(
            pool.imap(execute_well_wrapper, wells, chunksize=10),
            total=len(wells),
            desc="Executing wells"
        ))

    # Package results
    output = {
        "design_id": design['design_id'],
        "seed": seed,
        "plate_id": plate_id,
        "n_wells": len(results),
        "raw_results": results,
        "metadata": design.get('metadata', {}),
    }

    # Save results
    results_path = output_dir / "plate_results.json"
    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"  Saved results: {results_path}")
    print(f"  Total wells executed: {len(results)}")

    return results_path


def apply_calibration(plate_path: Path, calibration_path: str, output_dir: Path):
    """Apply calibration and return path to calibrated results."""
    print(f"\n=== Applying calibration ===")
    print(f"  Calibration: {calibration_path}")

    # Load plate data
    with open(plate_path, 'r') as f:
        plate_data = json.load(f)

    # Load calibration profile
    profile = CalibrationProfile(calibration_path)

    # Apply calibration to raw_results
    calibrated_results = []
    for well in plate_data.get('raw_results', []):
        well_id = well['well_id']
        morph_raw = well.get('morphology', {})

        if not morph_raw:
            well_cal = well.copy()
            well_cal['morphology_corrected'] = {}
            well_cal['calibration_applied'] = False
            calibrated_results.append(well_cal)
            continue

        # Apply vignette correction
        morph_corrected = profile.correct_morphology(morph_raw, well_id)

        # Create calibrated well record
        well_cal = well.copy()
        well_cal['morphology_corrected'] = morph_corrected
        well_cal['calibration_applied'] = True

        calibrated_results.append(well_cal)

    # Create output with calibrated results
    output_data = plate_data.copy()
    output_data['raw_results'] = calibrated_results
    output_data['calibration_applied'] = True

    # Write output
    calibrated_path = output_dir / "plate_results_calibrated.json"
    with open(calibrated_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"  Saved calibrated results: {calibrated_path}")

    return calibrated_path


def load_morphology_data(plate_path: Path, use_calibrated: bool = False):
    """Load morphology features and metadata."""
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
            'compound': well.get('compound', 'Unknown'),
            'dose_uM': well.get('dose_uM', 0.0),
            'dose_multiplier': well.get('dose_multiplier', 0.0),
            'timepoint_h': well.get('timepoint_h', 24.0),
            'is_vehicle': well.get('is_vehicle', False),
        })

    return np.array(features), metadata


def compute_embeddings(features):
    """Compute PCA and UMAP embeddings."""
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # PCA
    pca = PCA(n_components=2)
    pca_coords = pca.fit_transform(features_scaled)
    pca_var = pca.explained_variance_ratio_

    # UMAP (if available)
    umap_coords = None
    if UMAP_AVAILABLE:
        umap_model = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
        umap_coords = umap_model.fit_transform(features_scaled)

    return {
        'pca': (pca_coords, pca_var),
        'umap': (umap_coords, None),
        'features_scaled': features_scaled,
    }


def plot_pca_umap_comparison(raw_data, cal_data, output_dir: Path):
    """Generate PCA and UMAP comparison plots (raw vs calibrated)."""
    print(f"\n=== Generating PCA/UMAP comparison plots ===")

    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Compute embeddings
    raw_emb = compute_embeddings(raw_features)
    cal_emb = compute_embeddings(cal_features)

    # Prepare colors for compounds
    all_compounds = sorted(set(m['compound'] for m in raw_meta))
    compound_colors = plt.cm.tab10(np.linspace(0, 1, len(all_compounds)))
    compound_color_map = {cpd: compound_colors[i] for i, cpd in enumerate(all_compounds)}

    cell_line_colors = {'A549': '#e41a1c', 'HepG2': '#377eb8'}

    # ===== PCA Plot =====
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    for row, (label, emb, meta) in enumerate([
        ('RAW', raw_emb['pca'], raw_meta),
        ('CALIBRATED', cal_emb['pca'], cal_meta)
    ]):
        coords, var_ratio = emb

        # Cell line colored
        ax = axes[row, 0]
        for cell_line in ['A549', 'HepG2']:
            mask = np.array([m['cell_line'] == cell_line for m in meta])
            if np.sum(mask) > 0:
                ax.scatter(coords[mask, 0], coords[mask, 1],
                          c=[cell_line_colors[cell_line]], label=cell_line,
                          alpha=0.6, s=30)
        ax.set_xlabel(f'PC1 ({var_ratio[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({var_ratio[1]*100:.1f}%)')
        ax.set_title(f'{label}: Cell Line')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Timepoint colored
        ax = axes[row, 1]
        for timepoint in [24.0, 48.0]:
            mask = np.array([m['timepoint_h'] == timepoint for m in meta])
            if np.sum(mask) > 0:
                ax.scatter(coords[mask, 0], coords[mask, 1],
                          label=f'{int(timepoint)}h', alpha=0.6, s=30)
        ax.set_xlabel(f'PC1 ({var_ratio[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({var_ratio[1]*100:.1f}%)')
        ax.set_title(f'{label}: Timepoint')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Compound colored
        ax = axes[row, 2]
        for compound in all_compounds[:8]:  # Show first 8 compounds
            mask = np.array([m['compound'] == compound for m in meta])
            if np.sum(mask) > 0:
                ax.scatter(coords[mask, 0], coords[mask, 1],
                          c=[compound_color_map[compound]], label=compound,
                          alpha=0.6, s=20)
        ax.set_xlabel(f'PC1 ({var_ratio[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({var_ratio[1]*100:.1f}%)')
        ax.set_title(f'{label}: Compound')
        ax.legend(fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    pca_path = output_dir / "pca_raw_vs_calibrated.png"
    plt.savefig(pca_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {pca_path}")
    plt.close()

    # ===== UMAP Plot (only if available) =====
    if UMAP_AVAILABLE and raw_emb['umap'][0] is not None:
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))

        for row, (label, emb, meta) in enumerate([
            ('RAW', raw_emb['umap'], raw_meta),
            ('CALIBRATED', cal_emb['umap'], cal_meta)
        ]):
            coords, _ = emb

            # Cell line colored
            ax = axes[row, 0]
            for cell_line in ['A549', 'HepG2']:
                mask = np.array([m['cell_line'] == cell_line for m in meta])
                if np.sum(mask) > 0:
                    ax.scatter(coords[mask, 0], coords[mask, 1],
                              c=[cell_line_colors[cell_line]], label=cell_line,
                              alpha=0.6, s=30)
            ax.set_xlabel('UMAP 1')
            ax.set_ylabel('UMAP 2')
            ax.set_title(f'{label}: Cell Line')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Timepoint colored
            ax = axes[row, 1]
            for timepoint in [24.0, 48.0]:
                mask = np.array([m['timepoint_h'] == timepoint for m in meta])
                if np.sum(mask) > 0:
                    ax.scatter(coords[mask, 0], coords[mask, 1],
                              label=f'{int(timepoint)}h', alpha=0.6, s=30)
            ax.set_xlabel('UMAP 1')
            ax.set_ylabel('UMAP 2')
            ax.set_title(f'{label}: Timepoint')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Compound colored
            ax = axes[row, 2]
            for compound in all_compounds[:8]:
                mask = np.array([m['compound'] == compound for m in meta])
                if np.sum(mask) > 0:
                    ax.scatter(coords[mask, 0], coords[mask, 1],
                              c=[compound_color_map[compound]], label=compound,
                              alpha=0.6, s=20)
            ax.set_xlabel('UMAP 1')
            ax.set_ylabel('UMAP 2')
            ax.set_title(f'{label}: Compound')
            ax.legend(fontsize=8, ncol=2)
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        umap_path = output_dir / "umap_raw_vs_calibrated.png"
        plt.savefig(umap_path, dpi=150, bbox_inches='tight')
        print(f"  Saved: {umap_path}")
        plt.close()
    else:
        print("  Skipping UMAP plot (UMAP not available)")


def plot_dose_trajectories(raw_data, cal_data, output_dir: Path):
    """Generate dose trajectory plots showing dose progression."""
    print(f"\n=== Generating dose trajectory plots ===")

    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Compute PCA for both
    raw_emb = compute_embeddings(raw_features)
    cal_emb = compute_embeddings(cal_features)

    # Get unique compounds (exclude vehicles)
    compounds = sorted(set(m['compound'] for m in raw_meta if not m['is_vehicle']))

    # Prepare colors
    compound_colors = plt.cm.tab10(np.linspace(0, 1, len(compounds)))
    compound_color_map = {cpd: compound_colors[i] for i, cpd in enumerate(compounds)}

    # ===== Dose Trajectories in PCA space =====
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for col, (label, emb, meta) in enumerate([
        ('RAW', raw_emb['pca'], raw_meta),
        ('CALIBRATED', cal_emb['pca'], cal_meta)
    ]):
        coords, var_ratio = emb
        ax = axes[col]

        # Plot all points in gray background
        ax.scatter(coords[:, 0], coords[:, 1], c='lightgray', alpha=0.2, s=10)

        # For each compound, compute dose centroids and connect
        for compound in compounds:
            mask = np.array([m['compound'] == compound and not m['is_vehicle'] for m in meta])
            if np.sum(mask) == 0:
                continue

            # Get doses and sort
            doses = sorted(set(m['dose_multiplier'] for i, m in enumerate(meta)
                             if mask[i] and m['dose_multiplier'] > 0))

            if len(doses) < 2:
                continue

            # Compute centroids for each dose
            centroids = []
            for dose in doses:
                dose_mask = mask & np.array([m['dose_multiplier'] == dose for m in meta])
                if np.sum(dose_mask) > 0:
                    centroids.append(np.mean(coords[dose_mask], axis=0))

            if len(centroids) < 2:
                continue

            centroids = np.array(centroids)
            color = compound_color_map[compound]

            # Plot trajectory
            ax.plot(centroids[:, 0], centroids[:, 1], 'o-',
                   color=color, linewidth=2, markersize=8,
                   label=compound, alpha=0.8)

            # Add arrow to show direction
            if len(centroids) >= 2:
                dx = centroids[-1, 0] - centroids[-2, 0]
                dy = centroids[-1, 1] - centroids[-2, 1]
                ax.arrow(centroids[-2, 0], centroids[-2, 1], dx*0.3, dy*0.3,
                        head_width=0.3, head_length=0.2, fc=color, ec=color, alpha=0.8)

        ax.set_xlabel(f'PC1 ({var_ratio[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({var_ratio[1]*100:.1f}%)')
        ax.set_title(f'{label}: Dose Trajectories')
        ax.legend(fontsize=8, ncol=2, loc='best')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    traj_path = output_dir / "dose_trajectories.png"
    plt.savefig(traj_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {traj_path}")
    plt.close()


def compute_direction_vectors(features, metadata):
    """Compute direction vectors from DMSO to high dose for each compound."""
    # Standardize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Get unique compounds (exclude vehicles)
    compounds = sorted(set(m['compound'] for m in metadata if not m['is_vehicle']))

    direction_vectors = {}

    for compound in compounds:
        # Get vehicle (dose=0) centroids for this compound
        vehicle_mask = np.array([
            m['compound'] == compound and m['is_vehicle']
            for m in metadata
        ])

        # Get high dose (max dose_multiplier) centroids
        max_dose = max(
            (m['dose_multiplier'] for m in metadata
             if m['compound'] == compound and not m['is_vehicle']),
            default=0
        )

        if max_dose == 0:
            continue

        high_dose_mask = np.array([
            m['compound'] == compound and m['dose_multiplier'] == max_dose
            for m in metadata
        ])

        if np.sum(vehicle_mask) == 0 or np.sum(high_dose_mask) == 0:
            continue

        # Compute centroids
        vehicle_centroid = np.mean(features_scaled[vehicle_mask], axis=0)
        high_dose_centroid = np.mean(features_scaled[high_dose_mask], axis=0)

        # Direction vector
        direction = high_dose_centroid - vehicle_centroid

        # Normalize
        direction_norm = direction / (np.linalg.norm(direction) + 1e-10)

        direction_vectors[compound] = direction_norm

    return direction_vectors


def plot_direction_cosine_heatmap(raw_data, cal_data, output_dir: Path):
    """Generate heatmap of cosine similarities between compound direction vectors."""
    print(f"\n=== Generating direction cosine heatmap ===")

    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Compute direction vectors
    raw_directions = compute_direction_vectors(raw_features, raw_meta)
    cal_directions = compute_direction_vectors(cal_features, cal_meta)

    # Compute cosine similarity matrices
    compounds = sorted(raw_directions.keys())

    def cosine_similarity_matrix(directions):
        n = len(compounds)
        matrix = np.zeros((n, n))
        for i, cpd1 in enumerate(compounds):
            for j, cpd2 in enumerate(compounds):
                vec1 = directions[cpd1]
                vec2 = directions[cpd2]
                matrix[i, j] = np.dot(vec1, vec2)
        return matrix

    raw_cosine = cosine_similarity_matrix(raw_directions)
    cal_cosine = cosine_similarity_matrix(cal_directions)

    # Plot side-by-side heatmaps
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax, cosine_mat, label in zip(axes, [raw_cosine, cal_cosine], ['RAW', 'CALIBRATED']):
        im = ax.imshow(cosine_mat, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        ax.set_xticks(range(len(compounds)))
        ax.set_yticks(range(len(compounds)))
        ax.set_xticklabels(compounds, rotation=45, ha='right', fontsize=9)
        ax.set_yticklabels(compounds, fontsize=9)
        ax.set_title(f'{label}: Direction Cosine Similarity')

        # Add colorbar
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        # Add text annotations
        for i in range(len(compounds)):
            for j in range(len(compounds)):
                text = ax.text(j, i, f'{cosine_mat[i, j]:.2f}',
                              ha="center", va="center", color="black", fontsize=7)

    plt.tight_layout()
    cosine_path = output_dir / "direction_cosine_heatmap.png"
    plt.savefig(cosine_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {cosine_path}")
    plt.close()


def compute_separation_metrics(raw_data, cal_data, output_dir: Path):
    """Compute quantitative separation metrics."""
    print(f"\n=== Computing separation metrics ===")

    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Compute embeddings
    raw_emb = compute_embeddings(raw_features)
    cal_emb = compute_embeddings(cal_features)

    metrics = {
        'raw': {},
        'calibrated': {},
    }

    for key, emb, meta in [
        ('raw', raw_emb, raw_meta),
        ('calibrated', cal_emb, cal_meta)
    ]:
        # Compute within-condition variance (tightness)
        compounds = set(m['compound'] for m in meta)
        within_var = []

        for compound in compounds:
            for dose in set(m['dose_multiplier'] for m in meta if m['compound'] == compound):
                mask = np.array([
                    m['compound'] == compound and m['dose_multiplier'] == dose
                    for m in meta
                ])
                if np.sum(mask) > 1:
                    coords = emb['pca'][0][mask]
                    centroid = np.mean(coords, axis=0)
                    var = np.mean(np.sum((coords - centroid) ** 2, axis=1))
                    within_var.append(var)

        metrics[key]['mean_within_condition_variance'] = float(np.mean(within_var))
        metrics[key]['median_within_condition_variance'] = float(np.median(within_var))

    # Save metrics
    metrics_path = output_dir / "separation_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"  Saved: {metrics_path}")
    print(f"  Raw mean within-condition variance: {metrics['raw']['mean_within_condition_variance']:.4f}")
    print(f"  Calibrated mean within-condition variance: {metrics['calibrated']['mean_within_condition_variance']:.4f}")

    variance_reduction = (
        (metrics['raw']['mean_within_condition_variance'] -
         metrics['calibrated']['mean_within_condition_variance']) /
        metrics['raw']['mean_within_condition_variance'] * 100
    )
    print(f"  Variance reduction: {variance_reduction:.1f}%")


def _pca_dimensionality(X: np.ndarray) -> dict:
    """Compute PCA dimensionality metrics for a feature matrix."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA

    Xs = StandardScaler().fit_transform(X)
    pca = PCA().fit(Xs)

    vr = pca.explained_variance_ratio_
    cv = np.cumsum(vr)

    # participation ratio (inverse Simpson)
    pr = float(1.0 / np.sum(vr ** 2))

    # optional: effective rank (exp entropy)
    eps = 1e-12
    erank = float(np.exp(-np.sum(vr * np.log(vr + eps))))

    n80 = int(np.argmax(cv >= 0.80) + 1)
    n95 = int(np.argmax(cv >= 0.95) + 1)

    return {
        "n_samples": int(X.shape[0]),
        "explained_variance_ratio": vr.tolist(),
        "cumulative_variance": cv.tolist(),
        "participation_ratio": pr,
        "effective_rank_exp": erank,
        "n_components_80pct": n80,
        "n_components_95pct": n95,
    }


def compute_axis_dimensionality_suite(raw_data, cal_data, output_dir: Path, plots_dir: Path):
    """Compute and plot axis dimensionality metrics."""
    print(f"\n=== Computing axis dimensionality ===")

    raw_features, raw_meta = raw_data
    cal_features, cal_meta = cal_data

    # Build dataframes for easier subsetting
    import pandas as pd

    df_raw = pd.DataFrame(raw_features, columns=['er', 'mito', 'nucleus', 'actin', 'rna'])
    for key in ['cell_line', 'timepoint_h', 'compound']:
        df_raw[key] = [m[key] for m in raw_meta]
    df_raw.rename(columns={'timepoint_h': 'timepoint_hours'}, inplace=True)

    df_cal = pd.DataFrame(cal_features, columns=['er', 'mito', 'nucleus', 'actin', 'rna'])
    for key in ['cell_line', 'timepoint_h', 'compound']:
        df_cal[key] = [m[key] for m in cal_meta]
    df_cal.rename(columns={'timepoint_h': 'timepoint_hours'}, inplace=True)

    FEATURES = ["er", "mito", "nucleus", "actin", "rna"]

    # Define subsets
    def _subset_dict(df: pd.DataFrame) -> dict:
        subsets = {"all": df}

        for cl in sorted(df["cell_line"].unique()):
            subsets[f"cell_line={cl}"] = df[df["cell_line"] == cl]

        for tp in sorted(df["timepoint_hours"].unique()):
            subsets[f"timepoint={tp}h"] = df[df["timepoint_hours"] == tp]

        # optional: 4-way
        for cl in sorted(df["cell_line"].unique()):
            for tp in sorted(df["timepoint_hours"].unique()):
                key = f"cell_line={cl}|timepoint={tp}h"
                subsets[key] = df[(df["cell_line"] == cl) & (df["timepoint_hours"] == tp)]

        # drop tiny subsets to avoid nonsense
        subsets = {k: v for k, v in subsets.items() if len(v) >= 10}
        return subsets

    subsets_raw = _subset_dict(df_raw)
    subsets_cal = _subset_dict(df_cal)

    metrics = {"raw": {}, "calibrated": {}}

    # Compute metrics
    for name, sdf in subsets_raw.items():
        X = sdf[FEATURES].to_numpy(dtype=float)
        metrics["raw"][name] = _pca_dimensionality(X)

    for name, sdf in subsets_cal.items():
        X = sdf[FEATURES].to_numpy(dtype=float)
        metrics["calibrated"][name] = _pca_dimensionality(X)

    # Write JSON
    metrics_path = output_dir / "axis_dimensionality_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"  Saved: {metrics_path}")

    # Print summary for key subsets
    for subset_name in ['all', 'cell_line=A549', 'cell_line=HepG2', 'timepoint=24.0h', 'timepoint=48.0h']:
        if subset_name in metrics['raw']:
            raw_m = metrics['raw'][subset_name]
            cal_m = metrics['calibrated'][subset_name]
            print(f"  {subset_name}:")
            print(f"    Raw: PR={raw_m['participation_ratio']:.2f}, 80%={raw_m['n_components_80pct']}PC, 95%={raw_m['n_components_95pct']}PC")
            print(f"    Cal: PR={cal_m['participation_ratio']:.2f}, 80%={cal_m['n_components_80pct']}PC, 95%={cal_m['n_components_95pct']}PC")

    # Plots only for "all" (clean overlays)
    all_raw = metrics["raw"]["all"]
    all_cal = metrics["calibrated"]["all"]

    # Scree plot
    vr_raw = np.array(all_raw["explained_variance_ratio"])
    vr_cal = np.array(all_cal["explained_variance_ratio"])
    n = min(len(vr_raw), len(vr_cal), 10)
    x = np.arange(1, n + 1)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, vr_raw[:n], marker="o", label="Raw", linewidth=2)
    ax.plot(x, vr_cal[:n], marker="o", label="Calibrated", linewidth=2)
    ax.set_xlabel("PC")
    ax.set_ylabel("Explained variance ratio")
    ax.set_title("PCA Scree Plot: Raw vs Calibrated")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    scree_path = plots_dir / "pca_scree_raw_vs_calibrated.png"
    plt.savefig(scree_path, dpi=200)
    plt.close()
    print(f"  Saved: {scree_path}")

    # Cumulative variance plot
    cv_raw = np.array(all_raw["cumulative_variance"])
    cv_cal = np.array(all_cal["cumulative_variance"])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, cv_raw[:n], marker="o", label="Raw", linewidth=2)
    ax.plot(x, cv_cal[:n], marker="o", label="Calibrated", linewidth=2)
    ax.axhline(0.80, linestyle="--", color="gray", alpha=0.5, label="80%")
    ax.axhline(0.95, linestyle="--", color="gray", alpha=0.5, label="95%")
    ax.set_xlabel("PC")
    ax.set_ylabel("Cumulative explained variance")
    ax.set_title("Cumulative Variance: Raw vs Calibrated")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    cum_path = plots_dir / "pca_cumulative_raw_vs_calibrated.png"
    plt.savefig(cum_path, dpi=200)
    plt.close()
    print(f"  Saved: {cum_path}")

    # Participation ratios across subsets
    keys = [k for k in metrics["raw"].keys() if k in metrics["calibrated"]]
    keys = sorted(keys, key=lambda s: (s != "all", s))  # put all first

    raw_pr = [metrics["raw"][k]["participation_ratio"] for k in keys]
    cal_pr = [metrics["calibrated"][k]["participation_ratio"] for k in keys]

    x_pos = np.arange(len(keys))
    w = 0.4

    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 0.6), 5))
    ax.bar(x_pos - w/2, raw_pr, width=w, label="Raw", alpha=0.8)
    ax.bar(x_pos + w/2, cal_pr, width=w, label="Calibrated", alpha=0.8)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(keys, rotation=45, ha="right")
    ax.set_ylabel("Participation ratio")
    ax.set_title("Participation Ratio by Subset")
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    pr_path = plots_dir / "participation_ratio_bars.png"
    plt.savefig(pr_path, dpi=200)
    plt.close()
    print(f"  Saved: {pr_path}")


def main():
    parser = argparse.ArgumentParser(description="Run manifold analysis with calibration")
    parser.add_argument('--design', required=True, help='Path to manifold plate design JSON')
    parser.add_argument('--calibration', required=True, help='Path to calibration report JSON')
    parser.add_argument('--output-dir', required=True, help='Output directory for results')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for execution')
    parser.add_argument('--skip-execution', action='store_true',
                       help='Skip plate execution (use existing results)')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    # Step 1: Execute plate (or skip if already done)
    if args.skip_execution:
        print("Skipping plate execution (using existing results)")
        results_path = output_dir / "plate_results.json"
        if not results_path.exists():
            raise FileNotFoundError(f"No existing results found at {results_path}")
    else:
        results_path = execute_plate(args.design, output_dir, args.seed)

    # Step 2: Apply calibration
    calibrated_path = apply_calibration(results_path, args.calibration, output_dir)

    # Step 3: Load morphology data
    print(f"\n=== Loading morphology data ===")
    raw_features, raw_meta = load_morphology_data(calibrated_path, use_calibrated=False)
    cal_features, cal_meta = load_morphology_data(calibrated_path, use_calibrated=True)
    print(f"  Raw: {len(raw_features)} wells")
    print(f"  Calibrated: {len(cal_features)} wells")

    # Check for errors in results
    if len(raw_features) == 0:
        with open(calibrated_path, 'r') as f:
            plate_data = json.load(f)

        # Check first few results for errors
        errors = [r.get('error') for r in plate_data.get('raw_results', [])[:5] if 'error' in r]
        if errors:
            print(f"\n❌ ERROR: No morphology data found. First errors:")
            for err in errors:
                print(f"  - {err}")
            raise RuntimeError("Execution failed - no morphology data available")
        else:
            raise RuntimeError("No morphology data found, but no obvious errors either")

    # Step 4: Generate plots
    plot_pca_umap_comparison((raw_features, raw_meta), (cal_features, cal_meta), plots_dir)
    plot_dose_trajectories((raw_features, raw_meta), (cal_features, cal_meta), plots_dir)
    plot_direction_cosine_heatmap((raw_features, raw_meta), (cal_features, cal_meta), plots_dir)

    # Step 5: Compute metrics
    compute_separation_metrics((raw_features, raw_meta), (cal_features, cal_meta), output_dir)
    compute_axis_dimensionality_suite((raw_features, raw_meta), (cal_features, cal_meta), output_dir, plots_dir)

    print(f"\n✅ Manifold analysis complete!")
    print(f"   Results: {output_dir}")
    print(f"   Plots: {plots_dir}")


if __name__ == '__main__':
    main()
