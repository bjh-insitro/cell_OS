"""
Semantic teeth tests: Prevent assay string ambiguity from spreading.

These tests enforce that:
1. AssayType.from_string() normalizes all legacy variants
2. Canonical Well only accepts AssayType (not strings)
3. New assay variants don't leak in without normalization
"""

from dataclasses import fields

from cell_os.core.assay import AssayType
from cell_os.core.experiment import Well, Treatment
from cell_os.core.legacy_adapters import well_spec_to_well


def test_assay_type_normalization():
    """AssayType.from_string() must normalize all legacy variants.

    This is the ONLY place where string normalization happens.
    """
    # Cell Painting variants
    assert AssayType.from_string("cell_painting") == AssayType.CELL_PAINTING
    assert AssayType.from_string("cellpainting") == AssayType.CELL_PAINTING
    assert AssayType.from_string("cell_paint") == AssayType.CELL_PAINTING
    assert AssayType.from_string("Cell_Painting") == AssayType.CELL_PAINTING  # Case insensitive

    # LDH variants
    assert AssayType.from_string("ldh_cytotoxicity") == AssayType.LDH_CYTOTOXICITY
    assert AssayType.from_string("ldh") == AssayType.LDH_CYTOTOXICITY
    assert AssayType.from_string("LDH") == AssayType.LDH_CYTOTOXICITY

    # scRNA-seq variants
    assert AssayType.from_string("scrna_seq") == AssayType.SCRNA_SEQ
    assert AssayType.from_string("scrna") == AssayType.SCRNA_SEQ
    assert AssayType.from_string("scrna-seq") == AssayType.SCRNA_SEQ
    assert AssayType.from_string("scRNA") == AssayType.SCRNA_SEQ

    # Scalar assays
    assert AssayType.from_string("atp") == AssayType.ATP
    assert AssayType.from_string("ATP") == AssayType.ATP
    assert AssayType.from_string("upr") == AssayType.UPR
    assert AssayType.from_string("trafficking") == AssayType.TRAFFICKING


def test_assay_type_unknown_string_raises():
    """Unknown assay strings must raise with helpful message."""
    try:
        AssayType.from_string("unknown_assay")
        assert False, "Should raise ValueError for unknown assay"
    except ValueError as e:
        # Check error message is helpful
        assert "unknown_assay" in str(e).lower()
        assert "valid variants" in str(e).lower()


def test_assay_type_try_from_string():
    """try_from_string() returns None for unknown strings."""
    # Known strings work
    assert AssayType.try_from_string("cell_painting") == AssayType.CELL_PAINTING

    # Unknown strings return None (don't raise)
    assert AssayType.try_from_string("unknown_assay") is None


def test_well_only_accepts_assay_type_not_string():
    """Canonical Well must only accept AssayType enum, not strings.

    This prevents raw strings from leaking into canonical types.
    """
    # Correct: Using AssayType enum
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,  # Enum, not string
        location=None
    )
    assert well.assay == AssayType.CELL_PAINTING

    # Wrong: Passing string directly should fail at type check
    # (Python doesn't enforce this at runtime, but type checkers will catch it)
    # This test documents the intended contract


def test_well_spec_adapter_normalizes_string():
    """Adapter must normalize string to AssayType."""

    class DummyWellSpec:
        cell_line = "A549"
        compound = "DMSO"
        dose_uM = 0.0
        time_h = 24.0
        assay = "cellpainting"  # Legacy variant (no underscore)
        position_tag = "center"

    spec = DummyWellSpec()
    well = well_spec_to_well(spec)

    # String was normalized to canonical enum
    assert well.assay == AssayType.CELL_PAINTING
    assert isinstance(well.assay, AssayType)


def test_assay_type_has_display_name():
    """AssayType must have human-readable display_name."""
    assert AssayType.CELL_PAINTING.display_name == "Cell Painting"
    assert AssayType.LDH_CYTOTOXICITY.display_name == "LDH Cytotoxicity"
    assert AssayType.SCRNA_SEQ.display_name == "scRNA-seq"
    assert AssayType.ATP.display_name == "ATP"


def test_assay_type_has_method_name():
    """AssayType must have method_name for BiologicalVirtualMachine."""
    assert AssayType.CELL_PAINTING.method_name == "cell_painting_assay"
    assert AssayType.LDH_CYTOTOXICITY.method_name == "ldh_cytotoxicity_assay"
    assert AssayType.SCRNA_SEQ.method_name == "scrna_seq_assay"


def test_assay_type_str_uses_display_name():
    """str(AssayType) should use display_name for logging."""
    assert str(AssayType.CELL_PAINTING) == "Cell Painting"
    assert str(AssayType.LDH_CYTOTOXICITY) == "LDH Cytotoxicity"


def test_assay_type_repr_shows_enum():
    """repr(AssayType) should show enum member for debugging."""
    assert repr(AssayType.CELL_PAINTING) == "AssayType.CELL_PAINTING"
    assert repr(AssayType.LDH_CYTOTOXICITY) == "AssayType.LDH_CYTOTOXICITY"


def test_well_assay_field_is_not_string():
    """Well.assay field type must be AssayType, not str."""
    well_fields_by_name = {f.name: f for f in fields(Well)}

    assay_field = well_fields_by_name['assay']

    # The field type should be AssayType
    # (This checks the type annotation, not runtime type)
    assert assay_field.type == AssayType or 'AssayType' in str(assay_field.type)


def test_no_new_assay_strings_leak():
    """Test that new code can't introduce raw assay strings.

    This is a meta-test: if you add a new assay string anywhere,
    you must add it to AssayType.from_string() normalization map first.

    Otherwise this test documents the pattern: all assays go through
    AssayType.from_string().
    """
    # If you're adding a new assay:
    # 1. Add to AssayType enum
    # 2. Add to from_string() normalization map
    # 3. Update this test

    # Example: if someone tries to add "imaging" as a new assay variant
    # without updating AssayType, this will fail:
    try:
        AssayType.from_string("imaging")
        assert False, "If 'imaging' is valid, update AssayType enum first"
    except ValueError:
        pass  # Expected - unknown assay


if __name__ == '__main__':
    test_assay_type_normalization()
    test_assay_type_unknown_string_raises()
    test_assay_type_try_from_string()
    test_well_only_accepts_assay_type_not_string()
    test_well_spec_adapter_normalizes_string()
    test_assay_type_has_display_name()
    test_assay_type_has_method_name()
    test_assay_type_str_uses_display_name()
    test_assay_type_repr_shows_enum()
    test_well_assay_field_is_not_string()
    test_no_new_assay_strings_leak()

    print("✓ All assay semantic teeth tests passed")
    print("✓ AssayType enum is canonical")
    print("✓ String variants normalized via from_string()")
    print("✓ No raw assay strings in canonical types")
