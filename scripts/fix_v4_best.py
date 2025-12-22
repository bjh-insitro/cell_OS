#!/usr/bin/env python3
"""
Fix CAL_384_RULES_WORLD_v4_best.json to properly enforce island assignments.

Issues to fix:
1. Update well_to_cell_line mapping for island wells (make homogeneous)
2. Remove island wells from scattered anchor lists
3. Remove island wells from contrastive tiles
4. Verify island columns avoid LOW/HIGH density extremes
"""

import json
from pathlib import Path

# Load v4_best
v4_path = Path("/Users/bjh/Downloads/CAL_384_RULES_WORLD_v4_best.json")
with open(v4_path, 'r') as f:
    v4 = json.load(f)

print("Fixing CAL_384_RULES_WORLD_v4...")
print()

# Fix 1: Update well_to_cell_line for all island wells
print("1. Enforcing island cell lines...")
for island in v4["reproducibility_islands"]["islands"]:
    cell_line = island["cell_line"]
    for well in island["wells"]:
        v4["cell_lines"]["well_to_cell_line"][well] = cell_line
    print(f"   ✓ {island['island_id']}: {len(island['wells'])} wells → {cell_line}")

# Fix 2: Remove island wells from scattered anchors
print("\n2. Removing island wells from scattered anchors...")
island_wells = set()
for island in v4["reproducibility_islands"]["islands"]:
    for well in island["wells"]:
        island_wells.add(well)

# Vehicle islands shouldn't be in anchor lists
vehicle_island_wells = set()
for island in v4["reproducibility_islands"]["islands"]:
    if island["treatment"] == "VEHICLE":
        for well in island["wells"]:
            vehicle_island_wells.add(well)

anchor_morph = set(v4["biological_anchors"]["wells"]["ANCHOR_MORPH"])
anchor_death = set(v4["biological_anchors"]["wells"]["ANCHOR_DEATH"])

# Remove vehicle island wells from scattered anchors
morph_before = len(anchor_morph)
death_before = len(anchor_death)

anchor_morph -= vehicle_island_wells
anchor_death -= vehicle_island_wells

v4["biological_anchors"]["wells"]["ANCHOR_MORPH"] = sorted(list(anchor_morph))
v4["biological_anchors"]["wells"]["ANCHOR_DEATH"] = sorted(list(anchor_death))

print(f"   ✓ Removed {morph_before - len(anchor_morph)} wells from ANCHOR_MORPH")
print(f"   ✓ Removed {death_before - len(anchor_death)} wells from ANCHOR_DEATH")

# Fix 3: Remove island wells from contrastive tiles
print("\n3. Removing colliding contrastive tiles...")
tiles_to_keep = []
tiles_removed = 0
for tile in v4["contrastive_tiles"]["tiles"]:
    tile_wells_set = set(tile["wells"])
    if tile_wells_set & island_wells:
        tiles_removed += 1
        print(f"   ✓ Removed {tile['tile_id']} (collision with islands)")
    else:
        tiles_to_keep.append(tile)

v4["contrastive_tiles"]["tiles"] = tiles_to_keep
print(f"   ✓ Kept {len(tiles_to_keep)} tiles, removed {tiles_removed}")

# Check density gradient (informational only - can't easily fix without relocating islands)
print("\n4. Checking density gradient placement...")
low_cols = set(v4["non_biological_provocations"]["cell_density_gradient"]["rule"]["LOW_cols"])
nominal_cols = set(v4["non_biological_provocations"]["cell_density_gradient"]["rule"]["NOMINAL_cols"])
high_cols = set(v4["non_biological_provocations"]["cell_density_gradient"]["rule"]["HIGH_cols"])

island_cols = set()
for island in v4["reproducibility_islands"]["islands"]:
    for well in island["wells"]:
        col = int(well[1:])
        island_cols.add(col)

in_low = island_cols & low_cols
in_nominal = island_cols & nominal_cols
in_high = island_cols & high_cols

print(f"   Islands in LOW cols: {sorted(in_low)} ({len(in_low)} cols)")
print(f"   Islands in NOMINAL cols: {sorted(in_nominal)} ({len(in_nominal)} cols)")
print(f"   Islands in HIGH cols: {sorted(in_high)} ({len(in_high)} cols)")

if in_low or in_high:
    print("   ⚠️  WARNING: Some islands in non-NOMINAL density columns")
    print("   This may be intentional if testing density effects in islands")
else:
    print("   ✓ All islands in NOMINAL density columns")

# Write fixed version
output_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json")
with open(output_path, 'w') as f:
    json.dump(v4, f, indent=2)

print(f"\n✓ Fixed version written to {output_path}")
print("\nRe-run validation: python3 scripts/validate_v4_islands.py")
