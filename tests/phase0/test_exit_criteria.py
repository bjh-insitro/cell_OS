"""
Phase 0 Exit Criteria Tests

These are enforcement tests, not coverage tests.
If these pass with arbitrary thresholds but fail with calibrated ones,
Phase 0 is not done.
"""

try:
    import pytest
except ImportError:
    pytest = None

from cell_os.phase0.exit_criteria import (
    RunSummary,
    SentinelObs,
    EdgeObs,
    PositiveControlObs,
    assert_sentinel_drift_below,
    assert_measurement_cv_below,
    assert_plate_edge_effect_detectable_or_absent,
    assert_effect_recovery_for_known_controls,
    assert_phase0_exit,
)
from cell_os.phase0.exceptions import Phase0GateFailure


def _make_good_run():
    # Sentinel plate means: very stable
    sentinels = []
    for plate_id, mean in [("P1", 100.0), ("P2", 101.0), ("P3", 99.5)]:
        for i in range(12):
            sentinels.append(SentinelObs(plate_id=plate_id, well_pos=f"A{i+1:02d}", metric_name="LDH", value=mean))

    # Measurement replicates: low CV
    measurement_reps = {
        "LDH": [100.0, 101.0, 99.5, 100.5, 100.2],
    }

    # Edge effects: small delta
    edge_effects = []
    for plate_id in ["P1", "P2"]:
        for i in range(12):
            edge_effects.append(EdgeObs(plate_id=plate_id, well_pos=f"A{i+1:02d}", metric_name="LDH", region="edge", value=100.5))
            edge_effects.append(EdgeObs(plate_id=plate_id, well_pos=f"B{i+1:02d}", metric_name="LDH", region="center", value=100.0))

    # Positive control: clear effect
    pos = [
        PositiveControlObs(metric_name="LDH", control_name="CCCP_mid", baseline_name="vehicle", control_value=140.0, baseline_value=100.0)
    ]

    return RunSummary(
        sentinels=sentinels,
        edge_effects=edge_effects,
        positive_controls=pos,
        measurement_replicates=measurement_reps,
    )


def test_sentinel_drift_passes():
    run = _make_good_run()
    assert_sentinel_drift_below(0.02, run)  # 2% CV threshold


def test_sentinel_drift_fails_when_plate_means_shift():
    run = _make_good_run()
    # introduce drift
    bad = list(run.sentinels)
    for idx, s in enumerate(bad):
        if s.plate_id == "P3":
            bad[idx] = SentinelObs(plate_id=s.plate_id, well_pos=s.well_pos, metric_name=s.metric_name, value=120.0)
    run2 = RunSummary(
        sentinels=bad,
        edge_effects=run.edge_effects,
        positive_controls=run.positive_controls,
        measurement_replicates=run.measurement_replicates,
    )
    if pytest:
        with pytest.raises(Phase0GateFailure) as exc:
            assert_sentinel_drift_below(0.02, run2)
        assert exc.value.criterion == "sentinel_stability"
    else:
        try:
            assert_sentinel_drift_below(0.02, run2)
            raise AssertionError("Should have failed")
        except Phase0GateFailure as e:
            assert e.criterion == "sentinel_stability"


def test_measurement_cv_passes():
    run = _make_good_run()
    assert_measurement_cv_below(0.03, run)  # 3% CV threshold


def test_measurement_cv_fails_when_noise_high():
    run = _make_good_run()
    run2 = RunSummary(
        sentinels=run.sentinels,
        edge_effects=run.edge_effects,
        positive_controls=run.positive_controls,
        measurement_replicates={"LDH": [100, 130, 70, 140, 60]},
    )
    if pytest:
        with pytest.raises(Phase0GateFailure) as exc:
            assert_measurement_cv_below(0.03, run2)
        assert exc.value.criterion == "measurement_precision"
    else:
        try:
            assert_measurement_cv_below(0.03, run2)
            raise AssertionError("Should have failed")
        except Phase0GateFailure as e:
            assert e.criterion == "measurement_precision"


def test_edge_effect_passes():
    run = _make_good_run()
    assert_plate_edge_effect_detectable_or_absent(run, max_abs_edge_center_delta=2.0)


def test_edge_effect_fails_when_delta_large():
    run = _make_good_run()
    bad = []
    for o in run.edge_effects:
        if o.region == "edge":
            bad.append(EdgeObs(o.plate_id, o.well_pos, o.metric_name, o.region, o.value + 10.0))
        else:
            bad.append(o)
    run2 = RunSummary(
        sentinels=run.sentinels,
        edge_effects=bad,
        positive_controls=run.positive_controls,
        measurement_replicates=run.measurement_replicates,
    )
    if pytest:
        with pytest.raises(Phase0GateFailure) as exc:
            assert_plate_edge_effect_detectable_or_absent(run2, max_abs_edge_center_delta=2.0)
        assert exc.value.criterion == "plate_edge_effects"
    else:
        try:
            assert_plate_edge_effect_detectable_or_absent(run2, max_abs_edge_center_delta=2.0)
            raise AssertionError("Should have failed")
        except Phase0GateFailure as e:
            assert e.criterion == "plate_edge_effects"


def test_positive_control_passes():
    run = _make_good_run()
    assert_effect_recovery_for_known_controls(run, min_abs_effect=20.0)


def test_positive_control_fails_when_effect_small():
    run = _make_good_run()
    run2 = RunSummary(
        sentinels=run.sentinels,
        edge_effects=run.edge_effects,
        positive_controls=[
            PositiveControlObs(metric_name="LDH", control_name="CCCP_mid", baseline_name="vehicle", control_value=108.0, baseline_value=100.0)
        ],
        measurement_replicates=run.measurement_replicates,
    )
    if pytest:
        with pytest.raises(Phase0GateFailure) as exc:
            assert_effect_recovery_for_known_controls(run2, min_abs_effect=20.0)
        assert exc.value.criterion == "positive_controls"
    else:
        try:
            assert_effect_recovery_for_known_controls(run2, min_abs_effect=20.0)
            raise AssertionError("Should have failed")
        except Phase0GateFailure as e:
            assert e.criterion == "positive_controls"


def test_assert_phase0_exit_runs_all():
    run = _make_good_run()
    assert_phase0_exit(
        run,
        sentinel_drift_cv=0.02,
        measurement_cv=0.03,
        max_edge_center_delta=2.0,
        min_positive_effect=20.0,
    )


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        print("Running Phase 0 exit criteria tests manually (pytest not available)...\n")

        tests = [
            ("test_sentinel_drift_passes", test_sentinel_drift_passes),
            ("test_sentinel_drift_fails_when_plate_means_shift", test_sentinel_drift_fails_when_plate_means_shift),
            ("test_measurement_cv_passes", test_measurement_cv_passes),
            ("test_measurement_cv_fails_when_noise_high", test_measurement_cv_fails_when_noise_high),
            ("test_edge_effect_passes", test_edge_effect_passes),
            ("test_edge_effect_fails_when_delta_large", test_edge_effect_fails_when_delta_large),
            ("test_positive_control_passes", test_positive_control_passes),
            ("test_positive_control_fails_when_effect_small", test_positive_control_fails_when_effect_small),
            ("test_assert_phase0_exit_runs_all", test_assert_phase0_exit_runs_all),
        ]

        passed = 0
        failed = 0

        for name, func in tests:
            try:
                func()
                print(f"✓ {name} PASSED")
                passed += 1
            except Exception as e:
                print(f"✗ {name} FAILED: {e}")
                failed += 1

        print(f"\n{passed} passed, {failed} failed")
