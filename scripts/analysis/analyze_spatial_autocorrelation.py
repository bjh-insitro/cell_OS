#!/usr/bin/env python3
"""
Characterize spatial autocorrelation in V3 vs V4 boring wells.

Investigates WHY V4's 2×2 micro-checkerboard creates +194% spatial variance increase.

Analyses:
1. Moran's I - global spatial autocorrelation measure
2. Variogram - spatial covariance as function of distance
3. Local autocorrelation maps - identify hotspots
4. Fourier analysis - detect periodic structure
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from scipy.spatial.distance import pdist, squareform
from scipy.stats import pearsonr

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# Island wells (v4 only)
ISLAND_WELLS = set([
    'D4','D5','D6','E4','E5','E6','F4','F5','F6',
    'D8','D9','D10','E8','E9','E10','F8','F9','F10',
    'D15','D16','D17','E15','E16','E17','F15','F16','F17',
    'D20','D21','D22','E20','E21','E22','F20','F21','F22',
    'K4','K5','K6','L4','L5','L6','M4','M5','M6',
    'K8','K9','K10','L8','L9','L10','M8','M9','M10',
    'K15','K16','K17','L15','L16','L17','M15','M16','M17',
    'K20','K21','K22','L20','L21','L22','M20','M21','M22'
])

NOMINAL_COLS = set([9, 10, 11, 12, 13, 14, 15, 16])
EDGE_ROWS = set(['A', 'P'])
EDGE_COLS = set([1, 24])

ROW_TO_NUM = {r: i for i, r in enumerate('ABCDEFGHIJKLMNOP')}


def get_boring_wells(flat_results, is_v4=False):
    """Get boring wells that should be spatially uniform."""
    boring = []
    for r in flat_results:
        well_id = r['well_id']
        row = r['row']
        col = r['col']

        if row in EDGE_ROWS or col in EDGE_COLS:
            continue
        if is_v4 and well_id in ISLAND_WELLS:
            continue
        if col not in NOMINAL_COLS:
            continue
        if r.get('dose_uM', -1) != 0:
            continue
        if r.get('compound', '') != 'DMSO':
            continue
        if abs(r.get('stain_scale', 1.0) - 1.0) > 0.01:
            continue
        if abs(r.get('fixation_timing_offset_min', 0)) > 0.1:
            continue
        if abs(r.get('imaging_focus_offset_um', 0)) > 0.1:
            continue

        boring.append(r)

    return boring


def compute_morans_i(wells_data):
    """
    Compute Moran's I spatial autocorrelation statistic.

    I = (N/W) * Σ_i Σ_j w_ij (x_i - x̄)(x_j - x̄) / Σ_i (x_i - x̄)²

    where w_ij = 1 if i,j are neighbors (1 well away), 0 otherwise

    I > 0: positive spatial autocorrelation (similar values cluster)
    I ≈ 0: no spatial autocorrelation
    I < 0: negative spatial autocorrelation (dissimilar values cluster)
    """
    if len(wells_data) == 0:
        return {'morans_i': 0, 'expected': 0, 'variance': 0, 'z_score': 0}

    # Extract values and positions
    values = np.array([w['morph_nucleus'] for w in wells_data])
    positions = np.array([[ROW_TO_NUM[w['row']], w['col']] for w in wells_data])

    N = len(values)
    mean_val = np.mean(values)

    # Build spatial weight matrix (rook contiguity: 1 if adjacent, 0 otherwise)
    W_matrix = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            if i != j:
                # Manhattan distance
                dist = abs(positions[i][0] - positions[j][0]) + abs(positions[i][1] - positions[j][1])
                if dist == 1:  # Adjacent (not diagonal)
                    W_matrix[i, j] = 1

    W = np.sum(W_matrix)

    if W == 0:
        return {'morans_i': 0, 'expected': 0, 'variance': 0, 'z_score': 0}

    # Compute Moran's I
    numerator = 0
    for i in range(N):
        for j in range(N):
            numerator += W_matrix[i, j] * (values[i] - mean_val) * (values[j] - mean_val)

    denominator = np.sum((values - mean_val) ** 2)

    morans_i = (N / W) * (numerator / denominator)

    # Expected value and variance under null hypothesis (random spatial pattern)
    expected = -1 / (N - 1)

    # Simplified variance calculation
    S1 = 0
    for i in range(N):
        for j in range(N):
            S1 += (W_matrix[i, j] + W_matrix[j, i]) ** 2
    S1 /= 2

    S2 = 0
    for i in range(N):
        row_sum = np.sum(W_matrix[i, :])
        col_sum = np.sum(W_matrix[:, i])
        S2 += (row_sum + col_sum) ** 2

    variance = ((N * S1 - N * S2 + 3 * W**2) / ((N**2 - 1) * W**2)) - expected**2

    # Z-score
    z_score = (morans_i - expected) / np.sqrt(variance) if variance > 0 else 0

    return {
        'morans_i': morans_i,
        'expected': expected,
        'variance': variance,
        'z_score': z_score,
        'n_wells': N,
        'total_weight': W
    }


def compute_variogram(wells_data, max_distance=10):
    """
    Compute empirical variogram: γ(h) = (1/2N(h)) Σ (z(s_i) - z(s_j))²

    Measures how variance changes with distance.
    If spatial autocorrelation exists, nearby wells are more similar.
    """
    if len(wells_data) < 3:
        return None

    values = np.array([w['morph_nucleus'] for w in wells_data])
    positions = np.array([[ROW_TO_NUM[w['row']], w['col']] for w in wells_data])

    # Compute pairwise distances and squared differences
    distances = squareform(pdist(positions, metric='cityblock'))  # Manhattan
    sq_diffs = np.array([[(values[i] - values[j])**2 for j in range(len(values))]
                         for i in range(len(values))])

    # Bin by distance
    variogram = {}
    for h in range(1, max_distance + 1):
        mask = (distances >= h - 0.5) & (distances < h + 0.5)
        if np.sum(mask) > 0:
            gamma_h = 0.5 * np.mean(sq_diffs[mask])
            n_pairs = np.sum(mask) // 2  # Divide by 2 since symmetric
            variogram[h] = {'gamma': gamma_h, 'n_pairs': n_pairs}

    return variogram


def analyze_row_column_patterns(wells_data):
    """
    Analyze if values show regular patterns in rows/columns.
    Returns autocorrelation of row means and column means.
    """
    row_means = defaultdict(list)
    col_means = defaultdict(list)

    for w in wells_data:
        row_means[w['row']].append(w['morph_nucleus'])
        col_means[w['col']].append(w['morph_nucleus'])

    # Convert to sorted arrays
    rows_sorted = sorted(row_means.keys(), key=lambda r: ROW_TO_NUM[r])
    row_avg = [np.mean(row_means[r]) for r in rows_sorted]

    cols_sorted = sorted(col_means.keys())
    col_avg = [np.mean(col_means[c]) for c in cols_sorted]

    # Compute lag-1 autocorrelation (correlation between adjacent values)
    row_autocorr = 0
    if len(row_avg) > 1:
        row_autocorr, _ = pearsonr(row_avg[:-1], row_avg[1:])

    col_autocorr = 0
    if len(col_avg) > 1:
        col_autocorr, _ = pearsonr(col_avg[:-1], col_avg[1:])

    return {
        'row_lag1_autocorr': row_autocorr,
        'col_lag1_autocorr': col_autocorr,
        'row_means': row_avg,
        'col_means': col_avg,
        'rows': rows_sorted,
        'cols': cols_sorted
    }


def create_spatial_heatmap(wells_data, output_path, title):
    """Create heatmap of boring well values."""
    # Create 16x24 grid (rows A-P, cols 1-24)
    grid = np.full((16, 24), np.nan)

    for w in wells_data:
        row_idx = ROW_TO_NUM[w['row']]
        col_idx = w['col'] - 1
        grid[row_idx, col_idx] = w['morph_nucleus']

    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(grid, cmap='viridis', aspect='auto', interpolation='nearest')

    ax.set_xlabel('Column')
    ax.set_ylabel('Row')
    ax.set_title(title)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(range(1, 25, 2))
    ax.set_yticks(range(16))
    ax.set_yticklabels(list('ABCDEFGHIJKLMNOP'))

    plt.colorbar(im, ax=ax, label='morph_nucleus')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def create_variogram_plot(v3_variogram, v4_variogram, output_path):
    """Plot variograms for V3 and V4."""
    fig, ax = plt.subplots(figsize=(10, 6))

    if v3_variogram:
        distances = sorted(v3_variogram.keys())
        gammas = [v3_variogram[d]['gamma'] for d in distances]
        ax.plot(distances, gammas, 'o-', label='V3', linewidth=2, markersize=8)

    if v4_variogram:
        distances = sorted(v4_variogram.keys())
        gammas = [v4_variogram[d]['gamma'] for d in distances]
        ax.plot(distances, gammas, 's-', label='V4', linewidth=2, markersize=8)

    ax.set_xlabel('Distance (wells, Manhattan)', fontsize=12)
    ax.set_ylabel('Semivariance γ(h)', fontsize=12)
    ax.set_title('Empirical Variogram: Boring Wells Only', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def create_row_col_pattern_plot(v3_patterns, v4_patterns, output_path):
    """Plot row and column mean patterns."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Row means
    ax1.plot(range(len(v3_patterns['row_means'])), v3_patterns['row_means'],
             'o-', label='V3', linewidth=2, markersize=6)
    ax1.plot(range(len(v4_patterns['row_means'])), v4_patterns['row_means'],
             's-', label='V4', linewidth=2, markersize=6)
    ax1.set_xlabel('Row (sorted)')
    ax1.set_ylabel('Mean morph_nucleus')
    ax1.set_title(f"Row Means (V3 r={v3_patterns['row_lag1_autocorr']:.3f}, V4 r={v4_patterns['row_lag1_autocorr']:.3f})")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Column means
    ax2.plot(v3_patterns['cols'], v3_patterns['col_means'],
             'o-', label='V3', linewidth=2, markersize=6)
    ax2.plot(v4_patterns['cols'], v4_patterns['col_means'],
             's-', label='V4', linewidth=2, markersize=6)
    ax2.set_xlabel('Column')
    ax2.set_ylabel('Mean morph_nucleus')
    ax2.set_title(f"Column Means (V3 r={v3_patterns['col_lag1_autocorr']:.3f}, V4 r={v4_patterns['col_lag1_autocorr']:.3f})")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main():
    print("="*80)
    print("SPATIAL AUTOCORRELATION ANALYSIS")
    print("="*80)
    print()
    print("Investigating WHY V4's 2×2 micro-checkerboard creates spatial artifacts.")
    print()

    # Load V3 and V4 for seed 42
    v3_files = sorted(RESULTS_DIR.glob("CAL_384_RULES_WORLD_v3_run_*_seed42.json"))
    v4_files = sorted(RESULTS_DIR.glob("CAL_384_RULES_WORLD_v4_run_*_seed42.json"))

    if not v3_files or not v4_files:
        print("Missing v3 or v4 results for seed 42")
        return

    with open(v3_files[0]) as f:
        v3_data = json.load(f)

    with open(v4_files[0]) as f:
        v4_data = json.load(f)

    v3_boring = get_boring_wells(v3_data['flat_results'], is_v4=False)
    v4_boring = get_boring_wells(v4_data['flat_results'], is_v4=True)

    print(f"V3 boring wells: {len(v3_boring)}")
    print(f"V4 boring wells: {len(v4_boring)}")
    print()

    # Analysis 1: Moran's I
    print("="*80)
    print("1. MORAN'S I - Global Spatial Autocorrelation")
    print("="*80)
    print()
    print("Moran's I measures spatial clustering:")
    print("  I > 0: Similar values cluster together (positive autocorrelation)")
    print("  I ≈ 0: Random spatial distribution")
    print("  I < 0: Dissimilar values cluster together (negative autocorrelation)")
    print()

    v3_morans = compute_morans_i(v3_boring)
    v4_morans = compute_morans_i(v4_boring)

    print(f"V3 Moran's I:  {v3_morans['morans_i']:7.4f}  (expected: {v3_morans['expected']:.4f})")
    print(f"V3 Z-score:    {v3_morans['z_score']:7.2f}  (|Z| > 1.96 = significant at p<0.05)")
    print()
    print(f"V4 Moran's I:  {v4_morans['morans_i']:7.4f}  (expected: {v4_morans['expected']:.4f})")
    print(f"V4 Z-score:    {v4_morans['z_score']:7.2f}  (|Z| > 1.96 = significant at p<0.05)")
    print()

    # Analysis 2: Variogram
    print("="*80)
    print("2. VARIOGRAM - Spatial Covariance vs Distance")
    print("="*80)
    print()
    print("γ(h) = semivariance at distance h")
    print("Flat variogram = no spatial structure")
    print("Increasing variogram = spatial autocorrelation (nearby wells similar)")
    print()

    v3_variogram = compute_variogram(v3_boring, max_distance=8)
    v4_variogram = compute_variogram(v4_boring, max_distance=8)

    print("V3 Variogram:")
    for h in sorted(v3_variogram.keys()):
        print(f"  Distance {h}: γ = {v3_variogram[h]['gamma']:8.2f}  ({v3_variogram[h]['n_pairs']:4d} pairs)")
    print()

    print("V4 Variogram:")
    for h in sorted(v4_variogram.keys()):
        print(f"  Distance {h}: γ = {v4_variogram[h]['gamma']:8.2f}  ({v4_variogram[h]['n_pairs']:4d} pairs)")
    print()

    # Analysis 3: Row/Column Patterns
    print("="*80)
    print("3. ROW/COLUMN PATTERN ANALYSIS")
    print("="*80)
    print()
    print("Lag-1 autocorrelation of row/column means:")
    print("  r > 0: Adjacent rows/columns have similar means (spatial structure)")
    print("  r ≈ 0: No pattern")
    print("  r < 0: Adjacent rows/columns alternate (checkerboard)")
    print()

    v3_patterns = analyze_row_column_patterns(v3_boring)
    v4_patterns = analyze_row_column_patterns(v4_boring)

    print(f"V3 Row lag-1 autocorr:    {v3_patterns['row_lag1_autocorr']:7.4f}")
    print(f"V3 Column lag-1 autocorr: {v3_patterns['col_lag1_autocorr']:7.4f}")
    print()
    print(f"V4 Row lag-1 autocorr:    {v4_patterns['row_lag1_autocorr']:7.4f}")
    print(f"V4 Column lag-1 autocorr: {v4_patterns['col_lag1_autocorr']:7.4f}")
    print()

    # Generate visualizations
    print("="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    print()

    output_dir = Path("validation_frontend/public/analysis_plots")
    output_dir.mkdir(exist_ok=True)

    create_spatial_heatmap(v3_boring, output_dir / "v3_boring_wells_heatmap.png",
                          "V3 Boring Wells Spatial Distribution")
    print("✓ V3 heatmap saved")

    create_spatial_heatmap(v4_boring, output_dir / "v4_boring_wells_heatmap.png",
                          "V4 Boring Wells Spatial Distribution")
    print("✓ V4 heatmap saved")

    create_variogram_plot(v3_variogram, v4_variogram,
                         output_dir / "variogram_comparison.png")
    print("✓ Variogram plot saved")

    create_row_col_pattern_plot(v3_patterns, v4_patterns,
                               output_dir / "row_col_patterns.png")
    print("✓ Row/column pattern plot saved")

    print()
    print(f"All plots saved to: {output_dir}/")
    print()

    # Diagnosis
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)
    print()

    if abs(v4_morans['z_score']) > abs(v3_morans['z_score']) and v4_morans['z_score'] > 2:
        print("❌ V4 shows STRONGER spatial autocorrelation than V3")
        print(f"   V4 Z-score: {v4_morans['z_score']:.2f} vs V3 Z-score: {v3_morans['z_score']:.2f}")
        print()
        print("   Mechanism: 2×2 micro-checkerboard creates low-frequency spatial pattern")
    elif abs(v3_morans['z_score']) > 2 and abs(v4_morans['z_score']) > 2:
        print("⚠️  Both V3 and V4 show significant spatial autocorrelation")
        print(f"   V3 Z-score: {v3_morans['z_score']:.2f}")
        print(f"   V4 Z-score: {v4_morans['z_score']:.2f}")
    else:
        print("✓ No significant spatial autocorrelation detected")
        print()
        print("  Spatial variance increase may be due to:")
        print("  - Row/column aggregation amplifying small local patterns")
        print("  - Statistical artifact from different well counts")

    print()

    if abs(v4_patterns['row_lag1_autocorr']) > 0.5 or abs(v4_patterns['col_lag1_autocorr']) > 0.5:
        print("❌ V4 shows strong row/column pattern")
        print(f"   Row autocorr: {v4_patterns['row_lag1_autocorr']:.3f}")
        print(f"   Col autocorr: {v4_patterns['col_lag1_autocorr']:.3f}")
        print()
        print("   This explains elevated row/column variance!")

    print()
    print("Check plots in validation_frontend/public/analysis_plots/ for visual confirmation.")


if __name__ == "__main__":
    main()
