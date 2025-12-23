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

    Note: v1 designs are converted to v2 format before this function is called.

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
    design, well_to_tile, well_to_anchor, well_to_probe_type = _load_and_validate_design(json_path)
    design_components = _extract_design_components(design)
    background_wells = set(design_components['non_bio']['background_controls']['wells_no_cells'])

    wells = []
    for row in design_components['rows']:
        for col in design_components['cols']:
            well_id = f"{row}{col}"
            assignment = _build_well_assignment(
                well_id, row, col,
                design_components,
                well_to_tile, well_to_anchor, well_to_probe_type,
                background_wells
            )
            wells.append(_create_parsed_well(well_id, row, col, assignment))

    metadata = _build_metadata(well_to_tile, well_to_anchor, well_to_probe_type, background_wells)
    return wells, metadata


def _convert_v1_to_v2_format(v1_design: Dict) -> Dict:
    """
    Convert v1 plate design format to v2 format for uniform processing.

    v1 has simple structure: tiles, anchors, cell_lines
    v2 has structured format: contrastive_tiles, biological_anchors, non_biological_provocations
    """
    # Build row_to_cell_line mapping from v1 cell_lines
    row_to_cell_line = {}
    for cell_line_id, cell_line_info in v1_design['cell_lines'].items():
        for row in cell_line_info['rows']:
            row_to_cell_line[row] = cell_line_info['name']

    # Convert anchors to v2 format
    biological_anchors = {
        'anchors': []
    }
    anchor_wells_by_type = {}

    for anchor_type, anchor_info in v1_design.get('anchors', {}).items():
        biological_anchors['anchors'].append({
            'anchor_id': anchor_type,
            'treatment': f"ANCHOR_{anchor_type}",
            'reagent': "Nocodazole",  # Default for v1
            'dose_uM': anchor_info.get('dose', 1.0),
            'notes': f"{anchor_type} anchor"
        })
        anchor_wells_by_type[anchor_type] = anchor_info['wells']

    biological_anchors['wells'] = anchor_wells_by_type

    # Convert tiles to v2 contrastive_tiles format
    contrastive_tiles = {'tiles': []}
    if 'tiles' in v1_design and 'wells' in v1_design['tiles']:
        contrastive_tiles['tiles'].append({
            'tile_id': 'TILE_V1',
            'wells': v1_design['tiles']['wells'],
            'description': v1_design['tiles'].get('description', 'Tile wells from v1'),
            'assignment': {
                'treatment': 'VEHICLE_TILE',
                'reagent': 'DMSO',
                'dose_uM': 0
            }
        })

    # Build v2 design
    v2_design = {
        'schema_version': 'calibration_plate_v2',
        'plate': v1_design['plate'],
        'intent': v1_design.get('intent', 'Converted from v1 format'),
        'global_defaults': {
            'timepoint_hours': 48,  # Default
            'default_assignment': {
                'treatment': 'VEHICLE',
                'reagent': 'DMSO',
                'dose_uM': 0,
                'cell_density': 'NOMINAL',
                'stain_scale': 1.0,
                'fixation_timing_offset_min': 0,
                'imaging_focus_offset_um': 0,
                'notes': 'Default for v1 conversion'
            }
        },
        'cell_lines': {
            'strategy': 'row_assignment',
            'row_to_cell_line': row_to_cell_line
        },
        'biological_anchors': biological_anchors,
        'contrastive_tiles': contrastive_tiles,
        'non_biological_provocations': {
            'background_controls': {
                'wells_no_cells': []  # v1 doesn't have explicit background wells
            },
            'cell_density_gradient': {
                'rule': {
                    'LOW_cols': [],
                    'HIGH_cols': [],
                    'NOMINAL_cols': list(range(1, 25))
                }
            }
        }
    }

    return v2_design


def _load_and_validate_design(json_path: Path):
    """Load JSON design and build assignment maps."""
    with open(json_path) as f:
        design = json.load(f)

    # Convert v1 to v2 format if needed
    if design.get('schema_version') == 'calibration_plate_v1':
        design = _convert_v1_to_v2_format(design)

    well_to_tile, well_to_anchor, well_to_probe_type = build_assignment_maps(design)
    return design, well_to_tile, well_to_anchor, well_to_probe_type


def _extract_design_components(design: Dict) -> Dict:
    """Extract key components from design specification."""
    # Handle both row-based (v2) and well-based (v3 checkerboard) cell line mappings
    cell_lines = design["cell_lines"]
    if "well_to_cell_line" in cell_lines:
        # v3 checkerboard: well-level mapping
        cell_lines_map = cell_lines["well_to_cell_line"]
        cell_lines_strategy = "checkerboard"
    else:
        # v2 interleaved or v1 blocked: row-level mapping
        cell_lines_map = cell_lines["row_to_cell_line"]
        cell_lines_strategy = "row_based"

    return {
        'plate': design["plate"],
        'rows': design["plate"]["rows"],
        'cols': design["plate"]["cols"],
        'global_defaults': design["global_defaults"],
        'cell_lines_map': cell_lines_map,
        'cell_lines_strategy': cell_lines_strategy,
        'non_bio': design["non_biological_provocations"],
        'anchors_data': {a['anchor_id']: a for a in design['biological_anchors']['anchors']}
    }


