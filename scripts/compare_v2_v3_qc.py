#!/usr/bin/env python3
"""
Compare QC metrics between CAL_384_RULES_WORLD_v2 and v3 across multiple seeds.

Analyzes:
1. Tile CV (replicate precision)
2. Z-factor (anchor quality)
3. Spatial effects (row/column variance)
4. Channel correlation (feature coupling)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

# Seeds to compare
SEEDS = [42, 123, 456, 789, 1000]

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# Tile regions (2x2 replicates)
TILE_REGIONS = [
    ['B2', 'B3', 'C2', 'C3'],  # TL-corner
    ['B22', 'B23', 'C22', 'C23'],  # TR-corner
    ['O2', 'O3', 'P2', 'P3'],  # BL-corner
    ['O22', 'O23', 'P22', 'P23'],  # BR-corner
    ['G2', 'G3', 'H2', 'H3'],  # Mid-L
    ['G22', 'G23', 'H22', 'H23'],  # Mid-R
    ['J2', 'J3', 'K2', 'K3'],  # Mid2-L
    ['J22', 'J23', 'K22', 'K23'],  # Mid2-R
]


def calculate_cv(values):
    """Calculate coefficient of variation."""
    if len(values) == 0:
        return 0.0
    mean = np.mean(values)
    if mean == 0:
        return 0.0
    std = np.std(values, ddof=1)
    return (std / mean) * 100


def calculate_z_factor(positive, negative):
    """Calculate Z-factor."""
    if len(positive) == 0 or len(negative) == 0:
        return -999

    mean_pos = np.mean(positive)
    mean_neg = np.mean(negative)
    std_pos = np.std(positive, ddof=1)
    std_neg = np.std(negative, ddof=1)

    denominator = abs(mean_pos - mean_neg)
    if denominator == 0:
        return -999

    return 1 - (3 * (std_pos + std_neg)) / denominator


def load_run(plate_id, seed):
    """Load run results."""
    # Find the run file
    pattern = f"{plate_id}_run_*_seed{seed}.json"
    files = list(RESULTS_DIR.glob(pattern))

    if not files:
        print(f"⚠️  Warning: No file found for {plate_id} seed {seed}")
        return None

    with open(files[0], 'r') as f:
        return json.load(f)


def analyze_tile_cv(data):
    """Analyze tile CV across all channels."""
    flat_results = data['flat_results']

    tile_cvs = []
    for tile_wells in TILE_REGIONS:
        tile_measurements = [r for r in flat_results if r['well_id'] in tile_wells]
        if len(tile_measurements) == 0:
            continue

        # Calculate CV for each channel
        for channel in ['morph_nucleus', 'morph_er', 'morph_actin', 'morph_mito', 'morph_rna']:
            values = [m[channel] for m in tile_measurements]
            cv = calculate_cv(values)
            tile_cvs.append(cv)

    return {
        'mean_cv': np.mean(tile_cvs) if tile_cvs else 0,
        'max_cv': np.max(tile_cvs) if tile_cvs else 0,
        'n_tiles': len(TILE_REGIONS)
    }


def analyze_anchor_z_factor(data):
    """Analyze Z-factor for anchors."""
    flat_results = data['flat_results']

    # Identify DMSO, MILD (dose=1), STRONG (dose=100)
    dmso_wells = [r for r in flat_results if r.get('dose_uM', 0) == 0 and r.get('compound') == 'DMSO']
    mild_wells = [r for r in flat_results if r.get('dose_uM', 0) == 0.3 and r.get('compound') == 'Nocodazole']
    strong_wells = [r for r in flat_results if r.get('dose_uM', 0) == 0.05 and r.get('compound') == 'Thapsigargin']

    z_factors = []

    # Calculate Z-factor for DNA channel (most robust)
    dmso_dna = [w['morph_nucleus'] for w in dmso_wells]
    mild_dna = [w['morph_nucleus'] for w in mild_wells]
    strong_dna = [w['morph_nucleus'] for w in strong_wells]

    if dmso_dna and mild_dna:
        z_mild = calculate_z_factor(mild_dna, dmso_dna)
        z_factors.append(z_mild)

    if dmso_dna and strong_dna:
        z_strong = calculate_z_factor(strong_dna, dmso_dna)
        z_factors.append(z_strong)

    return {
        'mean_z_factor': np.mean(z_factors) if z_factors else -999,
        'min_z_factor': np.min(z_factors) if z_factors else -999,
        'n_comparisons': len(z_factors)
    }


def analyze_spatial_variance(data):
    """Analyze spatial variance by row and column."""
    flat_results = data['flat_results']

    # Group by row
    row_means = defaultdict(list)
    for r in flat_results:
        row_means[r['row']].append(r['morph_nucleus'])

    row_avgs = [np.mean(vals) for vals in row_means.values()]
    row_variance = np.var(row_avgs, ddof=1) if len(row_avgs) > 1 else 0

    # Group by column
    col_means = defaultdict(list)
    for r in flat_results:
        col_means[r['col']].append(r['morph_nucleus'])

    col_avgs = [np.mean(vals) for vals in col_means.values()]
    col_variance = np.var(col_avgs, ddof=1) if len(col_avgs) > 1 else 0

    return {
        'row_variance': row_variance,
        'col_variance': col_variance,
        'total_spatial_var': row_variance + col_variance
    }


def analyze_channel_correlation(data):
    """Analyze channel correlation matrix."""
    flat_results = data['flat_results']

    channels = ['morph_nucleus', 'morph_er', 'morph_actin', 'morph_mito', 'morph_rna']

    # Build data matrix
    matrix = []
    for channel in channels:
        matrix.append([r[channel] for r in flat_results])

    matrix = np.array(matrix)

    # Calculate correlation matrix
    corr_matrix = np.corrcoef(matrix)

    # Get off-diagonal correlations (coupling between different channels)
    off_diag = []
    for i in range(len(channels)):
        for j in range(i+1, len(channels)):
            off_diag.append(abs(corr_matrix[i][j]))

    return {
        'mean_abs_correlation': np.mean(off_diag),
        'max_abs_correlation': np.max(off_diag),
        'n_pairs': len(off_diag)
    }


def main():
    print("="*80)
    print("V2 vs V3 Micro-Checkerboard QC Comparison")
    print("="*80)
    print()

    results_v2 = []
    results_v3 = []

    # Load all runs
    print("Loading runs...")
    for seed in SEEDS:
        v2_data = load_run("CAL_384_RULES_WORLD_v2", seed)
        v3_data = load_run("CAL_384_RULES_WORLD_v3", seed)

        if v2_data:
            results_v2.append({
                'seed': seed,
                'tile_cv': analyze_tile_cv(v2_data),
                'z_factor': analyze_anchor_z_factor(v2_data),
                'spatial': analyze_spatial_variance(v2_data),
                'correlation': analyze_channel_correlation(v2_data)
            })

        if v3_data:
            results_v3.append({
                'seed': seed,
                'tile_cv': analyze_tile_cv(v3_data),
                'z_factor': analyze_anchor_z_factor(v3_data),
                'spatial': analyze_spatial_variance(v3_data),
                'correlation': analyze_channel_correlation(v3_data)
            })

    print(f"✓ Loaded {len(results_v2)} v2 runs and {len(results_v3)} v3 runs")
    print()

    # 1. TILE CV COMPARISON
    print("="*80)
    print("1. REPLICATE PRECISION (Tile CV)")
    print("="*80)
    v2_cvs = [r['tile_cv']['mean_cv'] for r in results_v2]
    v3_cvs = [r['tile_cv']['mean_cv'] for r in results_v3]

    print(f"V2 Mean CV: {np.mean(v2_cvs):.2f}% ± {np.std(v2_cvs):.2f}%")
    print(f"V3 Mean CV: {np.mean(v3_cvs):.2f}% ± {np.std(v3_cvs):.2f}%")
    print(f"Δ (v3 - v2): {np.mean(v3_cvs) - np.mean(v2_cvs):+.2f}%")

    if np.mean(v3_cvs) < np.mean(v2_cvs):
        print("✅ V3 wins: Tighter replicates despite checkerboard")
    elif np.mean(v3_cvs) < np.mean(v2_cvs) + 2:
        print("⚠️  V3 comparable: Slight increase acceptable")
    else:
        print("❌ V2 wins: V3 checkerboard hurts reproducibility")
    print()

    # 2. Z-FACTOR COMPARISON
    print("="*80)
    print("2. ASSAY QUALITY (Z-Factor)")
    print("="*80)
    v2_z = [r['z_factor']['mean_z_factor'] for r in results_v2 if r['z_factor']['mean_z_factor'] > -999]
    v3_z = [r['z_factor']['mean_z_factor'] for r in results_v3 if r['z_factor']['mean_z_factor'] > -999]

    print(f"V2 Mean Z': {np.mean(v2_z):.3f} ± {np.std(v2_z):.3f}")
    print(f"V3 Mean Z': {np.mean(v3_z):.3f} ± {np.std(v3_z):.3f}")
    print(f"Δ (v3 - v2): {np.mean(v3_z) - np.mean(v2_z):+.3f}")

    if np.mean(v3_z) > 0.5 and np.mean(v2_z) > 0.5:
        print("✅ Both excellent: Z' > 0.5")
    elif np.mean(v3_z) >= np.mean(v2_z) - 0.1:
        print("⚠️  V3 comparable: Anchors still separable")
    else:
        print("❌ V2 wins: V3 degrades anchor quality")
    print()

    # 3. SPATIAL VARIANCE COMPARISON
    print("="*80)
    print("3. SPATIAL EFFECTS (Row/Column Variance)")
    print("="*80)
    v2_spatial = [r['spatial']['total_spatial_var'] for r in results_v2]
    v3_spatial = [r['spatial']['total_spatial_var'] for r in results_v3]

    print(f"V2 Total Spatial Var: {np.mean(v2_spatial):.4f} ± {np.std(v2_spatial):.4f}")
    print(f"V3 Total Spatial Var: {np.mean(v3_spatial):.4f} ± {np.std(v3_spatial):.4f}")
    print(f"Δ (v3 - v2): {np.mean(v3_spatial) - np.mean(v2_spatial):+.4f}")

    reduction_pct = ((np.mean(v2_spatial) - np.mean(v3_spatial)) / np.mean(v2_spatial)) * 100
    print(f"Reduction: {reduction_pct:.1f}%")

    if np.mean(v3_spatial) < np.mean(v2_spatial):
        print("✅ V3 wins: Decorrelated layout reduces spatial variance")
    else:
        print("⚠️  V2 wins: V3 doesn't improve spatial correction")
    print()

    # 4. CHANNEL CORRELATION COMPARISON
    print("="*80)
    print("4. CHANNEL COUPLING (Mean Abs Correlation)")
    print("="*80)
    v2_corr = [r['correlation']['mean_abs_correlation'] for r in results_v2]
    v3_corr = [r['correlation']['mean_abs_correlation'] for r in results_v3]

    print(f"V2 Mean |Corr|: {np.mean(v2_corr):.3f} ± {np.std(v2_corr):.3f}")
    print(f"V3 Mean |Corr|: {np.mean(v3_corr):.3f} ± {np.std(v3_corr):.3f}")
    print(f"Δ (v3 - v2): {np.mean(v3_corr) - np.mean(v2_corr):+.3f}")

    if abs(np.mean(v3_corr) - np.mean(v2_corr)) < 0.05:
        print("✅ No new artifacts: Correlations stable")
    elif np.mean(v3_corr) > np.mean(v2_corr):
        print("⚠️  V3 increases coupling: Potential neighbor artifact")
    else:
        print("✅ V3 reduces coupling: Unexpected benefit")
    print()

    # FINAL VERDICT
    print("="*80)
    print("FINAL VERDICT")
    print("="*80)

    v3_wins = 0
    v2_wins = 0
    ties = 0

    # Tile CV
    if abs(np.mean(v3_cvs) - np.mean(v2_cvs)) < 1:
        ties += 1
        print("Tile CV: ⚖️  Tie (within 1%)")
    elif np.mean(v3_cvs) < np.mean(v2_cvs):
        v3_wins += 1
        print("Tile CV: ✅ V3 wins")
    else:
        v2_wins += 1
        print("Tile CV: ❌ V2 wins")

    # Z-factor
    if abs(np.mean(v3_z) - np.mean(v2_z)) < 0.05:
        ties += 1
        print("Z-Factor: ⚖️  Tie (within 0.05)")
    elif np.mean(v3_z) > np.mean(v2_z):
        v3_wins += 1
        print("Z-Factor: ✅ V3 wins")
    else:
        v2_wins += 1
        print("Z-Factor: ❌ V2 wins")

    # Spatial variance
    if abs(reduction_pct) < 5:
        ties += 1
        print("Spatial Variance: ⚖️  Tie (within 5%)")
    elif np.mean(v3_spatial) < np.mean(v2_spatial):
        v3_wins += 1
        print("Spatial Variance: ✅ V3 wins")
    else:
        v2_wins += 1
        print("Spatial Variance: ❌ V2 wins")

    # Channel correlation
    if abs(np.mean(v3_corr) - np.mean(v2_corr)) < 0.03:
        ties += 1
        print("Channel Coupling: ⚖️  Tie (within 0.03)")
    elif np.mean(v3_corr) < np.mean(v2_corr):
        v3_wins += 1
        print("Channel Coupling: ✅ V3 wins")
    else:
        v2_wins += 1
        print("Channel Coupling: ❌ V2 wins")

    print()
    print(f"Score: V3={v3_wins}, V2={v2_wins}, Ties={ties}")
    print()

    if v3_wins > v2_wins:
        print("🏆 RECOMMENDATION: Adopt V3 micro-checkerboard")
        print("   V3 is strictly better. Retire v2.")
    elif v3_wins == v2_wins and v3_wins > 0:
        print("⚖️  RECOMMENDATION: V3 comparable, use for decorrelation studies")
        print("   Keep both: v2 as safe baseline, v3 for spatial tests.")
    else:
        print("🛡️  RECOMMENDATION: Keep V2 as primary")
        print("   V2 safer. V3 useful only if decorrelation needed.")


if __name__ == "__main__":
    main()
