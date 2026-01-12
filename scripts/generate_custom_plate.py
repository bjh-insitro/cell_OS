#!/usr/bin/env python3
"""
Custom Plate Generator CLI

Generates randomized plate designs for 96-well and 384-well formats.
Supports multiple replicate plates with independent randomization.
Includes advanced controls for seeding density, dose ladders, edge exclusions,
per-compound start doses, multiple vehicle controls, and the optional Phase 0 fixed sentinel scaffold.

Usage:
    python scripts/generate_custom_plate.py --output my_plate.json --format 384 --num-plates 3 --scaffold --vehicles DMSO aqueous ...
"""

import argparse
import json
import sys
import os
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, Union

# Ensure we can import from the scripts directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from phase0_sentinel_scaffold import get_sentinel_tokens, SENTINEL_POSITIONS, SENTINEL_POSITIONS_384
except ImportError:
    # Fallback if running from a different context where import fails
    # But since we added sys.path, it should work.
    print("Warning: Could not import phase0_sentinel_scaffold. Sentinel support disabled.")
    get_sentinel_tokens = None
    SENTINEL_POSITIONS = []

# -----------------------------------------------------------------------------
# Core Generator Logic (Standalone)
# -----------------------------------------------------------------------------

def make_rng(seed: int, salt: str) -> random.Random:
    """Create deterministic RNG seeded per design + salt."""
    base = str(seed) + "|" + salt
    h = hashlib.sha256(base.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)

def get_all_positions(plate_format: int) -> List[str]:
    """Get all well positions for a given format."""
    if plate_format == 96:
        rows = "ABCDEFGH"
        cols = range(1, 13)
    elif plate_format == 384:
        rows = "ABCDEFGHIJKLMNOP"
        cols = range(1, 25)
    else:
        raise ValueError(f"Unsupported plate format: {plate_format}")
    
    return [f"{r}{c:02d}" for r in rows for c in cols]

def get_exclusions(plate_format: int, include_edges: bool) -> Set[str]:
    """
    Get excluded wells.
    If include_edges is True, returns empty set.
    Otherwise, returns standard edge exclusions (1 ring for 96, 2 rings for 384).
    """
    exclusions = set()
    
    if include_edges:
        return exclusions

    if plate_format == 96:
        # Standard 1-ring exclusion
        rows = "ABCDEFGH"
        cols = range(1, 13)
        for c in cols:
            exclusions.add(f"A{c:02d}")
            exclusions.add(f"H{c:02d}")
        for r in rows:
            exclusions.add(f"{r}01")
            exclusions.add(f"{r}12")
            
    elif plate_format == 384:
        # 2-ring exclusion for 384
        rows = "ABCDEFGHIJKLMNOP"
        cols = range(1, 25)
        
        # Rows A, B, O, P
        for c in cols:
            exclusions.add(f"A{c:02d}")
            exclusions.add(f"B{c:02d}")
            exclusions.add(f"O{c:02d}")
            exclusions.add(f"P{c:02d}")
            
        # Cols 1, 2, 23, 24
        for r in rows:
            exclusions.add(f"{r}01")
            exclusions.add(f"{r}02")
            exclusions.add(f"{r}23")
            exclusions.add(f"{r}24")
            
    return exclusions

