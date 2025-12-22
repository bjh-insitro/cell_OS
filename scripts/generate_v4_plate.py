#!/usr/bin/env python3
"""
Generate CAL_384_RULES_WORLD_v4.json - sparse micro-checkerboard with CV islands.

V4 Design Philosophy:
- Keep v3's micro-checkerboard for 90% of wells (preserve 49% spatial variance win)
- Add 8 dedicated "CV islands" (3×3 homogeneous tiles) for clean reproducibility measurement
- Islands placed in quadrants, away from edges and probe columns
- Both cell lines represented in islands
- Vehicle and one anchor in islands
- Islands excluded from stain/focus/fixation probes and density extremes
"""

import json
from pathlib import Path

# Load v3 as base
v3_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json")
with open(v3_path, 'r') as f:
    v4 = json.load(f)

# Update schema and metadata
v4["schema_version"] = "calibration_plate_v4"
v4["plate"]["plate_id"] = "CAL_384_RULES_WORLD_v4"
v4["intent"] = "Sparse micro-checkerboard: v3 spatial benefits + dedicated CV islands for clean reproducibility measurement"

# Add CV islands to cell_lines section
v4["cell_lines"]["notes"].append("V4 adds CV islands: 8 homogeneous 3×3 tiles for unconfounded CV measurement")
v4["cell_lines"]["notes"].append("Islands override checkerboard locally but preserve global decorrelation")

# Define CV islands (3×3 tiles, homogeneous cell line, away from edges and probe columns)
# Quadrants: NW, NE, SW, SE
# Avoid: col 1 (focus), col 6 (stain), col 12 (fixation), col 19 (stain), col 24 (focus)
# Avoid: row A, P (edges)

cv_islands = {
    "purpose": "Homogeneous 3×3 tiles for clean CV measurement without cell line or neighbor confounding",
    "tile_shape": "3x3",
    "islands": [
        # NW quadrant - Vehicle islands
        {
            "island_id": "CV_NW_HEPG2_VEH",
            "cell_line": "HepG2",
            "treatment": "VEHICLE",
            "wells": ["D4", "D5", "D6", "E4", "E5", "E6", "F4", "F5", "F6"],
            "notes": "NW quadrant, HepG2, vehicle baseline CV"
        },
        {
            "island_id": "CV_NW_A549_VEH",
            "cell_line": "A549",
            "treatment": "VEHICLE",
            "wells": ["D8", "D9", "D10", "E8", "E9", "E10", "F8", "F9", "F10"],
            "notes": "NW quadrant, A549, vehicle baseline CV"
        },
        # NE quadrant - Vehicle islands
        {
            "island_id": "CV_NE_HEPG2_VEH",
            "cell_line": "HepG2",
            "treatment": "VEHICLE",
            "wells": ["D15", "D16", "D17", "E15", "E16", "E17", "F15", "F16", "F17"],
            "notes": "NE quadrant, HepG2, vehicle baseline CV"
        },
        {
            "island_id": "CV_NE_A549_VEH",
            "cell_line": "A549",
            "treatment": "VEHICLE",
            "wells": ["D20", "D21", "D22", "E20", "E21", "E22", "F20", "F21", "F22"],
            "notes": "NE quadrant, A549, vehicle baseline CV"
        },
        # SW quadrant - Anchor islands
        {
            "island_id": "CV_SW_HEPG2_MORPH",
            "cell_line": "HepG2",
            "treatment": "ANCHOR_MORPH",
            "reagent": "Nocodazole",
            "dose_uM": 0.3,
            "wells": ["K4", "K5", "K6", "L4", "L5", "L6", "M4", "M5", "M6"],
            "notes": "SW quadrant, HepG2, anchor morph CV"
        },
        {
            "island_id": "CV_SW_A549_MORPH",
            "cell_line": "A549",
            "treatment": "ANCHOR_MORPH",
            "reagent": "Nocodazole",
            "dose_uM": 0.3,
            "wells": ["K8", "K9", "K10", "L8", "L9", "L10", "M8", "M9", "M10"],
            "notes": "SW quadrant, A549, anchor morph CV"
        },
        # SE quadrant - Mixed
        {
            "island_id": "CV_SE_HEPG2_VEH",
            "cell_line": "HepG2",
            "treatment": "VEHICLE",
            "wells": ["K15", "K16", "K17", "L15", "L16", "L17", "M15", "M16", "M17"],
            "notes": "SE quadrant, HepG2, vehicle baseline CV"
        },
        {
            "island_id": "CV_SE_A549_DEATH",
            "cell_line": "A549",
            "treatment": "ANCHOR_DEATH",
            "reagent": "Thapsigargin",
            "dose_uM": 0.05,
            "wells": ["K20", "K21", "K22", "L20", "L21", "L22", "M20", "M21", "M22"],
            "notes": "SE quadrant, A549, anchor death CV"
        }
    ]
}

v4["reproducibility_islands"] = cv_islands

# Update cell_lines.well_to_cell_line to enforce island assignments
for island in cv_islands["islands"]:
    cell_line = island["cell_line"]
    for well in island["wells"]:
        v4["cell_lines"]["well_to_cell_line"][well] = cell_line

