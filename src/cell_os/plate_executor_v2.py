"""
Plate Executor V2: Corrected implementation with proper time semantics

Key fixes:
1. Per-well isolated simulation (fixes time accumulation bug)
2. Non-biological provocations actually affect measurements
3. Realistic background wells (not all zeros)
4. Robust compound normalization and validation
5. Precomputed maps for performance
6. Flattened output for analysis

Architecture:
1. validate_plate_design() - upfront validation
2. parse_plate_design_v2() - JSON → List[ParsedWell] with precomputed maps
3. execute_well() - isolated per-well simulation
4. execute_plate_design() - orchestrate execution
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass, asdict
import numpy as np

from src.cell_os.epistemic_agent.schemas import WellSpec
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.core.assay import AssayType
from src.cell_os.hardware.run_context import RunContext


# ============================================================================
# Compound Normalization and Validation
# ============================================================================

# Canonical compound name registry (maps aliases → canonical name)
COMPOUND_ALIASES = {
    # Oxidative stress
    'tbhq': 'tbhq',
    't-bhq': 'tbhq',
    'tert-butylhydroquinone': 'tbhq',
    'h2o2': 'h2o2',
    'hydrogen_peroxide': 'h2o2',
    'hydrogen peroxide': 'h2o2',
    'tbhp': 'tbhp',

    # ER stress
    'tunicamycin': 'tunicamycin',
    'thapsigargin': 'thapsigargin',
    'tg': 'thapsigargin',

    # Mitochondrial
    'cccp': 'cccp',
    'oligomycin': 'oligomycin',
    'oligomycin_a': 'oligomycin',
    'oligomycin a': 'oligomycin',
    'two_deoxy_d_glucose': 'two_deoxy_d_glucose',
    '2-dg': 'two_deoxy_d_glucose',
    '2dg': 'two_deoxy_d_glucose',

    # DNA damage
    'etoposide': 'etoposide',
    'cisplatin': 'cisplatin',
    'doxorubicin': 'doxorubicin',
    'staurosporine': 'staurosporine',

    # Proteasome
    'mg132': 'mg132',
    'mg-132': 'mg132',

    # Microtubule
    'nocodazole': 'nocodazole',
    'paclitaxel': 'paclitaxel',

    # Vehicle
    'dmso': 'dmso',
    'vehicle': 'dmso',
}


def canonicalize_compound(reagent: str) -> str:
    """
    Normalize compound name to canonical form.

    Args:
        reagent: Raw compound name from plate design

    Returns:
        Canonical compound name

    Raises:
        ValueError: If compound cannot be resolved
    """
    # Normalize: lowercase, strip whitespace, replace underscores
    normalized = reagent.lower().strip().replace('_', '').replace('-', '').replace(' ', '')

    # Also try original casing normalized
    for pattern in [normalized, reagent.lower().strip()]:
        if pattern in COMPOUND_ALIASES:
            return COMPOUND_ALIASES[pattern]

    # Not found
    raise ValueError(
        f"Unknown compound '{reagent}'. "
        f"Known compounds: {sorted(set(COMPOUND_ALIASES.values()))}"
    )


def validate_compounds(parsed_wells: List['ParsedWell']) -> None:
    """
    Validate all compounds in design can be resolved.

    Raises:
        ValueError: With list of unknown compounds
    """
    unknown = set()
    for pw in parsed_wells:
        if pw.reagent == "DMSO":
            continue
        try:
            canonicalize_compound(pw.reagent)
        except ValueError:
            unknown.add(pw.reagent)

    if unknown:
        raise ValueError(
            f"Unknown compounds in plate design: {sorted(unknown)}. "
            f"Valid compounds: {sorted(set(COMPOUND_ALIASES.values()))}"
        )


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ParsedWell:
    """Intermediate representation of a well before execution."""
    well_id: str  # e.g., "A1"
    row: str
    col: int
    cell_line: str
    treatment: str
    reagent: str  # Raw name from JSON
    dose_uM: float
    cell_density: str  # "LOW", "NOMINAL", "HIGH", "NONE"
    stain_scale: float
    fixation_timing_offset_min: float
    imaging_focus_offset_um: float
    timepoint_hours: float


@dataclass
class MeasurementContext:
    """Context for non-biological provocations applied during measurement."""
    stain_scale: float = 1.0
    fixation_timing_offset_min: float = 0.0
    imaging_focus_offset_um: float = 0.0
    cell_density: str = "NOMINAL"
    well_position: str = ""  # For spatial effects

    def to_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs for cell_painting_assay."""
        return {
            'stain_scale': self.stain_scale,
            'fixation_offset_min': self.fixation_timing_offset_min,
            'focus_offset_um': self.imaging_focus_offset_um,
            'cell_density': self.cell_density,
            'well_position': self.well_position
        }


