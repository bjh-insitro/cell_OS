#!/usr/bin/env python3
"""
Decisive test: V3 vs V4 spatial variance on "boring wells" only.

Boring wells = wells that should be spatially uniform:
- Treatment: VEHICLE (DMSO)
- Density: NOMINAL (columns 9-16)
- Not in: islands, probes, edges, anchors
- This is the ONLY subset where spatial variance = spatial artifact

If V4 boring wells still show elevated spatial variance, design is broken.
If V4 boring wells look fine, earlier metric was conflating design with artifact.
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V4 Island wells
ISLAND_WELLS = set([
    'D4','D5','D6','E4','E5','E6','F4','F5','F6',  # CV_NW_HEPG2_VEH
    'D8','D9','D10','E8','E9','E10','F8','F9','F10',  # CV_NW_A549_VEH
    'D15','D16','D17','E15','E16','E17','F15','F16','F17',  # CV_NE_HEPG2_VEH
    'D20','D21','D22','E20','E21','E22','F20','F21','F22',  # CV_NE_A549_VEH
    'K4','K5','K6','L4','L5','L6','M4','M5','M6',  # CV_SW_HEPG2_MORPH
    'K8','K9','K10','L8','L9','L10','M8','M9','M10',  # CV_SW_A549_MORPH
    'K15','K16','K17','L15','L16','L17','M15','M16','M17',  # CV_SE_HEPG2_VEH
    'K20','K21','K22','L20','L21','L22','M20','M21','M22'  # CV_SE_A549_DEATH
])

# Nominal density columns (shared between v3 and v4)
NOMINAL_COLS = set([9, 10, 11, 12, 13, 14, 15, 16])

# Edge rows/cols to exclude
EDGE_ROWS = set(['A', 'P'])
EDGE_COLS = set([1, 24])


def get_boring_wells(flat_results, is_v4=False):
    """
    Identify boring wells that should be spatially uniform.

    Criteria:
    - Treatment: VEHICLE (dose_uM == 0, compound == 'DMSO')
    - Density: NOMINAL (columns 9-16)
    - Not in: islands (v4 only), edges
    - Not in: probe wells (stain/focus/fixation affected)
    """
    boring = []

    for r in flat_results:
        well_id = r['well_id']
        row = r['row']
        col = r['col']

        # Skip edges
        if row in EDGE_ROWS or col in EDGE_COLS:
            continue

        # Skip islands (v4 only)
        if is_v4 and well_id in ISLAND_WELLS:
            continue

        # Skip non-NOMINAL density columns
        if col not in NOMINAL_COLS:
            continue

        # Must be vehicle
        if r.get('dose_uM', -1) != 0:
            continue
        if r.get('compound', '') != 'DMSO':
            continue

        # Check for probe contamination via metadata
        # (stain_scale, fixation_timing_offset_min, imaging_focus_offset_um should be nominal)
        if abs(r.get('stain_scale', 1.0) - 1.0) > 0.01:
            continue
        if abs(r.get('fixation_timing_offset_min', 0)) > 0.1:
            continue
        if abs(r.get('imaging_focus_offset_um', 0)) > 0.1:
            continue

        boring.append(r)

    return boring


def analyze_spatial_variance(flat_results):
    """Compute row/column variance on given well set."""
    if len(flat_results) == 0:
        return {'row_variance': 0, 'col_variance': 0, 'total_spatial_var': 0, 'n_wells': 0}

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
    print("DECISIVE TEST: Spatial Variance on Boring Wells Only")
    print("="*80)
    print()
    print("Boring wells = VEHICLE + NOMINAL density + non-probe + non-edge + non-island")
    print("This is the ONLY subset where spatial variance = spatial artifact.")
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

    # Get boring wells
    v3_boring = get_boring_wells(v3_results, is_v4=False)
    v4_boring = get_boring_wells(v4_results, is_v4=True)

    print(f"V3 total wells: {len(v3_results)}")
    print(f"V3 boring wells: {len(v3_boring)} ({len(v3_boring)/len(v3_results)*100:.1f}%)")
    print()
    print(f"V4 total wells: {len(v4_results)}")
    print(f"V4 boring wells: {len(v4_boring)} ({len(v4_boring)/len(v4_results)*100:.1f}%)")
    print()

    # Compute spatial variance on boring wells
    v3_spatial = analyze_spatial_variance(v3_boring)
    v4_spatial = analyze_spatial_variance(v4_boring)

    print("="*80)
    print("SPATIAL VARIANCE - BORING WELLS ONLY")
    print("="*80)
    print()
    print(f"V3 boring wells: {v3_spatial['total_spatial_var']:.2f}  ({v3_spatial['n_wells']} wells)")
    print(f"V4 boring wells: {v4_spatial['total_spatial_var']:.2f}  ({v4_spatial['n_wells']} wells)")
    print()
    print(f"Δ (v4 - v3):     {v4_spatial['total_spatial_var'] - v3_spatial['total_spatial_var']:+.2f}")

    if v3_spatial['total_spatial_var'] > 0:
        change_pct = ((v4_spatial['total_spatial_var'] - v3_spatial['total_spatial_var']) / v3_spatial['total_spatial_var']) * 100
        print(f"Change:          {change_pct:+.1f}%")
    else:
        print("Change:          N/A (v3 baseline is zero)")
    print()

    # Verdict
    print("="*80)
    print("VERDICT")
    print("="*80)
    print()

    if v3_spatial['total_spatial_var'] == 0:
        print("⚠️  V3 boring wells have ZERO spatial variance")
        print("   This suggests v3 boring wells are too uniform or too few.")
        print("   Cannot compare meaningfully.")
    elif abs(change_pct) < 20:
        print("✅ V4 SPATIAL DECORRELATION PRESERVED")
        print()
        print(f"   Boring wells change: {change_pct:+.1f}%")
        print()
        print("   Conclusion: Earlier +538% was measuring DESIGNED heterogeneity,")
        print("              not spatial artifact. V4 is working as intended.")
        print()
        print("   Action: Fix spatial variance metric to use boring subset.")
    elif change_pct > 20:
        print("❌ V4 SPATIAL DECORRELATION DEGRADED")
        print()
        print(f"   Boring wells change: {change_pct:+.1f}%")
        print()
        print("   Conclusion: V4 introduces real spatial artifact in uniform wells.")
        print()
        print("   Possible causes:")
        print("   - Micro-checkerboard creates low-frequency structure")
        print("   - Simulator neighbor effects around island boundaries")
        print("   - Bug in v4 execution")
        print()
        print("   Action: Investigate v4 execution or redesign island placement.")
    else:
        print("✅ V4 SPATIAL DECORRELATION IMPROVED")
        print()
        print(f"   Boring wells change: {change_pct:+.1f}%")
        print()
        print("   V4 non-island wells have BETTER spatial uniformity than v3.")

    # Debug: Show some boring well values
    print()
    print("="*80)
    print("DEBUG: Sample Boring Well Values (morph_nucleus)")
    print("="*80)
    print()
    print("V3 boring wells (first 10):")
    for r in v3_boring[:10]:
        print(f"  {r['well_id']}: {r['morph_nucleus']:.2f}")

    print()
    print("V4 boring wells (first 10):")
    for r in v4_boring[:10]:
        print(f"  {r['well_id']}: {r['morph_nucleus']:.2f}")


if __name__ == "__main__":
    main()
