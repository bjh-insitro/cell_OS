"""
Plate Executor: Parse and execute 384-well plate designs

Converts JSON plate designs (like CAL_384_RULES_WORLD_v2.json) into WellSpec lists
and executes them through BiologicalVirtualMachine.

Architecture:
1. parse_plate_design() - JSON → List[WellSpec]
2. execute_plate_design() - orchestrate simulation
3. save_results() - write to disk
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

from src.cell_os.epistemic_agent.schemas import WellSpec, Proposal
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.core.assay import AssayType
from src.cell_os.hardware.run_context import RunContext


@dataclass
class ParsedWell:
    """Intermediate representation of a well before WellSpec creation."""
    well_id: str  # e.g., "A1"
    row: str
    col: int
    cell_line: str
    treatment: str
    reagent: str
    dose_uM: float
    cell_density: str  # "LOW", "NOMINAL", "HIGH", "NONE"
    stain_scale: float
    fixation_timing_offset_min: float
    imaging_focus_offset_um: float
    timepoint_hours: float


def parse_plate_design_v2(json_path: Path) -> List[ParsedWell]:
    """
    Parse CAL_384_RULES_WORLD_v2.json into list of ParsedWell objects.

    Resolution order (first match wins):
    1. background_controls.wells_no_cells
    2. contrastive_tiles.tiles[].assignment
    3. biological_anchors.wells
    4. non_biological_provocations (stain, timing, focus)
    5. cell_density_gradient by column
    6. global_defaults.default_assignment
    """
    with open(json_path) as f:
        design = json.load(f)

    plate = design["plate"]
    global_defaults = design["global_defaults"]
    cell_lines_map = design["cell_lines"]["row_to_cell_line"]
    non_bio = design["non_biological_provocations"]
    anchors = design["biological_anchors"]
    tiles = design["contrastive_tiles"]

    # Build well assignments
    wells = []
    rows = plate["rows"]
    cols = plate["cols"]

    for row in rows:
        for col in cols:
            well_id = f"{row}{col}"

            # Start with global defaults
            assignment = global_defaults["default_assignment"].copy()
            assignment["timepoint_hours"] = global_defaults["timepoint_hours"]

            # Derive cell_line from row
            assignment["cell_line"] = cell_lines_map[row]

            # Apply cell density gradient by column (unless overridden later)
            if col in non_bio["cell_density_gradient"]["rule"]["LOW_cols"]:
                assignment["cell_density"] = "LOW"
            elif col in non_bio["cell_density_gradient"]["rule"]["HIGH_cols"]:
                assignment["cell_density"] = "HIGH"
            else:
                assignment["cell_density"] = "NOMINAL"

            # Apply non-biological provocations (higher precedence)

            # Stain scale probes
            if well_id in non_bio["stain_scale_probes"]["wells"]["STAIN_LOW"]:
                assignment["stain_scale"] = non_bio["stain_scale_probes"]["levels"]["STAIN_LOW"]
            elif well_id in non_bio["stain_scale_probes"]["wells"]["STAIN_HIGH"]:
                assignment["stain_scale"] = non_bio["stain_scale_probes"]["levels"]["STAIN_HIGH"]

            # Fixation timing probes
            if well_id in non_bio["fixation_timing_probes"]["wells"]["EARLY_FIX"]:
                assignment["fixation_timing_offset_min"] = non_bio["fixation_timing_probes"]["levels"]["EARLY_FIX"]
            elif well_id in non_bio["fixation_timing_probes"]["wells"]["LATE_FIX"]:
                assignment["fixation_timing_offset_min"] = non_bio["fixation_timing_probes"]["levels"]["LATE_FIX"]

            # Focus probes
            if well_id in non_bio["imaging_focus_probes"]["wells"]["FOCUS_MINUS"]:
                assignment["imaging_focus_offset_um"] = non_bio["imaging_focus_probes"]["levels"]["FOCUS_MINUS"]
            elif well_id in non_bio["imaging_focus_probes"]["wells"]["FOCUS_PLUS"]:
                assignment["imaging_focus_offset_um"] = non_bio["imaging_focus_probes"]["levels"]["FOCUS_PLUS"]

            # Biological anchors (higher precedence)
            if well_id in anchors["wells"]["ANCHOR_MORPH"]:
                anchor = [a for a in anchors["anchors"] if a["anchor_id"] == "ANCHOR_MORPH"][0]
                assignment["treatment"] = "ANCHOR_MORPH"
                assignment["reagent"] = anchor["reagent"]
                assignment["dose_uM"] = anchor["dose_uM"]
            elif well_id in anchors["wells"]["ANCHOR_DEATH"]:
                anchor = [a for a in anchors["anchors"] if a["anchor_id"] == "ANCHOR_DEATH"][0]
                assignment["treatment"] = "ANCHOR_DEATH"
                assignment["reagent"] = anchor["reagent"]
                assignment["dose_uM"] = anchor["dose_uM"]

            # Contrastive tiles (highest precedence except background)
            for tile in tiles["tiles"]:
                if well_id in tile["wells"]:
                    tile_assignment = tile["assignment"]
                    assignment["treatment"] = tile_assignment["treatment"]
                    assignment["reagent"] = tile_assignment["reagent"]
                    assignment["dose_uM"] = tile_assignment["dose_uM"]
                    # Tile may override density
                    if "cell_density" in tile_assignment:
                        assignment["cell_density"] = tile_assignment["cell_density"]
                    break

            # Background controls (highest precedence)
            if well_id in non_bio["background_controls"]["wells_no_cells"]:
                bg_assignment = non_bio["background_controls"]["assignment"]
                assignment.update(bg_assignment)

            # Create ParsedWell
            wells.append(ParsedWell(
                well_id=well_id,
                row=row,
                col=col,
                cell_line=assignment["cell_line"],
                treatment=assignment["treatment"],
                reagent=assignment["reagent"],
                dose_uM=assignment["dose_uM"],
                cell_density=assignment["cell_density"],
                stain_scale=assignment.get("stain_scale", 1.0),
                fixation_timing_offset_min=assignment.get("fixation_timing_offset_min", 0),
                imaging_focus_offset_um=assignment.get("imaging_focus_offset_um", 0),
                timepoint_hours=assignment["timepoint_hours"]
            ))

    return wells


def parse_plate_design_v3(json_path: Path) -> List[ParsedWell]:
    """
    Parse CAL_384_RULES_WORLD_v3/v4/v5.json into list of ParsedWell objects.

    Supports:
    - well_to_cell_line (checkerboard patterns)
    - reproducibility_islands with exclusion_rules

    Resolution order (first match wins):
    1. background_controls.wells_no_cells
    2. contrastive_tiles.tiles[].assignment
    3. reproducibility_islands (with forced settings)
    4. biological_anchors.wells
    5. non_biological_provocations (stain, timing, focus)
    6. cell_density_gradient by column
    7. global_defaults.default_assignment
    """
    with open(json_path) as f:
        design = json.load(f)

    plate = design["plate"]
    global_defaults = design["global_defaults"]
    cell_lines_map = design["cell_lines"]["well_to_cell_line"]
    non_bio = design["non_biological_provocations"]
    anchors = design["biological_anchors"]
    tiles = design["contrastive_tiles"]

    # Handle reproducibility islands if present
    island_wells_set = set()
    island_assignments = {}

    if "reproducibility_islands" in design:
        islands = design["reproducibility_islands"]["islands"]
        exclusion_rules = design["reproducibility_islands"].get("exclusion_rules", {})
        forced_fields = exclusion_rules.get("forced_fields", {})

        for island in islands:
            island_assignment = island.get("assignment", {})
            for well in island["wells"]:
                island_wells_set.add(well)
                # Merge island assignment with forced fields
                assignment = {
                    "cell_line": island["cell_line"],
                    "treatment": island_assignment.get("treatment", "VEHICLE"),
                    "reagent": island_assignment.get("reagent", "DMSO"),
                    "dose_uM": island_assignment.get("dose_uM", 0),
                }
                # Apply forced fields
                assignment.update(forced_fields)
                island_assignments[well] = assignment

    # Build well assignments
    wells = []
    rows = plate["rows"]
    cols = plate["cols"]

    for row in rows:
        for col in cols:
            well_id = f"{row}{col}"

            # Start with global defaults
            assignment = global_defaults["default_assignment"].copy()
            assignment["timepoint_hours"] = global_defaults["timepoint_hours"]

            # Get cell_line from well_to_cell_line map
            assignment["cell_line"] = cell_lines_map[well_id]

            # Apply cell density gradient by column (unless overridden later)
            if col in non_bio["cell_density_gradient"]["rule"]["LOW_cols"]:
                assignment["cell_density"] = "LOW"
            elif col in non_bio["cell_density_gradient"]["rule"]["HIGH_cols"]:
                assignment["cell_density"] = "HIGH"
            else:
                assignment["cell_density"] = "NOMINAL"

            # Apply non-biological provocations (unless in island)
            if well_id not in island_wells_set:
                # Stain scale probes
                if well_id in non_bio["stain_scale_probes"]["wells"]["STAIN_LOW"]:
                    assignment["stain_scale"] = non_bio["stain_scale_probes"]["levels"]["STAIN_LOW"]
                elif well_id in non_bio["stain_scale_probes"]["wells"]["STAIN_HIGH"]:
                    assignment["stain_scale"] = non_bio["stain_scale_probes"]["levels"]["STAIN_HIGH"]

                # Fixation timing probes
                if well_id in non_bio["fixation_timing_probes"]["wells"]["EARLY_FIX"]:
                    assignment["fixation_timing_offset_min"] = non_bio["fixation_timing_probes"]["levels"]["EARLY_FIX"]
                elif well_id in non_bio["fixation_timing_probes"]["wells"]["LATE_FIX"]:
                    assignment["fixation_timing_offset_min"] = non_bio["fixation_timing_probes"]["levels"]["LATE_FIX"]

                # Focus probes
                if well_id in non_bio["imaging_focus_probes"]["wells"]["FOCUS_MINUS"]:
                    assignment["imaging_focus_offset_um"] = non_bio["imaging_focus_probes"]["levels"]["FOCUS_MINUS"]
                elif well_id in non_bio["imaging_focus_probes"]["wells"]["FOCUS_PLUS"]:
                    assignment["imaging_focus_offset_um"] = non_bio["imaging_focus_probes"]["levels"]["FOCUS_PLUS"]

                # Biological anchors
                if well_id in anchors["wells"]["ANCHOR_MORPH"]:
                    anchor = [a for a in anchors["anchors"] if a["anchor_id"] == "ANCHOR_MORPH"][0]
                    assignment["treatment"] = "ANCHOR_MORPH"
                    assignment["reagent"] = anchor["reagent"]
                    assignment["dose_uM"] = anchor["dose_uM"]
                elif well_id in anchors["wells"]["ANCHOR_DEATH"]:
                    anchor = [a for a in anchors["anchors"] if a["anchor_id"] == "ANCHOR_DEATH"][0]
                    assignment["treatment"] = "ANCHOR_DEATH"
                    assignment["reagent"] = anchor["reagent"]
                    assignment["dose_uM"] = anchor["dose_uM"]

            # Reproducibility islands (high precedence)
            if well_id in island_assignments:
                assignment.update(island_assignments[well_id])

            # Contrastive tiles (higher precedence except background)
            for tile in tiles["tiles"]:
                if well_id in tile["wells"]:
                    tile_assignment = tile["assignment"]
                    assignment["treatment"] = tile_assignment["treatment"]
                    assignment["reagent"] = tile_assignment["reagent"]
                    assignment["dose_uM"] = tile_assignment["dose_uM"]
                    # Tile may override density
                    if "cell_density" in tile_assignment:
                        assignment["cell_density"] = tile_assignment["cell_density"]
                    break

            # Background controls (highest precedence)
            if well_id in non_bio["background_controls"]["wells_no_cells"]:
                bg_assignment = non_bio["background_controls"]["assignment"]
                assignment.update(bg_assignment)

            # Create ParsedWell
            wells.append(ParsedWell(
                well_id=well_id,
                row=row,
                col=col,
                cell_line=assignment["cell_line"],
                treatment=assignment["treatment"],
                reagent=assignment["reagent"],
                dose_uM=assignment["dose_uM"],
                cell_density=assignment["cell_density"],
                stain_scale=assignment.get("stain_scale", 1.0),
                fixation_timing_offset_min=assignment.get("fixation_timing_offset_min", 0),
                imaging_focus_offset_um=assignment.get("imaging_focus_offset_um", 0),
                timepoint_hours=assignment["timepoint_hours"]
            ))

    return wells


def parsed_wells_to_wellspecs(parsed_wells: List[ParsedWell]) -> List[WellSpec]:
    """
    Convert ParsedWell objects to WellSpec objects for simulation.

    WellSpec needs: cell_line, compound, dose_uM, time_h, position_tag, assay
    """
    wellspecs = []

    for pw in parsed_wells:
        # Map treatment/reagent to compound name
        # For DMSO/VEHICLE, use "DMSO"
        # For anchors, use reagent name (Nocodazole, Thapsigargin)
        if pw.treatment in ["VEHICLE", "VEHICLE_TILE", "VEHICLE_TILE_DENSITY_LOW", "VEHICLE_TILE_DENSITY_HIGH"]:
            compound = "DMSO"
        elif pw.treatment in ["NO_CELLS"]:
            compound = "NO_CELLS"  # Special marker for background wells
        else:
            compound = pw.reagent

        # Position tag: encode row + col + density info
        # This helps track plate effects later
        density_marker = ""
        if pw.cell_density == "LOW":
            density_marker = "_dens_low"
        elif pw.cell_density == "HIGH":
            density_marker = "_dens_high"
        elif pw.cell_density == "NONE":
            density_marker = "_no_cells"

        position_tag = f"{pw.well_id}{density_marker}"

        wellspec = WellSpec(
            cell_line=pw.cell_line,
            compound=compound,
            dose_uM=pw.dose_uM,
            time_h=pw.timepoint_hours,
            position_tag=position_tag,
            assay=AssayType.CELL_PAINTING  # Primary assay
        )

        wellspecs.append(wellspec)

    return wellspecs


def execute_plate_design(
    json_path: Path,
    seed: int = 42,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Execute full 384-well plate simulation with batch processing.

    Args:
        json_path: Path to JSON plate design
        seed: Random seed for reproducibility
        output_dir: Optional directory to save results
        verbose: Print progress messages

    Returns:
        Dictionary with:
        - plate_id: Plate identifier
        - seed: Random seed used
        - n_wells: Number of wells executed
        - parsed_wells: List[dict] - metadata for each well
        - raw_results: List[dict] - simulation results per well
        - metadata: Summary statistics
    """
    if verbose:
        print(f"{'='*70}")
        print(f"CAL_384 Plate Executor - Full Simulation")
        print(f"{'='*70}")
        print(f"\nLoading plate design: {json_path.name}")

    # Auto-detect parser version based on plate format
    with open(json_path) as f:
        design = json.load(f)

    if "well_to_cell_line" in design["cell_lines"]:
        # V3/V4/V5 format with well-based cell line assignment
        parsed_wells = parse_plate_design_v3(json_path)
    else:
        # V2 format with row-based cell line assignment
        parsed_wells = parse_plate_design_v2(json_path)

    if verbose:
        print(f"✓ Parsed {len(parsed_wells)} wells")

    # Convert to WellSpecs
    wellspecs = parsed_wells_to_wellspecs(parsed_wells)

    # Summary statistics
    cell_lines = set(pw.cell_line for pw in parsed_wells if pw.cell_line != "NONE")
    treatments = set(pw.treatment for pw in parsed_wells)
    compounds = set(pw.reagent for pw in parsed_wells if pw.reagent != "DMSO")

    if verbose:
        print(f"\nPlate summary:")
        print(f"  Cell lines: {', '.join(sorted(cell_lines))}")
        print(f"  Compounds: {', '.join(sorted(compounds))}")
        print(f"  Treatments: {len(treatments)} unique")

    # Initialize RunContext and BiologicalVirtualMachine
    if verbose:
        print(f"\nInitializing BiologicalVirtualMachine (seed={seed})...")

    run_context = RunContext.sample(seed=seed)
    vm = BiologicalVirtualMachine(seed=seed, run_context=run_context)

    # Execute batch simulation
    raw_results = []

    if verbose:
        print(f"\nExecuting {len(parsed_wells)} wells...")

    for i, (pw, ws) in enumerate(zip(parsed_wells, wellspecs)):
        if verbose and (i + 1) % 96 == 0:
            print(f"  Progress: {i + 1}/{len(parsed_wells)} wells ({100*(i+1)//len(parsed_wells)}%)")

        # Handle NO_CELLS wells (background controls)
        if pw.treatment == "NO_CELLS":
            result = {
                "well_id": pw.well_id,
                "cell_line": "NONE",
                "compound": "NO_CELLS",
                "dose_uM": 0.0,
                "time_h": pw.timepoint_hours,
                "position_tag": ws.position_tag,
                "assay": "cell_painting",
                "morphology": {
                    "er": 0.0,      # Background fluorescence
                    "mito": 0.0,
                    "nucleus": 0.0,
                    "actin": 0.0,
                    "rna": 0.0
                },
                "morphology_struct": {
                    "er": 0.0,
                    "mito": 0.0,
                    "nucleus": 0.0,
                    "actin": 0.0,
                    "rna": 0.0
                },
                "viability": 0.0,
                "n_cells": 0,
                # Provenance
                "treatment": pw.treatment,
                "cell_density": pw.cell_density,
                "stain_scale": pw.stain_scale,
                "fixation_offset_min": pw.fixation_timing_offset_min,
                "focus_offset_um": pw.imaging_focus_offset_um
            }
            raw_results.append(result)
            continue

        # Normal wells with cells: create independent vessel per well
        vessel_id = f"well_{pw.well_id}_{pw.cell_line}"

        # Parse density scale from cell_density annotation
        density_scale = 1.0
        if pw.cell_density == "LOW":
            density_scale = 0.7
        elif pw.cell_density == "HIGH":
            density_scale = 1.3

        # Seed vessel with scaled cell count
        initial_cells = int(1e6 * density_scale)
        vm.seed_vessel(vessel_id, pw.cell_line, initial_count=initial_cells)

        # Apply treatment if not DMSO
        if pw.reagent != "DMSO" and pw.dose_uM > 0:
            vm.treat_with_compound(vessel_id, pw.reagent.lower(), pw.dose_uM)

        # Advance time to measurement timepoint
        vm.advance_time(pw.timepoint_hours)

        # Execute Cell Painting assay
        try:
            cp_result = vm.cell_painting_assay(vessel_id)

            # Get vessel state for cell count
            vessel = vm.vessel_states.get(vessel_id, None)
            n_cells = int(vessel.cell_count) if vessel else 0

            # Package result
            result = {
                "well_id": pw.well_id,
                "cell_line": pw.cell_line,
                "compound": pw.reagent,
                "dose_uM": pw.dose_uM,
                "time_h": pw.timepoint_hours,
                "position_tag": ws.position_tag,
                "assay": "cell_painting",
                "morphology": cp_result.get("morphology", {}),  # Cell Painting channels
                "morphology_struct": cp_result.get("morphology_struct", {}),  # True structural state
                "viability": cp_result.get("viability", 1.0),
                "n_cells": n_cells,
                # Provenance from plate design
                "treatment": pw.treatment,
                "cell_density": pw.cell_density,
                "stain_scale": pw.stain_scale,
                "fixation_offset_min": pw.fixation_timing_offset_min,
                "focus_offset_um": pw.imaging_focus_offset_um,
                # Additional metadata
                "initial_cell_count": initial_cells,
                "density_scale": density_scale,
                "run_context_id": cp_result.get("run_context_id", ""),
                "batch_id": cp_result.get("batch_id", "")
            }

        except Exception as e:
            # If well fails, log error but continue
            if verbose:
                print(f"    ⚠️  Well {pw.well_id} failed: {e}")

            result = {
                "well_id": pw.well_id,
                "error": str(e),
                "cell_line": pw.cell_line,
                "compound": pw.reagent,
                "dose_uM": pw.dose_uM,
                "treatment": pw.treatment
            }

        raw_results.append(result)

    if verbose:
        print(f"\n✓ Simulation complete: {len(raw_results)} wells")

    # Count successes vs failures
    n_success = sum(1 for r in raw_results if "error" not in r)
    n_failed = len(raw_results) - n_success

    if verbose and n_failed > 0:
        print(f"  ⚠️  {n_failed} wells failed")

    # Package output
    treatment_counts = {}
    for pw in parsed_wells:
        treatment_counts[pw.treatment] = treatment_counts.get(pw.treatment, 0) + 1

    output = {
        "plate_id": json_path.stem,
        "seed": seed,
        "n_wells": len(raw_results),
        "n_success": n_success,
        "n_failed": n_failed,
        "parsed_wells": [vars(pw) for pw in parsed_wells],
        "raw_results": raw_results,
        "metadata": {
            "cell_lines": list(cell_lines),
            "treatments": list(treatments),
            "compounds": list(compounds),
            "treatment_counts": treatment_counts
        }
    }

    # Save results if output_dir provided
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{json_path.stem}_results_seed{seed}.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        if verbose:
            print(f"\n✓ Results saved: {output_file}")

    return output


if __name__ == "__main__":
    # Test execution
    import sys

    json_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")

    if not json_path.exists():
        print(f"✗ Plate design not found: {json_path}")
        sys.exit(1)

    # Run full simulation
    results = execute_plate_design(
        json_path=json_path,
        seed=42,
        output_dir=Path("results/calibration_plates"),
        verbose=True
    )

    print(f"\n{'='*70}")
    print(f"EXECUTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Wells executed: {results['n_wells']}")
    print(f"  Successful: {results['n_success']}")
    if results['n_failed'] > 0:
        print(f"  Failed: {results['n_failed']}")
    print(f"  Cell lines: {', '.join(results['metadata']['cell_lines'])}")
    print(f"  Treatments: {len(results['metadata']['treatments'])}")
    print(f"\nResults saved to: results/calibration_plates/")
    print(f"\nTo analyze results:")
    print(f"  python -c \"import json; print(json.load(open('results/calibration_plates/CAL_384_RULES_WORLD_v2_results_seed42.json')))\"\")")