# ============================================================================
# Parsing with Validation
# ============================================================================

def build_assignment_maps(design: Dict) -> Tuple[Dict, Dict, Dict]:
    """
    Precompute assignment maps for fast lookup and validate overlaps.

    Returns:
        (well_to_tile, well_to_anchor, well_to_probe_type)

    Raises:
        ValueError: If wells appear in multiple exclusive categories
    """
    well_to_tile = {}
    well_to_anchor = {}
    well_to_probe_type = {}

    # Build tile map
    for tile in design['contrastive_tiles']['tiles']:
        tile_id = tile['tile_id']
        for well_id in tile['wells']:
            if well_id in well_to_tile:
                raise ValueError(f"Well {well_id} appears in multiple tiles: {well_to_tile[well_id]} and {tile_id}")
            well_to_tile[well_id] = tile

    # Build anchor map
    for anchor_type, wells in design['biological_anchors']['wells'].items():
        for well_id in wells:
            if well_id in well_to_anchor:
                raise ValueError(f"Well {well_id} appears in multiple anchor types")
            well_to_anchor[well_id] = anchor_type

    # Build probe map (stain, fixation, focus)
    non_bio = design['non_biological_provocations']

    for probe_type in ['stain_scale_probes', 'fixation_timing_probes', 'imaging_focus_probes']:
        if probe_type not in non_bio:
            continue
        for level, wells in non_bio[probe_type]['wells'].items():
            for well_id in wells:
                if well_id not in well_to_probe_type:
                    well_to_probe_type[well_id] = {}
                well_to_probe_type[well_id][probe_type] = level

    return well_to_tile, well_to_anchor, well_to_probe_type


