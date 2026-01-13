#!/usr/bin/env python3
"""
Create V5 hybrid plate design.

Strategy:
1. Start with V3 base (single-well alternating checkerboard)
2. Add V4's 8 homogeneous islands (3×3 each)
3. Keep V4's exclusion rules
4. Update cell_lines.well_to_cell_line for island wells

This should give us:
- V3's spatial decorrelation benefits (single-well alternation)
- V4's CV measurement zones (homogeneous islands)
- None of V4's spatial artifacts (no 2×2 blocking in mixed regions)
"""

import json
from pathlib import Path

def create_v5():
    # Load V3 as base
    v3_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json")
    with open(v3_path, 'r') as f:
        v5 = json.load(f)

    # Update metadata
    v5["plate"]["plate_id"] = "CAL_384_RULES_WORLD_v5"
    v5["intent"] = "V5 Hybrid: V3 checkerboard + V4 islands. Combines V3's spatial decorrelation with V4's CV measurement zones."

    # Load V4 islands section
    v4_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json")
    with open(v4_path, 'r') as f:
        v4 = json.load(f)

    # Copy islands section from V4
    v5["reproducibility_islands"] = v4["reproducibility_islands"]

    # Update well_to_cell_line for all island wells
    print("Updating well_to_cell_line for island wells...")
    island_updates = 0
    for island in v5["reproducibility_islands"]["islands"]:
        cell_line = island["cell_line"]
        for well in island["wells"]:
            old_cl = v5["cell_lines"]["well_to_cell_line"].get(well, "?")
            v5["cell_lines"]["well_to_cell_line"][well] = cell_line
            if old_cl != cell_line:
                island_updates += 1
                print(f"  {well}: {old_cl} → {cell_line}")

    print(f"\nUpdated {island_updates} wells for island enforcement")

    # Remove scattered anchors that overlap with vehicle islands
    vehicle_islands = [
        'D4','D5','D6','E4','E5','E6','F4','F5','F6',
        'D8','D9','D10','E8','E9','E10','F8','F9','F10',
        'D15','D16','D17','E15','E16','E17','F15','F16','F17',
        'D20','D21','D22','E20','E21','E22','F20','F21','F22',
        'K15','K16','K17','L15','L16','L17','M15','M16','M17',
        'K20','K21','K22','L20','L21','L22','M20','M21','M22'
    ]
    vehicle_island_set = set(vehicle_islands)

    # Clean scattered anchors
    anchor_morph = set(v5.get("scattered_anchors", {}).get("nocodazole", {}).get("wells", []))
    anchor_death = set(v5.get("scattered_anchors", {}).get("thapsigargin", {}).get("wells", []))

    anchor_morph_cleaned = anchor_morph - vehicle_island_set
    anchor_death_cleaned = anchor_death - vehicle_island_set

    if "scattered_anchors" in v5:
        v5["scattered_anchors"]["nocodazole"]["wells"] = sorted(anchor_morph_cleaned)
        v5["scattered_anchors"]["thapsigargin"]["wells"] = sorted(anchor_death_cleaned)

    removed_morph = len(anchor_morph) - len(anchor_morph_cleaned)
    removed_death = len(anchor_death) - len(anchor_death_cleaned)

    print(f"\nRemoved {removed_morph} nocodazole anchors from vehicle islands")
    print(f"Removed {removed_death} thapsigargin anchors from vehicle islands")

    # Remove contrastive tiles that overlap with islands
    all_island_wells = set()
    for island in v5["reproducibility_islands"]["islands"]:
        all_island_wells.update(island["wells"])

    if "contrastive_tiles" in v5:
        original_tiles = v5["contrastive_tiles"]["tiles"]
        cleaned_tiles = []

        for tile in original_tiles:
            wells = set(tile["wells"])
            if wells & all_island_wells:
                print(f"Removing tile {tile['tile_id']} (overlaps with islands)")
            else:
                cleaned_tiles.append(tile)

        v5["contrastive_tiles"]["tiles"] = cleaned_tiles
        print(f"\nRemoved {len(original_tiles) - len(cleaned_tiles)} contrastive tiles (island overlap)")

    # Update cell_lines strategy description
    v5["cell_lines"]["strategy"] = "v3_checkerboard_with_islands"
    v5["cell_lines"]["description"] = "Single-well alternating checkerboard (inherited from V3) with 8× 3×3 homogeneous reproducibility islands overlaid"

    # Save V5
    output_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json")
    with open(output_path, 'w') as f:
        json.dump(v5, f, indent=2)

    print(f"\n✅ V5 hybrid created: {output_path}")
    print()
    print("V5 Design Summary:")
    print("  Base: V3 single-well alternating checkerboard")
    print("  Islands: 8× 3×3 homogeneous (from V4)")
    print("  Exclusions: Forced NOMINAL density + no probes in islands")
    print()
    print("Expected Benefits:")
    print("  ✅ V3-level spatial decorrelation (no 2×2 blocking)")
    print("  ✅ V4-level CV measurement (13% in islands)")
    print("  ✅ No spatial artifacts (single-well alternation is high-frequency)")


if __name__ == "__main__":
    create_v5()
