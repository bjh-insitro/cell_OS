"""
Test SNR Policy Integration

Phase 4 feature: Validates that SNR policy prevents agent from learning
in sub-noise regimes when floor.observable = true.

Contract:
1. SNR policy filters/flags conditions below minimum detectable signal
2. Policy respects strict vs non-strict mode
3. Policy is disabled when floor not observable
4. Minimum detectable signals are computed correctly (floor_mean + k*floor_sigma)
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy


def create_mock_calibration_report(floor_observable: bool = True) -> dict:
    """Create mock calibration report with floor data."""
    report = {
        "schema_version": "bead_plate_calibration_report_v1",
        "created_utc": "2025-01-01T00:00:00Z",
        "channels": ["er", "mito", "nucleus", "actin", "rna"],
        "inputs": {
            "design_sha256": "mock_design",
            "detector_config_sha256": "mock_config"
        },
        "vignette": {
            "observable": True,
            "edge_multiplier": {
                "er": 0.85,
                "mito": 0.83,
                "nucleus": 0.88,
                "actin": 0.86,
                "rna": 0.84
            }
        },
        "saturation": {
            "observable": True,
            "per_channel": {
                "er": {"p99": 800.0, "confidence": "high"},
                "mito": {"p99": 900.0, "confidence": "high"},
                "nucleus": {"p99": 1000.0, "confidence": "high"},
                "actin": {"p99": 800.0, "confidence": "high"},
                "rna": {"p99": 850.0, "confidence": "high"}
            }
        },
        "quantization": {
            "observable": True,
            "per_channel": {
                "er": {"quant_step_estimate": 0.015},
                "mito": {"quant_step_estimate": 0.015},
                "nucleus": {"quant_step_estimate": 0.015},
                "actin": {"quant_step_estimate": 0.015},
                "rna": {"quant_step_estimate": 0.015}
            }
        },
        "floor": {
            "observable": floor_observable,
            "reason": None if floor_observable else "Insufficient dark wells",
            "per_channel": {
                "er": {
                    "mean": 0.25,
                    "std": 0.0,  # Computed from range in profile.py
                    "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]  # Range ~0.05, sigma ~0.01
                },
                "mito": {
                    "mean": 0.25,
                    "std": 0.0,
                    "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]
                },
                "nucleus": {
                    "mean": 0.25,
                    "std": 0.0,
                    "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]
                },
                "actin": {
                    "mean": 0.25,
                    "std": 0.0,
                    "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]
                },
                "rna": {
                    "mean": 0.25,
                    "std": 0.0,
                    "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]
                }
            } if floor_observable else {}
        },
        "exposure_recommendations": {
            "observable": True,
            "global": {
                "warnings": []
            },
            "per_channel": {
                "er": {"recommended_exposure_multiplier": 0.9}
            }
        }
    }
    return report


@pytest.fixture
def mock_calibration_profile_floor_observable():
    """Create mock CalibrationProfile with observable floor."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report = create_mock_calibration_report(floor_observable=True)
        json.dump(report, f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    yield profile

    # Cleanup
    temp_path.unlink()


@pytest.fixture
def mock_calibration_profile_floor_not_observable():
    """Create mock CalibrationProfile with non-observable floor."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report = create_mock_calibration_report(floor_observable=False)
        json.dump(report, f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    yield profile

    # Cleanup
    temp_path.unlink()


def test_snr_policy_enabled_when_floor_observable(mock_calibration_profile_floor_observable):
    """SNR policy should be enabled when floor is observable."""
    policy = SNRPolicy(mock_calibration_profile_floor_observable, threshold_sigma=5.0)
    assert policy.enabled is True


def test_snr_policy_disabled_when_floor_not_observable(mock_calibration_profile_floor_not_observable):
    """SNR policy should be disabled when floor is not observable."""
    policy = SNRPolicy(mock_calibration_profile_floor_not_observable, threshold_sigma=5.0)
    assert policy.enabled is False


def test_snr_policy_rejects_dim_signal(mock_calibration_profile_floor_observable):
    """SNR policy should reject signals below threshold."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    # Floor: mean=0.25, sigma~0.01 (from unique_values range)
    # Threshold: 0.25 + 5*0.01 ≈ 0.30 AU

    # Test signal below threshold
    is_above, reason = policy.check_measurement(signal=0.28, channel="er")
    assert is_above is False, "Signal 0.28 AU should be below 5σ threshold (~0.30 AU)"
    assert "below 5.0σ threshold" in reason


def test_snr_policy_accepts_bright_signal(mock_calibration_profile_floor_observable):
    """SNR policy should accept signals above threshold."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    # Floor: mean=0.25, sigma~0.01
    # Threshold: 0.25 + 5*0.01 ≈ 0.30 AU

    # Test signal above threshold
    is_above, reason = policy.check_measurement(signal=0.50, channel="er")
    assert is_above is True, "Signal 0.50 AU should be above 5σ threshold (~0.30 AU)"
    assert reason is None


def test_snr_policy_minimum_detectable_signals(mock_calibration_profile_floor_observable):
    """Minimum detectable signals should be computed correctly."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    mds = policy.minimum_detectable_signals()

    # All channels should have MDS ≈ 0.30 AU (0.25 + 5*0.01)
    for ch in ["er", "mito", "nucleus", "actin", "rna"]:
        assert mds[ch] is not None
        # Floor mean=0.25, sigma≈0.05/6≈0.0083, threshold=0.25+5*0.0083≈0.29
        assert 0.29 <= mds[ch] <= 0.31, f"{ch} MDS should be ~0.30 AU, got {mds[ch]}"


def test_snr_policy_strict_mode_rejects_condition(mock_calibration_profile_floor_observable):
    """Strict mode should reject conditions with ANY channel below threshold."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=True)

    # Condition with one dim channel (er=0.28) and rest bright
    condition = {
        "compound": "DMSO",
        "dose_uM": 0.0,
        "time_h": 12.0,
        "feature_means": {
            "er": 0.28,        # Below threshold (~0.30)
            "mito": 0.50,      # Above threshold
            "nucleus": 0.60,   # Above threshold
            "actin": 0.55,     # Above threshold
            "rna": 0.52        # Above threshold
        }
    }

    is_valid, warnings, _ = policy.check_condition_summary(condition)
    assert is_valid is False, "Strict mode should reject condition with dim channel"
    assert len(warnings) >= 1, "Should have warning for dim er channel"
    assert any("er" in w for w in warnings), "Warning should mention er channel"


def test_snr_policy_lenient_mode_allows_condition(mock_calibration_profile_floor_observable):
    """Lenient mode should allow conditions with warnings (agent decides)."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)

    # Condition with one dim channel
    condition = {
        "compound": "DMSO",
        "dose_uM": 0.0,
        "time_h": 12.0,
        "feature_means": {
            "er": 0.28,        # Below threshold
            "mito": 0.50,      # Above threshold
            "nucleus": 0.60,
            "actin": 0.55,
            "rna": 0.52
        }
    }

    is_valid, warnings, _ = policy.check_condition_summary(condition)
    assert is_valid is True, "Lenient mode should allow condition with warnings"
    assert len(warnings) >= 1, "Should have warning for dim channel"


def test_snr_policy_filter_observation_strict_mode(mock_calibration_profile_floor_observable):
    """Filter observation should remove dim conditions in strict mode."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=True)

    observation = {
        "design_id": "test_design",
        "conditions": [
            {
                "compound": "DMSO",
                "dose_uM": 0.0,
                "time_h": 12.0,
                "feature_means": {
                    "er": 0.28,  # Dim (below threshold)
                    "mito": 0.28,
                    "nucleus": 0.28,
                    "actin": 0.28,
                    "rna": 0.28
                }
            },
            {
                "compound": "tBHQ",
                "dose_uM": 10.0,
                "time_h": 12.0,
                "feature_means": {
                    "er": 0.50,  # Bright (above threshold)
                    "mito": 0.60,
                    "nucleus": 0.70,
                    "actin": 0.65,
                    "rna": 0.58
                }
            }
        ]
    }

    filtered_obs = policy.filter_observation(observation, annotate=True)

    # Strict mode should reject dim condition
    assert len(filtered_obs["conditions"]) == 1, "Should have 1 valid condition"
    assert filtered_obs["conditions"][0]["compound"] == "tBHQ", "Should keep bright condition"

    # Check SNR policy summary
    assert "snr_policy_summary" in filtered_obs
    assert filtered_obs["snr_policy_summary"]["n_conditions_rejected"] == 1
    assert filtered_obs["snr_policy_summary"]["n_conditions_accepted"] == 1


def test_snr_policy_filter_observation_lenient_mode(mock_calibration_profile_floor_observable):
    """Filter observation should annotate but keep all conditions in lenient mode."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)

    observation = {
        "design_id": "test_design",
        "conditions": [
            {
                "compound": "DMSO",
                "dose_uM": 0.0,
                "time_h": 12.0,
                "feature_means": {
                    "er": 0.28,  # Dim
                    "mito": 0.28,
                    "nucleus": 0.28,
                    "actin": 0.28,
                    "rna": 0.28
                }
            }
        ]
    }

    filtered_obs = policy.filter_observation(observation, annotate=True)

    # Lenient mode should keep all conditions
    assert len(filtered_obs["conditions"]) == 1, "Should keep dim condition with warnings"

    # Check SNR annotation on condition
    assert "snr_policy" in filtered_obs["conditions"][0]
    snr_meta = filtered_obs["conditions"][0]["snr_policy"]
    assert snr_meta["is_valid"] is True, "Lenient mode: is_valid=True even with warnings"
    assert len(snr_meta["warnings"]) > 0, "Should have warnings for dim channels"


def test_snr_policy_summary(mock_calibration_profile_floor_observable):
    """Policy summary should show configuration and thresholds."""
    profile = mock_calibration_profile_floor_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=True)

    summary = policy.summary()

    assert summary["enabled"] is True
    assert summary["threshold_sigma"] == 5.0
    assert summary["strict_mode"] is True
    assert "minimum_detectable_signals_AU" in summary
    assert "STRICT" in summary["policy"]


def test_snr_policy_disabled_summary(mock_calibration_profile_floor_not_observable):
    """Policy summary should indicate when disabled."""
    profile = mock_calibration_profile_floor_not_observable
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    summary = policy.summary()

    assert summary["enabled"] is False
    assert "reason" in summary
    assert "Floor not observable" in summary.get("reason", "") or "Insufficient dark wells" in summary.get("reason", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
