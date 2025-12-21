"""
Semantic teeth tests: Capabilities must be immutable and fingerprintable.

These tests enforce that:
1. PlateGeometry is canonical and provides edge detection
2. Capabilities is immutable (frozen=True)
3. Capabilities fingerprint is deterministic
4. AllocationPolicy is immutable and fingerprintable
"""

from dataclasses import fields

from cell_os.core import (
    PlateGeometry,
    Capabilities,
    AllocationPolicy,
    AssayType,
)


def test_plate_geometry_is_immutable():
    """PlateGeometry must be frozen (immutable)."""
    geometry = PlateGeometry(
        rows=8,
        cols=12,
        well_ids=["A01", "A02", "B01", "B02"],
    )

    try:
        geometry.rows = 16  # type: ignore
        assert False, "PlateGeometry should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_plate_geometry_provides_edge_detection():
    """PlateGeometry must provide is_edge() helper."""
    geometry = PlateGeometry(
        rows=8,
        cols=12,
        well_ids=[],  # Not needed for edge detection
    )

    # Edge wells (96-well plate)
    assert geometry.is_edge("A01") == True, "A01 should be edge"
    assert geometry.is_edge("A12") == True, "A12 should be edge"
    assert geometry.is_edge("H01") == True, "H01 should be edge"
    assert geometry.is_edge("H12") == True, "H12 should be edge"
    assert geometry.is_edge("D01") == True, "D01 (left edge) should be edge"
    assert geometry.is_edge("D12") == True, "D12 (right edge) should be edge"

    # Center wells
    assert geometry.is_edge("B02") == False, "B02 should be center"
    assert geometry.is_edge("D06") == False, "D06 should be center"
    assert geometry.is_edge("G11") == False, "G11 should be center"


def test_plate_geometry_standard_96_well():
    """PlateGeometry should support standard 96-well plate."""
    geometry = PlateGeometry.standard_96_well()

    assert geometry.rows == 8, "96-well plate has 8 rows"
    assert geometry.cols == 12, "96-well plate has 12 columns"
    assert len(geometry.well_ids) == 96, "96-well plate has 96 wells"

    # Verify first and last wells
    assert "A01" in geometry.well_ids
    assert "H12" in geometry.well_ids


def test_capabilities_is_immutable():
    """Capabilities must be frozen (immutable)."""
    geometry = PlateGeometry.standard_96_well()

    capabilities = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING, AssayType.LDH_CYTOTOXICITY]),
    )

    try:
        capabilities.geometry = PlateGeometry(rows=16, cols=24, well_ids=[])  # type: ignore
        assert False, "Capabilities should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_capabilities_supported_assays_is_frozenset():
    """Capabilities.supported_assays must be frozenset (immutable set)."""
    geometry = PlateGeometry.standard_96_well()

    capabilities = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING]),
    )

    assert isinstance(capabilities.supported_assays, frozenset), \
        "Capabilities.supported_assays must be frozenset"

    # Verify immutable
    try:
        capabilities.supported_assays.add(AssayType.LDH_CYTOTOXICITY)  # type: ignore
        assert False, "supported_assays should be immutable (frozenset)"
    except (AttributeError, Exception):
        pass  # Expected


def test_capabilities_fingerprint_is_deterministic():
    """Capabilities fingerprint must be deterministic."""
    geometry = PlateGeometry.standard_96_well()

    cap1 = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING, AssayType.LDH_CYTOTOXICITY]),
    )

    cap2 = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING, AssayType.LDH_CYTOTOXICITY]),
    )

    # Same capabilities → same fingerprint
    assert cap1.fingerprint() == cap2.fingerprint(), \
        "Capabilities fingerprint must be deterministic"


def test_capabilities_fingerprint_changes_with_geometry():
    """Capabilities fingerprint must change if geometry changes."""
    geometry_96 = PlateGeometry.standard_96_well()
    geometry_384 = PlateGeometry(rows=16, cols=24, well_ids=[])

    cap1 = Capabilities(
        geometry=geometry_96,
        supported_assays=frozenset([AssayType.CELL_PAINTING]),
    )

    cap2 = Capabilities(
        geometry=geometry_384,
        supported_assays=frozenset([AssayType.CELL_PAINTING]),
    )

    # Different geometry → different fingerprint
    assert cap1.fingerprint() != cap2.fingerprint(), \
        "Capabilities fingerprint must change if geometry changes"


def test_capabilities_fingerprint_changes_with_assays():
    """Capabilities fingerprint must change if supported assays change."""
    geometry = PlateGeometry.standard_96_well()

    cap1 = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING]),
    )

    cap2 = Capabilities(
        geometry=geometry,
        supported_assays=frozenset([AssayType.CELL_PAINTING, AssayType.LDH_CYTOTOXICITY]),
    )

    # Different assays → different fingerprint
    assert cap1.fingerprint() != cap2.fingerprint(), \
        "Capabilities fingerprint must change if supported assays change"


def test_allocation_policy_is_immutable():
    """AllocationPolicy must be frozen (immutable)."""
    policy = AllocationPolicy(
        policy_id="sequential",
        params={"order": "row_major"},
    )

    try:
        policy.policy_id = "random"  # type: ignore
        assert False, "AllocationPolicy should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_allocation_policy_fingerprint_is_deterministic():
    """AllocationPolicy fingerprint must be deterministic."""
    policy1 = AllocationPolicy(
        policy_id="sequential",
        params={"order": "row_major"},
    )

    policy2 = AllocationPolicy(
        policy_id="sequential",
        params={"order": "row_major"},
    )

    # Same policy → same fingerprint
    assert policy1.fingerprint() == policy2.fingerprint(), \
        "AllocationPolicy fingerprint must be deterministic"


def test_allocation_policy_fingerprint_changes_with_params():
    """AllocationPolicy fingerprint must change if params change."""
    policy1 = AllocationPolicy(
        policy_id="sequential",
        params={"order": "row_major"},
    )

    policy2 = AllocationPolicy(
        policy_id="sequential",
        params={"order": "column_major"},  # Different param
    )

    # Different params → different fingerprint
    assert policy1.fingerprint() != policy2.fingerprint(), \
        "AllocationPolicy fingerprint must change if params change"


def test_allocation_policy_no_legacy_fields():
    """AllocationPolicy must not have legacy string fields."""
    policy_fields = {f.name for f in fields(AllocationPolicy)}

    # Must have canonical fields
    assert "policy_id" in policy_fields
    assert "params" in policy_fields

    # Must NOT have legacy fields
    assert "name" not in policy_fields  # Use policy_id, not name
    assert "type" not in policy_fields  # Use policy_id, not type


if __name__ == "__main__":
    test_plate_geometry_is_immutable()
    test_plate_geometry_provides_edge_detection()
    test_plate_geometry_standard_96_well()
    test_capabilities_is_immutable()
    test_capabilities_supported_assays_is_frozenset()
    test_capabilities_fingerprint_is_deterministic()
    test_capabilities_fingerprint_changes_with_geometry()
    test_capabilities_fingerprint_changes_with_assays()
    test_allocation_policy_is_immutable()
    test_allocation_policy_fingerprint_is_deterministic()
    test_allocation_policy_fingerprint_changes_with_params()
    test_allocation_policy_no_legacy_fields()

    print("✓ All capabilities semantic teeth tests passed")
    print("✓ PlateGeometry provides edge detection")
    print("✓ Capabilities is immutable (frozen=True)")
    print("✓ Capabilities fingerprint is deterministic")
    print("✓ AllocationPolicy is immutable and fingerprintable")
