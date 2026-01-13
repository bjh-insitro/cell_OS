#!/usr/bin/env python3
"""
Compare QC metrics between CAL_384_RULES_WORLD_v3 and v4 across multiple seeds.

Analyzes:
1. Tile CV (replicate precision) - separate for islands vs mixed tiles
2. Z-factor (anchor quality)
3. Spatial effects (row/column variance)
4. Channel correlation (feature coupling)

V4 adds: Island-specific CV analysis (homogeneous 3×3 tiles)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

# Seeds to compare
SEEDS = [42, 123, 456, 789, 1000]

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# Tile regions (2x2 replicates) - same for v3 and v4 mixed regions
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

# V4 Island regions (3x3 homogeneous tiles)
V4_ISLANDS = [
    ['D4', 'D5', 'D6', 'E4', 'E5', 'E6', 'F4', 'F5', 'F6'],  # CV_NW_HEPG2_VEH
    ['D8', 'D9', 'D10', 'E8', 'E9', 'E10', 'F8', 'F9', 'F10'],  # CV_NW_A549_VEH
    ['D15', 'D16', 'D17', 'E15', 'E16', 'E17', 'F15', 'F16', 'F17'],  # CV_NE_HEPG2_VEH
    ['D20', 'D21', 'D22', 'E20', 'E21', 'E22', 'F20', 'F21', 'F22'],  # CV_NE_A549_VEH
    ['K4', 'K5', 'K6', 'L4', 'L5', 'L6', 'M4', 'M5', 'M6'],  # CV_SW_HEPG2_MORPH
    ['K8', 'K9', 'K10', 'L8', 'L9', 'L10', 'M8', 'M9', 'M10'],  # CV_SW_A549_MORPH
    ['K15', 'K16', 'K17', 'L15', 'L16', 'L17', 'M15', 'M16', 'M17'],  # CV_SE_HEPG2_VEH
    ['K20', 'K21', 'K22', 'L20', 'L21', 'L22', 'M20', 'M21', 'M22'],  # CV_SE_A549_DEATH
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


def analyze_tile_cv(data, tile_regions):
    """Analyze tile CV across all channels for given regions."""
    flat_results = data['flat_results']

    tile_cvs = []
    for tile_wells in tile_regions:
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
        'n_tiles': len(tile_regions)
    }


def analyze_anchor_z_factor(data):
    """Analyze Z-factor for anchors."""
    flat_results = data['flat_results']

    # Identify DMSO, MILD (dose=0.3), STRONG (dose=0.05)
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
    print("V3 vs V4 Micro-Checkerboard + Islands QC Comparison")
    print("="*80)
    print()

    results_v3 = []
    results_v4 = []

    # Load all runs
    print("Loading runs...")
    for seed in SEEDS:
        v3_data = load_run("CAL_384_RULES_WORLD_v3", seed)
        v4_data = load_run("CAL_384_RULES_WORLD_v4", seed)

        if v3_data:
            results_v3.append({
                'seed': seed,
                'tile_cv': analyze_tile_cv(v3_data, TILE_REGIONS),
                'z_factor': analyze_anchor_z_factor(v3_data),
                'spatial': analyze_spatial_variance(v3_data),
                'correlation': analyze_channel_correlation(v3_data)
            })

        if v4_data:
            # For v4, analyze both mixed tiles and islands separately
            mixed_cv = analyze_tile_cv(v4_data, TILE_REGIONS)
            island_cv = analyze_tile_cv(v4_data, V4_ISLANDS)

            results_v4.append({
                'seed': seed,
                'tile_cv': mixed_cv,  # Mixed checkerboard regions
                'island_cv': island_cv,  # Homogeneous islands
                'z_factor': analyze_anchor_z_factor(v4_data),
                'spatial': analyze_spatial_variance(v4_data),
                'correlation': analyze_channel_correlation(v4_data)
            })

    print(f"✓ Loaded {len(results_v3)} v3 runs and {len(results_v4)} v4 runs")
    print()

    # 1. TILE CV COMPARISON (CRITICAL TEST)
    print("="*80)
    print("1. REPLICATE PRECISION (Tile CV)")
    print("="*80)
    v3_cvs = [r['tile_cv']['mean_cv'] for r in results_v3]
    v4_mixed_cvs = [r['tile_cv']['mean_cv'] for r in results_v4]
    v4_island_cvs = [r['island_cv']['mean_cv'] for r in results_v4]

    print(f"V3 Mixed Tiles (2x2):     {np.mean(v3_cvs):.2f}% ± {np.std(v3_cvs):.2f}%")
    print(f"V4 Mixed Tiles (2x2):     {np.mean(v4_mixed_cvs):.2f}% ± {np.std(v4_mixed_cvs):.2f}%")
    print(f"V4 Islands (3x3 homog):   {np.mean(v4_island_cvs):.2f}% ± {np.std(v4_island_cvs):.2f}%")
    print()
    print(f"Δ (v4_mixed - v3):        {np.mean(v4_mixed_cvs) - np.mean(v3_cvs):+.2f}%")
    print(f"Δ (v4_island - v3):       {np.mean(v4_island_cvs) - np.mean(v3_cvs):+.2f}%")
    print()

    if np.mean(v4_island_cvs) < np.mean(v3_cvs):
        print("✅ HYPOTHESIS CONFIRMED: Homogeneous islands reduce CV")
        print("   → Neighbor diversity was inflating v3 tile CV")
    else:
        print("❌ HYPOTHESIS REJECTED: Islands don't improve CV")
        print("   → Noise source is not neighbor coupling")
    print()

    # 2. Z-FACTOR COMPARISON
    print("="*80)
    print("2. ASSAY QUALITY (Z-Factor)")
    print("="*80)
    v3_z = [r['z_factor']['mean_z_factor'] for r in results_v3 if r['z_factor']['mean_z_factor'] > -999]
    v4_z = [r['z_factor']['mean_z_factor'] for r in results_v4 if r['z_factor']['mean_z_factor'] > -999]

    print(f"V3 Mean Z': {np.mean(v3_z):.3f} ± {np.std(v3_z):.3f}")
    print(f"V4 Mean Z': {np.mean(v4_z):.3f} ± {np.std(v4_z):.3f}")
    print(f"Δ (v4 - v3): {np.mean(v4_z) - np.mean(v3_z):+.3f}")

    if abs(np.mean(v4_z) - np.mean(v3_z)) < 0.1:
        print("✅ Anchors stable: Islands don't degrade anchor separability")
    elif np.mean(v4_z) > np.mean(v3_z):
        print("✅ V4 improves: Better anchor separation with islands")
    else:
        print("⚠️  V4 degrades: Islands may interfere with anchors")
    print()

    # 3. SPATIAL VARIANCE COMPARISON
    print("="*80)
    print("3. SPATIAL EFFECTS (Row/Column Variance)")
    print("="*80)
    v3_spatial = [r['spatial']['total_spatial_var'] for r in results_v3]
    v4_spatial = [r['spatial']['total_spatial_var'] for r in results_v4]

    print(f"V3 Total Spatial Var: {np.mean(v3_spatial):.4f} ± {np.std(v3_spatial):.4f}")
    print(f"V4 Total Spatial Var: {np.mean(v4_spatial):.4f} ± {np.std(v4_spatial):.4f}")
    print(f"Δ (v4 - v3): {np.mean(v4_spatial) - np.mean(v3_spatial):+.4f}")

    change_pct = ((np.mean(v4_spatial) - np.mean(v3_spatial)) / np.mean(v3_spatial)) * 100
    print(f"Change: {change_pct:+.1f}%")

    if abs(change_pct) < 5:
        print("✅ Spatial variance preserved: V4 islands don't break decorrelation")
    elif change_pct < 0:
        print("✅ Spatial variance improved: V4 even better than v3")
    else:
        print("⚠️  Spatial variance increased: Islands may introduce new artifacts")
    print()

    # 4. CHANNEL CORRELATION COMPARISON
    print("="*80)
    print("4. CHANNEL COUPLING (Mean Abs Correlation)")
    print("="*80)
    v3_corr = [r['correlation']['mean_abs_correlation'] for r in results_v3]
    v4_corr = [r['correlation']['mean_abs_correlation'] for r in results_v4]

    print(f"V3 Mean |Corr|: {np.mean(v3_corr):.3f} ± {np.std(v3_corr):.3f}")
    print(f"V4 Mean |Corr|: {np.mean(v4_corr):.3f} ± {np.std(v4_corr):.3f}")
    print(f"Δ (v4 - v3): {np.mean(v4_corr) - np.mean(v3_corr):+.3f}")

    if abs(np.mean(v4_corr) - np.mean(v3_corr)) < 0.03:
        print("✅ Correlations stable: No new coupling artifacts")
    print()

    # FINAL VERDICT
    print("="*80)
    print("FINAL VERDICT")
    print("="*80)

    island_win = np.mean(v4_island_cvs) < np.mean(v3_cvs)
    spatial_preserved = abs(change_pct) < 10

    print()
    if island_win and spatial_preserved:
        print("🏆 V4 SUCCEEDS: Islands improve CV while preserving spatial decorrelation")
        print()
        print("Key findings:")
        print(f"  • Island CV: {np.mean(v4_island_cvs):.1f}% (vs v3: {np.mean(v3_cvs):.1f}%)")
        print(f"  • Spatial variance: {np.mean(v4_spatial):.0f} ({change_pct:+.1f}% from v3)")
        print(f"  • Hypothesis: Neighbor coupling was inflating v3 CV ✓")
        print()
        print("Recommendation: Adopt V4 as default calibration plate")
    elif island_win:
        print("⚖️  V4 PARTIAL WIN: Islands improve CV but affect spatial model")
        print()
        print("Key findings:")
        print(f"  • Island CV: {np.mean(v4_island_cvs):.1f}% (better than v3)")
        print(f"  • Spatial variance: {change_pct:+.1f}% change (>10% threshold)")
        print()
        print("Recommendation: Investigate why islands affect global spatial structure")
    else:
        print("❌ V4 HYPOTHESIS REJECTED: Islands don't improve CV")
        print()
        print("Key findings:")
        print(f"  • Island CV: {np.mean(v4_island_cvs):.1f}% (not better than v3: {np.mean(v3_cvs):.1f}%)")
        print(f"  • Neighbor coupling is NOT the dominant noise source")
        print()
        print("Recommendation: Keep v3, investigate other noise sources (segmentation, extraction)")


if __name__ == "__main__":
    main()
