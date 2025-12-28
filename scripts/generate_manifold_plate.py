"""
Generate 384-well manifold plate for morphology geometry visualization.

Design:
- 2 cell lines (A549, HepG2)
- 2 timepoints (24h, 48h)
- 8 compounds (stress axes)
- 6 doses (0 + 5 log-spaced)
- 2 replicates per condition
= 384 wells exactly

Spatial layout:
- Stratified placement: one rep in center zone, one in edge/near-edge
- 4 groups (cell_line × timepoint) assigned to quadrants
- 10% cross-quadrant swaps to prevent spatial confounding
"""

import json
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Set


def make_rng(seed: int, salt: str) -> random.Random:
    """Create deterministic RNG."""
    base = f"{seed}|{salt}"
    h = hashlib.sha256(base.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)


def classify_well_zone(row: str, col: int) -> str:
    """Classify well as edge, near-edge, or center."""
    row_idx = ord(row) - ord('A')  # 0-15

    # Edge: row A/P or col 1/24
    if row_idx == 0 or row_idx == 15 or col == 1 or col == 24:
        return "edge"

    # Near-edge: row B/O or col 2/23
    if row_idx == 1 or row_idx == 14 or col == 2 or col == 23:
        return "near_edge"

    return "center"


def get_all_wells() -> List[str]:
    """Get all 384 well positions."""
    rows = [chr(ord('A') + i) for i in range(16)]  # A-P
    cols = range(1, 25)  # 1-24
    return [f"{r}{c:02d}" for r in rows for c in cols]


def partition_wells_by_zone() -> Dict[str, List[str]]:
    """Partition wells into edge, near-edge, center zones."""
    wells = get_all_wells()
    zones = {"edge": [], "near_edge": [], "center": []}

    for well in wells:
        row = well[0]
        col = int(well[1:])
        zone = classify_well_zone(row, col)
        zones[zone].append(well)

    return zones


def get_quadrant_wells() -> Dict[str, List[str]]:
    """Get wells for each quadrant."""
    rows = [chr(ord('A') + i) for i in range(16)]
    cols = range(1, 25)

    quadrants = {
        "Q1": [],  # A-H, 1-12
        "Q2": [],  # A-H, 13-24
        "Q3": [],  # I-P, 1-12
        "Q4": [],  # I-P, 13-24
    }

    for r in rows:
        for c in cols:
            well = f"{r}{c:02d}"
            row_idx = ord(r) - ord('A')

            if row_idx < 8:
                if c <= 12:
                    quadrants["Q1"].append(well)
                else:
                    quadrants["Q2"].append(well)
            else:
                if c <= 12:
                    quadrants["Q3"].append(well)
                else:
                    quadrants["Q4"].append(well)

    return quadrants


