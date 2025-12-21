"""
End-to-end test: Valid temporal configurations work correctly.

This test proves that the temporal causality enforcement doesn't break
normal, valid use cases.
"""

import sys
from cell_os.core.experiment import Well, Treatment, SpatialLocation, Experiment, DesignSpec
from cell_os.core.observation import RawWellResult, Observation
from cell_os.core.assay import AssayType


def test_normal_24h_experiment():
    """Most common case: treatment at t=0, observation at t=24h."""
    print("Test: Normal 24h experiment (treatment at t=0, observe at t=24h)")

    # Create well
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="staurosporine", dose_uM=0.1),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=0.0,  # Treatment at experiment start
        location=SpatialLocation(plate_id="P1", well_id="A01"),
    )

    print(f"  Well created: {well.treatment.compound} @ {well.treatment.dose_uM} µM")
    print(f"  Treatment start: {well.treatment_start_time_h} h")
    print(f"  Observation: {well.observation_time_h} h")
    assert well.observation_time_h == 24.0
    assert well.treatment_start_time_h == 0.0
    print("  ✓ Well creation succeeded\n")

    # Create experiment with this well
    experiment = Experiment(
        experiment_id="exp-001",
        wells=(well,),
        design_spec=DesignSpec(template="test", params={}),
        capabilities_id="cap-1",
        allocation_policy_id="alloc-1",
    )

    print(f"  Experiment created: {experiment.experiment_id}")
    print(f"  Number of wells: {len(experiment.wells)}")
    print("  ✓ Experiment creation succeeded\n")

    # Create observation result
    result = RawWellResult(
        location=well.location,
        cell_line=well.cell_line,
        treatment=well.treatment,
        assay=well.assay,
        observation_time_h=24.0,
        readouts={"viability": 0.85, "cell_count": 15000},
    )

    print(f"  RawWellResult created")
    print(f"  Observation time: {result.observation_time_h} h")
    print(f"  Readouts: viability={result.readouts['viability']:.2f}")
    print("  ✓ RawWellResult creation succeeded\n")

    # Create full observation
    observation = Observation(
        experiment_fingerprint=experiment.fingerprint(),
        raw_wells=(result,),
    )

    print(f"  Observation created")
    print(f"  Linked to experiment: {observation.experiment_fingerprint[:8]}...")
    print("  ✓ Observation creation succeeded\n")

    print("✓ PASS: Normal 24h experiment works correctly")
    return True


def test_delayed_treatment_experiment():
    """Treatment added at t=24h, observation at t=48h."""
    print("Test: Delayed treatment (treatment at t=24h, observe at t=48h)")

    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="tunicamycin", dose_uM=1.0),
        observation_time_h=48.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=24.0,  # Treatment added at t=24h
        location=SpatialLocation(plate_id="P1", well_id="B02"),
    )

    print(f"  Treatment start: {well.treatment_start_time_h} h")
    print(f"  Observation: {well.observation_time_h} h")
    print(f"  Duration: {well.observation_time_h - well.treatment_start_time_h} h")
    assert well.observation_time_h == 48.0
    assert well.treatment_start_time_h == 24.0
    print("  ✓ Well creation succeeded\n")

    print("✓ PASS: Delayed treatment experiment works correctly")
    return True


def test_immediate_observation():
    """Observation at treatment time (boundary case)."""
    print("Test: Immediate observation (treatment and observation both at t=0)")

    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=0.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=0.0,
        location=SpatialLocation(plate_id="P1", well_id="C03"),
    )

    print(f"  Treatment start: {well.treatment_start_time_h} h")
    print(f"  Observation: {well.observation_time_h} h")
    assert well.observation_time_h == 0.0
    assert well.treatment_start_time_h == 0.0
    print("  ✓ Well creation succeeded\n")

    print("✓ PASS: Immediate observation works correctly")
    return True


def test_multi_well_experiment():
    """Experiment with multiple wells at different timepoints."""
    print("Test: Multi-well experiment with different observation times")

    wells = [
        Well(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=24.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id=f"A{i:02d}"),
        )
        for i in range(1, 4)
    ] + [
        Well(
            cell_line="A549",
            treatment=Treatment(compound="staurosporine", dose_uM=0.1),
            observation_time_h=48.0,
            assay=AssayType.CELL_PAINTING,
            location=SpatialLocation(plate_id="P1", well_id=f"B{i:02d}"),
        )
        for i in range(1, 4)
    ]

    print(f"  Created {len(wells)} wells")
    print(f"  3 wells at t=24h, 3 wells at t=48h")

    experiment = Experiment(
        experiment_id="exp-multi",
        wells=tuple(wells),
        design_spec=DesignSpec(template="multi_timepoint", params={}),
        capabilities_id="cap-1",
        allocation_policy_id="alloc-1",
    )

    print(f"  Experiment created with {len(experiment.wells)} wells")
    print("  ✓ Multi-well experiment creation succeeded\n")

    print("✓ PASS: Multi-well experiment works correctly")
    return True


def test_default_treatment_start_time():
    """Test that treatment_start_time_h defaults to 0.0."""
    print("Test: Default treatment_start_time_h (should be 0.0)")

    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        location=SpatialLocation(plate_id="P1", well_id="D01"),
        # Note: treatment_start_time_h not specified
    )

    print(f"  Well created without explicit treatment_start_time_h")
    print(f"  Actual value: {well.treatment_start_time_h} h")
    assert well.treatment_start_time_h == 0.0
    print("  ✓ Default treatment_start_time_h is 0.0\n")

    print("✓ PASS: Default treatment start time works correctly")
    return True


def run_all_tests():
    """Run all end-to-end tests."""
    tests = [
        ("Normal 24h experiment", test_normal_24h_experiment),
        ("Delayed treatment experiment", test_delayed_treatment_experiment),
        ("Immediate observation", test_immediate_observation),
        ("Multi-well experiment", test_multi_well_experiment),
        ("Default treatment start time", test_default_treatment_start_time),
    ]

    print("=" * 80)
    print("End-to-End Temporal Causality Tests")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                print(f"✗ FAIL: {name} returned False\n")
                failed += 1
        except Exception as e:
            print(f"✗ ERROR in {name}: {type(e).__name__}: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
