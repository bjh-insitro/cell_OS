"""
Contract tests for Phase 2C.1: Identifiability Suite - Ablation Tests

Tests that Phase 1 and Phase 2A variance sources are independent and identifiable.

Ablation tests:
1. Phase 2A OFF → near-zero events in Plate C
2. Phase 1 OFF → ICC collapses in Plate A
3. Coupling smoke test → commitment params stable across Phase 1 CV settings
"""

import pytest
import tempfile
import pandas as pd
import copy
from pathlib import Path

pytest.skip("Identifiability suite tests are compute-intensive - skipping", allow_module_level=True)


def test_ablation_phase2a_off():
    """
    Test that with Phase 2A disabled, commitment events are near-zero.

    Acceptance criteria:
    - Event fraction in Plate C ≤ 0.02 (2% false positives)
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner

    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    design = IdentifiabilityDesign(str(config_path))

    # Disable Phase 2A
    design.truth['phase2a_er']['enabled'] = False

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = IdentifiabilityRunner(design, Path(tmpdir), run_id="test_ablation_phase2a_off")
        artifacts = runner.run()

        events_df = pd.read_csv(artifacts['events'])

        # Check Plate C events
        events_c = events_df[events_df['regime'] == 'high_stress_event_rich']
        n_wells_c = len(events_c)
        n_events_c = events_c['committed'].sum()
        event_fraction_c = n_events_c / n_wells_c if n_wells_c > 0 else 0.0

        print(f"\nAblation: Phase 2A OFF (Plate C)")
        print(f"  Events: {n_events_c}/{n_wells_c} wells")
        print(f"  Event fraction: {event_fraction_c:.4f}")

        # Assert acceptance criteria
        max_false_positive_rate = 0.02
        assert event_fraction_c <= max_false_positive_rate, \
            f"Event fraction {event_fraction_c:.4f} exceeds false positive threshold {max_false_positive_rate}"

        print(f"✅ Event fraction within false positive threshold (<= {max_false_positive_rate})")


def test_ablation_phase1_off():
    """
    Test that with Phase 1 disabled, ICC collapses in Plate A.

    Acceptance criteria:
    - ICC(Phase1 OFF) < 0.3 * ICC(Phase1 ON)
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
    from cell_os.calibration.identifiability_inference import fit_re_icc

    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    # Run with Phase 1 ON
    design_on = IdentifiabilityDesign(str(config_path))
    with tempfile.TemporaryDirectory() as tmpdir:
        runner_on = IdentifiabilityRunner(design_on, Path(tmpdir), run_id="test_phase1_on")
        artifacts_on = runner_on.run()
        observations_on = pd.read_csv(artifacts_on['observations'])
        icc_on = fit_re_icc(observations_on, metric="cell_count", regime="low_stress_re_only")

    # Run with Phase 1 OFF
    design_off = IdentifiabilityDesign(str(config_path))
    design_off.truth['phase1']['enabled'] = False
    design_off.truth['phase1']['growth_cv'] = 0.0
    design_off.truth['phase1']['stress_sensitivity_cv'] = 0.0
    design_off.truth['phase1']['hazard_scale_cv'] = 0.0

    with tempfile.TemporaryDirectory() as tmpdir:
        runner_off = IdentifiabilityRunner(design_off, Path(tmpdir), run_id="test_phase1_off")
        artifacts_off = runner_off.run()
        observations_off = pd.read_csv(artifacts_off['observations'])
        icc_off = fit_re_icc(observations_off, metric="cell_count", regime="low_stress_re_only")

    print(f"\nAblation: Phase 1 OFF (Plate A)")
    print(f"  ICC (Phase 1 ON): {icc_on['icc']:.4f}")
    print(f"  ICC (Phase 1 OFF): {icc_off['icc']:.4f}")
    print(f"  Ratio: {icc_off['icc'] / icc_on['icc'] if icc_on['icc'] > 0 else 0:.2f}")

    # Assert acceptance criteria
    collapse_ratio_threshold = 0.3
    ratio = icc_off['icc'] / icc_on['icc'] if icc_on['icc'] > 0 else 0.0
    assert ratio < collapse_ratio_threshold, \
        f"ICC collapse ratio {ratio:.2f} exceeds threshold {collapse_ratio_threshold} (REs still visible when disabled)"

    print(f"✅ ICC collapses when Phase 1 disabled (ratio < {collapse_ratio_threshold})")


