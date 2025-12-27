"""
SNR Guardrail Tests

Validates that the calibration profile provides SNR-based guardrails
to prevent the agent from learning morphology shifts in sub-noise regimes.

Phase 4 feature: requires floor.observable = true
"""

from __future__ import annotations

import pytest
import json
import tempfile
from pathlib import Path

from cell_os.calibration.profile import CalibrationProfile


@pytest.fixture
def darkfix_calibration_profile():
    """Load Phase 4 darkfix calibration profile."""
    report_path = Path("results/cal_beads_dyes_seed42_darkfix/calibration/calibration_report.json")
    if not report_path.exists():
        pytest.skip("Phase 4 darkfix calibration not found; run calibration first")
    return CalibrationProfile(report_path)


@pytest.mark.contracts
def test_floor_statistics_accessible(darkfix_calibration_profile):
    """
    Contract: Floor mean and sigma must be accessible via CalibrationProfile.

    This enables SNR-based exposure policies in the agent.
    """
    profile = darkfix_calibration_profile

    # Floor should be observable in Phase 4
    assert profile.floor_observable(), "Floor must be observable in Phase 4"

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        # Floor mean should be positive (bias applied)
        floor_mean = profile.floor_mean(ch)
        assert floor_mean is not None, f"Floor mean missing for {ch}"
        assert floor_mean > 0, f"Floor mean for {ch} is {floor_mean} (expected > 0)"

        # Floor sigma should be positive (noise applied)
        floor_sigma = profile.floor_sigma(ch)
        assert floor_sigma is not None, f"Floor sigma missing for {ch}"
        assert floor_sigma > 0, f"Floor sigma for {ch} is {floor_sigma} (expected > 0)"

        print(f"✓ {ch}: floor mean={floor_mean:.4f} AU, sigma={floor_sigma:.4f} AU")


@pytest.mark.contracts
def test_is_above_noise_floor_guardrail(darkfix_calibration_profile):
    """
    Contract: is_above_noise_floor() must correctly classify signals.

    Test cases:
      1. Signal >> floor (e.g., 10 AU) → should be above threshold
      2. Signal ~ floor (e.g., 0.3 AU) → should be below 5σ threshold
      3. Signal < floor mean → definitely below threshold
    """
    profile = darkfix_calibration_profile

    ch = 'er'
    floor_mean = profile.floor_mean(ch)
    floor_sigma = profile.floor_sigma(ch)

    # Case 1: High signal (well above noise)
    high_signal = 10.0  # AU
    is_above, reason = profile.is_above_noise_floor(high_signal, ch, k=5.0)
    assert is_above == True, f"High signal {high_signal} should be above noise floor"
    assert reason is None

    # Case 2: Signal near floor mean (below 5σ threshold)
    low_signal = floor_mean + 2.0 * floor_sigma  # 2σ above floor
    is_above, reason = profile.is_above_noise_floor(low_signal, ch, k=5.0)
    assert is_above == False, f"Low signal {low_signal} should be below 5σ threshold"
    assert reason is not None
    assert "below 5.0σ threshold" in reason

    # Case 3: Signal at floor mean (definitely below threshold)
    floor_signal = floor_mean
    is_above, reason = profile.is_above_noise_floor(floor_signal, ch, k=5.0)
    assert is_above == False
    assert reason is not None

    print(f"✓ SNR guardrail correctly classifies signals (floor={floor_mean:.4f}±{floor_sigma:.4f} AU)")


@pytest.mark.contracts
def test_minimum_detectable_signal(darkfix_calibration_profile):
    """
    Contract: minimum_detectable_signal() must return floor_mean + k*floor_sigma.

    This threshold defines when the agent can trust morphology shifts.
    """
    profile = darkfix_calibration_profile

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    k = 5.0  # Conservative threshold (5σ)

    for ch in channels:
        floor_mean = profile.floor_mean(ch)
        floor_sigma = profile.floor_sigma(ch)
        min_detectable = profile.minimum_detectable_signal(ch, k=k)

        assert min_detectable is not None, f"Minimum detectable signal missing for {ch}"

        # Should equal floor_mean + k*floor_sigma
        expected = floor_mean + k * floor_sigma
        assert abs(min_detectable - expected) < 1e-6, (
            f"Minimum detectable signal for {ch} is {min_detectable:.4f}, "
            f"expected {expected:.4f} (floor={floor_mean:.4f}, sigma={floor_sigma:.4f})"
        )

        print(f"✓ {ch}: min_detectable={min_detectable:.4f} AU (= {floor_mean:.4f} + {k}*{floor_sigma:.4f})")


@pytest.mark.contracts
def test_snr_guardrails_in_apply_calibration(darkfix_calibration_profile):
    """
    Contract: apply_calibration must add SNR warnings when signal is below threshold.

    This prevents the agent from learning from dim, sub-noise observations.
    """
    from cell_os.analysis.apply_calibration import apply_calibration_to_observation

    profile = darkfix_calibration_profile

    # Create synthetic observation with dim signal (below 5σ threshold)
    floor_mean_er = profile.floor_mean('er')
    floor_sigma_er = profile.floor_sigma('er')

    dim_signal = floor_mean_er + 2.0 * floor_sigma_er  # 2σ above floor (below 5σ threshold)

    obs = {
        "well_id": "H12",  # Center well
        "morphology": {
            "er": dim_signal,
            "mito": 50.0,  # Bright enough
            "nucleus": 60.0,
            "actin": 45.0,
            "rna": 55.0
        }
    }

    # Apply calibration
    obs_cal = apply_calibration_to_observation(obs, profile)

    # Should have SNR warnings for 'er' channel
    assert "snr_warnings" in obs_cal["calibration"], "SNR warnings should be present for dim signal"
    snr_warnings = obs_cal["calibration"]["snr_warnings"]

    # Find warning for 'er' channel
    er_warning = [w for w in snr_warnings if w.startswith("er:")]
    assert len(er_warning) > 0, f"Expected SNR warning for 'er' channel, got: {snr_warnings}"

    print(f"✓ SNR warning triggered for dim signal: {er_warning[0]}")


@pytest.mark.contracts
def test_snr_guardrail_disabled_when_floor_not_observable():
    """
    Contract: SNR guardrails must be conservative when floor is not observable.

    If floor.observable = false, is_above_noise_floor() must return (False, reason).
    This prevents agent from using unreliable data.
    """
    # Create synthetic calibration report with floor.observable = false
    report = {
        "schema_version": "bead_plate_calibration_report_v1",
        "channels": ["er", "mito", "nucleus", "actin", "rna"],
        "floor": {
            "observable": False,
            "reason": "DARK wells return literal 0.0 with zero variance"
        },
        "vignette": {"observable": False},
        "saturation": {"observable": False},
        "quantization": {"observable": False},
        "exposure_recommendations": {}
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report_path = Path(f.name)
        json.dump(report, f)

    try:
        profile = CalibrationProfile(report_path)

        # Floor should not be observable
        assert not profile.floor_observable()

        # is_above_noise_floor should return False (conservative)
        is_above, reason = profile.is_above_noise_floor(signal=10.0, channel='er', k=5.0)
        assert is_above == False, "Should be conservative when floor not observable"
        assert reason is not None
        assert "Floor not observable" in reason

        print("✓ SNR guardrail correctly disabled when floor not observable")

    finally:
        report_path.unlink()


if __name__ == '__main__':
    # Run SNR guardrail tests
    pytest.main([__file__, '-xvs'])
