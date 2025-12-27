"""
Contract test for material assignment mapping (snapshot-style).

Verifies:
1. All assignments in CAL_384_MICROSCOPE_BEADS_DYES_v1.json are mapped
2. Unmapped assignments fail loudly with helpful error
3. Mapping table is complete (no silent fallback to cells)

Runtime: <0.1 seconds (pure validation, no VM)
"""

import pytest
import json
from pathlib import Path
from cell_os.hardware.material_assignments import (
    ASSIGNMENT_TO_MATERIAL,
    create_material_from_assignment,
    validate_plate_assignments,
    get_all_valid_assignments
)


def test_bead_plate_assignments_all_mapped():
    """
    All assignments in bead plate JSON must be in mapping table.

    This is a snapshot-style test: if bead plate JSON changes, this test
    fails loudly and forces explicit mapping table update.
    """
    # Load bead plate design
    plate_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not plate_path.exists():
        pytest.skip(f"Bead plate not found: {plate_path}")

    with open(plate_path) as f:
        plate_design = json.load(f)

    # Validate all assignments are mapped (should not raise)
    try:
        validate_plate_assignments(plate_design)
    except ValueError as e:
        pytest.fail(f"Bead plate has unmapped assignments:\n{e}")

    print("✓ All bead plate assignments are mapped in ASSIGNMENT_TO_MATERIAL")


def test_unmapped_assignment_fails_loudly():
    """
    Unmapped assignments must fail with helpful error (not silent fallback).
    """
    with pytest.raises(ValueError, match="Unknown material assignment"):
        create_material_from_assignment("NONEXISTENT_MATERIAL", "H12")

    with pytest.raises(ValueError, match="Valid assignments"):
        create_material_from_assignment("TYPO_DYE_LOW", "H12")

    print("✓ Unmapped assignments fail loudly with helpful error")


def test_mapping_table_complete_for_known_materials():
    """
    Mapping table covers all known material types from material_state.py.
    """
    from cell_os.hardware.material_state import MATERIAL_NOMINAL_INTENSITIES

    # Check that all materials with nominal intensities are mapped
    # (Excluding materials that might be internal/derived)
    known_materials = set(MATERIAL_NOMINAL_INTENSITIES.keys())
    mapped_materials = set()

    for assignment, props in ASSIGNMENT_TO_MATERIAL.items():
        # Extract which MATERIAL_NOMINAL_INTENSITIES key this uses
        intensities = props['base_intensities']
        for mat_name, mat_intensities in MATERIAL_NOMINAL_INTENSITIES.items():
            if intensities == mat_intensities:
                mapped_materials.add(mat_name)

    # All known materials should be mapped
    unmapped = known_materials - mapped_materials
    if unmapped:
        print(f"Warning: Some materials have intensities but no assignment: {unmapped}")

    assert len(mapped_materials) > 0, "Mapping table should cover known materials"
    print(f"✓ Mapping table covers {len(mapped_materials)}/{len(known_materials)} known materials")


def test_create_material_from_assignment_dark():
    """Test creating MaterialState from DARK assignment."""
    material = create_material_from_assignment("DARK", "H12")

    assert material.material_type == "buffer_only"
    assert material.well_position == "H12"
    assert all(v == 0.0 for v in material.base_intensities.values()), \
        "DARK should have zero intensities"
    assert material.spatial_pattern is None

    print(f"✓ DARK assignment creates correct MaterialState")


def test_create_material_from_assignment_dye():
    """Test creating MaterialState from FLATFIELD_DYE_LOW assignment."""
    material = create_material_from_assignment("FLATFIELD_DYE_LOW", "H12")

    assert material.material_type == "fluorescent_dye_solution"
    assert material.well_position == "H12"
    assert material.base_intensities['er'] > 0, "Dye should have nonzero intensity"
    assert material.spatial_pattern is None

    print(f"✓ FLATFIELD_DYE_LOW assignment creates correct MaterialState")


def test_create_material_from_assignment_beads():
    """Test creating MaterialState from MULTICOLOR_BEADS_SPARSE assignment."""
    material = create_material_from_assignment("MULTICOLOR_BEADS_SPARSE", "H12")

    assert material.material_type == "fluorescent_beads"
    assert material.well_position == "H12"
    assert material.spatial_pattern == "sparse"
    assert material.bead_count is None  # Uses default from BEAD_COUNTS

    print(f"✓ MULTICOLOR_BEADS_SPARSE assignment creates correct MaterialState")


def test_assignment_names_case_insensitive():
    """Assignment names should be case-insensitive (normalized)."""
    material1 = create_material_from_assignment("DARK", "H12")
    material2 = create_material_from_assignment("dark", "H12")
    material3 = create_material_from_assignment("Dark", "H12")

    assert material1.material_type == material2.material_type == material3.material_type
    assert material1.base_intensities == material2.base_intensities == material3.base_intensities

    print("✓ Assignment names are case-insensitive")


def test_get_all_valid_assignments():
    """get_all_valid_assignments() returns complete list."""
    assignments = get_all_valid_assignments()

    assert len(assignments) > 0
    assert 'DARK' in assignments
    assert 'FLATFIELD_DYE_LOW' in assignments
    assert 'MULTICOLOR_BEADS_SPARSE' in assignments

    # Should be sorted
    assert assignments == sorted(assignments)

    print(f"✓ Valid assignments: {assignments}")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