def parse_plate_design_v2(json_path: Path) -> Tuple[List[ParsedWell], Dict]:
    """
    Parse plate design with validation and precomputed maps.

    Returns:
        (parsed_wells, metadata) where metadata contains precomputed maps
    """
    with open(json_path) as f:
        design = json.load(f)

    # Precompute assignment maps and validate
    well_to_tile, well_to_anchor, well_to_probe_type = build_assignment_maps(design)

    plate = design["plate"]
    global_defaults = design["global_defaults"]
    cell_lines_map = design["cell_lines"]["row_to_cell_line"]
    non_bio = design["non_biological_provocations"]
    anchors_data = {a['anchor_id']: a for a in design['biological_anchors']['anchors']}

    # Background wells set (highest precedence)
    background_wells = set(non_bio['background_controls']['wells_no_cells'])

    wells = []
    rows = plate["rows"]
    cols = plate["cols"]

    for row in rows:
        for col in cols:
            well_id = f"{row}{col}"

            # Start with defaults
            assignment = global_defaults["default_assignment"].copy()
            assignment["timepoint_hours"] = global_defaults["timepoint_hours"]
            assignment["cell_line"] = cell_lines_map[row]

            # Apply density gradient by column
            if col in non_bio["cell_density_gradient"]["rule"]["LOW_cols"]:
                assignment["cell_density"] = "LOW"
            elif col in non_bio["cell_density_gradient"]["rule"]["HIGH_cols"]:
                assignment["cell_density"] = "HIGH"
            else:
                assignment["cell_density"] = "NOMINAL"

            # Apply probe settings
            if well_id in well_to_probe_type:
                probes = well_to_probe_type[well_id]
                if 'stain_scale_probes' in probes:
                    level = probes['stain_scale_probes']
                    assignment["stain_scale"] = non_bio["stain_scale_probes"]["levels"][level]
                if 'fixation_timing_probes' in probes:
                    level = probes['fixation_timing_probes']
                    assignment["fixation_timing_offset_min"] = non_bio["fixation_timing_probes"]["levels"][level]
                if 'imaging_focus_probes' in probes:
                    level = probes['imaging_focus_probes']
                    assignment["imaging_focus_offset_um"] = non_bio["imaging_focus_probes"]["levels"][level]

            # Apply anchors
            if well_id in well_to_anchor:
                anchor_id = well_to_anchor[well_id]
                anchor = anchors_data[anchor_id]
                assignment["treatment"] = anchor_id
                assignment["reagent"] = anchor["reagent"]
                assignment["dose_uM"] = anchor["dose_uM"]

            # Apply tiles (overrides anchors)
            if well_id in well_to_tile:
                tile = well_to_tile[well_id]
                tile_assignment = tile["assignment"]
                assignment["treatment"] = tile_assignment["treatment"]
                assignment["reagent"] = tile_assignment["reagent"]
                assignment["dose_uM"] = tile_assignment["dose_uM"]
                if "cell_density" in tile_assignment:
                    assignment["cell_density"] = tile_assignment["cell_density"]

            # Apply background (highest precedence)
            if well_id in background_wells:
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

    metadata = {
        'well_to_tile': well_to_tile,
        'well_to_anchor': well_to_anchor,
        'well_to_probe_type': well_to_probe_type,
        'background_wells': background_wells
    }

    return wells, metadata


# ============================================================================
# Well Execution with Isolated Simulation
# ============================================================================

def compute_initial_cells(cell_density: str, base_count: int = 1_000_000) -> int:
    """Compute initial cell count based on density annotation."""
    density_multipliers = {
        "LOW": 0.7,
        "NOMINAL": 1.0,
        "HIGH": 1.3,
        "NONE": 0
    }
    return int(base_count * density_multipliers.get(cell_density, 1.0))


def generate_background_morphology(
    rng: np.random.Generator,
    measurement_ctx: MeasurementContext
) -> Dict[str, float]:
    """
    Generate realistic background fluorescence for NO_CELLS wells.

    Background includes:
    - Per-channel baseline offsets
    - Measurement noise
    - Stain scale effects
    - Spatial gradients (via well position)
    """
    # Baseline background per channel (arbitrary units, typical autofluorescence)
    baseline = {
        'er': 15.0,
        'mito': 12.0,
        'nucleus': 20.0,  # DAPI has higher background
        'actin': 10.0,
        'rna': 18.0
    }

    # Apply stain scale
    for ch in baseline:
        baseline[ch] *= measurement_ctx.stain_scale

    # Add shot noise (Poisson-like, ~10% CV)
    for ch in baseline:
        baseline[ch] *= rng.normal(1.0, 0.10)

    # Floor at zero
    for ch in baseline:
        baseline[ch] = max(0.0, baseline[ch])

    return baseline


def stable_hash_seed(base_seed: int, *components: str) -> int:
    """Generate deterministic seed from base seed and string components."""
    h = hashlib.blake2s(digest_size=4)
    h.update(str(base_seed).encode())
    for comp in components:
        h.update(str(comp).encode())
    return int.from_bytes(h.digest(), byteorder='little', signed=False)


