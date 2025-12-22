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
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Execute full plate simulation.

    Args:
        json_path: Path to JSON plate design
        seed: Random seed for reproducibility
        output_dir: Optional directory to save results

    Returns:
        Dictionary with:
        - parsed_wells: List[ParsedWell]
        - wellspecs: List[WellSpec]
        - raw_results: List of simulation outputs
        - metadata: plate_id, seed, timestamp
    """
    print(f"Loading plate design: {json_path.name}")

    # Parse plate design
    parsed_wells = parse_plate_design_v2(json_path)
    print(f"Parsed {len(parsed_wells)} wells")

    # Convert to WellSpecs
    wellspecs = parsed_wells_to_wellspecs(parsed_wells)
    print(f"Created {len(wellspecs)} WellSpec objects")

    # Summary statistics
    cell_lines = set(pw.cell_line for pw in parsed_wells)
    treatments = set(pw.treatment for pw in parsed_wells)
    compounds = set(pw.reagent for pw in parsed_wells)

    print(f"\nPlate summary:")
    print(f"  Cell lines: {', '.join(sorted(cell_lines))}")
    print(f"  Treatments: {len(treatments)} unique")
    print(f"  Compounds: {', '.join(sorted(compounds))}")

    # Count by treatment type
    treatment_counts = {}
    for pw in parsed_wells:
        treatment_counts[pw.treatment] = treatment_counts.get(pw.treatment, 0) + 1

    print(f"\nWell distribution:")
    for treatment, count in sorted(treatment_counts.items(), key=lambda x: -x[1]):
        print(f"  {treatment}: {count} wells")

    # Initialize BiologicalVirtualMachine
    print(f"\nInitializing BiologicalVirtualMachine (seed={seed})...")
    vm = BiologicalVirtualMachine(seed=seed)

    # Seed vessels for each cell line
    # For NO_CELLS wells, we'll handle specially
    for cell_line in cell_lines:
        if cell_line != "NONE":
            vessel_id = f"plate_384_{cell_line}"
            vm.seed_vessel(vessel_id, cell_line, initial_count=1e6)
            print(f"  Seeded vessel: {vessel_id} with {cell_line}")

    # Execute each well
    print(f"\nExecuting plate simulation...")
    raw_results = []

    for i, (pw, ws) in enumerate(zip(parsed_wells, wellspecs)):
        if (i + 1) % 96 == 0:
            print(f"  Progress: {i + 1}/{len(parsed_wells)} wells")

        # For NO_CELLS wells, we need to handle differently
        # For now, skip or return mock data
        if pw.treatment == "NO_CELLS":
            # Background control - no cells, just measure background
            result = {
                "well_id": pw.well_id,
                "cell_line": "NONE",
                "compound": "NO_CELLS",
                "dose_uM": 0.0,
                "time_h": pw.timepoint_hours,
                "position_tag": ws.position_tag,
                "assay": "cell_painting",
                "channels": {
                    "ER": 0.0,  # Background signal
                    "Mito": 0.0,
                    "Nucleus": 0.0,
                    "Actin": 0.0,
                    "RNA": 0.0
                },
                "ldh": 0.0,  # No cells = no LDH release
                "viability": 0.0,
                "n_cells": 0
            }
            raw_results.append(result)
            continue

        # Normal wells with cells
        vessel_id = f"plate_384_{pw.cell_line}"

        # Apply treatment (compound + dose)
        if pw.compound != "DMSO" and pw.dose_uM > 0:
            vm.add_treatment(vessel_id, pw.reagent, pw.dose_uM)

        # Advance time to timepoint
        vm.advance_time(pw.timepoint_hours)

        # Execute Cell Painting assay
        cp_result = vm.cell_painting_assay(vessel_id)

        # Package result
        result = {
            "well_id": pw.well_id,
            "cell_line": pw.cell_line,
            "compound": pw.reagent,
            "dose_uM": pw.dose_uM,
            "time_h": pw.timepoint_hours,
            "position_tag": ws.position_tag,
            "assay": "cell_painting",
            "channels": cp_result.get("channels", {}),
            "ldh": cp_result.get("ldh", 0.0),
            "viability": cp_result.get("viability", 1.0),
            "n_cells": cp_result.get("n_cells", 0),
            # Store provenance from plate design
            "treatment": pw.treatment,
            "cell_density": pw.cell_density,
            "stain_scale": pw.stain_scale,
            "fixation_offset_min": pw.fixation_timing_offset_min,
            "focus_offset_um": pw.imaging_focus_offset_um
        }

        raw_results.append(result)

        # Reset vessel for next well (each well is independent)
        # In reality, each well is a separate physical well
        # For simulation, we re-seed
        vm.seed_vessel(vessel_id, pw.cell_line, initial_count=1e6)

    print(f"\n✓ Simulation complete: {len(raw_results)} wells")

    # Package output
    output = {
        "plate_id": json_path.stem,
        "seed": seed,
        "n_wells": len(raw_results),
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

        print(f"\n✓ Results saved: {output_file}")

    return output


if __name__ == "__main__":
    # Test execution
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")

    if not json_path.exists():
        print(f"✗ Plate design not found: {json_path}")
        exit(1)

    results = execute_plate_design(
        json_path=json_path,
        seed=42,
        output_dir=Path("results/calibration_plates")
    )

    print(f"\n{'='*70}")
    print(f"EXECUTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Wells executed: {results['n_wells']}")
    print(f"  Cell lines: {', '.join(results['metadata']['cell_lines'])}")
    print(f"  Treatments: {len(results['metadata']['treatments'])}")
