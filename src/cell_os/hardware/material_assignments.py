"""
Material Assignment Mapping - Single Source of Truth

Maps assignment strings from plate designs → MaterialState constructor params.
This prevents silent failures when plate JSON uses unmapped assignment names.

Design:
- Every assignment string in CAL_384_MICROSCOPE_BEADS_DYES_v1.json is mapped
- Unmapped strings fail loudly with helpful error
- No scattered string checks in executor logic (single table)

Usage:
    material = create_material_from_assignment(
        assignment_name="FLATFIELD_DYE_LOW",
        well_position="H12"
    )
"""

from typing import Dict, Any
from .material_state import (
    MaterialState,
    MATERIAL_NOMINAL_INTENSITIES,
    MATERIAL_TYPE_MAP,
    MATERIAL_SPATIAL_PATTERNS
)


# Single source of truth: assignment string → material properties
ASSIGNMENT_TO_MATERIAL = {
    'DARK': {
        'material_type': 'buffer_only',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['DARK'],
        'spatial_pattern': None,
        'bead_count': None,
        'description': 'Buffer only - camera baseline and read noise measurement'
    },
    'BLANK': {
        'material_type': 'buffer_only',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['BLANK'],
        'spatial_pattern': None,
        'bead_count': None,
        'description': 'Empty well or minimal buffer - dust/autofluorescence check'
    },
    'FLATFIELD_DYE_LOW': {
        'material_type': 'fluorescent_dye_solution',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        'spatial_pattern': None,
        'bead_count': None,
        'description': 'Low intensity uniform dye - floor-limited regime and linearity'
    },
    'FLATFIELD_DYE_HIGH': {
        'material_type': 'fluorescent_dye_solution',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_HIGH'],
        'spatial_pattern': None,
        'bead_count': None,
        'description': 'High intensity uniform dye - saturation testing and dynamic range'
    },
    'MULTICOLOR_BEADS_SPARSE': {
        'material_type': 'fluorescent_beads',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['MULTICOLOR_BEADS_SPARSE'],
        'spatial_pattern': 'sparse',
        'bead_count': None,  # Uses default from BEAD_COUNTS['sparse']
        'description': 'Sparse multicolor beads - registration, focus sensitivity, PSF'
    },
    'MULTICOLOR_BEADS_DENSE': {
        'material_type': 'fluorescent_beads',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['MULTICOLOR_BEADS_DENSE'],
        'spatial_pattern': 'dense',
        'bead_count': None,  # Uses default from BEAD_COUNTS['dense']
        'description': 'Dense multicolor beads - repeatability, robust statistics'
    },
    'FOCUS_BEADS': {
        'material_type': 'fluorescent_beads',
        'base_intensities': MATERIAL_NOMINAL_INTENSITIES['FOCUS_BEADS'],
        'spatial_pattern': 'medium',
        'bead_count': None,  # Uses default from BEAD_COUNTS['medium']
        'description': 'Bright beads for autofocus - field curvature mapping'
    },
}


def create_material_from_assignment(
    assignment_name: str,
    well_position: str,
    seed: int = 0
) -> MaterialState:
    """
    Create MaterialState from plate assignment string.

    Args:
        assignment_name: Assignment from plate design (e.g., "FLATFIELD_DYE_LOW")
        well_position: Well ID (e.g., "H12")
        seed: Optional seed for MaterialState (not used for RNG, just metadata)

    Returns:
        MaterialState instance

    Raises:
        ValueError: If assignment_name is not in mapping table (with helpful error)
    """
    # Normalize: uppercase, strip whitespace
    assignment_name = assignment_name.upper().strip()

    if assignment_name not in ASSIGNMENT_TO_MATERIAL:
        # Fail loudly with helpful error
        valid_assignments = sorted(ASSIGNMENT_TO_MATERIAL.keys())
        raise ValueError(
            f"Unknown material assignment: '{assignment_name}'\n"
            f"Valid assignments: {valid_assignments}\n"
            f"This assignment must be mapped in material_assignments.py"
        )

    # Lookup properties
    props = ASSIGNMENT_TO_MATERIAL[assignment_name]

    # Create MaterialState
    material = MaterialState(
        material_id=f"material_{well_position}_{assignment_name}",
        material_type=props['material_type'],
        well_position=well_position,
        base_intensities=props['base_intensities'],
        spatial_pattern=props['spatial_pattern'],
        bead_count=props['bead_count'],
        seed=seed
    )

    return material


def validate_plate_assignments(plate_design: Dict[str, Any]) -> None:
    """
    Validate all assignments in plate design are mapped.

    Scans plate JSON for all material assignments and checks mapping table.
    Fails loudly if any assignments are unmapped.

    Args:
        plate_design: Loaded plate design JSON dict

    Raises:
        ValueError: If any assignments are unmapped (with list of missing)
    """
    # Extract all assignments from plate design
    assignments_used = set()

    # Check explicit_assignments section
    if 'explicit_assignments' in plate_design:
        for group_name, group_data in plate_design['explicit_assignments'].items():
            if 'material' in group_data:
                assignments_used.add(group_data['material'])

    # Check repeatability_tiles section
    if 'repeatability_tiles' in plate_design:
        tiles = plate_design['repeatability_tiles'].get('tiles', [])
        for tile in tiles:
            if 'material' in tile:
                assignments_used.add(tile['material'])

    # Check default assignment
    if 'layout_strategy' in plate_design:
        default_mat = plate_design['layout_strategy'].get('default_assignment', {}).get('material')
        if default_mat:
            assignments_used.add(default_mat)

    # Check all assignments are mapped
    unmapped = []
    for assignment in assignments_used:
        assignment_normalized = assignment.upper().strip()
        if assignment_normalized not in ASSIGNMENT_TO_MATERIAL:
            unmapped.append(assignment)

    if unmapped:
        valid_assignments = sorted(ASSIGNMENT_TO_MATERIAL.keys())
        raise ValueError(
            f"Plate design uses unmapped material assignments: {sorted(unmapped)}\n"
            f"Valid assignments: {valid_assignments}\n"
            f"Add missing assignments to ASSIGNMENT_TO_MATERIAL in material_assignments.py"
        )


def get_all_valid_assignments() -> list[str]:
    """Get list of all valid assignment names (for documentation/validation)."""
    return sorted(ASSIGNMENT_TO_MATERIAL.keys())
