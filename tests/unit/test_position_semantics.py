"""
Semantic teeth tests: Prevent position round-trip inference.

These tests enforce that:
1. Position abstractions (edge/center) are DERIVED from physical location
2. No reverse inference (well_id → position_tag → stored separately)
3. SpatialLocation.position_class is the canonical way to derive position
4. Canonical Well does not have position_tag field
"""

from dataclasses import fields

from cell_os.core.experiment import Well, SpatialLocation, Treatment
from cell_os.core.assay import AssayType


def test_spatial_location_derives_position_class():
    """position_class must be derived from well_id, not stored."""

    # Edge wells
    edge_locations = [
        SpatialLocation("Plate1", "A01"),  # Top-left corner
        SpatialLocation("Plate1", "A12"),  # Top-right corner
        SpatialLocation("Plate1", "H01"),  # Bottom-left corner
        SpatialLocation("Plate1", "H12"),  # Bottom-right corner
        SpatialLocation("Plate1", "D01"),  # Left edge, middle
        SpatialLocation("Plate1", "D12"),  # Right edge, middle
    ]

    for loc in edge_locations:
        assert loc.position_class == "edge", f"{loc.well_id} should be edge"

    # Center wells
    center_locations = [
        SpatialLocation("Plate1", "B02"),  # Interior
        SpatialLocation("Plate1", "D06"),  # Middle
        SpatialLocation("Plate1", "G11"),  # Interior, near edge but not on edge
    ]

    for loc in center_locations:
        assert loc.position_class == "center", f"{loc.well_id} should be center"


def test_position_class_is_property_not_field():
    """position_class must be a derived property, not stored field.

    This prevents storing abstract position tags separately from location.
    """
    location = SpatialLocation("Plate1", "A01")

    # position_class is accessible
    assert location.position_class == "edge"

    # But it's not stored as a field (it's computed)
    location_fields = {f.name for f in fields(SpatialLocation)}
    assert "position_class" not in location_fields, \
        "position_class must be property, not field (prevents storage)"


def test_well_does_not_have_position_tag():
    """Canonical Well must not have position_tag field.

    Position is represented by SpatialLocation, and abstractions
    are derived via location.position_class.
    """
    well_fields = {f.name for f in fields(Well)}

    # location field exists
    assert "location" in well_fields

    # But position_tag does not
    assert "position_tag" not in well_fields, \
        "Well must not have position_tag - use location.position_class instead"


def test_position_abstraction_derived_not_stored():
    """Demonstrate the correct pattern: derive abstractions, don't store them.

    WRONG pattern (causes round-trips):
    1. Agent specifies position_tag="edge"
    2. World allocates to well_id="A01"
    3. World reverse-infers position_tag="edge" from well_id
    4. position_tag stored in ConditionSummary

    CORRECT pattern (no round-trips):
    1. Agent specifies position_tag="edge" (legacy input)
    2. World allocates to well_id="A01"
    3. World creates SpatialLocation("Plate1", "A01")
    4. position_class derived from location.position_class when needed
    """
    # Correct: physical location is source of truth
    location = SpatialLocation(plate_id="Plate1", well_id="A01")

    # Abstraction is derived on demand
    position = location.position_class

    # No separate storage of position_tag
    # position_class is computed every time it's accessed
    assert position == "edge"


def test_edge_detection_96_well():
    """Test edge detection for standard 96-well plate.

    96-well plate layout:
    - Rows: A-H (8 rows)
    - Columns: 01-12 (12 columns)
    - Edge: A/H rows, 01/12 columns
    - Center: all others
    """
    # All A row is edge
    for col in range(1, 13):
        loc = SpatialLocation("P1", f"A{col:02d}")
        assert loc.position_class == "edge", f"A{col:02d} should be edge"

    # All H row is edge
    for col in range(1, 13):
        loc = SpatialLocation("P1", f"H{col:02d}")
        assert loc.position_class == "edge", f"H{col:02d} should be edge"

    # Column 01 is edge
    for row in "ABCDEFGH":
        loc = SpatialLocation("P1", f"{row}01")
        assert loc.position_class == "edge", f"{row}01 should be edge"

    # Column 12 is edge
    for row in "ABCDEFGH":
        loc = SpatialLocation("P1", f"{row}12")
        assert loc.position_class == "edge", f"{row}12 should be edge"

    # Interior wells are center
    interior_wells = ["B02", "B11", "C05", "D06", "G11"]
    for well_id in interior_wells:
        loc = SpatialLocation("P1", well_id)
        assert loc.position_class == "center", f"{well_id} should be center"


def test_position_class_handles_invalid_well_ids():
    """position_class should handle invalid well_ids gracefully."""
    # Empty well_id
    loc = SpatialLocation("P1", "")
    assert loc.position_class == "unknown"

    # Too short
    loc = SpatialLocation("P1", "A")
    assert loc.position_class == "unknown"

    # Invalid format
    loc = SpatialLocation("P1", "ABC")
    assert loc.position_class == "unknown"


def test_no_reverse_inference_in_canonical_types():
    """Canonical types must not do position_tag round-trips.

    This test documents the anti-pattern to avoid:
    - Storing position_tag separately from location
    - Inferring position_tag from well_id
    - Round-tripping between abstract and concrete representations
    """
    # Canonical Well has location (concrete)
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="A01")
    )

    # Position is derived FROM location
    position = well.location.position_class if well.location else "unknown"
    assert position == "edge"

    # Well itself doesn't store position_tag
    assert not hasattr(well, 'position_tag'), \
        "Canonical Well must not have position_tag attribute"


if __name__ == '__main__':
    test_spatial_location_derives_position_class()
    test_position_class_is_property_not_field()
    test_well_does_not_have_position_tag()
    test_position_abstraction_derived_not_stored()
    test_edge_detection_96_well()
    test_position_class_handles_invalid_well_ids()
    test_no_reverse_inference_in_canonical_types()

    print("✓ All position semantic teeth tests passed")
    print("✓ Position abstractions derived from physical location")
    print("✓ No reverse inference (well_id → position_tag)")
    print("✓ SpatialLocation.position_class is canonical")
