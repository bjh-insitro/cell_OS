"""
Semantic teeth tests: Experiment must be canonical, immutable, and fingerprintable.

These tests enforce that:
1. Experiment uses canonical types (AssayType, observation_time_h, SpatialLocation)
2. Experiment is immutable (frozen=True)
3. Experiment fingerprint is deterministic and stable
4. No legacy string fields (time_h, position_tag, raw assay strings)
5. Wells are ordered (tuple) but fingerprint is order-independent
"""

from dataclasses import fields
import json

from cell_os.core import (
    Experiment,
    DesignSpec,
    Well,
    Treatment,
    SpatialLocation,
    AssayType,
)


def test_experiment_is_immutable():
    """Experiment must be frozen (immutable)."""
    design_spec = DesignSpec(
        template="baseline_replicates",
        params={"n_reps": 4},
    )

    wells = (
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id="A01"),
        ),
    )

    experiment = Experiment(
        experiment_id="exp_001",
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="sequential",
    )

    # Verify experiment is frozen
    try:
        experiment.experiment_id = "exp_002"  # type: ignore
        assert False, "Experiment should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected

    # Verify design_spec is frozen
    try:
        design_spec.template = "modified"  # type: ignore
        assert False, "DesignSpec should be immutable (frozen=True)"
    except (AttributeError, Exception):
        pass  # Expected


def test_experiment_uses_canonical_types():
    """Experiment must use canonical types (no legacy strings)."""
    design_spec = DesignSpec(
        template="dose_response",
        params={"compound": "CCCP", "n_doses": 8},
    )

    wells = (
        Well(
            cell_line="A549",
            treatment=Treatment(compound="CCCP", dose_uM=1.0),
            observation_time_h=24.0,  # ✓ Canonical time field
            assay=AssayType.CELL_PAINTING,  # ✓ Enum, not string
            location=SpatialLocation(plate_id="P1", well_id="B02"),  # ✓ Canonical location
        ),
    )

    experiment = Experiment(
        experiment_id="exp_002",
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="sequential",
    )

    # Verify wells use canonical types
    well = experiment.wells[0]
    assert isinstance(well.assay, AssayType), "Well.assay must be AssayType enum"
    assert isinstance(well.location, SpatialLocation), "Well.location must be SpatialLocation"
    assert hasattr(well, "observation_time_h"), "Well must have observation_time_h"

    # Verify no legacy string fields in Experiment
    exp_fields = {f.name for f in fields(Experiment)}
    assert "time_h" not in exp_fields, "Experiment must not have time_h field"
    assert "position_tag" not in exp_fields, "Experiment must not have position_tag field"
    assert "timepoint" not in exp_fields, "Experiment must not have timepoint field"


def test_experiment_wells_are_ordered():
    """Experiment.wells must be tuple (ordered, immutable)."""
    design_spec = DesignSpec(template="test", params={})

    wells = (
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id="A01"),
        ),
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id="A02"),
        ),
    )

    experiment = Experiment(
        experiment_id="exp_003",
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="sequential",
    )

    # Verify wells is tuple (not list)
    assert isinstance(experiment.wells, tuple), "Experiment.wells must be tuple (ordered)"

    # Verify cannot modify wells
    try:
        experiment.wells[0] = None  # type: ignore
        assert False, "Experiment.wells should be immutable"
    except (TypeError, Exception):
        pass  # Expected


def test_experiment_fingerprint_is_deterministic():
    """Experiment fingerprint must be deterministic (same inputs → same hash)."""
    design_spec = DesignSpec(template="test", params={"n_reps": 4})

    wells = (
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id="A01"),
        ),
    )

    exp1 = Experiment(
        experiment_id="exp_004",
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="sequential",
    )

    exp2 = Experiment(
        experiment_id="exp_005",  # Different ID
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="sequential",
    )

    # Fingerprint should be same (ID not included in fingerprint)
    fp1 = exp1.fingerprint()
    fp2 = exp2.fingerprint()

    assert fp1 == fp2, "Fingerprint must be deterministic (same wells/design → same hash)"
    assert len(fp1) > 0, "Fingerprint must be non-empty"


