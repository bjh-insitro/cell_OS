#!/usr/bin/env python3
"""
Diagnose V4 spatial variance increase by masking islands.

Tests:
1. Spatial variance on ALL wells (original method)
2. Spatial variance on NON-ISLAND wells only (masked)
3. Spatial variance on ISLAND wells only (isolation check)

Hypothesis: Islands contaminate spatial variance because they're:
- Clustered spatially (quadrants)
- Forced NOMINAL density (neighbors have gradients)
- Homogeneous (neighbors are mixed)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V4 Island wells (all 72)
ISLAND_WELLS = set([
    # CV_NW_HEPG2_VEH
    'D4', 'D5', 'D6', 'E4', 'E5', 'E6', 'F4', 'F5', 'F6',
    # CV_NW_A549_VEH
    'D8', 'D9', 'D10', 'E8', 'E9', 'E10', 'F8', 'F9', 'F10',
    # CV_NE_HEPG2_VEH
    'D15', 'D16', 'D17', 'E15', 'E16', 'E17', 'F15', 'F16', 'F17',
    # CV_NE_A549_VEH
    'D20', 'D21', 'D22', 'E20', 'E21', 'E22', 'F20', 'F21', 'F22',
    # CV_SW_HEPG2_MORPH
    'K4', 'K5', 'K6', 'L4', 'L5', 'L6', 'M4', 'M5', 'M6',
    # CV_SW_A549_MORPH
    'K8', 'K9', 'K10', 'L8', 'L9', 'L10', 'M8', 'M9', 'M10',
    # CV_SE_HEPG2_VEH
    'K15', 'K16', 'K17', 'L15', 'L16', 'L17', 'M15', 'M16', 'M17',
    # CV_SE_A549_DEATH
    'K20', 'K21', 'K22', 'L20', 'L21', 'L22', 'M20', 'M21', 'M22'
])


def analyze_spatial_variance(flat_results, well_filter=None):
    """
    Analyze spatial variance by row and column.

    Args:
        flat_results: List of well measurements
        well_filter: Optional set of well_ids to include (None = all)
    """
    if well_filter is not None:
        flat_results = [r for r in flat_results if r['well_id'] in well_filter]

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
        'total_spatial_var': row_variance + col_variance,
        'n_wells': len(flat_results)
    }


def main():
    print("="*80)
    print("V4 Spatial Variance Diagnosis (Masked Analysis)")
    print("="*80)
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

    v3_results = v3_data['flat_results']
    v4_results = v4_data['flat_results']

    # Get non-island wells for v4
    all_v4_wells = set(r['well_id'] for r in v4_results)
    non_island_wells = all_v4_wells - ISLAND_WELLS

    print(f"V4 well breakdown:")
    print(f"  Total: {len(all_v4_wells)} wells")
    print(f"  Islands: {len(ISLAND_WELLS)} wells")
    print(f"  Non-islands: {len(non_island_wells)} wells")
    print()

    # Analysis 1: All wells (original method)
    print("="*80)
    print("1. SPATIAL VARIANCE - ALL WELLS (Original Method)")
    print("="*80)

    v3_all = analyze_spatial_variance(v3_results)
    v4_all = analyze_spatial_variance(v4_results)

    print(f"V3 (all wells):      {v3_all['total_spatial_var']:.2f}")
    print(f"V4 (all wells):      {v4_all['total_spatial_var']:.2f}")
    print(f"Δ (v4 - v3):         {v4_all['total_spatial_var'] - v3_all['total_spatial_var']:+.2f}")
    print(f"Change:              {((v4_all['total_spatial_var'] - v3_all['total_spatial_var']) / v3_all['total_spatial_var'] * 100):+.1f}%")
    print()

    # Analysis 2: Non-island wells only (masked)
    print("="*80)
    print("2. SPATIAL VARIANCE - NON-ISLAND WELLS ONLY (Masked)")
    print("="*80)

    v4_masked = analyze_spatial_variance(v4_results, non_island_wells)

    print(f"V3 (all wells):      {v3_all['total_spatial_var']:.2f}")
    print(f"V4 (non-islands):    {v4_masked['total_spatial_var']:.2f}  ({v4_masked['n_wells']} wells)")
    print(f"Δ (v4 - v3):         {v4_masked['total_spatial_var'] - v3_all['total_spatial_var']:+.2f}")
    print(f"Change:              {((v4_masked['total_spatial_var'] - v3_all['total_spatial_var']) / v3_all['total_spatial_var'] * 100):+.1f}%")
    print()

    # Analysis 3: Island wells only (isolation check)
    print("="*80)
    print("3. SPATIAL VARIANCE - ISLAND WELLS ONLY (Isolation Check)")
    print("="*80)

    v4_islands = analyze_spatial_variance(v4_results, ISLAND_WELLS)

    print(f"V4 (islands only):   {v4_islands['total_spatial_var']:.2f}  ({v4_islands['n_wells']} wells)")
    print()

    # Verdict
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)
    print()

    masked_change = ((v4_masked['total_spatial_var'] - v3_all['total_spatial_var']) / v3_all['total_spatial_var'] * 100)

    if abs(masked_change) < 10:
        print("✅ ISLANDS WERE CONTAMINATING SPATIAL VARIANCE")
        print()
        print(f"   Original (all wells):     +37.2% increase")
        print(f"   Masked (non-islands):     {masked_change:+.1f}% change")
        print()
        print("   Conclusion: V4 spatial decorrelation is preserved.")
        print("   The +37% was an artifact of including islands in row/col means.")
    elif masked_change > 10:
        print("⚠️  SPATIAL VARIANCE STILL ELEVATED AFTER MASKING")
        print()
        print(f"   Masked change: {masked_change:+.1f}%")
        print()
        print("   Possible causes:")
        print("   - Island placement creates edge effects on neighbors")
        print("   - Anchor island distribution unbalanced")
        print("   - Bug in v4 execution or assignment")
    else:
        print("✅ SPATIAL VARIANCE IMPROVED")
        print()
        print(f"   Masked change: {masked_change:+.1f}%")
        print()
        print("   V4 non-island wells have BETTER spatial decorrelation than v3.")

    print()
    print("Island isolation:")
    island_var = v4_islands['total_spatial_var']
    if island_var < v3_all['total_spatial_var'] / 2:
        print(f"   ✓ Islands well-isolated (variance = {island_var:.2f})")
    else:
        print(f"   ⚠️  Islands show spatial structure (variance = {island_var:.2f})")


if __name__ == "__main__":
    main()