def create_custom_design(
    design_id: str,
    description: str,
    seed: int,
    plate_format: int,
    num_plates: int,
    cell_lines: List[str],
    stressors: List[str], # Changed from compounds
    doses: Dict[str, List[float]], # Keyed by STRESSOR name
    reps: int,
    vehicle_reps: int,
    vehicles: List[str],
    seeding_densities: Dict[str, int],
    include_edges: bool = False,
    use_scaffold: bool = False,
    sentinel_types: List[str] = None,
    sentinel_reps: int = 3
) -> Dict:
    """
    Generate a custom plate design with N plates.
    Implements Cartesian Product: All Cell Lines x All Compounds.
    """
    
    # 1. Setup Geometry
    all_pos = get_all_positions(plate_format)
    exclusions = get_exclusions(plate_format, include_edges)
    
    # Sentinel Handling
    sentinel_wells = []
    sentinel_positions = set()
    
    if use_scaffold:
        from phase0_sentinel_scaffold import get_dynamic_sentinel_tokens, SENTINEL_POSITIONS
        
        # Default to all pathways if none specified
        if not sentinel_types:
            sentinel_types = ["ER", "Mito", "Proteostasis", "Oxidative"]
            
        # Generate dynamic tokens (for up to 2 cell lines)
        tokens = get_dynamic_sentinel_tokens(
            cell_lines=cell_lines,
            pathways=sentinel_types,
            reps_per_pathway=sentinel_reps,
            vehicle_reps_per_cl=4
        )
        
        # Assign positions from the fixed pool first
        # Select sentinel pool based on format
        if plate_format == 384:
            pool = SENTINEL_POSITIONS_384.copy()
        else:
            pool = SENTINEL_POSITIONS.copy()
            
        rng_sentinel = make_rng(seed, "sentinel_layout")
        rng_sentinel.shuffle(pool)
        
        for tok in tokens:
            if pool:
                pos = pool.pop(0)
            else:
                # Overflow to usable experimental positions if pool is full
                # We'll handle this by adding them to sentinel_positions set
                # and assigning them later from the usable_pos pool
                # But for now, let's just raise an error if we exceed 28 for simplicity
                # OR we can just take from all_pos that are not exclusions
                available_overflow = [p for p in all_pos if p not in exclusions and p not in sentinel_positions]
                if not available_overflow:
                    raise ValueError("No more positions available for sentinels!")
                pos = available_overflow[0]
            
            sentinel_positions.add(pos)
            sentinel_wells.append({
                **tok,
                "dose_type": "sentinel_" + tok['sentinel_type'],
                "well_pos": pos,
                "seeding_density": seeding_densities.get(tok['cell_line'], 5000)
            })

    # Calculate usable positions
    usable_pos = [p for p in all_pos if p not in exclusions and p not in sentinel_positions]
    
    wells = []
    
    # 2. Build Experimental Tokens (Per Cell Line)
    tokens_per_plate = []
    
    # Add Vehicle Controls (For EACH vehicle type, for EACH cell line)
    for cl in cell_lines:
        density = seeding_densities.get(cl, 0)
        for vehicle in vehicles:
            for _ in range(vehicle_reps):
                tokens_per_plate.append({
                    "cell_line": cl,
                    "compound": vehicle,
                    "dose_uM": 0.0,
                    "dose_type": "vehicle",
                    "is_sentinel": False,
                    "seeding_density": density
                })
            
    # Add Experimental Conditions (Cartesian Product: Cell Lines x Stressors)
    for cl in cell_lines:
        density = seeding_densities.get(cl, 0)
        
        for stressor in stressors:
            # Get doses for this STRESSOR
            current_doses = doses.get(stressor, [])
            if not current_doses:
                 raise ValueError(f"No doses defined for stressor {stressor}")

            for dose in current_doses:
                for _ in range(reps):
                    tokens_per_plate.append({
                        "cell_line": cl,
                        "compound": stressor,
                        "dose_uM": dose,
                        "dose_type": "experimental",
                        "is_sentinel": False,
                        "seeding_density": density
                    })
                
    # Check Capacity
    if len(tokens_per_plate) > len(usable_pos):
        raise ValueError(
            f"Capacity Error: Design requires {len(tokens_per_plate)} experimental wells, "
            f"but only {len(usable_pos)} are available "
            f"(Format: {plate_format}, Edges: {include_edges}, Scaffold: {use_scaffold})."
        )
        
    print(f"  Plate Fill: {len(tokens_per_plate)} experimental + {len(sentinel_wells)} sentinels + {len(usable_pos) - len(tokens_per_plate)} filler")
    print(f"  Total Used: {len(usable_pos) + len(sentinel_wells)} / {len(all_pos)} wells")

    # 3. Generate N Plates
    for i in range(num_plates):
        plate_index = i + 1
        plate_id = f"Plate_{plate_index}"
        
        # Deterministic RNG for this plate
        rng = make_rng(seed, f"plate_{plate_index}")
        
        # Shuffle positions
        current_plate_positions = usable_pos.copy()
        rng.shuffle(current_plate_positions)
        
        # Assign experimental tokens to positions
        for token, pos in zip(tokens_per_plate, current_plate_positions):
            wells.append({
                **token,
                "plate_id": plate_id,
                "well_pos": pos,
                "plate_index": plate_index
            })
            
        # Fill remaining usable positions with vehicle filler
        remaining_pos = current_plate_positions[len(tokens_per_plate):]
        for idx, pos in enumerate(remaining_pos):
            # Alternate cell lines for filler
            cl = cell_lines[idx % len(cell_lines)]
            density = seeding_densities.get(cl, 0)
            # Use the first vehicle as the filler
            filler_vehicle = vehicles[0] if vehicles else "DMSO"
            
            wells.append({
                "cell_line": cl,
                "compound": filler_vehicle,
                "dose_uM": 0.0,
                "dose_type": "vehicle_filler",
                "is_sentinel": False,
                "seeding_density": density,
                "plate_id": plate_id,
                "well_pos": pos,
                "plate_index": plate_index
            })
            
        # Add Fixed Sentinels
        for s_tok in sentinel_wells:
            wells.append({
                **s_tok,
                "plate_id": plate_id,
                "plate_index": plate_index
            })
            
    # 4. Construct Design Object
    design = {
        "design_id": design_id,
        "design_type": "custom_generated",
        "description": description,
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "generator": "generate_custom_plate.py",
            "seed": seed,
            "plate_format": plate_format,
            "num_plates": num_plates,
            "cell_lines": cell_lines,
            "stressors": stressors,
            "doses": doses,
            "replicates_per_dose": reps,
            "vehicle_replicates": vehicle_reps,
            "vehicles": vehicles,
            "seeding_densities": seeding_densities,
            "include_edges": include_edges,
            "use_scaffold": use_scaffold,
            "sentinel_types": sentinel_types,
            "sentinel_reps": sentinel_reps
        },
        "wells": wells
    }
    
    return design

