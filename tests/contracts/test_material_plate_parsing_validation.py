"""
Contract tests for material plate parsing validation.

Verifies loud failure modes for malformed plate designs:
- Overlapping explicit assignments (well in multiple groups)
- Unmapped material assignments

Runtime: <0.1 seconds (pure parsing, no execution)
"""

import pytest
import json
from pathlib import Path
from src.cell_os.plate_executor_v2 import parse_plate_design_v2


def test_overlapping_explicit_assignments_fail_loudly():
    """
    Wells appearing in multiple explicit assignment groups must fail loudly.

    Calibration plates should be strict - if JSON is inconsistent, fail.
    """
    # Create malformed plate design with overlapping assignments
    malformed_design = {
        "schema_version": "microscope_calibration_plate_v1",
        "plate": {
            "plate_id": "TEST_OVERLAP",
            "format": "384",
            "rows": ["A"],
            "cols": [1, 2, 3]
        },
        "layout_strategy": {
            "default_assignment": {"material": "DARK"}
        },
        "explicit_assignments": {
            "group1": {
                "material": "FLATFIELD_DYE_LOW",
                "wells": ["A1", "A2"]
            },
            "group2": {
                "material": "MULTICOLOR_BEADS_SPARSE",
                "wells": ["A2", "A3"]  # A2 overlaps with group1
            }
        }
    }

    # Write to temp file
    temp_file = Path("/tmp/test_overlapping_assignments.json")
    with open(temp_file, 'w') as f:
        json.dump(malformed_design, f)

    # Parse should fail with helpful error
    try:
        with pytest.raises(ValueError, match="appears in multiple explicit assignment groups"):
            parsed_wells, metadata = parse_plate_design_v2(temp_file)
        print("✓ Overlapping assignments fail loudly with helpful error")
    finally:
        temp_file.unlink()


def test_unmapped_material_assignment_fails():
    """
    Unmapped material assignments must fail loudly (no silent fallback).

    This was already covered in Phase 1, but verify it works at plate level.
    """
    # Create plate with unknown material
    malformed_design = {
        "schema_version": "microscope_calibration_plate_v1",
        "plate": {
            "plate_id": "TEST_UNMAPPED",
            "format": "384",
            "rows": ["A"],
            "cols": [1]
        },
        "layout_strategy": {
            "default_assignment": {"material": "NONEXISTENT_MATERIAL"}
        }
    }

    temp_file = Path("/tmp/test_unmapped_material.json")
    with open(temp_file, 'w') as f:
        json.dump(malformed_design, f)

    try:
        # Parse succeeds (parsing doesn't validate materials)
        parsed_wells, metadata = parse_plate_design_v2(temp_file)

        # But execution should fail when trying to create material
        from src.cell_os.hardware.material_assignments import create_material_from_assignment

        pw = parsed_wells[0]
        with pytest.raises(ValueError, match="Unknown material assignment"):
            create_material_from_assignment(pw.material_assignment, pw.well_id, seed=0)

        print("✓ Unmapped materials fail loudly with helpful error")
    finally:
        temp_file.unlink()


def test_valid_plate_with_no_overlaps_succeeds():
    """
    Valid plate design with no overlaps should parse successfully.
    """
    valid_design = {
        "schema_version": "microscope_calibration_plate_v1",
        "plate": {
            "plate_id": "TEST_VALID",
            "format": "384",
            "rows": ["A"],
            "cols": [1, 2, 3]
        },
        "layout_strategy": {
            "default_assignment": {"material": "DARK"}
        },
        "explicit_assignments": {
            "group1": {
                "material": "FLATFIELD_DYE_LOW",
                "wells": ["A1"]
            },
            "group2": {
                "material": "MULTICOLOR_BEADS_SPARSE",
                "wells": ["A2"]
            }
            # A3 gets default (DARK)
        }
    }

    temp_file = Path("/tmp/test_valid_plate.json")
    with open(temp_file, 'w') as f:
        json.dump(valid_design, f)

    try:
        parsed_wells, metadata = parse_plate_design_v2(temp_file)
        assert len(parsed_wells) == 3
        assert parsed_wells[0].material_assignment == "FLATFIELD_DYE_LOW"
        assert parsed_wells[1].material_assignment == "MULTICOLOR_BEADS_SPARSE"
        assert parsed_wells[2].material_assignment == "DARK"  # Default

        print("✓ Valid plate with no overlaps parses successfully")
    finally:
        temp_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
