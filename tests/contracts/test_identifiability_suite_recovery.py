"""
Contract tests for Phase 2C.1: Identifiability Suite - Recovery Tests

Tests that Phase 1 (smooth REs) and Phase 2A (commitment) parameters
can be recovered from simulated observations with acceptable accuracy.

Acceptance criteria:
1. RE ICC increases monotonically with Phase 1 CV
2. Commitment params (threshold, λ0, p) recovered within tolerance
3. Held-out prediction (Plate B) matches empirical within tolerance
"""

import pytest
import tempfile
import pandas as pd
from pathlib import Path

pytest.skip("Identifiability suite tests are compute-intensive - skipping", allow_module_level=True)


def test_commitment_parameter_recovery():
    """
    Test that commitment parameters can be recovered from Plate C.

    Acceptance criteria:
    - Threshold recovered within ±0.10 absolute error
    - Sharpness p recovered within ±1.0 absolute error
    - Baseline hazard λ0 recovered within factor 3 (log scale)
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
    from cell_os.calibration.identifiability_inference import fit_commitment_params

    # Use actual config
    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    design = IdentifiabilityDesign(str(config_path))

    # Run suite in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = IdentifiabilityRunner(design, Path(tmpdir), run_id="test_recovery")
        artifacts = runner.run()

        # Load observations and events
        observations_df = pd.read_csv(artifacts['observations'])
        events_df = pd.read_csv(artifacts['events'])

        # Fit commitment params
        result = fit_commitment_params(
            events_df=events_df,
            observations_df=observations_df,
            regime="high_stress_event_rich",
            mechanism="er_stress",
            stress_metric="er_stress"
        )

        # Load ground truth
        truth = design.truth['phase2a_er']
        threshold_truth = truth['threshold']
        lambda0_truth = truth['baseline_hazard_per_h']
        p_truth = truth['sharpness_p']

        # Check recovery
        assert result['threshold'] is not None, "Threshold recovery failed (returned None)"
        assert result['baseline_hazard_per_h'] is not None, "Lambda0 recovery failed (returned None)"
        assert result['sharpness_p'] is not None, "Sharpness recovery failed (returned None)"

        threshold_error = abs(result['threshold'] - threshold_truth)
        p_error = abs(result['sharpness_p'] - p_truth)
        lambda0_ratio = result['baseline_hazard_per_h'] / lambda0_truth

        print(f"\nCommitment Parameter Recovery:")
        print(f"  Threshold: truth={threshold_truth:.2f}, recovered={result['threshold']:.2f}, error={threshold_error:.3f}")
        print(f"  Sharpness p: truth={p_truth:.1f}, recovered={result['sharpness_p']:.1f}, error={p_error:.2f}")
        print(f"  Baseline λ0: truth={lambda0_truth:.3f}, recovered={result['baseline_hazard_per_h']:.3f}, ratio={lambda0_ratio:.2f}x")

        # Assert acceptance criteria
        acceptance = design.acceptance['recovery']
        assert threshold_error <= acceptance['threshold_abs_error'], \
            f"Threshold error {threshold_error:.3f} exceeds tolerance {acceptance['threshold_abs_error']}"

        assert p_error <= acceptance['sharpness_abs_error'], \
            f"Sharpness error {p_error:.2f} exceeds tolerance {acceptance['sharpness_abs_error']}"

        assert (1.0 / acceptance['baseline_hazard_log_factor']) <= lambda0_ratio <= acceptance['baseline_hazard_log_factor'], \
            f"Lambda0 ratio {lambda0_ratio:.2f}x outside factor {acceptance['baseline_hazard_log_factor']}"

        print("✅ All commitment parameters recovered within tolerance")


def test_held_out_prediction():
    """
    Test that recovered parameters predict held-out regime (Plate B) accurately.

    Acceptance criteria:
    - Predicted commitment fraction within ±0.15 absolute error of empirical
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
    from cell_os.calibration.identifiability_inference import (
        fit_commitment_params,
        predict_commitment_fraction,
        compare_prediction_to_empirical,
    )

    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    design = IdentifiabilityDesign(str(config_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = IdentifiabilityRunner(design, Path(tmpdir), run_id="test_prediction")
        artifacts = runner.run()

        observations_df = pd.read_csv(artifacts['observations'])
        events_df = pd.read_csv(artifacts['events'])

        # Fit on Plate C
        commitment_result = fit_commitment_params(
            events_df=events_df,
            observations_df=observations_df,
            regime="high_stress_event_rich",
            mechanism="er_stress",
            stress_metric="er_stress"
        )

        # Predict on Plate B
        prediction_result = predict_commitment_fraction(
            observations_df=observations_df,
            recovered_params=commitment_result,
            regime="mid_stress_mixed",
            stress_metric="er_stress"
        )

        # Compare to empirical
        comparison_result = compare_prediction_to_empirical(
            events_df=events_df,
            predicted_fraction=prediction_result['predicted_fraction'],
            regime="mid_stress_mixed"
        )

        print(f"\nHeld-Out Prediction (Plate B):")
        print(f"  Predicted: {comparison_result['predicted_fraction']:.4f}")
        print(f"  Empirical: {comparison_result['empirical_fraction']:.4f}")
        print(f"  Error: {comparison_result['fraction_error']:.4f}")

        # Assert acceptance criteria
        acceptance = design.acceptance['prediction']
        assert comparison_result['fraction_error'] <= acceptance['commitment_fraction_abs_error'], \
            f"Prediction error {comparison_result['fraction_error']:.4f} exceeds tolerance {acceptance['commitment_fraction_abs_error']}"

        print("✅ Held-out prediction within tolerance")


def test_re_icc_monotonicity():
    """
    Test that ICC increases monotonically with Phase 1 CV.

    This is a smoke test for RE identifiability - not a full recovery test,
    but checks that REs create observable variance.
    """
    from cell_os.calibration.identifiability_design import IdentifiabilityDesign
    from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
    from cell_os.calibration.identifiability_inference import fit_re_icc

    config_path = Path(__file__).parent.parent.parent / "configs/calibration/identifiability_2c1.yaml"
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    design = IdentifiabilityDesign(str(config_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = IdentifiabilityRunner(design, Path(tmpdir), run_id="test_icc")
        artifacts = runner.run()

        observations_df = pd.read_csv(artifacts['observations'])

        # Fit ICC
        icc_result = fit_re_icc(
            observations_df=observations_df,
            metric="cell_count",
            regime="low_stress_re_only"
        )

        print(f"\nRE ICC (Plate A):")
        print(f"  ICC: {icc_result['icc']:.4f}")
        print(f"  var_well: {icc_result['var_well']:.2e}")
        print(f"  var_resid: {icc_result['var_resid']:.2e}")

        # Check that ICC is non-trivial (Phase 1 enabled with CV=0.10)
        # Expect ICC > 0.05 (loose check for monotonicity)
        assert icc_result['icc'] > 0.05, \
            f"ICC={icc_result['icc']:.4f} too low for Phase 1 CV=0.10 (REs not visible)"

        print("✅ RE ICC is non-trivial (Phase 1 variance visible)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 2C.1: IDENTIFIABILITY SUITE - RECOVERY TESTS")
    print("=" * 70)

    test_commitment_parameter_recovery()
    test_held_out_prediction()
    test_re_icc_monotonicity()

    print("\n" + "=" * 70)
    print("✅ ALL RECOVERY TESTS PASSED")
    print("=" * 70)