# -----------------------------------------------------------------------------
# CLI Interface
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a custom plate design JSON.")
    
    # Basic Metadata
    parser.add_argument("--output", type=str, required=True, help="Output JSON file path")
    parser.add_argument("--design-id", type=str, default="custom_design", help="ID for the design")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for layout")
    
    # Geometry & Replicates
    parser.add_argument("--format", type=int, choices=[96, 384], default=96, help="Plate format (96 or 384)")
    parser.add_argument("--num-plates", type=int, default=1, help="Number of replicate plates to generate")
    parser.add_argument("--include-edges", action="store_true", help="Include edge wells (disable default exclusions)")
    parser.add_argument("--scaffold", action="store_true", help="Include Phase 0 fixed sentinel scaffold")
    parser.add_argument("--sentinel-types", nargs="+", help="List of sentinel pathways (ER, Mito, Proteostasis, Oxidative)")
    parser.add_argument("--sentinel-reps", type=int, default=3, help="Replicates per sentinel pathway")
    
    # Experiment Configuration
    parser.add_argument("--cell-lines", nargs="+", default=["A549", "HepG2"], help="List of cell lines")
    parser.add_argument("--stressors", nargs="+", help="List of stressors (applied to all cell lines)")
    parser.add_argument("--seeding-densities", nargs="+", type=int, help="Seeding density per cell line (order matters)")
    
    # Dose Configuration
    parser.add_argument("--reps", type=int, default=8, help="Replicates per dose")
    parser.add_argument("--vehicle-reps", type=int, default=12, help="Replicates for vehicle control (per vehicle type)")
    parser.add_argument("--vehicles", nargs="+", default=["DMSO"], help="List of vehicle names (default: DMSO)")
    
    # Dose Configuration (Manual or Automatic)
    parser.add_argument("--doses", nargs="+", type=float, help="Manual list of dose multipliers (applied to all)")
    parser.add_argument("--start-dose", type=float, help="Highest dose (uM) for automatic ladder (applied to all)")
    parser.add_argument("--start-doses", nargs="+", type=float, help="List of highest doses (uM), one per stressor")
    parser.add_argument("--dilution-factor", type=float, help="Dilution factor (e.g., 3.0 for 1:3)")
    parser.add_argument("--num-doses", type=int, help="Number of dose steps")

    args = parser.parse_args()

    # Validate Seeding Densities
    seeding_map = {}
    if args.seeding_densities:
        if len(args.seeding_densities) != len(args.cell_lines):
            print(f"Error: You provided {len(args.cell_lines)} cell lines but {len(args.seeding_densities)} seeding densities. Counts must match.")
            sys.exit(1)
        for cl, dens in zip(args.cell_lines, args.seeding_densities):
            seeding_map[cl] = dens
    else:
        # Default density if not provided
        for cl in args.cell_lines:
            seeding_map[cl] = 5000 # Default placeholder

    # 1. Prepare Doses
    stressor_doses = {}
    if args.doses:
        # Manual doses applied to all stressors
        for s in args.stressors:
            stressor_doses[s] = args.doses
    elif args.start_dose or args.start_doses:
        # Automatic ladder
        num_doses = args.num_doses or 6
        df = args.dilution_factor or 2.0
        
        for idx, s in enumerate(args.stressors):
            if args.start_doses:
                if idx >= len(args.start_doses):
                    raise ValueError(f"Not enough start doses for stressor {s}")
                start = args.start_doses[idx]
            else:
                start = args.start_dose
            
            stressor_doses[s] = [start / (df ** i) for i in range(num_doses)]
    else:
        raise ValueError("Must provide either --doses or --start-dose/--start-doses")

    print(f"Generating design '{args.design_id}'...")
    print(f"  Format: {args.format}-well (Edges included: {args.include_edges})")
    print(f"  Scaffold: {args.scaffold}")
    print(f"  Plates: {args.num_plates}")
    print(f"  Cell Lines: {args.cell_lines}")
    print(f"  Seeding Densities: {seeding_map}")
    print(f"  Stressors: {args.stressors}")
    print(f"  Vehicles: {args.vehicles}")
    print(f"  Doses (First Stressor): {[f'{d:.4f}' for d in list(stressor_doses.values())[0]]}")

    # 2. Generate Design
    try:
        design = create_custom_design(
            design_id=args.design_id,
            description=f"Generated by CLI on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            seed=args.seed,
            plate_format=args.format,
            num_plates=args.num_plates,
            cell_lines=args.cell_lines,
            stressors=args.stressors,
            doses=stressor_doses,
            reps=args.reps,
            vehicle_reps=args.vehicle_reps,
            vehicles=args.vehicles,
            seeding_densities=seeding_map,
            include_edges=args.include_edges,
            use_scaffold=args.scaffold,
            sentinel_types=args.sentinel_types,
            sentinel_reps=args.sentinel_reps
        )
        
        # Ensure output directory exists
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(design, f, indent=2)
            
        print(f"Success! Design written to: {output_path}")
        
    except Exception as e:
        print(f"Error generating design: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