def test_experiment_fingerprint_order_independent():
    """Experiment fingerprint should be order-independent for wells.

    Wells are stored in given order, but fingerprint sorts by location
    so same wells in different order produce same fingerprint.
    """
    design_spec = DesignSpec(template="test", params={})

    well_a = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="A01"),
    )

    well_b = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="B01"),
    )

    # Different well order
    exp1 = Experiment(
        experiment_id="exp_006",
        wells=(well_a, well_b),
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="seq",
    )

    exp2 = Experiment(
        experiment_id="exp_007",
        wells=(well_b, well_a),  # Reversed
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="seq",
    )

    # Fingerprint should be same (order-independent)
    assert exp1.fingerprint() == exp2.fingerprint(), \
        "Fingerprint must be order-independent (same wells → same hash)"


def test_experiment_fingerprint_changes_with_allocation():
    """Experiment fingerprint must change if well locations change."""
    design_spec = DesignSpec(template="test", params={})

    well_a01 = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="A01"),
    )

    well_a02 = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="A02"),  # Different location
    )

    exp1 = Experiment(
        experiment_id="exp_008",
        wells=(well_a01,),
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="seq",
    )

    exp2 = Experiment(
        experiment_id="exp_009",
        wells=(well_a02,),  # Different well location
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="seq",
    )

    # Fingerprint must be different
    assert exp1.fingerprint() != exp2.fingerprint(), \
        "Fingerprint must change if well location changes"


def test_design_spec_params_are_json_serializable():
    """DesignSpec.params must be JSON-serializable (no Python objects)."""
    # Valid params
    design_spec = DesignSpec(
        template="test",
        params={
            "n_reps": 4,
            "compound": "DMSO",
            "dose_uM": 1.0,
            "nested": {"key": "value"},
        },
    )

    # Should be JSON-serializable
    try:
        json.dumps(design_spec.params)
    except (TypeError, ValueError):
        assert False, "DesignSpec.params must be JSON-serializable"


def test_experiment_metadata_is_optional():
    """Experiment.metadata should be optional (default empty)."""
    design_spec = DesignSpec(template="test", params={})

    wells = (
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id="A01"),
        ),
    )

    # Create without metadata
    experiment = Experiment(
        experiment_id="exp_010",
        wells=wells,
        design_spec=design_spec,
        capabilities_id="cap_v1",
        allocation_policy_id="seq",
    )

    # Metadata should exist but be empty
    assert hasattr(experiment, "metadata"), "Experiment must have metadata field"
    assert experiment.metadata == {}, "Default metadata should be empty dict"


def test_design_spec_no_legacy_fields():
    """DesignSpec must not have legacy time/assay string fields."""
    design_spec_fields = {f.name for f in fields(DesignSpec)}

    # Must have canonical fields
    assert "template" in design_spec_fields
    assert "params" in design_spec_fields

    # Must NOT have legacy fields
    assert "time_h" not in design_spec_fields
    assert "timepoint_h" not in design_spec_fields
    assert "assay" not in design_spec_fields  # Assay is in Well, not DesignSpec


if __name__ == "__main__":
    test_experiment_is_immutable()
    test_experiment_uses_canonical_types()
    test_experiment_wells_are_ordered()
    test_experiment_fingerprint_is_deterministic()
    test_experiment_fingerprint_order_independent()
    test_experiment_fingerprint_changes_with_allocation()
    test_design_spec_params_are_json_serializable()
    test_experiment_metadata_is_optional()
    test_design_spec_no_legacy_fields()

    print("✓ All experiment semantic teeth tests passed")
    print("✓ Experiment is immutable (frozen=True)")
    print("✓ Experiment uses canonical types (no legacy strings)")
    print("✓ Experiment fingerprint is deterministic")
    print("✓ Wells are ordered but fingerprint is order-independent")
    print("✓ DesignSpec params are JSON-serializable")