def execute_well(
    pw: ParsedWell,
    base_seed: int,
    run_context: RunContext,
    plate_id: str = "CAL_384"
) -> Dict[str, Any]:
    """
    Execute a single well with isolated simulation.

    Args:
        pw: Parsed well specification
        base_seed: Base random seed for plate
        run_context: Shared RunContext for plate-level batch effects
        plate_id: Plate identifier for technical noise

    Returns:
        Result dictionary with measurements and metadata
    """
    # Deterministic per-well seed
    well_seed = stable_hash_seed(base_seed, pw.well_id, pw.cell_line)

    # Create fresh VM per well (fixes time accumulation bug)
    vm = BiologicalVirtualMachine(seed=well_seed, run_context=run_context)

    # Build measurement context
    measurement_ctx = MeasurementContext(
        stain_scale=pw.stain_scale,
        fixation_timing_offset_min=pw.fixation_timing_offset_min,
        imaging_focus_offset_um=pw.imaging_focus_offset_um,
        cell_density=pw.cell_density,
        well_position=pw.well_id
    )

    try:
        # Handle NO_CELLS wells (background controls)
        if pw.treatment == "NO_CELLS":
            rng = np.random.default_rng(well_seed)
            background = generate_background_morphology(rng, measurement_ctx)

            return {
                "well_id": pw.well_id,
                "row": pw.row,
                "col": pw.col,
                "cell_line": "NONE",
                "compound": "NO_CELLS",
                "dose_uM": 0.0,
                "time_h": pw.timepoint_hours,
                "assay": "cell_painting",
                "morphology": background,
                "morphology_struct": {k: 0.0 for k in background.keys()},  # True structure is zero
                "viability": 0.0,
                "n_cells": 0,
                "treatment": pw.treatment,
                "cell_density": pw.cell_density,
                **measurement_ctx.to_kwargs()
            }

        # Normal wells with cells
        vessel_id = f"well_{pw.well_id}_{pw.cell_line}"
        initial_cells = compute_initial_cells(pw.cell_density)

        vm.seed_vessel(vessel_id, pw.cell_line, initial_count=initial_cells)

        # Apply treatment if not vehicle
        if pw.reagent != "DMSO" and pw.dose_uM > 0:
            canonical_compound = canonicalize_compound(pw.reagent)
            vm.treat_with_compound(vessel_id, canonical_compound, pw.dose_uM)

        # Advance time to target timepoint (VM starts at t=0)
        vm.advance_time(pw.timepoint_hours)

        # Execute Cell Painting assay with measurement context
        assay_kwargs = {
            'plate_id': plate_id,
            **measurement_ctx.to_kwargs()
        }
        cp_result = vm.cell_painting_assay(vessel_id, **assay_kwargs)

        # Get final vessel state
        vessel = vm.vessel_states.get(vessel_id)
        n_cells = int(vessel.cell_count) if vessel else 0

        return {
            "well_id": pw.well_id,
            "row": pw.row,
            "col": pw.col,
            "cell_line": pw.cell_line,
            "compound": pw.reagent,
            "dose_uM": pw.dose_uM,
            "time_h": pw.timepoint_hours,
            "assay": "cell_painting",
            "morphology": cp_result.get("morphology", {}),
            "morphology_struct": cp_result.get("morphology_struct", {}),
            "viability": cp_result.get("viability", 1.0),
            "n_cells": n_cells,
            "treatment": pw.treatment,
            "cell_density": pw.cell_density,
            "initial_cell_count": initial_cells,
            "run_context_id": cp_result.get("run_context_id", ""),
            "batch_id": cp_result.get("batch_id", ""),
            "well_seed": well_seed,
            **measurement_ctx.to_kwargs()
        }

    except Exception as e:
        return {
            "well_id": pw.well_id,
            "row": pw.row,
            "col": pw.col,
            "error": str(e),
            "cell_line": pw.cell_line,
            "compound": pw.reagent,
            "dose_uM": pw.dose_uM,
            "treatment": pw.treatment
        }


# ============================================================================
# Flattened Output for Analysis
# ============================================================================

