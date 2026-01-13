#!/usr/bin/env python3
"""
Analyze neighbor coupling effects in simulator.

Tests if island boundaries create edge effects on neighboring wells.
Measures if simulator has neighbor kernel that propagates values.

Strategy:
1. Identify island boundary wells (adjacent to islands)
2. Compare boundary wells vs interior wells (same conditions)
3. Measure if boundary wells show different variance/bias
4. Test coupling distance (1-well, 2-well away from islands)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# All island wells
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

ROW_TO_NUM = {r: i for i, r in enumerate('ABCDEFGHIJKLMNOP')}
NUM_TO_ROW = {i: r for r, i in ROW_TO_NUM.items()}


def get_neighbors(well_id, distance=1):
    """Get all wells within Manhattan distance from well_id."""
    row = well_id[0]
    col = int(well_id[1:])
    row_idx = ROW_TO_NUM[row]

    neighbors = []
    for dr in range(-distance, distance + 1):
        for dc in range(-distance, distance + 1):
            manhattan = abs(dr) + abs(dc)
            if manhattan == 0 or manhattan > distance:
                continue

            new_row_idx = row_idx + dr
            new_col = col + dc

            if 0 <= new_row_idx < 16 and 1 <= new_col <= 24:
                new_well = NUM_TO_ROW[new_row_idx] + str(new_col)
                neighbors.append(new_well)

    return neighbors


def classify_wells_by_island_proximity(all_wells):
    """
    Classify wells by distance to nearest island.

    Returns:
    - boundary_1: Wells 1-away from islands (immediate neighbors)
    - boundary_2: Wells 2-away from islands
    - interior: Wells >2 away from islands
    """
    boundary_1 = set()
    boundary_2 = set()

    for island_well in ISLAND_WELLS:
        # Get 1-away neighbors
        neighbors_1 = get_neighbors(island_well, distance=1)
        for n in neighbors_1:
            if n not in ISLAND_WELLS:
                boundary_1.add(n)

        # Get 2-away neighbors
        neighbors_2 = get_neighbors(island_well, distance=2)
        for n in neighbors_2:
            manhattan = abs(ROW_TO_NUM[n[0]] - ROW_TO_NUM[island_well[0]]) + abs(int(n[1:]) - int(island_well[1:]))
            if manhattan == 2 and n not in ISLAND_WELLS:
                boundary_2.add(n)

    # Remove overlap (prefer closest classification)
    boundary_2 -= boundary_1

    interior = all_wells - ISLAND_WELLS - boundary_1 - boundary_2

    return {
        'boundary_1': boundary_1,
        'boundary_2': boundary_2,
        'interior': interior
    }


def get_boring_wells_by_category(flat_results, well_category):
    """Get boring wells within a specific category (boundary_1, boundary_2, interior)."""
    boring = []

    NOMINAL_COLS = set([9, 10, 11, 12, 13, 14, 15, 16])
    EDGE_ROWS = set(['A', 'P'])
    EDGE_COLS = set([1, 24])

    for r in flat_results:
        well_id = r['well_id']

        if well_id not in well_category:
            continue

        row = r['row']
        col = r['col']

        if row in EDGE_ROWS or col in EDGE_COLS:
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


def analyze_variance_by_proximity(flat_results, proximity_classes):
    """Analyze if variance differs by distance from islands."""
    results = {}

    for category, wells in proximity_classes.items():
        boring = get_boring_wells_by_category(flat_results, wells)

        if len(boring) < 2:
            results[category] = {
                'n_wells': len(boring),
                'mean': 0,
                'std': 0,
                'cv': 0
            }
            continue

        values = [w['morph_nucleus'] for w in boring]
        mean = np.mean(values)
        std = np.std(values, ddof=1)
        cv = (std / mean) * 100

        results[category] = {
            'n_wells': len(boring),
            'mean': mean,
            'std': std,
            'cv': cv,
            'values': values
        }

    return results


def test_cell_line_mixing_at_boundaries(flat_results, proximity_classes):
    """
    Test if boundary wells show more cell line mixing.

    Strategy: Count how many boring wells have each cell line at different distances.
    """
    results = {}

    for category, wells in proximity_classes.items():
        boring = get_boring_wells_by_category(flat_results, wells)

        cell_line_counts = defaultdict(int)
        for w in boring:
            # Infer cell line from value (rough heuristic: ~75 = A549, ~195 = HepG2)
            if w['morph_nucleus'] < 120:
                cell_line_counts['A549-like'] += 1
            else:
                cell_line_counts['HepG2-like'] += 1

        results[category] = {
            'n_wells': len(boring),
            'cell_line_counts': dict(cell_line_counts)
        }

    return results


def create_proximity_histogram(v3_results, v4_results, output_path):
    """Compare value distributions by proximity to islands."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    categories = ['interior', 'boundary_2', 'boundary_1']
    titles = ['Interior (>2 away)', 'Boundary 2 (2-away)', 'Boundary 1 (1-away)']

    for idx, (cat, title) in enumerate(zip(categories, titles)):
        # V3 (no islands, use all as "interior")
        ax_v3 = axes[0, idx]
        if cat in v3_results and v3_results[cat]['n_wells'] > 0:
            ax_v3.hist(v3_results[cat]['values'], bins=20, alpha=0.7, edgecolor='black')
            ax_v3.set_title(f"V3 {title}\n(n={v3_results[cat]['n_wells']}, CV={v3_results[cat]['cv']:.1f}%)")
            ax_v3.set_xlabel('morph_nucleus')
            ax_v3.set_ylabel('Count')
        else:
            ax_v3.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax_v3.transAxes)
            ax_v3.set_title(f"V3 {title}")

        # V4
        ax_v4 = axes[1, idx]
        if cat in v4_results and v4_results[cat]['n_wells'] > 0:
            ax_v4.hist(v4_results[cat]['values'], bins=20, alpha=0.7, edgecolor='black', color='orange')
            ax_v4.set_title(f"V4 {title}\n(n={v4_results[cat]['n_wells']}, CV={v4_results[cat]['cv']:.1f}%)")
            ax_v4.set_xlabel('morph_nucleus')
            ax_v4.set_ylabel('Count')
        else:
            ax_v4.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax_v4.transAxes)
            ax_v4.set_title(f"V4 {title}")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main():
    print("="*80)
    print("NEIGHBOR COUPLING ANALYSIS")
    print("="*80)
    print()
    print("Testing if island boundaries create edge effects on neighboring wells.")
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

    # Classify wells by proximity to islands
    all_v4_wells = set(r['well_id'] for r in v4_data['flat_results'])
    v4_proximity = classify_wells_by_island_proximity(all_v4_wells)

    print("V4 Well Classification by Island Proximity:")
    print(f"  Islands:        {len(ISLAND_WELLS)} wells")
    print(f"  Boundary 1-away: {len(v4_proximity['boundary_1'])} wells (immediate neighbors)")
    print(f"  Boundary 2-away: {len(v4_proximity['boundary_2'])} wells")
    print(f"  Interior (>2):   {len(v4_proximity['interior'])} wells")
    print()

    # For V3, treat all non-edge wells as "interior" (no islands)
    all_v3_wells = set(r['well_id'] for r in v3_data['flat_results'])
    v3_proximity = {
        'interior': all_v3_wells - ISLAND_WELLS,  # Exclude island positions for consistency
        'boundary_1': set(),
        'boundary_2': set()
    }

    # Analysis 1: Variance by Proximity
    print("="*80)
    print("1. VARIANCE BY PROXIMITY TO ISLANDS")
    print("="*80)
    print()
    print("Hypothesis: If simulator has neighbor coupling, boundary wells will show:")
    print("  - Different variance than interior wells")
    print("  - Bias toward island values")
    print()

    v3_variance = analyze_variance_by_proximity(v3_data['flat_results'], v3_proximity)
    v4_variance = analyze_variance_by_proximity(v4_data['flat_results'], v4_proximity)

    print("V3 (No Islands):")
    for cat in ['interior', 'boundary_2', 'boundary_1']:
        if cat in v3_variance and v3_variance[cat]['n_wells'] > 0:
            print(f"  {cat:15s}: n={v3_variance[cat]['n_wells']:3d}, mean={v3_variance[cat]['mean']:6.1f}, std={v3_variance[cat]['std']:6.2f}, CV={v3_variance[cat]['cv']:5.1f}%")
    print()

    print("V4 (With Islands):")
    for cat in ['interior', 'boundary_2', 'boundary_1']:
        if cat in v4_variance and v4_variance[cat]['n_wells'] > 0:
            print(f"  {cat:15s}: n={v4_variance[cat]['n_wells']:3d}, mean={v4_variance[cat]['mean']:6.1f}, std={v4_variance[cat]['std']:6.2f}, CV={v4_variance[cat]['cv']:5.1f}%")
    print()

    # Analysis 2: Cell Line Mixing
    print("="*80)
    print("2. CELL LINE DISTRIBUTION BY PROXIMITY")
    print("="*80)
    print()
    print("Testing if boundary wells show different cell line balance.")
    print("(Values ~75 = A549-like, ~195 = HepG2-like)")
    print()

    v4_mixing = test_cell_line_mixing_at_boundaries(v4_data['flat_results'], v4_proximity)

    for cat in ['interior', 'boundary_2', 'boundary_1']:
        if cat in v4_mixing and v4_mixing[cat]['n_wells'] > 0:
            counts = v4_mixing[cat]['cell_line_counts']
            total = v4_mixing[cat]['n_wells']
            print(f"{cat:15s}: {counts.get('A549-like', 0):3d} A549-like, {counts.get('HepG2-like', 0):3d} HepG2-like  (total {total})")
    print()

    # Generate visualization
    print("="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    print()

    output_dir = Path("validation_frontend/public/analysis_plots")
    output_dir.mkdir(exist_ok=True)

    create_proximity_histogram(v3_variance, v4_variance,
                              output_dir / "neighbor_coupling_histograms.png")
    print("✓ Proximity histograms saved")
    print()
    print(f"Plots saved to: {output_dir}/")
    print()

    # Diagnosis
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)
    print()

    if len(v4_variance['boundary_1']['values']) > 0 and len(v4_variance['interior']['values']) > 0:
        boundary_cv = v4_variance['boundary_1']['cv']
        interior_cv = v4_variance['interior']['cv']

        if abs(boundary_cv - interior_cv) > 10:
            print(f"⚠️  Boundary wells show different CV than interior")
            print(f"   Boundary 1-away CV: {boundary_cv:.1f}%")
            print(f"   Interior CV:        {interior_cv:.1f}%")
            print(f"   Difference:         {abs(boundary_cv - interior_cv):.1f}%")
            print()
            print("   Suggests neighbor coupling effects around island boundaries.")
        else:
            print(f"✓ Boundary wells show similar CV to interior")
            print(f"   Boundary 1-away CV: {boundary_cv:.1f}%")
            print(f"   Interior CV:        {interior_cv:.1f}%")
            print()
            print("   No evidence of neighbor coupling at island boundaries.")

    print()
    print("Key Finding:")
    print()

    # Check if 2×2 pattern is the issue
    if v4_variance['interior']['cv'] > v3_variance['interior']['cv'] * 1.5:
        print("❌ Even INTERIOR wells (far from islands) show elevated variance in V4")
        print(f"   V4 interior CV: {v4_variance['interior']['cv']:.1f}%")
        print(f"   V3 interior CV: {v3_variance['interior']['cv']:.1f}%")
        print()
        print("   Conclusion: Problem is NOT island boundary effects.")
        print("   Problem is inherent to V4's 2×2 micro-checkerboard layout.")
        print()
        print("   The 2×2 cell line tiling creates low-frequency spatial pattern")
        print("   that inflates row/column variance even in wells far from islands.")
    else:
        print("✓ V4 interior wells look similar to V3")
        print()
        print("   Problem may be localized to island boundaries.")


if __name__ == "__main__":
    main()
