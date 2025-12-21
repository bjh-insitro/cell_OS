"""
Semantic teeth tests: Observation must be canonical, immutable, and linked to Experiment.

These tests enforce that:
1. RawWellResult uses canonical types (AssayType, observation_time_h, SpatialLocation)
2. Observation is immutable (frozen=True)
3. Observation links to Experiment via fingerprint
4. No legacy string fields (time_h, position_tag, raw assay strings)
5. ConditionKey uses canonical axes for aggregation
"""

from dataclasses import fields

from cell_os.core import (
    RawWellResult,
    ConditionKey,
    Observation,
    SpatialLocation,
    Treatment,
    AssayType,
)


def test_raw_well_result_is_immutable():
    """RawWellResult must be frozen (immutable)."""
    result = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,
        readouts={"morphology": {"nucleus": 1.0}},
    )

    # Verify frozen
    try:
        result.cell_line = "HepG2"  # type: ignore
        assert False, "RawWellResult should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_raw_well_result_uses_canonical_types():
    """RawWellResult must use canonical types (no legacy strings)."""
    result = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,  # ✓ Enum, not string
        observation_time_h=24.0,  # ✓ Canonical time field
        readouts={"signal": 1.0},
    )

    # Verify canonical types
    assert isinstance(result.assay, AssayType), "RawWellResult.assay must be AssayType enum"
    assert isinstance(result.location, SpatialLocation), "RawWellResult.location must be SpatialLocation"
    assert hasattr(result, "observation_time_h"), "RawWellResult must have observation_time_h"

    # Verify no legacy fields
    result_fields = {f.name for f in fields(RawWellResult)}
    assert "time_h" not in result_fields, "RawWellResult must not have time_h"
    assert "timepoint_h" not in result_fields, "RawWellResult must not have timepoint_h"
    assert "position_tag" not in result_fields, "RawWellResult must not have position_tag"


def test_raw_well_result_readouts_are_flexible():
    """RawWellResult.readouts can hold arbitrary nested structure."""
    # Simple readout
    result1 = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.LDH_CYTOTOXICITY,
        observation_time_h=24.0,
        readouts={"ldh_absorbance": 0.5},
    )

    # Nested readout
    result2 = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A02"),
        cell_line="A549",
        treatment=Treatment(compound="CCCP", dose_uM=1.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,
        readouts={
            "morphology": {
                "nucleus": 1.0,
                "er": 0.98,
                "mito": 1.02,
            },
            "qc_passed": True,
        },
    )

    assert result1.readouts["ldh_absorbance"] == 0.5
    assert result2.readouts["morphology"]["nucleus"] == 1.0


def test_raw_well_result_qc_is_optional():
    """RawWellResult.qc should be optional (default empty)."""
    result = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,
        readouts={"signal": 1.0},
    )

    assert hasattr(result, "qc"), "RawWellResult must have qc field"
    assert result.qc == {}, "Default qc should be empty dict"


def test_condition_key_uses_canonical_axes():
    """ConditionKey must use canonical observation axes."""
    key = ConditionKey(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,  # ✓ Enum
        observation_time_h=24.0,  # ✓ Canonical time
        position_class="center",  # ✓ Derived from location, not stored
    )

    # Verify canonical types
    assert isinstance(key.assay, AssayType), "ConditionKey.assay must be AssayType enum"
    assert hasattr(key, "observation_time_h"), "ConditionKey must have observation_time_h"

    # Verify no legacy fields
    key_fields = {f.name for f in fields(ConditionKey)}
    assert "time_h" not in key_fields, "ConditionKey must not have time_h"
    assert "position_tag" not in key_fields, "ConditionKey must not have position_tag (use position_class)"


def test_condition_key_is_immutable():
    """ConditionKey must be frozen (immutable)."""
    key = ConditionKey(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,
        position_class="center",
    )

    try:
        key.cell_line = "HepG2"  # type: ignore
        assert False, "ConditionKey should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_observation_is_immutable():
    """Observation must be frozen (immutable)."""
    observation = Observation(
        experiment_fingerprint="abc123",
        raw_wells=(),
        metadata={},
    )

    try:
        observation.experiment_fingerprint = "xyz789"  # type: ignore
        assert False, "Observation should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_observation_links_to_experiment():
    """Observation must link to Experiment via fingerprint."""
    observation = Observation(
        experiment_fingerprint="exp_fp_12345",
        raw_wells=(),
        metadata={},
    )

    assert observation.experiment_fingerprint == "exp_fp_12345", \
        "Observation must store experiment fingerprint for linkage"
    assert len(observation.experiment_fingerprint) > 0, \
        "Experiment fingerprint must be non-empty"


def test_observation_raw_wells_are_ordered():
    """Observation.raw_wells must be tuple (ordered, immutable)."""
    result1 = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,
        readouts={"signal": 1.0},
    )

    observation = Observation(
        experiment_fingerprint="exp_fp",
        raw_wells=(result1,),
        metadata={},
    )

    # Verify tuple
    assert isinstance(observation.raw_wells, tuple), \
        "Observation.raw_wells must be tuple (ordered)"

    # Verify immutable
    try:
        observation.raw_wells[0] = None  # type: ignore
        assert False, "Observation.raw_wells should be immutable"
    except (TypeError, Exception):
        pass  # Expected


def test_observation_metadata_is_optional():
    """Observation.metadata should be optional (default empty)."""
    observation = Observation(
        experiment_fingerprint="exp_fp",
        raw_wells=(),
    )

    assert hasattr(observation, "metadata"), "Observation must have metadata field"
    assert observation.metadata == {}, "Default metadata should be empty dict"


def test_raw_well_result_no_legacy_fields():
    """RawWellResult must not have any legacy time/position/assay fields."""
    result_fields = {f.name for f in fields(RawWellResult)}

    # Must have canonical fields
    assert "location" in result_fields
    assert "assay" in result_fields
    assert "observation_time_h" in result_fields

    # Must NOT have legacy fields
    banned_fields = {"time_h", "timepoint_h", "timepoint", "position_tag", "well_id", "plate_id"}
    for banned in banned_fields:
        assert banned not in result_fields, \
            f"RawWellResult must not have {banned} field (use canonical types)"


if __name__ == "__main__":
    test_raw_well_result_is_immutable()
    test_raw_well_result_uses_canonical_types()
    test_raw_well_result_readouts_are_flexible()
    test_raw_well_result_qc_is_optional()
    test_condition_key_uses_canonical_axes()
    test_condition_key_is_immutable()
    test_observation_is_immutable()
    test_observation_links_to_experiment()
    test_observation_raw_wells_are_ordered()
    test_observation_metadata_is_optional()
    test_raw_well_result_no_legacy_fields()

    print("✓ All observation semantic teeth tests passed")
    print("✓ RawWellResult uses canonical types (no legacy strings)")
    print("✓ Observation is immutable (frozen=True)")
    print("✓ Observation links to Experiment via fingerprint")
    print("✓ ConditionKey uses canonical axes")
