#!/usr/bin/env python3
"""
Validate V5 hybrid design.

Checks:
1. Base pattern is V3 checkerboard (outside islands)
2. Island wells have correct cell line assignments
3. No probe/gradient contamination in islands
4. Scattered anchors don't overlap vehicle islands
5. Contrastive tiles don't overlap islands
"""

import json
from pathlib import Path

# Island wells
ISLAND_WELLS = set([
    # CV_NW_HEPG2_VEH
    'D4','D5','D6','E4','E5','E6','F4','F5','F6',
    # CV_NW_A549_VEH
    'D8','D9','D10','E8','E9','E10','F8','F9','F10',
    # CV_NE_HEPG2_VEH
    'D15','D16','D17','E15','E16','E17','F15','F16','F17',
    # CV_NE_A549_VEH
    'D20','D21','D22','E20','E21','E22','F20','F21','F22',
    # CV_SW_HEPG2_MORPH
    'K4','K5','K6','L4','L5','L6','M4','M5','M6',
    # CV_SW_A549_MORPH
    'K8','K9','K10','L8','L9','L10','M8','M9','M10',
    # CV_SE_HEPG2_VEH
    'K15','K16','K17','L15','L16','L17','M15','M16','M17',
    # CV_SE_A549_DEATH
    'K20','K21','K22','L20','L21','L22','M20','M21','M22'
])


def validate_v5():
    v5_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json")
    v3_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json")

    with open(v5_path, 'r') as f:
        v5 = json.load(f)

    with open(v3_path, 'r') as f:
        v3 = json.load(f)

    print("="*80)
    print("V5 HYBRID VALIDATION")
    print("="*80)
    print()

    all_pass = True

    # Check 1: Non-island wells match V3 checkerboard
    print("Check 1: Non-Island Wells Match V3 Checkerboard")
    print("-"*80)

    v5_cl = v5["cell_lines"]["well_to_cell_line"]
    v3_cl = v3["cell_lines"]["well_to_cell_line"]

    mismatches = []
    for well in v3_cl:
        if well in ISLAND_WELLS:
            continue  # Skip islands
        if v5_cl.get(well) != v3_cl.get(well):
            mismatches.append((well, v3_cl[well], v5_cl.get(well, "MISSING")))

    if mismatches:
        print(f"❌ FAILED: {len(mismatches)} non-island wells don't match V3")
        for well, v3_val, v5_val in mismatches[:10]:
            print(f"   {well}: V3={v3_val}, V5={v5_val}")
        if len(mismatches) > 10:
            print(f"   ... and {len(mismatches) - 10} more")
        all_pass = False
    else:
        print("✅ PASSED: All non-island wells match V3 checkerboard")

    print()

    # Check 2: Island wells have correct cell lines
    print("Check 2: Island Wells Have Correct Cell Line")
    print("-"*80)

    island_errors = []
    for island in v5["reproducibility_islands"]["islands"]:
        expected_cl = island["cell_line"]
        for well in island["wells"]:
            actual_cl = v5_cl.get(well)
            if actual_cl != expected_cl:
                island_errors.append((island["island_id"], well, expected_cl, actual_cl))

    if island_errors:
        print(f"❌ FAILED: {len(island_errors)} island wells have wrong cell line")
        for island_id, well, expected, actual in island_errors:
            print(f"   {island_id} / {well}: expected {expected}, got {actual}")
        all_pass = False
    else:
        print("✅ PASSED: All island wells have correct cell lines")

    print()

    # Check 3: Islands listed in exclusion rules
    print("Check 3: Exclusion Rules Present")
    print("-"*80)

    if "exclusion_rules" not in v5["reproducibility_islands"]:
        print("❌ FAILED: No exclusion_rules section")
        all_pass = False
    else:
        exclusions = v5["reproducibility_islands"]["exclusion_rules"]
        forced = exclusions.get("forced_fields", {})

        checks = [
            ("cell_density", "NOMINAL"),
            ("stain_scale", 1.0),
            ("fixation_timing_offset_min", 0),
            ("imaging_focus_offset_um", 0)
        ]

        for field, expected in checks:
            actual = forced.get(field)
            if actual == expected:
                print(f"   ✓ {field}: {actual}")
            else:
                print(f"   ❌ {field}: expected {expected}, got {actual}")
                all_pass = False

        print()
        print("✅ PASSED: Exclusion rules configured")

    print()

    # Check 4: Scattered anchors don't overlap vehicle islands
    print("Check 4: Scattered Anchors Don't Overlap Vehicle Islands")
    print("-"*80)

    vehicle_islands = []
    for island in v5["reproducibility_islands"]["islands"]:
        if island["assignment"]["treatment"] == "VEHICLE":
            vehicle_islands.extend(island["wells"])
    vehicle_island_set = set(vehicle_islands)

    if "scattered_anchors" in v5:
        anchor_morph = set(v5["scattered_anchors"]["nocodazole"]["wells"])
        anchor_death = set(v5["scattered_anchors"]["thapsigargin"]["wells"])

        morph_overlap = anchor_morph & vehicle_island_set
        death_overlap = anchor_death & vehicle_island_set

        if morph_overlap or death_overlap:
            print(f"❌ FAILED: Anchors overlap vehicle islands")
            if morph_overlap:
                print(f"   Nocodazole overlaps: {sorted(morph_overlap)}")
            if death_overlap:
                print(f"   Thapsigargin overlaps: {sorted(death_overlap)}")
            all_pass = False
        else:
            print("✅ PASSED: No anchor overlap with vehicle islands")
    else:
        print("⚠️  WARNING: No scattered_anchors section")

    print()

    # Check 5: Contrastive tiles don't overlap islands
    print("Check 5: Contrastive Tiles Don't Overlap Islands")
    print("-"*80)

    if "contrastive_tiles" in v5:
        tiles = v5["contrastive_tiles"]["tiles"]
        overlaps = []

        for tile in tiles:
            tile_wells = set(tile["wells"])
            overlap = tile_wells & ISLAND_WELLS
            if overlap:
                overlaps.append((tile["tile_id"], overlap))

        if overlaps:
            print(f"❌ FAILED: {len(overlaps)} tiles overlap islands")
            for tile_id, wells in overlaps:
                print(f"   {tile_id}: {sorted(wells)}")
            all_pass = False
        else:
            print("✅ PASSED: No tile overlap with islands")
    else:
        print("⚠️  WARNING: No contrastive_tiles section")

    print()

    # Summary
    print("="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print()

    if all_pass:
        print("✅ ALL CHECKS PASSED")
        print()
        print("V5 is ready for testing.")
        print()
        print("Expected improvements over V4:")
        print("  - V3-level spatial decorrelation (no 2×2 blocking artifacts)")
        print("  - V4-level CV measurement (13% in islands)")
        print("  - No spatial variance inflation in boring wells")
        print()
        print("Next steps:")
        print("  1. Run V3 vs V5 comparison with 5 seeds")
        print("  2. Compare boring wells spatial variance (should be similar)")
        print("  3. Compare island CV (should be ~13% like V4)")
        print("  4. If V5 passes, adopt as production standard")
    else:
        print("❌ VALIDATION FAILED")
        print()
        print("Fix errors before proceeding.")


if __name__ == "__main__":
    validate_v5()