def _build_well_assignment(
    well_id: str,
    row: str,
    col: int,
    design_components: Dict,
    well_to_tile: Dict,
    well_to_anchor: Dict,
    well_to_probe_type: Dict,
    background_wells: set
) -> Dict:
    """Build complete assignment for a single well by applying precedence rules."""
    global_defaults = design_components['global_defaults']
    cell_lines_map = design_components['cell_lines_map']
    cell_lines_strategy = design_components['cell_lines_strategy']
    non_bio = design_components['non_bio']
    anchors_data = design_components['anchors_data']

    # Initialize with defaults
    assignment = global_defaults["default_assignment"].copy()
    assignment["timepoint_hours"] = global_defaults["timepoint_hours"]

    # Get cell line based on strategy (row-based or well-based)
    if cell_lines_strategy == "checkerboard":
        assignment["cell_line"] = cell_lines_map[well_id]
    else:
        assignment["cell_line"] = cell_lines_map[row]

    # Apply modifications in precedence order (lowest to highest)
    _apply_density_gradient(assignment, col, non_bio)
    _apply_probe_settings(assignment, well_id, well_to_probe_type, non_bio)
    _apply_anchor(assignment, well_id, well_to_anchor, anchors_data)
    _apply_tile(assignment, well_id, well_to_tile)
    _apply_background(assignment, well_id, background_wells, non_bio)

    return assignment


def _apply_density_gradient(assignment: Dict, col: int, non_bio: Dict):
    """Apply cell density gradient based on column."""
    gradient = non_bio["cell_density_gradient"]["rule"]
    if col in gradient["LOW_cols"]:
        assignment["cell_density"] = "LOW"
    elif col in gradient["HIGH_cols"]:
        assignment["cell_density"] = "HIGH"
    else:
        assignment["cell_density"] = "NOMINAL"


def _apply_probe_settings(assignment: Dict, well_id: str, well_to_probe_type: Dict, non_bio: Dict):
    """Apply probe settings (stain scale, fixation timing, imaging focus)."""
    if well_id not in well_to_probe_type:
        return

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


def _apply_anchor(assignment: Dict, well_id: str, well_to_anchor: Dict, anchors_data: Dict):
    """Apply biological anchor (treatment, reagent, dose)."""
    if well_id not in well_to_anchor:
        return

    anchor_id = well_to_anchor[well_id]
    anchor = anchors_data[anchor_id]
    assignment["treatment"] = anchor_id
    assignment["reagent"] = anchor["reagent"]
    assignment["dose_uM"] = anchor["dose_uM"]


def _apply_tile(assignment: Dict, well_id: str, well_to_tile: Dict):
    """Apply contrastive tile (overrides anchors)."""
    if well_id not in well_to_tile:
        return

    tile = well_to_tile[well_id]
    tile_assignment = tile["assignment"]
    assignment["treatment"] = tile_assignment["treatment"]
    assignment["reagent"] = tile_assignment["reagent"]
    assignment["dose_uM"] = tile_assignment["dose_uM"]
    if "cell_density" in tile_assignment:
        assignment["cell_density"] = tile_assignment["cell_density"]


def _apply_background(assignment: Dict, well_id: str, background_wells: set, non_bio: Dict):
    """Apply background control (highest precedence)."""
    if well_id in background_wells:
        bg_assignment = non_bio["background_controls"]["assignment"]
        assignment.update(bg_assignment)


def _create_parsed_well(well_id: str, row: str, col: int, assignment: Dict) -> ParsedWell:
    """Create ParsedWell object from assignment dictionary."""
    return ParsedWell(
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
    )


def _build_metadata(
    well_to_tile: Dict,
    well_to_anchor: Dict,
    well_to_probe_type: Dict,
    background_wells: set
) -> Dict:
    """Build metadata dictionary with precomputed maps."""
    return {
        'well_to_tile': well_to_tile,
        'well_to_anchor': well_to_anchor,
        'well_to_probe_type': well_to_probe_type,
        'background_wells': list(background_wells)  # Convert set to list for JSON
    }


# ============================================================================
# Well Execution with Isolated Simulation
# ============================================================================

def compute_initial_cells(
    cell_line: str,
    vessel_type: str,
    cell_density: str
) -> int:
    """
    Compute initial cell count from database based on cell line, vessel type, and density level.

    Args:
        cell_line: Cell line identifier (e.g., "A549", "HepG2")
        vessel_type: Vessel type (e.g., "384-well", "96-well")
        cell_density: Density level ("LOW", "NOMINAL", "HIGH", "NONE")

    Returns:
        Number of cells to seed

    Note: This replaces the old hardcoded base_count approach with database lookup.
    """
    if cell_density == "NONE":
        return 0

    from src.cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed(cell_line, vessel_type, cell_density)


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
    plate_id: str = "CAL_384",
    vessel_type: str = "384-well"
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
    # Disable database to avoid SQLite locking in parallel execution
    vm = BiologicalVirtualMachine(seed=well_seed, run_context=run_context, use_database=False)

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
        initial_cells = compute_initial_cells(pw.cell_line, vessel_type, pw.cell_density)

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

    # Load design to extract plate format
    with open(json_path) as f:
        design = json.load(f)
    plate_format = design.get("plate", {}).get("format", "384")
    vessel_type = f"{plate_format}-well"

    # Parse with validation
    parsed_wells, parse_metadata = parse_plate_design_v2(json_path)
    if verbose:
        print(f"✓ Parsed {len(parsed_wells)} wells (format: {vessel_type})")

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

        result = execute_well(pw, seed, run_context, plate_id, vessel_type)
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