def flatten_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested morphology dicts into scalar columns for DataFrame compatibility.

    Converts:
        morphology: {er: 100, mito: 200, ...}
    To:
        morph_er: 100, morph_mito: 200, ...
    """
    flat = {k: v for k, v in result.items() if k not in ['morphology', 'morphology_struct']}

    # Flatten morphology
    if 'morphology' in result:
        for ch, val in result['morphology'].items():
            flat[f'morph_{ch}'] = val

    # Flatten morphology_struct
    if 'morphology_struct' in result:
        for ch, val in result['morphology_struct'].items():
            flat[f'struct_{ch}'] = val

    return flat


# ============================================================================
# Plate Execution
# ============================================================================

def execute_plate_design(
    json_path: Path,
    seed: int = 42,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Execute full 384-well plate simulation with corrected time semantics.

    Args:
        json_path: Path to JSON plate design
        seed: Random seed for reproducibility
        output_dir: Optional directory to save results
        verbose: Print progress messages

    Returns:
        Dictionary with results and metadata
    """
    if verbose:
        print(f"{'='*70}")
        print(f"CAL_384 Plate Executor V2 - Corrected Implementation")
        print(f"{'='*70}")
        print(f"\nLoading plate design: {json_path.name}")

    # Parse with validation
    parsed_wells, parse_metadata = parse_plate_design_v2(json_path)
    if verbose:
        print(f"✓ Parsed {len(parsed_wells)} wells")

    # Validate compounds
    validate_compounds(parsed_wells)
    if verbose:
        print(f"✓ Validated all compounds")

    # Summary statistics
    cell_lines = set(pw.cell_line for pw in parsed_wells if pw.cell_line != "NONE")
    treatments = set(pw.treatment for pw in parsed_wells)
    compounds = set(pw.reagent for pw in parsed_wells if pw.reagent != "DMSO")

    if verbose:
        print(f"\nPlate summary:")
        print(f"  Cell lines: {', '.join(sorted(cell_lines))}")
        print(f"  Compounds: {', '.join(sorted(compounds))}")
        print(f"  Treatments: {len(treatments)} unique")
        print(f"  Background wells: {len(parse_metadata['background_wells'])}")
        print(f"\nExecution mode: Per-well isolated simulation")
        print(f"Seed: {seed}")

    # Create shared RunContext for plate-level batch effects
    run_context = RunContext.sample(seed=seed)
    plate_id = json_path.stem

    if verbose:
        print(f"\nExecuting {len(parsed_wells)} wells...")

    # Execute wells
    raw_results = []
    for i, pw in enumerate(parsed_wells):
        if verbose and (i + 1) % 96 == 0:
            print(f"  Progress: {i + 1}/{len(parsed_wells)} wells ({100*(i+1)//len(parsed_wells)}%)")

        result = execute_well(pw, seed, run_context, plate_id)
        raw_results.append(result)

    if verbose:
        print(f"\n✓ Simulation complete: {len(raw_results)} wells")

    # Count successes vs failures
    n_success = sum(1 for r in raw_results if "error" not in r)
    n_failed = len(raw_results) - n_success

    if verbose and n_failed > 0:
        print(f"  ⚠️  {n_failed} wells failed")

    # Generate flattened results for analysis
    flat_results = [flatten_result(r) for r in raw_results]

    # Package output
    treatment_counts = {}
    for pw in parsed_wells:
        treatment_counts[pw.treatment] = treatment_counts.get(pw.treatment, 0) + 1

    output = {
        "plate_id": plate_id,
        "seed": seed,
        "n_wells": len(raw_results),
        "n_success": n_success,
        "n_failed": n_failed,
        "parsed_wells": [asdict(pw) for pw in parsed_wells],
        "raw_results": raw_results,
        "flat_results": flat_results,  # New: for pandas DataFrame
        "metadata": {
            "cell_lines": list(cell_lines),
            "treatments": list(treatments),
            "compounds": list(compounds),
            "treatment_counts": treatment_counts,
            **parse_metadata
        }
    }

    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{plate_id}_results_seed{seed}.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        if verbose:
            print(f"\n✓ Results saved: {output_file}")

    return output


if __name__ == "__main__":
    import sys

    json_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")

    if not json_path.exists():
        print(f"✗ Plate design not found: {json_path}")
        sys.exit(1)

    # Run with corrected time semantics
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
