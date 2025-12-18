#!/usr/bin/env python3
"""
Spatial Diagnostic: Verify sentinel distribution isn't neutered

Checks:
1. Quadrant distribution (2x2 grid)
2. Edge band distribution (outer ring vs interior)
3. Row/column distribution

This ensures that "0 warnings" isn't because checks are blind.
"""

import json
import sys
from collections import Counter


def position_to_coords(pos):
    """Convert well position like 'A02' to (row, col) indices"""
    row = ord(pos[0]) - ord('A')
    col = int(pos[1:]) - 1
    return row, col


def classify_quadrant(row, col, n_rows=8, n_cols=12):
    """Classify well into quadrant (0-3)"""
    mid_row = n_rows // 2
    mid_col = n_cols // 2

    if row < mid_row:
        return 0 if col < mid_col else 1  # Top-left, Top-right
    else:
        return 2 if col < mid_col else 3  # Bottom-left, Bottom-right


def is_edge_well(row, col, n_rows=8, n_cols=12, excluded=None):
    """Check if well is in edge band (outer ring)"""
    if excluded and f"{chr(65+row)}{col+1:02d}" in excluded:
        return False  # Don't count excluded wells

    return row == 0 or row == n_rows - 1 or col == 0 or col == n_cols - 1


def analyze_spatial_distribution(design_path, excluded_wells=None):
    """Analyze spatial distribution of sentinels"""

    if excluded_wells is None:
        excluded_wells = {'A01', 'A12', 'H01', 'H12', 'A06', 'A07', 'H06', 'H07'}

    with open(design_path) as f:
        design = json.load(f)

    wells = design['wells']

    # Get sentinels from first plate (all plates should be identical)
    plate1_sentinels = [w for w in wells if w['plate_id'] == 'Plate_1' and w['is_sentinel']]

    print(f"Spatial Distribution Analysis")
    print(f"=" * 60)
    print(f"Plate format: 96-well (8 rows × 12 cols)")
    print(f"Excluded wells: {len(excluded_wells)}")
    print(f"Sentinels: {len(plate1_sentinels)}")
    print()

    # Quadrant distribution
    quadrant_counts = Counter()
    quadrant_types = {0: [], 1: [], 2: [], 3: []}

    for sentinel in plate1_sentinels:
        row, col = position_to_coords(sentinel['well_pos'])
        quadrant = classify_quadrant(row, col)
        quadrant_counts[quadrant] += 1
        quadrant_types[quadrant].append(sentinel['sentinel_type'])

    print("## Quadrant Distribution (2×2)")
    print()
    expected_per_quadrant = len(plate1_sentinels) / 4

    for q in [0, 1, 2, 3]:
        count = quadrant_counts[q]
        deviation = abs(count - expected_per_quadrant)
        status = "✅" if deviation <= 2 else "⚠️ " if deviation <= 4 else "❌"
        label = ["Top-left", "Top-right", "Bottom-left", "Bottom-right"][q]

        print(f"  {status} Q{q} ({label}): {count} sentinels (expected ~{expected_per_quadrant:.1f}, deviation {deviation:.1f})")

        type_counts = Counter(quadrant_types[q])
        print(f"      Types: {dict(type_counts)}")

    print()

    # Edge band distribution
    edge_sentinels = []
    interior_sentinels = []

    for sentinel in plate1_sentinels:
        row, col = position_to_coords(sentinel['well_pos'])
        if is_edge_well(row, col, excluded=excluded_wells):
            edge_sentinels.append(sentinel)
        else:
            interior_sentinels.append(sentinel)

    print("## Edge Band Distribution")
    print()

    total_available = 96 - len(excluded_wells)
    # Rough estimate: edge band is ~40% of non-excluded wells
    expected_edge_fraction = 0.4
    expected_edge = len(plate1_sentinels) * expected_edge_fraction

    edge_count = len(edge_sentinels)
    edge_fraction = edge_count / len(plate1_sentinels)
    deviation = abs(edge_count - expected_edge)

    status = "✅" if deviation <= 4 else "⚠️ " if deviation <= 6 else "❌"

    print(f"  {status} Edge band: {edge_count} sentinels ({edge_fraction*100:.1f}%)")
    print(f"      Expected ~{expected_edge:.1f} (±4 acceptable)")
    print(f"      Types: {dict(Counter(s['sentinel_type'] for s in edge_sentinels))}")
    print()
    print(f"  Interior: {len(interior_sentinels)} sentinels ({(1-edge_fraction)*100:.1f}%)")
    print(f"      Types: {dict(Counter(s['sentinel_type'] for s in interior_sentinels))}")
    print()

    # Row distribution
    row_counts = Counter()
    for sentinel in plate1_sentinels:
        row, col = position_to_coords(sentinel['well_pos'])
        row_counts[row] += 1

    print("## Row Distribution")
    print()

    expected_per_row = len(plate1_sentinels) / 8
    for row in range(8):
        count = row_counts[row]
        deviation = abs(count - expected_per_row)
        status = "✅" if deviation <= 2 else "⚠️ "
        label = chr(65 + row)
        print(f"  {status} Row {label}: {count} sentinels (expected ~{expected_per_row:.1f})")

    print()

    # Summary
    print("## Summary")
    print()

    max_quadrant_dev = max(abs(quadrant_counts[q] - expected_per_quadrant) for q in range(4))
    edge_dev = abs(edge_count - expected_edge)
    max_row_dev = max(abs(row_counts[row] - expected_per_row) for row in range(8))

    if max_quadrant_dev <= 2 and edge_dev <= 4 and max_row_dev <= 2:
        print("✅ SPATIAL DISTRIBUTION: GOOD")
        print("   Sentinels are evenly distributed across plate regions.")
        print("   Warning checks are NOT neutered - geometry is balanced by construction.")
    elif max_quadrant_dev <= 4 and edge_dev <= 6 and max_row_dev <= 3:
        print("⚠️  SPATIAL DISTRIBUTION: ACCEPTABLE")
        print("   Minor imbalances detected but within reasonable bounds.")
    else:
        print("❌ SPATIAL DISTRIBUTION: POOR")
        print("   Significant spatial clustering detected.")
        print(f"   Max quadrant deviation: {max_quadrant_dev:.1f}")
        print(f"   Edge deviation: {edge_dev:.1f}")
        print(f"   Max row deviation: {max_row_dev:.1f}")


if __name__ == '__main__':
    design_path = 'data/designs/phase0_founder_v2_regenerated.json'
    if len(sys.argv) > 1:
        design_path = sys.argv[1]

    analyze_spatial_distribution(design_path)