def generate_manifold_plate(seed: int = 42) -> Dict:
    """Generate 384-well manifold plate JSON."""

    # Configuration
    cell_lines = ["A549", "HepG2"]
    timepoints_h = [24.0, 48.0]

    # 8 compounds across stress axes
    compounds = [
        "Nocodazole",
        "Paclitaxel",
        "Thapsigargin",
        "Tunicamycin",
        "CCCP",
        "Oligomycin",
        "MG132",
        "tBHQ",
    ]

    # IC50 reference values (µM)
    compound_ic50 = {
        "Nocodazole": 0.5,
        "Paclitaxel": 0.01,
        "Thapsigargin": 0.5,
        "Tunicamycin": 1.0,
        "CCCP": 5.0,
        "Oligomycin": 1.0,
        "MG132": 1.0,
        "tBHQ": 30.0,
    }

    # 6 doses: 0 + 5 log-spaced
    dose_multipliers = [0.0, 0.003, 0.01, 0.03, 0.1, 0.3]
    n_replicates = 2

    # Create all condition tuples
    conditions = []
    for cell_line in cell_lines:
        for timepoint in timepoints_h:
            for compound in compounds:
                ic50 = compound_ic50[compound]
                for dose_mult in dose_multipliers:
                    dose_uM = dose_mult * ic50 if dose_mult > 0 else 0.0
                    for rep_id in range(n_replicates):
                        conditions.append({
                            "cell_line": cell_line,
                            "timepoint_h": timepoint,
                            "compound": compound,  # Keep original compound name for trajectory tracking
                            "dose_uM": dose_uM,
                            "dose_multiplier": dose_mult,
                            "replicate_id": rep_id,
                            "is_vehicle": dose_mult == 0.0,
                        })

    assert len(conditions) == 384, f"Expected 384 conditions, got {len(conditions)}"

    # Get quadrant wells
    quadrant_wells = get_quadrant_wells()

    # Assign groups to quadrants
    group_to_quadrant = {
        ("A549", 24.0): "Q1",
        ("HepG2", 24.0): "Q2",
        ("A549", 48.0): "Q3",
        ("HepG2", 48.0): "Q4",
    }

    # Partition conditions by group
    conditions_by_group = {}
    for cond in conditions:
        group_key = (cond["cell_line"], cond["timepoint_h"])
        if group_key not in conditions_by_group:
            conditions_by_group[group_key] = []
        conditions_by_group[group_key].append(cond)

    # For each group, assign wells with stratified placement
    rng = make_rng(seed, "manifold_plate")
    well_assignments = {}

    for group_key, group_conditions in conditions_by_group.items():
        quadrant = group_to_quadrant[group_key]
        available_wells = quadrant_wells[quadrant].copy()

        # Shuffle available wells deterministically
        group_rng = make_rng(seed, f"group_{group_key[0]}_{group_key[1]}")
        group_rng.shuffle(available_wells)

        # Classify wells by zone
        wells_by_zone = {"center": [], "near_edge": [], "edge": []}
        for well in available_wells:
            row = well[0]
            col = int(well[1:])
            zone = classify_well_zone(row, col)
            wells_by_zone[zone].append(well)

        # Assign conditions with stratified placement
        # Group by (compound, dose) to ensure replicates are placed across zones
        conditions_by_compound_dose = {}
        for cond in group_conditions:
            key = (cond["compound"], cond["dose_multiplier"])
            if key not in conditions_by_compound_dose:
                conditions_by_compound_dose[key] = []
            conditions_by_compound_dose[key].append(cond)

        # Create stratified well pools
        # Rep 0 prefers center, rep 1 prefers non-center
        center_pool = wells_by_zone["center"].copy()
        non_center_pool = wells_by_zone["near_edge"] + wells_by_zone["edge"]
        group_rng.shuffle(center_pool)
        group_rng.shuffle(non_center_pool)

        center_idx = 0
        non_center_idx = 0

        for (compound, dose_mult), cond_reps in conditions_by_compound_dose.items():
            assert len(cond_reps) == 2, f"Expected 2 reps for {compound} @ {dose_mult}x"

            # Rep 0 from center pool (fallback to non-center)
            if center_idx < len(center_pool):
                well_assignments[center_pool[center_idx]] = cond_reps[0]
                center_idx += 1
            else:
                well_assignments[non_center_pool[non_center_idx]] = cond_reps[0]
                non_center_idx += 1

            # Rep 1 from non-center pool (fallback to center)
            if non_center_idx < len(non_center_pool):
                well_assignments[non_center_pool[non_center_idx]] = cond_reps[1]
                non_center_idx += 1
            else:
                well_assignments[center_pool[center_idx]] = cond_reps[1]
                center_idx += 1

    # Apply 10% cross-quadrant swaps (40 wells total)
    n_swaps = 10  # 10 wells per quadrant
    swap_rng = make_rng(seed, "cross_quadrant_swaps")

    wells_by_quadrant = {q: [] for q in ["Q1", "Q2", "Q3", "Q4"]}
    for well, cond in well_assignments.items():
        row = well[0]
        col = int(well[1:])
        row_idx = ord(row) - ord('A')

        if row_idx < 8:
            q = "Q1" if col <= 12 else "Q2"
        else:
            q = "Q3" if col <= 12 else "Q4"

        wells_by_quadrant[q].append(well)

    # Select wells to swap from each quadrant
    wells_to_swap = {}
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        quad_wells = wells_by_quadrant[q]
        swap_rng.shuffle(quad_wells)
        wells_to_swap[q] = quad_wells[:n_swaps]

    # Cycle swap: Q1→Q2→Q4→Q3→Q1
    cycle = ["Q1", "Q2", "Q4", "Q3"]
    swap_buffer = {}

    for i, q in enumerate(cycle):
        next_q = cycle[(i + 1) % len(cycle)]

        for well_idx in range(n_swaps):
            well_from = wells_to_swap[q][well_idx]
            well_to = wells_to_swap[next_q][well_idx]

            # Buffer the swap
            if well_from not in swap_buffer:
                swap_buffer[well_from] = well_assignments[well_to]

    # Apply swaps
    for well_from, cond_to in swap_buffer.items():
        well_assignments[well_from] = cond_to

    # Create wells list with simple well IDs (A01, A02, etc.)
    wells = []
    plate_id = "ManifoldPlate_1"

    for well_pos, cond in sorted(well_assignments.items()):
        # Use simple well position as well_id (e.g., "A01", "P24")
        wells.append({
            "well_id": well_pos,
            "plate_id": plate_id,
            "well_pos": well_pos,
            "cell_line": cond["cell_line"],
            "compound": cond["compound"],
            "dose_uM": cond["dose_uM"],
            "dose_multiplier": cond["dose_multiplier"],
            "timepoint_h": cond["timepoint_h"],
            "replicate_id": cond["replicate_id"],
            "is_vehicle": cond["is_vehicle"],
            "exposure_multiplier": 1.0,
            "is_sentinel": False,
        })

    # Create design JSON
    design = {
        "design_id": f"manifold_geometry_384well_seed{seed}",
        "design_type": "manifold_geometry",
        "description": "384-well plate for morphology manifold geometry visualization with stratified spatial layout",
        "metadata": {
            "seed": seed,
            "plate_format": 384,
            "n_wells": 384,
            "cell_lines": cell_lines,
            "timepoints_h": timepoints_h,
            "compounds": compounds,
            "compound_ic50_uM": compound_ic50,
            "dose_multipliers": dose_multipliers,
            "n_replicates": n_replicates,
            "spatial_strategy": {
                "method": "stratified_placement_with_quadrant_mixing",
                "rep_0_zone": "center",
                "rep_1_zone": "edge_or_near_edge",
                "cross_quadrant_swaps_per_quadrant": n_swaps,
                "swap_cycle": "Q1→Q2→Q4→Q3→Q1",
            },
            "quadrant_assignment": {
                "Q1": "A549 @ 24h (rows A-H, cols 1-12)",
                "Q2": "HepG2 @ 24h (rows A-H, cols 13-24)",
                "Q3": "A549 @ 48h (rows I-P, cols 1-12)",
                "Q4": "HepG2 @ 48h (rows I-P, cols 13-24)",
            },
            "design_goal": "smooth dose trajectories with orthogonal stress axes for manifold geometry visualization",
        },
        "wells": wells,
    }

    return design


if __name__ == "__main__":
    design = generate_manifold_plate(seed=42)

    output_path = Path(__file__).parent.parent / "data" / "designs" / "manifold_geometry_384well_seed42.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(design, f, indent=2)

    print(f"✅ Manifold plate generated: {output_path}")
    print(f"   Total wells: {len(design['wells'])}")
    print(f"   Cell lines: {design['metadata']['cell_lines']}")
    print(f"   Compounds: {len(design['metadata']['compounds'])}")
    print(f"   Timepoints: {design['metadata']['timepoints_h']}")
    print(f"   Doses: {len(design['metadata']['dose_multipliers'])}")
    print(f"   Replicates per condition: {design['metadata']['n_replicates']}")