# Remove island wells from stain probes
stain_low_wells = set(v4["non_biological_provocations"]["stain_scale_probes"]["wells"]["STAIN_LOW"])
stain_high_wells = set(v4["non_biological_provocations"]["stain_scale_probes"]["wells"]["STAIN_HIGH"])

for island in cv_islands["islands"]:
    for well in island["wells"]:
        stain_low_wells.discard(well)
        stain_high_wells.discard(well)

v4["non_biological_provocations"]["stain_scale_probes"]["wells"]["STAIN_LOW"] = sorted(list(stain_low_wells))
v4["non_biological_provocations"]["stain_scale_probes"]["wells"]["STAIN_HIGH"] = sorted(list(stain_high_wells))

# Remove island wells from fixation probes
early_fix_wells = set(v4["non_biological_provocations"]["fixation_timing_probes"]["wells"]["EARLY_FIX"])
late_fix_wells = set(v4["non_biological_provocations"]["fixation_timing_probes"]["wells"]["LATE_FIX"])

for island in cv_islands["islands"]:
    for well in island["wells"]:
        early_fix_wells.discard(well)
        late_fix_wells.discard(well)

v4["non_biological_provocations"]["fixation_timing_probes"]["wells"]["EARLY_FIX"] = sorted(list(early_fix_wells))
v4["non_biological_provocations"]["fixation_timing_probes"]["wells"]["LATE_FIX"] = sorted(list(late_fix_wells))

# Remove island wells from focus probes
focus_minus_wells = set(v4["non_biological_provocations"]["imaging_focus_probes"]["wells"]["FOCUS_MINUS"])
focus_plus_wells = set(v4["non_biological_provocations"]["imaging_focus_probes"]["wells"]["FOCUS_PLUS"])

for island in cv_islands["islands"]:
    for well in island["wells"]:
        focus_minus_wells.discard(well)
        focus_plus_wells.discard(well)

v4["non_biological_provocations"]["imaging_focus_probes"]["wells"]["FOCUS_MINUS"] = sorted(list(focus_minus_wells))
v4["non_biological_provocations"]["imaging_focus_probes"]["wells"]["FOCUS_PLUS"] = sorted(list(focus_plus_wells))

# Remove island wells from biological anchors (they'll be managed by islands)
anchor_morph_wells = set(v4["biological_anchors"]["wells"]["ANCHOR_MORPH"])
anchor_death_wells = set(v4["biological_anchors"]["wells"]["ANCHOR_DEATH"])

for island in cv_islands["islands"]:
    for well in island["wells"]:
        anchor_morph_wells.discard(well)
        anchor_death_wells.discard(well)

v4["biological_anchors"]["wells"]["ANCHOR_MORPH"] = sorted(list(anchor_morph_wells))
v4["biological_anchors"]["wells"]["ANCHOR_DEATH"] = sorted(list(anchor_death_wells))

# Remove island wells from contrastive tiles
tiles_to_keep = []
for tile in v4["contrastive_tiles"]["tiles"]:
    tile_wells_set = set(tile["wells"])
    island_collision = False
    for island in cv_islands["islands"]:
        if tile_wells_set.intersection(set(island["wells"])):
            island_collision = True
            break
    if not island_collision:
        tiles_to_keep.append(tile)

v4["contrastive_tiles"]["tiles"] = tiles_to_keep
v4["contrastive_tiles"]["notes"] = "V4: Some tiles removed to avoid collision with CV islands"

# Update resolution rules to add islands at highest precedence
v4["resolution_rules"]["order_of_precedence"] = [
    "reproducibility_islands.islands[].wells (V4: highest precedence for clean CV measurement)",
    "background_controls.wells_no_cells",
    "contrastive_tiles.tiles[].assignment",
    "biological_anchors.wells",
    "non_biological_provocations.*.wells",
    "non_biological_provocations.cell_density_gradient.rule",
    "global_defaults.default_assignment"
]

# Update expected learning deliverables
v4["expected_learning_deliverables"].insert(0,
    "Clean CV measurement from homogeneous 3×3 islands (eliminates neighbor coupling artifacts from v3)")

# Add v4-specific sanity checks
v4["sanity_checks"].append({
    "name": "cv_islands_tight",
    "description": "CV islands should show tighter local CV than v3 checkerboard tiles (validates that neighbor diversity was inflating v3 tile CV)"
})

v4["sanity_checks"].append({
    "name": "spatial_variance_preserved",
    "description": "Global spatial variance should remain ~49% better than v2 (validates that islands don't break decorrelation)"
})

# Write output
output_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json")
with open(output_path, 'w') as f:
    json.dump(v4, f, indent=2)

print(f"✓ Generated {output_path}")
print(f"✓ CV Islands: {len(cv_islands['islands'])} (3×3 homogeneous)")
print(f"✓ Island wells: {len(cv_islands['islands']) * 9} total")
print(f"✓ Checkerboard wells: {384 - len(cv_islands['islands']) * 9 - 8} (8 no-cells)")
print("\nIsland Summary:")
for island in cv_islands["islands"]:
    print(f"  - {island['island_id']}: {island['cell_line']}, {island['treatment']}")