def test_coupling_smoke():
    """
    Smoke test for accidental coupling between Phase 1 and Phase 2A.

    Run with two different Phase 1 CV settings and check that recovered
    commitment params don't drift wildly.

    This is not a perfect test but catches obvious coupling where REs
    drive commitment timing through stress dynamics.
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
    from cell_os.calibration.identifiability_inference import fit_commitment_params

    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    # Run with CV = 0.10 (default)
    design_cv010 = IdentifiabilityDesign(str(config_path))
    with tempfile.TemporaryDirectory() as tmpdir:
        runner_cv010 = IdentifiabilityRunner(design_cv010, Path(tmpdir), run_id="test_coupling_cv010")
        artifacts_cv010 = runner_cv010.run()
        observations_cv010 = pd.read_csv(artifacts_cv010['observations'])
        events_cv010 = pd.read_csv(artifacts_cv010['events'])
        result_cv010 = fit_commitment_params(
            events_df=events_cv010,
            observations_df=observations_cv010,
            regime="high_stress_event_rich",
            mechanism="er_stress",
            stress_metric="er_stress"
        )

    # Run with CV = 0.20 (2x higher)
    design_cv020 = IdentifiabilityDesign(str(config_path))
    design_cv020.truth['phase1']['growth_cv'] = 0.20
    design_cv020.truth['phase1']['stress_sensitivity_cv'] = 0.16
    design_cv020.truth['phase1']['hazard_scale_cv'] = 0.24

    with tempfile.TemporaryDirectory() as tmpdir:
        runner_cv020 = IdentifiabilityRunner(design_cv020, Path(tmpdir), run_id="test_coupling_cv020")
        artifacts_cv020 = runner_cv020.run()
        observations_cv020 = pd.read_csv(artifacts_cv020['observations'])
        events_cv020 = pd.read_csv(artifacts_cv020['events'])
        result_cv020 = fit_commitment_params(
            events_df=events_cv020,
            observations_df=observations_cv020,
            regime="high_stress_event_rich",
            mechanism="er_stress",
            stress_metric="er_stress"
        )

    print(f"\nCoupling Smoke Test:")
    print(f"  CV=0.10: threshold={result_cv010['threshold']:.2f}, λ0={result_cv010['baseline_hazard_per_h']:.3f}, p={result_cv010['sharpness_p']:.1f}")
    print(f"  CV=0.20: threshold={result_cv020['threshold']:.2f}, λ0={result_cv020['baseline_hazard_per_h']:.3f}, p={result_cv020['sharpness_p']:.1f}")

    # Check that params don't drift wildly (loose bounds)
    # Threshold should be within ±0.20 absolute
    threshold_drift = abs(result_cv020['threshold'] - result_cv010['threshold'])
    assert threshold_drift < 0.20, \
        f"Threshold drifts by {threshold_drift:.2f} across CV settings (possible coupling)"

    # p should be within ±1.5 absolute
    p_drift = abs(result_cv020['sharpness_p'] - result_cv010['sharpness_p'])
    assert p_drift < 1.5, \
        f"Sharpness drifts by {p_drift:.1f} across CV settings (possible coupling)"

    print(f"  Threshold drift: {threshold_drift:.2f} (< 0.20) ✅")
    print(f"  Sharpness drift: {p_drift:.1f} (< 1.5) ✅")
    print("✅ No strong coupling detected between Phase 1 and Phase 2A")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 2C.1: IDENTIFIABILITY SUITE - ABLATION TESTS")
    print("=" * 70)

    test_ablation_phase2a_off()
    test_ablation_phase1_off()
    test_coupling_smoke()

    print("\n" + "=" * 70)
    print("✅ ALL ABLATION TESTS PASSED")
    print("=" * 70)
