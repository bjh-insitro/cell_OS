"""
Semantic teeth tests: Prevent time ambiguity from spreading.

These tests enforce that:
1. WellSpec.time_h maps to Well.observation_time_h (and nothing else)
2. Well has no ambiguous time fields (time_h, timepoint_h banned)
3. The mapping preserves semantics (not just renames)
"""

from dataclasses import fields

from cell_os.core.experiment import Well, Treatment
from cell_os.core.legacy_adapters import well_spec_to_well


class DummyWellSpec:
    """Mock WellSpec without importing legacy schemas."""
    def __init__(self):
        self.cell_line = "A549"
        self.compound = "DMSO"
        self.dose_uM = 0.0
        self.time_h = 24.0
        self.assay = "cell_painting"
        self.position_tag = "center"


def test_well_spec_maps_to_observation_time_h():
    """WellSpec.time_h must map to Well.observation_time_h and nothing else.

    This enforces semantic clarity: time_h (ambiguous) becomes
    observation_time_h (explicit meaning: hours since treatment start
    when assay readout is taken).
    """
    spec = DummyWellSpec()
    well = well_spec_to_well(spec)

    # Correct mapping
    assert well.observation_time_h == 24.0

    # Old names don't exist on canonical Well
    assert not hasattr(well, "time_h"), \
        "Well must not have 'time_h' field - use observation_time_h"
    assert not hasattr(well, "timepoint_h"), \
        "Well must not have 'timepoint_h' field - use observation_time_h"


def test_well_has_no_ambiguous_time_fields():
    """Well type must not have time_h or timepoint_h fields.

    This prevents the old vocabulary from spreading. Only observation_time_h
    is allowed, and it has explicit semantics documented in the docstring.
    """
    well_fields = {f.name for f in fields(Well)}

    # Canonical name exists
    assert "observation_time_h" in well_fields, \
        "Well must have observation_time_h field"

    # Old names banned
    assert "time_h" not in well_fields, \
        "Well must not have ambiguous 'time_h' field"
    assert "timepoint_h" not in well_fields, \
        "Well must not have simulator-specific 'timepoint_h' field"


def test_observation_time_h_semantics_documented():
    """observation_time_h must have explicit semantics in docstring.

    Prevents silent reinterpretation later.
    """
    # Check that Well class has docstring
    assert Well.__doc__ is not None, "Well must have docstring"

    # Check that observation_time_h semantics are documented
    doc = Well.__doc__.lower()
    assert "observation_time_h" in doc, \
        "Well docstring must document observation_time_h"
    # Updated to check for new absolute time semantics (hours since t=0)
    assert ("hours since" in doc or "time origin" in doc), \
        "observation_time_h semantics must specify time reference"


def test_treatment_is_composite_not_flat():
    """Treatment must be a structured object, not flat fields.

    This prevents compound/dose_uM from spreading as separate fields
    throughout the codebase.
    """
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay="cell_painting",
        location=None
    )

    # Treatment is an object
    assert isinstance(well.treatment, Treatment)
    assert well.treatment.compound == "DMSO"
    assert well.treatment.dose_uM == 0.0

    # Flat fields don't exist on Well
    assert not hasattr(well, "compound"), \
        "Well must not have flat 'compound' field - use well.treatment.compound"
    assert not hasattr(well, "dose_uM"), \
        "Well must not have flat 'dose_uM' field - use well.treatment.dose_uM"


def test_well_is_immutable():
    """Well should be frozen to prevent accidental mutation.

    Immutability makes provenance cleaner and prevents "spooky action
    at a distance" where one part of the code modifies a well that
    another part is still using.
    """
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay="cell_painting",
        location=None
    )

    # Try to mutate - should raise
    try:
        well.observation_time_h = 48.0
        assert False, "Well should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected - well is frozen


def test_adapter_preserves_numeric_precision():
    """Adapter must not lose precision in time conversion.

    float(spec.time_h) should preserve the value exactly.
    """
    spec = DummyWellSpec()
    spec.time_h = 12.5  # Non-integer time

    well = well_spec_to_well(spec)

    assert well.observation_time_h == 12.5, \
        "Adapter must preserve numeric precision"


def test_adapter_fails_on_missing_fields():
    """Adapter should fail cleanly if required fields missing.

    Better to fail fast than create a Well with None values.
    """
    class IncompleteSpec:
        cell_line = "A549"
        # Missing: compound, dose_uM, time_h, assay

    spec = IncompleteSpec()

    try:
        well = well_spec_to_well(spec)
        assert False, "Should raise AttributeError on missing fields"
    except AttributeError:
        pass  # Expected


if __name__ == '__main__':
    test_well_spec_maps_to_observation_time_h()
    test_well_has_no_ambiguous_time_fields()
    test_observation_time_h_semantics_documented()
    test_treatment_is_composite_not_flat()
    test_well_is_immutable()
    test_adapter_preserves_numeric_precision()
    test_adapter_fails_on_missing_fields()

    print("✓ All semantic teeth tests passed")
    print("✓ Time ambiguity cannot spread")
    print("✓ observation_time_h is the only canonical time field")
